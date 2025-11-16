# mpesa_handler.py — FINAL (strict idempotency + Daraja auto-verify + Twilio SMS if configured)
# Save as mpesa_handler.py in project root
# ------------------------------------------------------------------------
import os
import sys
import json
import time
import logging
import sqlite3
import traceback
import requests

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional
from flask import current_app
from flask import Blueprint, request, jsonify

from models import db, Tenant, Payment


from utils import _normalize_msisdn, _send_sms  # ✅ absolute import fix
 # optional helper imports
from mpesa_core import process_direct_payment  # ✅ absolute import fix

# Try to import Flask-SQLAlchemy models & extensions if your project has them.
_USE_ORM = False
try:
    # extensions.py should define `db` and `socketio` if using SQLAlchemy + SocketIO
    from extensions import db, socketio  # type: ignore
    # models.py should define Tenant, Payment, AuditLog, User if present
    from models import Tenant, Payment, AuditLog  # type: ignore
    _USE_ORM = True
except Exception:
    # fallback, we will use local raw DB helpers (sqlite/postgres) below
    socketio = None
    db = None
    Tenant = None
    Payment = None
    AuditLog = None

# Provide a blueprint (no url_prefix so it registers under root routes used in conversation)
mpesa_bp = Blueprint("mpesa_bp", __name__)

# Database Config
# -------------------------
DB_PATH = "rentana_full.db"
DEFAULT_PAYBILL = "174379"

def _connect():
    """Create and return a SQLite connection with Row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# -------------------------
# Logging Setup
# -------------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
LOG_FILE = os.path.join(BASE_DIR, "mpesa.log")

os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logger = logging.getLogger(__name__)

# Also log to console (for dev/debug)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(console_handler)

# -------------------------
# Optional ReportLab (receipt)
# -------------------------
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False

# -------------------------
# Optional Twilio
# -------------------------
try:
    from twilio.rest import Client as TwilioClient
    TWILIO_AVAILABLE = True
except Exception:
    TWILIO_AVAILABLE = False

# -------------------------
# Optional Postgres libs
# -------------------------
try:
    import psycopg2
    import psycopg2.extras
    from psycopg2 import IntegrityError as PGIntegrityError  # type: ignore
    PSYCOPG2_AVAILABLE = True
except Exception:
    psycopg2 = None
    PGIntegrityError = None
    PSYCOPG2_AVAILABLE = False

# Use DB URL detection to pick backend
DB_URL = os.getenv("DATABASE_URL")
DB_SQLITE_PATH = os.path.join(BASE_DIR, "rentana_full.db")
RECEIPT_DIR = os.path.join(BASE_DIR, "static", "receipts")
os.makedirs(RECEIPT_DIR, exist_ok=True)

# Daraja config
DARAJA_CONSUMER_KEY = os.getenv("DARAJA_CONSUMER_KEY", os.getenv("SANDBOX_CONSUMER_KEY"))
DARAJA_CONSUMER_SECRET = os.getenv("DARAJA_CONSUMER_SECRET", os.getenv("SANDBOX_CONSUMER_SECRET"))
DARAJA_ENV = os.getenv("DARAJA_ENV", "sandbox").lower()
DARAJA_BASE = "https://api.safaricom.co.ke" if DARAJA_ENV == "production" else "https://sandbox.safaricom.co.ke"
_OAUTH_TOKEN_CACHE = {"token": None, "expiry": 0}

# Twilio
TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN")
TWILIO_FROM = os.getenv("TWILIO_FROM")

# Paybill default
DEFAULT_PAYBILL = os.getenv("DEFAULT_PAYBILL", os.getenv("SANDBOX_SHORTCODE", "600000"))

# Fallback IntegrityError
try:
    from psycopg2 import IntegrityError as IntegrityError  # type: ignore
except Exception:
    IntegrityError = sqlite3.IntegrityError

# -------------------------
# DB helper functions (fallback if not using ORM)
# -------------------------
_USE_PG = False
if DB_URL and DB_URL.startswith(("postgres://", "postgresql://")) and PSYCOPG2_AVAILABLE:
    _USE_PG = True
    logger.info("DB: configured to use PostgreSQL (psycopg2 available)")
else:
    logger.info("DB: using SQLite fallback (or SQLAlchemy ORM if present)")

def _pg_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=psycopg2.extras.RealDictCursor)

def _sqlite_conn():
    conn = sqlite3.connect(DB_SQLITE_PATH, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def _connect():
    if _USE_PG:
        return _pg_conn()
    return _sqlite_conn()

def _ensure_tables():
    """Create minimal tables when ORM isn't used."""
    if _USE_ORM:
        logger.info("ORM present — skipping fallback table creation.")
        return
    if _USE_PG:
        q = """
        CREATE TABLE IF NOT EXISTS "user" (
            id SERIAL PRIMARY KEY,
            email VARCHAR(256) UNIQUE,
            paybill_number VARCHAR(50),
            till_number VARCHAR(50),
            phone_number VARCHAR(50)
        );
        CREATE TABLE IF NOT EXISTS tenant (
            id SERIAL PRIMARY KEY,
            owner_id INTEGER NOT NULL,
            name VARCHAR(256),
            phone VARCHAR(80),
            house_no VARCHAR(80),
            monthly_rent NUMERIC DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS payment (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER,
            amount NUMERIC,
            transaction_id TEXT UNIQUE,
            note TEXT,
            paid_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT now()
        );
        """
        conn = None
        try:
            conn = _pg_conn()
            cur = conn.cursor()
            cur.execute(q)
            conn.commit()
            cur.close()
            logger.info("Ensured Postgres tables exist (fallback).")
        except Exception:
            logger.exception("Failed to ensure Postgres tables.")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()
    else:
        conn = _sqlite_conn()
        try:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS "user" (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE,
                    paybill_number TEXT,
                    till_number TEXT,
                    phone_number TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tenant (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_id INTEGER NOT NULL,
                    name TEXT,
                    phone TEXT,
                    house_no TEXT,
                    monthly_rent REAL DEFAULT 0
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS payment (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id INTEGER,
                    amount REAL,
                    transaction_id TEXT UNIQUE,
                    note TEXT,
                    paid_at TEXT,
                    created_at TEXT
                )
            """)
            conn.commit()
            logger.info("Ensured SQLite tables exist (fallback).")
        except Exception:
            logger.exception("Failed to ensure SQLite tables (fallback).")
            conn.rollback()
        finally:
            conn.close()

# Ensure fallback tables exist at import time if needed
try:
    _ensure_tables()
except Exception:
    logger.exception("Error running _ensure_tables()")

# -------------------------
# Utilities: phone normalization and DB helpers
# -------------------------
def _normalize_msisdn(msisdn):
    if not msisdn:
        return None
    s = str(msisdn).strip()
    if s.startswith("+"):
        s = s[1:]
    s = s.replace(" ", "")
    if s.startswith("254") and len(s) >= 12:
        return s
    if s.startswith("0") and len(s) == 10:
        return "254" + s[1:]
    if s.startswith("7") and len(s) == 9:
        return "254" + s
    return s

def _norm_phone_db(p: Optional[str]) -> str:
    if not p:
        return ""
    digits = "".join(ch for ch in str(p) if ch.isdigit())
    if len(digits) == 10 and digits.startswith("0"):
        digits = "254" + digits[1:]
    if len(digits) == 9 and digits.startswith("7"):
        digits = "254" + digits
    return digits

# Fallback DB helpers (raw queries)
def _tx_exists(conn, tx_id: str) -> bool:
    if not tx_id:
        return False
    cur = conn.cursor()
    if _USE_PG:
        cur.execute("SELECT 1 FROM payment WHERE transaction_id = %s LIMIT 1", (tx_id,))
        r = cur.fetchone()
        return bool(r)
    else:
        cur.execute("SELECT 1 FROM payment WHERE transaction_id=? LIMIT 1", (tx_id,))
        return cur.fetchone() is not None

def _find_tenant_by_phone(conn, phone: str):
    target = _norm_phone_db(phone)
    cur = conn.cursor()
    if _USE_PG:
        cur.execute("SELECT id, name, phone, house_no, monthly_rent, owner_id FROM tenant")
        rows = cur.fetchall()
        for r in rows:
            ph = r['phone']
            if ph and (_norm_phone_db(ph).endswith(target) or target.endswith(_norm_phone_db(ph))):
                return {"id": r['id'], "name": r['name'], "phone": r['phone'], "house_no": r['house_no'], "monthly_rent": float(r['monthly_rent'] or 0), "owner_id": r['owner_id']}
        return None
    else:
        cur.execute("SELECT id, name, phone, house_no, monthly_rent, owner_id FROM tenant")
        for tid, name, ph, house_no, rent, owner_id in cur.fetchall():
            if ph and (_norm_phone_db(ph).endswith(target) or target.endswith(_norm_phone_db(ph))):
                return {"id": tid, "name": name, "phone": ph, "house_no": house_no, "monthly_rent": rent or 0.0, "owner_id": owner_id}
        return None

def _find_tenant_by_house_and_account(conn, house_no: Optional[str], account: str):
    account = (account or "").strip()
    if not house_no:
        return None
    house_no_l = house_no.strip().lower()
    cur = conn.cursor()
    if _USE_PG:
        cur.execute("SELECT id FROM \"user\" WHERE paybill_number=%s OR till_number=%s OR phone_number=%s", (account, account, account))
        users = [r['id'] for r in cur.fetchall()]
        if not users:
            return None
        placeholders = ",".join(["%s"] * len(users))
        query = f"SELECT id, name, phone, house_no, monthly_rent, owner_id FROM tenant WHERE lower(house_no)=lower(%s) AND owner_id IN ({placeholders}) LIMIT 1"
        params = [house_no] + users
        cur.execute(query, params)
        r = cur.fetchone()
        if not r:
            return None
        return {"id": r['id'], "name": r['name'], "phone": r['phone'], "house_no": r['house_no'], "monthly_rent": float(r['monthly_rent'] or 0), "owner_id": r['owner_id']}
    else:
        cur.execute("""SELECT id FROM "user" WHERE paybill_number=? OR till_number=? OR phone_number=?""", (account, account, account))
        users = [r[0] for r in cur.fetchall()]
        if not users:
            return None
        placeholders = ",".join("?" for _ in users)
        sql = f"""SELECT id, name, phone, house_no, monthly_rent, owner_id
                  FROM tenant WHERE lower(house_no)=? AND owner_id IN ({placeholders})"""
        params = [house_no_l] + users
        cur.execute(sql, params)
        r = cur.fetchone()
        if not r:
            return None
        tid, name, ph, hno, rent, owner_id = r
        return {"id": tid, "name": name, "phone": ph, "house_no": hno, "monthly_rent": rent or 0.0, "owner_id": owner_id}

def _insert_payment(conn, tenant_id, amount, tx_id, note=None):
    now = datetime.utcnow().isoformat(timespec="seconds")
    cur = conn.cursor()
    try:
        if _USE_PG:
            cur.execute(
                "INSERT INTO payment (tenant_id, amount, transaction_id, note, paid_at, created_at) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
                (tenant_id, float(amount), tx_id, note, now, now)
            )
            new_id = cur.fetchone()['id']
            conn.commit()
            return new_id
        else:
            cur.execute(
                """INSERT INTO payment (tenant_id, amount, transaction_id, note, paid_at, created_at)
                   VALUES (?,?,?,?,?,?)""",
                (tenant_id, float(amount), tx_id, note, now, now),
            )
            conn.commit()
            return cur.lastrowid
    except Exception as e:
        # handle uniqueness / duplicates
        conn.rollback()
        text = str(e).lower()
        if "unique" in text or "duplicate" in text or isinstance(e, sqlite3.IntegrityError) or (PGIntegrityError and isinstance(e, PGIntegrityError)):
            logger.warning("Integrity error / duplicate tx ignored: %s", tx_id)
            return None
        else:
            logger.exception("Unexpected error inserting payment: %s", e)
            raise

def _total_paid(conn, tenant_id):
    cur = conn.cursor()
    if _USE_PG:
        cur.execute("SELECT SUM(amount) AS total FROM payment WHERE tenant_id=%s", (tenant_id,))
        r = cur.fetchone()
        return float(r['total'] or 0.0) if r else 0.0
    else:
        cur.execute("SELECT SUM(amount) FROM payment WHERE tenant_id=?", (tenant_id,))
        r = cur.fetchone()
        return float(r[0] or 0.0)

# -------------------------
# Receipt creation
# -------------------------
def _create_pdf_receipt(tenant, amount, tx_id, remaining):
    filename = f"receipt_{tenant['id']}_{tx_id}.pdf"
    out = os.path.join(RECEIPT_DIR, filename)
    try:
        if REPORTLAB_AVAILABLE:
            c = canvas.Canvas(out, pagesize=A4)
            c.setFont("Helvetica-Bold", 14)
            c.drawString(50, 800, "Rentana – Payment Receipt")
            c.setFont("Helvetica", 11)
            c.drawString(50, 780, f"Tenant: {tenant['name']} (House {tenant['house_no']})")
            c.drawString(50, 760, f"Amount: Ksh {float(amount):,.2f}")
            c.drawString(50, 740, f"Transaction ID: {tx_id}")
            c.drawString(50, 720, f"Remaining Balance: Ksh {float(remaining):,.2f}")
            c.drawString(50, 700, f"Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
            c.showPage()
            c.save()
        else:
            with open(out, "w", encoding="utf-8") as f:
                f.write(f"Tenant {tenant['name']} | {tenant['house_no']}\n")
                f.write(f"Amount {amount}\nTx {tx_id}\nBalance {remaining}\n")
        return out
    except Exception:
        logger.exception("Error creating receipt")
        return None

# -------------------------
# Twilio SMS
# -------------------------
def _send_sms(phone, message):
    if not (TWILIO_AVAILABLE and TWILIO_SID and TWILIO_TOKEN and TWILIO_FROM):
        logger.info("SMS not sent (Twilio not configured). Preview: %s", message)
        return
    try:
        client = TwilioClient(TWILIO_SID, TWILIO_TOKEN)
        client.messages.create(body=message, from_=TWILIO_FROM, to=phone)
        logger.info("SMS sent to %s", phone)
    except Exception:
        logger.exception("Twilio error when sending SMS")

# -------------------------
# Daraja oauth + verify
# -------------------------
def _get_oauth_token() -> Optional[str]:
    if not (DARAJA_CONSUMER_KEY and DARAJA_CONSUMER_SECRET):
        logger.warning("Daraja credentials not configured.")
        return None
    now_ts = int(time.time())
    if _OAUTH_TOKEN_CACHE["token"] and _OAUTH_TOKEN_CACHE["expiry"] - now_ts > 30:
        return _OAUTH_TOKEN_CACHE["token"]
    url = f"{DARAJA_BASE}/oauth/v1/generate?grant_type=client_credentials"
    try:
        resp = requests.get(url, auth=(DARAJA_CONSUMER_KEY, DARAJA_CONSUMER_SECRET), timeout=10)
        j = resp.json()
        token = j.get("access_token")
        expires_in = int(j.get("expires_in", 3600))
        _OAUTH_TOKEN_CACHE["token"] = token
        _OAUTH_TOKEN_CACHE["expiry"] = now_ts + expires_in
        logger.info("Got Daraja oauth token (masked)")
        return token
    except Exception:
        logger.exception("Daraja token fetch failed")
        return None

def verify_transaction_with_daraja(transaction_id: str, amount: float, msisdn: str, shortcode: str) -> bool:
    token = _get_oauth_token()
    if not token:
        logger.debug("Daraja token unavailable; verification skipped")
        return False
    url = f"{DARAJA_BASE}/mpesa/transactionstatus/v1/query"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {
        "CommandID": "TransactionStatusQuery",
        "PartyA": shortcode,
        "IdentifierType": "4",
        "Remarks": "verify",
        "Initiator": os.getenv("DARAJA_INITIATOR", "testapi"),
        "SecurityCredential": os.getenv("DARAJA_SECURITY_CREDENTIAL", ""),
        "TransactionID": transaction_id,
        "Occasion": "verify"
    }
    try:
        resp = requests.post(url, json=body, headers=headers, timeout=12)
        if resp.status_code not in (200, 201):
            logger.error("Daraja verify failed HTTP %s: %s", resp.status_code, resp.text)
            return False
        resp_text = str(resp.text).lower()
        return any(k in resp_text for k in ["completed", "success", "accepted"])
    except Exception:
        logger.exception("Daraja verify exception")
        return False

# -------------------------
# Core processing function (ORM-aware)
def process_direct_payment(account, amount, tx_id, note=None, msisdn=None):
    """
    Handles M-Pesa payment confirmation:
    - Finds tenant via house_no (e.g. '600001#5' → 5)
    - Falls back to phone number if no match
    - Inserts payment, updates tenant totals
    - Emits socket + SMS updates
    """
    try:
        tx_id = (tx_id or "").strip()
        if not tx_id:
            return {"ok": False, "reason": "missing_tx_id"}

        # Validate and normalize amount
        try:
            amount_val = Decimal(str(amount or "0"))
        except (InvalidOperation, TypeError):
            logger.warning("Invalid amount for tx %s: %r", tx_id, amount)
            return {"ok": False, "reason": "invalid_amount"}
        if amount_val <= 0:
            return {"ok": False, "reason": "invalid_amount"}

        account = (account or "").strip()
        msisdn_norm = _normalize_msisdn(msisdn)
        house_no = None

        # Extract house_no (e.g. 600001#5 → 5)
        if "#" in account:
            _, house_no = account.split("#", 1)
            house_no = house_no.strip()

        # ORM path only (SQLite fallback removed)
        if _USE_ORM and Tenant is not None:
            try:
                tenant = None

                # Lookup by house number first
                if house_no:
                    tenant = Tenant.query.filter(Tenant.house_no == house_no).first()

                # Fallback to phone match
                if not tenant and msisdn_norm:
                    tenant = Tenant.query.filter(Tenant.phone.like(f"%{msisdn_norm[-6:]}%")).first()

                if not tenant:
                    return {"ok": False, "reason": "tenant_not_found"}

                # Prevent duplicate tx
                if Payment.query.filter_by(transaction_id=tx_id).first():
                    return {"ok": False, "reason": "duplicate_tx"}
                
                #create new payment record
                p = Payment(
                    transaction_id=tx_id,
                    tenant_id=tenant.id,
                    amount=float(amount_val),
                    paid_at=datetime.utcnow(),
                    note=note or f"M-Pesa payment from {msisdn_norm}",
                )

                db.session.add(p)

                # Commit the payment first available for calculations
                db.session.commit()

                # Recalculate totals using total_paid() method
                total_paid_now = tenant.total_paid()
                total_due_now = tenant.total_due_since()

                #compute locally
                balance_now = max(0.0, total_due_now - total_paid_now)
                
                current_app.logger.info(f"Tenant {tenant.name} new balance calculated: {balance_now}")



                # Notify tenant via SMS
                sms_text = (
                    f"Dear {tenant.name}, payment of Ksh {int(amount_val):,} "
                    f"for House {tenant.house_no} received. "
                    f"Balance: Ksh {int(tenant.balance):,}."
                )
                try:
                    _send_sms(tenant.phone, sms_text)
                except Exception:
                    logger.exception("SMS send failed")

                # Emit real-time update to dashboard
                if socketio:
                    socketio.emit(
                        "payment_update",
                        {
                            "tenant_id": tenant.id,
                            "tenant_name": tenant.name,
                            "amount": float(amount_val),
                            "trans_id": tx_id,
                            "new_total_paid": float(tenant.total_paid()),

                            "new_balance": float(tenant.balance),
                        },
                        broadcast=True,
                    )

                return {
                    "ok": True,
                    "tenant_id": tenant.id,
                    "tenant_name": tenant.name,
                    "amount": float(amount_val),
                    "tx_id": tx_id,
                }

            except Exception:
                db.session.rollback()
                logger.exception("Error updating tenant/payment")
                return {"ok": False, "reason": "db_error"}

        else:
            logger.error("ORM not available — cannot process payment via direct DB.")
            return {"ok": False, "reason": "orm_unavailable"}

    except Exception:
        logger.exception("Unexpected exception in process_direct_payment")
        return {"ok": False, "reason": "unexpected_error"}

# Simulation helpers
# -------------------------
def simulate_payment(phone, amount):
    from datetime import datetime
    tx_id = f"SIM{int(datetime.utcnow().timestamp())}"
    conn = None
    try:
        if _USE_ORM and Tenant is not None:
            tenant = Tenant.query.filter(Tenant.phone.like(f"%{_norm_phone_db(phone)[-6:]}%")).first()
            if not tenant:
                return {"ok": False, "reason": "tenant_not_found", "phone": phone}
            account = f"{DEFAULT_PAYBILL}#{tenant.house_no}"
            return process_direct_payment(account, amount, tx_id, note="Simulated payment via phone", msisdn=phone)
        else:
            conn = _connect()
            tenant = _find_tenant_by_phone(conn, phone)
            if not tenant:
                return {"ok": False, "reason": "tenant_not_found", "phone": phone}
            account = f"{DEFAULT_PAYBILL}#{tenant.get('house_no')}"
            return process_direct_payment(account, amount, tx_id, note="Simulated payment via phone", msisdn=phone)
    finally:
        try:
            if conn:
                conn.close()
        except Exception:
            pass

def simulate_direct_payment(account, amount):
    from datetime import datetime
    tx_id = f"SIMD{int(datetime.utcnow().timestamp())}"
    if "#" in account:
        sc, house = account.split("#", 1)
        account_numeric = sc.strip() or DEFAULT_PAYBILL
        house_no = house.strip()
    else:
        account_numeric = DEFAULT_PAYBILL
        house_no = account.strip()
    if _USE_ORM and Tenant is not None:
        tenant = Tenant.query.filter((Tenant.house_no == house_no) | (Tenant.id == house_no)).first()
        if not tenant:
            return {"ok": False, "reason": "tenant_not_found", "account": account}
        return process_direct_payment(f"{account_numeric}#{house_no}", amount, tx_id, note="Simulated direct payment", msisdn=tenant.phone)
    else:
        conn = _connect()
        try:
            tenant = _find_tenant_by_house_and_account(conn, house_no, account_numeric)
            if not tenant:
                return {"ok": False, "reason": "tenant_not_found", "account": account}
            return process_direct_payment(f"{account_numeric}#{house_no}", amount, tx_id, note="Simulated direct payment", msisdn=tenant.get("phone"))
        finally:
            try:
                conn.close()
            except Exception:
                pass

# -------------------------
# Daraja endpoints: validation & confirmation & test & old style aliases
# -------------------------
# -------------------------
# M-PESA Callback Endpoints
# -------------------------
# ============================================================
# M-PESA Callback Endpoints (Unified + ORM integrated version)
# ============================================================

logger = logging.getLogger(__name__)

DB_PATH = "rentana_full.db"
DEFAULT_PAYBILL = "600001"

def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# -------------------------
# /payment_callback/validate
# -------------------------
# /payment_callback/validate
# -------------------------
@mpesa_bp.route("/payment_callback/validate", methods=["POST"])
def mpesa_validate():
    """
    Called by Safaricom before payment is completed.
    Used to verify if the BillRefNumber (house_no / phone) belongs to a valid tenant.
    """
    data = request.get_json(silent=True) or {}
    logger.info("VALIDATION payload: %s", data)

    bill_ref = (
        data.get("BillRefNumber")
        or data.get("AccountReference")
        or data.get("BillRef")
        or ""
    ).strip()

    try:
        # ORM check first
        tenant = Tenant.query.filter(
            (Tenant.house_no == bill_ref) | (Tenant.phone.like(f"%{bill_ref}%"))
        ).first()

        if tenant:
            logger.info("✅ Validation Passed for BillRef: %s", bill_ref)
            return jsonify({"ResultCode": 0, "ResultDesc": "Validation Passed"}), 200
        else:
            logger.warning("❌ Validation failed for BillRef: %s", bill_ref)
            return jsonify({"ResultCode": 1, "ResultDesc": "Invalid tenant reference"}), 200

    except Exception as e:
        logger.exception("⚠️ Error during tenant validation: %s", e)
        return jsonify({"ResultCode": 1, "ResultDesc": "Validation Error"}), 200


# -------------------------
# /payment_callback/confirm
# -------------------------
@mpesa_bp.route("/payment_callback/confirm", methods=["POST"])
def mpesa_confirm():
    """
    Called by Safaricom after a successful M-Pesa C2B transaction.
    Confirms and records the payment in the database.
    """
    data = request.get_json(silent=True) or {}
    logger.info("CONFIRM payload: %s", data)

    try:
        tx_id = data.get("TransID") or data.get("transaction_id")
        amount = float(data.get("TransAmount") or data.get("Amount") or 0)
        msisdn = str(data.get("MSISDN") or data.get("Msisdn") or data.get("msisdn") or "").strip()
        bill_ref = (
            data.get("BillRefNumber")
            or data.get("AccountReference")
            or data.get("BillRef")
            or ""
        ).strip()

        note = f"M-Pesa rent payment from {msisdn}"

        result = process_direct_payment(
            bill_ref=bill_ref,
            amount=amount,
            tx_id=tx_id,
            note=note,
            msisdn=msisdn
        )

        if result.get("ok"):
            msg = f"✅ Payment confirmed: Tenant {result.get('tenant_id')} received Ksh {result.get('amount')}"
            logger.info(msg)
            return jsonify({"ResultCode": 0, "ResultDesc": msg}), 200
        else:
            msg = f"⚠️ Payment failed: {result.get('reason', 'unknown_reason')}"
            logger.warning(msg)
            return jsonify({"ResultCode": 1, "ResultDesc": msg}), 200

    except Exception as e:
        logger.exception("🚨 Exception in mpesa_confirm: %s", e)
        return jsonify({"ResultCode": 1, "ResultDesc": "Internal Error"}), 200


# -------------------------
# /api/... aliases for sandbox registration
# -------------------------
@mpesa_bp.route("/api/payment_callback/validate", methods=["POST"])
def api_payment_validate():
    logger.info("API VALIDATION received")
    return mpesa_validate()


@mpesa_bp.route("/api/payment_callback/confirm", methods=["POST"])
def api_payment_confirm():
    logger.info("API CONFIRMATION received")
    return mpesa_confirm()


# -------------------------
# Health check
# -------------------------
@mpesa_bp.route("/mpesa/health", methods=["GET"])
def mpesa_health():
    return jsonify({
        "status": "ok",
        "db": "sqlite",
        "default_paybill": DEFAULT_PAYBILL,
        "orm_enabled": bool(Tenant and Payment),
    }), 200

# -------------------------
# M-Pesa sandbox simulation (manual trigger for local testing)
# -------------------------
@mpesa_bp.route("/simulate-payment", methods=["POST"])
def simulate_payment():
    data = request.get_json(silent=True) or {}

    tx_id = data.get("TransID", "SIMULATED12345")
    amount = float(data.get("TransAmount", 0))
    msisdn = str(data.get("MSISDN", "254700000000"))
    bill_ref = data.get("BillRefNumber", "UNKNOWN")
    name = f"{data.get('FirstName', '')} {data.get('LastName', '')}".strip()

    current_app.logger.info(f"🧩 Simulating payment: {tx_id}, Ksh {amount} from {msisdn}")

    result = process_direct_payment(bill_ref, amount, tx_id, f"Simulated M-Pesa from {name}", msisdn)

    if result.get("ok"):
        return jsonify({
            "status": "success",
            "message": f"Simulated payment successful for {bill_ref}",
            "details": result
        }), 200
    else:
        return jsonify({
            "status": "failed",
            "message": result.get("reason", "Simulation failed")
        }), 400

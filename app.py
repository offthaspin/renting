import os
import io
import csv
import json
from datetime import datetime, date
from functools import wraps
from dateutil.relativedelta import relativedelta
import uuid

#from routes.rent_test import rent_test_bp



from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, send_from_directory, jsonify, abort, Response
)
from flask_login import (
    LoginManager, login_user, logout_user,
    login_required, current_user, UserMixin
)
from werkzeug.security import generate_password_hash, check_password_hash
from flask_migrate import Migrate
from dotenv import load_dotenv

# ✅ Local imports
from extensions import db, socketio
from models import User, Tenant, Payment, AuditLog
from mpesa_handler import mpesa_bp
from landlord_settings import landlord_settings_bp
from scheduler import start_scheduler
from register_daraja_live import register_urls

# -----------------------
# Load environment variables
# -----------------------
load_dotenv()

# -----------------------
# Base setup
# -----------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "rentana_full.db")
APK_FOLDER = os.path.join(BASE_DIR, "static", "apk")

# ✅ Create Flask app first
app = Flask(__name__, static_folder="static", template_folder="templates")
app.config.from_object("config")

# ✅ Environment overrides
app.config["SECRET_KEY"] = os.getenv("RENTANA_SECRET", "change-me-in-prod")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20MB upload limit

# ✅ Initialize extensions AFTER app is created
db.init_app(app)
socketio.init_app(app, cors_allowed_origins="*")
Migrate(app, db)

# -----------------------
# 🔌 Register Blueprints
# -----------------------
app.register_blueprint(landlord_settings_bp)

# ✅ Enable M-Pesa Blueprint for sandbox testing
app.register_blueprint(mpesa_bp, url_prefix="/mpesa")

print("✅ M-Pesa Sandbox Blueprint registered successfully at /mpesa")

#app.register_blueprint(rent_test_bp)
# -----------------------
# 🧠 DEBUG LOGGER - Log every incoming request
# -----------------------
@app.before_request
def log_request_info():
    print("\n====== 📥 NEW REQUEST RECEIVED ======")
    print(f"➡️  Path: {request.path}")
    print(f"➡️  Method: {request.method}")
    print(f"➡️  Headers:\n{dict(request.headers)}")

    try:
        data = request.get_json(force=True, silent=True)
        if data:
            print(f"➡️  JSON Body:\n{json.dumps(data, indent=2)}")
        else:
            print("➡️  No JSON body or invalid JSON format")
    except Exception as e:
        print(f"⚠️  Error parsing body: {e}")

    print("=====================================\n")

# -----------------------
# Initialize DB + Login Manager
# -----------------------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message_category = "warning"

# ✅ Automatically create database tables on startup
with app.app_context():
    db.create_all()
    start_scheduler() 

# -----------------------
# Login / audit helpers
# -----------------------
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def audit(user, action: str, meta: str = ""):
    """Log key user actions in the AuditLog table."""
    try:
        entry = AuditLog(user_id=(user.id if user else None), action=action, meta=str(meta))
        db.session.add(entry)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"⚠️  Audit log failed: {e}")


def ensure_apk_exists(func):
    """Ensure APK folder exists and contains at least one APK file."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not os.path.isdir(APK_FOLDER):
            flash("APK folder missing.", "danger")
            return redirect(url_for("dashboard"))
        apk_files = [f for f in os.listdir(APK_FOLDER) if f.lower().endswith(".apk")]
        if not apk_files:
            flash("No APK file found.", "warning")
            return redirect(url_for("dashboard"))
        kwargs["_apk_filename"] = apk_files[0]
        return func(*args, **kwargs)
    return wrapper


def owner_required(func):
    """Decorator to ensure only the tenant's owner (or admin) can access."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        tenant_id = (
            kwargs.get("tenant_id")
            or request.view_args.get("tenant_id")
            or request.form.get("tenant_id")
            or request.args.get("tenant_id")
        )
        if not tenant_id:
            abort(400, description="Tenant ID missing.")
        tenant = Tenant.query.get(int(tenant_id))
        if not tenant:
            abort(404, description="Tenant not found.")
        if not current_user.is_authenticated:
            return redirect(url_for("login", next=request.path))
        if tenant.owner_id != current_user.id and not current_user.is_admin:
            flash("No permission.", "danger")
            return redirect(url_for("tenant_list"))
        kwargs["_tenant_obj"] = tenant
        return func(*args, **kwargs)
    return wrapper

# -----------------------
# Auth routes
# -----------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm") or ""
        if not email or not password:
            flash("Email & password required.", "danger")
            return render_template("register.html")
        if password != confirm:
            flash("Passwords do not match.", "danger")
            return render_template("register.html")
        if User.query.filter_by(email=email).first():
            flash("Email exists. Login instead.", "warning")
            return redirect(url_for("login"))
        u = User(email=email)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        audit(u, "user_registered", meta=f"email:{email}")
        flash("Registered. Please login.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash("Invalid email or password.", "danger")
            return render_template("login.html", email=email)
        login_user(user)
        audit(user, "user_logged_in", meta=f"email:{email}")
        flash("Welcome back!", "success")
        return redirect(request.args.get("next") or url_for("dashboard"))
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    audit(current_user, "user_logged_out")
    logout_user()
    flash("Logged out.", "info")
    return redirect(url_for("login"))


# ✅ Helper Functions
# =====================================
#DUPLICATEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE
##3def process_payment(phone, amount, receipt, note="")

#manifesss

@app.route("/manifest.json")
def manifest():
    return send_from_directory('static', 'manifest.json', mimetype='application/manifest+json')


# Optional: health check
# ----------------------
@app.route("/webhook/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok", "message": "Webhook is alive"}), 200

# ----------------------
# Optional: simulate a test payment (offline)

# Settings
# -----------------------


#settingpayingg
@app.route('/settings/payment', methods=['GET', 'POST'])
@login_required
def settings_payment():
    # Only allow landlords
    if not getattr(current_user, "is_landlord", True):  # fallback True if attribute missing
        flash("Access denied.", "danger")
        return redirect(url_for('dashboard'))

    if request.method == "POST":
        paybill = (request.form.get("paybill_number") or "").strip()
        till = (request.form.get("till_number") or "").strip()
        phone = (request.form.get("phone_number") or "").strip()

        # Normalize digits
        import re
        def digits(n): return re.sub(r"\D", "", n or "")

        # Reset everything first
        current_user.payment_method = None
        current_user.paybill_number = None
        current_user.till_number = None
        current_user.phone_number = None

        # Assign based on which field is filled
        if paybill:
            current_user.payment_method = "Paybill"
            current_user.paybill_number = digits(paybill)
        elif till:
            current_user.payment_method = "Till"
            current_user.till_number = digits(till)
        elif phone:
            current_user.payment_method = "SendMoney"
            current_user.phone_number = digits(phone)

        db.session.commit()
        flash("Payment settings updated successfully.", "success")
        return redirect(url_for('settings_payment'))

    return render_template(
        "settings_payment.html",
        paybill=current_user.paybill_number,
        till=current_user.till_number,
        phone=current_user.phone_number,
        payment_method=current_user.payment_method  # send current method to template
    )

# -----------------------
# Dashboard


@app.route("/")
@login_required
def dashboard():
    """Render landlord dashboard."""
    return render_template("dashboard.html")


@app.route("/dashboard_data")
@login_required
def dashboard_data():
    """
    Return live dashboard data as JSON:
      - Tenant details
      - Recent payments
      - Totals: expected, collected, outstanding
      - Collected percentage
      - Payment method
    """

    # 🧭 Get all tenants for this landlord
    tenants = Tenant.query.filter_by(owner_id=current_user.id).order_by(Tenant.name).all()

    # 🧾 Get last 10 payments made to this landlord
    payments = (
        Payment.query.join(Tenant)
        .filter(Tenant.owner_id == current_user.id)
        .order_by(Payment.paid_at.desc())
        .limit(10)
        .all()
    )

    # 💰 Compute totals safely
    total_expected = sum(t.total_due_since() or 0 for t in tenants)
    total_collected = sum(t.total_paid() or 0 for t in tenants)
    total_outstanding = round(max(total_expected - total_collected, 0), 2)
    collected_percent = round((total_collected / total_expected * 100), 2) if total_expected else 0.0

    # 🪙 Get landlord’s payment method
    payment_method = getattr(current_user, "payment_method", None) or "Not set"

    # 📊 Prepare structured JSON response
    data = {
        "total_tenants": len(tenants),
        "total_expected": total_expected,
        "total_collected": total_collected,
        "total_outstanding": total_outstanding,
        "collected_percent": collected_percent,
        "payment_method": payment_method,
        "tenants": [
            {
                "id": t.id,
                "name": t.name,
                "phone": t.phone,
                "house_no": t.house_no,
                "monthly_rent": t.monthly_rent,
                "total_paid": t.total_paid() or 0,
                "total_due": t.total_due_since() or 0,
                "balance": (t.total_due_since() or 0) - (t.total_paid() or 0)
            } for t in tenants
        ],
        "payments": [
            {
                "id": p.id,
                "tenant_name": p.tenant.name if p.tenant else "Unknown",
                "amount": float(p.amount or 0),
                "note": p.note or "",
                "paid_at": p.paid_at.strftime("%Y-%m-%d %H:%M") if p.paid_at else "N/A"
            } for p in payments
        ]
    }

    return jsonify(data)


#payment type
# -----------------------

@app.route("/update_payment_settings", methods=["POST"])
@login_required
def update_payment_settings():
    method = (request.form.get("payment_method") or "").strip()  # normalize input
    account_number = (request.form.get("account_number") or "").strip()

    user = current_user

    # Save payment method explicitly
    if method in ["Paybill", "Till", "SendMoney"]:
        user.payment_method = method
    else:
        flash("Invalid payment method.", "danger")
        return redirect(url_for("dashboard"))

    # Reset all numbers first
    user.paybill_number = None
    user.till_number = None
    user.phone_number = None

    # Save the account/phone number based on method
    if method == "Paybill":
        user.paybill_number = account_number
    elif method == "Till":
        user.till_number = account_number
    else:  # SendMoney
        user.phone_number = account_number

    db.session.commit()
    flash("Payment settings updated successfully!", "success")
    return redirect(url_for("dashboard"))




# Tenants CRUD
# -----------------------
@app.route("/tenants")
@login_required
def tenant_list():
    q = (request.args.get("q") or "").strip()
    base_q = Tenant.query.filter_by(owner_id=current_user.id)
    if q:
        base_q = base_q.filter(
            (Tenant.name.ilike(f"%{q}%")) |
            (Tenant.phone.ilike(f"%{q}%")) |
            (Tenant.house_no.ilike(f"%{q}%"))
        )
    tenants = base_q.order_by(Tenant.name).all()
    return render_template("tenant_list.html", tenants=tenants, query=q)


@app.route("/tenant/add", methods=["GET", "POST"])
@login_required
def tenant_add():
    if request.method == "POST":
        try:
            move_in = request.form.get("move_in_date") or str(date.today())
            t = Tenant(
                owner_id=current_user.id,
                name=(request.form.get("name") or "").strip(),
                phone=(request.form.get("phone") or "").strip(),
                national_id=(request.form.get("national_id") or "").strip(),
                house_no=(request.form.get("house_no") or "").strip(),
                monthly_rent=float(request.form.get("monthly_rent") or 0),
                move_in_date=datetime.strptime(move_in, "%Y-%m-%d").date()
            )
        except Exception:
            flash("Invalid tenant data.", "danger")
            return render_template("add_tenant.html", form=request.form)
        db.session.add(t)
        db.session.commit()
        audit(current_user, "tenant_added", meta=f"id:{t.id}")
        flash("Tenant added.", "success")
        return redirect(url_for("dashboard"))
    return render_template("add_tenant.html")


@app.route("/tenant/<int:tenant_id>/edit", methods=["GET", "POST"])
@login_required
@owner_required
def tenant_edit(tenant_id, _tenant_obj=None):
    t = _tenant_obj
    if request.method == "POST":
        t.name = (request.form.get("name") or "").strip()
        t.phone = (request.form.get("phone") or "").strip()
        t.national_id = (request.form.get("national_id") or "").strip()
        t.house_no = (request.form.get("house_no") or "").strip()
        try:
            t.monthly_rent = float(request.form.get("monthly_rent") or t.monthly_rent)
        except ValueError:
            flash("Monthly rent must be a number.", "danger")
            return render_template("edit_tenants.html", tenant=t)
        move_in = request.form.get("move_in_date") or str(t.move_in_date)
        try:
            t.move_in_date = datetime.strptime(move_in, "%Y-%m-%d").date()
        except ValueError:
            flash("Move-in date must be YYYY-MM-DD.", "danger")
            return render_template("edit_tenants.html", tenant=t)
        db.session.commit()
        audit(current_user, "tenant_edited", meta=f"id:{t.id}")
        flash("Tenant updated.", "success")
        return redirect(url_for("tenant_list"))
    return render_template("edit_tenants.html", tenant=t)


@app.route("/tenant/<int:tenant_id>/delete", methods=["POST"])
@login_required
@owner_required
def tenant_delete(tenant_id, _tenant_obj=None):
    db.session.delete(_tenant_obj)
    db.session.commit()
    audit(current_user, "tenant_deleted", meta=f"id:{tenant_id}")
    flash("Tenant deleted.", "info")
    return redirect(url_for("tenant_list"))


# Bulk delete
@app.route("/tenants/bulk-delete", methods=["POST"])
@login_required
def tenant_bulk_delete():
    ids = request.form.getlist("tenant_ids")
    if not ids:
        flash("No tenants selected.", "warning")
        return redirect(url_for("tenant_list"))
    q = Tenant.query.filter(Tenant.id.in_(ids))
    if not current_user.is_admin:
        q = q.filter(Tenant.owner_id == current_user.id)
    tenants = q.all()
    count = len(tenants)
    for t in tenants:
        db.session.delete(t)
    db.session.commit()
    audit(current_user, "tenants_bulk_deleted", meta=f"ids:{','.join(ids)}")
    flash(f"{count} tenant(s) deleted.", "success")
    return redirect(url_for("tenant_list"))


# -----------------------
# Payments CRUD
# -----------------------
@app.route("/payment/add", methods=["GET", "POST"], endpoint="payment_add")
@login_required
@owner_required
def payment_add(_tenant_obj=None, tenant_id=None):
    tenant = _tenant_obj

    if request.method == "POST":
        try:
            amount = float(request.form.get("amount") or 0)
        except ValueError:
            flash("Amount must be a number.", "danger")
            return render_template("add_payment.html", tenant=tenant)

        note = (request.form.get("note") or "").strip()

        # ✅ Auto-generate unique transaction ID
        import uuid
        transaction_id = request.form.get("transaction_id")
        if not transaction_id or transaction_id.strip() == "":
            transaction_id = f"MANUAL-{uuid.uuid4().hex[:8].upper()}"

        # ✅ Create payment record
        from datetime import datetime
        p = Payment(
            tenant_id=tenant.id,
            amount=amount,
            note=note,
            transaction_id=transaction_id,
            paid_at=datetime.utcnow()  # 🧠 FIXED — ensure not null
        )

        # ✅ Commit safely
        try:
            db.session.add(p)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"[ERROR] Payment commit failed: {e}")
            flash("Error: Payment could not be saved. Please try again.", "danger")
            return render_template("add_payment.html", tenant=tenant)

        # ✅ Audit log
        audit(
            current_user,
            "payment_added",
            meta=f"payment_id:{p.id}, tenant_id:{tenant.id}, transaction_id:{transaction_id}"
        )

        flash(f"✅ Payment recorded successfully — Amount: {amount}, ID: {transaction_id}", "success")
        return redirect(url_for("dashboard"))

    # Render add payment page
    return render_template("add_payment.html", tenant=tenant)


@app.route("/payment/<int:payment_id>/edit", methods=["GET", "POST"])
@login_required
def payment_edit(payment_id):
    p = Payment.query.get_or_404(payment_id)
    if p.tenant.owner_id != current_user.id and not current_user.is_admin:
        flash("Not authorized.", "danger")
        return redirect(url_for("tenant_list"))
    if request.method == "POST":
        try:
            p.amount = float(request.form.get("amount") or p.amount)
        except ValueError:
            flash("Amount must be a number.", "danger")
            return render_template("payment_edit.html", payment=p)
        p.note = request.form.get("note") or ""
        db.session.commit()
        audit(current_user, "payment_edited", meta=f"id:{p.id}")
        flash("Payment updated.", "success")
        return redirect(url_for("dashboard"))
    return render_template("payment_edit.html", payment=p)


@app.route("/payments")
@login_required
def payment_list():
    payments = (Payment.query.join(Tenant)
                .filter(Tenant.owner_id == current_user.id)
                .order_by(Payment.paid_at.desc())
                .all())
    return render_template("payment_list.html", payments=payments)


# Bulk pay
@app.route('/bulk_pay', methods=['POST'])
@login_required
def bulk_pay():
    tenant_ids = request.form.getlist('tenant_ids')
    amount_raw = request.form.get('amount')
    if not tenant_ids or not amount_raw:
        flash("Tenant(s) or amount missing.", "warning")
        return redirect(url_for("tenant_list"))
    try:
        amount = float(amount_raw)
    except ValueError:
        flash("Invalid amount.", "danger")
        return redirect(url_for("tenant_list"))
    created = 0
    for tid in tenant_ids:
        t = Tenant.query.get(int(tid))
        if t and (t.owner_id == current_user.id or current_user.is_admin):
            p = Payment(tenant_id=t.id, amount=amount, note="Bulk payment")
            db.session.add(p)
            created += 1
    db.session.commit()
    audit(current_user, "bulk_pay", meta=f"ids:{','.join(tenant_ids)},amount:{amount}")
    flash(f"Bulk payments created for {created} tenant(s).", "success")
    return redirect(url_for("dashboard"))


# -----------------------
# Exports
# -----------------------
def make_csv_response(csv_text: str, filename="export.csv"):
    return Response(csv_text, mimetype="text/csv",
                    headers={"Content-disposition": f"attachment; filename={filename}"})


@app.route("/export/tenants.csv")
@login_required
def export_tenants_csv():
    base_q = Tenant.query
    if not current_user.is_admin:
        base_q = base_q.filter_by(owner_id=current_user.id)
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(["id","name","phone","national_id","house_no","monthly_rent","move_in_date","total_paid","total_due","balance"])
    for t in base_q.order_by(Tenant.name).all():
        cw.writerow([
            t.id, t.name, t.phone, t.national_id, t.house_no,
            f"{t.monthly_rent:.2f}", t.move_in_date.isoformat(),
            f"{t.total_paid():.2f}", f"{t.total_due_since():.2f}", f"{t.balance:.2f}"
        ])
    return make_csv_response(si.getvalue(), "tenants_export.csv")


#daraja register

@app.route("/register_daraja", methods=["POST"])
def register_daraja():
    env = request.form.get("env", "sandbox")
    key = request.form.get("consumer_key")
    secret = request.form.get("consumer_secret")
    shortcode = request.form.get("shortcode")
    callback = request.form.get("callback_url")

    base_url = "https://api.safaricom.co.ke" if env == "live" else "https://sandbox.safaricom.co.ke"
    result = register_urls(env.upper(), base_url, key, secret, shortcode, callback, live=(env == "live"))
    return jsonify(result)


@app.route("/export/payments.csv")
@login_required
def export_payments_csv():
    base_q = Payment.query.join(Tenant)
    if not current_user.is_admin:
        base_q = base_q.filter(Tenant.owner_id == current_user.id)
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(["id","tenant_id","tenant_name","amount","note","paid_at"])
    for p in base_q.order_by(Payment.paid_at.desc()).all():
        cw.writerow([p.id, p.tenant_id, p.tenant.name, f"{p.amount:.2f}", p.note or "", p.paid_at.isoformat()])
    return make_csv_response(si.getvalue(), "payments_export.csv")


# -----------------------
# APK & PWA
# -----------------------
@app.route("/apk/download")
@login_required
@ensure_apk_exists
def apk_download(_apk_filename=None):
    return send_from_directory(APK_FOLDER, _apk_filename, as_attachment=True)


@app.route("/apk/latest")
@login_required
@ensure_apk_exists
def apk_latest(_apk_filename=None):
    return jsonify({"filename": _apk_filename, "url": url_for("apk_download")})


@app.route("/service-worker.js")
def service_worker():
    return send_from_directory(app.static_folder, "service-worker.js")


# -----------------------
# Context processors / errors / CLI
# -----------------------
@app.context_processor
def inject_now():
    return {"current_year": datetime.now().year, "today": date.today(), "date": date, "datetime": datetime}


@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html", code=403, message="Forbidden"), 403

@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="Not Found"), 404

@app.errorhandler(500)
def server_error(e):
    return render_template("error.html", code=500, message="Server Error"), 500


@app.cli.command("init-db")
def init_db():
    db.create_all()
    print("Database initialized at:", DB_PATH)


@app.cli.command("create-admin")
def create_admin():
    import getpass
    email = input("Admin email: ").strip().lower()
    if not email:
        print("Email required.")
        return
    if User.query.filter_by(email=email).first():
        print("User exists.")
        return
    pwd = getpass.getpass("Password: ")
    pwd2 = getpass.getpass("Confirm Password: ")
    if pwd != pwd2:
        print("Passwords do not match.")
        return
    u = User(email=email, is_admin=True)
    u.set_password(pwd)
    db.session.add(u)
    db.session.commit()
    print("Admin created.")


# -----------------------
# -------------------------------------
# -------------------------------------
# Compatibility / Aliases
# -------------------------------------
@app.route("/add_tenant")
@login_required
def add_tenant_alias():
    return redirect(url_for("tenant_add"))


@app.route("/edit_tenant/<int:tenant_id>")
@login_required
def edit_tenant_alias(tenant_id):
    return redirect(url_for("tenant_edit", tenant_id=tenant_id))


@app.route("/add_payment")
@login_required
def add_payment_alias():
    tenant_id = request.args.get("tenant_id")
    if tenant_id:
        return redirect(url_for("payment_add", tenant_id=tenant_id))
    return redirect(url_for("payment_list"))


@app.route("/payment/edit-redirect")
@login_required
def payment_edit_redirect():
    return redirect(url_for("payment_list"))


# -------------------------------------
# Database Initialization
# -------------------------------------
with app.app_context():
    try:
        db.create_all()
        print("✅ Database initialized successfully.")
    except Exception as e:
        print("❌ Database initialization failed:", e)


# -------------------------------------
# Landlord Settings Import
# -------------------------------------
try:
    import landlord_settings  # registers /settings/payment and defines LandlordSettings model
except Exception as e:
    print("⚠️ Failed to import landlord_settings:", e)


# -------------------------------------
# Monthly Rent Auto-Update (Kenya Time)
# -------------------------------------
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import pytz
from models import Tenant

def update_monthly_rent():
    with app.app_context():
        tenants = Tenant.query.all()
        for tenant in tenants:
            tenant.balance += tenant.rent_amount  # add unpaid rent to balance
        db.session.commit()
        print(f"[{datetime.now()}] ✅ Monthly rent balances updated successfully")

# Run every 1st of each month at 00:00 (Kenya time)
kenya_tz = pytz.timezone("Africa/Nairobi")
scheduler = BackgroundScheduler(timezone=kenya_tz)
scheduler.add_job(update_monthly_rent, "cron", day=1, hour=0, minute=0)
scheduler.start()
print("🕓 Scheduler started — updates unpaid rent every 1st of the month (Kenya time).")


# -------------------------------------
# Run App
# -------------------------------------
if __name__ == "__main__":
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler()]
    )
    logging.info("🚀 Rentana Flask app starting on port %s...", os.getenv("PORT", 5000))

    socketio.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

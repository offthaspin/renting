import os
from flask import session

import io
import json
import csv
from rentme.forms import LoginForm
from datetime import datetime, date, timedelta
from functools import wraps
import uuid
import pytz
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv
import random


from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, send_from_directory, jsonify, abort, Response
)
from flask_login import (
    LoginManager, login_user, logout_user,
    login_required, current_user, UserMixin
)
from flask import Flask, Blueprint, render_template, request, redirect, url_for, flash

from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from flask_mail import Mail
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash
import redis
# Local imports
from rentme.extensions import db, mail, limiter
from rentme.config import Config
from rentme.models import User, Tenant, Payment, AuditLog
from rentme.mpesa_handler import mpesa_bp
from rentme.landlord_settings import landlord_settings_bp
from scheduler import start_scheduler
from register_daraja_live import register_urls
from rentme.forms import RegisterForm
from rentme.forms import ForgotPasswordForm
from rentme.utils import send_sms_via_africastalking, send_reset_email, normalize_msisdn
from rentme.forms import TenantForm
from wtforms.validators import ValidationError
from flask_wtf.csrf import validate_csrf
from wtforms.validators import ValidationError
from flask_wtf import CSRFProtect
from sqlalchemy import or_
from sqlalchemy import func
from rentme.forms import ResetPasswordForm

# -----------------------
# Load environment variables
# -----------------------
load_dotenv()

# -----------------------
# Paths
# -----------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
APK_FOLDER = os.path.join(BASE_DIR, "static", "apk")
DB_PATH = os.path.join(BASE_DIR, "rentana_full.db")

# -----------------------
# Create Flask app
# -----------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
app.config.from_object(Config)

# Redis connection (optional, for production rate limiting)
r = redis.Redis(host='localhost', port=6379, db=0)

# Correct Limiter setup
limiter = Limiter(
    app=app,  # must be keyword
    key_func=get_remote_address,
    storage_uri="redis://localhost:6379"
)
# -----------------------
# Environment overrides
# -----------------------
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-me-in-prod")
db_url = os.getenv("DATABASE_URL") 
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

# -----------------------
# Init extensions
# -----------------------
db.init_app(app)
csrf = CSRFProtect(app)
mail.init_app(app)
limiter.init_app(app)
Migrate(app, db)

csrf.exempt(mpesa_bp)

# -----------------------
# Login manager
# -----------------------


login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message_category = "warning"

@login_manager.user_loader
def load_user(user_id):
    user = User.query.get(int(user_id))
    if not user:
        return None

    # Optional: reject sessions created before last_logout
    session_created_at = session.get("created_at")
    if session_created_at:
        try:
            session_created_dt = datetime.fromisoformat(session_created_at)
            if user.last_logout and session_created_dt < user.last_logout:
                return None
        except Exception as e:
            print("❌ Error checking last_logout:", e)

    return user

# -----------------------
# Timezone helpers
# -----------------------
NAIROBI_TZ = pytz.timezone("Africa/Nairobi")
def to_nairobi(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    return dt.astimezone(NAIROBI_TZ)
app.jinja_env.filters["to_nairobi"] = to_nairobi

# -----------------------
# Blueprints
# -----------------------
app.register_blueprint(mpesa_bp, url_prefix="/mpesa")
print("✅ M-Pesa Blueprint active at /mpesa")
app.register_blueprint(landlord_settings_bp, url_prefix="/settings")
# -----------------------
# Debug logger
# -----------------------
@app.before_request
def log_request_info():
    print("\n====== 📥 NEW REQUEST ======")
    print(f"➡️ Path:   {request.path}")
    print(f"➡️ Method: {request.method}")
    try:
        data = request.get_json(force=True, silent=True)
        print(f"➡️ Body: {json.dumps(data, indent=2) if data else 'None'}")
    except Exception as e:
        print(f"⚠️ JSON parse error: {e}")

# -----------------------
# DB + Scheduler
# -----------------------
with app.app_context():
    start_scheduler()

# -----------------------
# Audit helper
# -----------------------
def audit(user, action, meta=""):
    try:
        entry = AuditLog(user_id=(user.id if user else None),
                         action=action, meta=str(meta))
        db.session.add(entry)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"⚠️ Audit log failed: {e}")

# -----------------------
# Decorators
# -----------------------
def ensure_apk_exists(func):
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
    @wraps(func)
    def wrapper(*args, **kwargs):
        tenant_id = (kwargs.get("tenant_id") 
                     or request.view_args.get("tenant_id") 
                     or request.form.get("tenant_id") 
                     or request.args.get("tenant_id"))
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
# Routes
# -----------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    form = RegisterForm()

    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        raw_phone = form.login_phone.data.strip() if form.login_phone.data else ""
        phone = normalize_msisdn(raw_phone) if raw_phone else None

        # 🔍 Check existing email
        email_exists = User.query.filter_by(email=email).first()
        if email_exists:
            flash("Email already registered. Please login.", "warning")
            return redirect(url_for("login"))

        # 🔍 Check existing phone (only if provided & valid)
        if phone:
            phone_exists = User.query.filter_by(login_phone=phone).first()
            if phone_exists:
                flash("Phone number already registered. Please login.", "warning")
                return redirect(url_for("login"))

        # 🚨 Invalid phone provided
        if raw_phone and not phone:
            flash("Invalid phone number format.", "danger")
            return redirect(url_for("register"))

        # ✅ Create user
        user = User(
            full_name=form.full_name.data.strip(),
            email=email,
            login_phone=phone,
            password_hash=generate_password_hash(form.password.data)
        )

        try:
            db.session.add(user)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash("Registration failed. Please try again.", "danger")
            return redirect(url_for("register"))

        audit(
            user,
            "user_registered",
            f"email:{user.email}, phone:{user.login_phone or '-'}"
        )

        flash("Registration successful! You can now login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html", form=form)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        identifier = form.identifier.data.strip()
        password = form.password.data

        # Try email first
        user = User.query.filter_by(email=identifier.lower()).first()
        # Then phone if not found
        if not user:
            user = User.query.filter_by(login_phone=identifier).first()

        if not user or not user.check_password(password):
            flash("Invalid credentials.", "danger")
            return render_template("login.html", form=form)

        login_user(user)
        audit(user, "user_logged_in", f"id:{user.id}")
        flash("Welcome back!", "success")
        return redirect(request.args.get("next") or url_for("dashboard"))

    return render_template("login.html", form=form)


# -----------------------
@app.route("/logout")
@login_required
def logout():
    current_user.last_logout = datetime.utcnow()
    db.session.commit()
    logout_user()
    flash("Logged out.", "info")
    return redirect(url_for("login"))


# -----------------------------------------------------
# FORGOT PASSWORD
# -----------------------------------------------------
@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    form = ForgotPasswordForm()

    if form.validate_on_submit():
        value = form.email_or_phone.data.strip()

        # Detect email or phone
        if "@" in value:
            user = User.query.filter_by(email=value.lower()).first()
        else:
            normalized = normalize_msisdn(value)
            user = User.query.filter_by(login_phone=normalized).first()

        if not user:
            flash("No account found with that email or phone number.", "danger")
            return redirect("/forgot-password")

        # Generate reset code
        code = str(random.randint(100000, 999999))
        user.reset_code = code
        user.reset_code_expires_at = datetime.utcnow() + timedelta(minutes=10)

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error saving reset code: {e}")
            flash("Something went wrong. Try again.", "danger")
            return redirect("/forgot-password")

        # Try SMS first
        sent_sms = send_sms_via_africastalking(user.login_phone, f"Your Rentana reset code is {code}")

        # Fallback to email if SMS failed or credentials missing
        if not sent_sms:
            sent_email = send_reset_email(
                user.email,
                "Rentana Password Reset",
                f"Your Rentana password reset code is {code}"
            )
            if sent_email:
                flash("Reset code sent to your email.", "success")
            else:
                flash("Could not send reset code via SMS or email. Contact support.", "danger")
        else:
            flash("A reset code has been sent to your phone.", "success")

        return redirect("/reset-password")

    return render_template("forgot_password.html", form=form)

# -----------------------------------------------------
# RESET PASSWORD
# -----------------------------------------------------

@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    form = ResetPasswordForm()

    if form.validate_on_submit():
        identifier = form.identifier.data.strip()
        code = form.code.data.strip()
        password = form.password.data

        # email or phone
        if "@" in identifier:
            user = User.query.filter_by(email=identifier.lower()).first()
        else:
            normalized = normalize_msisdn(identifier)
            user = User.query.filter_by(login_phone=normalized).first()

        if not user:
            flash("Account not found.", "danger")
            return render_template("reset_password.html", form=form)

        now = datetime.utcnow()

        # validate reset code
        if user.reset_code != code:
            flash("Invalid reset code.", "danger")
            return render_template("reset_password.html", form=form)

        if not user.reset_code_expires_at or user.reset_code_expires_at < now:
            flash("Reset code expired.", "danger")
            return render_template("reset_password.html", form=form)

        # set new password
        user.set_password(password)
        user.reset_code = None
        user.reset_code_expires_at = None
        db.session.commit()

        flash("Password changed successfully.", "success")
        return redirect(url_for("login"))

    return render_template("reset_password.html", form=form)



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


# -----------------------
# -----------------------
# Dashboard

from pytz import timezone
NAIROBI_TZ = timezone("Africa/Nairobi")


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
      - Totals: expected, collected, outstanding
      - Collected percentage
    """

    # 🧭 Get all tenants for this landlord
    tenants = (
        Tenant.query
        .filter_by(owner_id=current_user.id)
        .order_by(Tenant.name)
        .all()
    )

    # 💰 Compute totals (based on real tenant data)
    total_expected = sum((t.total_due_since() or 0) for t in tenants)
    total_collected = sum((t.total_paid() or 0) for t in tenants)

    # Outstanding (cannot be negative even if tenant overpaid)
    total_outstanding = round(max(total_expected - total_collected, 0), 2)

    # Collection %
    collected_percent = (
        round((total_collected / total_expected * 100), 2)
        if total_expected else 0.0
    )

    # 🏠 Prepare tenant info for dashboard table
    tenants_list = []
    for t in tenants:
        paid = t.total_paid() or 0
        due = t.total_due_since() or 0
        balance = paid - due

        tenants_list.append({
            "id": t.id,
            "name": t.name,
            "phone": t.phone,
            "house_no": t.house_no,
            "monthly_rent": float(t.monthly_rent or 0),
            "total_paid": float(paid),
            "total_due": float(due),
            "balance": float(balance),
            "formatted_balance": f"{balance:,.2f}",
        })

    # 📤 Return dashboard stats + tenants
    return jsonify({
        "total_tenants": len(tenants),
        "total_expected": round(total_expected, 2),
        "total_collected": round(total_collected, 2),
        "total_outstanding": total_outstanding,
        "collected_percent": collected_percent,
        "tenants": tenants_list
    })


#payment type
# -----------------------



# Tenants CRUD
# ----------------------

@app.route("/tenants")
@login_required
def tenant_list():
    q = request.args.get("q", "", type=str).strip()
    page = request.args.get("page", 1, type=int)
    per_page = 20

    query = Tenant.query.filter(
        Tenant.owner_id == current_user.id
    )

    # 🔎 Case-insensitive search
    if q:
        search = f"%{q.lower()}%"
        query = query.filter(
            or_(
                func.lower(Tenant.name).like(search),
                func.lower(Tenant.phone).like(search),
                func.lower(Tenant.house_no).like(search),
            )
        )

    pagination = query.order_by(
        Tenant.house_no.asc()
    ).paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )

    # ⚡ AJAX response
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        rows_html = render_template(
            "_tenant_rows.html",
            tenants=pagination.items
        )
        pagination_html = render_template(
            "_tenant_pagination.html",
            pagination=pagination,
            query=q
        )
        return jsonify({
            "rows": rows_html,
            "pagination": pagination_html
        })

    # 🧱 Normal page load
    return render_template(
        "tenant_list.html",
        tenants=pagination.items,
        pagination=pagination,
        query=q
    )



@app.route("/tenant/add", methods=["GET", "POST"])
@login_required
def tenant_add():
    form = TenantForm()

    if form.validate_on_submit():
        try:
            move_in = form.move_in_date.data or str(date.today())
            t = Tenant(
                owner_id=current_user.id,
                name=form.name.data.strip(),
                phone=form.phone.data.strip(),
                national_id=form.national_id.data.strip(),
                house_no=form.house_no.data.strip(),
                monthly_rent=float(form.monthly_rent.data),
                move_in_date=datetime.strptime(move_in, "%Y-%m-%d").date()
            )
        except Exception:
            flash("Invalid tenant data.", "danger")
            return render_template("add_tenant.html", form=form)

        db.session.add(t)
        db.session.commit()
        audit(current_user, "tenant_added", meta=f"id:{t.id}")
        flash("Tenant added.", "success")
        return redirect(url_for("dashboard"))

    return render_template("add_tenant.html", form=form)



# ---------- EDIT TENANT ----------
@app.route("/tenant/<int:tenant_id>/edit", methods=["GET", "POST"])
@login_required
@owner_required
def tenant_edit(tenant_id, _tenant_obj=None):

    # Ensure tenant object exists
    t = _tenant_obj or Tenant.query.get_or_404(tenant_id)

    if request.method == "POST":

        # Validate CSRF
        try:
            validate_csrf(request.form.get("csrf_token"))
        except ValidationError:
            flash("Invalid or missing CSRF token. Please refresh the page.", "danger")
            return render_template("edit_tenants.html", tenant=t)

        # Update fields
        t.name = (request.form.get("name") or "").strip()
        t.phone = (request.form.get("phone") or "").strip()
        t.national_id = (request.form.get("national_id") or "").strip()
        t.house_no = (request.form.get("house_no") or "").strip()

        try:
            t.monthly_rent = float(request.form.get("monthly_rent") or t.monthly_rent)
        except ValueError:
            flash("Monthly rent must be a valid number.", "danger")
            return render_template("edit_tenants.html", tenant=t)

        # Move-in date
        move_in = request.form.get("move_in_date") or str(t.move_in_date)
        try:
            t.move_in_date = datetime.strptime(move_in, "%Y-%m-%d").date()
        except ValueError:
            flash("Move-in date must be in format YYYY-MM-DD.", "danger")
            return render_template("edit_tenants.html", tenant=t)

        db.session.commit()
        audit(current_user, "tenant_edited", meta=f"id:{t.id}")

        flash("Tenant updated successfully!", "success")
        return redirect(url_for("tenant_list"))

    return render_template("edit_tenants.html", tenant=t)



# ---------- DELETE TENANT ----------
@app.route("/tenant/<int:tenant_id>/delete", methods=["POST"])
@login_required
@owner_required
def tenant_delete(tenant_id, _tenant_obj=None):

    # Lookup object if decorator didn't inject it
    t = _tenant_obj or Tenant.query.get_or_404(tenant_id)

    # Validate CSRF
    try:
        validate_csrf(request.form.get("csrf_token"))
    except ValidationError:
        flash("Invalid or missing CSRF token. Try again.", "danger")
        return redirect(url_for("tenant_list"))

    db.session.delete(t)
    db.session.commit()

    audit(current_user, "tenant_deleted", meta=f"id:{tenant_id}")
    flash("Tenant deleted successfully!", "info")

    return redirect(url_for("tenant_list"))



# ---------- BULK DELETE ----------
@app.route("/tenants/bulk-delete", methods=["POST"])
@login_required
def tenant_bulk_delete():

    # Validate CSRF
    try:
        validate_csrf(request.form.get("csrf_token"))
    except ValidationError:
        flash("Invalid CSRF token. Bulk delete cancelled.", "danger")
        return redirect(url_for("tenant_list"))

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

    flash(f"{count} tenant(s) deleted successfully.", "success")
    return redirect(url_for("tenant_list"))

# -----------------------
# Payments CRUD
# -----------------------
@app.route("/payment/add", methods=["GET", "POST"], endpoint="payment_add")
@login_required
@owner_required
def payment_add(_tenant_obj=None, tenant_id=None):
    tenant = _tenant_obj

    # 🧩 SAFETY: Always resolve tenant if not injected
    if tenant is None:
        # Try URL kwarg first (from /payment/add?tenant_id=X or route param)
        tid = tenant_id or request.args.get("tenant_id") or request.form.get("tenant_id")
        if tid:
            try:
                tid_int = int(tid)
            except ValueError:
                tid_int = None
            if tid_int:
                tenant = Tenant.query.filter_by(id=tid_int, owner_id=current_user.id).first()

    # If still no tenant → redirect
    if tenant is None:
        flash("Bad request: Tenant not found or missing tenant ID.", "danger")
        return redirect(url_for("tenant_list"))

    if request.method == "POST":
        # 🔐 1) Get password from form (filled by popup / modal JS)
        password = (request.form.get("password_confirm") or "").strip()

        if not password:
            flash("Password confirmation is required to add a payment.", "danger")
            return render_template("add_payment.html", tenant=tenant)

        # 🔐 2) Verify user password using your User model method
        try:
            is_valid = current_user.check_password(password)
        except AttributeError:
            # Fallback if your User model doesn't have check_password()
            from werkzeug.security import check_password_hash
            is_valid = check_password_hash(current_user.password_hash, password)

        if not is_valid:
            flash("Incorrect password. Payment was not added.", "danger")
            return render_template("add_payment.html", tenant=tenant)

        # ✅ 3) Validate amount
        try:
            amount = float(request.form.get("amount") or 0)
        except ValueError:
            flash("Amount must be a number.", "danger")
            return render_template("add_payment.html", tenant=tenant)

        if amount <= 0:
            flash("Amount must be greater than zero.", "danger")
            return render_template("add_payment.html", tenant=tenant)

        note = (request.form.get("note") or "").strip()

        # ✅ 4) Auto-generate unique transaction ID
        import uuid
        transaction_id = request.form.get("transaction_id")
        if not transaction_id or transaction_id.strip() == "":
            transaction_id = f"MANUAL-{uuid.uuid4().hex[:8].upper()}"

        from datetime import datetime
        p = Payment(
            tenant_id=tenant.id,
            amount=amount,
            note=note,
            transaction_id=transaction_id,
            paid_at=datetime.utcnow()
        )

        # ✅ 5) Commit safely
        try:
            db.session.add(p)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"[ERROR] Payment commit failed: {e}")
            flash("Error: Payment could not be saved. Please try again.", "danger")
            return render_template("add_payment.html", tenant=tenant)

        # ✅ 6) Audit log
        audit(
            current_user,
            "payment_added",
            meta=f"payment_id:{p.id}, tenant_id:{tenant.id}, transaction_id:{transaction_id}"
        )

        flash(f"✅ Payment recorded successfully — Amount: {amount}, ID: {transaction_id}", "success")
        return redirect(url_for("dashboard"))

    # GET
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
    from rentme.landlord_settings import landlord_settings_bp
except ImportError as e:
    print(f"⚠️ Failed to import landlord_settings: {e}")

# -------------------------------------
# Monthly Rent Auto-Update (Kenya Time)
# -------------------------------------
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import pytz
from rentme.models import Tenant

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

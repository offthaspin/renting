# models.py
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import pytz
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Column, DateTime
from rentme.extensions import db 


class JobLock(db.Model):
    __tablename__ = "job_locks"

    id = db.Column(db.Integer, primary_key=True)
    job_name = db.Column(db.String(100), unique=True, nullable=False)
    last_run = db.Column(db.Date, nullable=True)
    locked_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<JobLock {self.job_name}>"

class MpesaCredential(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    shortcode = db.Column(db.String(50))
    shortcode_type = db.Column(db.String(20))   # paybill, till, sendmoney
    callback_url = db.Column(db.String(500))

    mpesa_env = db.Column(db.String(20), default="sandbox")

    encrypted_consumer_key = db.Column(db.LargeBinary)
    encrypted_consumer_secret = db.Column(db.LargeBinary)
    encrypted_passkey = db.Column(db.LargeBinary)

    def set_secret(self, key_name, raw_value):
        setattr(self, f"encrypted_{key_name}", encrypt_value(raw_value))

    def get_secret(self, key_name):
        return decrypt_value(getattr(self, f"encrypted_{key_name}"))


# ==============================================================
# USER MODEL (Each user has own tenants + own MPESA credentials)
# ==============================================================
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)

    # Identity
    full_name = db.Column(db.String(180), nullable=True)
    email = db.Column(db.String(256), unique=True, nullable=False, index=True)
    login_phone = db.Column(db.String(20), unique=True, nullable=True, index=True)
    password_hash = db.Column(db.String(256), nullable=False)

    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # ============================
    # PAYMENT METHOD CHOSEN BY USER
    # ============================
    # "SendMoney" | "Paybill" | "Till"
    payment_method = db.Column(db.String(50), nullable=True)

    # SEND MONEY OPTION
    phone_number = db.Column(db.String(20), nullable=True)  
    # (tenant pays to this number)

    # PAYBILL OPTION
    paybill_number = db.Column(db.String(30), nullable=True)

    # TILL OPTION
    till_number = db.Column(db.String(30), nullable=True)

    # ============================
    # DARAJA MPESA CREDENTIALS (stored per user)
    # ============================
    mpesa_consumer_key = db.Column(db.String(200), nullable=True)
    mpesa_consumer_secret = db.Column(db.String(200), nullable=True)
    mpesa_passkey = db.Column(db.String(200), nullable=True)
    mpesa_shortcode = db.Column(db.String(20), nullable=True)
    mpesa_env = db.Column(db.String(20), default="sandbox")  # sandbox or production

    # Optional: user-specific callback (but system uses a shared callback)
    mpesa_callback_url = db.Column(db.String(500), nullable=True)

    # Password reset fields
    reset_code = db.Column(db.String(10), nullable=True)
    reset_code_expires_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    tenants = db.relationship("Tenant", backref="owner", cascade="all, delete-orphan")
    payments = db.relationship("Payment", backref="payer", cascade="all, delete-orphan")
    audit_logs = db.relationship("AuditLog", backref="user", cascade="all, delete-orphan")

    last_logout = Column(DateTime, default=datetime.utcnow)

    # Auth helpers
    def set_password(self, pwd: str):
        self.password_hash = generate_password_hash(pwd)

    def check_password(self, pwd: str) -> bool:
        return check_password_hash(self.password_hash, pwd)

    def __repr__(self):
        return f"<User {self.email} | payment={self.payment_method} | shortcode={self.mpesa_shortcode}>"
 

 #LANDLORD SETTINGS------------------------------------
class LandlordSettings(db.Model):
    __tablename__ = "landlord_settings"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    payment_method = db.Column(db.String(50), nullable=True)

    # Business receiving numbers
    paybill_number = db.Column(db.String(32), nullable=True)
    till_number = db.Column(db.String(32), nullable=True)
    send_money_number = db.Column(db.String(32), nullable=True)
    phone_number = db.Column(db.String(50), nullable=True)  # optional display phone

    # Per-landlord Daraja credentials (used for STK push & token generation)
    mpesa_consumer_key = db.Column(db.String(255), nullable=True)
    mpesa_consumer_secret = db.Column(db.String(255), nullable=True)
    mpesa_shortcode = db.Column(db.String(32), nullable=True)   # BusinessShortCode / Paybill/Till
    mpesa_passkey = db.Column(db.String(255), nullable=True)
    mpesa_mode = db.Column(db.String(20), default="production", nullable=False)  # 'production' or 'sandbox'
    callback_url = db.Column(db.String(512), nullable=True)  # optional per-landlord callback override

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # relationship
    user = db.relationship("User", backref=db.backref("landlord_settings", uselist=False))

    def __repr__(self):
        return f"<LandlordSettings user_id={self.user_id} mpesa_mode={self.mpesa_mode}>"


# ==============================================================
# TENANT MODEL (Each tenant belongs to a specific user)
# ==============================================================
class Tenant(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    name = db.Column(db.String(180), nullable=False)
    phone = db.Column(db.String(80), nullable=False)
    national_id = db.Column(db.String(80))
    house_no = db.Column(db.String(80), nullable=False)  # <-- used as Paybill Account Number
    monthly_rent = db.Column(db.Float, nullable=False, default=0.0)
    move_in_date = db.Column(db.Date, nullable=False, default=date.today)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    last_rent_update = db.Column(db.Date, nullable=False, default=date.today)
    amount_due = db.Column(db.Float, nullable=False, default=0.0)

    # Relationship
    payments = db.relationship("Payment", backref="tenant", cascade="all, delete-orphan")

    # -----------------------
    # Tenant Rent Calculations
    # -----------------------
    def total_paid(self) -> float:
        return sum((p.amount or 0.0) for p in self.payments) if self.payments else 0.0

    def months_since_move_in(self, upto: date = None) -> int:
        upto = upto or date.today()
        if upto < self.move_in_date:
            return 0
        rd = relativedelta(upto, self.move_in_date)
        return rd.years * 12 + rd.months + (1 if rd.days >= 0 else 0)

    def total_due_since(self, upto: date = None) -> float:
        return self.months_since_move_in(upto) * float(self.monthly_rent)

    def balance_calc(self, upto: date = None) -> float:
        return round(self.total_paid() - self.total_due_since(upto), 2)

    @property
    def balance(self) -> float:
        return self.balance_calc()

    def formatted_balance(self) -> str:
        bal = self.balance
        sign = "+" if bal >= 0 else "-"
        return f"{sign}{abs(bal):,.2f}"

    def update_monthly_due(self):
        today = date.today()
        if self.last_rent_update.month == today.month and self.last_rent_update.year == today.year:
            return

        months_behind = (
            (today.year - self.last_rent_update.year) * 12 +
            (today.month - self.last_rent_update.month)
        )
        if months_behind > 0:
            self.amount_due += self.monthly_rent * months_behind
            self.last_rent_update = today
            db.session.commit()



# ==============================================================
# PAYMENT MODEL
# Used for SendMoney, Paybill, Till, and Daraja STK Push
# ==============================================================
class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    transaction_id = db.Column(db.String(100), unique=True, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    paid_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    note = db.Column(db.String(255))

    # Foreign Keys
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenant.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    # CheckoutRequestID for Daraja callbacks routing
    checkout_request_id = db.Column(db.String(100), index=True, nullable=True)

    def apply_payment(self):
        """Reduce tenant’s amount_due when payment is made"""
        if self.tenant:
            self.tenant.amount_due = max(0.0, self.tenant.amount_due - self.amount)
            self.tenant.last_rent_update = date.today()
            db.session.commit()



# ==============================================================
# AUDIT LOG MODEL
# ==============================================================
class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    action = db.Column(db.String(200), nullable=False)
    meta = db.Column(db.String(1000))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)



# ==============================================================
# AUTO RENT UPDATER (Kenya Time)
# ==============================================================
def auto_update_all_unpaid_rents():
    kenya_tz = pytz.timezone("Africa/Nairobi")
    now = datetime.now(kenya_tz)
    today = now.date()

    tenants = Tenant.query.all()
    updated = 0

    for t in tenants:
        months_behind = (today.year - t.last_rent_update.year) * 12 + (today.month - t.last_rent_update.month)
        if months_behind > 0:
            t.amount_due += t.monthly_rent * months_behind
            t.last_rent_update = today
            updated += 1

    if updated > 0:
        db.session.commit()
        db.session.add(AuditLog(
            user_id=None,
            action="Auto rent update",
            meta=f"{updated} tenants updated on {today.isoformat()} (EAT)"
        ))
        db.session.commit()

    return updated

# models.py
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import pytz
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db  # shared db instance


# -----------------------
# User Model
# -----------------------
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(256), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Payment Preferences
    payment_method = db.Column(db.String(50), nullable=True)   # "SendMoney", "Paybill", "Till"
    paybill_number = db.Column(db.String(30), nullable=True)
    till_number = db.Column(db.String(30), nullable=True)
    phone_number = db.Column(db.String(20), nullable=True)     # for SendMoney (2547xxxxxxx)

    # Relationships
    tenants = db.relationship("Tenant", backref="owner", cascade="all, delete-orphan")
    audit_logs = db.relationship("AuditLog", backref="user", cascade="all, delete-orphan")

    def set_password(self, pwd: str):
        self.password_hash = generate_password_hash(pwd)

    def check_password(self, pwd: str) -> bool:
        return check_password_hash(self.password_hash, pwd)

    def __repr__(self):
        return f"<User {self.email} | method={self.payment_method}>"


# -----------------------
# Tenant Model
# -----------------------
class Tenant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    name = db.Column(db.String(180), nullable=False)
    phone = db.Column(db.String(80), nullable=False)
    national_id = db.Column(db.String(80))
    house_no = db.Column(db.String(80), nullable=False)
    monthly_rent = db.Column(db.Float, nullable=False, default=0.0)
    move_in_date = db.Column(db.Date, nullable=False, default=date.today)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    last_rent_update = db.Column(db.Date, nullable=False, default=date.today)
    amount_due = db.Column(db.Float, nullable=False, default=0.0)

    payments = db.relationship("Payment", backref="tenant", cascade="all, delete-orphan")

    # -----------------------
    # Helpers
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
        """Positive means tenant has overpaid (credit). Negative means they owe."""
        return round(self.total_paid() - self.total_due_since(upto), 2)

    @property
    def balance(self) -> float:
        return self.balance_calc()

    def formatted_balance(self) -> str:
        """Return balance string with sign and commas (e.g., +1,000 or -500)"""
        bal = self.balance
        sign = "+" if bal >= 0 else "-"
        return f"{sign}{abs(bal):,.2f}"

    def update_monthly_due(self):
        """Automatically accumulate unpaid rent for missed months"""
        today = date.today()
        if self.last_rent_update.month == today.month and self.last_rent_update.year == today.year:
            return  # already updated this month

        months_behind = (today.year - self.last_rent_update.year) * 12 + (today.month - self.last_rent_update.month)
        if months_behind > 0:
            self.amount_due += self.monthly_rent * months_behind
            self.last_rent_update = today
            db.session.commit()


# -----------------------
# Payment Model
# -----------------------
class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.String(50), unique=True, nullable=False)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenant.id'))
    amount = db.Column(db.Float, nullable=False)
    paid_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    note = db.Column(db.String(255))

    def apply_payment(self):
        """Reduce tenant’s amount_due when payment is made"""
        if self.tenant:
            self.tenant.amount_due = max(0.0, self.tenant.amount_due - self.amount)
            self.tenant.last_rent_update = date.today()
            db.session.commit()


# -----------------------
# Audit Log Model
# -----------------------
class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    action = db.Column(db.String(200), nullable=False)
    meta = db.Column(db.String(1000))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# -----------------------
# Utility: auto-update unpaid rents monthly (Kenya Time)
# -----------------------
def auto_update_all_unpaid_rents():
    """Runs monthly — adds unpaid rent for tenants behind schedule"""
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
        log = AuditLog(
            user_id=None,
            action="Auto rent update",
            meta=f"{updated} tenants updated on {today.isoformat()} (EAT)"
        )
        db.session.add(log)
        db.session.commit()

    return updated

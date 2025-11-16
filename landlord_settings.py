import os
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db

# --------------------------------
# Blueprint
# --------------------------------
landlord_settings_bp = Blueprint(
    "landlord_settings", __name__, template_folder="templates"
)

# --------------------------------
# DATABASE MODEL
# --------------------------------
class LandlordSettings(db.Model):
    __tablename__ = "landlord_settings"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    payment_method = db.Column(db.String(50), nullable=False)
    paybill_number = db.Column(db.String(20))
    till_number = db.Column(db.String(20))
    send_money_number = db.Column(db.String(20))
    phone_number = db.Column(db.String(50))  # Optional account name or phone
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self):
        return f"<LandlordSettings user_id={self.user_id} method={self.payment_method}>"

# --------------------------------
# ROUTES
# --------------------------------
@landlord_settings_bp.route("/settings/payment", methods=["GET", "POST"])
@login_required
def settings_payment():
    """
    Page where a landlord chooses how tenants pay (Paybill, Till, Send Money).
    Saves or updates settings tied to the logged-in user.
    """
    user_id = current_user.id
    settings = LandlordSettings.query.filter_by(user_id=user_id).first()

    if request.method == "POST":
        payment_method = request.form.get("payment_method")
        account_number = request.form.get("account_number", "").strip()
        pay_name = request.form.get("pay_name", "").strip()

        if not payment_method or not account_number:
            flash("⚠️ Please select a payment method and provide an account number.", "warning")
            return redirect(url_for("landlord_settings.settings_payment"))

        # Update existing record
        if settings:
            settings.payment_method = payment_method
            settings.phone_number = pay_name or settings.phone_number
            settings.paybill_number = account_number if payment_method == "Paybill" else None
            settings.till_number = account_number if payment_method == "Till" else None
            settings.send_money_number = account_number if payment_method == "Send Money" else None
            flash("✅ Payment settings updated successfully!", "success")

        # Create new record
        else:
            settings = LandlordSettings(
                user_id=user_id,
                payment_method=payment_method,
                paybill_number=account_number if payment_method == "Paybill" else None,
                till_number=account_number if payment_method == "Till" else None,
                send_money_number=account_number if payment_method == "Send Money" else None,
                phone_number=pay_name,
            )
            db.session.add(settings)
            flash("✅ Payment settings saved successfully!", "success")

        db.session.commit()
        return redirect(url_for("landlord_settings.settings_payment"))

    # GET method
    return render_template("settings_payment.html", settings=settings)

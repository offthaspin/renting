# rentme/landlord_settings.py
import os
import base64
import requests
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from .extensions import db
from .models import LandlordSettings
from .forms import MPesaSettingsForm


# -------------------------------------------------
# BLUEPRINT
# -------------------------------------------------
# landlord_settings.py
landlord_settings_bp = Blueprint('landlord_settings', __name__, url_prefix="/landlord")

# -------------------------------------------------
# Helper: get or create the landlord's settings row
# -------------------------------------------------
def get_or_create_settings():
    s = LandlordSettings.query.filter_by(user_id=current_user.id).first()
    if not s:
        s = LandlordSettings(user_id=current_user.id)
        db.session.add(s)
        db.session.commit()
    return s


# -------------------------------------------------
# -------------------------------------------------
# SETTINGS PAGE — GET + POST
# -------------------------------------------------
@landlord_settings_bp.route("/payment", methods=["GET", "POST"])
@login_required
def settings_payment():
    """Render and save per-landlord MPesa + payment options."""

    # Only landlords allowed
    if not getattr(current_user, "is_landlord", True):
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard"))

    # Fetch or create landlord settings
    settings = get_or_create_settings()
    form = MPesaSettingsForm()

    if form.validate_on_submit():
        # ----------------------------
        # Payment method fields
        # ----------------------------
        settings.payment_method = form.payment_method.data or settings.payment_method
        settings.paybill_number = form.paybill_number.data or None
        settings.till_number = form.till_number.data or None
        settings.send_money_number = form.send_money_number.data or None
        settings.phone_number = form.phone_number.data or settings.phone_number

        # ----------------------------
        # MPESA API credentials
        # ----------------------------
        if form.mpesa_consumer_key.data:
            settings.mpesa_consumer_key = form.mpesa_consumer_key.data
        if form.mpesa_consumer_secret.data:
            settings.mpesa_consumer_secret = form.mpesa_consumer_secret.data
        if form.mpesa_shortcode.data:
            settings.mpesa_shortcode = form.mpesa_shortcode.data
        if form.mpesa_passkey.data:
            settings.mpesa_passkey = form.mpesa_passkey.data
        if form.callback_url.data:
            settings.callback_url = form.callback_url.data

        settings.mpesa_mode = form.mpesa_mode.data or "production"

        # Commit changes
        db.session.commit()
        flash("✅ Payment & MPesa settings saved.", "success")

        # -------------------------------------------------------
        # FIXED REDIRECT — correct blueprint endpoint name
        # -------------------------------------------------------
        return redirect(url_for("landlord_settings.settings_payment"))

    else:
        # Pre-fill form with existing settings
        form.payment_method.data = settings.payment_method
        form.paybill_number.data = settings.paybill_number
        form.till_number.data = settings.till_number
        form.send_money_number.data = settings.send_money_number
        form.phone_number.data = settings.phone_number
        form.mpesa_consumer_key.data = settings.mpesa_consumer_key
        form.mpesa_consumer_secret.data = settings.mpesa_consumer_secret
        form.mpesa_shortcode.data = settings.mpesa_shortcode
        form.mpesa_passkey.data = settings.mpesa_passkey
        form.mpesa_mode.data = settings.mpesa_mode
        form.callback_url.data = settings.callback_url

    return render_template("settings_payment.html", settings=settings, form=form)




# -------------------------------------------------
# TEST MPESA CREDENTIALS
# -------------------------------------------------
@landlord_settings_bp.route("/settings/payment/test", methods=["POST"])
@login_required
def test_mpesa():
    """Test MPesa Consumer Key + Secret using Daraja OAuth call."""

    settings = get_or_create_settings()
    body = request.get_json(silent=True) or {}

    # Prefer JSON body, fallback to form, fallback to DB settings
    consumer_key = (
        body.get("consumer_key")
        or request.form.get("consumer_key")
        or settings.mpesa_consumer_key
    )

    consumer_secret = (
        body.get("consumer_secret")
        or request.form.get("consumer_secret")
        or settings.mpesa_consumer_secret
    )

    shortcode = (
        body.get("shortcode")
        or request.form.get("shortcode")
        or settings.mpesa_shortcode
    )

    mode = (
        body.get("mode")
        or request.form.get("mode")
        or settings.mpesa_mode
        or "production"
    ).lower()

    if not consumer_key or not consumer_secret:
        return jsonify({"ok": False, "msg": "Missing Consumer Key or Secret"}), 400

    # Daraja OAuth URL
    auth_url = (
        "https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
        if mode == "production"
        else "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    )

    try:
        r = requests.get(auth_url, auth=(consumer_key, consumer_secret), timeout=10)

        if r.status_code not in (200, 201):
            try:
                data = r.json()
            except:
                data = {"raw": r.text}

            return jsonify({
                "ok": False,
                "msg": "OAuth Request Failed",
                "status": r.status_code,
                "response": data
            }), 400

        data = r.json()
        token = data.get("access_token")

        return jsonify({
            "ok": True,
            "msg": "MPesa Credentials Are Valid ✔️",
            "token_sample": f"{token[:8]}..." if token else None,
            "environment": mode
        })

    except requests.RequestException as ex:
        return jsonify({
            "ok": False,
            "msg": "Network Error",
            "error": str(ex)
        }), 500

#rentme/utils.py
"""
Notifications & utilities module

Provides:
- send_reset_email(to_email, token, subject=None, body=None)
- send_sms_via_africastalking(phone_number, message)
- send_sms_via_twilio(phone_number, message)  # optional
- normalize_msisdn(phone)  -> returns normalized string like '2547XXXXXXXX'
- generate_reset_token(email)
- verify_reset_token(token, max_age=3600)
- mask_secret(s) -> for safe logs
"""

import re
import logging
import smtplib
from email.mime.text import MIMEText
from typing import Optional

from flask import current_app
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from typing import Optional
from flask import current_app
import logging



log = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def _mask_secret(s: Optional[str], keep: int = 4) -> str:
    """Return masked secret with last `keep` chars visible (for safe logging)."""
    if not s:
        return ""
    s = str(s)
    if len(s) <= keep:
        return "*" * len(s)
    return "*" * (len(s) - keep) + s[-keep:]


# ---------------------------------------------------------------------
# Email sending 
# ---------------------------------------------------------------------
def send_reset_email(
    to_email: str,
    token: str,
    subject: Optional[str] = None,
    body: Optional[str] = None
) -> bool:
    """
    Send password reset email using mail-api.dev with debug logs
    """

    if not current_app:
        log.error("Flask current_app not available")
        return False

    api_key = current_app.config.get("MAIL_API_KEY")
    email_from = current_app.config.get("EMAIL_FROM")
    base_url = current_app.config.get("BASE_URL", "").rstrip("/")

    if not api_key or not email_from or not base_url:
        log.error("Mail API configuration missing")
        return False

    reset_link = f"{base_url}/reset_password/{token}"

    subject = subject or "Password Reset"
    body = body or f"""Hello,

You requested a password reset.

Click the link below to reset your password:
{reset_link}

This link expires in 1 hour.

If you didn’t request this, ignore this email.

— RentMe Team
"""

    try:
        response = requests.post(
            "https://mail-api.dev/api/send",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": email_from,
                "to": to_email,
                "subject": subject,
                "text": body,
            },
            timeout=10,
        )

        # DEBUG: print response for troubleshooting
        print(f"[DEBUG] status_code: {response.status_code}, response_text: {response.text}")

        if response.status_code in (200, 202):
            log.info("Password reset email sent to %s", to_email)
            return True

        log.error("Mail API error %s: %s", response.status_code, response.text)
        return False

    except Exception as e:
        log.exception("Mail API exception: %s", e)
        return False

# ---------------------------------------------------------------------
# Africa's Talking SMS (safe import inside function)
# ---------------------------------------------------------------------
def send_sms_via_africastalking(phone_number: str, message: str) -> bool:
    """
    Send an SMS via Africa's Talking.
    Uses AFRICASTALKING_USERNAME and AFRICASTALKING_API_KEY from config.
    Returns True if send succeeded (or SDK returned success), False otherwise.
    """
    if not current_app:
        log.error("current_app unavailable in send_sms_via_africastalking")
        return False

    username = current_app.config.get("AFRICASTALKING_USERNAME")
    api_key = current_app.config.get("AFRICASTALKING_API_KEY")

    if not username or not api_key:
        log.warning(
            "AFRICASTALKING credentials not configured. SMS not sent. phone=%s message=%s",
            phone_number,
            (message[:120] + "...") if message and len(message) > 120 else message,
        )
        return False

    # Import SDK lazily so missing dependency doesn't break app import-time
    try:
        # The SDK API differs across versions; handle both common patterns
        import africastalking as at_sdk
    except Exception as e:
        log.exception("africastalking SDK not available: %s", e)
        return False

    try:
        at = at_sdk.initialize(username=username, api_key=api_key)
        sms = at.SMS
        response = sms.send(message=message, to=[phone_number])
        log.info("Africa's Talking SMS response: %s", response)
        return True
    except Exception as e:
        log.exception("Failed to send SMS via Africa's Talking to %s: %s", phone_number, e)
        return False


# ---------------------------------------------------------------------
# Twilio support (optional). Use only if configured.
# ---------------------------------------------------------------------
def send_sms_via_twilio(phone_number: str, message: str) -> bool:
    """
    Send SMS using Twilio if TWILIO_SID/TWILIO_TOKEN/TWILIO_FROM are set in config.
    Returns True on success, False on failure.
    """
    if not current_app:
        log.error("current_app unavailable in send_sms_via_twilio")
        return False

    sid = current_app.config.get("TWILIO_SID")
    token = current_app.config.get("TWILIO_TOKEN")
    sender = current_app.config.get("TWILIO_FROM")

    if not sid or not token or not sender:
        log.debug("Twilio not configured; skipping Twilio SMS.")
        return False

    try:
        from twilio.rest import Client as TwilioClient
    except Exception:
        log.exception("twilio package not installed.")
        return False

    try:
        client = TwilioClient(sid, token)
        client.messages.create(body=message, from_=sender, to=phone_number)
        log.info("Twilio SMS sent to %s", phone_number)
        return True
    except Exception as e:
        log.exception("Failed to send SMS via Twilio to %s: %s", phone_number, e)
        return False


# ---------------------------------------------------------------------
# Phone normalization
def normalize_msisdn(phone: Optional[str]) -> str:
    """
    Normalize Kenyan phone numbers to the canonical format: 2547XXXXXXXX
    Returns empty string for invalid or non-Kenyan numbers.
    """
    if not phone:
        return ""

    # Convert to string & strip
    s = str(phone).strip()

    # Remove everything except digits
    s = re.sub(r"\D", "", s)

    # Handle common Kenyan formats
    # 0712345678  -> 254712345678
    if s.startswith("0") and len(s) == 10:
        s = "254" + s[1:]

    # 712345678 -> 254712345678
    elif s.startswith("7") and len(s) == 9:
        s = "254" + s

    # +254712345678 or 254712345678
    elif s.startswith("254") and len(s) == 12:
        pass  # already correct

    # Long numbers containing Kenyan MSISDN (e.g. 00254712345678)
    elif "2547" in s:
        idx = s.find("2547")
        s = s[idx:idx + 12]

    else:
        return ""

    # Final strict validation
    if not re.fullmatch(r"2547\d{8}", s):
        return ""

    return s

# ---------------------------------------------------------------------
# Token generation and verification (password reset)
# ---------------------------------------------------------------------
def generate_reset_token(email: str) -> str:
    """
    Generate a URL-safe timed token for password reset.
    Uses SECRET_KEY from Flask config.
    """
    secret = current_app.config.get("SECRET_KEY", None)
    if not secret:
        log.error("SECRET_KEY not configured; cannot generate reset token.")
        raise RuntimeError("SECRET_KEY not configured in Flask app config")
    s = URLSafeTimedSerializer(secret)
    return s.dumps(email, salt="password-reset-salt")


def verify_reset_token(token: str, max_age: int = 3600) -> Optional[str]:
    """
    Verify a reset token (returns the email if valid, None otherwise).
    max_age is in seconds; default 3600 (1 hour).
    """
    secret = current_app.config.get("SECRET_KEY", None)
    if not secret:
        log.error("SECRET_KEY not configured; cannot verify token.")
        return None
    s = URLSafeTimedSerializer(secret)
    try:
        email = s.loads(token, salt="password-reset-salt", max_age=max_age)
        return email
    except SignatureExpired:
        log.info("Reset token expired.")
        return None
    except BadSignature:
        log.warning("Invalid reset token signature.")
        return None
    except Exception:
        log.exception("Unexpected error while verifying reset token.")
        return None

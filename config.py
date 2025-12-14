import os
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect

# Load .env file
load_dotenv()


class Config:
    # -------------------------
    # Database
    # -------------------------
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # -------------------------
    # Security
    # -------------------------
    SECRET_KEY = os.environ.get("SECRET_KEY", os.urandom(32))
    FLASK_ENV = os.environ.get("FLASK_ENV", "production")

    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True

    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False

    # -------------------------
    # Africa's Talking
    # -------------------------
    AT_USERNAME = os.environ.get("AFRICASTALKING_USERNAME")
    AT_API_KEY = os.environ.get("AFRICASTALKING_API_KEY")
    AT_SENDER = os.environ.get("AT_SENDER", "Rentana")

    # -------------------------
    # Twilio (optional)
    # -------------------------
    TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
    TWILIO_FROM = os.environ.get("TWILIO_FROM")

    # -------------------------
    # MPESA CONFIG
    # -------------------------
    MPESA_ENV = os.environ.get("MPESA_ENV", "sandbox")

    # Live Credentials
    LIVE_CONSUMER_KEY = os.environ.get("LIVE_CONSUMER_KEY")
    LIVE_CONSUMER_SECRET = os.environ.get("LIVE_CONSUMER_SECRET")
    LIVE_SHORTCODE = os.environ.get("LIVE_SHORTCODE")
    LIVE_PASSKEY = os.environ.get("LIVE_PASSKEY")

    # Sandbox Credentials
    SANDBOX_CONSUMER_KEY = os.environ.get("SANDBOX_CONSUMER_KEY")
    SANDBOX_CONSUMER_SECRET = os.environ.get("SANDBOX_CONSUMER_SECRET")
    SANDBOX_SHORTCODE = os.environ.get("SANDBOX_SHORTCODE")
    SANDBOX_PASSKEY = os.environ.get("SANDBOX_PASSKEY")

    # Callback
    CALLBACK_BASE = os.environ.get("CALLBACK_BASE")


    #secure Cookies
    SESSION_COOKIE_SECURE = True            # HTTPS only
    SESSION_COOKIE_HTTPONLY = True          # JS cannot access
    SESSION_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True


    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600

    csrf = CSRFProtect(app)


    # Derived Values
    @property
    def MPESA_CONSUMER_KEY(self):
        return (
            self.LIVE_CONSUMER_KEY
            if self.MPESA_ENV == "live"
            else self.SANDBOX_CONSUMER_KEY
        )

    @property
    def MPESA_CONSUMER_SECRET(self):
        return (
            self.LIVE_CONSUMER_SECRET
            if self.MPESA_ENV == "live"
            else self.SANDBOX_CONSUMER_SECRET
        )

    @property
    def MPESA_SHORTCODE(self):
        return (
            self.LIVE_SHORTCODE
            if self.MPESA_ENV == "live"
            else self.SANDBOX_SHORTCODE
        )

    @property
    def MPESA_PASSKEY(self):
        return (
            self.LIVE_PASSKEY
            if self.MPESA_ENV == "live"
            else self.SANDBOX_PASSKEY
        )

    @property
    def MPESA_CALLBACK_URL(self):
        return f"{self.CALLBACK_BASE}/stkpush"

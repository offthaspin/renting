import os
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect

# Load .env file
load_dotenv()



class Config:
    # ------------------------------------------------------------------
    # Security
    # ------------------------------------------------------------------
    SECRET_KEY = os.environ.get("SECRET_KEY", os.urandom(32))
    FLASK_ENV = os.environ.get("FLASK_ENV", "production")

    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True

    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ------------------------------------------------------------------
    # Email (mail-api.dev)
    # ------------------------------------------------------------------
    MAIL_API_KEY = os.environ.get("MAIL_API_KEY")
    EMAIL_FROM = os.environ.get("EMAIL_FROM")
    BASE_URL = os.environ.get("BASE_URL")

    # ------------------------------------------------------------------
    # Africa's Talking
    # ------------------------------------------------------------------
    AT_USERNAME = os.environ.get("AFRICASTALKING_USERNAME")
    AT_API_KEY = os.environ.get("AFRICASTALKING_API_KEY")
    AT_SENDER = os.environ.get("AT_SENDER", "Rentana")

    # ------------------------------------------------------------------
    # MPESA
    # ------------------------------------------------------------------
    MPESA_ENV = os.environ.get("MPESA_ENV", "sandbox")

    LIVE_CONSUMER_KEY = os.environ.get("LIVE_CONSUMER_KEY")
    LIVE_CONSUMER_SECRET = os.environ.get("LIVE_CONSUMER_SECRET")
    LIVE_SHORTCODE = os.environ.get("LIVE_SHORTCODE")
    LIVE_PASSKEY = os.environ.get("LIVE_PASSKEY")

    SANDBOX_CONSUMER_KEY = os.environ.get("SANDBOX_CONSUMER_KEY")
    SANDBOX_CONSUMER_SECRET = os.environ.get("SANDBOX_CONSUMER_SECRET")
    SANDBOX_SHORTCODE = os.environ.get("SANDBOX_SHORTCODE")
    SANDBOX_PASSKEY = os.environ.get("SANDBOX_PASSKEY")

    CALLBACK_BASE = os.environ.get("CALLBACK_BASE")

    @property
    def MPESA_CALLBACK_URL(self):
        return f"{self.CALLBACK_BASE.rstrip('/')}/stkpush"

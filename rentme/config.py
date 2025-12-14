import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()


class Config:
    # -------------------------
    # Flask / Security
    # -------------------------
    SECRET_KEY = os.environ.get("RENTANA_SECRET", os.urandom(32))
    FLASK_ENV = os.environ.get("FLASK_ENV", "production")

    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = os.environ.get("FLASK_SECURE_COOKIES", "1") == "1"
    REMEMBER_COOKIE_SECURE = os.environ.get("FLASK_SECURE_COOKIES", "1") == "1"
    SESSION_COOKIE_SAMESITE = 'Lax'

    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600

    # Example for local development
    BASE_URL = "http://127.0.0.1:5000"  # or your deployed domain
    EMAIL_FROM = "noreply@rentana.com"
    SMTP_SERVER = "smtp.yourmail.com"
    SMTP_PORT = 587
    SMTP_USERNAME = "your_username"
    SMTP_PASSWORD = "your_password"


    

    # -------------------------
    # Database
    # -------------------------
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # -------------------------
    # Africa's Talking
    # -------------------------
    AT_USERNAME = os.environ.get("AFRICASTALKING_USERNAME")
    AT_API_KEY = os.environ.get("AFRICASTALKING_API_KEY")
    AT_SENDER = os.environ.get("AT_SENDER", "Rentana")

    # -------------------------
    # MPESA CONFIG
    # -------------------------
    MPESA_ENV = os.environ.get("MPESA_ENV", "sandbox")

    # Live credentials
    LIVE_CONSUMER_KEY = os.environ.get("LIVE_CONSUMER_KEY")
    LIVE_CONSUMER_SECRET = os.environ.get("LIVE_CONSUMER_SECRET")
    LIVE_SHORTCODE = os.environ.get("LIVE_SHORTCODE")
    LIVE_PASSKEY = os.environ.get("LIVE_PASSKEY")

    # Sandbox credentials
    SANDBOX_CONSUMER_KEY = os.environ.get("SANDBOX_CONSUMER_KEY")
    SANDBOX_CONSUMER_SECRET = os.environ.get("SANDBOX_CONSUMER_SECRET")
    SANDBOX_SHORTCODE = os.environ.get("SANDBOX_SHORTCODE")
    SANDBOX_PASSKEY = os.environ.get("SANDBOX_PASSKEY")

    CALLBACK_BASE = os.environ.get("CALLBACK_BASE", "http://localhost:5000")

    # -------------------------
    # Rate Limiter
    # -------------------------
    RATELIMIT_DEFAULT = "200 per day;50 per hour"
    RATELIMIT_HEADERS_ENABLED = True

    # -------------------------
    # Derived MPESA properties
    # -------------------------
    @property
    def MPESA_CONSUMER_KEY(self):
        return self.LIVE_CONSUMER_KEY if self.MPESA_ENV == "live" else self.SANDBOX_CONSUMER_KEY

    @property
    def MPESA_CONSUMER_SECRET(self):
        return self.LIVE_CONSUMER_SECRET if self.MPESA_ENV == "live" else self.SANDBOX_CONSUMER_SECRET

    @property
    def MPESA_SHORTCODE(self):
        return self.LIVE_SHORTCODE if self.MPESA_ENV == "live" else self.SANDBOX_SHORTCODE

    @property
    def MPESA_PASSKEY(self):
        return self.LIVE_PASSKEY if self.MPESA_ENV == "live" else self.SANDBOX_PASSKEY

    @property
    def MPESA_CALLBACK_URL(self):
        return f"{self.CALLBACK_BASE}/stkpush"

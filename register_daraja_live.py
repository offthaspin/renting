"""
Safaricom Daraja C2B URL Registration (Dynamic Web + CLI)
----------------------------------------------------------
✅ Works standalone (CLI mode) OR as a web app (Flask)
✅ No .env needed – accepts credentials from frontend
✅ Supports LIVE and SANDBOX with HTTPS validation
✅ Gracefully handles duplicate registrations
"""

import os
import sys
import json
import urllib.parse
import requests
import logging
from requests.auth import HTTPBasicAuth
from flask import Flask, render_template, request, jsonify

# =======================================================
# LOGGING SETUP
# =======================================================
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
LOG_FILE = os.path.join(BASE_DIR, "daraja_register.log")
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(console_handler)

# =======================================================
# UTILITIES
# =======================================================
def clean_url(u: str, live: bool = False) -> str:
    """Trim spaces, validate full URL, enforce HTTPS if live."""
    if not u:
        raise ValueError("Empty URL")

    u = u.strip().replace(" ", "")
    parsed = urllib.parse.urlparse(u)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or not parsed.path:
        raise ValueError(f"Invalid URL format: {u}")

    if live and parsed.scheme != "https":
        raise ValueError("LIVE environment requires HTTPS callback URLs.")

    return urllib.parse.urlunparse(parsed._replace(fragment=""))

def pretty_print_response(resp):
    """Pretty-print Daraja JSON responses."""
    try:
        j = resp.json()
        logger.info(json.dumps(j, indent=2))
    except Exception:
        logger.warning(resp.text)

# =======================================================
# CORE REGISTRATION LOGIC
# =======================================================
def register_urls(env_name, base_url, key, secret, shortcode, callback_base, live=False):
    result = {"env": env_name, "status": "failed", "response": None}
    logger.info(f"\n🔐 Attempting {env_name} Daraja registration...")

    # Get access token
    try:
        token_url = f"{base_url}/oauth/v1/generate?grant_type=client_credentials"
        token_res = requests.get(token_url, auth=HTTPBasicAuth(key, secret), timeout=10)
        token_res.raise_for_status()
        access_token = token_res.json().get("access_token")
    except Exception as e:
        logger.error(f"{env_name}: Token request failed → {e}")
        return result

    if not access_token:
        logger.error(f"{env_name}: No access_token in response.")
        pretty_print_response(token_res)
        return result

    logger.info(f"✅ {env_name}: Token generated successfully.")

    # Validate callback URLs
    try:
        confirm_url = clean_url(f"{callback_base}/confirm", live)
        validate_url = clean_url(f"{callback_base}/validate", live)
    except ValueError as e:
        logger.error(f"{env_name}: Callback URL validation failed → {e}")
        return result

    payload = {
        "ShortCode": shortcode,
        "ResponseType": "Completed",
        "ConfirmationURL": confirm_url,
        "ValidationURL": validate_url,
    }
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    logger.info(f"📡 Registering for {env_name}:\n{json.dumps(payload, indent=2)}")

    try:
        res = requests.post(f"{base_url}/mpesa/c2b/v1/registerurl", headers=headers, json=payload, timeout=10)
    except Exception as e:
        logger.error(f"{env_name}: Registration request failed → {e}")
        return result

    if res.status_code == 200:
        logger.info(f"✅ {env_name}: URL registration successful.")
        pretty_print_response(res)
        result.update(status="success", response=res.json())
        return result

    # Handle duplicate registration
    try:
        body = res.json()
        if body.get("errorCode") == "500.003.1001":
            logger.info(f"ℹ️ {env_name}: Already registered (duplicate). Treating as success.")
            result.update(status="success", response=body)
            return result
    except Exception:
        body = res.text

    logger.warning(f"⚠️ {env_name}: Registration failed ({res.status_code}) → {body}")
    result.update(response=body)
    return result

# =======================================================
# INTERACTIVE CLI MODE
# =======================================================
def run_registration_interactive():
    print("\n🧠 Dynamic Daraja C2B Registration Setup")
    print("--------------------------------------")
    env_choice = input("Environment (live/sandbox): ").strip().lower() or "sandbox"
    consumer_key = input("Consumer Key: ").strip()
    consumer_secret = input("Consumer Secret: ").strip()
    shortcode = input("Short Code: ").strip()
    callback_base = input("Callback Base URL (https://xxxx.ngrok-free.app/payment_callback): ").strip()

    if not all([consumer_key, consumer_secret, shortcode, callback_base]):
        print("❌ Missing required fields. Try again.")
        sys.exit(1)

    live = env_choice == "live"
    base_url = "https://api.safaricom.co.ke" if live else "https://sandbox.safaricom.co.ke"

    result = register_urls(env_choice.upper(), base_url, consumer_key, consumer_secret, shortcode, callback_base, live=live)
    print("\n🏁 Final Result:")
    print(json.dumps(result, indent=2))

# =======================================================
# FLASK WEB UI MODE
# =======================================================
app = Flask(__name__)

@app.route("/")
def index():
    return """
    <h2>Daraja Registration Portal</h2>
    <ul>
      <li><a href='/register_sandbox'>Register Sandbox</a></li>
      <li><a href='/register_live'>Register Live</a></li>
    </ul>
    """

@app.route("/register_live")
def register_live():
    return render_template("register_live.html")

@app.route("/register_sandbox")
def register_sandbox():
    return render_template("register_sandbox.html")

@app.route("/api/register", methods=["POST"])
def api_register():
    data = request.get_json()
    env = data.get("env", "sandbox").lower()
    key = data.get("consumer_key")
    secret = data.get("consumer_secret")
    shortcode = data.get("shortcode")
    callback = data.get("callback_url")

    if not all([key, secret, shortcode, callback]):
        return jsonify({"status": "error", "message": "All fields are required"}), 400

    live = env == "live"
    base_url = "https://api.safaricom.co.ke" if live else "https://sandbox.safaricom.co.ke"

    result = register_urls(env.upper(), base_url, key, secret, shortcode, callback, live)
    return jsonify(result)

# =======================================================
# ENTRYPOINT
# =======================================================
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "web":
        print("🌍 Starting Flask Daraja UI at http://127.0.0.1:5005")
        app.run(debug=True, port=5005)
    else:
        run_registration_interactive()

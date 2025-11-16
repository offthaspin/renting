#!/usr/bin/env python3
"""
Improved STK Push script (Environment-based)
--------------------------------------------
- Reads credentials from .env
- Validates inputs and phone format
- Generates password (ShortCode + PassKey + Timestamp)
- Retries requests on failure
- Redacts sensitive info in logs
- Works for both LIVE and SANDBOX (auto-switch)
"""
import os
import sys
import time
import json
import base64
import requests
from datetime import datetime
from typing import Any, Dict
from dotenv import load_dotenv

# -------- Load Environment --------
load_dotenv()

# -------- Configuration --------
MPESA_ENV = os.getenv("MPESA_ENV", "sandbox").lower()
if MPESA_ENV not in ("sandbox", "live"):
    MPESA_ENV = "sandbox"

CONSUMER_KEY = os.getenv("MPESA_CONSUMER_KEY")
CONSUMER_SECRET = os.getenv("MPESA_CONSUMER_SECRET")
SHORTCODE = os.getenv("MPESA_SHORTCODE")
PASSKEY = os.getenv("MPESA_PASSKEY")
CALLBACK_URL = os.getenv("MPESA_CALLBACK_URL")

if not all([CONSUMER_KEY, CONSUMER_SECRET, SHORTCODE, PASSKEY, CALLBACK_URL]):
    print("❌ Missing required .env variables for M-Pesa configuration.")
    sys.exit(1)

# Base URLs
if MPESA_ENV == "live":
    BASE_URL = "https://api.safaricom.co.ke"
else:
    BASE_URL = "https://sandbox.safaricom.co.ke"

OAUTH_URL = f"{BASE_URL}/oauth/v1/generate?grant_type=client_credentials"
STK_PUSH_URL = f"{BASE_URL}/mpesa/stkpush/v1/processrequest"

TIMEOUT = 10
MAX_RETRIES = 3
RETRY_DELAY = 1.0

# -------- Helpers --------
def format_phone(phone: str) -> str:
    p = phone.strip()
    if p.startswith("+"):
        p = p[1:]
    if p.startswith("0") and len(p) == 10:
        return "254" + p[1:]
    if p.startswith("7") and len(p) == 9:
        return "254" + p
    if p.startswith("254") and len(p) == 12:
        return p
    raise ValueError(f"Invalid phone format: {phone}")

def ts_now() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")

def generate_password(shortcode: str, passkey: str, timestamp: str) -> str:
    raw = f"{shortcode}{passkey}{timestamp}"
    return base64.b64encode(raw.encode()).decode("utf-8")

def redacted(s: str) -> str:
    if not s:
        return ""
    if len(s) <= 12:
        return s[:3] + "..." + s[-3:]
    return s[:6] + "..." + s[-6:]

def request_with_retries(method: str, url: str, **kwargs) -> requests.Response:
    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.request(method, url, timeout=TIMEOUT, **kwargs)
            return r
        except requests.RequestException as e:
            last_exc = e
            print(f"Request failed (attempt {attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
    raise last_exc

# -------- Tenant Data (Example) --------
tenant = {
    "Name": "Kareem Juma",
    "Phone": "254114713717",
    "House No": 24,
    "Balance": 200
}

try:
    phone_number = format_phone(tenant["Phone"])
except Exception as e:
    print("❌ Phone formatting error:", e)
    sys.exit(1)

if "<paste" in PASSKEY or "xxxx" in PASSKEY:
    print("❌ Error: PASSKEY is placeholder. Replace with actual passkey.")
    sys.exit(1)

# -------- 1️⃣ Get OAuth Token --------
print(f"\n🔐 Requesting OAuth token from {MPESA_ENV.upper()}...")
token_resp = request_with_retries("GET", OAUTH_URL, auth=(CONSUMER_KEY, CONSUMER_SECRET))
print("HTTP Status:", token_resp.status_code)
try:
    token_resp.raise_for_status()
except Exception:
    print("Failed to obtain access token. Response body:", token_resp.text)
    sys.exit(1)

token_body = token_resp.json()
access_token = token_body.get("access_token")
if not access_token:
    print("Access token missing in response:", json.dumps(token_body, indent=2))
    sys.exit(1)
print("✅ Access Token generated successfully (redacted):", redacted(access_token))

# -------- 2️⃣ Build STK Payload --------
timestamp = ts_now()
password = generate_password(SHORTCODE, PASSKEY, timestamp)
amount = int(tenant["Balance"])
payload: Dict[str, Any] = {
    "BusinessShortCode": SHORTCODE,
    "Password": password,
    "Timestamp": timestamp,
    "TransactionType": "CustomerPayBillOnline",
    "Amount": amount,
    "PartyA": phone_number,
    "PartyB": SHORTCODE,
    "PhoneNumber": phone_number,
    "CallBackURL": CALLBACK_URL,
    "AccountReference": f"House {tenant['House No']}",
    "TransactionDesc": f"Rent Payment for {tenant['Name']}"
}

print("\n📦 STK Push Payload Sent (redacted):")
redacted_payload = {k: ("<hidden>" if k == "Password" else v) for k, v in payload.items()}
print(json.dumps(redacted_payload, indent=2))

# -------- 3️⃣ Send STK Push --------
headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
resp = request_with_retries("POST", STK_PUSH_URL, json=payload, headers=headers)
print("\n🌍 M-Pesa Response HTTP:", resp.status_code)

# -------- 4️⃣ Handle Response --------
try:
    resp_json = resp.json()
    print(json.dumps(resp_json, indent=2))
except Exception:
    print(resp.text)
    resp_json = None

if resp.status_code >= 400:
    print("\n⚠️ Debug summary:")
    print("  Shortcode:", SHORTCODE)
    print("  ConsumerKey:", redacted(CONSUMER_KEY))
    print("  Passkey:", redacted(PASSKEY))
    print("  Callback URL:", CALLBACK_URL)
    if isinstance(resp_json, dict):
        print("  errorCode:", resp_json.get("errorCode"))
        print("  errorMessage:", resp_json.get("errorMessage"))
    sys.exit(1)
else:
    if isinstance(resp_json, dict):
        print("\n✅ STK Push Accepted:")
        print("  MerchantRequestID:", resp_json.get("MerchantRequestID"))
        print("  CheckoutRequestID:", resp_json.get("CheckoutRequestID"))
        print("  ResponseCode:", resp_json.get("ResponseCode"))
        print("  ResponseDescription:", resp_json.get("ResponseDescription"))
    else:
        print("\n✅ Request appears successful; check your callback endpoint for confirmation.")

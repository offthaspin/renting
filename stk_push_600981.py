#!/usr/bin/env python3
import os, sys, json, base64, requests
from datetime import datetime

CONSUMER_KEY = os.getenv("MPESA_CONSUMER_KEY")
CONSUMER_SECRET = os.getenv("MPESA_CONSUMER_SECRET")
SHORTCODE = os.getenv("MPESA_SHORTCODE", "600981")
PASSKEY = os.getenv("MPESA_PASSKEY")
CALLBACK_URL = os.getenv("MPESA_CALLBACK_URL", "https://cf26f541e9e0.ngrok-free.app/payment_callback/stkpush")

OAUTH_URL = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
STK_PUSH_URL = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"

def format_phone(p):
    p = p.strip()
    if p.startswith("+"): p = p[1:]
    if p.startswith("0") and len(p) == 10: return "254"+p[1:]
    if p.startswith("7") and len(p) == 9: return "254"+p
    if p.startswith("254") and len(p) == 12: return p
    raise ValueError("Invalid phone format")

def ts(): return datetime.now().strftime("%Y%m%d%H%M%S")
def gen_password(shortcode, passkey, timestamp):
    return base64.b64encode(f"{shortcode}{passkey}{timestamp}".encode()).decode()

def red(s):
    if not s: return ""
    if len(s)<=12: return s[:3]+"..."+s[-3:]
    return s[:6]+"..."+s[-6:]

if not (CONSUMER_KEY and CONSUMER_SECRET and PASSKEY):
    print("Error: set MPESA_CONSUMER_KEY, MPESA_CONSUMER_SECRET and MPESA_PASSKEY in your environment")
    sys.exit(1)

tenant = {"Name":"Issa Kareem","Phone":"0797546387","House No":5,"Balance":800}
try:
    phone = format_phone(tenant["Phone"])
except Exception as e:
    print("Phone error:", e); sys.exit(1)

# OAuth
r = requests.get(OAUTH_URL, auth=(CONSUMER_KEY, CONSUMER_SECRET), timeout=10)
print("OAuth status:", r.status_code)
try:
    r.raise_for_status()
except Exception:
    print("OAuth failed:", r.text); sys.exit(1)
token = r.json().get("access_token")
print("Token present:", bool(token), "token (redacted):", red(token))

# build payload
timestamp = ts()
password = gen_password(SHORTCODE, PASSKEY, timestamp)
payload = {
  "BusinessShortCode": SHORTCODE,
  "Password": password,
  "Timestamp": timestamp,
  "TransactionType": "CustomerPayBillOnline",
  "Amount": int(tenant["Balance"]),
  "PartyA": phone,
  "PartyB": SHORTCODE,
  "PhoneNumber": phone,
  "CallBackURL": CALLBACK_URL,
  "AccountReference": f"House {tenant['House No']}",
  "TransactionDesc": f"Rent Payment for {tenant['Name']}"
}

print("\nPayload (redacted):")
print(json.dumps({k:("<hidden>" if k=="Password" else v) for k,v in payload.items()}, indent=2))

# STK Push
h = {"Authorization": f"Bearer {token}", "Content-Type":"application/json"}
resp = requests.post(STK_PUSH_URL, json=payload, headers=h, timeout=15)
print("\nSTK Push HTTP:", resp.status_code)
try:
    body = resp.json(); print(json.dumps(body, indent=2))
except Exception:
    print(resp.text); body = None

if resp.status_code >= 400:
    print("\nDebug:")
    print(" Shortcode:", SHORTCODE)
    print(" ConsumerKey (redacted):", red(CONSUMER_KEY))
    print(" Passkey (redacted):", red(PASSKEY))
    if isinstance(body, dict):
        print(" requestId:", body.get("requestId"))
        print(" errorCode:", body.get("errorCode"))
        print(" errorMessage:", body.get("errorMessage"))
    sys.exit(1)

print("\nSTK Push accepted. Save CheckoutRequestID and watch callback.")

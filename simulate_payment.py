import requests
from requests.auth import HTTPBasicAuth
import json

# ============ CONFIG ============
env = "sandbox"  # or "live"
shortcode = "600001"  # your registered shortcode
consumer_key = "RfoU0DNgOTrehcoRPgMdbhGzKMNAjCrgvMAjaYny4pclLnA2"
consumer_secret = "YbLFo4q51WJFZyQxTcknzXIL1nEr4B9pefPVWTnB1qDf7jvoa2atQQm6AYH0D5pu"

tenant_name = "kareem juma"
tenant_phone = "0114713717"
tenant_house = "13"
tenant_amount = "2000"
# ================================

def get_base_url(env):
    if env == "live":
        return "https://api.safaricom.co.ke"
    return "https://sandbox.safaricom.co.ke"

def get_access_token(env, key, secret):
    token_url = f"{get_base_url(env)}/oauth/v1/generate?grant_type=client_credentials"
    res = requests.get(token_url, auth=HTTPBasicAuth(key, secret))
    res.raise_for_status()
    return res.json()["access_token"]

def simulate_payment():
    print(f"\n🚀 Simulating {env.upper()} C2B Payment for {tenant_name}...")
    access_token = get_access_token(env, consumer_key, consumer_secret)
    print(f"✅ Access Token retrieved")

    simulate_url = f"{get_base_url(env)}/mpesa/c2b/v1/simulate"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    payload = {
        "ShortCode": shortcode,
        "CommandID": "CustomerPayBillOnline",
        "Amount": tenant_amount,
        "Msisdn": tenant_phone,
        "BillRefNumber": tenant_house
    }

    res = requests.post(simulate_url, headers=headers, json=payload)
    print("\n📡 Sending Simulation Request...")
    print(json.dumps(payload, indent=2))

    try:
        data = res.json()
    except:
        data = {"error": res.text}

    print("\n🏁 Response:")
    print(json.dumps(data, indent=2))

if __name__ == "__main__":
    simulate_payment()

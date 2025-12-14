#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
----------------------------------------------------------
RENTANA — FULL SIMULATION SCRIPT (Updated)
End-to-end: register user → login → add tenants → add M-Pesa settings → simulate payments
Now includes OwnerID resolution simulation for production-like testing.
----------------------------------------------------------
"""

import uuid
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import os
from dotenv import load_dotenv

# --------------------------
# Load .env
# --------------------------
load_dotenv()
MPESA_CALLBACK = os.getenv("MPESA_CALLBACK", "https://yourdomain.com/mpesa/callback")

# --------------------------
# Configuration
# --------------------------
BASE_URL = "https://bell-unwillful-adriene.ngrok-free.dev"
session = requests.Session()  # Maintain cookies across requests

# --------------------------
# 1️⃣ REGISTER FAKE USER
# --------------------------
def register_fake_user(full_name, email, phone, password):
    r = session.get(f"{BASE_URL}/register")
    soup = BeautifulSoup(r.text, "html.parser")
    csrf_token = soup.find("input", {"id": "csrf_token"})["value"]

    data = {
        "full_name": full_name,
        "email": email,
        "login_phone": phone,
        "password": password,
        "confirm": password,
        "csrf_token": csrf_token,
        "submit": "Register"
    }

    print(f"\n[REGISTER FAKE USER] {full_name}")
    response = session.post(f"{BASE_URL}/register", data=data)
    print("Status:", response.status_code)
    print("Response snippet:", response.text[:200])


# --------------------------
# 2️⃣ LOGIN USER
# --------------------------
def login_user(email_or_phone, password):
    r = session.get(f"{BASE_URL}/login")
    soup = BeautifulSoup(r.text, "html.parser")
    csrf_token = soup.find("input", {"id": "csrf_token"})["value"]

    data = {
        "identifier": email_or_phone,
        "password": password,
        "csrf_token": csrf_token,
        "submit": "Login"
    }

    response = session.post(f"{BASE_URL}/login", data=data)
    print(f"\n[LOGIN] {email_or_phone}")
    print("Status:", response.status_code)
    print("Response snippet:", response.text[:200])


# --------------------------
# 3️⃣ ADD TENANTS
# --------------------------
def register_tenant(name, phone, national_id, house_no, monthly_rent, move_in_date):
    r = session.get(f"{BASE_URL}/tenant/add")
    soup = BeautifulSoup(r.text, "html.parser")
    csrf_token = soup.find("input", {"id": "csrf_token"})["value"]

    data = {
        "name": name,
        "phone": phone,
        "national_id": national_id,
        "house_no": house_no,
        "monthly_rent": monthly_rent,
        "move_in_date": move_in_date,
        "csrf_token": csrf_token,
        "submit": "Save"
    }

    print(f"\n[REGISTER TENANT] {house_no} → {monthly_rent}")
    response = session.post(f"{BASE_URL}/tenant/add", data=data)
    print("Status:", response.status_code)
    print("Response snippet:", response.text[:200])


# --------------------------
# 4️⃣ ADD M-PESA / PAYMENT SETTINGS
# --------------------------
def add_mpesa_settings(payment_method, paybill, till, send_money_number, display_phone,
                       consumer_key, consumer_secret, shortcode, passkey, mode):
    r = session.get(f"{BASE_URL}/settings/payment")
    soup = BeautifulSoup(r.text, "html.parser")
    csrf_token = soup.find("input", {"id": "csrf_token"})["value"]

    data = {
        "payment_method": payment_method,
        "paybill_number": paybill,
        "till_number": till,
        "send_money_number": send_money_number,
        "phone_number": display_phone,
        "mpesa_consumer_key": consumer_key,
        "mpesa_consumer_secret": consumer_secret,
        "mpesa_shortcode": shortcode,
        "mpesa_passkey": passkey,
        "mpesa_mode": mode,
        "callback_url": MPESA_CALLBACK,
        "csrf_token": csrf_token,
        "submit": "Save Settings"
    }

    print(f"\n[ADDING M-PESA SETTINGS] Paybill: {paybill}")
    response = session.post(f"{BASE_URL}/settings/payment", data=data)
    print("Status:", response.status_code)
    print("Response snippet:", response.text[:200])


# --------------------------
# 5️⃣ SIMULATE STK PUSH
# --------------------------
def simulate_stk_push(house_no, amount):
    checkout_id = f"CHECKOUT_{house_no}_{uuid.uuid4().hex[:6]}"
    print(f"\n[SIMULATED STK PUSH] Tenant {house_no} paying {amount}")
    print("Generated CheckoutRequestID:", checkout_id)
    return checkout_id


# --------------------------
# 6️⃣ SEND MPESA CALLBACK (with OwnerID simulation)
# --------------------------
def send_callback(house_no, amount, checkout_id, owner_id=None):
    """
    Simulate M-Pesa callback. 
    If owner_id is provided, include it to prevent 'Missing OwnerID' errors in production.
    """
    url = f"{BASE_URL}/mpesa/payment_callback/confirmation"
    
    callback_item = [
        {"Name": "Amount", "Value": amount},
        {"Name": "MpesaReceiptNumber", "Value": "R" + uuid.uuid4().hex[:8].upper()},
        {"Name": "Balance"},
        {"Name": "TransactionDate", "Value": int(datetime.now().strftime("%Y%m%d%H%M%S"))},
        {"Name": "PhoneNumber", "Value": 254700123456},
        {"Name": "AccountReference", "Value": house_no},
    ]
    
    # Include OwnerID if provided
    if owner_id:
        callback_item.append({"Name": "OwnerID", "Value": owner_id})

    callback_data = {
        "Body": {
            "stkCallback": {
                "MerchantRequestID": "99999",
                "CheckoutRequestID": checkout_id,
                "ResultCode": 0,
                "ResultDesc": "The service request is processed successfully.",
                "CallbackMetadata": {"Item": callback_item}
            }
        }
    }

    print(f"\n[SENDING CALLBACK] → Tenant {house_no}")
    response = session.post(url, json=callback_data)
    print("Status:", response.status_code)
    print("Response snippet:", response.text[:200])


# --------------------------
# RUN FULL SIMULATION
# --------------------------
register_fake_user(
    full_name="Tenant Test1",
    email="tenant_test1@example.com",
    phone="0700123456",
    password="TestPass123!"
)

login_user("tenant_test1@example.com", "TestPass123!")

register_tenant("Alice", "0700111222", "12345678", "A101", "15000", "2025-12-01")
register_tenant("Bob", "0700222333", "87654321", "A102", "18000", "2025-12-01")
register_tenant("Charlie", "0700333444", "11223344", "A103", "12500", "2025-12-01")

add_mpesa_settings(
    payment_method="Paybill",
    paybill="512345",
    till="",
    send_money_number="254700000000",
    display_phone="0700123456",
    consumer_key="A_K3Y_9fd821aa",
    consumer_secret="A_S3CR3T_4be7fd20",
    shortcode="512345",
    passkey="A_PASSKEY_8921fda09123ab23",
    mode="sandbox"
)

checkout_A101 = simulate_stk_push("A101", 15000)

# Include a simulated OwnerID (for production-like test)
simulated_owner_id = "1"  # Replace with a real user ID from your DB if needed
send_callback("A101", 15000, checkout_A101, owner_id=simulated_owner_id)

print("\n✅ Simulation completed! Check your frontend dashboard for user, tenants, M-Pesa settings, and payment update.")

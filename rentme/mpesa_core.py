# mpesa_core.py
# Core M-Pesa logic placeholder (for testing sandbox)

import json

def process_direct_payment(amount, phone_number, account_reference="Rentana", description="Test Payment"):
    """
    Simulates processing a direct M-Pesa payment for sandbox testing.
    """
    print(f"📲 Simulating payment: {phone_number} -> {amount} ({account_reference})")
    mock_response = {
        "MerchantRequestID": "12345-abcde",
        "CheckoutRequestID": "67890-fghij",
        "ResponseCode": "0",
        "ResponseDescription": "Success. Request accepted for processing",
        "CustomerMessage": "Success. Payment simulated."
    }
    return mock_response

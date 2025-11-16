import re
import requests

# -------------------------
# ✅ Normalize MSISDN (Phone Number)
# -------------------------
def _normalize_msisdn(phone: str) -> str:
    """
    Normalize Kenyan phone numbers to 2547XXXXXXXX format.
    Accepts +2547, 07, or 7 prefixes.
    """
    if not phone:
        return ""
    phone = str(phone).strip()
    phone = re.sub(r"\D", "", phone)  # remove non-digits

    if phone.startswith("0"):
        phone = "254" + phone[1:]
    elif phone.startswith("7"):
        phone = "254" + phone
    elif phone.startswith("+254"):
        phone = "254" + phone[4:]
    elif not phone.startswith("254"):
        phone = "254" + phone
    return phone[:12]


# -------------------------
# ✅ Send SMS (stub for now)
# -------------------------
def _send_sms(phone: str, message: str) -> bool:
    """
    Simulate sending an SMS. Replace with real integration later.
    """
    try:
        print(f"📩 Sending SMS to {phone}: {message}")
        # Example if you later integrate with Africa's Talking or Twilio:
        # requests.post("https://api.africastalking.com/sms/send", data={...})
        return True
    except Exception as e:
        print(f"⚠️ SMS sending failed: {e}")
        return False

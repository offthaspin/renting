Updated Rentana package (prepared by assistant)
- Added templates/payment_settings.html (copy of settings_payment.html) so render_template("payment_settings.html") works.
- Added africastalking==2.2.0 to requirements.txt.
- Created static/receipts/ for storing generated PDF receipts.
- Added .env.example with required environment variables (AFRICASTALKING_USERNAME, AFRICASTALKING_API_KEY, AT_SENDER).
- Kept existing mpesa_handler.py and wiring in app.py (route /webhook/mpesa).
IMPORTANT: Fill .env with your Africa's Talking credentials (username + api key) and set AT_SENDER to Rentana before running.
Install requirements: pip install -r requirements.txt
Run: flask run (or gunicorn) after exporting DATABASE_URL and other env vars.

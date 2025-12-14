# rentme/forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, DecimalField, SelectField
from wtforms.validators import DataRequired, Email, EqualTo, Optional, Length

# -----------------------
# Register form
# -----------------------
class RegisterForm(FlaskForm):
    full_name = StringField('Full Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    login_phone = StringField('Phone')
    password = PasswordField('Password', validators=[DataRequired()])
    confirm = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

# -----------------------
# Login form
# -----------------------
class LoginForm(FlaskForm):
    identifier = StringField("Email or Phone", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")

# -----------------------
# Forgot Password Form
# -----------------------
class ForgotPasswordForm(FlaskForm):
    email_or_phone = StringField("Email or Phone", validators=[DataRequired()])
    submit = SubmitField("Send Reset Code")

# -----------------------
# Tenant Form
# -----------------------
class TenantForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    phone = StringField("Phone", validators=[DataRequired()])
    national_id = StringField("National ID")
    house_no = StringField("House No", validators=[DataRequired()])
    monthly_rent = StringField("Monthly Rent", validators=[DataRequired()])
    move_in_date = StringField("Move-in Date (YYYY-MM-DD)")
    submit = SubmitField("Save")

# -----------------------
# Landlord MPesa / Payment Settings Form
# -----------------------
class MPesaSettingsForm(FlaskForm):
    payment_method = SelectField(
        "Payment Method",
        choices=[
            ("", "Select"),
            ("Paybill", "Paybill (C2B)"),
            ("Till", "Till / BuyGoods"),
            ("Send Money", "Send Money (P2P)")
        ],
        validators=[Optional()]
    )
    paybill_number = StringField("Paybill Number", validators=[Optional()])
    till_number = StringField("Till / BuyGoods Number", validators=[Optional()])
    send_money_number = StringField("Send Money Receiver (phone)", validators=[Optional()])
    phone_number = StringField("Display Phone (optional)", validators=[Optional()])
    
    mpesa_consumer_key = StringField("Daraja: Consumer Key", validators=[Optional()])
    mpesa_consumer_secret = PasswordField("Daraja: Consumer Secret", validators=[Optional()])
    mpesa_shortcode = StringField("BusinessShortCode / Shortcode", validators=[Optional()])
    mpesa_passkey = PasswordField("Daraja: Passkey", validators=[Optional()])
    mpesa_mode = SelectField(
        "Daraja Mode",
        choices=[("production", "Production"), ("sandbox", "Sandbox")],
        validators=[Optional()]
    )
    callback_url = StringField("Callback URL (optional)", validators=[Optional()])
    
    submit = SubmitField("Save Settings")
    test_credentials = SubmitField("Test Credentials")


#RESET
class ResetPasswordForm(FlaskForm):
    identifier = StringField("Email or Phone", validators=[DataRequired()])
    code = StringField("Reset Code", validators=[DataRequired()])
    password = PasswordField(
        "New Password",
        validators=[DataRequired(), Length(min=6)]
    )
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[DataRequired(), EqualTo("password")]
    )
    submit = SubmitField("Reset Password")
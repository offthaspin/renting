# rentme/forms.py
from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    PasswordField,
    SubmitField,
    SelectField
)
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    Optional,
    Length
)

# ======================================================
# 🔐 REGISTER FORM
# ======================================================
class RegisterForm(FlaskForm):
    full_name = StringField(
        "Full Name",
        validators=[DataRequired()],
        render_kw={
            "autocomplete": "off",
            "autocapitalize": "off",
            "spellcheck": "false"
        }
    )

    email = StringField(
        "Email",
        validators=[DataRequired(), Email()],
        render_kw={
            "autocomplete": "off",
            "inputmode": "email"
        }
    )

    login_phone = StringField(
        "Phone",
        render_kw={
            "autocomplete": "off",
            "inputmode": "tel"
        }
    )

    password = PasswordField(
        "Password",
        validators=[DataRequired()],
        render_kw={
            "autocomplete": "new-password"
        }
    )

    confirm = PasswordField(
        "Confirm Password",
        validators=[DataRequired(), EqualTo("password")],
        render_kw={
            "autocomplete": "new-password"
        }
    )

    submit = SubmitField("Register")


# ======================================================
# 🔑 LOGIN FORM
# ======================================================
class LoginForm(FlaskForm):
    identifier = StringField(
        "Email or Phone",
        validators=[DataRequired()],
        render_kw={
            "autocomplete": "off",
            "inputmode": "text"
        }
    )

    password = PasswordField(
        "Password",
        validators=[DataRequired()],
        render_kw={
            "autocomplete": "new-password"
        }
    )

    submit = SubmitField("Login")


# ======================================================
# 🔁 FORGOT PASSWORD
# ======================================================
class ForgotPasswordForm(FlaskForm):
    email_or_phone = StringField(
        "Email or Phone",
        validators=[DataRequired()],
        render_kw={
            "autocomplete": "off",
            "autocapitalize": "off",
            "spellcheck": "false"
        }
    )

    submit = SubmitField("Send Reset Code")


# ======================================================
# 🏠 TENANT FORM
# ======================================================
class TenantForm(FlaskForm):
    name = StringField(
        "Name",
        validators=[DataRequired()],
        render_kw={
            "autocomplete": "off"
        }
    )

    phone = StringField(
        "Phone",
        validators=[DataRequired()],
        render_kw={
            "autocomplete": "off",
            "inputmode": "tel"
        }
    )

    national_id = StringField(
        "National ID",
        render_kw={
            "autocomplete": "off"
        }
    )

    house_no = StringField(
        "House No",
        validators=[DataRequired()],
        render_kw={
            "autocomplete": "off"
        }
    )

    monthly_rent = StringField(
        "Monthly Rent",
        validators=[DataRequired()],
        render_kw={
            "autocomplete": "off",
            "inputmode": "numeric"
        }
    )

    move_in_date = StringField(
        "Move-in Date (YYYY-MM-DD)",
        render_kw={
            "autocomplete": "off"
        }
    )

    submit = SubmitField("Save")


# ======================================================
# 💳 LANDLORD MPESA / PAYMENT SETTINGS
# ======================================================
class MPesaSettingsForm(FlaskForm):
    payment_method = SelectField(
        "Payment Method",
        choices=[
            ("", "Select"),
            ("Paybill", "Paybill (C2B)"),
            ("Till", "Till / BuyGoods"),
            ("Send Money", "Send Money (P2P)")
        ],
        validators=[Optional()],
        render_kw={
            "autocomplete": "off"
        }
    )

    paybill_number = StringField(
        "Paybill Number",
        validators=[Optional()],
        render_kw={
            "autocomplete": "off"
        }
    )

    till_number = StringField(
        "Till / BuyGoods Number",
        validators=[Optional()],
        render_kw={
            "autocomplete": "off"
        }
    )

    send_money_number = StringField(
        "Send Money Receiver (phone)",
        validators=[Optional()],
        render_kw={
            "autocomplete": "off",
            "inputmode": "tel"
        }
    )

    phone_number = StringField(
        "Display Phone (optional)",
        validators=[Optional()],
        render_kw={
            "autocomplete": "off"
        }
    )

    mpesa_consumer_key = StringField(
        "Daraja: Consumer Key",
        validators=[Optional()],
        render_kw={
            "autocomplete": "off"
        }
    )

    mpesa_consumer_secret = PasswordField(
        "Daraja: Consumer Secret",
        validators=[Optional()],
        render_kw={
            "autocomplete": "new-password"
        }
    )

    mpesa_shortcode = StringField(
        "BusinessShortCode / Shortcode",
        validators=[Optional()],
        render_kw={
            "autocomplete": "off"
        }
    )

    mpesa_passkey = PasswordField(
        "Daraja: Passkey",
        validators=[Optional()],
        render_kw={
            "autocomplete": "new-password"
        }
    )

    mpesa_mode = SelectField(
        "Daraja Mode",
        choices=[("production", "Production"), ("sandbox", "Sandbox")],
        validators=[Optional()],
        render_kw={
            "autocomplete": "off"
        }
    )

    callback_url = StringField(
        "Callback URL (optional)",
        validators=[Optional()],
        render_kw={
            "autocomplete": "off"
        }
    )

    submit = SubmitField("Save Settings")


# ======================================================
# 🔐 RESET PASSWORD
# ======================================================
class ResetPasswordForm(FlaskForm):
    identifier = StringField(
        "Email or Phone",
        validators=[DataRequired()],
        render_kw={
            "autocomplete": "off"
        }
    )

    code = StringField(
        "Reset Code",
        validators=[DataRequired()],
        render_kw={
            "autocomplete": "off"
        }
    )

    password = PasswordField(
        "New Password",
        validators=[DataRequired(), Length(min=6)],
        render_kw={
            "autocomplete": "new-password"
        }
    )

    confirm_password = PasswordField(
        "Confirm Password",
        validators=[DataRequired(), EqualTo("password")],
        render_kw={
            "autocomplete": "new-password"
        }
    )

    submit = SubmitField("Reset Password")

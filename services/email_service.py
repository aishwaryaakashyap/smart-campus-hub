import smtplib
from email.message import EmailMessage

from flask import current_app


def send_password_reset_email(recipient, reset_url):
    config = current_app.config

    mail_server = config.get("MAIL_SERVER")
    mail_port = config.get("MAIL_PORT")
    sender = config.get("MAIL_DEFAULT_SENDER")
    username = config.get("MAIL_USERNAME")
    password = "".join((config.get("MAIL_PASSWORD") or "").split())
    use_tls = config.get("MAIL_USE_TLS", True)

    if not mail_server or not sender:
        raise RuntimeError("SMTP email settings are incomplete.")

    message = EmailMessage()
    message["Subject"] = "Smart Campus Hub - Password Reset"
    message["From"] = sender
    message["To"] = recipient

    message.set_content(
        "Hello,\n\n"
        "We received a request to reset your Smart Campus Hub password.\n\n"
        f"Use this link to create a new password:\n{reset_url}\n\n"
        "This link expires in 15 minutes and can only be used once.\n"
        "If you did not request this reset, you can ignore this email.\n\n"
        "Smart Campus Hub Support"
    )

    with smtplib.SMTP(mail_server, mail_port, timeout=15) as smtp:
        smtp.ehlo()

        if use_tls:
            smtp.starttls()
            smtp.ehlo()

        if username:
            smtp.login(username, password)

        smtp.send_message(message)


def send_account_setup_email(
    recipient, setup_url, expiry_minutes, account_label="Advisor"
):
    """Send an approved Advisor a secure password setup link."""
    config = current_app.config

    mail_server = config.get("MAIL_SERVER")
    mail_port = config.get("MAIL_PORT")
    sender = config.get("MAIL_DEFAULT_SENDER")
    username = config.get("MAIL_USERNAME")
    password = "".join((config.get("MAIL_PASSWORD") or "").split())
    use_tls = config.get("MAIL_USE_TLS", True)

    if not mail_server or not sender or not mail_port:
        raise RuntimeError("SMTP email settings are incomplete.")

    message = EmailMessage()
    message["Subject"] = f"Smart Campus Hub - {account_label} Account Setup"
    message["From"] = sender
    message["To"] = recipient

    message.set_content(
        "Hello,\n\n"
        f"Your Smart Campus Hub {account_label} account has been approved.\n\n"
        "Use the secure link below to create your password:\n"
        f"{setup_url}\n\n"
        f"This link expires in {expiry_minutes} minutes "
        "and can only be used once.\n\n"
        "If you were not expecting this invitation, contact your "
        "institution's Coordinator.\n\n"
        "Smart Campus Hub Support"
    )

    with smtplib.SMTP(mail_server, mail_port, timeout=15) as smtp:
        smtp.ehlo()

        if use_tls:
            smtp.starttls()
            smtp.ehlo()

        if username:
            smtp.login(username, password)

        smtp.send_message(message)


def send_student_otp_email(recipient, otp, expiry_minutes=10):
    """Send a student registration email verification OTP."""
    config = current_app.config

    mail_server = config.get("MAIL_SERVER")
    mail_port = config.get("MAIL_PORT")
    sender = config.get("MAIL_DEFAULT_SENDER")
    username = config.get("MAIL_USERNAME")
    password = "".join((config.get("MAIL_PASSWORD") or "").split())
    use_tls = config.get("MAIL_USE_TLS", True)

    if not mail_server or not sender or not mail_port:
        raise RuntimeError("SMTP email settings are incomplete.")

    message = EmailMessage()
    message["Subject"] = "Smart Campus Hub - Email Verification"
    message["From"] = sender
    message["To"] = recipient

    message.set_content(
        "Hello,\n\n"
        "Thank you for registering with Smart Campus Hub.\n\n"
        f"Your email verification OTP is: {otp}\n\n"
        f"This OTP expires in {expiry_minutes} minutes "
        "and can only be used once.\n\n"
        "Do not share this code with anyone.\n\n"
        "If you did not request this registration, "
        "you can ignore this email.\n\n"
        "Smart Campus Hub Support"
    )

    with smtplib.SMTP(mail_server, mail_port, timeout=15) as smtp:
        smtp.ehlo()

        if use_tls:
            smtp.starttls()
            smtp.ehlo()

        if username:
            smtp.login(username, password)

        smtp.send_message(message)

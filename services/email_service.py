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

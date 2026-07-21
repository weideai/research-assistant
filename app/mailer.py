import smtplib
from email.message import EmailMessage

from flask import current_app


def send_email(recipient, subject, body):
    host = current_app.config.get("SMTP_HOST", "")
    sender = current_app.config.get("MAIL_FROM", "") or current_app.config.get("SMTP_USERNAME", "")
    if not host or not sender:
        current_app.logger.warning("Email not sent because SMTP is not configured: %s", subject)
        return False

    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    try:
        with smtplib.SMTP(host, current_app.config["SMTP_PORT"], timeout=20) as server:
            if current_app.config["SMTP_USE_TLS"]:
                server.starttls()
            username = current_app.config.get("SMTP_USERNAME", "")
            if username:
                server.login(username, current_app.config.get("SMTP_PASSWORD", ""))
            server.send_message(message)
        return True
    except (OSError, smtplib.SMTPException):
        current_app.logger.exception("Unable to send email: %s", subject)
        return False


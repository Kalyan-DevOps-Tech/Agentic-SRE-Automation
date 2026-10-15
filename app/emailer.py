import os
import smtplib
from email.message import EmailMessage

def send_email(subject: str, body: str, recipients: str) -> bool:
    recipients = [x.strip() for x in recipients.split(",") if x.strip()]
    host = os.getenv("SMTP_HOST")
    sender = os.getenv("EMAIL_FROM", "sre-agent@example.com")
    if not host or not recipients:
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.set_content(body)

    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME", "")
    password = os.getenv("SMTP_PASSWORD", "")
    with smtplib.SMTP(host, port, timeout=15) as server:
        server.ehlo()
        if os.getenv("SMTP_STARTTLS", "true").lower() == "true":
            server.starttls()
            server.ehlo()
        if username:
            server.login(username, password)
        server.send_message(msg)
    return True

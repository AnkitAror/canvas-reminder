"""Send an email via Gmail SMTP using an app password.

Env: GMAIL_ADDRESS, GMAIL_APP_PASSWORD, DIGEST_TO (defaults to GMAIL_ADDRESS)
"""
import os
import smtplib
import ssl
from email.message import EmailMessage

from dotenv import load_dotenv

load_dotenv()


def send_email(subject, html_body, text_body):
    sender = os.environ.get("GMAIL_ADDRESS")
    password = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "")
    to = os.environ.get("DIGEST_TO") or sender
    if not sender or not password:
        raise RuntimeError("GMAIL_ADDRESS and GMAIL_APP_PASSWORD must be set (see .env).")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"Canvas Reminder <{sender}>"
    msg["To"] = to
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as s:
        s.login(sender, password)
        s.send_message(msg)
    print(f"Sent '{subject}' to {to}")

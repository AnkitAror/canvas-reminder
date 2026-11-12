"""Read manual completion marks from Gmail.

Each digest item has a "✓ Done" mailto link that sends an email to GMAIL_ADDRESS with subject
  [Canvas Done] <title> | assignment_123,assignment_456
This tool searches the mailbox (IMAP, same app password) for those emails and returns the IDs.
Deleting a "[Canvas Done]" email un-marks the item.

Usage: python tools/read_done_marks.py   (prints the IDs found)
Env: GMAIL_ADDRESS, GMAIL_APP_PASSWORD, DIGEST_TO, DONE_MARK_LOOKBACK_DAYS (default 180)
"""
import email
import imaplib
import os
import re
import ssl
from email.header import decode_header, make_header
from email.utils import parseaddr

import certifi
from dotenv import load_dotenv

load_dotenv()

SUBJECT_TAG = "[Canvas Done]"
ID_RE = re.compile(r"\b([a-z]+(?:_[a-z]+)*_\d+)\b")


def _allowed_senders():
    addrs = {os.environ.get("GMAIL_ADDRESS", ""), os.environ.get("DIGEST_TO", "")}
    return {a.strip().lower() for a in addrs if a and a.strip()}


def read_done_ids():
    user = os.environ.get("GMAIL_ADDRESS")
    pw = (os.environ.get("GMAIL_APP_PASSWORD") or "").replace(" ", "")
    days = int(os.environ.get("DONE_MARK_LOOKBACK_DAYS") or 180)
    if not user or not pw:
        raise RuntimeError("GMAIL_ADDRESS and GMAIL_APP_PASSWORD must be set (see .env).")

    ctx = ssl.create_default_context(cafile=certifi.where())
    ids = set()
    with imaplib.IMAP4_SSL("imap.gmail.com", 993, ssl_context=ctx) as m:
        m.login(user, pw)
        m.select('"[Gmail]/All Mail"', readonly=True)  # excludes Trash, so deleting = undo
        typ, data = m.search(None, "X-GM-RAW", f'"subject:(Canvas Done) newer_than:{days}d"')
        if typ != "OK" or not data or not data[0]:
            return ids
        for num in data[0].split():
            typ, msg_data = m.fetch(num, "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)])")
            if typ != "OK" or not msg_data or not isinstance(msg_data[0], tuple):
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            sender = parseaddr(msg.get("From", ""))[1].lower()
            if sender not in _allowed_senders():
                continue  # only trust marks sent by you
            subject = str(make_header(decode_header(msg.get("Subject", ""))))
            if SUBJECT_TAG not in subject or "|" not in subject:
                continue
            ids.update(ID_RE.findall(subject.rsplit("|", 1)[1]))
    return ids


if __name__ == "__main__":
    found = read_done_ids()
    print(f"{len(found)} item(s) marked done: {sorted(found)}")

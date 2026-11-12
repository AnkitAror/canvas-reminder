"""Entry point: fetch Canvas data -> read done marks -> merge duplicates & drop completed
-> build digest -> send Gmail.

Usage:
  python tools/run_daily_digest.py            # fetch + send
  python tools/run_daily_digest.py --dry-run  # fetch + write .tmp/digest.html, no email
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_digest_email import build  # noqa: E402
from canvas_client import CanvasAuthError  # noqa: E402
from dedupe_and_filter import process  # noqa: E402
from read_done_marks import read_done_ids  # noqa: E402
from fetch_canvas_data import main as fetch_api  # noqa: E402
from fetch_canvas_ics import main as fetch_ics  # noqa: E402
from send_gmail import send_email  # noqa: E402


def fetch():
    """Prefer the API (richer: announcements, submission status); fall back to the .ics feed."""
    if os.environ.get("CANVAS_API_TOKEN"):
        return fetch_api()
    if os.environ.get("CANVAS_ICS_URL"):
        return fetch_ics()
    raise RuntimeError("Set CANVAS_API_TOKEN (+ CANVAS_API_URL) or CANVAS_ICS_URL in .env.")

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Don't send; write .tmp/digest.html")
    args = ap.parse_args()

    try:
        data = fetch()
    except CanvasAuthError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        if not args.dry_run:
            send_email(
                "⚠️ Canvas Reminder: access token invalid",
                "<p>Your Canvas access token was rejected (401). Generate a new one in Canvas → "
                "Account → Settings → New Access Token, then update <code>CANVAS_API_TOKEN</code> "
                "in .env and in your GitHub repo secrets.</p>",
                "Your Canvas access token was rejected (401). Generate a new one in Canvas -> "
                "Account -> Settings -> New Access Token, then update CANVAS_API_TOKEN in .env "
                "and in your GitHub repo secrets.",
            )
        sys.exit(1)

    # Manual "✓ Done" marks from Gmail. A failure here must not block the digest.
    try:
        done_ids = read_done_ids()
        print(f"{len(done_ids)} item(s) marked done via email")
    except Exception as exc:  # noqa: BLE001
        print(f"WARNING: could not read done marks from Gmail: {exc}", file=sys.stderr)
        done_ids = set()
        data["done_marks_error"] = True

    data = process(data, done_ids)
    print(f"Excluded {data['excluded']} by rules; merged {data['duplicates_merged']} duplicate(s); "
          f"hid {data['hidden_done']} completed item(s)")

    subject, html_body, text_body = build(data)
    if args.dry_run:
        (ROOT / ".tmp" / "digest.html").write_text(html_body)
        (ROOT / ".tmp" / "digest.txt").write_text(text_body)
        print(f"[dry-run] Subject: {subject}\nWrote .tmp/digest.html and .tmp/digest.txt")
        return
    send_email(subject, html_body, text_body)


if __name__ == "__main__":
    main()

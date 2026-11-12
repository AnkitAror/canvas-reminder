"""Entry point: fetch Canvas data -> build digest -> send Gmail.

Usage:
  python tools/run_daily_digest.py            # fetch + send
  python tools/run_daily_digest.py --dry-run  # fetch + write .tmp/digest.html, no email
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_digest_email import build  # noqa: E402
from canvas_client import CanvasAuthError  # noqa: E402
from fetch_canvas_data import main as fetch  # noqa: E402
from send_gmail import send_email  # noqa: E402

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

    subject, html_body, text_body = build(data)
    if args.dry_run:
        (ROOT / ".tmp" / "digest.html").write_text(html_body)
        (ROOT / ".tmp" / "digest.txt").write_text(text_body)
        print(f"[dry-run] Subject: {subject}\nWrote .tmp/digest.html and .tmp/digest.txt")
        return
    send_email(subject, html_body, text_body)


if __name__ == "__main__":
    main()

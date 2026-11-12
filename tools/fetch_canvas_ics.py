"""Token-free fallback: build .tmp/canvas_digest.json from the Canvas Calendar Feed (.ics).

Use when the school blocks student API tokens. Covers assignment due dates and calendar
events (exams) across all courses. No announcements, no submission status.

Usage: python tools/fetch_canvas_ics.py
Env: CANVAS_ICS_URL (Canvas -> Calendar -> "Calendar Feed"), LOOKAHEAD_DAYS (default 7),
     TIMEZONE (used for all-day events, default America/New_York)
"""
import json
import os
import re
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv
from icalendar import Calendar

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_canvas_data import EXAM_RE, OUT_PATH, _iso  # noqa: E402

load_dotenv()

COURSE_RE = re.compile(r"\s*\[([^\]]+)\]\s*$")  # Canvas appends " [Course Name]" to SUMMARY


def _to_utc(value, tz):
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=tz)
        return value.astimezone(timezone.utc)
    if isinstance(value, date):  # all-day: treat as end of that day locally
        return datetime.combine(value, time(23, 59), tzinfo=tz).astimezone(timezone.utc)
    return None


def _kind(uid):
    uid = uid or ""
    if "assignment" in uid:
        return "assignment"
    if "quiz" in uid:
        return "quiz"
    if "discussion" in uid:
        return "discussion_topic"
    return "calendar_event"


def fetch_ics(url, now, end, tz):
    resp = requests.get(url, timeout=30)
    if resp.status_code in (401, 403, 404):
        raise RuntimeError(f"Calendar feed returned {resp.status_code}; re-copy the Calendar Feed URL.")
    resp.raise_for_status()
    cal = Calendar.from_ical(resp.content)

    items, courses = [], set()
    for ev in cal.walk("VEVENT"):
        start = ev.get("DTSTART")
        if not start:
            continue
        due = _to_utc(start.dt, tz)
        if not due or due < now or due > end:
            continue
        summary = str(ev.get("SUMMARY", "(untitled)"))
        m = COURSE_RE.search(summary)
        course = m.group(1) if m else ""
        title = COURSE_RE.sub("", summary).strip() or "(untitled)"
        if course:
            courses.add(course)
        kind = _kind(str(ev.get("UID", "")))
        items.append({
            "kind": kind,
            "title": title,
            "course": course or "Calendar",
            "due_at": _iso(due),
            "points": None,
            "url": str(ev.get("URL", "")) or url.split("/feeds/")[0],
            "is_exam": kind == "quiz" or bool(EXAM_RE.search(title)),
        })
    items.sort(key=lambda i: i["due_at"])
    return items, sorted(courses)


def main():
    url = os.environ.get("CANVAS_ICS_URL")
    if not url:
        raise RuntimeError("CANVAS_ICS_URL must be set (see .env).")
    lookahead = int(os.environ.get("LOOKAHEAD_DAYS") or 7)
    tz = ZoneInfo(os.environ.get("TIMEZONE") or "America/New_York")
    now = datetime.now(timezone.utc).replace(microsecond=0)

    items, courses = fetch_ics(url, now, now + timedelta(days=lookahead), tz)
    data = {
        "source": "ics",
        "generated_at": _iso(now),
        "lookahead_days": lookahead,
        "announcement_lookback_hours": 0,
        "courses": [{"name": c} for c in courses],
        "items": items,
        "announcements": [],
    }
    OUT_PATH.parent.mkdir(exist_ok=True)
    OUT_PATH.write_text(json.dumps(data, indent=2))
    print(f"Wrote {OUT_PATH} from calendar feed: {len(courses)} courses, {len(items)} upcoming items")
    return data


if __name__ == "__main__":
    main()

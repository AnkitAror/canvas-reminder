"""Pull active courses, upcoming due items, calendar events (exams) and recent announcements
from Canvas, normalize them, and write .tmp/canvas_digest.json.

Usage: python tools/fetch_canvas_data.py
Env: CANVAS_API_URL, CANVAS_API_TOKEN, LOOKAHEAD_DAYS (default 7),
     ANNOUNCEMENT_LOOKBACK_HOURS (default 24)
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from canvas_client import CanvasClient  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / ".tmp" / "canvas_digest.json"

EXAM_RE = re.compile(r"\b(exam|midterm|mid-term|final|quiz|test)\b", re.IGNORECASE)
SKIP_PLANNER_TYPES = {"announcement", "calendar_event"}  # fetched from dedicated endpoints


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse(ts):
    if not ts:
        return None
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def _abs_url(client, url):
    if not url:
        return client.base_url
    return url if url.startswith("http") else client.base_url + url


def fetch_courses(client):
    courses = client.get_all("courses", {"enrollment_state": "active", "include[]": "term"})
    out = {}
    for c in courses:
        if c.get("access_restricted_by_date") or not c.get("name"):
            continue
        out[c["id"]] = {"id": c["id"], "name": c["name"], "code": c.get("course_code", "")}
    return out


def fetch_planner_items(client, courses, start, end):
    items = client.get_all("planner/items", {"start_date": _iso(start), "end_date": _iso(end)})
    out = []
    for it in items:
        ptype = it.get("plannable_type", "")
        if ptype in SKIP_PLANNER_TYPES:
            continue
        p = it.get("plannable") or {}
        due = it.get("plannable_date") or p.get("due_at") or p.get("todo_date")
        if not due:
            continue
        subs = it.get("submissions") or {}
        submitted = bool(subs.get("submitted")) if isinstance(subs, dict) else False
        # Keep completed items: dedupe_and_filter needs them so a completed duplicate
        # also hides its unsubmitted copy.
        completed = submitted or bool((it.get("planner_override") or {}).get("marked_complete"))
        title = p.get("title") or p.get("name") or "(untitled)"
        course_id = it.get("course_id")
        course = courses.get(course_id, {}).get("name") or it.get("context_name") or "Personal"
        out.append({
            "id": f"{ptype}_{it.get('plannable_id')}",
            "completed": completed,
            "kind": ptype,
            "title": title,
            "course": course,
            "due_at": due,
            "points": p.get("points_possible"),
            "url": _abs_url(client, it.get("html_url")),
            "is_exam": ptype == "quiz" or bool(EXAM_RE.search(title)),
        })
    return out


def fetch_calendar_events(client, courses, start, end):
    out = []
    codes = [f"course_{cid}" for cid in courses]
    for batch in _chunks(codes, 10):  # Canvas caps context_codes at 10 per request
        events = client.get_all("calendar_events", {
            "type": "event",
            "context_codes[]": batch,
            "start_date": _iso(start),
            "end_date": _iso(end),
        })
        for ev in events:
            if not ev.get("start_at"):
                continue
            cid = int(str(ev.get("context_code", "_0")).split("_")[-1] or 0)
            title = ev.get("title") or "(untitled event)"
            out.append({
                "id": f"calendar_event_{ev.get('id')}",
                "completed": False,
                "kind": "calendar_event",
                "title": title,
                "course": courses.get(cid, {}).get("name", ev.get("context_name", "")),
                "due_at": ev["start_at"],
                "points": None,
                "url": _abs_url(client, ev.get("html_url")),
                "is_exam": bool(EXAM_RE.search(title)),
            })
    return out


def fetch_announcements(client, courses, since, now):
    out = []
    codes = [f"course_{cid}" for cid in courses]
    for batch in _chunks(codes, 10):
        anns = client.get_all("announcements", {
            "context_codes[]": batch,
            "start_date": (since - timedelta(days=1)).strftime("%Y-%m-%d"),
            "end_date": (now + timedelta(days=1)).strftime("%Y-%m-%d"),
        })
        for a in anns:
            posted = _parse(a.get("posted_at") or a.get("delayed_post_at"))
            if not posted or posted < since or posted > now:
                continue
            cid = int(str(a.get("context_code", "_0")).split("_")[-1] or 0)
            out.append({
                "title": a.get("title") or "(no title)",
                "course": courses.get(cid, {}).get("name", ""),
                "posted_at": _iso(posted),
                "author": (a.get("author") or {}).get("display_name", ""),
                "message_html": a.get("message") or "",
                "url": _abs_url(client, a.get("html_url")),
            })
    out.sort(key=lambda a: a["posted_at"], reverse=True)
    return out


def main():
    lookahead = int(os.environ.get("LOOKAHEAD_DAYS") or 7)
    lookback_h = int(os.environ.get("ANNOUNCEMENT_LOOKBACK_HOURS") or 24)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    end = now + timedelta(days=lookahead)

    client = CanvasClient()
    courses = fetch_courses(client)
    items = fetch_planner_items(client, courses, now, end)
    items += fetch_calendar_events(client, courses, now, end)
    # Duplicates and completed items are handled later by dedupe_and_filter.process()
    deduped = sorted(items, key=lambda i: i["due_at"])
    announcements = fetch_announcements(client, courses, now - timedelta(hours=lookback_h), now)

    data = {
        "generated_at": _iso(now),
        "lookahead_days": lookahead,
        "announcement_lookback_hours": lookback_h,
        "courses": list(courses.values()),
        "items": deduped,
        "announcements": announcements,
    }
    OUT_PATH.parent.mkdir(exist_ok=True)
    OUT_PATH.write_text(json.dumps(data, indent=2))
    print(f"Wrote {OUT_PATH}: {len(courses)} courses, {len(deduped)} upcoming items, "
          f"{len(announcements)} announcements")
    return data


if __name__ == "__main__":
    main()

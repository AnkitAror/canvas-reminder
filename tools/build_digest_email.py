"""Render .tmp/canvas_digest.json into an email (subject, HTML, plain text).

Usage: python tools/build_digest_email.py   -> writes .tmp/digest.html and .tmp/digest.txt
Env: TIMEZONE (IANA name, default America/New_York)
"""
import html
import json
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
IN_PATH = ROOT / ".tmp" / "canvas_digest.json"
EXCERPT_CHARS = 400

KIND_LABEL = {
    "assignment": "Assignment",
    "quiz": "Quiz",
    "discussion_topic": "Discussion",
    "wiki_page": "Page",
    "planner_note": "To-do",
    "calendar_event": "Event",
    "assessment_request": "Peer review",
}


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ("br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4"):
            self.parts.append(" ")

    def handle_data(self, data):
        self.parts.append(data)


def html_to_text(s):
    p = _TextExtractor()
    p.feed(s or "")
    return re.sub(r"\s+", " ", "".join(p.parts)).strip()


def excerpt(s, n=EXCERPT_CHARS):
    text = html_to_text(s)
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0] + "…"


def done_link(item):
    """mailto: link that sends a "[Canvas Done]" email to yourself (read by read_done_marks.py)."""
    to = os.environ.get("GMAIL_ADDRESS", "")
    ids = item.get("ids") or ([item["id"]] if item.get("id") else [])
    if not to or not ids:
        return ""
    title = re.sub(r"[|\r\n]+", " ", item["title"])[:80]
    subject = f"[Canvas Done] {title} | {','.join(ids)}"
    body = ("Send this email to mark the assignment done; it will be hidden from tomorrow's "
            "digest. To undo, delete this email (from Sent, and Inbox if it shows up there).")
    return f"mailto:{to}?subject={quote(subject)}&body={quote(body)}"


def _course_label(item):
    extra = item.get("also_in") or []
    return item["course"] + (f" (+ duplicate in {', '.join(extra)})" if extra else "")


def _local(ts, tz):
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(tz)


def _fmt_when(dt, today):
    delta = (dt.date() - today).days
    day = "Today" if delta == 0 else "Tomorrow" if delta == 1 else dt.strftime("%a %b %-d")
    return f"{day}, {dt.strftime('%-I:%M %p')}"


def build(data):
    tz = ZoneInfo(os.environ.get("TIMEZONE") or "America/New_York")
    now = _local(data["generated_at"], tz)
    today = now.date()
    soon_cutoff = now + timedelta(hours=48)

    items = []
    for it in data["items"]:
        it = dict(it, local=_local(it["due_at"], tz))
        items.append(it)

    urgent = [i for i in items if i["local"] <= soon_cutoff]
    exams = [i for i in items if i["is_exam"] and i not in urgent]
    later = [i for i in items if i not in urgent and i not in exams]
    anns = data["announcements"]

    n_due = len(items)
    subject = f"📚 Canvas digest {now.strftime('%a %b %-d')}: "
    if urgent:
        subject += f"{len(urgent)} due in 48h"
    elif n_due:
        subject += f"{n_due} due this week"
    else:
        subject += "all clear"
    if anns:
        subject += f", {len(anns)} new announcement{'s' if len(anns) != 1 else ''}"

    # ---------- plain text ----------
    t = [f"Canvas digest for {now.strftime('%A, %B %-d')}", ""]

    def text_items(title, rows):
        if not rows:
            return
        t.append(title)
        for i in rows:
            tag = "[EXAM] " if i["is_exam"] else ""
            t.append(f"  - {tag}{i['title']} ({_course_label(i)}): {_fmt_when(i['local'], today)}")
            t.append(f"    {i['url']}")
        t.append("")

    text_items("DUE IN THE NEXT 48 HOURS", urgent)
    text_items("EXAMS & QUIZZES COMING UP", exams)
    text_items(f"LATER (next {data['lookahead_days']} days)", later)
    if anns:
        t.append(f"NEW ANNOUNCEMENTS (last {data['announcement_lookback_hours']}h)")
        for a in anns:
            t.append(f"  - {a['title']} ({a['course']}), {a['author']}")
            t.append(f"    {excerpt(a['message_html'])}")
            t.append(f"    {a['url']}")
        t.append("")
    if not items and not anns:
        t.append("Nothing due in the look-ahead window and no new announcements. 🎉")
    text = "\n".join(t)

    # ---------- HTML ----------
    e = html.escape
    h = ['<div style="font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;'
         'max-width:640px;margin:auto;color:#1f2328;line-height:1.45">',
         f'<h2 style="margin:0 0 4px">📚 Canvas digest</h2>'
         f'<div style="color:#656d76;margin-bottom:16px">{e(now.strftime("%A, %B %-d"))}</div>']

    def row(i, accent):
        kind = KIND_LABEL.get(i["kind"], i["kind"].replace("_", " ").title())
        pts = f" · {i['points']:g} pts" if isinstance(i.get("points"), (int, float)) else ""
        exam = ('<span style="background:#ffebe9;color:#cf222e;border-radius:4px;'
                'padding:1px 6px;font-size:12px;margin-left:6px">EXAM</span>') if i["is_exam"] else ""
        link = done_link(i)
        done = (f'<a href="{e(link)}" style="float:right;font-size:12px;color:#1a7f37;'
                'border:1px solid #1a7f37;border-radius:12px;padding:1px 8px;text-decoration:none;'
                'margin-left:8px">✓ Done</a>') if link else ""
        return (f'<div style="border-left:4px solid {accent};padding:6px 10px;margin:6px 0;'
                f'background:#f6f8fa;border-radius:4px">{done}'
                f'<a href="{e(i["url"])}" style="color:#0969da;font-weight:600;text-decoration:none">'
                f'{e(i["title"])}</a>{exam}<br>'
                f'<span style="color:#656d76;font-size:13px">{e(_course_label(i))} · {e(kind)}{pts} · '
                f'<b>{e(_fmt_when(i["local"], today))}</b></span></div>')

    def section(title, rows, accent, group_by_course=False):
        if not rows:
            return
        h.append(f'<h3 style="margin:20px 0 6px">{title}</h3>')
        if group_by_course:
            groups = defaultdict(list)
            for i in rows:
                groups[i["course"]].append(i)
            for course, rs in groups.items():
                h.append(f'<div style="font-weight:600;margin-top:10px">{e(course)}</div>')
                h.extend(row(i, accent) for i in rs)
        else:
            h.extend(row(i, accent) for i in rows)

    section("⚠️ Due in the next 48 hours", urgent, "#cf222e")
    section("📝 Exams & quizzes coming up", exams, "#bf8700")
    section(f"📅 Later (next {data['lookahead_days']} days)", later, "#0969da", group_by_course=True)

    if anns:
        h.append(f'<h3 style="margin:20px 0 6px">📢 New announcements</h3>')
        for a in anns:
            posted = _fmt_when(_local(a["posted_at"], tz), today)
            h.append(
                '<div style="border:1px solid #d0d7de;border-radius:6px;padding:10px;margin:8px 0">'
                f'<a href="{e(a["url"])}" style="color:#0969da;font-weight:600;text-decoration:none">'
                f'{e(a["title"])}</a><br>'
                f'<span style="color:#656d76;font-size:13px">{e(a["course"])} · {e(a["author"])} · '
                f'{e(posted)}</span>'
                f'<p style="margin:6px 0 0">{e(excerpt(a["message_html"]))}</p></div>')

    if not items and not anns:
        h.append('<p style="font-size:16px">Nothing due in the look-ahead window and no new '
                 'announcements. 🎉</p>')
    stats = []
    if data.get("hidden_done"):
        stats.append(f"{data['hidden_done']} completed item(s) hidden")
    if data.get("excluded"):
        stats.append(f"{data['excluded']} item(s) excluded by your rules")
    if data.get("duplicates_merged"):
        stats.append(f"{data['duplicates_merged']} duplicate(s) merged")
    if data.get("done_marks_error"):
        stats.append("⚠️ couldn't read your Done marks today, so done items may reappear")
    note = "Tap ✓ Done and send the email it opens to hide an item (delete that email to undo)."
    if data.get("source") != "ics":
        note = "Submitted items are hidden automatically. " + note
    h.append('<p style="color:#8c959f;font-size:12px;margin-top:24px">'
             + (e(" · ".join(stats)) + "<br>" if stats else "")
             + f'Sent automatically by your Canvas Reminder. {e(note)}</p></div>')
    if stats:
        text += "\n\n" + " · ".join(stats)

    return subject, "".join(h), text


def main():
    data = json.loads(IN_PATH.read_text())
    subject, html_body, text_body = build(data)
    (ROOT / ".tmp" / "digest.html").write_text(html_body)
    (ROOT / ".tmp" / "digest.txt").write_text(text_body)
    print(f"Subject: {subject}\nWrote .tmp/digest.html and .tmp/digest.txt")


if __name__ == "__main__":
    main()

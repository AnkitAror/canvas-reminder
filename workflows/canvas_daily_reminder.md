# Workflow: Canvas Daily Reminder

## Objective
Send one Gmail each morning that lists:
- what's due soon in the user's active Canvas courses
- upcoming exams and quizzes
- instructor announcements posted in the last 24 hours

## Required inputs (`.env` locally, GitHub secrets/variables in CI)
| Key | Where | Notes |
|---|---|---|
| `CANVAS_API_URL` | secret | Your school's Canvas base URL, e.g. `https://school.instructure.com` |
| `CANVAS_API_TOKEN` | secret | Canvas → Account → Settings → "+ New Access Token". Set an expiry date and record it here. |
| `GMAIL_ADDRESS` | secret | The Gmail account that sends the digest |
| `GMAIL_APP_PASSWORD` | secret | https://myaccount.google.com/apppasswords (needs 2-Step Verification). Spaces are stripped automatically. |
| `DIGEST_TO` | secret (optional) | Recipient. Defaults to `GMAIL_ADDRESS`. |
| `TIMEZONE` | variable | IANA name, e.g. `America/Chicago`. Default is `America/New_York`. |
| `LOOKAHEAD_DAYS` | variable | Default 7 |
| `ANNOUNCEMENT_LOOKBACK_HOURS` | variable | Default 24. Keep it the same as the run interval. |

## Data source modes
- **Calendar feed mode (current):** used when `CANVAS_ICS_URL` is set and `CANVAS_API_TOKEN` is blank. `tools/fetch_canvas_ics.py` reads the Canvas Calendar Feed (Canvas → Calendar → "Calendar Feed"). It gets due dates and exams from all courses. It has no announcements, and submitted items still appear. Use this when the school blocks student access tokens.
  - The course name comes from the `[Course Name]` suffix that Canvas adds to each event title.
  - All-day events are treated as due at 11:59 PM local time.
- **API mode:** used when `CANVAS_API_TOKEN` is set. It adds announcements and hides submitted items. `run_daily_digest.py` prefers this mode automatically whenever a token is present.

## Tools (run in this order)
1. `tools/fetch_canvas_data.py` writes `.tmp/canvas_digest.json`. It pulls from these endpoints:
   - `/courses` (active only)
   - `/planner/items` (assignments, quizzes, discussions, to-dos)
   - `/calendar_events?type=event` (exams and other events)
   - `/announcements`
   (In calendar feed mode, `tools/fetch_canvas_ics.py` does this step instead.)
2. `tools/build_digest_email.py` builds the subject, HTML and text. The sections are:
   - Due in 48h
   - Exams & quizzes
   - Later, grouped by course
   - Announcements
3. `tools/read_done_marks.py` reads manual "✓ Done" marks from Gmail over IMAP, using the same app password (see Completion below).
4. `tools/dedupe_and_filter.py` merges duplicate assignments, then drops every group that has a completed member.
5. `tools/send_gmail.py` sends over SMTP_SSL to smtp.gmail.com:465.

`tools/run_daily_digest.py` runs all five steps. Use `--dry-run` to write `.tmp/digest.html` without sending anything.

## Schedule
`.github/workflows/daily_digest.yml` runs at cron `0 12 * * *` (UTC). You can also trigger it manually from the Actions tab (`workflow_dispatch`). Change the cron line when you change timezones; GitHub cron does not adjust for DST.

## Edge cases & behavior
- **Canvas returns 401** (token expired or revoked): the job sends a "token invalid" alert email and exits with code 1, so the Actions run shows as failed.
- **Nothing due and no announcements:** an "all clear" email still goes out, so you know the job ran.
- **Hidden items:** an item is hidden when it is completed (see Completion below). Items with no date are skipped.
- **Exam detection:** an item counts as an exam if it is a `quiz` type, or if its title matches exam/midterm/final/quiz/test. Expect some false positives, such as "Test your setup".
- **Duplicates** (`dedupe_and_filter.py`): items are merged when all three of these hold:
  - they are due at the same minute
  - their titles match after normalization, or are at least 90% similar
  - their courses are related: the same name, or the same Rutgers course code `NN:NNN:NNN` (for example `01:640:350:03 LINEAR ALGEBRA` and `01:640:350:03 (COPY)`). When a course has no code, the names must match once "(COPY)" is removed.

  Same title and due date in *different* courses is NOT a duplicate. That bug was fixed: an early version treated any "(COPY)" course as related to every course. The email shows the real course, followed by "(+ duplicate in …)".

## Exclusion rules
- **Where:** `config/exclude_rules.json`. Each rule has an optional `course` regex and an optional `title` regex, both case-insensitive. An item is dropped when every field set in a rule matches.
- **When:** rules are applied before duplicate grouping.
- **Current rule:** Career Explorations (`01:090:210`) items whose title starts with `PRACTICE #`.
- **To add a rule:** edit the JSON, then commit and push. GitHub Actions reads the file from the repo.

## Completion
- **If ANY member of a duplicate group is completed, the whole group is done and hidden.** Completion is applied *after* grouping. That's why the fetchers keep completed items instead of dropping them.
- **API mode:** `submissions.submitted` or the planner's `marked_complete` counts as completed.
- **Calendar feed mode:** the feed has no submission status, so completion is manual.
  - Each item has a **✓ Done** mailto link. It sends an email to `GMAIL_ADDRESS` with the subject `[Canvas Done] <title> | <id>,<id>`.
  - On the next run, `read_done_marks.py` searches `[Gmail]/All Mail` for `subject:(Canvas Done) newer_than:180d` (set by `DONE_MARK_LOOKBACK_DAYS`).
  - It only trusts emails sent From `GMAIL_ADDRESS` or `DIGEST_TO`.
  - **Undo:** delete the Done email. Trash is not part of All Mail.
- **IDs:** an item's ID is its Canvas UID, for example `assignment_4383111`. The Done email carries the IDs of every member of the group.
- **If reading Gmail fails,** the digest still sends, with a warning in the footer saying done items may reappear.
- **Tested 2026-11-11:**
  - Marking only the `(COPY)` HW #10 done hid the Linear Algebra copy as well.
  - Trashing the Done email brought the item back.

## Known quirks
- Canvas limits `context_codes[]` to 10 per request, so the tools batch course codes in groups of 10.
- Some schools disable student access tokens. In that case, fall back to the Canvas calendar iCal feed (Calendar → Calendar Feed). It has due dates only, no announcements.
- GitHub scheduled runs can start 5–30 minutes late.
- GitHub disables schedules on **public** repos after 60 days without activity, so keep the repo private.
- Gmail app passwords are revoked whenever the Google account password changes.
- School Google accounts (e.g. @scarletmail.rutgers.edu) block app passwords: Google shows "The setting you are looking for is not available". Send from a personal @gmail.com account instead, and set `DIGEST_TO` if the digest should land in the school inbox.
- python.org builds of Python on macOS ship without system CA certificates, which causes `CERTIFICATE_VERIFY_FAILED` on SMTP. `send_gmail.py` passes certifi's CA bundle to fix this.
- Rutgers' calendar feed also lists cross-listed "(COPY)" course shells, so the same assignment can appear twice.

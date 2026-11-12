# Canvas Reminder

A daily email that lists what's due in your Canvas courses.

**What's in the email:**

- ⚠️ **Due in the next 48 hours**
- 📝 **Exams & quizzes** coming up
- 📅 **Everything else due this week**, grouped by course
- 📢 **New announcements** (only when you use a Canvas API token, see [Step 2](#2-connect-canvas))

**How it handles your assignments:**

- **Duplicates are merged.** The same assignment can appear in a cross-listed or "(COPY)" course. It shows up once.
- **Finished work is hidden.** Each item has a **✓ Done** button. Tap it, send the email it opens, and the item disappears from the next digest. If you mark any copy of a duplicate done, the whole group counts as done. With an API token, work you've submitted is hidden automatically.
- **Exclusion rules** let you skip things you never want to see, such as optional practice assignments.

**Where it can run:**

- **On GitHub, for free.** It runs every morning even when your laptop is off. This is recommended.
- **On your own laptop**, on a schedule.

---

## What you need

| | |
|---|---|
| **Python 3.10+** | Check with `python3 --version`. Get it from [python.org](https://www.python.org/downloads/) if needed. |
| **A Canvas account** | Any school using Canvas (`yourschool.instructure.com`). |
| **A personal Gmail account** | A regular `@gmail.com` address. School Google accounts usually block the "app password" this needs. The digest can still be **delivered** to your school address. |
| **A GitHub account** (optional) | Only needed for the free daily cloud schedule. |

Setup takes about 15 minutes.

---

## 1. Get the code

**With git:**

```bash
git clone https://github.com/<owner>/canvas-reminder.git
cd canvas-reminder
```

**Without git:** download the ZIP from the repo page (green **Code** button → **Download ZIP**), unzip it, and open a terminal in that folder.

Then install the dependencies in a virtual environment.

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell):**

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Then create your private settings file from the template:

```bash
cp .env.example .env        # Windows: copy .env.example .env
```

Open `.env` in any text editor. You'll fill it in over the next two steps.

> 🔒 `.env` holds your passwords. It's in `.gitignore`, so it never gets uploaded. Don't share it.

---

## 2. Connect Canvas

Pick **one** of the two options.

### Option A: Calendar feed (works for everyone)

1. In Canvas, click **Calendar** in the left sidebar.
2. At the bottom right, click **Calendar Feed** and copy the link.
3. Paste it into `.env`:

   ```
   CANVAS_ICS_URL=https://yourschool.instructure.com/feeds/calendars/user_xxxxx.ics
   ```

This gets due dates and exams for all your courses. It does **not** include announcements, and it can't tell what you've submitted, so use the ✓ Done button instead.

### Option B: API token (more features, if your school allows it)

1. In Canvas, go to **Account → Settings**.
2. Scroll to **Approved Integrations** and click **+ New Access Token**. Give it a name and an expiry date.
   - If there's no such button, your school blocks tokens. Use Option A.
3. Copy the token into `.env`:

   ```
   CANVAS_API_URL=https://yourschool.instructure.com
   CANVAS_API_TOKEN=paste-token-here
   ```

The API token adds announcements and hides submitted work automatically. If both options are filled in, the token is used.

---

## 3. Set up Gmail sending

The script sends mail through Gmail using an **app password**. This is a separate 16-character code, **not** your normal password.

1. Use a **personal @gmail.com** account.
2. Turn on **2-Step Verification**: https://myaccount.google.com/security
3. Create an app password at https://myaccount.google.com/apppasswords. Name it "Canvas Reminder" and copy the 16-character code. Google only shows it once.
4. Fill in `.env`:

   ```
   GMAIL_ADDRESS=you@gmail.com
   GMAIL_APP_PASSWORD=abcd efgh ijkl mnop
   DIGEST_TO=                         # optional: e.g. your school email. Blank = GMAIL_ADDRESS
   TIMEZONE=America/New_York          # your timezone (see list below)
   ```

For `TIMEZONE`, use an IANA name: `America/New_York`, `America/Chicago`, `America/Denver`, `America/Los_Angeles`, `Europe/London`, `Asia/Kolkata`, and so on. [Full list](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones).

> If Google says *"The setting you are looking for is not available for your account,"* either 2-Step Verification is off, or it's a school/work account. Use a personal Gmail.

---

## 4. Test it

Preview without sending anything:

```bash
python3 tools/run_daily_digest.py --dry-run      # Windows: py tools\run_daily_digest.py --dry-run
```

Open `.tmp/digest.html` in your browser to see the email. If it looks right, send a real one:

```bash
python3 tools/run_daily_digest.py
```

Check your inbox. You should see an email titled **📚 Canvas digest …**.

---

## 5. Make it run every day

### Option A: GitHub Actions (recommended, runs even when your laptop is off)

1. **Create your own private repo:**
   - On GitHub, click **New repository**, make it **Private**, and leave it empty.
   - Push your copy:
     ```bash
     git remote set-url origin https://github.com/<you>/canvas-reminder.git   # or: git remote add origin ...
     git push -u origin main
     ```
   - If you downloaded the ZIP instead, run `git init && git add -A && git commit -m "init"` first.
   - Keep the repo **private**. GitHub pauses schedules on public repos after 60 days without activity, and your setup is personal.
2. **Add your secrets:**
   - Open the repo → **Settings → Secrets and variables → Actions**.
   - Under **Secrets**, add each value from your `.env` that you filled in: `CANVAS_ICS_URL` (or `CANVAS_API_URL` + `CANVAS_API_TOKEN`), `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, and `DIGEST_TO` if you used it.
   - Under **Variables**, add `TIMEZONE`.

   With the [GitHub CLI](https://cli.github.com/) you can do this from the terminal instead:

   ```bash
   gh secret set CANVAS_ICS_URL       # paste the value when prompted
   gh secret set GMAIL_ADDRESS
   gh secret set GMAIL_APP_PASSWORD
   gh variable set TIMEZONE --body "America/Chicago"
   ```
3. **Set the send time.** Edit `.github/workflows/daily_digest.yml`. The schedule is in **UTC**:

   ```yaml
   - cron: "0 12 * * *"   # 12:00 UTC = 7 AM Eastern (winter) / 8 AM (summer)
   ```

   Some conversions for 7 AM local time:

   | Timezone | Winter | Summer |
   |---|---|---|
   | Eastern | `0 12` | `0 11` |
   | Central | `0 13` | `0 12` |
   | Mountain | `0 14` | `0 13` |
   | Pacific | `0 15` | `0 14` |

   GitHub doesn't adjust for daylight saving time, so the email arrives an hour off for part of the year. That's normal.
4. **Turn on Actions and test:**
   - Open the **Actions** tab. If GitHub asks, click **"I understand my workflows, go ahead and enable them."**
   - Click **Canvas daily digest → Run workflow** and wait for the green check ✅.
   - The email should arrive.

After that it runs every morning automatically. GitHub sometimes starts scheduled runs 5–30 minutes late.

> If `git push` is rejected with *"refusing to allow an OAuth App to create or update workflow"*, run `gh auth refresh -s workflow` and push again.

### Option B: Your own computer

This only runs while the computer is on and awake.

**macOS (launchd).** This example sends at 7:00 AM every day. If the Mac was asleep, it runs when the Mac wakes up.

1. Create `~/Library/LaunchAgents/com.canvas-reminder.plist`. Replace both `/FULL/PATH/TO/canvas-reminder` with your folder's path (run `pwd` inside it to get the path):

   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0"><dict>
     <key>Label</key><string>com.canvas-reminder</string>
     <key>ProgramArguments</key><array>
       <string>/FULL/PATH/TO/canvas-reminder/.venv/bin/python</string>
       <string>/FULL/PATH/TO/canvas-reminder/tools/run_daily_digest.py</string>
     </array>
     <key>WorkingDirectory</key><string>/FULL/PATH/TO/canvas-reminder</string>
     <key>StartCalendarInterval</key><dict>
       <key>Hour</key><integer>7</integer><key>Minute</key><integer>0</integer>
     </dict>
     <key>StandardOutPath</key><string>/tmp/canvas-reminder.log</string>
     <key>StandardErrorPath</key><string>/tmp/canvas-reminder.log</string>
   </dict></plist>
   ```

2. Load it:

   ```bash
   launchctl load ~/Library/LaunchAgents/com.canvas-reminder.plist
   ```

   To stop it later, run `launchctl unload ~/Library/LaunchAgents/com.canvas-reminder.plist`.

**Windows (Task Scheduler).** Run this in PowerShell from inside the project folder:

```powershell
$dir = (Get-Location).Path
schtasks /Create /SC DAILY /ST 07:00 /TN "Canvas Reminder" `
  /TR "`"$dir\.venv\Scripts\python.exe`" `"$dir\tools\run_daily_digest.py`""
```

To make it catch up after the PC was off, open Task Scheduler, find **Canvas Reminder → Properties → Settings**, and check **"Run task as soon as possible after a scheduled start is missed."**

**Linux (cron).** Run `crontab -e` and add:

```
0 7 * * * cd /FULL/PATH/TO/canvas-reminder && .venv/bin/python tools/run_daily_digest.py >> /tmp/canvas-reminder.log 2>&1
```

---

## Using it day to day

- **Mark something done:**
  - Tap **✓ Done** next to an item and send the email it opens. Leave the subject alone.
  - It's hidden starting with the next digest.
  - To undo, delete that "[Canvas Done]" email from your Sent folder and your Inbox.
  - Open the Done link with your **Gmail** app or website. Done emails sent from a different account are ignored.
- **Duplicates:**
  - Two items are merged when they have the same title (ignoring punctuation), the same due time, and are in the same course or its "(COPY)" version.
  - The email shows them once, with "(+ duplicate in …)".
  - Marking either copy done hides both.
- **Skip things you never want to see:**
  - Edit `config/exclude_rules.json`.
  - Each rule takes a `course` and/or `title` pattern (case-insensitive), for example:

    ```json
    {"note": "Skip optional readings", "course": "BIOLOGY", "title": "^Optional"}
    ```

  - ⚠️ The file comes with a rule written for one specific Rutgers course (`01:090:210`, PRACTICE assignments). **Delete it or replace it with your own.**
  - If you use GitHub Actions, commit and push after editing.
- **Change how far ahead it looks:** set `LOOKAHEAD_DAYS` in `.env`, or as a GitHub variable. The default is 7.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `CANVAS_API_URL and CANVAS_API_TOKEN must be set` / `Set CANVAS_API_TOKEN ... or CANVAS_ICS_URL` | `.env` is empty or isn't in the project folder. Fill in Step 2. |
| `Calendar feed returned 404` | The feed link was reset or copied wrong. Copy it again from Canvas → Calendar → Calendar Feed. |
| `SMTPAuthenticationError` / `Username and Password not accepted` | Use the 16-character **app password**, not your normal Gmail password. App passwords stop working when you change your Google password, so make a new one. |
| `CERTIFICATE_VERIFY_FAILED` | Run `pip install -r requirements.txt` inside the virtual environment, so `certifi` is installed. |
| "Token invalid" alert email | Your Canvas token expired. Create a new one (Step 2B) and update `.env` and the GitHub secret. |
| Email footer says *"couldn't read your Done marks"* | Gmail IMAP login failed, usually because of a wrong or revoked app password. The digest still sends, but done items may reappear. |
| GitHub run is red ❌ | Open the run in the **Actions** tab. The log shows the error. Usually a secret is missing or misspelled. |
| No email from GitHub on schedule | Check that Actions is enabled (Step 5A.4) and that the repo is private and active. |
| Two different assignments got merged | They had the same title, the same due time and related courses. Tell the maintainer, or adjust `tools/dedupe_and_filter.py`. |

---

## How it works (for the curious)

```
tools/run_daily_digest.py          entry point (add --dry-run to preview)
 ├─ fetch_canvas_ics.py / fetch_canvas_data.py   get items from Canvas (feed or API)
 ├─ read_done_marks.py             find your "[Canvas Done]" emails in Gmail (IMAP)
 ├─ dedupe_and_filter.py           apply exclusion rules → merge duplicates → drop completed groups
 ├─ build_digest_email.py          render the HTML + plain-text email
 └─ send_gmail.py                  send through Gmail SMTP
```

The detailed operating notes and known quirks are in [`workflows/canvas_daily_reminder.md`](workflows/canvas_daily_reminder.md).

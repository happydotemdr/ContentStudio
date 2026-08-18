# coach-prep-app — one-time setup

`coach-prep-app` holds its own OAuth client and token, entirely separate from
doc-ingest-app's two credential pairs. One consent grants three scopes at
once: `calendar.readonly`, `gmail.readonly`, `drive.file`.

1. In the Google Cloud Console, reuse or create a project under the
   `admin@freedom2beu.com` Workspace account.
2. Enable three APIs: **Google Calendar API**, **Gmail API**, **Google Drive API**.
3. OAuth consent screen: **User type: Internal** (same reasoning as
   doc-ingest-app/SETUP.md -- an External/Testing app's refresh tokens expire
   after 7 days, which would silently break the 4-hourly cron about a week
   after setup).
4. Create an OAuth client of type **Desktop app**.
5. Download the client secret JSON and save it as
   `coach-prep-app/client_secret.json` (gitignored -- never commit it).
6. Create the **Pending Review** Drive folder by hand (any name, e.g. "Coach
   Prep — Pending Review"), share it with `admin@freedom2beu.com` if it isn't
   already, and copy its folder ID (the long ID segment in the folder's
   Drive URL).
7. Run the app once by hand to complete the one-time browser consent:

   ```bash
   cd coach-prep-app
   python -c "from pathlib import Path; from coach_prep_app.google_clients import get_credentials; get_credentials(Path('token.json'), Path('client_secret.json'))"
   ```

   The resulting token is cached at `coach-prep-app/token.json` (gitignored)
   and refreshed silently thereafter.

Verify:

```bash
cd coach-prep-app && python -c "from pathlib import Path; from coach_prep_app.google_clients import get_credentials; c = get_credentials(Path('token.json'), Path('client_secret.json')); print('valid:', c.valid)"
```

## 2. `coach-prep-app/config.yaml` — required before the scheduled tasks run for real

Both scheduled entry points (`run_coachprep_cron.py`, `run_client_audit.py`) are
invoked by Windows Task Scheduler with **no `--config` flag** — they default to
reading `coach-prep-app/config.yaml` if it exists, and fall back to hardcoded
defaults otherwise. `pending_review_drive_folder_id` defaults to an empty
string, which both scripts now refuse to run against (`main()` fails loudly
with a clear stderr message rather than silently trying to publish to an
empty Drive folder ID). **This file must exist before Task 26 registers
either scheduled task**, or every wake will exit immediately with that error.

Create `coach-prep-app/config.yaml` (gitignored — it holds real,
environment-specific values, never commit it):

```yaml
pending_review_drive_folder_id: "<the folder ID from Step 6 above>"
notify_recipient: "brian@happydotemdr.com"  # optional -- this is already the default
```

Only `pending_review_drive_folder_id` is required; every other `Config`
field (see `coach_prep_app/config.py`) has a working default and only needs
an entry here if you want to override it. `load_config` rejects any key that
isn't a real `Config` field name, so a typo here fails loudly rather than
being silently ignored.

Verify it's picked up:

```bash
cd coach-prep-app && python -c "from pathlib import Path; from coach_prep_app import config; print(config.load_config(Path('config.yaml')).pending_review_drive_folder_id)"
```

## 3. Resend API key — required for both scheduled tasks to send email

`notify.py` reads the Resend API key from the `RESEND_API_KEY` environment
variable first, falling back to `coach-prep-app/resend_api_key.txt` if that
env var isn't set. **Environment variables are unreliable under Windows Task
Scheduler** (a system-level env var set via the GUI requires a fresh
shell/session, or a reboot, to be visible to a scheduled task) — the file is
the more reliable path for this deployment.

Create `coach-prep-app/resend_api_key.txt` (gitignored — never commit it)
containing just the raw API key from resend.com, no quotes, no trailing
newline required:

```bash
cd coach-prep-app
echo -n "re_your_actual_key_here" > resend_api_key.txt
```

Without this file (or the env var), `run_coachprep_cron.py` still publishes
drafts to Drive successfully but never sends the review email (retried every
4 hours, forever, since the watermark is deliberately left unset on a notify
failure — see `orchestrator.py`'s docstring), and `run_client_audit.py` now
exits with status 1 and a clear stderr message rather than silently
succeeding with no email sent.

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

## 4. `framework_catalog.yaml` — required before generation can pick an activity

The prep doc draws exercises from the whole `Frameworks to consider/` corpus, not just
the handful of documents in `program_sources.yaml`. It reaches them through a catalog:
one compact entry per usable activity, small enough that the whole corpus fits in a
single selection prompt.

The catalog is committed to the repo, so a fresh checkout already has one. Rebuild it
only when the corpus changes:

```bash
cd coach-prep-app
python scripts/build_framework_catalog.py --dry-run   # what would be re-indexed
python scripts/build_framework_catalog.py             # do it
```

Each changed corpus file costs one isolated `claude -p` turn, **billed to your Claude
plan**. Files whose doc-ingest version is unchanged are skipped, so a refresh after
adding one document costs one turn, not ninety. `--only <substring>` narrows it further;
`--rebuild-all` ignores versions entirely.

**Correcting an entry.** The build pass gets some wrong — a `one_line` that describes
the topic instead of what the exercise does to a client, a `use_when` tag that does not
match how Ryan would search for it. Edit `framework_catalog.yaml` by hand and set
`curated: true` on that entry. No rebuild will overwrite it. If its source document
later changes, the build names it on stdout so you can re-check it rather than leaving
a correction pinned to text that no longer exists.

Without a catalog, generation stops at the selection stage and reports
`selection_failed` — a transient status, retried on the next wake, so the run is not
lost. It never falls back to recommending an exercise from general knowledge.

## 5. Regenerating the corpus after a converter fix

`doc-ingest-app` will not retry a file that already failed at its current source
version — correct, since it stops the 30-minute cron burning firecrawl credits on a
permanently broken document. But it means a fix to the converter or the gauntlet never
reaches the files it fixes. After landing one:

```bash
cd doc-ingest-app
python scripts/run_ingest_cron.py --retry-failed "%.gsheet"
```

Pass a SQL `LIKE` pattern narrow enough to cover only what your fix addresses. Clearing
everything would also re-attempt the files still failing for unrelated reasons, at real
per-file cost.

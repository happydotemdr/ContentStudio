# doc-ingest-app — one-time setup

Two external credentials need manual, one-time setup before the cron can run:
a `FIRECRAWL_API_KEY` for the `firecrawl-py` SDK, and a Google Drive/Docs/Sheets
OAuth client. Both are per-machine setup, not part of the app's code.

## 1. Firecrawl API key

```bash
cd doc-ingest-app
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

`firecrawl-py` (in `requirements.txt`) reads `FIRECRAWL_API_KEY` from the environment
automatically — set it as a Windows user environment variable (get a key at
firecrawl.dev). Verify the key and the install both work:

```bash
python -c "from firecrawl import Firecrawl; from firecrawl.v2.types import ParseOptions; c = Firecrawl(); r = c.parse(b'<html><body>hello world</body></html>', filename='test.html', content_type='text/html', options=ParseOptions(formats=['markdown'])); print('ok:', bool(r.markdown))"
```

(HTML, not plain text, deliberately — `text/plain` isn't in firecrawl's supported format list, so a plain-text smoke test would fail with "unsupported format" and look like a broken setup when it isn't.)

If this raises an authentication error, double-check the environment variable is set
in the same shell/session that will run the cron (a system-level env var set via the
Windows GUI requires a fresh shell, or a reboot for a Task Scheduler run, to take
effect).

## 2. Google Drive/Docs/Sheets API (for `.gdoc`/`.gsheet` export)

1. In the Google Cloud Console, create a new project (or reuse an existing one) under
   the `admin@freedom2beu.com` Workspace account.
2. Enable three APIs for that project: **Google Drive API**, **Google Docs API**,
   **Google Sheets API**.
3. Configure the OAuth consent screen:
   - **User type: Internal.** This is a correctness requirement, not a preference —
     an External app left in Testing status issues refresh tokens that expire after
     7 days, which would silently break the 30-minute cron about a week after setup.
     Internal is available because `admin@freedom2beu.com` is a Workspace account, and
     it doesn't need Google's app-verification review since this is a single-user tool
     for the domain's own account.
4. Create an OAuth client of type **Desktop app**.
5. Download the client secret JSON and save it as `doc-ingest-app/client_secret.json`
   (already gitignored — never commit this file).
6. Run the app once by hand to complete the one-time browser consent:

   ```bash
   cd doc-ingest-app
   python -c "from pathlib import Path; from doc_ingest.drive_client import get_credentials; get_credentials(Path('token.json'), Path('client_secret.json'))"
   ```

   This opens a browser for one-time consent. The resulting token is cached at
   `doc-ingest-app/token.json` (gitignored) and refreshed silently thereafter.

## 3. Verify both are ready

```bash
python -c "from firecrawl import Firecrawl; from firecrawl.v2.types import ParseOptions; c = Firecrawl(); r = c.parse(b'<html><body>hello world</body></html>', filename='test.html', content_type='text/html', options=ParseOptions(formats=['markdown'])); print('ok:', bool(r.markdown))"
```

```bash
cd doc-ingest-app && python -c "from pathlib import Path; from doc_ingest.drive_client import get_credentials; c = get_credentials(Path('token.json'), Path('client_secret.json')); print('valid:', c.valid)"
```

Both must succeed before registering the cron task (`python scripts/setup_ingest_task.py --apply`).

## 4. Calendar API (for meeting-note client tagging)

This is a **separate, additive** credential from the Drive/Docs/Sheets one above —
its own OAuth client and its own token file, scoped only to `calendar.readonly`.
It exists so the classifier can look up an event's attendees to tag meeting notes
by client. Setting this up must never touch `client_secret.json` or `token.json`;
the running ingest cron's credential is not part of this flow.

1. In the Google Cloud Console, reuse the same project used for section 2 (or
   create a new one) under the `admin@freedom2beu.com` Workspace account.
2. Enable the **Google Calendar API** for that project.
3. Configure the OAuth consent screen the same way as section 2 (**User type:
   Internal**, for the same 7-day-refresh-token reason).
4. Create a **second** OAuth client of type **Desktop app** (or reuse the existing
   client and request the new scope in a separate consent) — either way, the
   scope granted must be limited to `calendar.readonly`.
5. Download the client secret JSON and save it as
   `doc-ingest-app/calendar_client_secret.json` (already gitignored — never
   commit this file, and never save it as `client_secret.json`).
6. Run the one-time browser consent by hand:

   ```bash
   cd doc-ingest-app
   python -c "from pathlib import Path; from doc_ingest.calendar_client import get_credentials; get_credentials(Path('calendar_token.json'), Path('calendar_client_secret.json'))"
   ```

   This opens a browser for one-time consent. The resulting token is cached at
   `doc-ingest-app/calendar_token.json` (gitignored) and refreshed silently
   thereafter — distinct from and never overwriting `token.json`.

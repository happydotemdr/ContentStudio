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
   already, and record its folder ID in `coach-prep-app`'s config as
   `pending_review_drive_folder_id`.
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

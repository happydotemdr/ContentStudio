# Freedom2BeU Coach-Prep Automation — Design

**Status:** Approved in brainstorming, pending final user sign-off on this written spec.
**Date:** 2026-08-17

## Context

Ryan (the F2BU coach) needs a prep document ahead of each upcoming client call: what the client
was asked to do after the last session, a draft agenda grounded in the F2BU offer/program, and a
few Positive Intelligence starter questions. Today this is manual. The goal is to automate it end
to end: detect an upcoming meeting, assemble the right inputs, generate the doc, publish it to
Drive, and email Ryan the link — on a schedule, unattended.

Two pieces of infrastructure already exist and this design deliberately extends rather than
duplicates them:

- **`doc-ingest-app`** converts Freedom2BeU's Google Drive corpus (`Freedom2BeU/converted/`) to
  local markdown with YAML frontmatter, on a 30-minute Windows Task Scheduler cron
  (`doc-ingest-app/scripts/run_ingest_cron.py` + `setup_ingest_task.py`). It owns OAuth to
  `admin@freedom2beu.com` (Drive/Docs/Sheets), a SQLite DB (`doc_ingest.db`), and a mechanical,
  non-LLM validation gate (`doc_ingest/gauntlet.py`).
- **`pipeline-app`** runs a similar cron for content discovery, and its
  `pipeline_app/comment_draft.py` already solves "let an LLM draft something from one piece of
  private data without giving it the means to go read anything else": a `claude -p` subprocess
  with every tool denied, zero MCP servers, and an empty scratch working directory. That exact
  pattern is the backbone of this design's isolation guarantee.

`Freedom2BeU/` (the real client corpus) is gitignored — it lives only in the main checkout at
`C:\Projects\ContentStudio\Freedom2BeU\`, not in this worktree. `doc-ingest-app` and `pipeline-app`
run there today via Windows Task Scheduler entries pointed at that checkout. Code from this design
gets built and reviewed here, then merged to `main`, where it becomes runnable against the real
corpus the same way — same pattern as any other change to these two apps.

### The gap this design closes

There is currently **no client field anywhere** in the corpus. Frontmatter carries only
`business_line: freedom2beu`. `Client Session Outlines/` is organized into one folder per client
(`Joanne`, `Josh`, `Ryan Ratto`, `Sean`), which is a reliable signal — but `Client Meet Recordings &
Notes/` is not: it mixes real coaching sessions with an investor meeting, a personal trip, and other
non-client calls, all as loosely-named files with no attribution. Confirmed by inspection: the
Gemini-generated notes embed an `Invited [...]` line with real attendee email addresses (e.g. the
Costa Rica note lists `jake.m.lockwood@gmail.com`; the Chris Griswold note lists
`cgris68@gmail.com` — neither is a registered client). This line is the deterministic signal the
tagging mechanism below is built on.

## Goals

1. Detect, unattended, when a registered client has a meeting the next calendar day.
2. Generate a coach-prep markdown doc: last-meeting activities (from Ryan's follow-up email),
   a draft agenda grounded in the current F2BU offer/program docs, and 3 PQ saboteur starter
   questions — for that one client only.
3. Publish the doc as a Google Doc in that client's Drive folder, and email Ryan the link by
   ~7am the day before the meeting.
4. **Never mix client data** — mechanically guaranteed, not merely LLM-trusted.
5. Always use the current version of any source document; never a stale or archived one.
6. Persist exactly which inputs produced every generated doc, for debugging and audit.
7. A weekly audit that mechanically re-checks (4) against everything generated that week.

## Non-goals (v1)

- No handling of a meeting that reschedules or cancels *after* its prep doc has already been
  generated and sent. Flagged as a known gap, not silently ignored.
- No per-client "current week/pillar" progress tracker. The agenda draws from the program docs and
  the last-meeting email only; Ryan adjusts by hand. May become a later phase.
- No use of the actual saboteur "top accomplice" per client (would require PQ assessment results
  not currently captured anywhere) — sparks draw from whatever saboteur module files exist today
  (currently only "The Judge"), extensible with zero code change as more are added.
- No auto-registration of new clients. The registry is populated by an explicit one-line command
  only.
- Exact-to-the-minute 7am delivery. See "Trigger timing" below for the accepted precision.
- Local `.md` write path for the generated doc. It is created directly as a Google Doc in Drive and
  arrives in the local mirror via `doc-ingest-app`'s existing sync on its next 30-minute wake.

## Architecture

Two phases, one coherent design, built in order because Phase 2 depends on Phase 1 being
trustworthy.

| Component | Lives in | Responsibility |
|---|---|---|
| `clients` table + frontmatter `client:` field | `doc-ingest-app` | Client registry; deterministic per-file client tagging |
| Attendee-matcher | `doc-ingest-app` (shared import) | `Invited [...]` line / attendee list → client slug or `unmatched` |
| `scripts/backfill_client_tags.py` | `doc-ingest-app` | One-time tagging of the existing ~24 meeting-note files |
| `coach-prep-app/` (new, sibling to `doc-ingest-app`/`pipeline-app`) | new | Trigger detection, bundle assembly, generation, publish, notify |
| `scripts/run_coachprep_cron.py` + `setup_coachprep_task.py` | `coach-prep-app` | `schtasks /SC MINUTE /MO 240` registration, mirrors `run_ingest_cron.py`'s shape |
| `scripts/run_client_audit.py` | `coach-prep-app` | Weekly mechanical + content leakage scan, email report |

### Phase 1 — Client Identity & Isolation Foundation

**Registry** — new table in `doc-ingest-app/doc_ingest.db`:

```sql
CREATE TABLE clients (
  slug TEXT PRIMARY KEY,          -- "sean", "josh", "joanne", "ryan_ratto"
  display_name TEXT NOT NULL,
  primary_email TEXT NOT NULL,
  alias_emails_json TEXT NOT NULL DEFAULT '[]',
  session_outlines_dir TEXT NOT NULL,   -- "Client Session Outlines/Sean"
  drive_folder_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',  -- 'active' | 'inactive' — never deleted
  created_at TEXT NOT NULL
);
```

Registration is explicit and manual via `scripts/register_client.py add --slug ... --email ...
--session-outlines-dir ... --drive-folder-id ...`. No code path ever creates a client record
automatically — an unrecognized attendee is a reason to tag `unmatched`, never a reason to invent a
new client.

**Frontmatter extension** — one new optional field, `client: <slug>`, added only for files under
`Client Meet Recordings & Notes/` and `Client Session Outlines/*/`. Offer/Framework/PQ docs stay
client-less by design — they are shared program material.

**Tagging logic — deterministic, never LLM-guessed:**

- *`Client Session Outlines/<Folder>/`*: the folder name is the client. Validated against
  `clients.display_name`/`slug` at conversion time; a folder matching no registered client fails
  loudly (an `events` row, not a silent skip) rather than being tagged on a guess.
- *`Client Meet Recordings & Notes/`*: parse the `Invited [...]` mailto addresses already present
  in the converted body. Match each address against `primary_email` / `alias_emails_json` across
  the registry.
  - Exactly one client matches → tag `client: <slug>`.
  - Zero matches, or two or more distinct clients match → tag `client: unmatched`, log an
    `events` row. This is what correctly excludes "Investor Operator Meeting" (no `Invited` line
    at all) and "Our Costa Rica Adventure" (attendee is a friend, not a client) from ever being
    attributed to a client.

**Rollout**: `scripts/backfill_client_tags.py --dry-run` produces a classification report over the
existing ~24 files for Ryan/Brian to eyeball before `--apply`. Going forward, `doc-ingest-app`'s
existing conversion worker runs the same classifier on every new/changed file under those two
folders as part of its normal 30-minute cycle — no separate process to remember to run.

### Phase 2 — Trigger, Generation & Delivery

`coach-prep-app` wakes every 4 hours (`schtasks /SC MINUTE /MO 240`, mirroring
`setup_ingest_task.py`'s registration shape exactly). Each wake:

1. **Detect**: list Calendar (`admin@freedom2beu.com`) events in the next 48 hours.
2. **Classify**: match each event's attendees against the client registry (same matcher as Phase
   1). No match → not a client meeting, skip.
3. **Gate on timing**: for a matched `(client, event)`, proceed only if local time is **≥ 7:00 AM
   on (meeting date − 1 day)** and a watermark keyed by `(client_slug, event_id)` shows this hasn't
   already run. Because the poll cadence is 4 hours, actual send time is 7:00–10:59am, not
   to-the-minute — accepted precision, not a bug.
4. **Assemble a single-client input bundle** — nothing else touches this run:
   - Most recent Gmail **sent** email to `primary_email` (`in:sent to:<address>`, most recent
     before today) — the activities source.
   - That client's most recent `client == <slug>`-tagged file in `Client Meet Recordings & Notes/`
     before today — meeting context.
   - Current (`status: current`, `gauntlet_passed_at` set) Offer & Coaching Framework docs — global.
   - Whatever files currently exist under `Frameworks to consider/Sabatoures/` — global.
   - This exact bundle — file paths, versions/hashes, Gmail thread ID, calendar event ID — is
     written to a `generation_inputs` table **before** generation runs. This row exists regardless
     of what happens downstream, and is what the weekly audit checks against.
5. **Generate**: invoke `claude -p` non-interactively — no tools, no MCP servers, empty scratch
   dir — with the bundle embedded as text in the prompt. Same isolation pattern as
   `pipeline_app/comment_draft.py`: the model cannot reach anyone else's data because it has no
   means to query anything beyond what's in the prompt.
6. **Isolation gate** (mechanical): scan the generated text for any *other* registered client's
   `display_name` / `primary_email` / alias. A hit fails the run — no doc saved, no email sent,
   logged, and (per the immediate-alert decision below) surfaced to Ryan right away rather than
   waiting for the weekly audit.
7. **Publish**: create a Google Doc via the Drive API in `drive_folder_id`, titled
   `Coach Prep — <Client> — <meeting date>`.
8. **Notify**: email Ryan (existing Resend pattern from `discovery_notify.py`) with the Doc link.
   Mark the `(client_slug, event_id)` watermark done.
9. The local `.md` mirror under `Client Session Outlines/<Client>/` appears on its own via
   `doc-ingest-app`'s next 30-minute wake, with full version/frontmatter tracking — no new
   local-write code path.

## Traceability, Weekly Audit & Error Handling

**Traceability**: the `generation_inputs` table from step 4 above is the complete record for every
run — which files (with version/hash), which Gmail thread, which calendar event. Debugging "why
does this doc say X" is a direct DB lookup.

**Weekly audit** (`scripts/run_client_audit.py`, its own weekly `schtasks` trigger):

1. *Mechanical scan*: for every `generation_inputs` row, resolve each client-scoped input's
   `client` frontmatter tag and confirm all inputs for a run resolve to one client (global docs
   excluded from this check by design). Flags mixed or untagged inputs.
2. *Content scan*: grep every generated doc's text for any other registered client's
   `display_name`/`primary_email`/alias. Flags any hit.
3. *Report*: emails Ryan a short weekly summary via the existing Resend pattern — clean, or the
   specific doc/client/reason if something's wrong.

**Error handling** (quarantine, don't discard; don't silently retry into a mess — same stance as
the existing crons):

- Calendar/Gmail/Drive API failure mid-run → log, skip that client this wake; nothing is marked
  done until step 8 succeeds, so the next 4-hourly wake retries naturally.
- `claude -p` subprocess failure or malformed output → treated like a gauntlet failure: logged with
  a reason, no partial doc, no email, watermark stays unset, retries next wake.
- Isolation-gate failure (step 6) → hard stop, never auto-retried silently, and emailed to Ryan
  immediately — the one failure mode worth interrupting for, since it's the exact thing this
  project exists to prevent.

## Testing Strategy

- **Attendee-matcher**: unit tests against fixtures built from the real ambiguous cases found
  during design (Costa Rica, Investor Operator Meeting, Chris Griswold, plus a real client note) —
  locks in "zero or multiple matches → `unmatched`, never a guess."
- **Trigger timing**: unit tests on the `(event_time, now, last_watermark)` due-check, mirroring
  `pipeline_app/discovery_scheduling.py`'s existing test style (DST edges, already-sent-today,
  not-yet-7am).
- **Isolation gate**: unit tests feeding known-bad text (containing another client's name/email)
  to confirm it blocks, and known-good text for the target client to confirm no false positive.
  **Bundle assembly / traceability**: a test that a run's persisted `generation_inputs` rows all
  resolve to exactly one client for a realistic fixture set.
- **No automated coverage of `claude -p`'s output quality** — same boundary `comment_draft.py`
  already draws; a manual-review concern, not a unit-testable one.
- **Manual verification before go-live**: run `backfill_client_tags.py --dry-run` and have
  Ryan/Brian review the classification report for all existing meeting-notes files before
  `--apply`, since that step operates on real historical data rather than a fresh code path.

## Open Questions / Risks

- Exact Drive folder IDs for each client's subfolder under `Client Session Outlines/` need to be
  looked up and entered at registration time — not yet done for any of the four existing clients.
- If Ryan's follow-up-email habits vary (sometimes no follow-up sent, or sent much later than the
  session), step 4's "most recent sent email" may occasionally pick up something stale or find
  nothing — worth a first-week manual spot-check once real runs start.

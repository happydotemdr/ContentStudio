# Freedom2BeU Coach-Prep Automation — Design

**Status:** Revised after adversarial review (Opus, 2026-08-17). Pending user sign-off on this
revision.
**Date:** 2026-08-17 (rev. 2)
**Supersedes:** rev. 1 of this same file. The review that drove this revision found the original
attendee-text-matching mechanism has confirmed false negatives in the real corpus, the freshness
selector (`status: current`) is provably false against real duplicate/archived files, the isolation
gate can't see the realistic leak shape, and the OAuth scope expansion needed for Phase 2 would
break the currently-running ingest cron. All four are addressed below; the two-phase shape and the
`claude -p` subprocess isolation pattern survive unchanged.

## Context

Ryan (the F2BU coach) needs a prep document ahead of each upcoming client call: what the client
was asked to do after the last session, a draft agenda grounded in the F2BU offer/program, and a
few Positive Intelligence starter questions. Today this is manual. The goal is to automate it end
to end: detect an upcoming meeting, assemble the right inputs, generate the doc, get it in front of
Ryan for review, and — once he's placed it where it belongs — done.

Two pieces of infrastructure already exist and this design deliberately extends rather than
duplicates them:

- **`doc-ingest-app`** converts Freedom2BeU's Google Drive corpus (`Freedom2BeU/converted/`) to
  local markdown with YAML frontmatter, on a 30-minute Windows Task Scheduler cron
  (`doc-ingest-app/scripts/run_ingest_cron.py` + `setup_ingest_task.py`). It owns OAuth to
  `admin@freedom2beu.com` with **read-only** scopes (`doc_ingest/drive_client.py:17-20` —
  `drive.readonly`, `documents.readonly`, `spreadsheets.readonly`), a SQLite DB (`doc_ingest.db`),
  and a mechanical, non-LLM validation gate (`doc_ingest/gauntlet.py`).
- **`pipeline-app`** runs a similar cron for content discovery, and its
  `pipeline_app/comment_draft.py` already solves "let an LLM draft something from one piece of
  private data without giving it the means to go read anything else": a `claude -p` subprocess
  with every tool denied, zero MCP servers, and an empty scratch working directory. That exact
  pattern is the backbone of this design's generation-isolation guarantee.

`Freedom2BeU/` (the real client corpus) is gitignored — it lives only in the main checkout at
`C:\Projects\ContentStudio\Freedom2BeU\`, not in this worktree. `doc-ingest-app` and `pipeline-app`
run there today via Windows Task Scheduler entries pointed at that checkout. Code from this design
gets built and reviewed here, then merged to `main`, where it becomes runnable against the real
corpus the same way — same pattern as any other change to these two apps.

**Credentials note, load-bearing for everything in Phase 2**: `doc-ingest-app`'s OAuth token is
read-only and does not cover Calendar, Gmail, or Drive-write. Widening it would invalidate the
current `token.json` and force a manual interactive re-consent — breaking the *running* ingest cron
until someone does that by hand (`drive_client.py`'s `build_default_service` deliberately refuses
the interactive flow under cron, so this can't self-heal). **`coach-prep-app` therefore holds its
own, separate OAuth client and token** (its own `client_secret.json`/`token.json`, its own one-time
consent flow documented the same way `doc-ingest-app/SETUP.md` documents its), scoped to exactly
what it needs: `calendar.readonly`, `gmail.readonly`, and Drive write access limited to one folder
(see "Publish" below). This never touches doc-ingest-app's credentials.

### The gap this design closes

There is currently **no client field anywhere** in the corpus. Frontmatter carries only
`business_line: freedom2beu`. `Client Session Outlines/` is organized into one folder per client
(`Joanne`, `Josh`, `Ryan Ratto`, `Sean`), which is a reliable signal — but `Client Meet Recordings &
Notes/` is not: it mixes real coaching sessions with an investor meeting, a personal trip, and other
non-client calls, all as loosely-named files with no attribution.

The original plan was to parse the `Invited [...]` mailto line Gemini renders into each note's
body. Real files rule this out: `Joanne and Ryan Chat - ... V3.gdoc.md` renders attendees as plain
`Name <email>` text with **zero `mailto:` links** for a real client session; 4 of the ~24 meeting
files have **no `Invited` line at all**, and 3 of those 4 are real client sessions, not just the
non-client cases (Investor Operator Meeting, Our Costa Rica Adventure) originally cited. A
text-parsing matcher tags real client sessions `unmatched` at a meaningful rate.

The fix: every Gemini note also carries an `Attachments [...](https://calendar.google.com/calendar/
event?eid=...)` link — present even on the files with no `Invited` line (confirmed on the Investor
Operator Meeting note). That `eid` is a **canonical join to the actual calendar event**, not a
re-parse of Gemini's own text rendering. Classification calls the Calendar API for that event's
structured attendee list instead of scraping prose.

## Goals

1. Detect, unattended, when a registered client has a meeting the next calendar day.
2. Generate a coach-prep markdown doc: last-meeting activities (from Ryan's follow-up email),
   a draft agenda grounded in the current F2BU offer/program docs, and 3 PQ saboteur starter
   questions — for that one client only, with each substantive claim tagged to the specific source
   it came from.
3. Get the draft in front of Ryan for review, with a clear, low-friction way for him to move it
   into the client's real Drive folder once he's happy with it.
4. **Never mix client data** — mechanically guaranteed where possible, and never resting on a
   single check that has a known blind spot.
5. Always ground global program/framework content in an explicitly curated, human-reviewed set of
   current files — never inferred from a per-file status flag that duplicate/archived files have
   already been shown to falsify.
6. Persist exactly which inputs produced every generated doc, with each generated claim traceable
   to one of them.
7. A weekly audit that mechanically re-checks (4) and (6) against everything generated that week.

## Non-goals (v1)

- **No auto-publish into a client's Drive folder.** The system publishes a draft to a single,
  non-client-scoped review location; moving it into the client's actual folder is a manual action
  by Ryan, and that manual action *is* the approval step. No click-to-approve web UI, no reply-to-
  approve email parsing — those are real projects if this friction turns out to matter later.
- No handling of a meeting that reschedules or cancels *after* its prep doc has already been
  generated. Flagged as a known gap, not silently ignored.
- No per-client "current week/pillar" progress tracker. The agenda draws from the program docs and
  the last-meeting email only; Ryan adjusts by hand. May become a later phase.
- No use of the actual saboteur "top accomplice" per client (would require PQ assessment results
  not currently captured anywhere) — sparks draw from whatever saboteur module files exist today
  (currently only "The Judge"), extensible with zero code change as more are added.
- No auto-registration of new clients. The registry is populated by an explicit one-line command
  only. **"Ryan Ratto" cannot be registered yet** — no email address for him appears anywhere in the
  corpus; this blocks his onboarding until Brian/Ryan supplies one (see Open Questions).
- Exact-to-the-minute 7am delivery. See "Trigger timing" below for the accepted precision.
- Local `.md` write path for the generated doc. It arrives in the local mirror via
  `doc-ingest-app`'s existing sync, once it's inside a folder doc-ingest-app watches — which, before
  Ryan moves it, it is not (see "Publish").

## Architecture

Two phases, one coherent design, built in order because Phase 2 depends on Phase 1 being
trustworthy.

| Component | Lives in | Responsibility |
|---|---|---|
| `clients` table + frontmatter `client:` field | `doc-ingest-app` | Client registry; deterministic per-file client tagging |
| Event-attendee matcher | `doc-ingest-app` (shared import) | Calendar API attendee list (live, or via a note's embedded `eid`) → client slug or `unmatched` |
| `program_sources` allowlist | `doc-ingest-app` config | Explicit, human-reviewed list of the exact global files (Offer/Framework/PQ) generation is allowed to use |
| `scripts/backfill_client_tags.py` | `doc-ingest-app` | One-time tagging of the existing ~24 meeting-note files |
| `coach-prep-app/` (new, sibling to `doc-ingest-app`/`pipeline-app`) | new | Trigger detection, bundle assembly, generation, draft publish, notify |
| `coach-prep-app`'s own OAuth credentials | `coach-prep-app` | Calendar/Gmail read, Drive write to the review folder only — independent of doc-ingest-app's token |
| `scripts/run_coachprep_cron.py` + `setup_coachprep_task.py` | `coach-prep-app` | `schtasks /SC MINUTE /MO 240` registration, same registration *shape* as `run_ingest_cron.py`'s (the due-check logic itself is new, see below) |
| `scripts/run_client_audit.py` | `coach-prep-app` | Weekly mechanical + content leakage scan, email report |

### Phase 1 — Client Identity & Isolation Foundation

**Registry** — new table in `doc-ingest-app/doc_ingest.db`:

```sql
CREATE TABLE clients (
  slug TEXT PRIMARY KEY,          -- "sean", "josh", "joanne"  ("ryan_ratto" blocked, see above)
  display_name TEXT NOT NULL,
  primary_email TEXT NOT NULL,
  alias_emails_json TEXT NOT NULL DEFAULT '[]',
  session_outlines_dir TEXT NOT NULL,   -- "Client Session Outlines/Sean"
  drive_folder_id TEXT NOT NULL,        -- the client's REAL folder; used for audit verification,
                                         -- not for direct writes (see Phase 2 Publish)
  status TEXT NOT NULL DEFAULT 'active',  -- 'active' | 'inactive' — never deleted
  created_at TEXT NOT NULL
);
```

Registration is explicit and manual via `scripts/register_client.py add --slug ... --email ...
--session-outlines-dir ... --drive-folder-id ...`. No code path ever creates a client record
automatically — an unrecognized attendee is a reason to tag `unmatched`, never a reason to invent a
new client. `admin@freedom2beu.com` (Ryan's own address, which appears in nearly every meeting) is
**always excluded** from matching before comparison — otherwise every note becomes a multi-way match
the moment any client is ever registered under a `freedom2beu.com` address too.

**Frontmatter extension** — one new optional field, `client: <slug>`, added only for files under
`Client Meet Recordings & Notes/` and `Client Session Outlines/*/`. Offer/Framework/PQ docs stay
client-less by design — they're covered by the `program_sources` allowlist instead (below).

**Tagging logic — deterministic, never LLM-guessed:**

- *`Client Session Outlines/<Folder>/`*: the folder name is the client. Validated against
  `clients.display_name`/`slug` at conversion time; a folder matching no registered client fails
  loudly (an `events` row, not a silent skip) rather than being tagged on a guess.
- *`Client Meet Recordings & Notes/`*: extract the calendar `eid` from the note's `Attachments [...]
  (https://calendar.google.com/calendar/event?eid=...)` link and call the Calendar API for that
  event's actual, structured attendee list — not a re-parse of Gemini's prose rendering. Exclude
  Ryan's own address, then match remaining attendees against `primary_email` /
  `alias_emails_json`.
  - Exactly one client matches → tag `client: <slug>`.
  - Zero matches, two or more distinct clients match, or the `eid` link is missing/the Calendar API
    call fails (e.g. a plain `.md` transcript with no Gemini export metadata, or an event since
    deleted) → tag `client: unmatched`, log an `events` row with the specific reason. This is what
    correctly excludes "Investor Operator Meeting" and "Our Costa Rica Adventure," and it no longer
    depends on Gemini's inconsistent prose rendering to do it.

**Freshness — explicit allowlist, not a status flag.** `status: current` at the source-file level
turned out not to mean "the single current version of this logical document": the Sabatoures folder
has two `status: current` copies of the Judge module (`F2BU_Module_00_The_Judge.docx.md` and
`... (1).docx.md`), and the Webinar Guide V2 exists as `status: current` in **both**
`Offer & Coaching Framework/Archived/` and `.../Current finalized documents/`. Instead of scanning
by status, `program_sources` is a small, explicit, human-maintained list of exact relative paths —
one entry per logical document — that Phase 2 is allowed to draw program/framework/PQ content from.
Adding, superseding, or retiring a program doc means updating this list, not just converting a new
file. As a cheap drift check, the same conversion worker step that maintains `client:` tags also
logs a warning (not a failure) if a file appears under `Offer & Coaching Framework/Current finalized
documents/` or `Frameworks to consider/Sabatoures/` that isn't yet in `program_sources` — a nudge to
update the list, not a silent gap.

**Rollout**: `scripts/backfill_client_tags.py --dry-run` produces a classification report over the
existing ~24 files for Ryan/Brian to eyeball before `--apply`, including an explicit count of
`unmatched` files and why each was unmatched. Going forward, `doc-ingest-app`'s existing conversion
worker runs the same classifier on every new/changed file under the two client folders as part of
its normal 30-minute cycle — no separate process to remember to run.

### Phase 2 — Trigger, Generation & Draft Delivery

`coach-prep-app` wakes every 4 hours (`schtasks /SC MINUTE /MO 240` — same registration mechanism as
`setup_ingest_task.py`, but the due-check logic below is new and per-`(client, event instance)`,
not a reuse of `discovery_scheduling.py`'s daily-once global watermark). Each wake:

1. **Detect**: list Calendar (`admin@freedom2beu.com`) events in the next 48 hours via
   `coach-prep-app`'s own credentials.
2. **Classify**: exclude Ryan's own address, then match each event's structured attendee list
   against the client registry. No match → not a client meeting, skip.
3. **Gate on timing**: for a matched `(client, event)`, proceed only if local time is **≥ 7:00 AM
   on (meeting date − 1 day)** and a watermark keyed by `(client_slug, calendar_event_instance_id)`
   — the per-**instance** ID, not the recurring-series ID, so a recurring booking doesn't get
   suppressed after its first occurrence — shows this hasn't already run. Poll cadence is 4 hours,
   so actual generation happens 7:00–10:59am, not to-the-minute — accepted precision.
   - If a client has two distinct meetings inside the 48h window, both are processed independently
     — two drafts, no dedup, no ordering assumption between them.
4. **Assemble a single-client input bundle** — nothing else touches this run:
   - Most recent Gmail **sent** email to `primary_email` (`in:sent to:<address>`, most recent
     before today) — the activities source. If the most recent match is **older than 30 days**,
     it's still used, but the bundle (and the generated doc) explicitly notes "no recent follow-up
     found" rather than presenting a stale email as current.
   - That client's most recent `client == <slug>`-tagged file in `Client Meet Recordings & Notes/`
     before today — meeting context.
   - The `program_sources` allowlist's current entries — global, not client-scoped.
   - This exact bundle — file paths with version/hash, Gmail thread ID, calendar event instance
     ID, plus a short **source label** for each item (e.g. `last-meeting-email`,
     `program-structure-v3`, `judge-module`) — is written to a `generation_inputs` table **before**
     generation runs. This row exists regardless of what happens downstream.
5. **Generate**: invoke `claude -p` non-interactively — no tools, no MCP servers, empty scratch
   dir — with the bundle embedded as text in the prompt. The prompt requires every substantive
   bullet (an activity, an agenda item, a spark) to be tagged inline with the source label it came
   from, e.g. `- Reflect on the morality exercise [last-meeting-email]`. Same isolation pattern as
   `pipeline_app/comment_draft.py`: the model cannot reach anyone else's data because it has no
   means to query anything beyond what's in the prompt.
6. **Mechanical gates** (defense-in-depth, not the sole safety mechanism — see Publish below):
   - *Citation gate*: every source-label tag in the output must match one of the bundle's own
     labels from step 4. An invented or missing label fails the run — catches both leakage-shaped
     and hallucination-shaped failures the same way.
   - *Leakage scan*: the output is checked against every *other* registered client's display name,
     email, and known first name/alias — a best-effort tripwire, understood to not catch every
     possible phrasing, which is exactly why step 7 never auto-publishes to a client-facing
     location regardless of this gate's result.
   - A failure at either gate stops the run: no draft published, no email sent, logged, and (per
     the error-handling section below) emailed to Ryan immediately rather than waiting for the
     weekly audit.
7. **Publish (draft, not final)**: create the Google Doc via the Drive API in a single,
   non-client-scoped **"Coach Prep — Pending Review"** folder — never directly in any client's
   folder. Title: `DRAFT — Coach Prep — <Client> — <meeting date> — review before use`.
8. **Notify**: email Ryan (existing Resend pattern from `discovery_notify.py`) the draft's link,
   framed as "review, then move into <Client>'s folder yourself when ready." Mark the
   `(client_slug, event_instance_id)` watermark done — this fires once per meeting regardless of
   whether Ryan acts on it.
9. **Approval, by hand**: Ryan reviews the draft and moves (or copies) it into the client's actual
   Drive folder himself when he's satisfied — that move *is* the approval. Once it's there,
   `doc-ingest-app`'s existing 30-minute sync picks it up and produces the local `.md` mirror with
   full version/frontmatter tracking automatically, same as any other file in that folder.

## Traceability, Weekly Audit & Error Handling

**Traceability**: the `generation_inputs` table from step 4 is the complete record for every run —
which files (with version/hash), which Gmail thread, which calendar event instance, and which
source label each was given. Because step 5 requires the model to tag every substantive claim with
one of those labels, and step 6's citation gate rejects any claim tagged with a label that isn't in
the bundle, "why does this doc say X" resolves to "look up the label on that bullet, then look up
that label in `generation_inputs`" — not just "here are the 5-10 documents it might have come
from."

**Weekly audit** (`scripts/run_client_audit.py`, its own weekly `schtasks` trigger):

1. *Mechanical scan*: for every `generation_inputs` row, resolve each client-scoped input's
   `client` frontmatter tag and confirm all inputs for a run resolve to one client (global
   `program_sources` entries excluded from this check by design). Flags mixed or untagged inputs.
2. *Content scan*: grep every generated doc's text for any other registered client's
   `display_name`/`primary_email`/alias/first name. Flags any hit. Understood to be a tripwire, not
   a guarantee — see step 6 above.
3. *Placement check*: for drafts marked done in step 8, check whether the doc (by Drive file ID) is
   still sitting in the Pending Review folder, or has moved — and if moved, whether it landed in
   the *correct* client's `drive_folder_id`. A draft that's been sitting unreviewed for a long time,
   or one that landed in the wrong client's folder, is worth knowing about even though Ryan doing
   the actual moving is the trusted step.
4. *Unmatched count*: how many meeting-note files are currently `client: unmatched`, so a rising
   count (a new client whose registry entry is missing, or a new corpus edge case) doesn't go
   unnoticed indefinitely.
5. *Report*: emails Ryan a short weekly summary via the existing Resend pattern — clean, or the
   specific doc/client/reason if something's wrong.

**Error handling** (quarantine, don't discard; don't silently retry into a mess — same stance as
the existing crons):

- Calendar/Gmail/Drive API failure mid-run → log, skip that client this wake; nothing is marked
  done until step 8 succeeds, so the next 4-hourly wake retries naturally.
- `claude -p` subprocess failure or malformed output → treated like a gauntlet failure: logged with
  a reason, no draft, no email, watermark stays unset, retries next wake.
- Either mechanical gate failing (step 6) → hard stop, never auto-retried silently, emailed to Ryan
  immediately — worth interrupting for, since it's the exact thing this project exists to prevent.

## Testing Strategy

- **Event-attendee matcher**: unit tests against fixtures built from the real ambiguous cases found
  during design and review — Costa Rica (no client match), Investor Operator Meeting (no `Invited`
  line, has `eid`), Chris Griswold (no client match), Joanne's V3 chat (non-mailto `Invited`
  rendering — must still resolve correctly via `eid`, not the old text parse), and a plain `.md`
  transcript with no Gemini metadata at all (must resolve to `unmatched`, not error). Also: Ryan's
  own address must never itself register as a client match.
- **`program_sources` allowlist**: a test that the duplicate-Judge-file and Archived/Current
  duplicate cases are excluded by construction (only the allowlisted path is ever selected), plus a
  drift-check test that a new file appearing under a watched folder but absent from the allowlist
  produces a warning, not a silent gap and not a hard failure.
- **Trigger timing**: unit tests on the `(event_time, now, last_watermark)` due-check — modeled on
  `pipeline_app/discovery_scheduling.py`'s test style (DST edges, already-sent-today,
  not-yet-7am) — plus a specific test that a recurring event's second occurrence is **not**
  suppressed by the first occurrence's watermark (this requires keying on instance ID, which is the
  fix for a gap found in review).
- **Mechanical gates**: unit tests feeding known-bad text (an invented citation label; another
  client's name/email/first-name) to confirm both gates block, and known-good text for the target
  client with correct citations to confirm neither false-positives.
- **Bundle assembly / traceability**: a test that a run's persisted `generation_inputs` rows all
  resolve to exactly one client (plus global sources) for a realistic fixture set, and that every
  citation label in a sample generated doc resolves to a row in that bundle.
- **No automated coverage of `claude -p`'s output quality** — same boundary `comment_draft.py`
  already draws; a manual-review concern, not a unit-testable one. This is also why Publish (step
  7) never writes to a client-facing location without Ryan's own review — the tests above cover the
  mechanism, not the model's judgment.
- **Manual verification before go-live**: run `backfill_client_tags.py --dry-run` and have
  Ryan/Brian review the classification report — including the `unmatched` list and reasons — before
  `--apply`, since that step operates on real historical data rather than a fresh code path.

## Open Questions / Risks (blocking)

- **"Ryan Ratto" has no discoverable email address anywhere in the corpus.** He cannot be
  registered, and therefore gets no automation, until Brian/Ryan supplies one. Until then his prep
  work stays fully manual, same as today.
- **`coach-prep-app` needs its own one-time OAuth consent** (Calendar readonly, Gmail readonly,
  Drive write scoped to the Pending Review folder) before Phase 2 can run at all — a documented
  manual step, deliberately kept separate from `doc-ingest-app`'s existing token so this rollout
  can't break the ingest cron that's already running in production.
- Exact Drive folder IDs for each client's real subfolder under `Client Session Outlines/` still
  need to be looked up and entered at registration time — used by the audit's placement check, not
  by Publish itself.
- `program_sources` is manually maintained. The drift-check warning mitigates staleness but doesn't
  eliminate the maintenance burden — worth a first-month check that the warning is actually getting
  noticed and acted on, not just logged into silence.

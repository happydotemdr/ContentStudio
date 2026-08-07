# Implement: `music-brief` stage + `elevenlabs-music` specialist (ContentStudio)

> **What this file is.** A self-contained kickoff prompt for a fresh agent with no
> conversation context, handing off
> [`2026-08-06-music-brief-elevenlabs-music.md`](2026-08-06-music-brief-elevenlabs-music.md)
> for implementation. Copy the body below into a new session verbatim. It deliberately does
> **not** restate the design — the plan is the single source of truth, and duplicating its
> decisions here would create two that drift.

---

## Where to work — do not create a new branch or worktree

- **Worktree:** `C:\Projects\ContentStudio\.claude\worktrees\music-brief-elevenlabs-specialist-af93d5`
- **Branch:** `claude/music-brief-elevenlabs-specialist-af93d5` — already exists, already
  pushed, upstream already tracking `origin`. **Work on this branch. Do not branch off it,
  do not create a worktree, do not switch.** Confirm before your first edit:

```bash
git branch --show-current
```

Expected: `claude/music-brief-elevenlabs-specialist-af93d5`. If it says anything else, stop
and fix that before touching a file.

## What to build

Read the plan and execute it task by task:

**`docs/superpowers/plans/2026-08-06-music-brief-elevenlabs-music.md`**

It is already committed and is the complete spec: 8 tasks, exact file paths, the actual code
and Markdown content for each step, and a verification pass. It was reviewed against the real
repo — the file paths, code claims, and predicted test failures in it were confirmed accurate.
Trust it over your own reconstruction, but grep to confirm line references before editing;
they drift.

Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to work
through it. Commit at the end of each task, as each task's final step specifies.

## Four things that will bite you if you skip this section

1. **Read the plan's "⚠ Read this before Task 1" deviation table FIRST.** The originating
   design brief's Eleven Music facts were re-verified against live vendor docs and **two were
   wrong**. The plan is built on the corrected facts. If you find yourself writing
   `lines: []` as an instrumental technique, or treating `seed` as a determinism guarantee,
   or treating `chunks[]` as inpainting-only — you have reverted to the wrong facts. The
   corrected versions: chunk plans are the `music_v2` composition plan; plan-mode instrumental
   is `negative_styles`; seed is a consistency aid the vendor explicitly disclaims as
   reproducible.

2. **Do NOT change `assembly.depends_on`.** It stays `[voiceover, visual]`. Stage rows are
   materialized only at project creation, and the unlock loop only promotes stages that have
   a DB row — a new hard dependency would leave every pre-existing project's `assembly` stage
   permanently LOCKED with no fix short of a backfill migration. The plan's Task 6 explains
   this in full. If you find yourself editing
   `test_assembly_depends_on_both_branch_stages`, stop and re-read it.

3. **There is no `ELEVENLABS_API_KEY` in this environment.** Task 1 Step 1 and Task 8 Step 7
   ask for a live generation to settle whether the vocal guard actually suppresses vocals.
   You almost certainly cannot run it. **Say so plainly, mark the affected lines
   `[T-unverified]`, record the reason in the runbook's verification log, and proceed.** Do
   not assume it works, and do not report an unrun step as passed.

4. **Marker discipline is the point of this project.** Every normative line in both new skills
   and the new runbook needs `[C]` (corpus-cited, `(Channel, video_id)` preserved verbatim),
   `[I]`, `[T]` (dated), or `[T-unverified]`. **An unmarked normative line is a bug.** Where
   the corpus is silent — and it has *zero* findings on AI music generation — say the gap
   exists. **Never fill a corpus gap with generic content-creation advice.** Read
   `CLAUDE.md`'s "Anti-generic guarantee" before writing any skill content.

## Standing constraints

- **FamilyBrain firewall.** Zero connection to `C:\Projects\FamilyBrain\` or any `brain_*` MCP
  tool. Never add a remote, submodule, or path reference to it.
- **Local only.** No deploying, no external hosting, no cloud sync.
- **Never edit an existing `rgs-briefs/*.md`** — a `PreToolUse` hook blocks it outright.
- **Never hand-edit `cowork-plugin/skills/` or `dist/`** — build artifacts. Re-run
  `scripts/build-cowork-plugin.sh`.
- **`output/` is git-ignored** — never commit it.

## Reporting

When done, report: what you built; **what you verified live vs. what stayed
`[T-unverified]`**; every gate result; and anything you could not complete and why. Lead with
the live-verification outcome — it determines how much of the specialist skill is trustworthy.
**Do not report completion for work that is partially done.**

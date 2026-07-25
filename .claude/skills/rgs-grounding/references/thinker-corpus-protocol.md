# Thinker Corpus Protocol

How `rgs-grounding` resolves a topic to a thinker citation. Two paths, in strict priority
order — never skip straight to path 2 because it's faster.

## Path 1 — the curated map (always try first)

1. Read `references/pairing-map.md` in full.
2. Look for a row whose concept plausibly fits the current topic.
3. If found: open the row's exact `Work / anchor` file path and confirm the cited
   lines/passage are still there and still say what the row claims (corpus text is static once
   downloaded, but always verify — don't trust the row's paraphrase of itself). This is the
   mandatory source-open step; it is not optional under time pressure. Skipping it because "the
   map already says this row is verified" reintroduces exactly the provenance-theater failure
   the map exists to prevent — the map records that a human verified the SOURCE, not that this
   pairing is trustworthy forever without re-reading it.
4. Use the row's `Quotability` field as-is; restate it in the Grounding Brief per beat (see
   `SKILL.md`), not just once.

## Path 2 — live-glob gap-fill (only when Path 1 has no fitting row)

1. Glob `manifests/thinkers.json`, filter to entries whose `pillars` array includes
   `"parenting"`.
2. Pick the entry that most plausibly fits the topic based on its `pillars` tags and title —
   this is a real judgment call, not a guarantee of fit.
3. Open that thinker's `.cleaned.md` file and search for an actual passage supporting the
   specific claim you're about to make. If nothing in the text actually supports it, this
   thinker is not a fit — try another candidate or report the pillar as thin for this topic
   rather than forcing a citation.
4. Any pairing produced via this path gets a **Gap-fill flag** in the Grounding Brief:

   ```markdown
   ## Gap-fill flag
   This pairing (Thinker: <name>, Concept: <concept>) came from live-glob, not the curated
   pairing map — flagged "candidate for brand-book review." Run `rgs-pairing-review` to
   formally evaluate adding it.
   ```

   `rgs-pairing-review` greps saved briefs in `rgs-briefs/` for this exact heading text
   (`## Gap-fill flag`) to find organically-discovered candidates — keep the heading text
   exact if you ever revise this protocol.

## What never happens

- Never write `[THINKER: ...]` into a brief without having opened the actual `.cleaned.md` file
  in this invocation and confirmed the passage. A thinker being "well known" for an idea is not
  a substitute for reading the specific text.
- Never treat `paraphrase-caution` as a technicality to route around — restate it at every beat
  that uses the citation, not just once at the top of the brief.

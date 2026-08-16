#!/usr/bin/env bash
# Package the .claude/skills/* skills as a Cowork plugin: the eight pipeline
# skills plus the three tool-specialist skills (elevenlabs-audio, midjourney-prompting,
# elevenlabs-music).
#
# .claude/skills/ is the single source of truth. This script copies it into
# cowork-plugin/skills/, writes a plugin.json manifest, and zips the result
# to dist/content-studio.plugin. Both cowork-plugin/ and dist/ are git-ignored
# build artifacts — never hand-edit cowork-plugin/skills/, re-run this script.
#
# The two RaisingGoodSports-only skills (rgs-grounding, rgs-pairing-review)
# are deliberately excluded from the copied plugin tree below: they depend
# on git-ignored local corpus data (output/thinkers/, output/youth-sports/,
# manifests/thinkers.json, rgs-briefs/) that this plugin doesn't bundle, so
# they can't function inside the packaged plugin.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"

PLUGIN_DIR="cowork-plugin"
PLUGIN_NAME="content-studio"

rm -rf "$PLUGIN_DIR"
mkdir -p "$PLUGIN_DIR/.claude-plugin" "$PLUGIN_DIR/skills"

# cp -R failure is already fatal under `set -euo pipefail` above; no separate
# check is needed for a short copy.
cp -R .claude/skills/. "$PLUGIN_DIR/skills/"
rm -rf "$PLUGIN_DIR/skills/rgs-grounding" "$PLUGIN_DIR/skills/rgs-pairing-review"

# Prune junk from the copied tree once, so both archive branches package an
# identical, already-clean directory. Putting the rule in the `zip` branch alone
# meant the same source produced two different artifacts depending on which
# packaging tool the machine happened to have.
find "$PLUGIN_DIR" \( -name '.DS_Store' -o -name 'Thumbs.db' -o -name '__pycache__' \) \
  -prune -exec rm -rf {} +

# The version must distinguish today's build from one made months and many skill
# edits ago. Commit count is monotonic and needs no tag discipline; the short sha
# makes the build identifiable in a bug report.
COMMIT_COUNT="$(git rev-list --count HEAD)"
SHORT_SHA="$(git rev-parse --short HEAD)"
VERSION="0.1.${COMMIT_COUNT}+g${SHORT_SHA}"

cat > "$PLUGIN_DIR/.claude-plugin/plugin.json" <<JSON
{
  "name": "content-studio",
  "version": "${VERSION}",
  "description": "Eight atomic, corpus-grounded skills taking a faceless-YouTube-Shorts idea from concept through a produced Short to multi-surface post copy, plus three tool-specialist skills (Midjourney V8.2 prompting, ElevenLabs audio, ElevenLabs Music) usable standalone or as pipeline downstreams.",
  "author": { "name": "ContentStudio" }
}
JSON

# The heredoc above is no longer quoted (it interpolates $VERSION), so it can
# no longer be assumed well-formed. Validate before anything is packaged.
python -c "import json,sys; json.load(open(sys.argv[1], encoding='utf-8'))" \
  "$PLUGIN_DIR/.claude-plugin/plugin.json"

# Assert what was actually copied against .claude/skills/ minus the two
# deliberately-excluded RGS skills, and write the tracked build stamp.
python scripts/cowork_plugin_lock.py --write --plugin-dir "$PLUGIN_DIR"

cat > "$PLUGIN_DIR/README.md" <<'MD'
# ContentStudio (Cowork plugin)

Eight atomic skills for producing faceless YouTube Shorts, chained by hand:
shorts-ideation -> shorts-scripting -> shorts-styleboard -> {voiceover-brief, visual-prompts}
  -> music-brief -> shorts-assembly -> social-repurpose.

Plus three tool-specialist skills, each usable standalone for any job in its tool
and also the downstream specialist for one pipeline stage:
  midjourney-prompting  <- visual-prompts delegates every still prompt to it
  elevenlabs-audio      <- voiceover-brief delegates the executable config to it
  elevenlabs-music      <- music-brief delegates the executable config to it

Every normative rule in these skills traces to a specific corpus finding
([C]/[I]/[T] markers) — see the parent ContentStudio repo's CLAUDE.md and
docs/ for the full corpus. This plugin ships only the skills, not the corpus
itself.
MD

mkdir -p dist
rm -f "dist/${PLUGIN_NAME}.plugin"

if command -v zip >/dev/null 2>&1; then
  ( cd "$PLUGIN_DIR" && zip -r "../dist/${PLUGIN_NAME}.plugin" . >/dev/null )
elif command -v powershell >/dev/null 2>&1 || command -v powershell.exe >/dev/null 2>&1; then
  # No `zip` on this machine (common on plain Windows) — use PowerShell's
  # Compress-Archive instead, then rename .zip -> .plugin.
  PS="$(command -v powershell.exe || command -v powershell)"
  "$PS" -NoProfile -Command "Compress-Archive -Path '$PLUGIN_DIR/*' -DestinationPath 'dist/${PLUGIN_NAME}.zip' -Force"
  mv "dist/${PLUGIN_NAME}.zip" "dist/${PLUGIN_NAME}.plugin"
else
  echo "error: neither 'zip' nor PowerShell found — install one to package the plugin." >&2
  exit 1
fi

# The roster is no longer worth re-deriving here for the echo: it was just
# asserted and recorded by cowork_plugin_lock.py above, in
# scripts/cowork-plugin.lock.json -- that file is the source of truth for
# which skills shipped, not a count printed and never checked.
echo "Built dist/${PLUGIN_NAME}.plugin (version ${VERSION}); roster recorded in scripts/cowork-plugin.lock.json."

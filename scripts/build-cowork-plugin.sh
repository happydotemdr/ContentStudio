#!/usr/bin/env bash
# Package the six .claude/skills/* skills as a Cowork plugin.
#
# .claude/skills/ is the single source of truth. This script copies it into
# cowork-plugin/skills/, writes a plugin.json manifest, and zips the result
# to dist/content-studio.plugin. Both cowork-plugin/ and dist/ are git-ignored
# build artifacts — never hand-edit cowork-plugin/skills/, re-run this script.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"

PLUGIN_DIR="cowork-plugin"
PLUGIN_NAME="content-studio"

rm -rf "$PLUGIN_DIR"
mkdir -p "$PLUGIN_DIR/.claude-plugin" "$PLUGIN_DIR/skills"

cp -R .claude/skills/. "$PLUGIN_DIR/skills/"

cat > "$PLUGIN_DIR/.claude-plugin/plugin.json" <<'JSON'
{
  "name": "content-studio",
  "version": "0.1.0",
  "description": "Six atomic, corpus-grounded skills that take a faceless-YouTube-Shorts idea from concept through a produced Short to multi-surface post copy.",
  "author": { "name": "ContentStudio" }
}
JSON

cat > "$PLUGIN_DIR/README.md" <<'MD'
# ContentStudio (Cowork plugin)

Six atomic skills for producing faceless YouTube Shorts, chained by hand:
shorts-ideation -> shorts-scripting -> {voiceover-brief, visual-prompts} -> shorts-assembly -> social-repurpose.

Every normative rule in these skills traces to a specific corpus finding
([C]/[I]/[T] markers) — see the parent ContentStudio repo's CLAUDE.md and
docs/ for the full corpus. This plugin ships only the skills, not the corpus
itself.
MD

mkdir -p dist
( cd "$PLUGIN_DIR" && zip -r "../dist/${PLUGIN_NAME}.plugin" . -x "*.DS_Store" >/dev/null )

echo "Built dist/${PLUGIN_NAME}.plugin from $(find "$PLUGIN_DIR/skills" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ') skills."

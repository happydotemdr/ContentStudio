#!/usr/bin/env bash
# Orchestrate all three corpus downloads into ./output/.
# Safe to re-run: each downloader skips items already present.
#
# Usage:
#   ./run_all.sh                 # thinkers + youth-sports + brand-intel (recent window)
#   ./run_all.sh --full-channel  # pull entire YouTube back-catalogue (much larger)
#
# Extra flags after run_all.sh are forwarded to download_brandintel.py, e.g.:
#   ./run_all.sh --cookies-from-browser chrome --limit 50
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

PY="${PYTHON:-python3}"

echo "==================================================================="
echo " ContentStudio corpus archive - downloading originals into ./output/"
echo "==================================================================="

echo
echo ">>> [1/3] Thinkers (public-domain library, 53 works)"
"$PY" download_thinkers.py --clean

echo
echo ">>> [2/3] Youth-sports (RaisingGoodSports research corpus)"
bash copy_youthsports.sh

echo
echo ">>> [3/3] Brand-intel / headless YouTube (transcripts + metadata + Bluesky/RSS)"
"$PY" download_brandintel.py "$@"

echo
echo "==================================================================="
echo " Done. Summary of ./output/:"
echo "==================================================================="
find output -type f 2>/dev/null | awk -F/ '{print $2"/"$3}' | sort | uniq -c || true
echo
echo "Total files: $(find output -type f 2>/dev/null | wc -l | tr -d ' ')"

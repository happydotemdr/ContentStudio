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
# This corpus's source is a sibling checkout that is absent in this repo by
# design. Under `set -e` a bare call aborted the whole run here and step 3 --
# the brand-intel download, the only corpus-refresh path CLAUDE.md points at --
# was unreachable (findings F-77, B-83).
youth_status=0
bash copy_youthsports.sh || youth_status=$?
if [[ "$youth_status" -eq 3 ]]; then
  echo ">>> [2/3] SKIPPED — sibling corpus/raisinggoodsports/ is not present."
elif [[ "$youth_status" -ne 0 ]]; then
  echo "! [2/3] failed with status $youth_status" >&2
  exit "$youth_status"
fi

echo
echo ">>> [3/3] brand-intel / headless YouTube (transcripts + metadata + Bluesky/RSS)"
"$PY" download_brandintel.py "$@"

echo
echo "==================================================================="
echo " Done. Summary of ./output/:"
echo "==================================================================="
find output -type f 2>/dev/null | awk -F/ '{print $2"/"$3}' | sort | uniq -c || true
echo
echo "Total files: $(find output -type f 2>/dev/null | wc -l | tr -d ' ')"

#!/usr/bin/env bash
# Copy the RaisingGoodSports youth-sports corpus verbatim.
#
# Unlike the other two corpora, this one's ORIGINAL source is already committed
# in the repo at corpus/raisinggoodsports/ (the operator's Master Edition v2
# digest + the 35 split rgs-*.md theme files + README). There is nothing to
# fetch; we just copy those files into output/ so all three corpora sit together.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$(cd "$HERE/.." && pwd)/corpus/raisinggoodsports"
DEST="$HERE/output/youth-sports/raisinggoodsports"

if [[ ! -d "$SRC" ]]; then
  echo "! Source not found: $SRC" >&2
  echo "  This step needs a sibling checkout with corpus/raisinggoodsports/ present." >&2
  echo "  Not runnable standalone in this repo — see the README's scope note." >&2
  exit 1
fi

mkdir -p "$DEST"
cp -R "$SRC"/. "$DEST"/
count="$(find "$DEST" -type f | wc -l | tr -d ' ')"
echo "youth-sports: copied $count files -> $DEST"
echo "  (includes master-edition-v2.md, 35 rgs-*.md theme files, README.md)"

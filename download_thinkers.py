#!/usr/bin/env python3
"""Download the 53-work AnchorAndWave "thinkers" public-domain corpus.

Reads manifests/thinkers.json (a per-work manifest of ordered source URLs) and
fetches the ORIGINAL raw text of each work from Project Gutenberg / Internet
Archive: ordered sourceUrls with fallback, redirects followed, a real
User-Agent, and a polite inter-work delay.

Saves per work, organised by thinker:
    output/thinkers/anchorandwave/<thinker>/<slug>.txt          (raw, as fetched)
    output/thinkers/anchorandwave/<thinker>/<slug>.cleaned.md   (with --clean)

This script only makes GET requests to public archives — no other app or
database is involved. Resumable: an existing <slug>.txt is skipped.

Usage:
    python download_thinkers.py [--clean] [--force] [--only SLUG[,SLUG...]]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("Missing dependency: pip install -r requirements.txt (needs 'requests')")

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "manifests" / "thinkers.json"
OUT_DIR = HERE / "output" / "thinkers" / "anchorandwave"
USER_AGENT = "ContentStudio-corpus-archive/1.0 (personal public-domain archival; local inspection)"
TIMEOUT = 60          # seconds; Gutenberg .txt can be ~1 MB
DELAY_S = 2.0         # politeness between works, matches acquire.ts
MIN_BYTES = 2000      # sanity floor for a "real" body


def slugify(value: str) -> str:
    value = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE).strip().lower()
    return re.sub(r"[\s_-]+", "-", value) or "unknown"


# --- optional cleaner: ports src/library/clean.ts (stripGutenbergBoilerplate + normalizeToMarkdown)
START_MARKERS = [
    re.compile(r"\*\*\*\s*START OF TH(E|IS) PROJECT GUTENBERG EBOOK.*?\*\*\*", re.IGNORECASE | re.DOTALL),
    re.compile(r"\*END\*THE SMALL PRINT!.*?\n", re.IGNORECASE),
]
END_MARKERS = [
    re.compile(r"\*\*\*\s*END OF TH(E|IS) PROJECT GUTENBERG EBOOK", re.IGNORECASE),
    re.compile(r"End of (the )?Project Gutenberg'?s? (Etext|EBook|Ebook)", re.IGNORECASE),
]
HEADING_MAX_CHARS = 60


def strip_gutenberg(raw: str) -> tuple[str, list[str]]:
    warnings: list[str] = []
    text = raw
    started = False
    for m in START_MARKERS:
        found = m.search(text)
        if found:
            text = text[found.end():]
            started = True
            break
    if not started:
        warnings.append("no-gutenberg-start-marker")
    ended = False
    for m in END_MARKERS:
        found = m.search(text)
        if found:
            text = text[: found.start()]
            ended = True
            break
    if not ended:
        warnings.append("no-gutenberg-end-marker")
    return text, warnings


def normalize_to_markdown(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x0c", "")
    paras = re.split(r"\n[ \t]*\n", text)
    out: list[str] = []
    for para in paras:
        lines = [ln.strip() for ln in para.split("\n") if ln.strip()]
        if not lines:
            continue
        joined = " ".join(lines)
        if len(joined) <= HEADING_MAX_CHARS and joined.isupper():
            out.append(f"## {joined.title()}")
        else:
            out.append(joined)
    return "\n\n".join(out) + "\n"


def clean_work_text(raw: str) -> tuple[str, list[str]]:
    stripped, warnings = strip_gutenberg(raw)
    return normalize_to_markdown(stripped), warnings


def fetch(urls: list[str], session: requests.Session) -> tuple[str, str]:
    errors = []
    for url in urls:
        try:
            resp = session.get(url, timeout=TIMEOUT, allow_redirects=True)
            if not resp.ok:
                errors.append(f"HTTP {resp.status_code} {url}")
                continue
            resp.encoding = resp.encoding or "utf-8"
            body = resp.text
            if not body.strip():
                errors.append(f"empty body {url}")
                continue
            return body, url
        except requests.RequestException as exc:
            errors.append(f"{type(exc).__name__} {url}")
    raise RuntimeError("all source URLs failed: " + " | ".join(errors))


def main() -> int:
    ap = argparse.ArgumentParser(description="Download the thinkers public-domain corpus.")
    ap.add_argument("--clean", action="store_true", help="also write <slug>.cleaned.md")
    ap.add_argument("--force", action="store_true", help="re-download even if output exists")
    ap.add_argument("--only", default="", help="comma-separated slugs to limit to")
    args = ap.parse_args()

    works = json.loads(MANIFEST.read_text(encoding="utf-8"))
    only = {s.strip() for s in args.only.split(",") if s.strip()}
    if only:
        works = [w for w in works if w["slug"] in only]

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    ok = skipped = failed = 0
    for i, w in enumerate(works):
        thinker_dir = OUT_DIR / slugify(w["thinker"])
        thinker_dir.mkdir(parents=True, exist_ok=True)
        raw_path = thinker_dir / f"{w['slug']}.txt"

        if raw_path.exists() and not args.force:
            print(f"= skip {w['slug']} (exists)")
            skipped += 1
            continue

        try:
            body, used_url = fetch(w["sourceUrls"], session)
        except RuntimeError as exc:
            print(f"! FAIL {w['slug']}: {exc}", file=sys.stderr)
            failed += 1
            continue

        if len(body.encode("utf-8")) < MIN_BYTES:
            print(f"! WARN {w['slug']}: body only {len(body)} chars from {used_url}", file=sys.stderr)

        raw_path.write_text(body, encoding="utf-8")
        note = f"  ({w['thinker']} — {w['title']})  <- {used_url}"
        print(f"+ {w['slug']}{note}")
        ok += 1

        if args.clean:
            cleaned, warnings = clean_work_text(body)
            (thinker_dir / f"{w['slug']}.cleaned.md").write_text(cleaned, encoding="utf-8")
            if warnings:
                print(f"    clean warnings: {', '.join(warnings)}")

        if i < len(works) - 1:
            time.sleep(DELAY_S)

    print(f"\nthinkers: {ok} downloaded, {skipped} skipped, {failed} failed "
          f"(of {len(works)}) -> {OUT_DIR}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

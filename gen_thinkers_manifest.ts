// Regenerates manifests/thinkers.json from a sibling app's source-of-truth
// manifest (../src/library/manifest.ts) — NOT runnable standalone in this
// repo (that sibling source tree lives elsewhere; the thinkers corpus is
// inert leftover toolkit capability here, unused by any ContentStudio skill
// — see the README's scope note). Kept as documentation of how the roster
// was originally regenerated: a pure, offline transform (no network, no DB).
//
//   npx tsx corpus-archive/gen_thinkers_manifest.ts   # from that sibling repo's root
import { writeFileSync } from 'node:fs';
import { LIBRARY_MANIFEST } from '../src/library/manifest';

const works = LIBRARY_MANIFEST.map((w) => ({
  slug: w.slug,
  thinker: w.thinker,
  title: w.title,
  pubYear: w.pubYear,
  translator: w.translator ?? null,
  translationYear: w.translationYear ?? null,
  sourceUrls: w.sourceUrls,
  sourceFormat: w.sourceFormat,
  pillars: w.pillars,
  quotability: w.quotability,
  cautionNote: w.cautionNote ?? null,
}));

const outUrl = new URL('./manifests/thinkers.json', import.meta.url);
writeFileSync(outUrl, JSON.stringify(works, null, 2) + '\n');
console.log(`wrote ${works.length} works -> corpus-archive/manifests/thinkers.json`);

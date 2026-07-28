# Pronunciation — inline IPA, PLS dictionaries, and the alias fallback

Distilled from `docs/elevenlabs-production-runbook.md` §6.

Two separate mechanisms. **Pick by model first** — most pronunciation failures are a routing error,
not a dictionary error.

## Mechanism 1 — inline IPA, `eleven_v3` only `[T]`

Write IPA between forward slashes directly in the text:

```
The cluster runs on /ˌkuːbərˈnɛtɪs/ in production.
```

- Include stress markers: `ˈ` primary, `ˌ` secondary `[T]`
- ElevenLabs reports roughly **80–90% pronunciation consistency** `[T]` — good, not deterministic
- **v3 only.** On any other model the slashes are read as literal text `[T]`

For a term that must be right *every* time across a long run, 80–90% is not enough — use a
dictionary `[I]`.

## Mechanism 2 — PLS pronunciation dictionaries `[T]`

`.PLS` (W3C Pronunciation Lexicon Specification) or `.TXT` files, uploaded once, attached per
request by locator.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<lexicon version="1.0"
    xmlns="http://www.w3.org/2005/01/pronunciation-lexicon"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.w3.org/2005/01/pronunciation-lexicon
    http://www.w3.org/TR/2007/CR-pronunciation-lexicon-20071212/pls.xsd"
    alphabet="ipa" xml:lang="en-US">

  <!-- <phoneme>: eleven_v3 and eleven_flash_v2 ONLY -->
  <lexeme>
    <grapheme>Kubernetes</grapheme>
    <phoneme>ˌkuːbərˈnɛtɪs</phoneme>
  </lexeme>

  <!-- <alias>: works on EVERY model — the safe default -->
  <lexeme>
    <grapheme>SQL</grapheme>
    <alias>Sequel</alias>
  </lexeme>

  <!-- case sensitivity: enumerate every casing you expect -->
  <lexeme><grapheme>nginx</grapheme><alias>engine ex</alias></lexeme>
  <lexeme><grapheme>NGINX</grapheme><alias>engine ex</alias></lexeme>
  <lexeme><grapheme>Nginx</grapheme><alias>engine ex</alias></lexeme>
</lexicon>
```

### The rules that matter `[T]`

| Rule | Detail |
|---|---|
| **`<phoneme>` model support** | **`eleven_v3` and `eleven_flash_v2` only.** Every other model — including `eleven_multilingual_v2` **and `eleven_flash_v2_5`** — requires `<alias>` |
| **Language** | Phoneme tags are **English-only by default**. For IPA/CMU in other languages you must use `eleven_v3` |
| **Alphabets** | IPA or CMU Arpabet. Docs recommend **CMU Arpabet for reliability** on the v2 SSML path |
| **Scope** | Phoneme substitution works on **individual words only** |
| **Case sensitivity** | **PLS matching is case-sensitive.** ElevenLabs' own example includes a term both with and without a capital for this reason |
| **Locator limit** | **Maximum 3 per request** |
| **Versioning** | `version_id` is optional; latest is used if omitted |

The supplied enterprise runbook claimed phoneme tags worked on `eleven_v3` **and
`eleven_flash_v2_5`**. That is **wrong** — it's `eleven_flash_v2`, the English-only 30k model. Flash
v2.5 cannot do phonemes. This matters because Flash v2.5 is the draft workhorse: **a phoneme fix
cannot be validated in the draft phase** `[I]`.

### v2 SSML phoneme form `[T]`

```xml
<phoneme alphabet="cmu-arpabet" ph="K UW1 B ER0 N EH1 T IY0 Z">Kubernetes</phoneme>
```

### Case-variant coverage `[I]`

Because matching is case-sensitive, a single entry silently misses real occurrences. For every term,
enumerate what will actually appear in the text:

| Term type | Enumerate |
|---|---|
| Acronym | `SQL`, `sql`, `Sql` |
| Product/brand | `nginx`, `NGINX`, `Nginx` |
| Proper noun mid-sentence and sentence-initial | `kubernetes`, `Kubernetes` |
| Possessive/plural forms if they appear | `Kubernetes'`, `APIs` |

A single-casing entry is a **finding**, not a style preference — Validation Gate 2 checks this.

### Creating and applying `[T]`

Create via `pronunciation_dictionaries.create_from_file()` (SDK) or the equivalent REST
create-from-file / add-from-rules endpoints. The response carries a
`pronunciation_dictionary_id` and a `version_id`. Apply:

```json
"pronunciation_dictionary_locators": [
  { "pronunciation_dictionary_id": "DICT_ID", "version_id": "VERSION_ID" }
]
```

**Pin `version_id` in production** `[I]`. Omitting it means the latest version is used — so a
dictionary edit silently changes the audio of a job you believed was reproducible. Dictionaries then
version independently of application code, which is the point of the mechanism.

## Choosing between them `[I]`

| Situation | Use |
|---|---|
| One-off odd word, v3, short script | Inline IPA |
| Same terms recur across many jobs | Dictionary |
| Model is not v3 or `eleven_flash_v2` | Dictionary with `<alias>` — **no other option** |
| Must be exactly right every time | Dictionary, `version_id` pinned |
| Non-English phonemes | v3 + dictionary |
| Draft phase on Flash v2.5 | `<alias>` only — phonemes are unavailable `[T]` |

## Before writing any pronunciation rule

1. **Check the model.** If it's not v3 or `eleven_flash_v2`, phonemes are off the table `[T]`.
2. **Check the language.** Non-English phonemes require v3 `[T]`.
3. **Try the text first.** Numbers, dates, currencies, and URLs are a *normalization* problem, not a
   pronunciation one — pre-convert them in the text instead `[T]` (`api-payload.md`).
4. **An alias is often the better answer even where phonemes work** `[I]` — "Sequel" for SQL is
   readable, reviewable, model-portable, and survives a routing change. Reach for IPA when the
   pronunciation genuinely can't be spelled out in ordinary letters.

# Styleboard format — the artifact Gate C reads

The styleboard artifact is the **single home of the world lock**. The prompt sheet no
longer carries one; `scripts/lint_prompt_sheet.py --styleboard <this file>` resolves
every world-lock check (C8–C10) and every slot declaration (C18) against it `[I]`.

## Exact shape

```
=== STYLEBOARD — [Short ID / title] ===

WORLD LOCK
  [the 11 keys from visual-registers.md §7, plus one slot_* line per slot the sheet uses]

BINDINGS
  [one line per slot: which Style Library entry it binds to, and why]

DISCOVERY REQUESTS
  [one line per world with no Library entry yet — or "none"]
```

The `WORLD LOCK` block's syntax is byte-identical to the block that used to live in the
prompt sheet: heading on its own line, two-space-indented `snake_case_key: value` pairs,
block ends at the first line that doesn't match `[a-z][a-z0-9_]*: value` `[I]`.

`BINDINGS` and `DISCOVERY REQUESTS` sit outside the parser — Gate C never reads them —
but they travel downstream to the render console and must always be present `[I]`.

## Why the code is not written here `[I]`

Writing a literal `--sref` code into this artifact would recreate the defect this split
exists to remove: a code invented before any image was rendered. The slot names a
*binding*; the render console resolves it against the Style Library at generate time.
An artifact that names `slot_register_a: rgs-present-soccer-a` is honest about what it
knows; one that names `--sref SREF-RGS-A-DL01` is not.

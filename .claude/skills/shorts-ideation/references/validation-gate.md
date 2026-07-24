# Validation gate

The output contract calls for a *validated* concept brief, not just a filled-in template.
This file is the gate: run every idea through these corpus-grounded checks before calling
the concept brief done. If an idea fails a check, go back to `angle-selection.md` and
re-narrow rather than shipping a brief you know is weak.

## Check 1 — Net information gain

- **`[C]` Net information gain is the core 2026 ranking lever — strongly-supported.**
  YouTube's Gemini reads the full transcript on upload; if the script repeats what other
  videos already say, it won't be pushed. Check the top 5 videos on the title/topic and
  deliberately identify what this idea says that they don't — e.g. a Titanic video about
  radio operator Jack Phillips instead of the iceberg/lifeboats everyone covers (One Person
  Business, MP7JYOm25-g; Romayroh, mPHdSkvoN10; Dan the creator, 4GAKrgNN8zQ).
  **Gate action:** name the specific new angle/fact/frame this idea adds that the top 5
  existing videos on the same topic don't. If you can't name one, the idea isn't
  differentiated enough yet — go back to `angle-selection.md`'s remix/combine/contrarian-take
  techniques.

## Check 2 — The home-feed click test

- **`[C]` "If this appeared on my own home feed, would I click it?"** Videos stuck under 200
  views are usually just too easy to ignore (Dan the creator, 1_9Xq0QnDAw).
  **Gate action:** state the packaging direction (title + thumbnail concept) out loud and
  honestly answer whether it would earn a click from a cold viewer, not just someone already
  interested in the topic.

## Check 3 — Packaging compellingness as an idea-quality proxy

- **`[C]` If you can't make compelling packaging, the idea is weak.** Deciding the title and
  thumbnail before committing to the video is itself a filter — an idea that can't produce a
  strong title/thumbnail probably isn't strong enough to make (Nick Nimmin, kcSOFqJhR9I;
  Romayroh, 1UkLWW0bs7o). **Gate action:** if `packaging-direction.md`'s checks (specific
  avatar callout, one clear focal point, complements-not-repeats-title) produced something
  generic or vague, treat that as a signal to revisit the angle, not just the packaging.

## Check 4 — Demonetization/policy safety

- **`[C]` Screen the idea against the demonetization-magnet niches before investing further.**
  Fully AI-generated "AI stories," sleeping, religion, motivation, spirituality content are
  top inauthentic-content targets (Romayroh, KbUXzJ55eJk); political content on a faceless
  channel carries a claimed ~99.9% termination risk (Romayroh, Mei39lsp9BE); avoid sensitive
  medical/financial advice framing and politicians'/celebrities' likenesses in the packaging
  direction (One Person Business, rQQjAWmA-9c). **Gate action:** confirm the idea and its
  packaging direction don't fall into any of these categories before handing off to
  scripting.

## What this gate does not cover

CTR performance after publish (the sub-5% signal in `packaging-direction.md`) and retention
mechanics (hook execution, re-hook cadence) are downstream concerns — the first is a
post-publish metric, the second belongs to `shorts-scripting`. This gate only certifies that
the *idea, angle, and packaging direction* are differentiated, clickable-in-concept, and
policy-safe before a script gets written against them.

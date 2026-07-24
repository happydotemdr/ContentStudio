# YouTube title rules

Source: `docs/headless-youtube-audit.md` §7 "Packaging (titles / thumbnails / CTR)" —
the densest section of the corpus. This is where the corpus is most confident; use it
directly rather than softening it into generic advice.

## Core rules

1. **[C] Trigger emotion/curiosity — don't describe.** Curiosity opens an information
   gap ("This one mistake killed my channel"); fear leverages loss aversion; desire
   promises transformation (Dan the creator, CWcalhl86DE; One Person Business,
   MP7JYOm25-g; Roberto Blake, TOx0RmdH1q4 — the "five C's": curiosity, conflict,
   conspiracy, confusion, controversy). Combining curiosity with negativity maximizes
   CTR (One Person Business, eVePkmCQV5c). — **strongly-supported**

2. **[C] Keep it short and front-load the strong words.** Roughly 40–60 characters;
   titles truncate around ~55 characters and 70%+ of views are mobile. Top-performer
   distributions cluster 40–50 characters (Dan the creator, CWcalhl86DE; Nick Nimmin,
   LAzYEKltBwA; Roberto Blake, InN8JOCRyXI — the "CLICKS" method; Nate Black,
   9mLuaqqW1jY). ~81.6% of top titles scored maximum clarity — an unclear title doesn't
   get clicked by new viewers (Nate Black, 9mLuaqqW1jY). — **strongly-supported**

3. **[C] Be specific; name the avatar.** Vague, broad titles fail for a small/new
   channel; naming the specific viewer ("swollen ankles after 60," "Gen X men") lets
   the algorithm route the video to the right audience (One Person Business,
   MP7JYOm25-g; Nick Nimmin, LAzYEKltBwA; vidIQ, SIp7MeYbz8U). Specificity makes the
   outcome feel attainable ("I made this in just 3 days"). Vague packaging that works
   for a multi-million-sub channel fails on a small channel, which needs
   value-explicit packaging (Nate Black, DNQ4YIkNBms). — **strongly-supported**

4. **[C] Browse titles and search titles are different games.** Browse (home
   feed/recommended) leans on curiosity/emotion; search-intent titles are clear,
   keyword-focused, evergreen (Dan the creator, CWcalhl86DE). Read the title out loud —
   if it doesn't sound conversational, rewrite it (Dan the creator, v562jH_TESg).

5. **[C] When generating candidates with AI, ask for 10 titles under 60 characters,
   avoid colons/em-dashes/semicolons, and pair each with a matching thumbnail concept**
   (Nick Nimmin, LCU3tjJHOaY). Generate several candidates this way, then hand-pick —
   don't take the first output.

## 2026 title-frame lift data (from ~4M videos)

**[C]** (vidIQ, n5NER9cbueY) — apply the highest-lift frames when they fit the Short's
actual content; frames amplify a viable topic, they do not fix a weak one:

| Frame | Lift | Example shape |
|---|---|---|
| Witness / "caught on camera" | 4.41x | "The moment X actually happened" |
| Transformation / "turning X into Y" | 3.22x | "Turning a $50 desk into a $500 one" |
| Access / "Inside X" | ~2.5x (most versatile) | "Inside the [thing] nobody sees" |
| Warning / "stop/don't/never" | ~1.77–2x (loss aversion) | "Stop doing this before X" |
| Age/tenure credibility | ~2.05x | "After 35 years, here's what I learned" |

**Underperforming, avoid leaning on these:** question titles (~0.82 lift, ~18% below
average), "I was wrong" confessions (<half average), burned-out "everything you know
about X is wrong." Plain how-to sits near-average (~1.07) — fine, not a lift lever
(vidIQ, n5NER9cbueY).

**Biggest outliers stack 3–4 frames in one title** — e.g. "99-year-old abandoned cruise
ship transformed into a luxury ocean mansion" stacks duration + forbidden +
transformation + superlative (vidIQ, n5NER9cbueY, 12M views). Don't force a stack if
the Short's content only honestly supports one or two frames — a stacked title that
over-promises triggers the "promise-breaker" problem (see item 8).

## Revenue-title data

**[C]** Tracked across ~$17.7M in creator sales (One Person Business, iwnUyE_s-6E):
- "How I" beats "How to" — how-to pulls 32% of clicks but only 18% of revenue (it hands
  over the solution, so the viewer no longer needs you).
- Exact dollar amounts, ideally as a rate, pull 34% of clicks and 52% of revenue.
- Pair hyper-specific odd numbers with identity/warning framing — "The $8,000 rule"
  beats "$10,000" (vidIQ, Sgav7Bkg36M).
- List and belief-validating "mystery" formats work well: "X Mysteries … Scientists
  Still Can't Explain" (One Person Business, eVePkmCQV5c).
- Use niche-specific "juicy words" ("dupes" in fragrance, "cheap" in meal prep)
  (Nate Black, 9mLuaqqW1jY).

**[C] Dissent, preserved not averaged:** plain, literally descriptive titles can win
because the algorithm never has to guess — the Organic Chemistry Tutor built 10.5M
subs on "How to solve quadratic equations" (vidIQ, SIp7MeYbz8U). If the Short is
strongly search-intent (a how-to/reference topic), weigh this against the emotion/
curiosity rules above rather than forcing a curiosity frame onto a clear-search topic.

## Title ↔ thumbnail and Shorts-specific constraints

6. **[C] The title must complement, not repeat, the thumbnail — a title-writing
   constraint, not a thumbnail-design task.** You only get two things to earn a click;
   repeating the thumbnail's words in the title wastes the opportunity to hit a
   *second*, different emotional trigger (One Person Business, 84bavOadYCI; One
   Person Business, MP7JYOm25-g). Full thumbnail design (VIBES framework, two-brain
   model, un-thumbnail pattern) is out of scope here — it belongs to
   `shorts-ideation`/`shorts-assembly`. This skill only needs to check the title
   doesn't collide with whatever thumbnail direction upstream already produced.

7. **[C] Shorts allow exactly one title and one thumbnail — no A/B test.** Custom
   Shorts thumbnails exist and matter specifically when Shorts traffic comes from
   search (vidIQ, mgqkfDBT7gU). Because there's no live A/B slot, get the title right
   before publishing rather than planning to iterate it live — this also matches the
   corpus's general caution against changing packaging on a live winner (Romayroh,
   1UkLWW0bs7o, §7 CTR/testing).

8. **[C] The opening must deliver on the title's promise ("the promise-breaker").** A
   title/thumbnail promise the video's opening doesn't match makes viewers bounce and
   reads to the algorithm as under-delivery (Dan the creator, 1_9Xq0QnDAw; One Person
   Business, 6RSWJ0IxKvs; Nick Nimmin, kcSOFqJhR9I). Check the title against the
   Short's actual opening line/hook before finalizing — this is a real risk when
   frame-stacking (item above) tempts you toward a bigger promise than the content
   delivers.

9. **[C] If this Short is part of a numbered series, omit the episode number from the
   title** — high episode numbers deter new viewers (Nate Black, anw0vK2a1T8).

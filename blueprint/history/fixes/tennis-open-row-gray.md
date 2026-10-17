# Fix: gray signal on the tennis slate's open row

**Type:** Fix

## The problem

A slate row opened inline (38c1, `TennisMatchDetail`) colors numbers that no
check has validated:

- **EV is green on every pick.** `.tennis-detail__ev` in
  `web/src/components/tennis/tennis-match-detail.css` sets `--positive` on best
  bets, angles and player props alike. The CSS comment says it copies the old
  side panel. The slate table and the digest color only a priced best bet's EV.
- **The LOCK and STRONG tags are green, and LEAN is amber.** `ConfidenceTag`
  reuses `.tennis-tier.is-lock` / `.is-strong` / `.is-lean`
  (`web/src/components/tennis/tennis-slate.css`). The tennis tier rule (32b)
  is still accruing for every tier, and 26b found that standard PrizePicks
  lines settle near a coin flip. So a tier is not yet a validated signal.

That breaks the project rule that an unvalidated number never gets green.

## The fix

Display only. No probability, EV, tier, rank, sort or pick changes.

- **EV:** green only when the item is a priced best bet (`kind === 'Best bet'`,
  the items `bestBetPicks` returns). That is the rule the table and the digest
  already follow. Angles and player props show EV in secondary gray.
- **Tier tags:** every tag in the open row is gray, with the text unchanged
  (LOCK, STRONG, LEAN, Review). Add a neutral `.tennis-tier.is-neutral` style
  and have `ConfidenceTag` use it. Delete the misleading comments on
  `ConfidenceTag` and `.tennis-detail__ev`.
- **Must not change:** the digest's tags and EV, the table, the shared
  `.tennis-tier.is-*` tones that other surfaces use, and the order of the
  pick list.

## Build steps

- [x] **1. Gray the open row.** In `TennisMatchDetail.tsx`, mark the EV cell
  `is-positive` only for best-bet items, and render `ConfidenceTag` as
  `is-neutral`. In the CSS, `.tennis-detail__ev` defaults to secondary text,
  `.tennis-detail__ev.is-positive` uses `--positive`, and `.tennis-tier.is-neutral`
  is added as a gray tag. **Done when** an opened row's props and angles show
  gray EV and gray tier tags, while a priced best bet's positive EV stays
  green. `npm run build` passes.

## Verify

- Open `/`, expand a match that has player props: the EVs and the
  LOCK/STRONG/LEAN tags are gray.
- Expand a match that has a priced best bet: its EV is green, and its tag is gray.
- The digest boxes above the table look unchanged.
- Run the Verify command: `npm --prefix web run verify && cd api && python -m pytest`.

## Out of scope, same rule (decide before /implement)

- **The Locks and Strong+ chips** in the page head (`TennisSlateSummary`) are
  green, and they count prop and best-bet tiers.
- **The digest's tier tags** (`TennisSlateDigest`) use the green
  `is-lock` / `is-strong` tones.
- **The tennis prop board (31c)** colors prop EV green or red
  (`evTone` in `web/src/utils/tennisPropCards.ts`).

## Outcome (2026-10-17)

- **Verify:** `npm --prefix web run verify && cd api && python -m pytest` passed
  (web typecheck, tests and build; 2597 API tests).
- **Running app, `/`, all 27 rows opened in turn:** 12 player props and 29
  angles show EV and tier in `--text-secondary` (`rgb(154, 154, 163)`); the 2
  priced best bets (+26.8%, +19.5%) keep a green EV (`rgb(0, 200, 5)`) with a
  gray tier tag. The digest's two boxes are unchanged (green EV, green LOCK and
  STRONG tags).
- **Left for a later decision (same rule):** the green Locks and Strong+ chips,
  the digest's tier tags, and the tennis prop board's green/red EV.

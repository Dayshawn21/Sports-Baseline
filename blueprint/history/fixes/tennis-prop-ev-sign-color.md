# Tennis prop EV colored by sign

**Type:** Fix

## The problem

On the tennis prop board (`/tennis/board`), a card's EV is colored by the pick's
side, not by the EV's sign. An OVER with -41.0% EV shows green, and an UNDER
with positive EV shows red. The overview says green is only for a positive
signal, so a losing EV should never be green.

The 31c spec made this choice on purpose ("EV and pick keep today's side
coloring... whatever the EV's sign"; the user decided to keep side coloring).
This fix reverses that decision for **EV only**.

Where:

- `web/src/components/tennis/TennisPropCard.tsx:24-27` - `HitBar` picks
  `is-over` / `is-under` from `card.isUnder`
- `web/src/components/tennis/TennisPropEvidencePanel.tsx:81` - `MobileSummary`
  does the same
- `web/src/components/tennis/tennis-prop-card.css:2, 224-225` - the header
  comment and the `.tennis-prop-card__ev.is-over` / `.is-under` rules

## The fix

- Add `evTone: 'positive' | 'negative' | null` to `TennisPropCardModel`, set in
  `propCard()` from `row.evPct`: above 0 is `positive`, below 0 is `negative`,
  and 0 or null is `null` (neutral gray).
- Both EV spans use `is-${card.evTone}` when it is set, and no modifier
  otherwise.
- Rename the CSS rules to `.tennis-prop-card__ev.is-positive` (`--positive`)
  and `.is-negative` (`--negative`), and update the header comment.

**Must not change:**

- The pick label (OVER / UNDER / BET) keeps its side coloring
  (`tennis-prop-card__pick`, `isUnder`)
- EV values, ranking, rateability, tiers, and every other number
- The hit bar stays neutral
- Other pages (tennis slate, best-pick cards) are out of scope

## Build steps

- [x] **Step 1 - EV tone by sign.** Add `evTone` to the card model and
  `propCard()`, use it in `HitBar` and `MobileSummary`, rename the two CSS
  rules, and fix the comment. In `tennisPropCards.test.ts`, extend the existing
  cases: OVER with positive EV gives `positive`, UNDER with negative EV
  (`-3.3%`) gives `negative`, missing EV gives `null`, and add one OVER with
  negative EV that gives `negative`.
  - **Done when:** `npm run test` and `npm run build` pass, and on
    `/tennis/board` an OVER card with negative EV shows red EV while its OVER
    label stays green.

## Verify

- `cd web && npm run test` and `npm run build`
- Open `/tennis/board`:
  - negative EV is red and positive EV is green, whichever the side
  - `EV --` stays gray
  - the pick label's color is unchanged
- At 390px, the mobile summary line under the selected card follows the same
  EV rule.

## Result (2026-09-28)

- `npm run test`: 251 passed; `npm run build` passes (`tsc -b` included).
- Live `/tennis/board` with Show all lines, headless Chromium at 1440px: an OVER
  at -29.8% EV renders red (`is-negative`) with its OVER label still green; an
  OVER at +35.6% renders green; a `--` pick at -3.7% renders red.
- At 390px the mobile summary line follows the same rule.
- Left as written: positive EV on a "Not rateable" card (for example an unlinked
  line) still shows green. Limiting green to rateable cards was raised and not
  decided.

# Fix: One set of web number, date and color formatters

**Type:** Fix
**Fixes:** F-60, F-72
**Branch:** `fix/web-formatting` (cut from `fix/web-dead-code`, so merge F-71 first)

**Completed:** 2026-11-16. Squash-merged to master at the user's request.

### The problem

The 2026-11-15 audit found the same small formatters written again and again
across `web/src`:

- **Signed numbers.** About 20 copies of `${x > 0 ? '+' : ''}${x.toFixed(n)}`
  in `nflSignal.ts`, `gapUnits.ts`, `nbaProps.ts`, `propRowVisuals.ts`,
  `nhlGame.ts`, `nhlProjection.ts`, `nflTrackRecord.ts`, `nflVolumeRecord.ts`,
  `calculators.ts`, `tennisPropCards.ts`, `nflBestLine.ts` and a few
  components. They disagree on zero: some sign before rounding (0.04 shows
  `+0.0`, -0.04 shows `-0.0`), the `>= 0` ones show an exact zero as `+0.0`,
  and `calculators.ts`, `propRowVisuals.ts`, `nhlGame.ts` round first.
- **Percentages.** `fmtPct` exists in `utils/odds.ts`, but 9 components keep a
  local `pct` (NflLineGrading, NflOverProbability, NflRankingSlices,
  NflVolumeRecord, NflPlayerRecord, ModelPrizePicksTable, ModelTierCards,
  ModelVerdictCards, ModelClv).
- **Central time.** `const CENTRAL = 'America/Chicago'` is declared in
  `gameState.ts`, `home.ts`, `nbaSlate.ts`, `nflSlate.ts` and `slatePeriod.ts`;
  `home.ts` and `slatePeriod.ts` build their own day key beside
  `format.ts` `ctDayKey`.
- **Plain dates.** `fmtMatchDateYear` (`tennisMatch.ts`) and `dateWithYear`
  (`tennisPlayer.ts`) are the same function, one without the ISO
  `.slice(0, 10)`. The two ProjectionHistory components each hand-roll a
  `shortDate` beside `tennisPlayer.ts` `shortDate`.
- **Odds math.** `tennisPropBoard.ts` keeps its own American-odds implied
  probability and de-vig instead of importing `oddsMath.ts`.
- **Tour colors.** `ParlaysPage.tsx` and `AdminPage.tsx` each keep a
  `TOUR_COLORS` map (Admin's has no CHALLENGER), while `format.ts`
  `tourColor` is unused and returns stale hex values.

### Decisions (asked 2026-11-15)

- **Placeholder:** keep each page's current missing-value text. Shared helpers
  take the placeholder, so tennis and odds cells keep the dash glyph and
  NFL/NHL keep `--`. Standardising it is a possible later fix.
- **Zero:** `fmtSigned` rounds first, then signs, and normalises -0. A value
  that rounds to zero shows unsigned (`0.0`).

### The fix

Add `fmtSigned(value, decimals, suffix?)` to `utils/format.ts`, give `fmtPct`
an optional placeholder, and route every copy above through the shared
helpers. Move the Central-time constant, the day key and the plain-date
formatters into `utils/format.ts`. `tourColor(tour)` returns the theme
variables Parlays uses today.

**Visible changes (approved above or stated here for review):**
- Values that round to zero lose their sign where they had one (`+0.0` or
  `-0.0` becomes `0.0`).
- Admin's tour tag for a Challenger row turns teal like everywhere else, where
  it is the secondary text color today.

Nothing else may change: same decimals, suffixes and placeholders per cell.
Stays inside `web/`.

### Build steps

- [x] **Step 1 - `fmtSigned`.** Add it with tests (rounding, -0, suffix,
  decimals); replace the signed-number copies in utils and components.
  Done when: grep for the inline `? '+' : ''` pattern finds only deliberate
  exceptions (named in the diff), existing tests for those utils still pass
  with only the zero cases updated, and Verify passes.
- [x] **Step 2 - `fmtPct`.** Replace the 9 component `pct` helpers and util
  copies that match it, and give `fmtPct` its own test. No placeholder
  argument after all: every replaced site either guards null itself or
  already shows the dash glyph, so it would have no caller.
  Done when: no local `pct` percent formatter remains and Verify passes.
- [x] **Step 3 - Central time and plain dates.** Export the Central zone and
  use `ctDayKey` in `home.ts` and `slatePeriod.ts`; one `shortDate` and one
  `dateWithYear` in `format.ts` used by tennisMatch, tennisPlayer and both
  ProjectionHistory components. `tennisMatch.ts` `fmtMatchDate` was a third
  copy of `shortDate` and goes too. Done when: `America/Chicago` is written
  once in `web/src` and Verify passes.
- [x] **Step 4 - odds math and tour colors.** `tennisPropBoard.ts` and
  `homeSources.ts` use `oddsMath.ts` `impliedProbFromAmerican` in place of
  `marketWinProbabilities`; `tourColor` replaces both `TOUR_COLORS` maps, with
  a test. Done when: Verify passes and the Parlays and Admin pages show the same
  tour colors as before (Challenger on Admin aside).

### Verify

- `npm --prefix web run verify` after each step.
- In the running app (`npm run dev`, port 3001): spot-check a signed value on
  the NFL board, the NHL game page and the tennis props page, a percentage on
  the NFL and tennis model pages, a date on a tennis player page, and the tour
  tags on Parlays.

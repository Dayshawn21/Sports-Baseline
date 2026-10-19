# Tennis prop board moneyline rows are reference only

**Type:** Fix
**Fixes:** F-03 (archived as `nfl-finished-week-stats/F-03`, accepted
2026-10-18 pending this repair)
**Branch:** `fix/tennis-board-moneyline-reference`

## The problem

Tennis moneyline picks have been off since the 26d follow-up fix
(`MONEYLINE_PICKS_ENABLED = False` in `api/app/services/tennis/best_picks.py:34`;
`blueprint/history/fixes/26d-follow-ups.md`), because 26d's holdout showed the
model's moneyline gaps lose at the close. The match page's moneyline EV tile
reads "-" and is never green.

The prop board rebuilds moneyline picks on the client anyway.
`moneylineBoardRows` (`web/src/utils/tennisPropBoard.ts:158`), fed from
`/tennis/predictions/today` by `TennisPropBoardPage.tsx:32`:

- sets `recommendation: 'BET'` and confidence `LEAN` whenever EV is positive
- passes `isTennisRateable` when the win probability is 50% or more, so the
  row is ranked in the actionable list
- carries `evPct`, which `propCard` (`tennisPropCards.ts:86-87`) styles
  `is-positive` (green) in the table and evidence drawer

`tennisPropBoard.test.ts:124-127` pins the `BET` behaviour, and
`tennisPropBoard.test.ts:28-32` pins the 50% floor for a moneyline row.

## The fix

Keep moneyline rows on the board as gray reference rows, the match page's
rule, without re-enabling moneylines.

- `moneylineBoardRows` emits `recommendation: null`, `confidence: null` and
  `evPct: null`. Model probability, market probability and odds stay, as
  plain numbers (the match page shows the same pair).
- `isTennisRateable` returns false for every moneyline row, so moneylines
  appear only under "Show all", unranked, trust "Review". The 50% moneyline
  floor (`MIN_MONEYLINE_WIN_PROBABILITY`) and its test go, since no moneyline
  row can be rateable.
- `signalSummary` for a moneyline row reads that it is reference only,
  because tennis moneyline picks are off, instead of the floor text.

**Must not break:**

- Prop, derived (Win a Set) and serve-edge rows, their ranking, tiers and EV
  colors are unchanged.
- No backend change; `MONEYLINE_PICKS_ENABLED` stays `False`.
- No new green anywhere; `SPORT_STATUS` on How it works already says tennis
  moneylines are off, so it needs no edit.
- No model, probability or version change.

## Build steps

- [x] **1. Moneyline board rows are reference only** - change
  `moneylineBoardRows`, `isTennisRateable` and `signalSummary` in
  `web/src/utils/tennisPropBoard.ts` as above. Replace the `BET` test with a
  regression: a clearly positive-EV moneyline input (model 62%, -110 both
  sides) yields rows with no recommendation, no confidence, no EV, not
  rateable, trust "Review", and a card with `evTone` null. Drop the moneyline
  floor test cases; keep the relative-edge test.
  **Done when:** the web tests pass, `npm run build` passes, and the
  Moneyline market on `/#/tennis/board` shows no ranked rows, "No actionable
  moneyline lines on this slate", and gray rows under Show all.

## Verify

- Full Verify command from the repo root:
  `npm --prefix web run verify && cd api && python -m pytest`.
- Manual: open the tennis prop board, pick the Moneyline market. Nothing is
  ranked; with Show all, each row shows odds and model vs market with "--" EV
  and no green; the drawer's reason says reference only.
- Run `/audit` on the branch so F-03's repair is re-reviewed before
  `/complete`. Because F-03 is already archived, record the repair in the
  fix's own archive with a pointer from the original entry's Resolution.

## Findings

### tennis-board-moneyline-reference/F-16 [P1] closed - Prop board recreates moneyline recommendations despite the moneyline-off decision (carried: nfl-finished-week-stats/F-03)

**File:** web/src/utils/tennisPropBoard.ts:157; web/src/pages/TennisPropBoardPage.tsx:32; web/src/utils/tennisPropCards.ts:86
**Found:** 2026-10-18 by /audit (scope: tennis prediction system and consumers); archived as `nfl-finished-week-stats/F-03` (accepted pending repair), carried here so its re-review is recorded with the repairing fix.
**Why it matters:** `moneylineBoardRows` turned positive-EV moneylines into `BET` rows, ranked them when the win probability was 50% or more, and colored their EV green, although tennis moneyline picks are off (`MONEYLINE_PICKS_ENABLED = False`).
**Suggested fix:** keep moneyline rows as neutral reference rows with no recommendation, ranking or positive styling; add a positive-EV regression.
**Resolution:** Fixed by `fix/tennis-board-moneyline-reference` and closed 2026-10-18 by /audit (scope: current; lenses: quality, security, performance, tests). Re-review of the repaired code:
- `moneylineBoardRows` now emits `recommendation`, `confidence` and `evPct` as null; `isTennisRateable` rejects every moneyline row first, so none can be ranked; `signalSummary` reads "Reference only: tennis moneyline picks are off".
- No remaining path to green: `propCard` gives `evTone` null and EV text `--`; the drawer hides EV when `--`; the table's hit-vs-market bar is gray (`tennis-prop-table.css:20`); `edgePct` is not rendered by any tennis board component.
- No other reader of `BET`, the removed `MIN_MONEYLINE_WIN_PROBABILITY` or `americanDecimalOdds`; `moneylineBoardRows` has one caller (`TennisPropBoardPage.tsx:32`). Prop, Win a Set and serve-edge paths are untouched.
- Regression `keeps a positive-EV moneyline as an unranked reference row...` (`tennisPropBoard.test.ts`) and the updated card test assert no recommendation, tier, EV, rank or EV tone.
- Evidence: Verify passed (611 web, 2,610 API tests, build green); live board on 2026-10-18 data showed Moneyline 0 ranked, 105 reference rows under Show all, no `.is-positive` cells.

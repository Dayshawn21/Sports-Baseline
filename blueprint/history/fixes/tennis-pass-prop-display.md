# Clarify tennis PASS prop displays

**Type:** Fix

## The problem

Tennis prop displays can make a PASS row look actionable. A bare `OVER` on
an over-only PrizePicks line reads as a recommendation, and positive EV is
colored green even when confidence is `PASS`. In
`web/src/utils/tennisPropCards.ts`, direction is passed through from
`recommendation` and EV tone currently depends only on its sign.

## The fix

Make over-only availability explicit with `OVER only` for PrizePicks demon
and goblin rows carrying `OVER`. Keep the existing payout tier visible.
For rows with `PASS` confidence, preserve the numeric EV but use a neutral
tone, including positive EV. Preserve standard OVER/UNDER recommendations
and existing non-PASS EV styling.

This is presentation only: do not change probabilities, payouts, EV math,
confidence thresholds, ranking, grading, or which lines are shown. Do not
enable goblins on the board or treat demon overs as validated signals.

## Build steps

- [x] Update the shared `propCard` display mapping and its existing unit tests.
  Confirm its consumers render the neutral EV tone and the longer direction
  label correctly; adjust a consumer only if needed.
  **Done when:** an over-only PASS row with +3.5% EV shows `OVER only`, its
  payout tier and PASS status remain visible, and the EV has no green signal
  styling. Standard recommendations and non-PASS EV styling are preserved.

## Verify

- Add regression cases in `web/src/utils/tennisPropCards.test.ts` for demon
  and goblin availability labels, positive/negative/zero/missing PASS EV,
  and unchanged standard OVER/UNDER and non-PASS displays.
- Inspect the running tennis prop display with an over-only PASS row and a
  standard row; check the board and any detail view sharing `propCard`.
- Run the documented Verify gate: `npm --prefix web run verify`, then
  `.venv\Scripts\python.exe -m pytest` from `api/` (the documented local
  venv equivalent of the combined command).

## Implementation evidence

- Implemented on `fix/tennis-pass-prop-display`; user approved the diff with
  "continue" and approved continuing closeout on 2026-10-20.
- `npm.cmd --prefix web run verify`: passed, 644 tests across 48 files,
  typecheck and production build. Vite reports its existing large-chunk warning.
- From `api/`, `.venv\Scripts\python.exe -m pytest`: 3,455 passed,
  one dependency deprecation warning.
- Table and evidence panel both consume `pickLabel` and `evTone` directly;
  their existing default EV styles are neutral. No consumer edit was needed.
- Equivalent rendering proof: Vite `ssrLoadModule` loaded the real
  `TennisPropTable` and `TennisPropEvidencePanel`; React's
  `renderToStaticMarkup` rendered both with demon PASS and standard STRONG
  fixtures. Assertions passed for `OVER only`, retained payout/PASS status,
  +3.5% EV without a signal class in both consumers, and unchanged standard
  `OVER` / +14.4% EV with `is-positive`. No database or provider was contacted.
- Browser layout verification was unavailable: Playwright could not open its
  occupied browser profile, and the alternate Node browser runtime failed to
  load. A follow-up attempt reproduced the occupied-profile failure; the
  alternate computer-use browser inventory is empty. No screenshot or
  rendered-layout pass is claimed.
- Final invariants review: clean. Presentation changes only; no query,
  holdout, model version, probability, payout or grading changes. No new
  signal color is introduced. `git diff --check` passed.
- Manual review: open `/#/tennis/board`, inspect a demon PASS row with positive
  EV, then open its detail drawer. Confirm `OVER only`, the retained PASS and
  payout tier, and neutral EV in both places. Compare a standard recommendation.
- Findings ledger: F-09 (P3) and F-12 (P2) remain unverified; no open/fixed
  P0 or P1 finding is listed.

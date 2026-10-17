# Fix: NFLverse spread sign in implied team totals

**Type:** Fix
**Status:** completed (2026-09-19). Sign corrected; the corrected implied-total
rerun improved the 2025 holdout overall but was rejected because QB and WR got
worse.

## Problem

`implied_team_points` in `api/app/core/nfl_game_script.py` treats a negative
NFLverse `spread_line` as a home favorite. It is the opposite: NFLverse
`spread_line` is the expected home margin, positive when the home team is
favored. On the stored 2012-2025 games, 2,272 home moneyline favorites carry a
positive line and 7 a negative one, and the line's MAE against the actual home
margin is 10.0 versus 14.4 with the sign flipped.

So the 19n implied-total backtest gave every favorite its opponent's implied
points. Its rejection (fitted exponent 0 and weight 0, a tie on the 2025
holdout) is what an inverted signal produces, so the signal was never fairly
tested. Production never called this code: no live projection, slate, or API
response is wrong.

The wrong convention is also written into two hand-made test fixtures
(`test_nflverse.py`: home -145 with spread -2.5; `test_nfl_td_backtest.py`:
home -150 with spread -3.0), the 19n archive, and `project-overview.md`.

## Fix

Correct the formula to home `total / 2 + spread / 2`, away `total / 2 - spread
/ 2`, pin the convention with a real NFLverse row, correct the fixtures and the
overview, then rerun the implied-total backtest once under 19n's unchanged grid
and rule and record the corrected decision.

Must not break: 24b (`core/nfl_game_lines.py` already uses the correct sign and
does not call this function), the red-zone, snap-share, and end-zone arms, or
any production output.

## Build steps

- [x] **Step 1 - Correct the sign.** Fix `implied_team_points` and its
  docstring. Replace the sign test with one built from a real stored NFLverse
  game (a home favorite with its actual `spread_line`, `total_line`, and
  moneylines), plus one road favorite. Flip the two fixtures so a home
  moneyline favorite has a positive line. Correct the `nfl_games` line in
  `project-overview.md`.
  *Done when:* the new tests fail on the old formula and pass on the new one,
  `pytest` is green, and no fixture pairs a home moneyline favorite with a
  negative `spread_line`.

- [x] **Step 2 - Rerun and record.** Run
  `python -m app.backtest.nfl_anytime_td --signal implied-total` once and apply
  19n's pre-registered rule unchanged: 2025 holdout log loss and Brier both
  improve, and no position with at least 500 evaluated games has worse log
  loss. Record the full output and the verdict below, and add a one-paragraph
  correction note to the 19n archive pointing here.
  *Done when:* the corrected decision is recorded. Adoption, if any, is a
  separate reviewed feature (19n Steps 5-6 equivalent), not part of this fix.

## Verify

- `.venv\Scripts\python.exe -m pytest` from `api/`.
- The Step 2 CLI output, compared with 19n's recorded run.
- One read-only query re-confirming the sign on stored games (home moneyline
  favorites with positive versus negative `spread_line`).

## Guardrails

- The grid, fit season (2024), holdout (2025), and adoption rule stay exactly
  as 19n registered them. Fixing an input bug is not retuning, but nothing else
  may change between the two runs.
- The 2025 holdout was already viewed once under the bug. Record that caveat
  with the result.
- No production wiring, model version bump, or UI change here.
- Leave the 19n archive's original text intact; append the correction note
  only.

## Decision

Recorded 2026-09-19 from the single corrected run
(`python -m app.backtest.nfl_anytime_td --signal implied-total`). Grid, fit
season, holdout, and rule are unchanged from 19n.

```
Implied-total configuration (fit 2024 only): league average 22.378, exponent 2.00, blend weight 0.3

set             games    LL base LL implied   LL diff   Br base Br implied   Br diff  p base p implied actual
2024 fit         3749    0.47290   0.47162  -0.00128   0.15209  0.15146  -0.00062   0.198  0.201  0.212
2025 holdout     5439    0.44382   0.44332  -0.00051   0.14033  0.14002  -0.00031   0.198  0.202  0.190
  2025 QB         582    0.37690   0.38108  +0.00418   0.11294  0.11416  +0.00122   0.158  0.162  0.141
  2025 RB        1410    0.49104   0.48849  -0.00255   0.16143  0.16021  -0.00121   0.260  0.263  0.247
  2025 TE        1174    0.43022   0.42860  -0.00162   0.13389  0.13323  -0.00066   0.145  0.148  0.169
  2025 WR        2273    0.43869   0.43883  +0.00014   0.13759  0.13763  +0.00004   0.198  0.202  0.178
```

**Rejected by the pre-registered rule, but no longer a null result.**

| Rule | Result |
|---|---|
| 2025 holdout log loss improves | Pass (0.44382 to 0.44332) |
| 2025 holdout Brier improves | Pass (0.14033 to 0.14002) |
| No position with at least 500 games has worse log loss | **Fail:** QB (582 games, +0.00418) and WR (2,273 games, +0.00014) got worse |

Under the bug the fit chose weight 0 and exponent 0, a tie. With the correct
sign the 2024 fit chose weight 0.3 and exponent 2.00, and the signal improves
the overall holdout and RB and TE. The sign bug hid a real but uneven effect.

**Caveats.**

- The 2025 holdout was viewed once before, under the bug. Only the input
  changed between the two runs.
- The fitted exponent (2.00) sits at the edge of 19n's grid.
- The RB and TE improvement is a subgroup seen after the fact. It adopts
  nothing. If pursued, an RB/TE-only implied-total arm must be pre-registered
  and scored on games not yet played (2026 onward), never refitted on 2025.

No production code changed. Anytime-TD output is identical to `master`.

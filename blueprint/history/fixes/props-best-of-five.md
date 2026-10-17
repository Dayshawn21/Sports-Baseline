# Props project men's Slam matches as best-of-3

**Type:** Fix

## The problem

The props read path never passes `best_of`, so every projection uses the
function defaults of 3. `best_of` appears nowhere in `app/routers/props.py` or
`app/repositories/props.py`.

The core layer is already best-of-5 aware and none of it engages:

- `tennis_props._BEST_OF_5_TOTAL_SCALE` is `30.45 / 22.29`, a **+36.6%** uplift
  on total games
- `prop_probs.prop_probabilities` has a dedicated `_BO5_SET_COUNT_WEIGHTS`
  mixture for over/under variance, gated on `best_of >= 5`

Measured gap from `expected_total_games_from_matchup`:

| Matchup | BO3 (projected today) | BO5 (correct) | Gap |
|---|---|---|---|
| Even, big servers | 23.73 | 32.42 | +8.69 games |
| Even, average | 22.58 | 30.85 | +8.27 games |
| Clear favorite | 21.35 | 29.17 | +7.82 games |

Roughly 8 games under-projected per men's Slam match. Against PrizePicks lines
set for best-of-5, the model reads low on Total Games and recommends UNDER
almost everywhere. This is the same systematic-bias shape as the 117/117 OVER
problem recorded in the `tennis_props.py` comments.

The data is already correct. Tomorrow's US Open R128 rows carry `best_of=5` for
ATP and `3` for WTA. Only the plumbing is missing.

Live scope: the US Open men's main draw starts 2026-08-30 and runs two weeks,
and the same bug applies to every future Slam.

**Partial existing mitigation.** `expected_total_games` and
`_downstream_total_games` short-circuit to the market total when it is >= 17.0,
so props on matches that have book odds are already anchored near the right
level. Matches without odds take the full error, and the best-of-5 probability
mixture never runs either way, so over/under confidence uses best-of-3 variance
even when the mean is right.

## The fix

Thread the `best_of` already stored on `matches` from the read path down to the
projection functions. This is plumbing, not new modelling: every coefficient and
weight it activates already exists and is already tested.

Where the parameter already exists, pass it. Where a function sits between the
router and a best-of-aware function, add a `best_of: int = 3` parameter and
forward it, so the default preserves today's behavior exactly.

It must not:

- change any projection for a best-of-3 match. Every existing test must pass
  untouched, and that is the regression bar
- introduce I/O into `app/core/`. These stay pure functions per
  `coding-standards.md`
- change the market-total short circuit. A market total is already the right
  scale and must keep passing through untouched
- guess a format for unlinked props. A prop with no linked match has no tour,
  tournament, or round to infer from, so it keeps the current default of 3
- alter ingest, ensemble, or bet behavior

Out of scope, deliberately: `prop_probs.games_won_probabilities` takes no
`best_of` and models games-won variance as a single normal. Its `expected` input
comes from `compute_stat_avg` and so will be best-of-5 correct after this fix,
meaning the mean is right and only the spread stays best-of-3. Widening that
distribution is a modelling change and belongs with build-plan item 16, not in a
plumbing fix shipped the night before the tournament.

Also out of scope, and found during step 2: `total_sets` and `total_tie_breaks`
both derive from `tennis_props.expected_sets_from_win_prob`, which is hardcoded
best-of-3 (`2.0 + 2p(1-p)`, range 2.0 to 2.5). A best-of-5 match runs 3 to 5
sets, so those two stats stay wrong for men's Slam matches after this fix, and a
correct version needs a new formula rather than a forwarded argument.

Writing that formula untested against real outcomes would turn an obviously
wrong number into a confidently wrong one, so instead these two stats are
**flagged** rather than silently projected. That is the same treatment
`match_finished` already gets: the flag joins `hard_blocks`, so no
recommendation or confidence surfaces and the prop cannot be acted on. The real
formula belongs with build-plan item 16.

A separate step covers that flag, because suppressing a recommendation is a
behavior change and deserves its own diff.

## Build steps

- [x] Carry `best_of` on the props read path.

  Done when `get_today_props` selects the linked match's `best_of` (respecting
  the existing `relinked` fallback the same way `surface` and `match_status`
  do), the `Prop` dataclass exposes it, and a test proves a prop linked to a
  best-of-5 match reports 5 while an unlinked prop reports `None`.

- [x] Thread `best_of` through the core projection functions.

  Done when `_downstream_total_games`, `expected_service_points`, and
  `expected_break_point_chances` accept `best_of: int = 3` and forward it to
  `expected_total_games`, with tests proving a best-of-5 call returns a larger
  projection than best-of-3 for the same inputs, and that omitting the argument
  reproduces the current best-of-3 numbers exactly.

- [x] Pass it from the router.

  Done when `_enrich` resolves `best_of` from the prop (defaulting to 3 when
  absent) and passes it to `_compute_stat_avg`, `_expected_service_points`,
  `_projection_inputs`, and `prop_probabilities`; and a test proves a best-of-5
  Total Games prop projects roughly 36% higher than the same prop at
  best-of-3 and takes the `_BO5_SET_COUNT_WEIGHTS` branch.

- [x] Flag set-count stats as unsupported on best-of-5.

  Done when a `total_sets` or `total_tie_breaks` prop on a `best_of >= 5` match
  carries a `bo5_unsupported_stat` data quality flag, that flag is in
  `hard_blocks` so recommendation and confidence come back `None`, the same
  stats on a best-of-3 match are untouched, and tests prove both.

## Verify

- `cd api && .venv\Scripts\python.exe -m pytest`
- `cd web && npm run build`
- Confirm the whole existing suite passes unchanged, since every current test
  covers best-of-3 and none of those numbers may move.
- Query tomorrow's US Open ATP props through the read path and confirm
  `best_of` is 5, the Total Games projection lands near the PrizePicks line
  rather than roughly 8 games under it, and WTA props are unchanged at 3.
- Compare the recommendation mix on men's US Open Total Games props before and
  after. A near-uniform UNDER skew before the fix should become a genuine split.
- Confirm a prop on a match with a market total >= 17.0 is unchanged, proving
  the market short circuit still wins.

## Result

Completed 2026-08-29, the night before the US Open men's main draw. Verify
passed: `pytest` 527 passed, `npm run build` clean, `npm run test` 31 passed.
Every pre-existing test passed unchanged, which was the regression bar. 29 tests
added across `test_props_best_of.py`, `test_prop_projection_best_of.py`, and
`test_props_router_best_of.py`.

Measured against the live slate, 1,061 best-of-5 props:

| Measure | Result |
|---|---|
| Projection change | mean **+3.72 games**, max +8.73 |
| Standard-odds props whose recommendation flipped | **14 of 101** |
| Set-count props suppressed by the new flag | 97 |

### Two corrections to the spec's own assumptions

**The market-total short circuit protected nothing.** The spec argued props on
matches with book odds were partly insulated. In practice all 1,061 best-of-5
props came back `projection_source: model_total` - none had odds - so every one
carried the full error. The bug was worse than specced, not milder.

**`compute_stat_avg` was a second, independent defect.** It already accepted
`best_of` but forwarded it only to the `total_games` branch. The `aces`,
`double_faults`, `break_points_*`, `games_won`, and `fantasy_score` branches all
dropped it, so even a correct router call would have fixed only Total Games.
Forwarding it in all five was required for the specced steps to do anything.

### Reading the recommendation mix

The post-fix mix on best-of-5 props is 773 OVER / 85 UNDER, which looks like a
new bias and is not. 941 of the 1,061 props are `goblin` or `demon`, which are
OVER-only by construction. On the 120 `standard` props, where direction is a
real choice, props recommended against their own projection: **0**. Any future
bias check on props must segment by `odds_type` or it will read this artifact as
a defect.

### Known remaining gaps

- `games_won_probabilities` still models variance as a single best-of-3 normal.
  Its mean is correct after this fix; the spread is too narrow, so confidence on
  Games Won props is mildly overstated. Build-plan item 16.
- `total_sets` and `total_tie_breaks` are suppressed, not fixed. They need a
  fitted best-of-5 set-count model. Build-plan item 16.

### Also included

`blueprint/context/project-overview.md`, regenerated by `/overview` in the same
session: item 15 moved to shipped, Alembic revision corrected from `0012` to
`0014`, the new `players` and `matches` columns documented, and the `h2h` unique
index description corrected to record the `NULLS NOT DISTINCT` plus
`p1_id < p2_id` canonicalization from migration `0013`. That last one mattered:
the old description would have led a future session to recreate the index that
caused 5,369 duplicate rows.

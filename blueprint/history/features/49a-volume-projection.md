# Feature: Volume times efficiency projection

**From build-plan:** feature 49a (NFL market-anchored prop model)
**Status:** complete (2026-10-30)
**Proposed branch:** `feature/nfl-volume-projection`

## Goal

Build an NFL prop projection that predicts each player-game's whole outcome
distribution, not a single mean. It works from three parts: how many plays
the team runs, the player's share of those plays, and what the player does
per opportunity. The win is a median and a spread that behave like real
results, which v4 lacks: v4 projects a mean while PrizePicks posts near the
median, so every v4 market leans OVER (27b `share_below` 54% to 64%).

The projection is chosen by rolling-origin validation over 2021-2025 against
a simple reference, under a rule pre-registered before any score is read.
Backtest only: nothing in production changes. 49b anchors the result to real
lines; this item never reads a PrizePicks line.

One feature with eight reviewable steps. No visual target or web change.

## In scope

- **History backfill.** NFLverse weekly player stats, snap counts and weekly
  rosters for 2018-2023 into the existing tables, through the existing
  ingest commands. Every season is published back to 2012 (checked
  2026-10-29). The stored history today holds 2024-2026 only.
- **Pure outcome distributions** (sport-neutral, in `app/core/`): a negative
  binomial for counts, a compound distribution for yards, CDF, median and
  CRPS.
- **Pure volume times efficiency projection** for seven markets, using
  pre-week inputs only.
- **A read-only season loader** for player-games, team-games and closing
  lines.
- **Rolling-origin fitting and scoring.** Score each season from 2021 to 2025
  with constants fitted only on 2018 through the season before it.
- **The adoption rule** as tested constants, committed as a pre-registration
  checkpoint before the first scoring run.
- **A CLI, one recorded run, and a frozen `nfl-volume-v1` configuration** for
  each adopted market.

## Out of scope

- PrizePicks or sportsbook lines of any kind, including the line anchor
  (49b).
- Serving, freezing, the slate, the prop board, pages, API schemas, 27j and
  `/nfl/model` (49c, 49d).
- Changes to v4's markets, versions, fit tables or forward sample. The same
  goes for Rec Targets.
- Fantasy points, anytime TD, Rec Targets and line-only markets.
- DVP, weather, injuries, depth charts, QB changes, teammate absences and
  rookies with no NFL history. These are candidates for a later version.
  Rookies are excluded from the cohort, and the report counts them.
- Schema migrations. The backfill writes only to existing tables.
- Any second candidate, tuning flag, or rerun with different settings after
  the first scored run.

## Build loop

Build one step at a time, never the whole feature at once.

1. Lay out the step before code.
2. Implement only that step, with its tests.
3. Show the diff and evidence for its done-when.
4. The user reviews and approves before the next step, and may choose an
   optional checkpoint commit. `/complete` owns the feature-level commit.

Split any diff too large to read in one sitting.

## Build steps

- [x] **Step 1 - Backfill 2018-2023 player history.** Check the Neon
  database size against its plan limit first. Then, for each season from 2018
  to 2023, run each command as a dry run:
  - `python -m app.ingest.nflverse --season S`
  - `python -m app.ingest.nflverse_snap_counts --season S`
  - `python -m app.ingest.nflverse_rosters --season S`

  Real runs need the owner's yes in chat, one command at a time, against the
  shared database. If an older file's columns differ, fix the parser with a
  test first. Never coerce a missing column to zero. Update the outdated
  "per-season asset covers 2022 onward" comment in `player_stats_url`.

  Run the seasons oldest first, in the order stats, rosters, snaps. Rosters
  and snaps skip players not yet stored. `upsert_player` overwrites
  `sport_players.name` and `team_id` with the loaded season's values, so
  after 2023, rerun `python -m app.ingest.nflverse --season` for 2024, 2025
  and 2026. That restores every player's latest name and team. Those reruns
  are the same idempotent upserts the scheduled job already makes.

  *Done when:*
  - A read-only count shows player-weeks, non-null targets and target share,
    snaps and roster rows per season from 2018 to 2025, recorded under
    Results.
  - The 2025 run of `python -m app.backtest.nfl_projections --arms
    production` prints the same tables as before the backfill. Diff the
    output, which shows the new seasons do not leak into v4.
  - No migration ran.

- [x] **Step 2 - Pure outcome distributions.** Add
  `app/core/outcome_distribution.py` with no NFL imports:
  - A negative binomial parameterized by mean and dispersion.
  - A compound yards distribution: N opportunities from a negative binomial,
    with yards per opportunity normal (fitted mean and sd), so
    `yards | N ~ Normal(N * mu, sqrt(N) * sd)` and N = 0 is a point mass at
    zero. Truncate N where the tail mass falls below 1e-6.
  - `cdf(x)`, `median()`, `p_over(line)` with an explicit push probability
    for integer count lines, and `crps(actual)` on a fixed grid. Use unit
    steps for counts and 1-yard steps for yards, from -20 to 600 yards.

  *Done when:* unit tests prove the PMFs sum to 1 within 1e-9, the mean and
  variance match the closed forms, the median of a skewed case falls below
  its mean, P(over) plus P(under) plus P(push) equals 1, and CRPS matches a
  hand-computed small case. Two more cases are covered: CRPS is zero for a
  point mass at the actual, and invalid parameters raise.

- [x] **Step 3 - Pure volume times efficiency projection.** Add
  `app/core/nfl_volume_projection.py`. It takes typed pre-week player
  history and team context and returns one distribution per eligible
  (position, market), using `REPLAY_MARKETS_BY_POSITION` for the seven
  markets:
  - **Team volume:** expected team pass attempts and rush attempts, as
    `a + b * implied_team_total + c * implied_margin`, using
    `nfl_game_environment.team_lines` for the split.
  - **Player share:** target share, carry share, and pass-attempt share for
    QBs. The current season counts by games; the previous season is weighted
    by `PREVIOUS_SEASON_WEIGHT` (0.6). The result is shrunk toward the
    position's share with `K_share` prior games.
  - **Efficiency:** catch rate, completion rate, and yards per target,
    carry and attempt, each shrunk toward the position rate with
    `K_rate[market]` prior opportunities.
  - **Assembly:** counts are the negative binomial at mean = volume x share
    (x rate for receptions and completions). Yards are the compound
    distribution with N at volume x share, and per-opportunity mean and sd
    from the shrunk rate and the fitted spread.

  *Done when:* unit tests cover:
  - Pre-week filtering, so a same-week game never counts.
  - The previous-season weight.
  - Shrinkage limits (zero games means the position prior; many games
    approach the player).
  - Home and away signs on the margin.
  - Zero versus missing opportunities.
  - A rookie with no history returns no projection, with a reason.
  - A QB's receiving markets are never produced.

  The input is not mutated. Every constant is a parameter, with no default
  that silently stands in for a fitted value.

- [x] **Step 4 - Read-only season loader.** Add
  `app/repositories/nfl_volume.py` with
  `get_volume_history(db, first_season, last_season)`. It returns typed rows:
  - Every regular-season player-game: player, team from weekly rosters,
    position, week, stats, targets, target share and offensive snaps.
  - Every team-game: pass and rush attempts summed from player stats, and
    plays from `nfl_team_game_efficiency`.
  - Each game's closing `spread_line` and `total_line`.

  Pre-week cutoffs are applied in pure code, not SQL.

  *Done when:* recorded-SQL tests prove the following, and no existing
  reader changes:
  - `sport = 'nfl'` on every shared-table alias, with `REG` and completed
    filters.
  - Roster-side team resolution.
  - Nullable stats stay null, with no `coalesce` to zero.
  - One row per player-game.

- [x] **Step 5 - Fitting both arms on fit seasons.** Add
  `app/core/nfl_volume_backtest.py` with `fit_volume(cases, fit_seasons)` and
  `fit_reference(cases, fit_seasons)`.

  **The volume arm** (each fitted only on fit seasons, from 2018 to s-1):
  - The team-volume regression.
  - Dispersion per (market, position).
  - Per-opportunity yards sd per (market, position).
  - `K_share` and `K_rate[market]`, chosen from the fixed grid {0.5, 1, 2,
    4, 8, 16, 32} for share and {2, 5, 10, 25, 50, 100, 200} for rates, by
    fit-season CRPS. Share is chosen first (rates held at the grid's middle,
    25), then each rate separately, so the search is 7 + 7 x markets
    evaluations, not a product.

  **The reference arm** (also fitted only on fit seasons): v4's core baseline
  (`blend_averages` at 0.6, regressed to the position average over
  `MIN_BASELINE_GAMES`, no moneyline, DVP, usage or wind), with 27g's ratio
  quantiles per (market, position). Its CDF is read at every grid threshold,
  integers included, so expose a public `ratio_cdf` in
  `nfl_over_probability.py` rather than calling `over_probability`, which
  refuses integer lines. `over_probability` behaviour stays unchanged.

  *Done when:* synthetic tests prove the following:
  - No fit ever sees a season outside `fit_seasons`.
  - Grid ties resolve to the smaller K.
  - A group with fewer than 2 cases gets no fit and falls out of the cohort.
  - The existing `nfl_over_probability` tests still pass untouched.

- [x] **Step 6 - Rolling-origin scoring and the pre-registered rule.** In the
  same module:
  - `score_origin(cases, season)` fits both arms on 2018 to season-1 and
    scores that season's common cohort (both arms produce a distribution) on
    CRPS.
  - P(over) is scored at the common lines `synthetic_lines(reference
    projection)`, which are fixed by the reference arm, so they are the same
    for both arms.
  - `verdict(...)` applies the rule below, written as module constants with
    tests.

  Then stop for a pre-registration checkpoint commit before any scoring run.
  It needs the owner's yes, is cited by hash, and merges `--ff-only`, never
  squashed.

  *Done when:* synthetic tests prove the following:
  - The cohort is common to both arms.
  - Pairing is by (player, game, market).
  - Standard errors are clustered by game.
  - Each rule clause can fail on its own, and an insufficient season makes
    the verdict `insufficient`.
  - An empty season raises.

  The checkpoint commit exists and its hash is recorded here.

- [x] **Step 7 - CLI and report.** Add `app/backtest/nfl_volume_projection.py`.
  It loads 2018-2025 once, runs the five origins and prints, per market:
  - Cases, CRPS for both arms, the paired difference with its SE, and wins
    by season.
  - ECE, the worst bin and median share-below.
  - The verdict.

  It takes no arm, grid or season options. `--help` works without a
  database.

  *Done when:* report tests show every column and verdict wording. `--help`
  exits before any database import. The command refuses to write anything.

- [x] **Step 8 - Run once and freeze.** Run the CLI once and record the
  command, date, elapsed time, coverage, rookie exclusions and every table
  under Results. For each adopted market, freeze the final constants,
  refitted on 2018-2025, as `NFL_VOLUME_MODEL_VERSION = "nfl-volume-v1"` in
  the projection module, with a test pinning them. Markets not adopted are
  recorded as rejected and left out. If none adopt, record that and stop,
  without tuning and rerunning.

  *Done when:* the Results explain every verdict and the frozen constants
  match them. No production caller imports the new modules. v4 and Rec
  Targets versions are unchanged. The full Verify gate passes. Update the
  employer interview guide (local, ignored, never staged) from the measured
  result, calling it backtest-only.

## The pre-registered rule (locked in Step 6, before any score)

**Pre-registration commit:** `5b9531259278d93de1ba70b010cfe266c46cb875`
(2026-10-30), made before any scoring run. Merge it `--ff-only`, never
squashed, so this hash stays on `master`.

A market adopts `nfl-volume-v1` only if all of the following hold:

1. At least 300 common-cohort cases in each of the five scored seasons
   (2021-2025).
2. The pooled paired mean CRPS difference (volume minus reference) is below
   zero by more than 2 SE, clustered by game.
3. Volume's mean CRPS is lower in at least 4 of the 5 seasons.
4. The pooled calibration of volume's P(over) at the common lines passes 27g's
   thresholds: ECE <= 0.02, and no bin of 200 or more pairs off by more than
   0.05.
5. The pooled share of actuals below volume's median lies within 0.47-0.53.
   An actual exactly on the median counts as half, since counts often land
   on it.

Otherwise the verdict is `reject`, or `insufficient` when clause 1 fails.
Verdicts are final for `nfl-volume-v1`. 2025 is scored here as one of five
seasons; this counts as the 2025 holdout's ninth read, and clause 3 is what
stops one familiar season from carrying the verdict.

## Files / areas

- `api/app/ingest/nflverse.py`: comment fix, plus a parser fix only if an
  old file needs one.
- `api/app/core/nfl_over_probability.py`: public `ratio_cdf` only (Step 5)
- `api/app/core/outcome_distribution.py` (new, sport-neutral)
- `api/app/core/nfl_volume_projection.py` (new)
- `api/app/core/nfl_volume_backtest.py` (new)
- `api/app/repositories/nfl_volume.py` (new)
- `api/app/backtest/nfl_volume_projection.py` (new)
- `api/tests/test_outcome_distribution.py`,
  `test_nfl_volume_projection.py`, `test_nfl_volume_backtest.py`,
  `test_nfl_volume_repository.py`, `test_nfl_volume_harness.py` (new)

## Data / contracts

- **No schema change.** The backfill writes existing columns of
  `nfl_player_weekly_stats`, `nfl_player_snap_counts`,
  `nfl_player_weekly_rosters` and `sport_players`.
- **Load-bearing for 49b and 49c:** the distribution interface (`cdf`,
  `median`, `p_over(line)` returning over, under and push, and `crps`), and
  `NFL_VOLUME_MODEL_VERSION`. 49b blends `p_over` with the line, and 49c
  serves it, so these signatures must not change after Step 8.
- **Backtest inputs are closing lines,** while production will use
  pre-kickoff lines. Closing lines hold slightly more information, so the
  backtest flatters the team-volume term a little. Record this beside the
  Results, and 49b's forward check measures the real thing.

## Testing

The test gate is on. The pure modules from Steps 2, 3, 5 and 6 and the report
from Step 7 ship unit tests in the same diff, and the loader in Step 4 gets
recorded-SQL tests. No test touches the database or the network. Steps 1 and
8 are evidence steps, verified by recorded command output. The full Verify
command (`npm --prefix web run verify && cd api && python -m pytest`) is the
final gate.

## Notes for the AI

- `app/core/` stays pure. `outcome_distribution.py` must not import NFL code
  (as `nfl_over_probability.py` does not), so NBA and NHL can reuse it.
- Reuse what exists: `team_lines`, `blend_averages`, `PREVIOUS_SEASON_WEIGHT`,
  `MIN_BASELINE_GAMES`, `ratio_quantiles`, `over_probability`,
  `synthetic_lines`, `calibrate`, `REPLAY_MARKETS_BY_POSITION` and
  `ReplayCase`.
- Every backfill or ingest write to the shared Neon database needs the
  owner's yes in chat, one command at a time. Dry runs first.
- One scoring run. A transient DB failure may be retried with the identical
  configuration. Any substantive rerun is recorded with its reason, and it
  never changes the rule, grid, cohort or seasons.
- No em dashes in new content. Comment the why only.
- Windows: run Python from the API venv (`api/.venv`, which lives in the main
  checkout at `C:\dev\SportAppV2\api`), with the selector event loop for
  async CLIs.
- Invariant 11 (history floors, added 2026-10-30): 49a names its own floor,
  `VOLUME_FIRST_HISTORY_SEASON = 2018`, and every history read in
  `get_volume_history` bounds the season from below with it. The reference
  arm is built in pure code from those rows, never from v4's slate readers,
  which are floored at 2024 by `PROJECTION_FIRST_HISTORY_SEASON`.

- **Disclosed read (2026-10-30, Step 5a).** A mechanics check scored the
  reference arm alone on 2025 (mean CRPS per market, fit on 2018-2024). No
  volume-arm score and no comparison was read. The rule, grid, cohort and
  seasons were already fixed above and do not change. Later mechanics checks
  score fit seasons only.
- **Grids extended (2026-10-30, Step 5b, owner's yes).** The spec's grids
  were {2, 4, 8, 16, 32} for share and {10, 25, 50, 100, 200} for rates. A
  fit on 2018-2020 (fit seasons only, no scored season read) chose the
  smallest share K (2) and the smallest rate K for rushing yards and
  completions (10), so the optimum could lie below the grid. Both grids were
  extended downward before the pre-registration commit; no volume-arm score
  on a scored season had been read.
- **Step 5 is built in two reviewed parts:** 5a (cases, `ratio_cdf`, the
  shared CRPS grids and the reference arm) and 5b (the volume arm's fit and
  grid search).

## Results

### Step 1 - backfill (2026-10-29 and 2026-10-30)

21 approved writes ran 2026-10-29 17:34-21:15 UTC: stats, rosters and snaps
for 2018-2023 oldest first, then `nflverse --season` reruns for 2024-2026.
All exited 0. No migration ran (the database's `0051` is the tennis ELO v2
migration from another branch).

| Season | Player-weeks | Non-null targets / target share | Snap rows | Roster rows |
|---|---|---|---|---|
| 2018 | 16,711 | 16,711 / 16,711 | 6,467 | 33,905 |
| 2019 | 16,646 | 16,646 / 16,646 | 6,454 | 37,878 |
| 2020 | 16,757 | 16,757 / 16,757 | 6,646 | 36,938 |
| 2021 | 18,110 | 18,110 / 18,110 | 7,101 | 40,179 |
| 2022 | 17,963 | 17,963 / 17,963 | 7,015 | 39,798 |
| 2023 | 17,788 | 17,788 / 17,788 | 7,012 | 39,602 |
| 2024 | 18,112 | 18,112 / 18,112 | 6,973 | 35,974 |
| 2025 | 18,522 | 18,522 / 18,522 | 6,981 | 37,555 |

- **Raiders 2018-2019.** The first pass skipped Oakland rows in rosters and
  snaps as `unknown teams ['OAK']`. Both parsers now map relocated codes
  through `franchise_code`, with a test each, and the 2018-2019 rosters and
  snaps were rerun with approval on 2026-10-30 (Raiders snaps 210 and 206,
  rosters 1,106 and 1,227, in line with 2020-2021).
- **v4 leak found and fixed.** The first post-backfill 2025 replay of
  `nfl_projections --arms production` did not match: v4's opponent, league
  and player baselines read every stored season with no floor (QB passing
  yards went from 582 to 600 cases, bias +2.72 to +5.47). Fixed on master by
  `07c66950` and `df80d3bb` (floor at 2024), now invariant 11.
- **Done-when met (2026-10-30).** After syncing to `df80d3bb`, the 2025
  replay (`nfl_projections --season 2025 --arms production`) is
  byte-identical to the pre-backfill output (`cmp` reports no difference).
  Verify passes: web typecheck, tests and build, then 5,084 API tests.

### Step 8 - the scoring run (2026-10-30)

**Command:** `python -m app.backtest.nfl_volume_projection` from `api/`, API
venv, code at `3486fe6c`. Started 16:10:53 UTC, ended 17:18:44 UTC, exit 0,
elapsed 4,069 s. Run once; no retry or rerun.

**Coverage:** 45,693 player-games and 4,254 team-games for 2018-2025; all
45,693 had closing lines and team attempts and became cases.

**Origins** (each fitted on 2018 to the season before):

| Season | Pairs | k_share | k_rate |
|---|---|---|---|
| 2021 | 15,357 | 0.5 | completions 2, passing yards 200, receiving yards 50, receptions 50, rushing yards 10 |
| 2022 | 15,388 | 0.5 | completions 2, passing yards 200, receiving yards 50, receptions 50, rushing yards 10 |
| 2023 | 15,332 | 0.5 | completions 5, passing yards 200, receiving yards 50, receptions 25, rushing yards 10 |
| 2024 | 15,385 | 0.5 | completions 10, passing yards 200, receiving yards 50, receptions 25, rushing yards 10 |
| 2025 | 15,758 | 0.5 | completions 25, passing yards 200, receiving yards 50, receptions 25, rushing yards 10 |

`k_share` sat at the extended grid's floor (0.5) at every origin and in the
final refit, so a smaller K might fit better still. The rule allows no
further search for `nfl-volume-v1`; this is a candidate for a later version.

**Exclusions** from the common cohort, per season 2021 / 2022 / 2023 / 2024
/ 2025, as no volume forecast | no reference forecast. The report counts
every volume skip under one reason, so rookies with no NFL history are
inside the first number, not counted separately.

| Market | No volume forecast | No reference forecast |
|---|---|---|
| passing_attempts, completions, yards (each) | 20 / 16 / 18 / 15 / 18 | 1 / 0 / 0 / 1 / 0 |
| receiving_yards | 145 / 120 / 120 / 135 / 139 | 94 / 107 / 69 / 116 / 154 |
| receptions | 145 / 120 / 120 / 135 / 139 | 82 / 105 / 67 / 116 / 150 |
| rushing_attempts | 42 / 39 / 34 / 40 / 45 | 41 / 35 / 18 / 45 / 21 |
| rushing_yards | 62 / 55 / 52 / 55 / 63 | 53 / 49 / 36 / 57 / 39 |

**Common-cohort cases:**

| Market | 2021 | 2022 | 2023 | 2024 | 2025 | Pooled |
|---|---|---|---|---|---|---|
| passing_attempts | 634 | 617 | 645 | 648 | 646 | 3,190 |
| passing_completions | 634 | 617 | 645 | 648 | 646 | 3,190 |
| passing_yards | 634 | 617 | 645 | 648 | 646 | 3,190 |
| receiving_yards | 4,972 | 4,948 | 4,949 | 4,949 | 5,080 | 24,898 |
| receptions | 4,984 | 4,950 | 4,951 | 4,949 | 5,084 | 24,918 |
| rushing_attempts | 1,438 | 1,518 | 1,435 | 1,453 | 1,514 | 7,358 |
| rushing_yards | 2,061 | 2,121 | 2,062 | 2,090 | 2,142 | 10,476 |

**CRPS, calibration and verdicts** (difference is volume minus reference, SE
clustered by game; ECE and worst bin are volume's P(over) at the reference
arm's synthetic lines):

| Market | Volume | Ref | Diff | SE | Won | ECE | Worst bin | Below median | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| passing_attempts | 6.533 | 7.116 | -0.584 | 0.041 | 5/5 | 0.0287 | 0.0791 | 0.482 | reject (calibration) |
| passing_completions | 4.389 | 4.960 | -0.571 | 0.027 | 5/5 | 0.0298 | 0.0685 | 0.482 | reject (calibration) |
| passing_yards | 50.533 | 51.695 | -1.162 | 0.286 | 5/5 | 0.0229 | 0.0452 | 0.497 | reject (calibration) |
| receiving_yards | 11.717 | 12.471 | -0.753 | 0.021 | 5/5 | 0.0483 | 0.0624 | 0.533 | reject (calibration, median) |
| receptions | 0.910 | 1.027 | -0.117 | 0.002 | 5/5 | 0.0184 | 0.0317 | 0.503 | **adopt** |
| rushing_attempts | 2.708 | 2.951 | -0.243 | 0.009 | 5/5 | 0.0316 | 0.0856 | 0.526 | reject (calibration) |
| rushing_yards | 12.581 | 13.490 | -0.909 | 0.033 | 5/5 | 0.0412 | 0.0663 | 0.541 | reject (calibration, median) |

- **Why the verdicts fall as they do.** Volume beats the reference on CRPS
  in every market and every season, by 4 to 58 SE, so clauses 1 to 3 hold
  everywhere. Clause 4 decides six markets: their P(over) misses the 0.02
  ECE limit, and the worst large bin is off by more than 0.05 in five of
  them (passing yards' is 0.045, inside the limit, but its ECE is 0.0229).
  Receiving and rushing yards also put too many actuals below the median
  (0.533 and 0.541), so their medians run high. Receptions passes all five
  clauses. Better CRPS did not mean calibrated probabilities.
- **Closing lines.** Team volume used each game's closing spread and total;
  production will use pre-kickoff lines, so these results flatter the
  team-volume term slightly. 49b's forward check measures the real thing.
- **Holdout.** This run counts as the 2025 holdout's ninth read, as
  disclosed in the rule.

**Freeze.** Receptions only. `NFL_VOLUME_MODEL_VERSION = "nfl-volume-v1"`,
`NFL_VOLUME_V1_MARKETS = ("receptions",)` and `NFL_VOLUME_V1_PARAMETERS` in
`app/core/nfl_volume_projection.py`, refitted on 2018-2025 by `fit_volume`
(a read-only helper outside `api/`, 1,312 s). It holds only the receptions
constants, so `project_player` returns `NO_FIT` for the six rejected markets
and for QBs. `test_nfl_volume_projection.py` pins every value.

| Constant | Frozen value |
|---|---|
| pass volume | 18.6642 + 0.66962 x team total - 0.32766 x margin |
| previous-season weight | 0.6 |
| k_share | 0.5 (share CRPS 1,037,215 at 0.5, rising to 1,183,793 at 32) |
| k_rate receptions | 25 (receptions CRPS 35,788 at 25; 35,795 at 50, 35,815 at 10) |
| target share prior | RB 0.06316, TE 0.09266, WR 0.12637 |
| catch rate prior | RB 0.77328, TE 0.69679, WR 0.63174 |
| dispersion | RB 4.638, TE 9.686, WR 9.386 |

The rush volume fit is also stored (32.4812 - 0.25512 x total + 0.35283 x
margin) but unused while no rush market is adopted.

**Checks.** No production caller imports the 49a modules (only they import
each other). v4 (`opponent-dvp-tg-blend-usage-snap-v4`) and Rec Targets
(`nfl-targets-v1`) are unchanged against `master`.

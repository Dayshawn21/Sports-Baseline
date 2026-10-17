# Feature: PrizePicks fantasy scoring

**From build-plan:** feature 27f
**Status:** complete (fantasy settled on PrizePicks points; the projection change not adopted)

## Goal

Score NFL fantasy points the way PrizePicks settles them, not with NFLverse PPR.
Store the scoring components, compute PrizePicks points in one pure function,
settle and grade fantasy lines on that number, and score a projection built
from it through the 27b harness on 2025. The projection is adopted only if it
passes the pre-registered rule.

**What is wrong today:**
- `nfl_player_weekly_stats.fantasy_points` is NFLverse `fantasy_points_ppr`.
  Baselines, DVP, the replay actual and 27a's settlement all read it.
- **The formulas differ in three places.** Checked on 2026-09-26 against
  [PrizePicks' own scoring table](https://www.prizepicks.com/playbook-article/how-to-play-prizepicks-nfl-fantasy-scoring-system)
  (dated 2025-09-17):

  | Stat | NFLverse PPR | PrizePicks |
  |---|---|---|
  | Interception | -2 | -1 |
  | Fumble lost | -2 | -1 |
  | Offensive fumble-recovery TD | 0 | +6 |

  Everything else matches: 0.04 per passing yard, 4 per passing TD, 0.1 per
  rushing or receiving yard, 6 per rushing or receiving TD, 1 per reception, 2
  per two-point conversion, and 6 per return TD.
- **Third-party calculators disagree** (one says half-PPR with -2 INT). PrizePicks'
  own page is the source; a comment in the formula links it.
- **The size of the gap.** On the 2025 NFLverse file, the components reproduce
  `fantasy_points_ppr` on all 18,540 REG rows. PrizePicks points differ on 429 of
  them: 322 QB, 60 RB, 30 WR, 17 TE. So this is mostly a QB change of about
  +1 point per interception or lost fumble.
- **Components are not stored.** `touchdowns` holds rushing plus receiving TDs
  only. Passing TDs, interceptions, fumbles lost, two-point conversions, return
  TDs and fumble-recovery TDs are not stored.

## In scope

- **Store the components** (migration `0036`) from the NFLverse weekly file, plus
  the derived `prizepicks_fantasy_points`, and backfill 2024 to 2026 by
  re-running the existing ingest.
- **One pure formula module:** PrizePicks points, plus NFLverse PPR from the same
  components as a reconciliation check.
- **Settle on PrizePicks points.** 27a's grading and the 27b harness actual for
  the fantasy market both switch to the new column. This is a measurement fix,
  not a model change, so it ships whether or not the projection is adopted.
- **PrizePicks averages beside NFLverse ones** on slate and replay rows, with no
  behavior change.
- **A `prizepicks_fantasy` harness arm,** stacked on production.
- **One scored run on 2025,** with the verdict under Results.
- **Conditional adoption** (Step 6): the slate projects fantasy from PrizePicks
  averages, the evidence panel shows PrizePicks points, and the model version is
  bumped. If rejected, Step 6 is skipped and production is unchanged.

## Out of scope

- **Kicker fantasy scoring** (field goals by distance, PATs). Kickers are not
  a rated position.
- **Team-game DVP inputs** (`get_team_game_position_totals`). They keep NFLverse
  PPR: 27c rejected team-game DVP for fantasy, so production never reads them for
  this market.
- **Retuning** anything else in the fantasy projection (season blend, moneyline,
  usage), or a second variant. Each extra arm spends the 2025 holdout again.
- **The ESPN path** (`app/ingest/espn_nfl.py`, `ppr_fantasy_points`). It is not
  on the slate's data path.
- Over probability (27g) and ranking (27h).

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at
   the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Components and the formula (pure + parser).**
  - `app/core/nfl_fantasy.py` gains:
    - `NflFantasyComponents` (frozen dataclass): passing yards and TDs,
      interceptions, rushing and receiving yards, scoring `touchdowns` (rushing
      plus receiving), receptions, fumbles lost, two-point conversions, return
      TDs, fumble-recovery TDs.
    - `prizepicks_fantasy_points(c) -> float` and
      `nflverse_ppr_points(c) -> float`, both rounded to 2 places. The
      PrizePicks one carries a one-line comment with the source URL and date.
  - `parse_player_stats` reads the new NFLverse columns into
    `NflversePlayerWeek`:
    - `passing_tds`, `passing_interceptions`
    - `fumbles_lost`: the sum of `sack_fumbles_lost`, `rushing_fumbles_lost`
      and `receiving_fumbles_lost`
    - `two_point_conversions`: passing plus rushing plus receiving
    - `special_teams_tds`, `fumble_recovery_tds`

    It then sets `prizepicks_fantasy_points` from the formula. Blank columns
    read as None, never 0; the derived value is None if any input it needs is
    None.

  *Done when:* unit tests show:
  - a QB week with 1 interception and 1 lost fumble scores 2 points more under
    PrizePicks than under PPR
  - a fumble-recovery TD adds 6 under PrizePicks only
  - `nflverse_ppr_points` matches `fantasy_points_ppr` on a fixture row copied
    from the 2025 file
  - a blank component column parses as None
- [x] **Step 2 - Store and backfill.**
  - Migration `0036`: nullable columns on `nfl_player_weekly_stats`:
    - `passing_tds`, `interceptions`, `fumbles_lost`, `two_point_conversions`,
      `return_tds`, `fumble_recovery_tds` (smallint)
    - `prizepicks_fantasy_points` (double precision)
  - The weekly-stats upsert in `app/repositories/nfl.py` writes and updates them.
  - Backfill: `python -m app.ingest.nflverse --season 2024`, then 2025 and 2026.

  *Done when:*
  - `alembic upgrade head` and `alembic downgrade -1` both run clean.
  - After the backfill, a SQL check records under Results, per season:
    - every row has `prizepicks_fantasy_points`
    - the PPR recomputed from the stored components matches `fantasy_points`
      within 0.011 on every row
    - the count of rows where the two formulas differ, by position
  - `pytest` passes.
- [x] **Step 3 - Settle fantasy lines on PrizePicks points.**
  - `STAT_COLUMN_BY_MARKET[FANTASY_POINTS]` in `app/core/nfl_line_grading.py`
    becomes `prizepicks_fantasy_points`, and `_GRADED_STAT_COLUMNS` adds it.
    This one map drives 27a settlement, the 27b replay actual, and the 27e fit
    samples.
  - Drop the "settle on NFLverse PPR" caveat from
    `app/backtest/nfl_prizepicks_lines.py`.

  *Done when:*
  - A grading test settles a QB fantasy line on PrizePicks points: 1
    interception flips a line that PPR would have settled UNDER.
  - `python -m app.backtest.nfl_prizepicks_lines` re-runs, and Results records
    the fantasy rows before and after (line count, over rate, model hit rate).
- [x] **Step 4 - PrizePicks averages on rows (no behavior change).**
  - In `app/repositories/nfl.py`:
    - `_BASELINES_CTE` adds `AVG(s.prizepicks_fantasy_points) AS
      prizepicks_fantasy_points` to all four aggregates.
    - `_slate_line_rows` selects them with the `player_`, `position_`,
      `opponent_` and `league_` prefixes.
    - `_averages` and `_EMPTY_AVERAGES` add the `prizepicks_fantasy_points`
      key.
  - Player history is left alone here: it reaches the slate JSON, so it
    changes only on adoption (Step 6).
  - `NflHistoricalAverages` gains `prizepicks_fantasy_points: float | None =
    None`, because `_slate_line` builds it with `**row["averages"]` and would
    reject an unknown key. The projection never reads it.

  *Built:* `/nfl/slate` for 2026 weeks 2 and 3 (`build_slate`, fixed `now`) is
  byte-identical before and after: SHA-256 `3790d1b0...` (week 2) and
  `42faa634...` (week 3).

  *Done when:*
  - A repository test shows a line whose `averages`, `position_averages`,
    `opponent_averages` and `league_position_averages` carry both keys.
  - `/nfl/slate` JSON for 2026 weeks 2 and 3 is byte-identical (SHA-256) before
    and after.
- [x] **Step 5 - The transform, the arm, and the 2025 score.**
  - `apply_prizepicks_fantasy(row) -> dict` in `app/core/nfl_fantasy.py`. On a
    `fantasy_points` row only, it copies `prizepicks_fantasy_points` over
    `fantasy_points` in:
    - `averages`, `position_averages`, `opponent_averages`,
      `league_position_averages`
    - every `baseline_seasons` entry's `averages` and `position_averages`

    Other markets pass through untouched. The row is not mutated.
  - `ARMS["prizepicks_fantasy"]` is `_production(apply_prizepicks_fantasy(row),
    season)`. The default `--arms` becomes `production,prizepicks_fantasy`.
  - Run `python -m app.backtest.nfl_projections` once.

  *Done when:*
  - A harness test shows a QB fantasy row projecting higher under the arm when
    its baseline had interceptions, and a receiving row unchanged.
  - The 2025 run completes for weeks 1-18.
  - Results holds the paired table, the fantasy verdict, the per-phase read, a
    per-position read (QB, RB, WR, TE; information only, not a verdict), and the
    unpaired counts.
  - Results notes that this is the **fifth use of the 2025 holdout**, and that
    earlier fantasy MAEs (27b to 27e) were scored against NFLverse PPR, so they
    are not comparable to this run's.
  - If the verdict is `reject`, Step 6 is marked skipped with the reason.
- [x] **Step 6 - Adopt (only on `adopt`).** *Skipped:* Step 5's verdict is
  `reject` (MAE +0.20%, about 2 SE worse), so production is unchanged. The
  transform and the arm stay as the record, and the harness default arms go
  back to `production,game_environment`.
  - The slate transform chain becomes `apply_prizepicks_fantasy`, then
    `apply_team_game_dvp`, then `apply_season_blend`, in
    `app/services/nfl/slate.py` and the harness `_production`.
  - `ARMS["prizepicks_fantasy"]` stays as the record, now equal to production.
  - `get_slate_player_history` serves `prizepicks_fantasy_points` as the
    fantasy value, so the evidence panel's recent form matches the line it
    settles on.
  - Bump `NFL_PROJECTION_MODEL_VERSION` to
    `opponent-dvp-tg-blend-usage-snap-v5`.

  *Done when:*
  - A slate test shows a QB fantasy line projected from PrizePicks averages.
  - Re-running the harness `production` arm reproduces Step 5's
    `prizepicks_fantasy` fantasy MAE.
  - `/nfl/slate` for 2026 week 3 returns 200 with the new version.

## Files / areas

- `api/app/core/nfl_fantasy.py` - components, both formulas, the transform.
- `api/app/ingest/nflverse.py` - parse the components.
- `api/app/db/migrations/versions/0036_nfl_fantasy_components.py` (new).
- `api/app/repositories/nfl.py` - upsert, baseline CTEs, row shaping, and
  player history (Step 6 only).
- `api/app/core/nfl_line_grading.py` - the fantasy settlement column.
- `api/app/backtest/nfl_prizepicks_lines.py` - drop the caveat.
- `api/app/backtest/nfl_projections.py` - the arm; `_production` on adoption.
- `api/app/services/nfl/slate.py` - the transform chain (Step 6 only).
- `api/app/core/nfl_projection.py` - version bump (Step 6 only).
- Tests: `test_nfl_fantasy.py`, `test_nflverse.py`, `test_nfl_line_grading.py`,
  `test_nfl_repository.py`, `test_nfl_projection_harness.py`,
  `test_nfl_projection.py` (Step 6).

## Data / contracts

Migration `0036` on `nfl_player_weekly_stats`, all nullable. NULL means not
loaded, never zero, as with the other stat columns.

| Column | Type | NFLverse source |
|---|---|---|
| `passing_tds` | smallint | `passing_tds` |
| `interceptions` | smallint | `passing_interceptions` |
| `fumbles_lost` | smallint | sack + rushing + receiving `*_fumbles_lost` |
| `two_point_conversions` | smallint | passing + rushing + receiving `*_2pt_conversions` |
| `return_tds` | smallint | `special_teams_tds` |
| `fumble_recovery_tds` | smallint | `fumble_recovery_tds` |
| `prizepicks_fantasy_points` | double | computed at ingest |

**Load-bearing:**
- **The formula lives only in `prizepicks_fantasy_points`** in
  `app/core/nfl_fantasy.py`. SQL averages the stored column and never recomputes
  it. A PrizePicks scoring change means a code change plus a re-ingest.
- **`fantasy_points` keeps its meaning** (NFLverse PPR). PrizePicks points always
  travel under the `prizepicks_fantasy_points` key.
- **Fantasy settlement is PrizePicks points** from Step 3 on, for 27a, 27b, and
  later 27g calibration.
- **Transform order,** if adopted: `apply_prizepicks_fantasy`, then
  `apply_team_game_dvp`, then `apply_season_blend`, then (arm only)
  `apply_game_environment`.

**The rule is 27b's, unchanged:** at least 300 paired cases, MAE at least 1.0%
lower, and the paired difference below zero by more than 2 SE, for the
`fantasy_points` market.

## Testing

- The test gate is on:
  - Step 1 ships formula and parser tests.
  - Step 2 ships the migration round trip and the reconciliation SQL.
  - Step 3 ships a grading test.
  - Step 4 ships a repository test and the byte-identical slate check.
  - Step 5 ships a harness test.
  - Step 6 ships a slate test.
- No web change is expected: the market label stays "Fantasy Score". If Step 6
  touches the evidence panel's types, it needs `npm run build` and a screenshot.
- Run with `cd api && .venv\Scripts\python.exe -m pytest`.

## Notes for the AI

- **A reject is a live outcome.** 27b found every market leaning OVER. The
  variant raises QB projections by about 1 point per interception or lost
  fumble, which may move projections the wrong way for MAE even though the
  target is now right. Record whatever the run says. Steps 1-4 ship either
  way, because settling on the right formula is correct regardless.
- **The fantasy-market MAE shifts at Step 3** for every arm, because the actual
  changes. Do not compare Step 5's numbers with the 27e archive's fantasy rows.
- **The 27e fit** also reads `STAT_COLUMN_BY_MARKET`. Its frozen fantasy slopes
  are zero and stay as recorded; do not re-run it.
- **Backfill uses the existing ingest,** which upserts on (`player_id`,
  `game_id`). It spends no quota (NFLverse is public). The local `ingest_daily`
  task also writes to this database, so run the backfill from this branch once
  Step 2's migration is applied.
- Use `from __future__ import annotations`, `X | None`, and no `Any`, and keep
  `app/core/` free of I/O.
- No em dashes in code comments, docs, or commit messages.

## Results

### Step 2 - backfill and reconciliation

Run 2026-09-26: migration `0036` upgraded, downgraded and re-upgraded clean,
then `python -m app.ingest.nflverse --season 2024`, 2025 and 2026 (about 10
minutes a season; the ingest upserts row by row).

**Every row has PrizePicks points, and the stored components rebuild NFLverse
PPR within 0.011 on every row,** so no scoring component is missing.

| Season | Rows | With PrizePicks points | PPR rebuilt | Differ: QB | RB | WR | TE | Other |
|---|---|---|---|---|---|---|---|---|
| 2024 | 18,112 | 18,112 | 18,112 | 325 | 66 | 34 | 20 | 20 |
| 2025 | 18,522 | 18,522 | 18,522 | 322 | 61 | 31 | 17 | 16 |
| 2026 | 2,291 | 2,291 | 2,291 | 38 | 12 | 5 | 1 | 2 |

About 2.5% of player-games differ between the two formulas, three quarters of
them QB weeks. "Other" is non-skill positions (fumble returns, fake punts), which
are not rated.

### Step 3 - fantasy settled on PrizePicks points

Run 2026-09-26, `python -m app.backtest.nfl_prizepicks_lines` (2026, model
`opponent-dvp-tg-blend-usage-snap-v4`) before and after the switch. **Only fantasy
rows moved,** and only slightly: the lines are the same, and a few QB weeks
with interceptions or lost fumbles gain a point and cross the line.

| Fantasy row | Lines | Before (PPR) | After (PrizePicks) |
|---|---|---|---|
| demon, over rate | 203 | 23.9% (2 push) | 24.3% (1 push) |
| goblin, over rate | 201 | 62.6% | 63.6% |
| standard, over rate | 218 | 41.7% | 43.1% |
| model hit rate, fantasy calls | 203 | 50.7% | 51.7% |
| model hit rate, all calls | 751 | 47.7% | 47.9% |

The model's fantasy hit rate is still well under the 57.7% Power break-even,
so settling on the right formula does not rescue the market. The caveat line
is gone from the report.

### Step 5 - the 2025 score

Run 2026-09-26 on 2025 REG weeks 1-18: `production` against
`prizepicks_fantasy`, both scored against PrizePicks points (Step 3). **This is
the fifth use of the 2025 holdout,** after F-02 (27b), 27c, 27d and 27e.
Fantasy MAEs in the 27b to 27e archives were scored against NFLverse PPR and are
not comparable with these.

**Verdict: reject.** The variant is slightly worse, and the seven other markets
are identical, as they should be.

| Market | Paired n | Prod MAE | Var MAE | Change | Diff / SE | Verdict |
|---|---|---|---|---|---|---|
| fantasy points | 5,371 | 4.603 | 4.613 | +0.20% | +0.009 / 0.004 | reject |

By position (arm metrics, information only):

| Position | n | Prod MAE / bias | Var MAE / bias |
|---|---|---|---|
| QB | 568 | 6.68 / -0.20 | 6.73 / +0.58 |
| RB | 1,395 | 4.59 / -0.03 | 4.60 / +0.02 |
| WR | 2,248 | 4.54 / +0.38 | 4.54 / +0.40 |
| TE | 1,160 | 3.73 / -0.07 | 3.73 / -0.05 |

Paired breakdown (fantasy only, one scratch replay of the same weeks; the
scored set matches: 5,371 paired, none unpaired):

| Group | n | Prod MAE | Var MAE | Change | Diff / SE |
|---|---|---|---|---|---|
| weeks 1-4 | 1,094 | 4.813 | 4.832 | +0.39% | +0.019 / 0.009 |
| weeks 5-10 | 1,711 | 4.650 | 4.651 | +0.02% | +0.001 / 0.007 |
| weeks 11-18 | 2,566 | 4.483 | 4.493 | +0.22% | +0.010 / 0.006 |
| QB | 568 | 6.677 | 6.726 | +0.73% | +0.049 / 0.037 |
| RB | 1,395 | 4.591 | 4.600 | +0.18% | +0.008 / 0.003 |
| WR | 2,248 | 4.538 | 4.540 | +0.04% | +0.002 / 0.001 |
| TE | 1,160 | 3.729 | 3.734 | +0.11% | +0.004 / 0.002 |

**No phase or position improves,** so the reject does not hide a subgroup gain.

**Reading it:**
- **The right target exposes an existing OVER lean.** Against PrizePicks
  actuals, production's QB fantasy projection is only 0.20 low: NFLverse's
  heavier interception charge was offsetting a baseline that already runs high.
  Switching the baseline to PrizePicks points adds about +0.8 a game and
  overshoots to +0.58.
- **RB, WR and TE barely move.** Few of their weeks differ between the formulas
  (Step 2).
- **Nothing to tune here.** A skewed stat's mean sits above its median. That
  is 27g's problem (a distribution around the projection), not a scoring-formula
  one.
- **What ships:** stored components, fantasy settlement on PrizePicks points for
  27a, 27b and later 27g, and PrizePicks averages on slate rows. The served
  projection and `NFL_PROJECTION_MODEL_VERSION` are unchanged.


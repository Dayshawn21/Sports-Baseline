# Feature 24c: Team efficiency ratings

**From build-plan:** feature 24c
**Status:** completed (2026-09-19)

## Final outcome

Both efficiency arms were rejected by the pre-registered rule on the 2022-2025
holdout: totals (adjusted MAE 10.2077 vs closing 10.1891; 0.5-point picks
48.7%) and spreads (adjusted MAE 9.5138 vs 9.4945; 0.5-point picks 41.4%).
Per-team, per-game offensive plays, summed EPA, and successes are now stored in
`nfl_team_game_efficiency` (migration `0032`) for every final regular-season
game 2012-2026 and refreshed by the Tuesday cron. 24d may show efficiency as
team context only. The 2022-2025 holdout has now been scored for 24b, 24e, and
24c; later signals should be confirmed on 2026 onward.

## Goal

Store per-team, per-game offensive EPA, success, and play counts from NFLverse
play-by-play for 2012-2026, turn them into pre-game team efficiency ratings,
and test whether those ratings explain where NFL closing spreads and totals
miss on the 2022-2025 holdout. Like 24e, the question is whether efficiency
adds anything *beyond the market*, so the arm adjusts the closing line rather
than building a standalone line.

## In scope

- A play-by-play parser that reduces each season file to one offensive row per
  team per regular-season game: plays, summed EPA, and successful plays.
- A new `nfl_team_game_efficiency` table (migration `0032`), a writer, a
  standalone ingest command with a season-range backfill, and a step in the
  Tuesday `nfl-ingest.yml` cron.
- Pure pre-game efficiency ratings in `core/`: offense and defense offsets for
  EPA per play, success rate, and plays, replayed with the same leakage
  contract as the 24b scoring ratings.
- An `efficiency` arm in the game-line backtest: fit the closing line's
  residual on efficiency features over 2014-2021 with no intercept, score
  2022-2025 once, report, and apply the rule below.
- A recorded decision.

## Out of scope

- Live use of any adopted adjustment, and slate display (24d).
- Combining efficiency with ELO, the scoring rating, or 24e context in one fit.
  One signal family per arm keeps the verdict attributable.
- Garbage-time, neutral-situation, pass/rush, or opponent-adjusted splits
  beyond what the rating replay does. One play definition is fixed below;
  alternatives would be forking paths on a reused holdout.
- Seconds-per-play pace. Pace here is offensive plays per game.
- Moneyline. Efficiency is tested through spread and total only.
- Refactoring `core/nfl_scoring_ratings.py` onto the new replay. Its 24b
  output is recorded; consolidation can be a later cleanup.
- Retuning any 24b or 24e grid, coefficient, or verdict.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Parse team efficiency.** New
  `app/ingest/nflverse_team_efficiency.py` with
  `parse_team_efficiency(lines, season) -> list[NflverseTeamEfficiency]`, one
  row per (game, offense) using the play rules below. `is_home` comes from
  `posteam == home_team`, so no team-code mapping is needed.
  *Done when:* parser tests cover a run and a pass counting, a sack and a
  scramble counting as plays, `no_play`, kneel, spike, two-point, punt, and
  blank-EPA rows excluded, success as `epa > 0` (zero is not a success), a
  postseason row ignored, and both teams of one game producing separate rows.

- [x] **Step 2 - Table and writer.** Migration `0032` creates
  `nfl_team_game_efficiency` (contract below). Repository
  `replace_team_efficiency(db, season_rows)` deletes rows for the file's games
  and inserts the parsed rows, resolving `team_id` from the game's home or
  away side. Games missing from `nfl_games` or not yet final are skipped and
  counted.
  *Done when:* the migration round-trips, and a repository test in the
  `test_nfl_repository.py` style pins the delete scope, the home/away team
  resolution, and the final-game filter.

- [x] **Step 3 - Ingest command, backfill, cron.** `run(season, dry_run)` and a
  CLI with `--season`, `--through-season`, and `--dry-run`, fetching through
  the existing `play_by_play_url` with the 19j streaming-gzip pattern. Run
  `python -m app.ingest.nflverse_team_efficiency --season 2012 --through-season 2026`.
  Add a "Load current-season team efficiency" step to `nfl-ingest.yml` after
  the stats load.
  *Done when:* the backfill stores exactly 7,326 rows for the 3,663 final
  regular-season games of 2012-2025 (two per game), plus two per final 2026
  game (34 today); each season's league EPA per play is within ±0.05 and
  plays per team-game is between 55 and 70; a rerun leaves the row count and
  a hash of every column except `id` and `fetched_at` unchanged; and a
  mocked-httpx fetch test (as in `test_nflverse_pbp.py`) covers parsing a
  gzipped body and the 404 `SeasonNotPublished` path.

- [x] **Step 4 - Pure efficiency ratings.** `app/core/nfl_efficiency_ratings.py`:
  a replay over the ordered games and a per-(game, team) metric map that
  yields each game's pre-game expected home and away value, as league average
  plus the team's offense offset plus the opponent's defense offset. Same
  contract as `nfl_scoring_ratings.replay`: ratings read only earlier games,
  the league average reads only earlier weeks, offsets regress by 1/3 between
  seasons, and a game with no metric (unplayed or not loaded) still gets a
  prediction but updates nothing.
  *Done when:* tests cover the update direction for offense and defense,
  season regression, a missing metric, two games in the same week that cannot
  see each other's results in the league average, and that each team-game
  counts once in the league average regardless of its play count.

- [x] **Step 5 - Generalize the residual arm.** Refactor
  `app/backtest/nfl_game_context.py` so fitting, scoring, and the report take
  each arm's feature names and a case-to-vector function instead of reading
  `total_features` and `spread_features` directly. No behavior change.
  *Done when:* existing 24e tests pass unchanged, and
  `python -m app.backtest.nfl_game_lines --signal context --dry-run-fit`
  prints exactly the coefficients recorded in the 24e decision.

- [x] **Step 6 - Efficiency features and rate fit.** Repository
  `get_team_efficiency(db)` returns the stored rows keyed by
  (`game_key`, `is_home`). New `app/backtest/nfl_game_efficiency.py`: on
  2014-2021 only, choose each metric's learning rate from the grid by its
  next-game MAE (predicted versus actual team-game value, never against the
  market), then build each game's spread and total feature vectors from the
  replay. Refuse to run, naming the games, if any final 2012-2025 regular-season
  game lacks either efficiency row.
  *Done when:* the repository test pins the key and the regular-season filter;
  feature tests pin the signs (a better home offense raises `epa_edge`, a
  faster pair raises `pace`, two average teams give all zeros); the coverage
  guard has a test; and chosen rates do not change when every holdout
  efficiency row is altered.

- [x] **Step 7 - Efficiency arm: fit, score, report.** Fit
  `actual - closing line` per arm with `LinearRegression(fit_intercept=False)`
  through the Step 5 helpers, score 2022-2025 once with the 24e table and
  thresholds, and wire `--signal efficiency` into
  `app/backtest/nfl_game_lines.py`; `--dry-run-fit` prints rates and
  coefficients only.
  *Done when:* a test proves coefficients do not change when every holdout
  outcome and every holdout efficiency row is altered, and the arm's verdict
  goes through the existing 24e rule (`context_adopted`), not a copy.

- [x] **Step 8 - Run once and record the decision.** Run
  `python -m app.backtest.nfl_game_lines --signal efficiency` a single time and
  record the output and per-arm verdicts under **Decision**.
  *Done when:* the output and verdicts are recorded, with no change to play
  rules, grids, features, thresholds, or the rule after the holdout is seen.

## Play rules

Fixed now. One definition, no alternatives tried.

| Rule | Value |
|---|---|
| Season | `season` equals the file season and `season_type` is `REG` |
| Play | `play_type` is `run` or `pass` (sacks and scrambles are `pass`) |
| Excluded | `two_point_attempt` is 1; `posteam` or `epa` blank; every other `play_type` (`no_play`, `qb_kneel`, `qb_spike`, special teams) |
| Offense | `posteam`; home when `posteam == home_team` |
| Success | `epa > 0`, computed here (NFLverse's own definition) |
| Stored | `plays`, summed `epa`, `successes` per (game, offense) |

No garbage-time filter. Blowout plays add noise to the ratings, but choosing a
win-probability cutoff is a tunable the holdout would then have to absorb.

## Ratings and features

Per metric, each team has an offense offset and a defense offset (value above
league average produced, and allowed). Pre-game, for each side:

`expected = league + offense[team] + defense[opponent]`

| Metric | Team-game value |
|---|---|
| EPA per play | `epa / plays` |
| Success rate | `successes / plays` |
| Plays | `plays` |

Grids and constants (fixed): learning rate 0.05, 0.1, 0.15, 0.2, fitted per
metric on 2014-2021 next-game MAE; season regression 1/3; league window one
season of team-games (544). Features use offsets only (expected minus
league), so a league-wide trend cannot pass for signal:

| Arm | Features |
|---|---|
| Spread | `epa_edge` = home minus away expected EPA per play; `success_edge` = same for success rate |
| Total | `epa_sum` = home plus away expected EPA per play; `success_sum`; `pace` = home plus away expected plays |

All offsets, so each is 0 for two average teams.

## Pre-registered adoption rule

Fixed now, before any holdout number exists. Fit 2014-2021, holdout 2022-2025.
Same rule, thresholds, and report as 24e.

| Arm | Adjusted line | Adopted only if, on the holdout |
|---|---|---|
| Total | `total_line + β · total_features` | Adjusted MAE beats the closing-total MAE, **and** picks where the adjustment is at least 0.5 points hit at least 52.4% over at least 100 non-push picks |
| Spread | `spread_line + β · spread_features` | Same, using home margin and the closing spread |

The 1.0 and 2.0 thresholds are reported for context only. An adoption is
**provisional**: this is the third signal scored on the 2022-2025 holdout, so
24d may not show it as an edge until it also holds on the completed 2026
season with the frozen rates and coefficients.

## Files / areas

- `api/app/ingest/nflverse_team_efficiency.py` (new)
- `api/app/db/migrations/versions/0032_nfl_team_game_efficiency.py` (new)
- `api/app/repositories/nfl.py` - `replace_team_efficiency`, `get_team_efficiency`
- `api/app/core/nfl_efficiency_ratings.py` (new)
- `api/app/backtest/nfl_game_context.py` (generalized), `api/app/backtest/nfl_game_efficiency.py` (new), `api/app/backtest/nfl_game_lines.py` (`--signal efficiency`)
- `.github/workflows/nfl-ingest.yml` - one step
- Tests: `test_nflverse_team_efficiency.py` (new), `test_nfl_repository.py`,
  `test_nfl_efficiency_ratings.py` (new), `test_nfl_game_context_backtest.py`
  (existing 24e tests, unchanged), `test_nfl_game_efficiency.py` (new)

## Data / contracts

**`nfl_team_game_efficiency`** (load-bearing: 24d and any later team-sport
rating read it; item 17 should treat it as a cross-sport team-game table):

| Column | Type | Note |
|---|---|---|
| `id` | bigint PK | |
| `game_id` | bigint FK `nfl_games.id`, cascade | |
| `team_id` | bigint FK `nfl_teams.id`, cascade | the offense, from the game's home or away side |
| `season`, `week` | smallint | copied from the game for as-of bounds without a join |
| `is_home` | boolean | |
| `plays` | smallint | counted plays, rules above |
| `epa` | double precision | summed, not averaged, so seasons aggregate exactly |
| `successes` | smallint | |
| `fetched_at` | timestamptz, default `now()` | |

Unique on (`game_id`, `team_id`); index on (`season`, `week`). A missing row
means play-by-play not loaded, never zero plays. Defense for a team-game is
the opponent's row.

**Efficiency features** (load-bearing if adopted, since 24d must compute the
same values live): names and definitions in the tables above.

## Testing

- The test gate is on. Parser, writer SQL, rating replay, feature signs,
  holdout independence, and the rule all get focused tests.
- Integration: the Step 3 backfill counts, sanity bounds, and rerun hash, the
  Step 5 coefficient match, and the Step 8 run are local-database checks with
  printed evidence.
- Final gate: `.venv\Scripts\python.exe -m pytest` from `api/`. No web change.

## Notes for the AI

- The play-by-play archive is ~19 MB per season (~100 MB CSV); parse it
  streaming, as `fetch_red_zone_usage` does. Raw plays are never stored.
- NFLverse `game_id` matches `nfl_games.nflverse_game_id`. Historical
  `posteam` codes (`STL`, `SD`, `OAK`) never need mapping because the writer
  takes the team from the game's home or away side.
- `spread_line` is the expected home margin, positive when the home team is
  favored. `epa_edge` is home minus away, so a positive coefficient means the
  market underrates the better offense.
- Games ordered as in `get_game_line_games` (date, then kickoff). A postponed
  game keeps its original week.
- 2012-2013 are burn-in and never become cases; 2026 is stored but not scored.
- The regression lives in the backtest module (scikit-learn); `core/` stays pure.
- Do not look at holdout numbers before Step 8, and do not change a play rule,
  grid, feature, threshold, or the rule after it.

## Decision

Recorded 2026-09-19 from the single holdout run
(`python -m app.backtest.nfl_game_lines --signal efficiency`). No play rule,
grid, feature, threshold, or rule changed after it.

```
Learning rates (fit-season next-game MAE): epa_per_play 0.05, success_rate 0.1, plays 0.05
Efficiency fit 2014-2021 (points added to the closing line per unit):
  total: epa_sum -1.582, success_sum -5.844, pace +0.066
  spread: epa_edge +3.131, success_edge +0.515

TOTAL EFFICIENCY (MAE: closing line, adjusted line; picks by adjustment size)
set          games     close  adjusted  hit rate (W-L-P)
2022-2025     1087   10.1891   10.2077  @0.5 0.487 (132-139-2)  @1 0.556 (10-8-1)  @2 1.000 (1-0-0)
  wk 1-4       256   10.3750   10.4326  @0.5 0.364 (16-28-0)  @1 0.000 (0-1-0)  @2   -   (0-0-0)
  wk 5+        831   10.1318   10.1384  @0.5 0.511 (116-111-2)  @1 0.588 (10-7-1)  @2 1.000 (1-0-0)
Verdict: rejected

SPREAD EFFICIENCY (MAE: closing line, adjusted line; picks by adjustment size)
set          games     close  adjusted  hit rate (W-L-P)
2022-2025     1087    9.4945    9.5138  @0.5 0.414 (60-85-1)  @1 1.000 (4-0-0)  @2   -   (0-0-0)
  wk 1-4       256    9.7539    9.7625  @0.5 0.571 (8-6-0)  @1   -   (0-0-0)  @2   -   (0-0-0)
  wk 5+        831    9.4146    9.4371  @0.5 0.397 (52-79-1)  @1 1.000 (4-0-0)  @2   -   (0-0-0)
Verdict: rejected
```

**Both arms rejected.**

| Arm | Why |
|---|---|
| Total | Adjusted MAE worse than the closing total (10.2077 vs 10.1891), and 0.5-point picks hit 48.7% (132-139), under 52.4% |
| Spread | Adjusted MAE worse (9.5138 vs 9.4945), and 0.5-point picks hit 41.4% over 145 decided picks, under 52.4% |

**What it means:** team EPA per play, success rate, and pace, as specified,
add nothing to NFL closing spreads or totals; the market already prices them.
The adjusted line lost to the close on MAE in every row, both buckets included.
24d may show efficiency as team context, never as an adjustment or an edge.
The stored `nfl_team_game_efficiency` table stays: it is a correct, refreshed
record of team play and a candidate input for item 17's cross-sport team
ratings.

**Notes, not evidence.**

- The 1.0-point cells (10-8-1 total, 4-0 spread) are tiny samples and adopt
  nothing.
- The spread arm did worse than a coin at 0.5 points in weeks 5+ (52-79). If
  anything, this suggests the market already weighs efficiency at least as
  heavily as this fit does. It is not a signal to fade: it is one cell, found
  after the fact.
- EPA and plays chose the lowest learning rate on the pre-registered grid
  (0.05), so a slower rate was never tried. A lower-rate grid is a legitimate
  follow-up only if it is pre-registered and scored on seasons not yet played
  (2026 onward), never refitted on 2022-2025, which has now been scored for
  24b, 24e, and 24c.

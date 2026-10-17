# Feature: NFL red-zone usage for anytime TD

**From build-plan:** feature 19j
**Status:** complete (2026-09-18); red-zone not adopted by the backtest

## Goal

Store per-player, per-game red-zone opportunity counts (carries and targets
inside the 20 and inside the 5) aggregated from NFLverse play-by-play, build a
repeatable anytime-TD backtest, and blend red-zone opportunity into the anytime-TD
probability **only if** the backtest shows it beats the current baseline on
held-out data. Touchdowns follow scoring-position opportunity more closely than
total volume, but that is a hypothesis this feature tests, not assumes.

## In scope

- Migration `0024`: four nullable red-zone count columns on `nfl_player_weekly_stats`.
- A pure NFLverse play-by-play parser that aggregates plays to per-player,
  per-game counts. Raw plays are never stored.
- A standalone ingest command that downloads one season's play-by-play, writes the
  counts, and is idempotent. Backfill 2024, 2025, and 2026 once.
- Add the play-by-play ingest to the Tuesday `nfl-ingest.yml` job so counts stay
  fresh whether or not the model adopts them.
- Pure red-zone TD math: pre-week red-zone opportunity rates, an expected TD rate
  from them, and a blend with the existing historical TD rate.
- A durable anytime-TD backtest: fit on 2024, evaluate on 2025 held out, scored
  by log loss and Brier against the actual outcome (scored a TD or not).
- **Only if the backtest passes the adoption rule:** wire the blend into
  `/nfl/slate` and `/nfl/projections`, bump the model version, and show red-zone
  evidence in the anytime-TD evidence panel.

## Out of scope

- Loading 2023 or earlier seasons. That would change current 2025 baselines and
  position rates. Early-2024 player-games drop out through the minimum-sample rule.
- Red-zone input to any market other than anytime TD (rushing yards, receptions,
  and so on).
- Passing TDs. QB anytime TD stays rushing plus receiving, matching the existing
  `touchdowns` column.
- Snap counts (19m), injuries and depth charts (19l), weekly rosters (19k).
- Backtesting against book prices or profitability. This backtest measures
  probability quality only.
- Re-tuning `TD_SEASON_WEIGHTS` or `TD_PRIOR_GAMES`. The baseline in the
  backtest is the production baseline, unchanged.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Red-zone storage and play-by-play parser.** Migration `0024`
  adds nullable `rz20_carries`, `rz20_targets`, `rz5_carries`, `rz5_targets`
  (`smallint`) to `nfl_player_weekly_stats`, with a downgrade. Add
  `parse_red_zone_usage(csv_text, season)` to a new
  `app/ingest/nflverse_pbp.py`, returning one frozen `NflverseRedZoneGame` per
  (gsis player id, game id) with the four counts. Play rules are in Data /
  contracts below.
  *Done when:* `alembic upgrade head` reaches `0024` and `downgrade -1` reverts
  cleanly. Parser tests on a fixture with the real published header prove: a
  carry at the 5 counts in both `rz5` and `rz20`, a carry at the 6 counts in
  `rz20` only, a carry at the 21 counts in neither, a target counts for the
  receiver, and sacks, two-point tries, `no_play`, kneels, spikes, postseason
  plays, and rows missing a player id are all excluded.

- [x] **Step 2 - Idempotent ingest, backfill, and cron.** Add
  `run(season, dry_run)` and a CLI (`python -m app.ingest.nflverse_pbp --season
  2025 [--dry-run]`) that streams the gzip CSV and writes counts through a new
  repository function. For every game in the file, the stored weekly-stat rows are
  first set to `0` for all four columns, then the counts are applied, so "no
  red-zone plays" reads `0` while "play-by-play not loaded" stays `NULL`. Players
  with red-zone plays but no weekly-stat row, and play-by-play games with no
  `nfl_games` row, are skipped and counted in the output, not created. The whole
  season parses before any write, and the write is one transaction, so a failed
  download or parse leaves the database untouched. `--dry-run` parses and prints
  counts without writing. A season not yet published raises the existing
  `SeasonNotPublished` style of error. Backfill 2024 to 2026, then add the step to
  `nfl-ingest.yml` after the NFLverse stats step.
  *Done when:* a repository test proves the reset-then-apply write, the zero
  versus `NULL` distinction, and a second run leaving identical values. After the
  backfill, a local query shows non-null red-zone counts on every 2024 and 2025
  regular-season weekly row, unchanged weekly-stat row counts, and a skipped-player
  count printed by the CLI. `nfl-ingest.yml` runs the new command.

- [x] **Step 3 - Pure red-zone TD math.** In `app/core/nfl_projection.py` (or a
  new `app/core/nfl_red_zone.py` if it reads better), add:
  `NflRedZoneSeason` (season, games with counts, four per-game averages);
  `red_zone_rates(seasons, line_season, position_rates)`, which recency-weights
  with `TD_SEASON_WEIGHTS` and shrinks toward the position with
  `TD_PRIOR_GAMES`, counting only games with non-null counts; and
  `red_zone_td_probability(historical_rate, rz_rates, coefficients, blend_weight)`,
  which turns rates into an expected TD rate
  (`intercept + sum(coefficient * rate)`), blends it with the historical rate,
  and returns a Poisson probability. Coefficients and blend weight are
  parameters, so the backtest can fit them and production can use frozen
  constants. Nothing is wired yet.
  *Done when:* unit tests prove that a blend weight of `0` exactly reproduces
  `anytime_td_probability`, that more inside-5 carries raise the probability,
  that a player with no red-zone evidence falls back to the position rates, that
  `NULL` count seasons contribute no evidence, and that negative or non-finite
  inputs are clamped rather than propagated.

- [x] **Step 4a - Pure backtest core.** New `app/core/nfl_td_backtest.py` with
  a `NflWeeklyTdRow` dataclass (player, position, season, week, touchdowns,
  nullable red-zone counts), a builder that turns a list of rows into strictly
  pre-week inputs for each evaluated player-game, and `log_loss`, `brier`, and a
  per-position predicted-versus-actual summary. "Pre-week" uses the same
  `season < s OR (season = s AND week < w)` predicate as `_td_history`, and the
  position rates are also pre-week. Only RB, WR, TE, and QB player-games with at
  least `MIN_BASELINE_GAMES` pre-week games are evaluated. Log loss clips
  probabilities to `[1e-6, 1 - 1e-6]`.
  *Done when:* unit tests prove the builder never uses the same or a later
  week (including for position rates), thin-history and non-skill positions are
  excluded, and log loss and Brier match hand-computed values on a three-row
  fixture.

- [x] **Step 4b - Backtest runner.** Add a repository query returning every
  regular-season weekly row as `NflWeeklyTdRow`, and
  `app/backtest/nfl_anytime_td.py` (`python -m app.backtest.nfl_anytime_td`).
  Two fits, both on 2024 only:
  1. **Conversion coefficients** - scikit-learn `LinearRegression(positive=True)`
     (non-negative least squares, identity link, matching the linear form in
     Step 3) of same-game `touchdowns` on same-game counts (`rz5_carries`,
     `rz20_carries - rz5_carries`, `rz5_targets`, `rz20_targets - rz5_targets`,
     so the inputs are disjoint), with intercept. This learns what an
     opportunity is worth, not who gets them.
  2. **Blend weight** - applying those coefficients to pre-week red-zone rates,
     choose the weight from `0.0` to `0.6` in `0.1` steps by 2024 log loss.

  Then score that single configuration on 2025.
  *Done when:* the CLI prints the fitted coefficients, the chosen weight, and a
  baseline-versus-red-zone table (log loss, Brier, evaluated games, mean
  predicted versus actual TD rate) for the 2024 fit set, the 2025 holdout, and
  each position on 2025. No test for the runner itself (it is I/O and a
  third-party fit). Its pure pieces are covered in 4a.

- [x] **Step 5 - Record the result and decide.** **Decision: not adopted** (see
  Implementation notes). Run the backtest and paste its
  output into Implementation notes. **Adoption rule:** red-zone is adopted only if
  the 2025 holdout improves **both** log loss and Brier over the baseline and no
  position with 500 or more evaluated games gets worse log loss. If adopted,
  freeze the fitted coefficients and weight as named constants with a comment
  citing the backtest date and holdout numbers. If not adopted, write down why,
  mark Steps 6 and 7 skipped, and go to Step 8. The user approves the decision
  before either path continues.
  *Done when:* Implementation notes hold the full backtest output, the rule
  evaluated line by line, and the user's decision.

- [x] **Step 6 - (Adopted only) Wire red-zone into the anytime-TD API.**
  **Skipped: red-zone not adopted in Step 5.** Extend
  `_td_history` in `app/repositories/nfl.py` to return per-season red-zone
  averages and position red-zone rates under the same pre-week predicate. Route
  the anytime-TD baseline in `routers/nfl.py` (`_projection_value` and
  `_baseline`) through `red_zone_td_probability` with the frozen constants, so
  `/projections` and `/slate` still agree. Bump `NFL_PROJECTION_MODEL_VERSION`.
  Add nullable `red_zone` evidence to the slate line: pre-week weighted per-game
  `rz20_carries`, `rz20_targets`, `rz5_carries`, `rz5_targets`, plus
  `red_zone_sample_games`. It is `null` for non-TD markets. Add a
  `red_zone_unavailable` quality flag when an anytime-TD line has no red-zone
  evidence.
  *Done when:* repository tests prove current-week and future rows are excluded
  from red-zone averages. A router-level test proves `/projections` and `/slate`
  return the same anytime-TD probability for one player. A live
  `/nfl/slate` call returns the new model version, populated `red_zone` on
  anytime-TD lines, and `null` on other markets.

- [x] **Step 7 - (Adopted only) Show red-zone evidence on the slate.**
  **Skipped: red-zone not adopted in Step 5.** Add the
  types to `web/src/types/nfl.ts` and one compact row to the anytime-TD evidence
  panel on `NflIntelligencePage` ("Red zone / game: 1.4 car, 0.8 tgt inside 20;
  0.5 car, 0.2 tgt inside 5 - 12 g"). Any formatter goes in `src/utils/` with a
  test.
  *Done when:* the panel on a live anytime-TD row matches the API values, a row
  without evidence shows the unavailable state rather than zeros, `npm run test`
  and `npm run build` pass, and the console is clean.

- [x] **Step 8 - Verify.** Run the full API tests, web tests, and web build.
  Confirm migration state `0024 (head)` and weekly-stat row counts unchanged from
  before Step 2.
  *Done when:* all three pass. The adopted path also has a `/nfl` screenshot
  showing the red-zone row. The rejected path shows an unchanged model version and
  identical anytime-TD probabilities to before the feature for one sampled week.

## Files / areas

| Path | Change |
|---|---|
| `api/app/db/migrations/versions/0024_nfl_red_zone_usage.py` | Four nullable count columns, with downgrade |
| `api/app/ingest/nflverse_pbp.py` | New: play-by-play parser, streaming fetch, CLI |
| `api/app/repositories/nfl.py` | Red-zone write; backtest row query; (adopted) pre-week red-zone aggregates in `_td_history` |
| `api/app/core/nfl_projection.py` or `api/app/core/nfl_red_zone.py` | Pure red-zone rates and blended TD probability |
| `api/app/core/nfl_td_backtest.py` | New: pure pre-week input builder and scoring |
| `api/app/backtest/__init__.py`, `api/app/backtest/nfl_anytime_td.py` | New: backtest runner |
| `.github/workflows/nfl-ingest.yml` | Tuesday play-by-play ingest step |
| `api/app/routers/nfl.py`, `api/app/schemas/nfl.py` | (Adopted) blended baseline, `red_zone` evidence, flag |
| `web/src/types/nfl.ts`, `web/src/pages/NflIntelligencePage.tsx` | (Adopted) evidence row |
| `api/tests/test_nflverse_pbp.py`, `test_nfl_red_zone.py`, `test_nfl_td_backtest.py`, `test_nfl_repository.py` | Parser, math, backtest, and as-of coverage |

## Data / contracts

**Source.** `https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.csv.gz`.
Public, no key, no quota. It is large (hundreds of columns), so stream it
through `gzip` and `csv.DictReader` and keep only the aggregate dict in memory.
Step 1 confirms the header names against a real download before writing the
fixture.

**Play rules (load-bearing, 19m's backtest reuses the same data):**

- Regular season only: `season_type == "REG"`.
- `play_type` in (`run`, `pass`). This drops `no_play` (penalty-nullified),
  `qb_kneel`, `qb_spike`, kickoffs, and punts.
- `two_point_attempt != 1`.
- **Carry:** `rush_attempt == 1` with a `rusher_player_id`. QB scrambles count,
  because they are real rushing TD chances.
- **Target:** `pass_attempt == 1`, `sack != 1`, with a `receiver_player_id`.
- **Zone:** `yardline_100 <= 20` counts toward `rz20_*`, and `yardline_100 <= 5`
  toward `rz5_*`. Inside-5 is a subset of inside-20, not exclusive.
- Player key: the gsis id (`rusher_player_id` / `receiver_player_id`), which is
  what `nfl_players.nflverse_id` stores. Game key: NFLverse `game_id`, matching
  `nfl_games.nflverse_game_id`.

**Schema (load-bearing), migration `0024`.** On `nfl_player_weekly_stats`, add
`rz20_carries`, `rz20_targets`, `rz5_carries`, `rz5_targets`, all `smallint
NULL`. `NULL` means play-by-play is not loaded for that game. `0` means it was
loaded and the player had no such plays. Never coerce `NULL` to `0`.

**Backtest contract (load-bearing for 19m).** `app/core/nfl_td_backtest.py`
exposes a pre-week input builder, `log_loss`, `brier`, and a per-position
calibration summary that take plain dataclasses. 19m adds a snap-share input to
the same harness rather than building a second one.

**Adopted-path API (Steps 6 and 7 only).** `NflSlateLineSchema` gains nullable
`red_zone: {rz20_carries, rz20_targets, rz5_carries, rz5_targets}` (pre-week
weighted per-game floats) and nullable `red_zone_sample_games`. Both are `null`
for every market except `anytime_touchdown`. New quality flag:
`red_zone_unavailable`.

## Testing

Test gate is on. Logic-bearing steps ship tests in the same diff:

- Step 1: parser rules on a fixture with the published header (every inclusion
  and exclusion rule above).
- Step 2: repository reset-then-apply, zero versus `NULL`, idempotent rerun.
- Step 3: pure math, including weight `0` equal to production and `NULL`
  handling.
- Step 4a: pre-week leakage guard (player and position) and hand-computed scoring.
- Step 6: as-of exclusion and `/projections` matching `/slate`.
- Step 7: any new `src/utils/` formatter.

No live downloads in tests. Run from `api/` with
`.venv\Scripts\python.exe -m pytest`, and from `web/` with `npm run test` and
`npm run build`. The backfill and the backtest run are explicit verification
actions against the local database, never part of the test suite.

## Notes for the AI

- The backtest decides. Do not wire red-zone into the API before Step 5's
  decision is recorded and the user approves it. A rejected result is a valid
  outcome of this feature, not a failure.
- Do not tune on 2025. Coefficients and blend weight come from 2024 only. 2025 is
  scored once with the chosen configuration. If you are tempted to adjust and
  rerun on 2025, stop and report instead.
- The baseline arm of the backtest must call the production
  `anytime_td_probability` unchanged, with the same pre-week predicate, so the
  comparison is against what users see.
- Downstream `model_projection` adjustments (market, home, opponent) apply the
  same way to both arms, so comparing at the baseline probability is fair.
- `core/` stays pure. The scikit-learn fit lives in the backtest runner, not in
  `core/`, and production only reads frozen constants.
- Keep `NULL` distinct from `0` through parser, repository, aggregates, model
  input, API, and UI, following 19h.
- The ingest writes to the local database. Run the backfill once in Step 2 as
  explicit verification, not in tests.
- `app/backtest/` is a durable, reusable harness (19m depends on it), not a
  one-off diagnostic script, so it belongs in the app tree.

## Implementation notes

- Step 1: header confirmed against the real 2024 file (all 13 needed columns
  present). Missing values are empty strings; `qb_kneel` rows carry
  `rush_attempt=1`, so the `play_type` filter is what excludes them. The parser
  takes `Iterable[str]` lines rather than one string so Step 2 can stream the
  ~100 MB decompressed file. Migration upgrade, downgrade, and re-upgrade clean;
  API tests 812 passed.
- Step 2: the parser now returns `NflverseRedZoneSeason(game_ids, games)` so a
  game with no red-zone plays is still zeroed. `SeasonNotPublished` takes an
  optional asset name. Backfill: 2024 272 games / 18,112 rows, 2025 272 / 18,522,
  2026 17 / 1,117, all rows non-null, row counts unchanged. Totals per season
  about 2,540 rz20 carries, 2,280 rz20 targets, 770 rz5 carries, 477 rz5
  targets. 2026 skipped 10 player-games, all from `2026_02_DET_BUF` (play-by-play
  published before its weekly stats); the cron runs stats first, so they attach
  on the next run. Rerunning 2025 left the per-season checksum identical. API
  tests 817 passed.
- Step 3: new `app/core/nfl_red_zone.py`. Expected TDs are linear in
  opportunities, so the linear model applied to per-game averages is exact; that
  is why Step 4b fits it with non-negative least squares instead of the spec's
  original `PoissonRegressor` (a log link would not match this formula).
  `anytime_td_rate` was extracted, unrounded, under `anytime_td_probability`
  (signature and output unchanged) so the backtest scores both arms without
  2-decimal rounding. API tests 828 passed.
- Step 4a: `app/core/nfl_td_backtest.py`. The position rate mirrors production
  exactly: pre-week position TD average in the player's `choose_baseline_season`
  season (both `/projections` and `/slate` do this); position red-zone rates use
  the same season. Rows replay one week at a time, so a case never sees any
  same-week game. Evaluation threshold is `MIN_BASELINE_GAMES` games inside the TD
  recency window, matching the slate's label games. Scoring raises on empty
  input rather than reporting a perfect score. API tests 837 passed.
- Step 4b: `get_weekly_td_rows` plus `app/backtest/nfl_anytime_td.py`. First run
  (2026-09-18, fit 2024, holdout 2025):

  ```
  Coefficients (fit 2024, TDs per game): intercept 0.0623, rz5 carry 0.3375, rz6-20 carry 0.0793, rz5 target 0.4403, rz6-20 target 0.1870
  Blend weight (by 2024 log loss): 0.2

  set             games    LL base     LL rz   LL diff   Br base    Br rz   Br diff  p base   p rz actual
  2024 fit         3749    0.48025   0.47982  -0.00042   0.15391  0.15401  +0.00009   0.199  0.200  0.212
  2025 holdout     5439    0.44929   0.44864  -0.00064   0.14181  0.14155  -0.00026   0.203  0.203  0.190
    2025 QB         582    0.37481   0.37526  +0.00045   0.11234  0.11240  +0.00006   0.156  0.155  0.141
    2025 RB        1410    0.50581   0.50590  +0.00009   0.16568  0.16554  -0.00013   0.267  0.270  0.247
    2025 TE        1174    0.43774   0.43544  -0.00230   0.13554  0.13494  -0.00060   0.160  0.163  0.169
    2025 WR        2273    0.43926   0.43874  -0.00052   0.13780  0.13755  -0.00025   0.197  0.194  0.178
  ```

- Step 5 decision (2026-09-18, approved by the user): **not adopted.** The
  adoption rule, line by line:
  1. 2025 holdout log loss improves: yes (-0.00064).
  2. 2025 holdout Brier improves: yes (-0.00026).
  3. No position with 500+ evaluated games gets worse log loss: **no.** QB (582
     games) +0.00045 and RB (1,410) +0.00009.

  The overall gain was also small (about 0.14% of log loss, blend weight 0.2):
  touchdown history already carries most of the goal-line role for rushers. TE
  and WR improved, but adopting for them alone would be a rule chosen after
  seeing 2025, so 2025 would no longer be a holdout. If a TE/WR-only rule is
  wanted later, pre-register it and test on 2026 once enough weeks are played.
  No coefficients were frozen, and production is unchanged. Steps 6 and 7 are
  skipped. The feature ships the stored counts, the Tuesday ingest, and the
  reusable backtest (which 19m will extend with snap share).
- Step 8 (rejected path): API tests 837 passed; web tests 76 passed; web build
  passed; migration `0024 (head)`; weekly-stat row counts unchanged
  (18,112 / 18,522 / 1,117). Anytime-TD output for 2026 week 2 was compared
  between this branch and `master` (scratch worktree, calling
  `get_projections` and `get_slate` against the same database): 2,614
  `/projections` rows and 717 slate TD lines identical in projection, edge,
  flags, and model version (`opponent-dvp-usage-v1`, unchanged).

# Feature 19n: NFL scoring environment for anytime TD

**From build-plan:** feature 19n
**Status:** completed (2026-09-19)

## Final outcome

Both pre-registered signals were rejected because their 2024-only fits selected
a zero blend weight and therefore tied the 2025 holdout production baseline on
both log loss and Brier. Historical game-line and end-zone-target data remain
stored for future, separately specified research; neither signal was wired into
the production API or UI.

## Goal

Test whether implied team points, calculated from a game's spread and total,
improve anytime-TD probability beyond the production historical-rate plus adopted
RB/TE snap-share baseline. Test WR/TE end-zone targets as a distinct second
signal. Each signal is adopted only when its pre-registered 2025 holdout passes.

## In scope

- Historical NFLverse game lines and game context on `nfl_games`.
- Pure implied-team-total math and an `implied-total` arm in the existing anytime-TD
  backtest, fit on 2024 and evaluated once on 2025.
- A decision record before any implied-total production wiring.
- If adopted, consistent API and slate evidence, then a small UI evidence row.
- A separate WR/TE-only end-zone-target ingest and backtest decision.

## Out of scope

- Any production wiring before the relevant backtest decision is recorded and
  approved.
- Retuning after the 2025 holdout is viewed, book-price profitability testing, and
  changes to the existing historical TD baseline.
- TDs allowed, route participation, unrelated NFLverse columns, and new prop
  markets. Those remain later work.

## Build loop

Build one step at a time, show the diff and verification evidence, then wait for
approval before the next step. Do not commit without permission. A rejected signal
is a complete, valid result.

## Build steps

- [ ] **Step 1 - Historical game-line storage.** Add migration `0028` with nullable
  `spread_line`, `total_line` (numeric), `home_moneyline`, `away_moneyline` (int),
  `roof` (text), `home_rest`, and `away_rest` (smallint) columns on `nfl_games`,
  including downgrade. Extend `parse_schedules` and its write path to retain those
  real `games.csv` headers without converting absent values to `0`. Verify the
  published `spread_line` sign convention against a real NFLverse file before
  encoding it, then explicitly backfill 2024 through 2026.
  *Done when:* upgrade, downgrade, and re-upgrade are clean; parser tests use the
  real header; every 2024 and 2025 regular-season game has non-null lines after
  the explicit backfill.

- [ ] **Step 2 - Pure implied-total math.** Add `app/core/nfl_game_script.py` with
  `implied_team_points(total, spread, is_home)`: `total / 2 + spread / 2` at home
  and `total / 2 - spread / 2` away, using Step 1's confirmed convention. Add
  `scoring_environment_probability(...)`, which scales the baseline expected TD
  rate by `(implied_points / league_average_implied_points) ** exponent`, blends
  that rate by a parameterized weight, and returns a Poisson probability.
  *Done when:* tests cover home and away values, exact baseline reproduction at
  weight `0`, missing-line fallback, and clamping non-finite inputs.

- [ ] **Step 3 - Implied-total backtest signal.** Add `--signal implied-total` to
  `app/backtest/nfl_anytime_td.py`. Its baseline is production's historical TD
  rate plus adopted RB/TE snap share. Determine whether production's moneyline
  adjustment changes anytime-TD probability; if it does, reproduce that adjustment
  in both arms from Step 1's historical moneylines. Fit only exponent and weight
  using 2024, then score 2025 once.
  *Done when:* the CLI prints fitted parameters and base-versus-signal tables for
  fit, holdout, and positions in the established signal format.

- [ ] **Step 4 - Record the implied-total decision.** Apply the pre-registered
  rule: 2025 holdout log loss and Brier both improve, and no position with at
  least 500 evaluated games has worse log loss. Paste complete CLI output and a
  rule-by-rule evaluation below, then obtain user approval before continuing.
  *Done when:* the approved adoption or rejection is recorded. On rejection,
  Steps 5 and 6 are skipped and output remains production-identical.

- [ ] **Step 5 - Adopted-only API wiring.** Use non-stale consensus or median
  `nfl_game_odds` spread and total live, falling back to historical game lines.
  Route the frozen implied-total constants through `_anytime_td` so projections and
  slate agree, bump `NFL_PROJECTION_MODEL_VERSION`, and expose nullable
  `implied_team_points` plus `implied_total_unavailable` on anytime-TD slate lines.
  *Done when:* router tests prove agreement and a live slate response has the
  version and evidence.

- [ ] **Step 6 - Adopted-only UI evidence.** Add the slate fields to
  `web/src/types/nfl.ts` and one anytime-TD evidence row, such as “Implied team
  total: 27.5”. Any formatter lives in `web/src/utils/` with a test.
  *Done when:* web tests and build pass, and missing evidence is not shown as zero.

- [ ] **Step 7 - WR/TE end-zone target signal.** Add nullable end-zone targets to
  `nfl_player_weekly_stats` in migration `0029`. In `nflverse_pbp.py`, count a
  non-sack pass with a receiver where `air_yards >= yardline_100`; backfill 2024
  through 2026. Add `--signal end-zone`, evaluated on top of Step 4's approved
  state and limited to WR/TE before the run. Apply the same adoption rule and
  obtain user approval before any production use.
  *Done when:* parser and storage tests preserve null versus zero, the CLI reports
  the separate result, and the decision is recorded below.

- [ ] **Step 8 - Final verification.** Run full API tests, web tests, and web
  build, and confirm the migration head. If neither signal is adopted, compare one
  sampled anytime-TD week to `master` and show identical output.
  *Done when:* all applicable checks pass and the adoption boundary is evidenced.

## Data / contracts

**Historical `nfl_games` columns (migration `0028`):** nullable source values are
never coerced to zero. `spread_line` follows NFLverse's verified home-team sign
convention. `total_line` is numeric; moneylines are integer; roof and rest fields
retain their source meaning.

**Implied total:** NFLverse `spread_line` is negative when the home team is
favored, verified against the published `games.csv` header and rows on 2026-09-18.
Therefore home is `total / 2 - spread / 2` and away is `total / 2 + spread / 2`.
The core module is pure and receives all fit constants as parameters. Production
can consume frozen constants only after approval.

**Live adopted path:** the latest non-stale consensus or median total and spread
from `nfl_game_odds` win over historical fields. Anytime-TD slate evidence adds
nullable `implied_team_points` and `implied_total_unavailable`.

**End-zone target:** a non-sack pass attempt with a receiver and
`air_yards >= yardline_100`. The stored count is nullable until its play-by-play
season is loaded; a loaded player-game with no qualifying target is `0`.

## Testing

- Step 1: parser tests use the actual published schedule header; migration is
  exercised upgrade, downgrade, re-upgrade.
- Step 2: pure math tests cover signs, fallback, exact zero-weight behavior, and
  finite clamping.
- Step 3: existing backtest-core tests remain green and baseline behavior stays
  equivalent to production including any applicable moneyline effect.
- Step 5: router agreement between projections and slate.
- Step 6: formatter tests plus web test and build.
- Step 7: end-zone parser and persistence tests, with pre-week leakage guards in
  the backtest core.
- Step 8: run `api/.venv\\Scripts\\python.exe -m pytest`, `web/npm run test`, and
  `web/npm run build`. Tests make no live downloads; backfills and backtests are
  explicit local-database verification.

## Notes for the AI

- The backtest decides. Do not wire a signal into production before its decision
  is recorded and approved.
- Never tune on 2025. Fit on 2024, score 2025 once, then stop and report.
- Keep `NULL` distinct from `0` throughout.
- `core/` stays pure. Scikit-learn fits belong only in the backtest runner.
- Preserve the 19j/19m harness and its production baseline. Do not double-count
  moneyline adjustment.
- The end-zone test is WR/TE-only by pre-registration. Red-zone usage remains
  rejected and is not revived here.

## Implementation notes

- Planning only. No application, database, backfill, or backtest changes have
  been made.
- Step 1 approved 2026-09-19. Migration `0028` upgrade, downgrade, and
  re-upgrade passed; API tests: 944 passed. The parser fixture uses NFLverse's
  published schedule header. NFLverse `spread_line` is negative for a home
  favorite. The completed backfill has lines on all 272 regular-season games in
  2024 and 2025; 48 of 272 2026 games have published lines, with the remainder
  correctly null.
- Step 2 approved 2026-09-19. Pure implied-total math follows the verified spread
  sign, blends unrounded rates before the Poisson conversion, and clamps invalid
  inputs. Focused tests: 9 passed; API tests: 953 passed.
- Step 3 completed 2026-09-19. The initial command stopped before scoring because
  Postgres `numeric` values arrived as `Decimal`; the repository now casts them
  to `double precision` at the float-only core boundary. The regression test
  failed before that fix and passed after it. API tests: 955 passed. The sole
  completed 2025 holdout run:

  ```
  Implied-total configuration (fit 2024 only): league average 22.241, exponent 0.00, blend weight 0.0

  set             games    LL base LL implied   LL diff   Br base Br implied   Br diff  p base p implied actual
  2024 fit         3749    0.47290   0.47290  +0.00000   0.15209  0.15209  +0.00000   0.198  0.198  0.212
  2025 holdout     5439    0.44382   0.44382  +0.00000   0.14033  0.14033  +0.00000   0.198  0.198  0.190
    2025 QB         582    0.37690   0.37690  +0.00000   0.11294  0.11294  +0.00000   0.158  0.158  0.141
    2025 RB        1410    0.49104   0.49104  +0.00000   0.16143  0.16143  +0.00000   0.260  0.260  0.247
    2025 TE        1174    0.43022   0.43022  +0.00000   0.13389  0.13389  +0.00000   0.145  0.145  0.169
    2025 WR        2273    0.43869   0.43869  +0.00000   0.13759  0.13759  +0.00000   0.198  0.198  0.178
  ```

  Step 4 decision pending user approval. The pre-registered adoption rule fails:
  holdout log loss does not improve (tie), and Brier does not improve (tie).
- Step 4 rejected by user approval 2026-09-19. Steps 5 and 6 are skipped. The
  end-zone signal remains a separate WR/TE-only decision.
- Step 7a completed 2026-09-19. Migration `0029` upgrade, downgrade, and
  re-upgrade passed; focused tests: 40 passed; API tests: 956 passed. The
  explicit play-by-play backfill reset and populated 18,112 weekly rows for
  2024, 18,522 for 2025, and 1,188 for the 17 played 2026 games, with no skipped
  games or player rows. Read-only coverage verification found all of those rows
  non-null: 927, 882, and 50 respectively have a positive end-zone target count;
  the remaining rows are stored zeroes.
- Step 7b decision pending user approval. The sole 2025 holdout run selected a
  2024-only end-zone blend weight of `0.0`, so it is production-identical and
  fails the pre-registered adoption rule:

  ```
  End-zone configuration (fit 2024 WR/TE only): intercept 0.0805, per target 0.3846, blend weight 0.0

  set             games    LL base LL end-zone   LL diff   Br base Br end-zone   Br diff  p base p end-zone actual
  2024 WR+TE       2340    0.47075   0.47075  +0.00000   0.15077  0.15077  +0.00000   0.180  0.180  0.200
  2025 WR+TE       3447    0.43581   0.43581  +0.00000   0.13633  0.13633  +0.00000   0.180  0.180  0.175
    2025 TE        1174    0.43022   0.43022  +0.00000   0.13389  0.13389  +0.00000   0.145  0.145  0.169
    2025 WR        2273    0.43869   0.43869  +0.00000   0.13759  0.13759  +0.00000   0.198  0.198  0.178
  ```
- Step 7b rejected by user approval 2026-09-19. No end-zone API or UI wiring is
  permitted. Both experimental signals are rejected; production remains unchanged.
- Step 8 completed 2026-09-19. API tests: 958 passed; web tests: 12 files / 88
  passed; web production build passed; migration is `0029 (head)`. The production
  NFL router and its `nfl_projection` and `nfl_snap_share` dependencies are
  byte-identical to `master`; the changed repository query is backtest-only.
  Therefore sampled slate output is production-identical by the unchanged path.

## Correction (2026-09-19)

The implied-total arm above used an inverted spread sign. NFLverse
`spread_line` is positive when the home team is favored, not negative, so every
favorite was given its opponent's implied points. The fix
`blueprint/history/fixes/nfl-implied-total-spread-sign.md` corrected
`implied_team_points` and reran the same grid and rule once: holdout log loss
and Brier both improved, but QB and WR got worse, so the signal stays rejected.
The end-zone arm did not use the spread and is unaffected. The original text
above is kept as the record of what was run.

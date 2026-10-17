# Feature: NBA projection backtest harness

**From build-plan:** feature 20f
**Status:** complete (2026-10-06)

## Goal

Build the gate every NBA prop projection must pass before 20g serves it, the
NBA counterpart of NFL's 27b. The harness replays a season game by game: for
every player-game it computes each arm's projection from box scores dated
before that game, then scores it against the result (MAE, RMSE, bias, share
below). It needs no prop lines, which do not exist before 2026-10-06.

It ships with:
- a **reference arm**, fixed now: the plain recent average every candidate
  must beat;
- a **pre-registered adoption rule**, fixed before any variant is scored on
  the holdout;
- a **development season (2024-25)** for building and fitting candidates, and
  the **2025-26 holdout** the build plan names, scored once per candidate.

It is read-only and changes no served number: NBA has no projection yet.

## Design reference

None. A CLI report, no UI.

## In scope

- **Backfill 2023-24 and 2024-25** box scores with the existing
  `python -m app.ingest.hoopr_nba --season N` (no code change), then reload
  2025-26 so each player's `team_id` is back to their latest team. 2023-24
  exists only so 2024-25's early games have a prior-season window.
- **A history loader**, `get_projection_history(db, seasons)` in
  `app/repositories/nba.py`: every non-`PRE` box-score row for the seasons,
  with the game's Eastern date and type.
- **A pure module, `app/core/nba_projection_backtest.py`:** markets,
  eligibility, the as-of history walk, the reference arm and one comparison
  arm (`last_10`), and the adoption rule as a function.
- **Shared metrics:** NFL's `market_metrics` and `paired` typed against a
  small `ScoredCase` protocol (type-only), so NBA reuses them rather than
  copying.
- **The harness, `python -m app.backtest.nba_projections`,** with `--season`
  (default 2025) and `--arms` (default `reference`).
- **Two first runs:** development (2024-25, `reference,last_10`, proving the
  paired path end to end) and holdout (2025-26, `reference` alone, a
  descriptive read with no verdict), pasted under Results.

## Out of scope

- Any served projection, edge, P(over) or UI (20g).
- Candidate projection models (minutes-scaled, opponent, pace, rest, home,
  injuries): 20g and later items bring them as arms under this rule.
- Double-double: a binary market, which needs a probability scored by Brier or
  log loss rather than MAE. 20g decides whether to project it.
- Fantasy Score and any market not in `NbaLineOnlyMarket`.
- Changing `upsert_players` so an older backfill cannot move `team_id`; the
  run order in Step 1 handles it.
- Seasons before 2023-24.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Backfill 2023-24 and 2024-25 (data only)** - before any
  write, record the 2025-26 counts (games by type, box-score rows) and a
  checksum of every NBA player's `(id, team_id)`. Then, one command at a time:
  `--season 2023 --dry-run`, `--season 2023`, `--season 2024`, then
  `--season 2025` and `python -m app.ingest.espn_nba_preseason` to restore the
  latest teams (the preseason ingest writes 2026-27 teams after 2025-26's).

  *Built 2026-10-06:* 2023-24 1,321 games (1,233 `REG`, 6 `PIN`, 82 `PST`),
  35,004 box-score rows; 2024-25 1,326 games (1,236 / 6 / 84), 35,198 rows;
  218 players added. After the 2025 reload 91 existing players still differed
  (their 2026-27 preseason team), and the preseason re-run brought the
  `(id, name, position, team_id)` snapshot of all 652 existing players back
  to identical.

  *Done when:* both older seasons are stored, with games by type and
  box-score rows printed per season; 2025-26 counts are unchanged; the
  `(id, team_id)` checksum over players that existed before matches the one
  recorded first; `/nba/games/21320/line-only-props` still shows DET and BOS
  for Cunningham and Tatum; the slate's `previousDate` from 2026-10-20 is
  still 2026-06-13. If hoopR has no file for a season, stop and report rather
  than switch sources.

- [x] **Step 2 - History loader** - `get_projection_history(db, seasons) ->
  list[NbaHistoryRow]`: one row per `nba_player_game_stats` row in `REG`,
  `PIN` or `PST` games of the given seasons (`'nba'` on every `sport_*`
  reference), with `player_id`, `game_id`, `season`, `game_date`,
  `game_type`, `did_not_play`, `minutes` and the stat columns
  `LINE_ONLY_COLUMNS` names, ordered by `game_date`, `game_id`.

  *Done when:* a recorded-SQL test (the `_RecordingSession` pattern in
  `test_nfl_repository.py`) shows the `'nba'` literal, the game-type filter
  excluding `PRE` and the seasons parameter; a live call for 2024 and 2025
  prints rows per season, equal to Step 1's non-`PRE` box-score counts.

- [x] **Step 3 - Cases, eligibility and arms (pure)** - in
  `app/core/nba_projection_backtest.py`:
  - `BACKTEST_MARKETS`: the nine summed `NbaLineOnlyMarket` values (no
    double-double); actuals come from `line_only_value`, so a market settles
    exactly as 20c settles it.
  - `replay_cases(history, season, arm) -> list[NbaReplayCase]`: walks the
    season's games in date order. A game's inputs are the player's played
    games (`did_not_play` false) in the loaded history dated strictly before
    its Eastern date, because box scores load the next morning.
  - **Eligible** player-games: the player played, has at least
    `MIN_PRIOR_GAMES` (10) prior played games, and averaged at least
    `MIN_PRIOR_MINUTES` (20.0) minutes over the last 10 of them (NULL minutes
    excluded from that mean; a pre-tip proxy for the players PrizePicks
    posts). Eligibility belongs to the harness, not the arm, so every arm is
    scored on the same cases.
  - **Arms**, each a pure function from prior played games to a projection per
    market, averaging the market's settled value (`line_only_value`), so a
    combo is the sum of its components' means whenever no component is NULL:
    - `reference`: the mean of each stat over the last 20 prior played games
      (all of them when 10 to 19 exist), skipping games where that stat is
      NULL.
    - `last_10`: the same over the last 10.
  - A case whose actual is None (a NULL stat) is not scored.

  *Done when:* unit tests cover: the as-of cutoff (a same-date game is
  excluded); DNP games skipped as inputs and as cases; a window crossing into
  the prior season; eligibility at exactly 10 games and exactly 20.0 minutes
  (and just under each); NULL minutes ignored in the eligibility mean; a NULL
  stat skipped in the mean and as an actual; a combo equal to the sum of its
  components; `reference` and `last_10` on a known history.

- [x] **Step 4 - Shared metrics and the NBA rule** - in
  `app/core/nfl_projection_backtest.py`, `market_metrics` and `paired` take a
  `ScoredCase` protocol (`key`, `error`) instead of `ReplayCase` (type-only).
  In the NBA module: `NbaReplayCase` satisfies it, and `nba_adoption_verdict`
  applies the rule below with its own constants, so a change to NFL's rule
  can never move NBA's.

  *Done when:* NBA tests cover each verdict branch, including exactly 1.0%,
  exactly 2 SE and n = 299 / 300; a constants test pins the rule values,
  `REFERENCE_ARM`, `HOLDOUT_SEASON` and `DEVELOPMENT_SEASON`;
  `test_nfl_projection_backtest.py` and `test_nfl_projection_harness.py`
  pass unchanged.

- [x] **Step 5 - The harness** - `app/backtest/nba_projections.py`
  (`--season`, default 2025; `--arms`, default `reference`; an unknown arm is
  an argparse error): loads history for the season and the one before it,
  builds cases per arm, and prints:
  - a header naming the season as **holdout** (2025) or **development**
    (any other), with the rule text;
  - per arm: n, MAE, RMSE, bias and share below by market, overall and by
    prior-minutes bucket (20 to under 28, 28 and up);
  - per non-reference arm: the paired table against `reference` and a
    verdict per market; on the holdout the header says each candidate is
    scored there once.

  *Done when:* a report test on synthetic cases checks one metrics row, one
  paired row and a verdict; live runs complete for `--season 2024 --arms
  reference,last_10` and `--season 2025`; both outputs and timings are pasted
  under Results, with the holdout read counted (read 1: reference only,
  descriptive).

## Files / areas

- New: `api/app/core/nba_projection_backtest.py`,
  `api/app/backtest/nba_projections.py`,
  `api/tests/test_nba_projection_backtest.py`,
  `api/tests/test_nba_projection_harness.py`,
  `api/tests/test_nba_repository.py` (the loader's recorded-SQL test)
- Changed: `api/app/repositories/nba.py` (`get_projection_history`),
  `api/app/core/nfl_projection_backtest.py` (protocol typing only)
- Read only: `api/app/core/nba_line_only.py`, `api/app/nba/markets.py`,
  `api/app/ingest/hoopr_nba.py`
- Data: 2023-24 and 2024-25 rows in `sport_games`, `sport_players`,
  `nba_player_game_stats` (additive; no migration)

## Data / contracts

No schema change.

**Load-bearing, since 20g and every later NBA projection item cite these:**

```python
# app/core/nba_projection_backtest.py
REFERENCE_ARM = "reference"
HOLDOUT_SEASON = 2025          # 2025-26
DEVELOPMENT_SEASON = 2024      # 2024-25
MIN_PRIOR_GAMES = 10
MIN_PRIOR_MINUTES = 20.0
BACKTEST_MARKETS = (points, rebounds, assists, threes_made, blocks,
                    points_rebounds_assists, points_rebounds, points_assists,
                    rebounds_assists)   # NbaLineOnlyMarket values

@dataclass(frozen=True)
class NbaReplayCase:
    player_id: int
    game_id: int
    game_date: date
    game_type: str          # REG | PIN | PST
    market: str
    prior_minutes: float    # mean of the last 10 prior played games
    projection: float
    actual: float
    # key = (player_id, game_id, market); error = projection - actual
```

**Pre-registered adoption rule, fixed when this spec is approved, before any
variant is scored on the holdout.** A candidate arm is adopted for a market
only when, on the 2025-26 holdout's eligible cases:

1. at least 300 paired cases exist in that market;
2. MAE is at least 1.0% lower than the comparison arm's;
3. the paired mean absolute-error difference is below zero by more than two
   standard errors.

Otherwise it is rejected ("insufficient" below 300). The comparison arm is
`reference` until a candidate is adopted for that market; adopted candidates
then stack in build-plan order, as NFL's did.

**What "passing 20f" means for 20g:** 20g serves, per market, the reference
arm or a candidate adopted under this rule, never an unscored or rejected
arm. Each candidate is scored on the holdout once. Anything fitted (weights,
slopes, windows) is fitted on 2024-25 only; 2024-25 may be replayed freely.
Every holdout read is counted in Results, as NFL counts its 2025 reads.

## Testing

- Test gate on: Step 2 ships a recorded-SQL test, Steps 3 and 4 unit tests,
  Step 5 a report test. Step 1 is data, proved by counts and checksums.
- `cd api && .venv\Scripts\python.exe -m pytest` after each step.
- No web change.

## Notes for the AI

- **Run ingest and migration commands one at a time** (memory: a chained
  downgrade once wiped data). Step 1 is additive; still, no chained commands.
- **`sport_players.team_id` is last-write-wins** and 20e's line-only cards show
  it, so 2025 must be the last season loaded. Check the checksum, not just a
  spot read.
- The local `ingest_daily` task and GitHub Actions write the same database; the
  daily NBA job loads only the current season, so it cannot reorder teams.
- 20b recorded 24 played 2025-26 rows with NULL `minutes`: unknown, not zero.
- Load all history once and walk it in Python (about 35,000 rows a season), no
  per-game queries. If a run takes over a minute, report it before optimizing.
- Every `sport_*` reference carries `'nba'`; never read `PRE` rows; a past
  game's team is the box-score row's, though no arm here uses team.
- Do not tune anything on 2025-26. `last_10` is a fixed comparison arm, not a
  20g candidate; scoring it on the development season only keeps the holdout
  unread by any variant.
- `X | None`, no `Any`, dataclasses inside, `app/core` pure, repositories own
  SQL, no em dashes, comment only the why.

## Results

Run 2026-10-06 against the shared database after Step 1's backfill.

**Holdout reads: 1** (2025-26, `reference` alone, descriptive; no verdict).

- **Development (2024-25, `--arms reference,last_10`):** 10.8 s. 17,010
  eligible player-games (15,784 `REG`, 87 `PIN`, 1,139 `PST`), 153,090 cases.
  **`last_10` loses to `reference` in every market**: 0.2% to 1.7% higher MAE,
  more than 2 SE worse in all five single stats, and a larger positive bias
  (points +0.24 against +0.05). A shorter window chases noise; it is the
  pipeline proof, not a 20g candidate.
- **Holdout (2025-26, `reference`):** 6.4 s. 17,314 eligible player-games per
  market, so every market clears the 300-case minimum about 58 times over.
  The reference is nearly unbiased (|bias| <= 0.04 overall) but runs above
  the median in every market: `share_below` 52.0% to 57.5%, and **blocks
  68.1%** (a mean of a right-skewed, often-zero count sits above its median).
  As with NFL's 27b, that is a mean-versus-median gap, the case for a
  distribution (P(over)) before any over/under call, not for a shifted mean.
- Rotation players (20 to 28 prior minutes) run slightly low on points and
  combos (bias -0.20 to -0.26), starters (28+) slightly high (+0.18 to
  +0.29), the regression-to-role signal a minutes-aware candidate in 20g
  could test.

Holdout output (`python -m app.backtest.nba_projections`):

```
NBA projection backtest, 2025-26 (HOLDOUT: each candidate arm is scored here once; fit nothing on it)

Adopt a market only with >= 300 paired holdout cases, MAE at least 1% lower than reference, and a paired mean |error| difference below zero by more than 2 standard errors (pre-registered 2026-10-06).

Arm reference: projection minus actual (bias > 0 and share below > 50% mean the projection runs high)
  market / prior minutes                    n      MAE     RMSE     bias    below
  points / all                          17314     5.28     6.77    -0.01    53.0%
  points / 20-28 min                     8510     4.83     6.15    -0.20    52.7%
  points / 28+ min                       8804     5.71     7.32    +0.18    53.3%
  rebounds / all                        17314     2.04     2.65    +0.04    54.2%
  rebounds / 20-28 min                   8510     1.97     2.59    -0.02    53.9%
  rebounds / 28+ min                     8804     2.11     2.72    +0.11    54.5%
  assists / all                         17314     1.57     2.08    -0.02    54.1%
  assists / 20-28 min                    8510     1.40     1.87    -0.04    55.1%
  assists / 28+ min                      8804     1.74     2.27    +0.00    53.1%
  threes_made / all                     17314     1.03     1.39    +0.01    57.5%
  threes_made / 20-28 min                8510     0.94     1.29    -0.03    57.2%
  threes_made / 28+ min                  8804     1.13     1.49    +0.05    57.8%
  blocks / all                          17314     0.57     0.79    +0.01    68.1%
  blocks / 20-28 min                     8510     0.54     0.75    +0.00    70.3%
  blocks / 28+ min                       8804     0.61     0.83    +0.01    66.1%
  points_rebounds_assists / all         17314     6.73     8.58    +0.02    52.0%
  points_rebounds_assists / 20-28 min    8510     6.40     8.07    -0.26    51.4%
  points_rebounds_assists / 28+ min      8804     7.06     9.05    +0.29    52.5%
  points_rebounds / all                 17314     6.19     7.90    +0.04    52.3%
  points_rebounds / 20-28 min            8510     5.83     7.39    -0.22    51.5%
  points_rebounds / 28+ min              8804     6.54     8.37    +0.29    53.0%
  points_assists / all                  17314     5.79     7.40    -0.03    52.0%
  points_assists / 20-28 min             8510     5.37     6.79    -0.24    51.7%
  points_assists / 28+ min               8804     6.20     7.95    +0.18    52.2%
  rebounds_assists / all                17314     2.86     3.69    +0.03    53.3%
  rebounds_assists / 20-28 min           8510     2.72     3.53    -0.06    53.7%
  rebounds_assists / 28+ min             8804     2.99     3.84    +0.11    53.0%
```

Development paired table (`--season 2024 --arms reference,last_10`; the
per-arm tables are omitted):

```
Arm last_10 against reference, paired on player, game and market
  market                          n   ref MAE   arm MAE   change     diff      SE  verdict
  points                      17010     5.355     5.413   +1.09%   +0.058   0.013  reject
  rebounds                    17010     2.073     2.098   +1.17%   +0.024   0.005  reject
  assists                     17010     1.582     1.600   +1.17%   +0.018   0.004  reject
  threes_made                 17010     1.067     1.085   +1.70%   +0.018   0.002  reject
  blocks                      17010     0.579     0.586   +1.23%   +0.007   0.001  reject
  points_rebounds_assists     17010     6.809     6.823   +0.20%   +0.013   0.017  reject
  points_rebounds             17010     6.272     6.323   +0.81%   +0.051   0.015  reject
  points_assists              17010     5.858     5.886   +0.48%   +0.028   0.014  reject
  rebounds_assists            17010     2.897     2.917   +0.69%   +0.020   0.007  reject
```

**Beyond the spec:**
- `--arms` must include `reference` (it is the comparison arm), as NFL's
  harness requires `production`.
- Restoring player teams after the backfill also needed the preseason
  ingest re-run (Step 1).

**Load-bearing run order for any later NBA backfill:** an older season
overwrites `sport_players.team_id` (last write wins), which 20e's line-only
cards show. After backfilling, reload 2025-26 (`--season 2025`) and then
re-run `python -m app.ingest.espn_nba_preseason`, and compare a
`(id, name, position, team_id)` snapshot taken before.

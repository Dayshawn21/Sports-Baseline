# Feature: NHL projection backtest harness

**From build-plan:** feature 56b (parent 56, NHL prop board and model)
**Status:** complete (2026-11-04)
**Type:** Feature
**Pre-registration commit:** `237c2bcc01caf68495c88982eedd4cdbf57da2a0` (rule, floors, arms, seasons, version; before any scoring code)
**Branch:** `feature/nhl-projection-backtest` (cut from `origin/master` at `d0477040`, after 56a merged)

## Goal

Build the gate every NHL prop projection must pass before 56c serves it, the
NHL counterpart of NBA's 20f. The harness replays a season game by game: for
every eligible player-game it computes each arm's projection from box scores
dated before that game and scores it against the settled result (MAE, RMSE,
bias, share below). It needs no prop lines, which exist only since October
2026. It ships with a reference arm, a **pre-registered adoption rule fixed in
its own commit before any variant is scored**, and a first development run.

It is backtest only: nothing is served, stored or shown, and no NHL page or
endpoint changes. 56c serves the reference projection; 56d grades it.

## Design reference

None. A CLI report, no UI. Pattern: `blueprint/history/features/20f-nba-projection-backtest.md`,
`api/app/core/nba_projection_backtest.py`, `api/app/backtest/nba_projections.py`.

## Seasons and the holdout (settled here, stated up front)

| Season (`sport_games.season`) | Role | 56b reads it |
|---|---|---|
| 2023 (2023-24) | prior: supplies early 2024-25 windows | yes, as inputs only |
| 2024 (2024-25) | development: replay and fit freely | yes |
| 2025 (2025-26) | **holdout, scored once per candidate**, designated by 45b and never scored or fit on | **no: zero reads** |
| 2026 (2026-27) | live season accruing | no |

The harness refuses `--season 2025` without an explicit `--holdout` flag, and
56b never passes it. The `reference` arm is the baseline, not a candidate, so
there is nothing for a holdout verdict to decide here; the one holdout read for
the served projection (its P(over) calibration, as 20g1 did for NBA) belongs to
56c under its own pre-registered rule. This is a deliberate difference from 20f,
which also took a descriptive holdout read: NHL's holdout stays unread until
something is decided on it.

## In scope

- **Pre-registration (Step 1, its own commit):** every constant the rule and the
  replay depend on, as pinned module constants, plus the verdict function, before
  the history loader or any scoring exists.
- **History loader:** skater and goalie box-score rows for chosen seasons, NHL
  scoped, with game date, type, position and the stat columns.
- **Replay core (pure):** eligibility, the as-of walk, two arms, replay cases,
  reusing `market_metrics` and `paired` from `nfl_projection_backtest.py`
  (already typed against `ScoredCase`) and `nhl_stat_value` for actuals.
- **Harness CLI** `python -m app.backtest.nhl_projections` and one development run.

## Out of scope

- Serving, freezing, P(over), prop board or game-page changes (56c), the ranking
  check and Model page (56d).
- Any candidate beyond `reference` and `last_10` (opponent, goalie, pace,
  injuries, home or rest). Later arms plug into this rule.
- Reading the 2025-26 holdout or 2026-27 (see above); any prop-line or odds read.
- The two combo markets and Fantasy Score (not stored or settleable per 45a).
- Availability: who dresses or starts is known only after the game. Cases are
  games the player actually played, as in 20f; 56c must gate a served projection
  on pre-game availability separately (45f's goalie and injury snapshots are
  display only until tested).

## Pre-registered rule and constants (frozen by Step 1)

Copied from NBA's rule and held as NHL's own constants, so a later change to
NBA's can never move NHL's:

- A market is adopted for a candidate only with **at least 300 paired holdout
  cases**, MAE **at least 1.0% lower** than `reference`, and a paired mean |error|
  difference below zero by **more than 2.0 standard errors**; verdicts
  `adopt`, `reject`, `insufficient` (fewer than 300 pairs).
- `reference` arm: the mean of the market's settled value over the player's last
  **20** prior played games (all of them when 10 to 19 exist), skipping games
  where that stat is NULL. `last_10`: the same over 10.
- A game's inputs are the player's played games dated **strictly before** its
  Eastern date (box scores load the next morning); a no-row game is not a game.
- **Eligible skater case:** at least **10** prior played games and a mean time on
  ice of at least **12.0 minutes** over the last 10 with TOI stored (a pre-game
  stand-in for the players PrizePicks posts). **Eligible goalie case:** a game
  the goalie started, with at least **5** prior started games.
- Markets scored: the ten skater markets and the two goalie markets in
  `NhlLineOnlyMarket`; Faceoffs Won only for `position = 'C'`. Actuals come from
  `nhl_stat_value`, so a market settles as the player page does (TOI in minutes;
  NULL is not scored, never zero).
- Game types `REG` and `PST`, the slate's served set; NHL season constants:
  `PRIOR_SEASON = 2023`, `DEVELOPMENT_SEASON = 2024`, `HOLDOUT_SEASON = 2025`;
  `NHL_PROJECTION_REFERENCE_VERSION = "nhl-reference-v1"` (what 56c will freeze).

## Decisions for the owner (defaults shown; change before Step 1)

1. **TOI floor 12.0 min and goalie floor 5 starts.** Stand-ins, not tuned. Any
   change must happen before Step 1's commit; afterwards they are frozen.
2. **Goalie markets in 56b.** Included, but a goalie case exists only if he
   started, which is known only after the game, so goalie error is optimistic
   about who plays. The report flags this and 56c must not serve goalie lines
   without a pre-game starter. Alternative: skater markets only.
3. **Holdout stays unread in 56b** (recommended). Alternative: take 20f's
   descriptive reference-only read now; it uses the holdout's one look earlier
   than anything needs it.
4. **Merge style.** Step 1's commit hash is cited in the code and report, so at
   `/complete` merge this branch **fast-forward only** (or squash plus a pushed
   tag), never a plain squash, per the project's pre-registration rule. It means
   the PR cannot be squash-merged on GitHub.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Step 1 is a required, separate commit (the pre-registration).

Never accept a step you haven't read. If a diff is too big to review, split it.

## Build steps

- [x] **Step 1 - Pre-register the rule (own commit)** - `app/core/nhl_projection_backtest.py` with only the constants above, `NhlHistoryRow` (player id, game id, season, game date, game type, position, `is_goalie`, `started`, a stat mapping that includes `time_on_ice_seconds`), `NhlReplayCase`, `NhlVerdict` and `nhl_adoption_verdict(diff)`; no loader, arms or scoring. Commit it alone with the message `chore: pre-register the NHL projection rule (56b)`. *Done when:* `test_nhl_projection_backtest.py` pins every constant value, `REFERENCE_ARM`, the three season constants and `NHL_PROJECTION_REFERENCE_VERSION`, and covers each verdict branch including exactly 1.0%, exactly 2 SE and n = 299 / 300; pytest passes; `git log` shows the commit before any later step's commit; no scoring code exists yet.
- [x] **Step 2 - History loader** - `get_projection_history(db, seasons)` in `app/repositories/nhl.py`: one `NhlHistoryRow` per skater and goalie row in `REG` or `PST` games of the seasons, oldest first, with `sport = 'nhl'` on every `sport_*` reference, position from `sport_players`, goalie rows carrying `started`. *Done when:* a recorded-SQL test shows the `'nhl'` literal, the game-type filter and the seasons parameter; a live call for seasons 2023 and 2024 prints rows per season equal to the stored skater and goalie counts for those seasons; nothing in the call can accept season 2025 unless it is passed explicitly (no default seasons).
- [x] **Step 3 - Eligibility, arms and replay (pure)** - in the same core module: `window_mean(games)`, `ARMS = {reference, last_10}`, `eligible_case(row, prior)`, `replay_cases(history, season, arm)`, with the as-of walk by Eastern date. *Done when:* unit tests cover the same-date cutoff, a window crossing from 2023 into 2024, eligibility at exactly 10 games and exactly 12.0 minutes (and just under each), NULL TOI ignored in the eligibility mean, a NULL stat skipped as input and as actual, TOI actuals in minutes, Faceoffs Won scored only for position C, a goalie case only when he started with at least 5 prior starts, and `reference` versus `last_10` on a known history.
- [x] **Step 4 - Harness CLI** - `app/backtest/nhl_projections.py` (`--season` default 2024, `--arms` default `reference,last_10`, unknown arm an argparse error, any season other than 2024, refused unless `--holdout` is passed, and `--holdout` only accepts 2025 or later): header naming the season role and the rule text; per arm and market n, MAE, RMSE, bias and share below, overall and by a TOI bucket; `last_10` against `reference` paired with the verdict; a goalie-availability caveat line; the pre-registration commit hash. *Done when:* tests cover report formatting on tiny fixed cases, the arm parser and the holdout guard (only 2024 allowed without the flag; 2022, 2023, 2025, 2026 and 2027 refused; the flag accepts 2025 and later only); the CLI prints a header and the table for a stub history.
- [x] **Step 5 - Development run and docs** - run `python -m app.backtest.nhl_projections --season 2024` (read only, session wrapped read-only like 45e's checks), paste the output under Results, and add the command to `AGENTS.md` and `docs/commands.md`. *Done when:* the run completes on 2024-25 with per-market n, MAE, RMSE, bias and share below for both arms and a paired table; a spot check recomputes one market's MAE from raw rows in SQL to the printed value; no 2025-26 or 2026-27 row was read (state the seasons queried); Verify passes and `/invariants-review` is clean.

## Files / areas

- API: new `app/core/nhl_projection_backtest.py`, new `app/backtest/nhl_projections.py`, `app/repositories/nhl.py`, new `tests/test_nhl_projection_backtest.py`, `tests/test_nhl_projection_harness.py`, a loader test.
- Reused unchanged: `app/core/nfl_projection_backtest.py` (`market_metrics`, `paired`), `app/core/nhl_player_values.py` (`nhl_stat_value`), `app/nhl/markets.py`.
- Docs: `AGENTS.md` and `docs/commands.md` command line; archive at `/complete`.
- No web change, no migration, no endpoint, no workflow.

## Data / contracts

- **Load-bearing for 56c and 56d:** the constants, `NHL_PROJECTION_REFERENCE_VERSION`, the reference arm and the eligibility rule, because 56c serves and freezes exactly this projection under that version and 56d's ranking check treats it as its own sample. Changing any of them later means a new version.
- `NhlHistoryRow` / `NhlReplayCase` are internal dataclasses, never an API shape.

## Testing

- Python unit tests for every pure piece (rule, eligibility, arms, replay, report, arg parser), per the logic-test gate; the loader gets a recorded-SQL test plus the live row-count check; the 2024-25 run is the integration evidence.
- Live runs use the selector-loop launcher pattern and the database URL through the environment (never printed), with a read-only session.

## Notes for the AI

- **Order matters:** Step 1 is committed alone and before any scoring code exists; do not fold it into later commits or reword its constants afterwards.
- Never score or print 2025 (holdout) or 2026 (live) rows in 56b; the history call takes explicit seasons and the CLI guards the holdout.
- NHL keeps its own constants and module; do not import NBA's rule or change NFL's metrics beyond what already exists.
- A missing row means the player did not play (a void, never zero); NULL stat means not loaded.
- No em dashes; comment the why only; ask before committing (Step 1's commit message is fixed above); no AI attribution in commits.

## Results

Development run, `python -m app.backtest.nhl_projections --season 2024` (2026-11-04, read-only transaction, about 17 s). Seasons queried: 2023 and 2024 only; no 2025-26 or 2026-27 row was read. The `last_10` verdicts below are development reads and count for nothing; adoption is decided only on the holdout.

- **Spot check:** Shots On Goal `reference` recomputed from raw `nhl_skater_game_stats` rows with SQL window functions (20 prior games, 10 prior games, 12.0 TOI minutes): n 42,362, MAE 1.081, equal to the printed row. Goals Allowed (goalie starts only, 5 prior starts): n 2,723, MAE 1.262, equal.
- **Read:** the 20-game `reference` has the lower MAE in nine of twelve markets. `last_10` is lower in Time On Ice (2.0%, which the rule's arithmetic would call `adopt` on this development season), Faceoffs Won (0.8%) and Power Play Points (0.7%, under the 1% bar). Those are development reads and are not a verdict; they say only that a shorter window is worth testing for those markets in a later pre-registered candidate. Bias is near zero except Goalie Saves (+0.51 for `reference`).

```
NHL projection backtest, 2024-25 (development: replay and fit freely)

Pre-registered in commit 237c2bcc01caf68495c88982eedd4cdbf57da2a0.
Adopt a market only with >= 300 paired holdout cases, MAE at least 1% lower than reference, and a paired mean |error| difference below zero by more than 2 standard errors.
Cases: skaters with >= 10 prior games and >= 12 mean TOI minutes over the last 10; goalies who started with >= 5 prior starts; Faceoffs Won for centers only.
Goalie caveat: a goalie is a case only because he started, which is known after the game, so goalie error understates the uncertainty about who plays.

Arm reference: projection minus actual (bias > 0 and share below > 50% mean the projection runs high)
  market / prior TOI                       n      MAE     RMSE     bias    below
  shots_on_goal / all                  42362    1.081    1.394   +0.014    56.1%
  shots_on_goal / 12-16 min            15015    0.976    1.252   +0.006    56.5%
  shots_on_goal / 16+ min              27347    1.139    1.466   +0.017    55.9%
  points / all                         42362    0.550    0.712   +0.001    65.8%
  points / 12-16 min                   15015    0.466    0.606   -0.007    71.7%
  points / 16+ min                     27347    0.596    0.764   +0.006    62.6%
  assists / all                        42362    0.425    0.569   +0.000    74.1%
  assists / 12-16 min                  15015    0.320    0.460   -0.003    81.3%
  assists / 16+ min                    27347    0.483    0.621   +0.003    70.2%
  goals / all                          42362    0.280    0.433   +0.001    81.6%
  goals / 12-16 min                    15015    0.237    0.392   -0.004    85.1%
  goals / 16+ min                      27347    0.304    0.454   +0.003    79.6%
  power_play_points / all              42362    0.174    0.338   -0.001    82.7%
  power_play_points / 12-16 min        15015    0.079    0.221   -0.003    89.2%
  power_play_points / 16+ min          27347    0.227    0.388   +0.001    80.7%
  blocked_shots / all                  42362    0.788    1.027   +0.011    59.4%
  blocked_shots / 12-16 min            15015    0.676    0.860   +0.012    60.9%
  blocked_shots / 16+ min              27347    0.849    1.108   +0.011    58.5%
  plus_minus / all                     42362    0.970    1.270   +0.005    49.8%
  plus_minus / 12-16 min               15015    0.804    1.076   -0.002    48.4%
  plus_minus / 16+ min                 27347    1.062    1.365   +0.008    50.6%
  goalie_saves / all                    2723    5.593    7.216   +0.509    53.3%
  hits / all                           42362    0.923    1.247   +0.012    60.1%
  hits / 12-16 min                     15015    0.994    1.335   -0.013    58.0%
  hits / 16+ min                       27347    0.885    1.196   +0.026    61.2%
  time_on_ice / all                    42362    1.975    2.641   +0.015    50.0%
  time_on_ice / 12-16 min              15015    1.941    2.540   -0.024    48.9%
  time_on_ice / 16+ min                27347    1.994    2.695   +0.036    50.7%
  goals_allowed / all                   2723    1.262    1.570   -0.014    51.7%
  faceoffs_won / all                   12679    2.020    2.717   -0.035    56.0%
  faceoffs_won / 12-16 min              5444    1.722    2.359   -0.071    57.3%
  faceoffs_won / 16+ min                7235    2.244    2.958   -0.008    55.0%

Arm last_10: projection minus actual (bias > 0 and share below > 50% mean the projection runs high)
  market / prior TOI                       n      MAE     RMSE     bias    below
  shots_on_goal / all                  42362    1.102    1.421   +0.012    55.9%
  shots_on_goal / 12-16 min            15015    0.992    1.272   -0.006    55.8%
  shots_on_goal / 16+ min              27347    1.163    1.497   +0.021    56.0%
  points / all                         42362    0.555    0.728   +0.003    65.5%
  points / 12-16 min                   15015    0.464    0.617   -0.007    70.5%
  points / 16+ min                     27347    0.605    0.782   +0.008    62.8%
  assists / all                        42362    0.426    0.582   +0.001    72.5%
  assists / 12-16 min                  15015    0.319    0.469   -0.004    78.8%
  assists / 16+ min                    27347    0.485    0.635   +0.004    69.4%
  goals / all                          42362    0.280    0.443   +0.001    78.4%
  goals / 12-16 min                    15015    0.236    0.399   -0.004    81.9%
  goals / 16+ min                      27347    0.305    0.465   +0.004    76.6%
  power_play_points / all              42362    0.173    0.344   -0.001    79.2%
  power_play_points / 12-16 min        15015    0.077    0.224   -0.005    84.6%
  power_play_points / 16+ min          27347    0.226    0.395   +0.001    77.7%
  blocked_shots / all                  42362    0.796    1.047   +0.009    59.5%
  blocked_shots / 12-16 min            15015    0.680    0.875   +0.000    60.9%
  blocked_shots / 16+ min              27347    0.860    1.130   +0.013    58.8%
  plus_minus / all                     42362    1.002    1.300   +0.004    49.8%
  plus_minus / 12-16 min               15015    0.835    1.099   -0.002    48.9%
  plus_minus / 16+ min                 27347    1.094    1.399   +0.008    50.3%
  goalie_saves / all                    2723    5.706    7.343   +0.282    52.0%
  hits / all                           42362    0.927    1.257   +0.010    59.9%
  hits / 12-16 min                     15015    0.999    1.347   -0.010    58.2%
  hits / 16+ min                       27347    0.888    1.205   +0.021    60.9%
  time_on_ice / all                    42362    1.935    2.596   +0.059    50.9%
  time_on_ice / 12-16 min              15015    1.875    2.462   -0.089    48.4%
  time_on_ice / 16+ min                27347    1.969    2.667   +0.141    52.3%
  goals_allowed / all                   2723    1.289    1.604   -0.012    52.1%
  faceoffs_won / all                   12679    2.004    2.704   -0.006    56.1%
  faceoffs_won / 12-16 min              5444    1.694    2.326   -0.053    57.5%
  faceoffs_won / 16+ min                7235    2.238    2.957   +0.030    55.0%

Arm last_10 against reference, paired on player, game and market
  market                         n   ref MAE   arm MAE   change     diff      SE  verdict
  shots_on_goal              42362     1.081     1.102   +1.94%   +0.021   0.001  reject
  points                     42362     0.550     0.555   +0.82%   +0.004   0.001  reject
  assists                    42362     0.425     0.426   +0.27%   +0.001   0.001  reject
  goals                      42362     0.280     0.280   +0.01%   +0.000   0.000  reject
  power_play_points          42362     0.174     0.173   -0.71%   -0.001   0.000  reject
  blocked_shots              42362     0.788     0.796   +1.07%   +0.008   0.001  reject
  plus_minus                 42362     0.970     1.002   +3.27%   +0.032   0.001  reject
  goalie_saves                2723     5.593     5.706   +2.02%   +0.113   0.028  reject
  hits                       42362     0.923     0.927   +0.42%   +0.004   0.001  reject
  time_on_ice                42362     1.975     1.935   -2.01%   -0.040   0.004  adopt
  goals_allowed               2723     1.262     1.289   +2.15%   +0.027   0.006  reject
  faceoffs_won               12679     2.020     2.004   -0.80%   -0.016   0.006  reject
```

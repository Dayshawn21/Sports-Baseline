# Feature: Opposing-goalie backtest arm

**From build-plan:** feature 67a (parent 67, Opposing-goalie adjustment for NHL skater props)
**Status:** complete 2026-11-11 (rejected on development: every market picked beta 0; holdout unread; 67b and 67c not built)
**Branch:** `feature/nhl-opp-goalie-arm` (worktree `nhl-goalie-skaters-007493`)

## Goal

Test, before anything is served, whether scaling an NHL skater's projection by the
quality of the goalie he will shoot at makes it more accurate. The served
`nhl-reference-v1` projection ignores the opposing starter: a skater facing a
backup with a poor save percentage gets the same Points line as one facing an elite
starter. Daily Edge's NHL model leads with that matchup, so it is the obvious input
to test next.

67a is backtest only. It adds a pure adjustment, gives the 56b replay the
point-in-time opposing starter, scores development arms on 2024-25, commits the
per-market choice, and then scores one candidate once on the 2025-26 holdout. The
holdout verdict decides whether 67b serves and freezes anything at all.

## Split (item 67)

| Item | What | Ships |
| --- | --- | --- |
| **67a** (this spec) | Pure adjustment, replay inputs, development arms, one holdout scoring run | A CLI report and a recorded verdict per market; nothing served |
| 67b | Serve and freeze `nhl-opp-goalie-v1` in the markets 67a adopts | Gray value beside the reference on the player page, a second frozen row per line |
| 67c | Forward paired check on 2026-27 frozen rows | A read-only report; adopts nothing |

If 67a adopts no market, 67 closes after 67a with the recorded reject and 67b and 67c
are marked not built. The contracts 67b and 67c depend on are locked below so 67a's
choices cannot strand them.

## In scope

- **Pure adjustment** in a new `app/core/nhl_goalie_adjustment.py`: constants, the
  shrunk save percentage, the clipped multiplier and the per-market exponent.
- **History rows that know the matchup**: `NhlHistoryRow` gains `team_id` and
  `opponent_team_id`, and goalie rows carry `shots_against`, read by the existing
  repository functions. Every existing arm's output is unchanged.
- **Point-in-time matchup builder** in `app/core/nhl_projection_backtest.py` (or a
  sibling core module): for each skater case, the opponent's starting goalie in that
  game, his last 20 starts before the game date, and the league save percentage
  before the game date.
- **Development arms** `opp_goalie_b05` and `opp_goalie_b10` in
  `python -m app.backtest.nhl_projections`, paired against `reference` on 2024-25.
- **A per-market exponent** chosen on 2024-25 by a pre-registered selection rule and
  committed as the `opp_goalie` candidate arm before any holdout read.
- **One holdout scoring run** of `opp_goalie` against `reference` on 2025-26, only
  after a separate yes in chat.
- Docs: `AGENTS.md`, `docs/commands.md`, a Results section here, and the local
  interview guide if present.

## Out of scope

- Serving, freezing or showing anything (67b), and the forward check (67c).
- A P(over) for the new version. 56c2's fit names `nhl-reference-v1` as the only
  projection it reads (`FIT_PROJECTION_MODEL_VERSION`), so the new version stores
  none, and so it cannot enter 56d's ranking slices. A fit for it is a later item,
  considered only if 67c reads well.
- Goalie markets (Goalie Saves, Goals Allowed): their own availability gate stays as
  56c1 built it.
- Other skater markets (Blocked Shots, Hits, Plus/Minus, Time On Ice, Faceoffs Won):
  the goalie has no plausible effect on them; they are not adjusted or scored.
- Team shot suppression, back-to-backs, home and away, or any second input. One input
  per candidate keeps the verdict readable.
- Any change to `nhl-reference-v1`, 56b's constants, rule or pre-registration commit,
  56c2's fit, 56d's rule, version or rows, or NBA and NFL code.

## Inputs, and how each is known point-in-time

| Input | Backtest (67a) | Served (67b) |
| --- | --- | --- |
| Skater's reference projection | `ARMS["reference"]` on prior played games, as 56b | `project_line`, unchanged |
| Opponent | `opponent_team_id` on the skater's own box-score row | the other side of the game in stored context |
| Opposing starter | the opponent's goalie row in the same game with `started = true` | the opponent side's ESPN probable goalie, `confirmed` or `expected`, fresh, linked to a stored player |
| Starter's quality | his last `GOALIE_QUALITY_STARTS = 20` starts dated strictly before the game's Eastern date, summing `saves` and `shots_against` (rows with either NULL skipped) | the same 20 starts from `get_prior_history`, which already returns a goalie's starts only and applies `NHL_FIRST_HISTORY_SEASON` |
| League save percentage | every start in the read window (the previous season and this season) dated strictly before the game date | a new repository aggregate over the same window, floored at `NHL_FIRST_HISTORY_SEASON` |

**Caveat, printed in the report:** the backtest knows who actually started, which is
only known after the game. The served version will use ESPN's expected starter, which
is sometimes wrong, so backtest gains overstate what the served version can earn. 67c
measures the served gap directly.

**Same-day rule:** inputs are games dated before the case's Eastern date, exactly as
`replay_cases` treats prior games, so an earlier game the same night is never an
input.

## The adjustment (pre-registered before any scoring)

All constants live in `app/core/nhl_goalie_adjustment.py` and are fixed in the
pre-registration commit (Step 5) before any opposing-goalie arm is scored on any
season. None is tuned after scoring except the exponent, and only by the selection
rule below on 2024-25.

- `NHL_OPP_GOALIE_VERSION = "nhl-opp-goalie-v1"` (the version 67b serves and freezes).
- `ADJUSTED_MARKETS = (SHOTS_ON_GOAL, POINTS, GOALS, ASSISTS, POWER_PLAY_POINTS)`.
- `GOALIE_QUALITY_STARTS = 20`.
- `SHRINK_SHOTS = 1000`: save percentage stabilises slowly, so a goalie needs about
  35 starts' worth of shots before his own number outweighs the league's. Fixed, not
  tuned.
- Shrunk save percentage: `(saves + SHRINK_SHOTS * league) / (shots + SHRINK_SHOTS)`.
  A goalie with no prior starts reads exactly the league value.
- Multiplier: `m = clip((1 - shrunk) / (1 - league), 0.80, 1.25)`. A better goalie
  (higher save percentage) gives `m < 1` and lowers the projection.
- Adjusted projection: `reference * m ** beta[market]`.
- **Development grid:** `beta` in `{0.5, 1.0}` as arms `opp_goalie_b05` and
  `opp_goalie_b10`; `beta = 0` is `reference` itself.
- **Selection rule (run on 2024-25 only):** per market, take the `beta` in
  `{0, 0.5, 1.0}` with the lowest 2024-25 MAE, ties to the smaller. A market whose
  pick is 0 is not adjusted and is not a holdout candidate. The picks become
  `OPP_GOALIE_BETA_BY_MARKET` and the `opp_goalie` arm, committed before the holdout
  run.
- **No opposing starter row** (a data gap): `m = 1`, so the case stays paired and
  every arm scores the same cases; the report counts these.

**Prior for Shots on Goal:** a goalie should not change how often a skater shoots,
so Shots on Goal is expected to pick `beta = 0`. It is tested because weak starters
correlate with weak teams and back-to-backs, which may raise shot volume; the grid
lets the data say no.

## Adoption rule (unchanged from 56b)

`nhl_adoption_verdict` exactly as pre-registered in commit `237c2bcc`: per market,
**adopt** only with at least 300 paired holdout cases, MAE at least 1.0% lower than
`reference`, and the paired mean |error| difference below zero by more than 2
standard errors; fewer than 300 is `insufficient`; anything else is `reject`. Scored
once, `opp_goalie` against `reference`, on 2025-26. Development verdicts print but
count for nothing.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Pure adjustment** - `app/core/nhl_goalie_adjustment.py` with the
  constants above, a `GoalieRecord(saves, shots)` dataclass, `shrunk_save_pct`,
  `goalie_multiplier` and `adjusted_value(value, market, multiplier, beta)`; no DB,
  no I/O. *Done when:* tests cover zero prior shots reads the league value, a hot and
  a cold goalie move `m` in the right direction, both clip bounds, `beta = 0` returns
  the input, a non-adjusted market returns the input, and a league save percentage
  of 1.0 or 0 is rejected rather than dividing by zero.
- [x] **Step 2 - History rows carry the matchup** - `NhlHistoryRow` gains
  `team_id: int | None = None` and `opponent_team_id: int | None = None`;
  `_history_rows` and `_prior_rows` select them; `_HISTORY_GOALIE_COLUMNS` adds
  `shots_against`. *Done when:* existing NHL tests pass unchanged; a test builds rows
  with and without the new fields and shows `reference` and `last_10` replay cases
  are identical; the served `project_line` output is unchanged on a fixture.
- [x] **Step 3 - Point-in-time matchup in the replay** - a pure builder that walks
  history in date order and, for each skater case, yields the opposing starter's
  `GoalieRecord` over his last 20 prior starts and the league save percentage from
  starts before that date; `replay_cases` accepts an optional matchup-aware arm while
  the existing `Arm` signature and its cases stay byte-identical. *Done when:* tests
  cover the opponent's starter is picked (not the skater's own goalie, not a relief
  goalie), a same-day earlier game is excluded from both the goalie record and the
  league value, the 21st-oldest start is dropped, a missing starter gives `m = 1`,
  and an opposing-goalie arm scores exactly the same case keys as `reference`.
- [x] **Step 4 - CLI arms and report** - `opp_goalie_b05` and `opp_goalie_b10` in
  `ARMS` and the CLI; paired tables for opposing-goalie arms list `ADJUSTED_MARKETS`
  only; header lines for the opposing-goalie rule, the hindsight-starter caveat and a
  count of cases with no opposing starter row; a selection table that applies the
  selection rule to the printed MAEs. *Done when:* tests cover the arm parser, the
  report on tiny fixed cases (including the selection table and its tie rule) and
  that the holdout guard is unchanged (2024 only without `--holdout`).
- [x] **Step 5 - Pre-registration commit** - commit Steps 1-4 on the branch before
  any opposing-goalie arm is scored on any season, then record its hash as
  `OPP_GOALIE_PREREGISTRATION_COMMIT` and print it in the header. Needs a yes in
  chat to commit. *Done when:* the commit exists, its diff contains every constant
  above, and no scoring output exists yet.
- [x] **Step 6 - Development run and the committed pick** - run
  `python -m app.backtest.nhl_projections --season 2024 --arms reference,opp_goalie_b05,opp_goalie_b10`
  read-only; paste the output under Results; apply the selection rule; add
  `OPP_GOALIE_BETA_BY_MARKET` and the `opp_goalie` arm; commit before any holdout
  read (yes in chat). *Done when:* the run reads seasons 2023 and 2024 only (stated);
  a SQL spot check recomputes one goalie's shrunk save percentage on one game date to
  the replay's value; the pick per market is recorded with its MAE; the commit
  precedes Step 7.
- [x] **Step 7 - Holdout scoring run (separate yes in chat)** (skipped 2026-11-11: no candidate, every market picked 0; the holdout was not read) - if any market picked
  `beta > 0`, run once:
  `python -m app.backtest.nhl_projections --season 2025 --holdout --arms reference,opp_goalie`;
  paste the output and the verdict per market under Results. Not run without that
  yes, never re-run, and nothing is refit after it. If every market picked 0, skip
  the run and record "no candidate". *Done when:* each adjusted market reads `adopt`,
  `reject` or `insufficient`, and the seasons read (2024 and 2025) are stated.
- [x] **Step 8 - Docs and close-out** - `AGENTS.md` and `docs/commands.md` name the
  new arms and that `opp_goalie` has had its one holdout read; the interview guide
  (local, untracked) gets the finding if present; the build plan's 67b and 67c are
  confirmed or marked not built from the verdict. *Done when:* Verify passes and
  `/invariants-review` is clean.


## Results

**Development run (Step 6)**, `python -m app.backtest.nhl_projections --season 2024 --arms reference,opp_goalie_b05,opp_goalie_b10`
(2026-11-11, read-only transaction, about 100 s). Seasons queried: 2023 and 2024 only; no 2025-26 or
2026-27 row was read. Run after the rule was pre-registered in `2a74cfbf`.

- **Reference unchanged:** every `reference` row equals 56b's recorded 2024-25 run (Shots on Goal n 42,362, MAE 1.081; Points 0.550), so the history change in Step 2 moved nothing.
- **Coverage:** every one of the 42,362 skater games found its opposing starter row; none was scored with `m = 1`.
- **Spot check:** player 362949, game 63001 on 2025-01-15, opposing starter 363395. Replay: 481 saves on 542 shots over his last 20 starts, league .903085, shrunk .897591, `m` 1.0567. Raw SQL (his last 20 starts before the date, seasons 2023 and 2024, `REG`/`PST`; every start in those seasons before the date for the league): 481 of 542, league 108,465 / 120,105 = .903085. Equal.
- **Pick (the pre-registered rule):** `beta = 0` in all five markets. Both exponents raise MAE everywhere; the largest move is Shots on Goal at `beta` 1.0 (+0.27%), and Points, Assists and Goals change only in the fourth decimal. `OPP_GOALIE_BETA_BY_MARKET` records 0 for every market, so `opp_goalie` would equal `reference` and is not registered as an arm.
- **Read:** on this rule the opposing starter's save percentage carries no MAE gain for skater props. MAE rewards the median, and for low counts (Goals median 0, Points median 0 or 1) a few percent on the mean rarely moves the median, so MAE is a blunt test of a mean adjustment; that is a reason a later, separately pre-registered item might score the same input on a likelihood metric, not a reason to retune this one. Shots on Goal, the one market with room to move, got worse, as its prior expected.

```
NHL projection backtest, 2024-25 (development: replay and fit freely)

Pre-registered in commit 237c2bcc01caf68495c88982eedd4cdbf57da2a0.
Adopt a market only with >= 300 paired holdout cases, MAE at least 1% lower than reference, and a paired mean |error| difference below zero by more than 2 standard errors.
Cases: skaters with >= 10 prior games and >= 12 mean TOI minutes over the last 10; goalies who started with >= 5 prior starts; Faceoffs Won for centers only.
Goalie caveat: a goalie is a case only because he started, which is known after the game, so goalie error understates the uncertainty about who plays.
Opposing-goalie rule pre-registered in commit 2a74cfbfbdfb2a5c828f2251fbbbf4a4371689be.
Opposing-goalie arms (nhl-opp-goalie-v1): reference x m ** beta in shots_on_goal, points, assists, goals, power_play_points, where m = (1 - shrunk save %) / (1 - league save %) clipped to [0.80, 1.25], from the starter's last 20 prior starts shrunk by 1000 league-average shots. Per market, beta is the one of 0, 0.5 and 1.0 with the lowest 2024-25 MAE, ties to the smaller; a market that picks 0 is not a holdout candidate.
Opposing-goalie caveat: the starter is the goalie who actually started, known only after the game; the served version will use ESPN's expected starter, so these gains overstate what it can earn.
Skater games with no opposing starter row (scored with m = 1): 0 of 42362.


Arm opp_goalie_b05 against reference, paired on player, game and market
  market                         n   ref MAE   arm MAE   change     diff      SE  verdict
  shots_on_goal              42362     1.081     1.082   +0.09%   +0.001   0.000  reject
  points                     42362     0.550     0.550   +0.01%   +0.000   0.000  reject
  assists                    42362     0.425     0.425   +0.00%   +0.000   0.000  reject
  goals                      42362     0.280     0.280   +0.02%   +0.000   0.000  reject
  power_play_points          42362     0.174     0.175   +0.06%   +0.000   0.000  reject

Arm opp_goalie_b10 against reference, paired on player, game and market
  market                         n   ref MAE   arm MAE   change     diff      SE  verdict
  shots_on_goal              42362     1.081     1.084   +0.27%   +0.003   0.000  reject
  points                     42362     0.550     0.550   +0.05%   +0.000   0.000  reject
  assists                    42362     0.425     0.425   +0.03%   +0.000   0.000  reject
  goals                      42362     0.280     0.280   +0.07%   +0.000   0.000  reject
  power_play_points          42362     0.174     0.175   +0.13%   +0.000   0.000  reject

Exponent pick per market (lowest MAE, ties to the smaller beta)
  market                        beta 0    beta 0.5      beta 1    pick
  shots_on_goal                 1.0815      1.0824      1.0844       0
  points                        0.5502      0.5502      0.5504       0
  assists                       0.4252      0.4252      0.4253       0
  goals                         0.2801      0.2801      0.2803       0
  power_play_points             0.1744      0.1745      0.1747       0
```

**Holdout (Step 7):** no candidate. Every market picked `beta = 0`, so under the rule there is nothing to score and the 2025-26 holdout stays unread for this input.

## Files / areas

- `api/app/core/nhl_goalie_adjustment.py` (new, pure)
- `api/app/core/nhl_projection_backtest.py` (row fields, matchup builder, arms)
- `api/app/repositories/nhl.py` (`_history_rows`, `_prior_rows`, goalie columns)
- `api/app/backtest/nhl_projections.py` (arms, report, commit constant)
- `api/tests/test_nhl_goalie_adjustment.py` (new), existing NHL backtest and projection tests
- `AGENTS.md`, `docs/commands.md`, `blueprint/build-plan.md` (close-out only)

No migration: every column read already exists (0049).

## Data / contracts

Load-bearing for 67b and 67c, locked here:

- **Version string** `nhl-opp-goalie-v1`. A later change to any constant above ships
  as `-v2`; `-v1` never changes meaning.
- **`NhlHistoryRow.team_id` / `opponent_team_id`**, defaulted `None` so every
  existing constructor keeps working.
- **`GoalieRecord(saves: int, shots: int)`** and `goalie_multiplier(record, league)`:
  the one function 67b's served path will call, so the served number cannot drift
  from the backtested one (the same reason 56c1 imports 56b's arm).
- **Frozen rows (67b):** one extra `sport_prop_predictions` row per line in adopted
  markets with `model_version = 'nhl-opp-goalie-v1'`, `over_probability_version`,
  `p_over`, `p_under` and `edge` all NULL. The existing unique index
  `(prop_line_id, model_version, over_probability_version)` keeps it apart from the
  reference row; no migration.
- **56d isolation (67b's first step, before any new-version row is written):**
  `get_frozen_gradeable_lines` and `get_frozen_coverage` take
  `p.model_version = 'nhl-reference-v1'` before `DISTINCT ON`. Today they pick the
  newest row per prop across every version, so a later `nhl-opp-goalie-v1` row would
  replace the reference row and be dropped as `wrong_version`, shrinking 56d's
  sample. NFL hit the same thing and filters other versions out before picking the
  newest (`NOT_OTHER_MODEL` in `repositories/nfl.py`). A test shows a fixture with a
  later new-version row still grades the reference row and coverage is unchanged.
- **Served gating (67b):** a number only when the opponent side's goalie report is
  `confirmed` or `expected`, fresh, and linked; otherwise a null projection with a
  flag (`opp_goalie_unconfirmed`, `opp_goalie_stale`), never a silent fall back to
  the reference value. Skater injury gating is the reference's.
- **Forward rule (67c), pre-registered in its own commit before any 2026-27 row is
  graded:** regular-season 2026-27 lines in finished weeks where both versions froze
  a number for the same frozen line, settled against the box score; per market,
  `opp_goalie` against `reference` paired MAE under `nhl_adoption_verdict`'s
  thresholds. "Adopt" there makes the version a candidate for a later item (a P(over)
  fit, then a ranking check of its own); it never edits 56d.

## Testing

Test gate is on. Logic tests ship with Steps 1-4 (named in each done-when): the
adjustment math, the row extension leaving existing arms identical, the point-in-time
builder's exclusions, and the CLI report and selection table. Steps 6 and 7 are
evidence runs: pasted output, the seasons read, and one SQL spot check. No UI.

## Notes for the AI

- `core/` stays pure; repositories own the SQL; the CLI opens a `READ ONLY`
  transaction as 56b's does.
- **Holdout discipline:** never pass `--holdout` without a separate yes in chat in
  the current session, run it once, and refit nothing afterwards. 2026-27 outcomes
  are not read in 67a at all. 56c2 already read 2025-26 once for the reference
  projection's P(over) fit; no projection arm has been scored there (56b left it
  unread), so `opp_goalie`'s one read is still its first.
- **Pre-registration commits** (Steps 5 and 6) are cited by hash, so they merge with
  `--ff-only`, never squash (as 56b's `237c2bcc` did).
- Do not edit `REFERENCE_ARM`, `NHL_PROJECTION_REFERENCE_VERSION`, 56b's constants or
  `PREREGISTRATION_COMMIT`; the new rule gets its own constant.
- History reads stay bounded by `NHL_FIRST_HISTORY_SEASON`; the backtest reads only
  the two seasons `seasons_to_read` returns.
- 56d's check is accruing toward 200 picks with no verdict before about 2026-12-01.
  Nothing in 67a writes to `sport_prop_predictions` or touches its readers.
- Item 60b (projection history, another worktree) also touches NHL projection
  display; 67a touches none of it.
- No em dashes in code, docs or commits.

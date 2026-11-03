# Feature: Line anchor fit

**From build-plan:** feature 49b (NFL market-anchored prop model)
**Status:** complete (2026-11-03)
**Proposed branch:** `feature/nfl-volume-anchor`

## Goal

Turn 49a's receptions P(over) into a probability anchored to the PrizePicks
standard line, and fix the rule that will judge it before any outcome it will
be judged on exists. The blend is a log-odds blend of `nfl-volume-v1`'s
P(over) at the line with the line itself, fitted on 2026 weeks 1-8 only.

The deliverable is code and constants, not a result: tested adoption-rule
constants committed before week 9 settles, then the two fitted blend
constants frozen under their own version. No production change, no served
number, no verdict.

## Timing check (read 2026-10-30, read-only queries)

The week 9 deadline is **feasible but tight**: about five days, with a hard
dependency on week 8 results.

| Fact | Value |
|---|---|
| Today / season position | 2026-10-30, NFL week 8 under way (1 of 14 games final) |
| Week 8 last kickoff | Mon 2026-11-02 8:15 PM ET (2026-11-03 01:15 UTC) |
| Week 9 first kickoff | Thu 2026-11-05 8:15 PM ET (2026-11-06 01:15 UTC) |
| Settled stats stored | weeks 1-7 (receptions non-null on every row); week 8 not yet |
| Game lines (`spread_line`, `total_line`) | present for every game, weeks 1-9 |
| Week 9 lines stored | none yet (first snapshot arrives after this spec) |

PrizePicks line snapshots in `sport_prop_lines` for 2026 (all markets, all
payouts), and the standard full-game receptions player-games they cover:

| Week | Games | Snapshots | Lines | Receptions player-games (standard) |
|---|---|---|---|---|
| 1 | 1 | 2 | 912 | 7 |
| 2 | 16 | 5 | 20,449 | 117 |
| 3 | 16 | 4 | 15,663 | 115 |
| 4 | 16 | 8 | 23,318 | 127 |
| 5 | 15 | 7 | 30,025 | 109 |
| 6 | 14 | 5 | 22,001 | 104 |
| 7 | 14 | 5 | 22,250 | 104 |
| 8 | 14 | 2 so far | 10,132 | 65 so far |

(Snapshot counts are distinct fetch hours; every stored line was fetched
before its game's kickoff.) Weeks 1-7 give about 680 standard receptions
player-games already; week 8 adds roughly 100 more. Week 1 holds only 7
because the weekly snapshot schedule started after most week 1 games.
Goblin and demon receptions lines exist too (all weeks: standard 1,489 rows, goblin
4,564 and demon 9,620). No earlier season has any stored
line, so there is no 2025 or older line to fit on, which is why the fit
window is 2026.

**What can and cannot finish before kickoff of week 9:**

- The rule, the blend form and the fit window can be committed now, with no
  outcome read. This is the pre-registration that must beat the deadline.
- The fitted blend constants need week 8 settled and ingested (about
  2026-11-03 to 11-04). That leaves one to two days. If week 8 stats are not
  in the database by 2026-11-05 16:00 UTC, the fit uses weeks 1-7 and says so
  (owner's call at that time, recorded under Results); it never uses a later
  week.
- Frozen week 9 predictions do not exist: 49c (serve and freeze) is not built.
  Week 9 and later are graded as a deterministic replay from the stored
  last pre-kickoff line and pre-week inputs, which 49d reads. That is weaker
  than a kickoff freeze and is disclosed in the rule below.

## Scope

49a adopted **receptions only** as `nfl-volume-v1`. The other six markets
(passing attempts, completions and yards, receiving yards, rushing attempts
and yards) were rejected under a final verdict and are not tuned, rerun or
anchored here. 49b therefore covers the full-game receptions market, one
market, for the roster of positions `nfl-volume-v1` fits (RB, TE, WR).

## In scope

- **Anchor module** (pure, `app/core/`): the blend, a two-parameter logistic
  fit, and the adoption-rule constants, with tests.
- **A pre-registration checkpoint commit** of the rule and the blend form
  before any 2026 outcome is joined to a projection.
- **A read-only loader** for 2026 weeks 1-8 standard receptions lines and
  settled receptions, built on 49a's `get_volume_history` so the history
  floor holds.
- **A read-only CLI**, one recorded run after week 8 settles, then the
  fitted constants frozen as `nfl-volume-anchor-v1`.
- In-sample diagnostics of the fit (clearly labelled in-sample, no verdict).

## Out of scope

- Any of the six rejected markets, any change to `nfl-volume-v1`'s constants,
  grids, rule or verdicts, and any rerun of 49a's scoring.
- Serving, freezing, the slate, prop board, pages, schemas, 27j and
  `/nfl/model` (49c, 49d). No production caller imports the new modules.
- A forward verdict. The adoption rule is fixed here and applied in 49d.
- Changes to v4 (`opponent-dvp-tg-blend-usage-snap-v4`), Rec Targets, the
  27i rule, or `prop_ranking_rule.py`.
- Additional blend features (position, team, game total, line size) and any
  second candidate form. The form below is the only one.
- Migrations. Nothing is written to the database.

## Build loop

Build one step at a time, never the whole feature at once.

1. Lay out the step before code.
2. Implement only that step, with its tests.
3. Show the diff and evidence for its done-when.
4. The user reviews and approves before the next step, and may choose an
   optional checkpoint commit. `/complete` owns the feature-level commit.

## The blend and the pre-registered rule (locked in Step 1, before any outcome)

**Blend.** For a standard receptions line `L` on a player-game with an
`nfl-volume-v1` distribution `D`:

- `q_vol = P(over | no push) = p_over(L) / (p_over(L) + p_under(L))` from `D`.
- `logit(q) = a + b * logit(q_vol)`, clamped so `q_vol` lies in
  [0.001, 0.999] before the logit.
- The pushed mass is kept: `p_over = q * (1 - p_push)`,
  `p_under = (1 - q) * (1 - p_push)`.
- The line enters through `L` (the distribution is read at the line, and
  `a`, `b` are fitted on lines where the market's own price is roughly even).
  `b < 1` means the projection is shrunk toward the line's implied 50/50;
  `a` absorbs a systematic over or under lean.
- `a` and `b` are fitted by maximum likelihood on standard lines with
  non-push outcomes, 2026 weeks 1-8, one line per player-game: the last
  snapshot fetched before kickoff (27a's convention). Refuse to fit below
  400 non-push player-games. No regularisation, no other inputs.

**Adoption rule (applied in 49d, never in 49b).** The version string is
`nfl-volume-anchor-v1`. The slices are the same four as 27j: standard over,
standard under, goblin over, demon over, receptions only. A slice reads
`adopt` only if both hold on its fixed verdict sample:

1. **27i's pick rule passes unchanged.** Reuse `prop_ranking_rule`'s constants
   by import, so no second copy exists: pick margin 0.03 over the payout's
   break-even, 200 picks, 4 periods (weeks), 2 SE, and the shortest-run
   verdict sample. This is the hit rate at real lines against each payout's
   break-even.
2. **Log loss beats both references.** On every line of the slice's payout in
   the same weeks (not just picks), the blend's mean log loss on the realised
   non-push outcome is lower than the raw `nfl-volume-v1` `q_vol`'s and lower
   than a constant 0.5, each by more than 2 SE of the paired difference,
   clustered by game, and lower in at least 3 of the 4 sample weeks.

Otherwise `reject`, or `insufficient` while the sample is not yet fixed.
Verdicts are final for `nfl-volume-anchor-v1`; a changed constant is a new
version and a new sample. `a` and `b` are applied unchanged to goblin and
demon rungs even though they are fitted on standard lines only; that is an
extrapolation the log-loss clause is there to catch.

**Disclosures fixed now.**

- **2025 holdout:** 49b makes **no** read of it. The holdout read count
  stays at 9 (49a's run was the ninth). The CLI refuses any season below 2026.
- **Fit data is in-sample for the fit.** Weeks 1-8 hit rates and log loss are
  reported as diagnostics and carry no verdict.
- **Weeks 9 onward are a replay, not a kickoff freeze,** until 49c exists. The
  inputs are the stored last pre-kickoff line and pre-week stats, with
  `nfl-volume-v1` and the fitted `a`, `b` frozen, so the replay is
  deterministic. The one drift risk is a game line (`spread_line`,
  `total_line`) updated after the fact; 49d records the stored value it used.
- **Only counts were read before this spec:** snapshot, line and
  player-game counts and week dates. No outcome was joined to a projection,
  and no line was compared with a result.
- **Pre-registration commit:** `33c53e2575fe04754a6a12dfb33b295bd0b5cff6` (2026-10-30), made before any 2026 outcome was joined to a projection. Merge it
  `--ff-only`, never squashed, so the hash stays on `master`.

## Build steps

- [x] **Step 1 - Rule constants and blend (pure).** Add
  `app/core/nfl_volume_anchor.py`:
  - `NFL_VOLUME_ANCHOR_VERSION = "nfl-volume-anchor-v1"`, the market
    (`receptions`), the fit window (`ANCHOR_FIT_SEASON = 2026`, weeks 1 to 8),
    `ANCHOR_MIN_FIT_PAIRS = 400`, `ANCHOR_Q_CLAMP = 0.001`.
  - The log-loss clause's constants (2 SE, 3 of 4 weeks, the two references)
    and the import of 27i's constants from `prop_ranking_rule`.
  - `anchored_probability(q_vol, p_push, a, b)` returning over and under.
  - A refusal for any market other than receptions, and for a distribution
    that is not from `nfl-volume-v1`.

  *Done when:* unit tests prove: `b = 1, a = 0` returns `q_vol` unchanged;
  `b = 0` returns 0.5 plus `a`; over plus under plus push equals 1; the
  clamp holds at 0 and 1; the rule constants equal the values above and
  27i's; every non-receptions market raises; the rule module does not
  import any I/O, DB or model-loading code.

- [x] **Step 2 - The fit (pure).** In the same module, add
  `fit_anchor(pairs)` taking `(q_vol, over_outcome)` pairs and returning
  `a`, `b`, standard errors and the pair count, by Newton-Raphson
  maximum likelihood on the two parameters.

  *Done when:* synthetic tests prove: it recovers known `a`, `b` from
  simulated outcomes within tolerance; it returns `b` near 0 when outcomes
  are independent of `q_vol`; fewer than `ANCHOR_MIN_FIT_PAIRS` raises;
  pushes and null outcomes are excluded by the caller, and a perfectly
  separated sample raises rather than returning infinite constants; ties on
  the line (several snapshots) are the caller's job, not this function's.

- [x] **Step 3 - Pre-registration checkpoint.** Show the owner the Step 1 and
  2 diff and the rule above. With the owner's yes in chat, make a checkpoint
  commit of the rule, the blend form and the fit code, before the loader or
  any 2026 outcome is touched. Record its hash under "Pre-registration
  commit" above. It merges `--ff-only`.

  *Done when:* the commit exists, `git log` shows it before any Step 4 code,
  and its hash is recorded in this file. Target: before 2026-11-06 01:15 UTC
  (week 9 first kickoff), and ideally this week.

- [x] **Step 4 - Read-only loader.** Add `app/repositories/nfl_volume_anchor.py`
  with `get_anchor_lines(db, season, first_week, last_week)` returning, for
  each player-game, the last standard full-game receptions line fetched
  before kickoff, the player's team and position, and the settled
  receptions (null when not settled). Pre-week player history comes from
  49a's `get_volume_history`, bounded below by
  `VOLUME_FIRST_HISTORY_SEASON` (2018), never an unbounded read and never
  v4's 2024-floored readers. The season is passed in and a season below
  2026 is refused.

  *Done when:* recorded-SQL tests prove: `sport = 'nfl'` on every
  shared-table alias; `fetched_at < start_utc`; standard odds type and
  full-game segment only; one row per player-game; a null result stays
  null; the season floor is present in the history query; no coalesce
  of a missing stat to zero.

- [x] **Step 5 - CLI and one recorded run.** Add
  `app/backtest/nfl_volume_anchor.py`. It takes no season, window, market or
  tuning option. It projects each loaded player-game with
  `nfl-volume-v1`, joins settled outcomes (skipping unsettled games and
  rookies or players the projection refuses, and counting them), fits
  `a`, `b`, and prints the pair count by week, `a`, `b` and SEs, and the
  in-sample diagnostics (log loss of blend, raw and 0.5; hit rate at each
  payout's break-even; a calibration table), all marked in-sample. It
  writes nothing and `--help` works without a database. Run it once, after
  week 8 is settled and ingested.

  *Done when:* report tests show every column and the in-sample label;
  `--help` exits before any database import; the run is recorded under
  Results with command, date, elapsed time, coverage and exclusions. A
  transient DB failure may be retried identically; nothing else may be rerun.

- [x] **Step 6 - Freeze.** Record the fitted `a`, `b` as
  `NFL_VOLUME_ANCHOR_PARAMETERS` in the anchor module, with a test pinning
  the values, and record whether the fit used weeks 1-8 or the weeks 1-7
  fallback. Commit before 2026-11-06 01:15 UTC. If the fit refuses or the
  sample is below 400 pairs, record that and stop.

  *Done when:* Results explain the fit and the frozen values match the
  recorded run; no production caller imports the new modules; v4, Rec
  Targets and `nfl-volume-v1` constants are unchanged against `master`; the
  full Verify gate passes. Update the employer interview guide (local,
  ignored, never staged), calling the anchor fitted and not yet judged.

## Files / areas

- `api/app/core/nfl_volume_anchor.py` (new)
- `api/app/repositories/nfl_volume_anchor.py` (new)
- `api/app/backtest/nfl_volume_anchor.py` (new)
- `api/tests/test_nfl_volume_anchor.py`,
  `test_nfl_volume_anchor_repository.py`,
  `test_nfl_volume_anchor_harness.py` (new)
- No edit to `nfl_volume_projection.py`, `prop_ranking_rule.py`, v4 or Rec
  Targets modules, or any migration.

## Data / contracts

- **No schema change and no database write.**
- **Load-bearing for 49c and 49d:** `NFL_VOLUME_ANCHOR_VERSION`,
  `anchored_probability(q_vol, p_push, a, b)`, the frozen
  `NFL_VOLUME_ANCHOR_PARAMETERS`, and the rule constants. 49c serves the
  anchored over and under; 49d applies the rule. These signatures do not
  change after Step 6.
- **History floor (invariant 11):** every history read bounds the season from
  below with the named constant `VOLUME_FIRST_HISTORY_SEASON = 2018` that
  49a defined, via `get_volume_history`.
- **Inputs are the stored last pre-kickoff line,** with team volume from the
  stored game `spread_line` and `total_line`. 49a's backtest used closing
  lines; this is the first fit on the production-style inputs.

## Testing

The test gate is on. Steps 1, 2, 4 and 5 ship unit tests in the same diff:
the blend and fit (synthetic data), the loader (recorded SQL), and the report.
No test touches the database or the network. Steps 3 and 6 are evidence and
commit steps. The full Verify command
(`npm --prefix web run verify && cd api && python -m pytest`) is the final gate.

## Notes for the AI

- `app/core/` stays pure; the fit is plain Newton-Raphson, no model loading.
- Reuse: `project_player`, `NFL_VOLUME_V1_PARAMETERS`,
  `NegativeBinomial.p_over` (over, under and push), `get_volume_history`,
  `prop_ranking_rule` constants, 27a's last-snapshot convention
  (`one_call_per_player_game`).
- The six rejected markets must not appear in any table, loop or flag.
- No rule or constant changes after the Step 3 commit; a change is a new
  version, never an edit.
- No em dashes in new content. Comment the why only.
- Windows: run Python from the API venv in the main checkout
  (`C:\dev\SportAppV2\api\.venv`), with the selector event loop for async CLIs.
  The worktree has no `api/app/.env`; the DB URL comes from the main
  checkout's, passed through the environment, never printed.
- Merge any commit later work cites with `--ff-only`, never squash.

## Results

### Step 5 - the recorded run (2026-11-03)

**Data.** Week 8 was not stored on 2026-11-03 16:09 UTC (13 of 14 games
completed, no week 8 stat rows). With the owner's yes, `python -m
app.ingest.nflverse --season 2026` was dry-run (8,420 player-weeks), then run
for real: 14 of 14 week 8 games completed and 980 week 8 player-week rows.
The fit therefore uses weeks 1-8, not the weeks 1-7 fallback.

**Command:** `python -m app.backtest.nfl_volume_anchor` from `api/`, code at
`1ffedc97`. Started 2026-11-03 16:28:22 UTC, ended 16:28:36 UTC, exit 0,
elapsed 11 s. Run once; no retry or rerun.

**Coverage:** 793 standard receptions lines loaded, 48,420 player-games of
history (2018-2026). 698 fit pairs (minimum 400).

| Week | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| Fit pairs | 5 | 101 | 100 | 112 | 95 | 93 | 96 | 96 |
| Unsettled | 0 | 6 | 3 | 8 | 4 | 4 | 3 | 10 |

**Exclusions:** 55 pushes (receptions equal the line), 38 unsettled (no
result, or did not play), 2 with no player-game with closing lines. None had
no volume forecast.

**Fit** (`logit(q) = a + b * logit(q_vol)`):

| Constant | Value | SE |
|---|---|---|
| a | -0.0136 | 0.0796 |
| b | +0.4341 | 0.1269 |

**Diagnostics (in-sample, no verdict):**

| Measure | Value |
|---|---|
| Log loss, blend | 0.6834 |
| Log loss, raw `nfl-volume-v1` | 0.6973 |
| Log loss, constant 0.5 | 0.6931 |
| Observed over rate | 47.7% |
| Picks clearing 57.7% + 3.0% | 57 picks, 43 hits (75.4%) |

| Bin | Pairs | Mean blended P(over) | Over rate |
|---|---|---|---|
| 1 | 139 | 38.5% | 35.3% |
| 2 | 140 | 44.7% | 50.7% |
| 3 | 139 | 47.8% | 54.0% |
| 4 | 140 | 50.9% | 42.9% |
| 5 | 140 | 56.5% | 55.7% |

- **Reading it.** `b` of 0.43 (SE 0.13) says the raw projection is overconfident
  against these lines: it is shrunk more than half the way toward 50/50. Raw
  volume is slightly worse than a constant 0.5 on log loss (0.6973 against
  0.6931), and the blend is slightly better (0.6834). The picks hit rate is
  fitted data, so it says nothing about the forward sample.
- **Closing versus pre-kickoff lines.** Team volume here used the stored game
  `spread_line` and `total_line`, the values on file now.

### Step 6 - freeze (2026-11-03)

`NFL_VOLUME_ANCHOR_PARAMETERS = AnchorParameters(a=-0.0136, b=0.4341)` in
`app/core/nfl_volume_anchor.py`, pinned by `test_nfl_volume_anchor.py`. The fit
used weeks 1-8 (not the weeks 1-7 fallback). The CLI prints four decimals and
its one run is not repeated, so the frozen values are the printed ones.
Checks: only the 49b anchor modules import the new code (no production
caller), and `nfl_volume_projection.py`, `prop_ranking_rule.py`, v4 and Rec
Targets are unchanged against `master`. The adoption rule in this spec is
applied in 49d, to weeks 9 onward.

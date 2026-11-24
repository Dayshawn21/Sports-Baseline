# Feature: Usage-shift arm, pre-registration and development run

**From build-plan:** feature 70b3 (parent 70b, Usage-shift backtest arm; feature 70, Injury-aware NFL projections)
**Status:** complete (2026-11-22). No market adopted on the 2025 holdout (all `insufficient`; receiving 17-22% worse), so 70c and 70d are not built. Rule pre-registered in `a0941c32`, pick in `43198da1`. Verify passed (1874 web tests, typecheck, build; 6653 API tests).
**Branch:** `feature/70b3-usage-shift-arm` (worktree `.claude/worktrees/70b3-usage-shift-arm`)

## Goal

Find out whether moving a freshly Out starter's carries or targets to the
teammate who takes his place makes that teammate's projection closer to what
happened. Add the `usage_shift` arms to the NFL projection replay, commit the
selection rule and the pass rule to git before anything is scored, pick each
market's `transfer` on 2024, and score the pick once on the 2025 holdout only
after a separate yes. The verdict per market decides whether 70c is built.

## What exists (read 2026-11-22)

- **70b2's pure pieces:** `usage_shifts(players, transfer, min_own_volume,
  max_multiplier)` and `apply_usage_shift(row, shift)` in
  `app/core/nfl_usage_shift.py`; `ReplayRow.usage_shift_players` carries the
  row's own team-position list. No parameter has a default.
- **Arms:** `ARMS` in `app/backtest/nfl_projections.py` maps a name to
  `(row, season) -> row`, so an arm sees only `replay.row`, not
  `replay.usage_shift_players`. `replay_cases` projects each transformed row
  through `_slate_line` and keeps rated rows (`edge_is_comparable`).
- **That CLI defaults to `--season 2025`** and prints paired errors, so it reads
  the holdout by default. 70b3 does not run it.
- **Adoption rule:** `adoption_verdict` (pre-registered 2026-09-26) needs at
  least 300 paired cases per market. 70b2's counts at illustration parameters:
  24 shiftable rows per rushing market and 139 per receiving market in 2024.
- **Pattern to follow:** 67a (NHL opposing goalie): a development grid, a
  selection rule and a holdout rule committed in their own commit, the hash
  printed in the report header, then one holdout read per candidate.

## Design (decisions to confirm at review)

1. **Scored on shifted rows only.** An unshifted row's projection is identical
   in both arms by construction, so pairing all rows only dilutes the
   difference. Every comparison pairs the variant's shifted cases with
   production's cases on the same player, game and market.
2. **Fixed, not tuned:** `USAGE_SHIFT_MIN_OWN_VOLUME = 2.0` carries or targets
   per game, `USAGE_SHIFT_MAX_MULTIPLIER = 3.0`. The cap stays at 3.0 because a
   backup taking a full workload really does triple his carries (Mattison, 2024
   week 5); `min_own_volume` rises from 70b2's illustrative 1.0 so a backup on
   one carry a game is not scaled from noise.
3. **Development grid:** `transfer` in `{0.5, 1.0}` as arms
   `usage_shift_t05` and `usage_shift_t10`; `transfer = 0` is production.
4. **Selection rule (2024 only):** per market (rushing yards, rushing attempts,
   receiving yards, receptions), pick the `transfer` among 0, 0.5 and 1.0 with
   the lowest MAE on that market's shifted rows, ties to the smaller. A market
   that picks 0 is not a holdout candidate. The picks become
   `USAGE_SHIFT_TRANSFER_BY_MARKET` and one `usage_shift` arm, committed before
   any holdout read.
5. **Holdout rule (2025, once per candidate market):** adopt only with at least
   `USAGE_SHIFT_MIN_SHIFTED_CASES = 60` paired shifted cases (set 2026-11-22 from Step 4's counts, was 100), MAE on those
   cases at least 1.0% lower than production, and a paired mean |error|
   difference below zero by more than 2 standard errors. Otherwise reject, or
   `insufficient` below 60. The 1% and 2 SE match the existing rule; only the
   minimum is new, sized to one season's rated receiving sample.
6. **Rushing is stated up front as unadoptable from one holdout season.** About
   15 rated shifted rows a season sits far under 60, so a rushing pick reads
   `insufficient` by design. It is still scored on 2024 and reported, never
   adopted. Pooling rushing yards with attempts is ruled out: the errors are in
   different units.
7. **A separate CLI**, `python -m app.backtest.nfl_usage_shift`: 2024 by
   default, any other season refused, 2025 only with `--holdout` and only for
   the committed `usage_shift` arm. `nfl_projections` and its defaults stay as
   they are.

## In scope

- Arms that read `ReplayRow.usage_shift_players`, with a shifted flag on each
  case.
- The pure selection and holdout verdict functions with their constants.
- The new CLI, its season guard and its report.
- The pre-registration commit, the 2024 development run and the committed pick.
- One holdout run, only after a separate yes, and only if a market picked
  `transfer > 0`.

## Out of scope

- Serving, freezing or a model version (70c), and the forward check (70d).
- Any change to `adoption_verdict`, its constants or the 2026-09-26 rule.
- Retuning `min_own_volume` or the cap after any score is seen.
- QB, passing, fantasy and anytime TD markets; cross-position effects.
- Changing `nfl_usage_shift.py`'s behavior or 70a's `role_changed` guard.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Replay arms that see the players.** `replay_cases` accepts
  arms of the form `(replay, season) -> row` beside the existing
  `(row, season)` ones (existing arms wrapped, unchanged). `ReplayCase` gains
  `shifted: bool = False`, true when the transformed row carries
  `usage_shift`. New module `app/core/nfl_usage_shift_rule.py` holds the two
  fixed constants and the grid; `usage_shift_arm(transfer)` returns the arm
  `apply_usage_shift(_production(row), shift)` for the row's player.
  *Done when:* tests show an unshifted row gives the same case as production
  with `shifted=False`; a fresh-Out fixture gives a larger rushing projection
  with `shifted=True`; all seven existing arms give identical cases.
- [x] **Step 2 - Selection and holdout rules (pure).** In
  `nfl_usage_shift_rule.py`: `shifted_paired(production, variant)` (paired on
  the variant's shifted cases), `pick_transfer(mae_by_transfer)` (lowest, ties
  to the smaller, 0 allowed) and `usage_shift_verdict(diff)` with
  `USAGE_SHIFT_MIN_SHIFTED_CASES` (60), reusing the existing 1% and 2 SE
  constants. *Done when:* tests cover the shifted-only pairing (unshifted cases
  excluded), a tie picking the smaller, a pick of 0, and each verdict
  (insufficient at 99, reject on 1% with 1.9 SE, adopt).
- [x] **Step 3 - The CLI and its guard.** `app/backtest/nfl_usage_shift.py`:
  development runs `production,usage_shift_t05,usage_shift_t10` on 2024 and
  prints, per market, shifted n, MAE for 0, 0.5 and 1.0, the pick, and a header
  with the rule text and the pre-registration commit. `--holdout` runs 2025
  with `production,usage_shift` only and prints the verdict per candidate
  market. Any other season, or `--holdout` without a committed pick, exits with
  a message. *Done when:* tests cover the report on fixed cases, the pick table
  and the guard (2025 without `--holdout`, 2023, `--holdout` with no pick).
- [x] **Step 4 - Rated-row counts at the fixed constants (2024, counts only).**
  `--count-only` on the new CLI prints, per market, how many 2024 rows the
  `t10` arm shifts after `edge_is_comparable` at `min_own_volume = 2.0`, plus
  rows with no closing moneyline; no projection, error or actual. If receiving
  falls under the minimum a season, stop and revisit the minimum with you before
  anything is committed. *Done when:* the counts are under Results.
- [x] **Step 5 - Pre-registration commit (yes in chat).** Commit Steps 1-4 on
  the branch before any scored run; record the hash as
  `USAGE_SHIFT_PREREGISTRATION_COMMIT` (a follow-up commit) and print it.
  *Done when:* the commit exists and its diff contains both fixed constants,
  the grid, the selection rule and the holdout rule.
- [x] **Step 6 - Development run and the committed pick (yes in chat).** Run
  `python -m app.backtest.nfl_usage_shift` on 2024 (slow, about 15+ minutes,
  foreground with keep-awake); paste the output under Results; apply the
  selection rule; set `USAGE_SHIFT_TRANSFER_BY_MARKET` and register the
  `usage_shift` arm; commit before any holdout read. *Done when:* the pick per
  market is recorded with its MAE and n, and the pick commit exists. If every
  market picks 0, Step 7 is skipped and the holdout stays unread.
- [x] **Step 7 - Holdout run (separate yes in chat).** Only if a market picked
  `transfer > 0`: run once with `--season 2025 --holdout`; paste the verdicts.
  *Done when:* each candidate market has a recorded verdict; no second holdout
  run happens.
- [x] **Step 8 - Verify, docs and plan notes.** CLI in `docs/commands.md` and
  `AGENTS.md`; the interview guide's 70 passage if the file exists; the build
  plan's 70c and 70d lines note the verdict (built only for adopted markets, or
  dropped). Run `npm --prefix web run verify && cd api && python -m pytest`.
  *Done when:* Verify passes.

## Files / areas

- `api/app/core/nfl_usage_shift_rule.py` (new, pure)
- `api/app/core/nfl_projection_backtest.py` (`ReplayCase.shifted`)
- `api/app/backtest/nfl_projections.py` (`replay_cases` accepts replay-level arms)
- `api/app/backtest/nfl_usage_shift.py` (new CLI)
- `api/tests/test_nfl_usage_shift_rule.py`, `api/tests/test_nfl_usage_shift_backtest.py` (new)
- `docs/commands.md`, `AGENTS.md`, `blueprint/build-plan.md`

## Data / contracts

- **Load-bearing for 70c:** `USAGE_SHIFT_TRANSFER_BY_MARKET`,
  `USAGE_SHIFT_MIN_OWN_VOLUME`, `USAGE_SHIFT_MAX_MULTIPLIER` and
  `USAGE_SHIFT_PREREGISTRATION_COMMIT`; 70c serves exactly these values in the
  adopted markets.
- `ReplayCase.shifted` defaults to False, so every existing caller is
  unchanged.
- No schema change and no stored data.

## Testing

- Pure: Step 1's arm on fixtures, Step 2's rules, Step 3's report and guard.
- Regression: the seven existing arms give identical cases.
- The scored runs are evidence, not tests, and never part of Verify.

## Notes for the AI

- **Holdout discipline:** never run `python -m app.backtest.nfl_projections`
  here. Nothing reads 2025 before the pick commit, and Step 7 needs its own yes.
- **Merge with `--ff-only`** at `/complete`, never squash, so the
  pre-registration and pick commits stay reachable on master (memory:
  pre-registration merge). If it lands as a squash, tag `prereg/70b3`.
- Freeze the rule before scoring: no change to the constants, grid or rules
  after Step 5 except recording the pick. If a bug forces a change, stop, say
  so, and make a new pre-registration commit before any rerun.
- In Step 4, check how many 2024 replay rows lack a closing moneyline
  (`home_market_prob` None); production and the arms share it, so it does not
  bias the pairing, but record the count.
- The shifted count after `edge_is_comparable` can be below 70b2's counts,
  which were taken before that filter and at `min_own_volume = 1.0`.
- The 2024 chart can omit a real starter (MIA week 2 has no Achane); read the
  2024 numbers knowing it.
- Served code stays unchanged: nothing in `app/services/` imports the new
  module.
- No em dashes in new comments, docs or commit messages.

## Results

### Step 1 - replay arms

`usage_shift_arm(transfer)` lives in `app/backtest/nfl_projections.py`, not the
core module, because it stacks on `_production`, which lives there; the core
module `nfl_usage_shift_rule.py` holds the two fixed values, the grid and the
arm names. `REPLAY_ARMS` (`usage_shift_t05`, `usage_shift_t10`) sit beside
`ARMS`, so `nfl_projections`' own CLI still refuses them. A case is `shifted`
only when its multiplier is not 1.0 (a receiver below the minimum gets a
`usage_shift` key at 1.0 and is not shifted). Tests: 7 new in
`tests/test_nfl_projection_harness.py`; all 1,964 NFL tests pass.

### Step 2 - selection and holdout rules

`shifted_paired`, `pick_transfer` and `usage_shift_verdict` in
`app/core/nfl_usage_shift_rule.py`, with `USAGE_SHIFT_MIN_SHIFTED_CASES = 100` (60 since Step 4)
and the existing 1% and 2 SE constants imported, not copied. Transfer 0's MAE is
production's on the same shifted keys, so all three grid points are judged on
one set of rows. Tests: 9 in `tests/test_nfl_usage_shift_rule.py`.

### Step 3 - the CLI and its guard

`app/backtest/nfl_usage_shift.py`: the development run scores `production,
usage_shift_t05, usage_shift_t10` on 2024 and prints a pick table per market;
`--holdout` scores `production, usage_shift` on 2025 with a verdict per candidate
market. `season_error` refuses 2025 without `--holdout`, any other season, and
`--holdout` before a committed pick above 0. `USAGE_SHIFT_PREREGISTRATION_COMMIT`
(None) and `USAGE_SHIFT_TRANSFER_BY_MARKET` (empty) live in the rule module; the
`usage_shift` arm is registered only once a market picks above 0, so it does not
exist yet. `SHIFT_MARKETS` added to `nfl_usage_shift.py` (a constant, no
behavior change). Tests: 10 in `tests/test_nfl_usage_shift_backtest.py`; all
1,983 NFL tests pass. `--season 2025` exits with the holdout message.

### Step 4 - rated-row counts (2024, counts only)

`python -m app.backtest.nfl_usage_shift --count-only`, 2026-11-22, arm
`usage_shift_t10`, `min_own_volume = 2`, cap 3; no projection, error or actual
printed:

```
Replay rows: 22056; without a closing moneyline: 0

  market                 rated  shifted
  rushing_yards           1417       15
  rushing_attempts        1023       15
  receiving_yards         3363       76
  receptions              3363       76
```

**Receiving falls under the 100-case minimum (76 a season)**, so per this step
the minimum is revisited with the owner before the pre-registration commit.
Every 2024 replay row has a closing moneyline.

**Decision 2026-11-22 (owner):** lower the holdout minimum from 100 to 60
shifted cases, leaving room for 2025 to run a little under 2024's 76. The 1%
and 2 SE requirements are unchanged, so only a large gain passes. Rushing stays
unadoptable (15 a season).

### Step 5 - pre-registration commit

Pre-registered in commit `a0941c328d1f14651a88842cbd1db8af0c1a878d`
(2026-11-22), after Verify passed (web typecheck, tests and build; 6,652 API
tests). Its diff holds both fixed values, the grid, the selection rule and the
holdout rule with the 60-case minimum. A follow-up commit sets
`USAGE_SHIFT_PREREGISTRATION_COMMIT` and the report header prints it. No
usage-shift arm has been scored on any season.

### Step 6 - development run and the committed pick

`python -m app.backtest.nfl_usage_shift`, 2026-11-22, 2024 only, under commit
`a0941c32`; no 2025 row read:

```
Transfer pick per market (MAE on shifted rows)
  market                   n       t 0     t 0.5       t 1    pick
  rushing_yards           15    15.645    15.844    26.349       0
  rushing_attempts        15     4.135     3.014     4.887     0.5
  receiving_yards         76    26.098    25.424    26.133     0.5
  receptions              76     1.939     1.844     1.882     0.5
```

- **Pick (the pre-registered rule):** 0.5 in rushing attempts, receiving yards
  and receptions; 0 in rushing yards, which is not a holdout candidate. Now
  `USAGE_SHIFT_TRANSFER_BY_MARKET`, and the `usage_shift` arm exists.
- **Read:** half the Out starter's volume beat both none and all of it in three
  markets; a full transfer overshoots everywhere, worst in rushing yards (MAE
  15.6 to 26.3 on 15 rows). The receiving gains on 2024 are 2.6% (yards) and
  4.9% (receptions) on 76 rows, picked on the same rows, so they are not
  evidence by themselves; the holdout decides.
- **Expected holdout outcome for rushing attempts:** about 15 shifted rows a
  season, so it reads `insufficient` under the 60-case minimum by design.

**Holdout incident, 2026-11-22.** Once the pick made `usage_shift` exist,
`test_cli_refuses_the_holdout_without_a_committed_pick` stopped being refused:
`main()` passed the guard and ran the real 2025 holdout scoring inside the API
test suite (the suite took 58 minutes instead of 3). pytest captured the
report and the command kept only the last two lines (`tail -2`), so the
verdicts were never displayed, written to a file or read by anyone; only the
summary `1 failed, 6652 passed` was seen. The picks above were set before that
run and are unaffected. Fix: the test pins an empty pick, and an autouse
fixture in `tests/test_nfl_usage_shift_backtest.py` replaces `_main` and
`_count`, so no CLI test can reach the database again (12 tests pass in 3 s).
Whether this counts as the one holdout read is the owner's call.
**Decision 2026-11-22 (owner): treat the 2025 holdout as unread**, since no
verdict was seen; the one deliberate holdout run is still Step 7, with its own
yes.

### Step 7 - holdout run (the one 2025 read)

`python -m app.backtest.nfl_usage_shift --season 2025 --holdout`, 2026-11-22,
once, under commits `a0941c32` (rule) and `43198da1` (pick):

```
Committed usage_shift against production on shifted rows
  market               transfer     n  prod MAE   var MAE   change     diff      SE  verdict
  rushing_yards               0    not a candidate
  rushing_attempts          0.5    13     6.602     5.617  -14.92%   -0.985   1.403  insufficient
  receiving_yards           0.5    49    25.289    30.804  +21.81%   +5.516   2.398  insufficient
  receptions                0.5    49     1.909     2.230  +16.79%   +0.321   0.207  insufficient
```

- **Verdict: no market adopts.** Every candidate is under the 60-case minimum
  (2025 shifted 49 receiving rows a market against 2024's 76, and 13 rushing).
- **Read beyond the rule:** the receiving shift made projections worse on the
  holdout (MAE +21.8% in yards and +16.8% in receptions, the yards difference
  2.3 standard errors above zero), reversing 2024's small gains, which were
  picked on the same rows. Rushing attempts improved on 13 rows, well inside
  noise. Moving an Out starter's targets to his chart backup does not hold up;
  the likely reason is that targets spread across the whole receiving room,
  while the chart names one successor.
- **Consequence:** 70c and 70d are not built, and 70a's `role_changed` guard
  stays as the permanent behavior, as the build plan set out.

### Step 8 - Verify, docs and plan notes

Verify passed 2026-11-22: web typecheck, 1,874 tests and build; API 6,653
passed. The CLI is in `docs/commands.md` and `AGENTS.md` with the spent-holdout
note; the build plan's 70c and 70d lines are marked not built; the interview
guide's Walker passage now describes the test and its rejection.

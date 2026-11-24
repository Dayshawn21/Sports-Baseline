# Feature: NHL over-probability fit

**From build-plan:** feature 56c2 (second of 56c's four parts; 56c1 served the projection, 56c3 serves P(over), 56c4 freezes)
**Status:** complete (2026-11-05)
**Branch (for /implement):** `feature/nhl-over-probability-fit` (already created from `origin/master`)

## Goal

Turn the served `nhl-reference-v1` projection into a probability that the result lands over a line, per market, and decide which markets may show it. The distribution is selected and fitted on the 2024-25 development season, then checked **once** on the 2025-26 holdout under a rule committed to git before any fit runs. Markets that pass are frozen into a generated module. **Nothing is served here:** 56c3 shows it, 56c4 freezes it.

**Why this is not a copy of 20g1:** NBA's first method (ratio quantiles of actual over projection) hid 8 of 9 markets, and 44a then needed count distributions and a second holdout-style read to recover them. NHL stats are small counts (Goals averages about 0.3, Power Play Points about 0.17) where a ratio is unstable, so this spec registers the whole candidate list and selection rule up front: ratio, negative binomial and scaled normal are all tried on development data, one family per market is chosen there, and the holdout is read once for that choice alone. A failed market stays hidden, as NBA's did; it does not get a second read.

## Design reference

None. A CLI report and a generated module, no UI.

## In scope

- **Pre-registration, its own commit, first (Step 1).** Before any fit code or run, one commit holds the rule as constants and text in `app/core/nhl_over_probability.py`: versions, candidate list and order, selection rule, confirmation rule, display rule, domain rules, holdout statement. A later reader must be able to show that commit precedes every fit and every holdout read.
- **Versions, fixed now:** `NHL_PROJECTION_MODEL_VERSION` stays `nhl-reference-v1` (56b's `NHL_PROJECTION_REFERENCE_VERSION`); `NHL_OVER_PROBABILITY_VERSION = "nhl-pover-v1"`. One version covers every shown market; the generated module records each market's selected family.
- **Candidate families, in tie-break order:** `negbin`, `scaled_normal`, `ratio`. Reused unchanged and sport-agnostic: `app/core/count_over_probability.py` (negbin, scaled normal), `ratio_quantiles` and `over_probability` from `app/core/nfl_over_probability.py`, and `synthetic_lines`, `calibrate`, `normal_over_probability` from `app/core/nfl_over_probability_calibration.py`.
- **Domain rules (registered):** `negbin` for every market except `plus_minus` and `time_on_ice` (negative or non-count values); `scaled_normal` for every market; `ratio` for every market except `plus_minus` (a non-positive projection has no ratio). The 12 markets are `NhlLineOnlyMarket`; goalie markets use started-game cases only, exactly 56b's replay.
- **Selection (development, 2024-25 only, free to rerun):** each family is cross-fitted by ISO-week parity of `game_date` (fit on one half, score the other, both ways, pooled), at 20g1's synthetic x.5 lines. A family is eligible only if it passes the display rule there. The eligible family with the lower Brier is selected, a tie going to the earlier one in the candidate order. A market with no eligible family is hidden and **never touches the holdout**.
- **Confirmation (holdout, 2025-26, once):** the selected family and parameters, fitted on all of 2024-25, scored on 2025-26 under the same display rule. Markets that pass are `show`; the rest are `hide`. This is the holdout's first read (56b made none).
- **Display rule (NHL's own constants, copied from NBA's 20g1 and 27g):** at least 300 cases, ECE at most 0.02, worst bin gap at most 0.05 for bins with at least 200 pairs, and Brier no worse than the constant-sigma normal's. Verdicts `show`, `hide`, `insufficient`.
- **Integer lines:** v1 reads None for them (a push is possible and is not modelled), flagged `integer_line` when 56c3 serves it, as NBA's `integer_line`. Goalie Saves and Goals Allowed post integer standard lines, so the report states how many synthetic lines this affects; handling pushes is a later, separately pre-registered item.
- **Generated module** `app/core/nhl_over_probability_fit.py` (never hand-edited): `FIT_SEASON`, `SCORED_SEASON`, `FIT_PROJECTION_MODEL_VERSION`, `OVER_PROBABILITY_VERSION`, `PRE_REGISTRATION_COMMIT`, `SHOWN_MARKETS`, and per shown market its family and parameters, all from the 2024-25 fit that was scored.
- **CLI** `python -m app.backtest.nhl_over_probability_fit`: default is the development selection report; `--confirm` runs the one holdout read and needs `--holdout`; `--write` renders the module and is accepted only with a completed `--confirm`.

## Out of scope

- Serving P(over) anywhere, schema or page changes (56c3); frozen predictions, `NhlPropSource`, workflows (56c4).
- Ranking, edges, break-even comparison, the Model page (56d).
- Push handling for integer lines, splits beyond market (position, TOI, home or away), refitting on 2025-26 for serving, and a second family search after the holdout. A hidden market stays hidden until a new version is pre-registered.
- Changes to 56b's backtest module or its pre-registered rule (`237c2bcc`).
- Any read of 2026-27 outcomes or stored prop lines for fitting.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

**Commit and merge rule for this feature:** Step 1's pre-registration commit is made on its own and every later step commits after it. `/complete` must merge this branch **fast-forward only**, never squash, so the cited pre-registration commit keeps its hash on `master`.

## Build steps

- [x] **Step 1 - Pre-registration (own commit, before any fit)** - `app/core/nhl_over_probability.py` with only the registered rule: the two versions, `CANDIDATE_ORDER`, domain rules per market, `FIT_SEASON = 2024`, `CONFIRMATION_SEASON = 2025`, the display-rule constants, the rule text, and a pure `nhl_display_verdict(cases_n, report, normal_brier)` and `select_family(results)`; plus `tests/test_nhl_over_probability.py` pinning every constant. No fitting, scoring or CLI code in this commit. *Done when:* the tests pin all constants (300 / 0.02 / 0.05 / 200, candidate order, domain rules, both versions, seasons), each verdict branch (299 vs 300 cases, ECE exactly 0.02, a 200-pair bin exactly 0.05 off, a 199-pair bin far off ignored, Brier equal to the normal's passing) and the tie-break; the full API suite passes; and the diff is committed alone with its hash recorded in the spec before Step 2 starts.
- [x] **Step 2 - Family fitting and reading (pure)** - `app/core/nhl_over_probability_crossfit.py`: fit and read each family per market from `NhlReplayCase` pairs (reusing the shared families), the market's domain rules, and integer lines skipped. *Done when:* tests cover a known case per family (negbin mean equal to the projection, scaled normal variance growing with the projection, ratio quantiles on a known set), a zero-projection case skipped, a market outside a family's domain returning no fit, and integer lines reading None.
- [x] **Step 3 - Cross-fit scoring and selection (pure)** - in the same module: parity split by ISO week of `game_date`, `cross_fit`, `score_cases` at synthetic x.5 lines with the constant-sigma normal baseline from the fitting half, and `evaluate` to a candidate result per family. *Done when:* tests show no case is scored by a fit containing it, both halves are used, a tiny fixture selects the lower-Brier eligible family, an ineligible family is never selected, and a market with no eligible family is hidden.
- [x] **Step 4 - Development CLI** - `app/backtest/nhl_over_probability_fit.py` default mode: reads 2023 and 2024 only (the same explicit-seasons rule as 56b), prints the header (pre-registration commit, rule text, seasons, "holdout not read"), per market and family cases, ECE, worst gap, Brier, normal Brier and eligibility, the selected family per market, hidden markets, and the integer-line share of synthetic lines. `--confirm` without `--holdout` is refused. *Done when:* report tests on a stub history check one market row and the selection table; the live run completes against the stored 2024-25 rows with its timing noted; no 2025 or 2026 row is read (asserted by the seasons passed to the history call).
- [x] **Step 5 - Holdout confirmation and the generated module (code only)** - `--confirm --holdout` fits each selected family on all of 2024-25, scores 2025-26, prints verdicts and "holdout read 1"; `--write` renders `nhl_over_probability_fit.py` for shown markets from the 2024-25 fits. The confirm run refuses when the generated module already exists, so the holdout cannot be read twice by accident. *Done when:* tests cover the render (small fit, expected text), the refusal when the module exists, `--write` without a completed confirmation refused, and that a hidden market has no entry; a stubbed confirm run scores only markets selected in development.
- [x] **Step 6 - The one holdout read (needs a separate yes in chat)** - run `--confirm --holdout --write` once, after the owner approves in chat, then paste the output under Results. *Done when:* Results holds the full printed report, every market's verdict and selected family, the generated module is committed with `PRE_REGISTRATION_COMMIT` set to Step 1's hash, and a test imports it and checks the versions match, `SHOWN_MARKETS` is a subset of the 12 markets, and every shown market has parameters while a hidden one has none.
- [x] **Step 7 - Verify and interview guide** - Run the Verify command; update `docs/SportApp-Employer-Interview-Guide.md` if present (a pre-registered selection then one holdout read, with the outcome stated plainly, shown or hidden). *Done when:* `npm --prefix web run verify && cd api && python -m pytest` passes and the summary names the guide update or that the file is absent.

## Files / areas

- New: `api/app/core/nhl_over_probability.py`, `api/app/core/nhl_over_probability_crossfit.py`, `api/app/backtest/nhl_over_probability_fit.py`, `api/app/core/nhl_over_probability_fit.py` (generated), `api/tests/test_nhl_over_probability.py`, `api/tests/test_nhl_over_probability_crossfit.py`, `api/tests/test_nhl_over_probability_fit.py`
- Read only: `api/app/core/nhl_projection_backtest.py` (imported, never edited), `api/app/core/count_over_probability.py`, `api/app/core/nfl_over_probability.py`, `api/app/core/nfl_over_probability_calibration.py`, `api/app/repositories/nhl.py` (`get_projection_history` with explicit seasons), the NBA equivalents as pattern only (`nba_over_probability*.py`, `app/backtest/nba_over_probability_fit.py`)

## Data / contracts

No schema, API or web change.

**Load-bearing for 56c3 and 56c4:**
- `NHL_OVER_PROBABILITY_VERSION = "nhl-pover-v1"` and `FIT_PROJECTION_MODEL_VERSION == "nhl-reference-v1"`: 56c3 must refuse to serve a probability if they differ, as NBA's `_fit_serves` does.
- The generated module's shape (`SHOWN_MARKETS`, per-market family and parameters) is what 56c3 reads; a hidden market has no entry.
- A served probability is for a started goalie or a dressed skater only (the cases exist only because the player played). 56c3 must serve it only where 56c1's availability gate already shows a number.
- The 56b `replay_cases` output (`NhlReplayCase`) is the only input; no new eligibility rule here.

## Testing

Test gate on. Every pure module ships its tests in the same step (Steps 1, 2, 3, 5); the CLI report is tested on stub histories; Steps 4 and 6 also ride on the live runs. API tests need `DATABASE_URL=postgresql://localhost/ci` and the main checkout's venv `C:/dev/SportAppV2/api/.venv/Scripts/python.exe`; the real runs read the shared database through `Settings` (never print the URL).

## Notes for the AI

- **Holdout discipline is the whole point.** Do not read, score or print 2025-26 or 2026-27 rows in Steps 1 to 5. The history call takes explicit seasons; development passes `(2023, 2024)` only.
- Do not run `--confirm --holdout` without the owner's separate yes in chat in the current session; a stubbed run in tests is fine.
- Step 1's commit must contain no fit or scoring code. Record its full hash in Results before Step 2. Never amend or reorder it after later commits exist.
- NHL keeps its own constants: a change to NBA's or NFL's rule must never move this one. The shared sport-agnostic pieces are imported, not copied.
- `core/` stays pure: no DB, no I/O, no clock. The CLI is the only place that reads the database.
- The generated module is written by the CLI, never edited by hand. No em dashes. No AI attribution in commits; ask before committing.
- If the development run shows every market hidden, stop and report it; do not add families or change the rule after seeing the data.

## Results

- **Step 1, pre-registration commit:** `512fe51eebd18dd3e7abd3bc15aa82e640831185` (`api/app/core/nhl_over_probability.py` and `api/tests/test_nhl_over_probability.py` only, 2026-11-04). No NHL family was fitted or scored and no 2025-26 row was read before it. Full API suite at that commit: 5653 passed.
- **Step 4, development run** (`python -m app.backtest.nhl_over_probability_fit`, 2026-11-05, read-only transaction, 27 s, seasons read: 2023 and 2024 only; the 2025-26 holdout was not read). 5 of 12 markets have an eligible family and go to the one holdout read; 7 are hidden and never touch it. Full report:

```
NHL over-probability fit, 2024-25 (development: select freely)

Pre-registered in commit 512fe51eebd18dd3e7abd3bc15aa82e640831185.
Show a market only if its selected family has >= 300 cases, ECE <= 0.02, every bin of >= 200 pairs within 0.05 of its observed rate, and a Brier no worse than the constant-sigma normal's. The family is selected on 2024-25 by ISO-week-parity cross-fit and confirmed once on 2025-26.
Projection nhl-reference-v1, over-probability nhl-pover-v1; candidates in tie-break order: negbin, scaled_normal, ratio.
Cases: 399383 reference-arm replay cases from 2024-25, cross-fitted by ISO-week parity.
Integer lines: a whole-number line can push, which no family models, so it reads no probability. The synthetic lines scored here are x.5 by construction, so this report cannot show how many posted lines are whole numbers (Goalie Saves and Goals Allowed post some).
Holdout (2025-26): not read.

Cross-fit at synthetic x.5 lines
  market / family                     cases   pairs     ECE     gap   Brier  normal  verdict
  shots_on_goal / negbin              42362  115391  0.0071  0.0180  0.2048  0.2078  show
  shots_on_goal / scaled_normal       42362  115391  0.0471  0.0791  0.2068  0.2078  hide (ece,bin)
  shots_on_goal / ratio               42362  115391  0.0187  0.0320  0.2060  0.2078  show
  points / negbin                     42071   53174  0.0228  0.0959  0.2049  0.2162  hide (ece,bin)
  points / scaled_normal              42071   53174  0.0876  0.1211  0.2123  0.2162  hide (ece,bin)
  points / ratio                      42071   53174  0.0706  0.1234  0.2157  0.2162  hide (ece,bin)
  assists / negbin                    41471   44230  0.0352  0.0879  0.1834  0.1960  hide (ece,bin)
  assists / scaled_normal             41471   44230  0.0991  0.1763  0.1928  0.1960  hide (ece,bin)
  assists / ratio                     41471   44230  0.0610  0.1089  0.1888  0.1960  hide (ece,bin)
  goals / negbin                      36699   36997  0.0264  0.1592  0.1405  0.1495  hide (ece,bin)
  goals / scaled_normal               36699   36997  0.1116  0.2643  0.1525  0.1495  hide (ece,bin,brier)
  goals / ratio                       36699   36997  0.0609  0.0670  0.1443  0.1495  hide (ece,bin)
  power_play_points / negbin          24225   24316  0.0247  0.1441  0.1319  0.1399  hide (ece,bin)
  power_play_points / scaled_normal   24225   24316  0.1145  0.2250  0.1447  0.1399  hide (ece,bin,brier)
  power_play_points / ratio           24225   24316  0.0588  0.0683  0.1347  0.1399  hide (ece,bin)
  blocked_shots / negbin              42315   76723  0.0135  0.1611  0.2108  0.2178  hide (bin)
  blocked_shots / scaled_normal       42315   76723  0.0726  0.1073  0.2154  0.2178  hide (ece,bin)
  blocked_shots / ratio               42315   76723  0.0570  0.2329  0.2183  0.2178  hide (ece,bin,brier)
  plus_minus / scaled_normal          19752   20267  0.0952  0.1746  0.2284  0.2284  hide (ece,bin)
  goalie_saves / negbin                2723   13615  0.0170  0.0381  0.1238  0.1240  show
  goalie_saves / scaled_normal         2723   13615  0.0184  0.0412  0.1239  0.1240  show
  goalie_saves / ratio                 2723   13615  0.0046  0.0211  0.1236  0.1240  show
  hits / negbin                       42298   89458  0.0124  0.1175  0.2098  0.2181  hide (bin)
  hits / scaled_normal                42298   89458  0.0726  0.0979  0.2147  0.2181  hide (ece,bin)
  hits / ratio                        42298   89458  0.0483  0.1559  0.2150  0.2181  hide (ece,bin)
  time_on_ice / scaled_normal         42362  211810  0.0034  0.0394  0.0689  0.0689  show
  time_on_ice / ratio                 42362  211810  0.0068  0.0654  0.0692  0.0689  hide (bin,brier)
  goals_allowed / negbin               2723    9827  0.0161  0.0254  0.1953  0.1951  hide (brier)
  goals_allowed / scaled_normal        2723    9827  0.0165  0.0342  0.1951  0.1951  show
  goals_allowed / ratio                2723    9827  0.0106  0.0242  0.1953  0.1951  hide (brier)
  faceoffs_won / negbin               12552   51577  0.0081  0.0233  0.1862  0.1878  show
  faceoffs_won / scaled_normal        12552   51577  0.0254  0.0621  0.1869  0.1878  hide (ece,bin)
  faceoffs_won / ratio                12552   51577  0.0402  0.1391  0.1922  0.1878  hide (ece,bin,brier)

Selected on development (each goes to the one holdout read; hidden markets never do)
  shots_on_goal       negbin
  points              hidden (no eligible family)
  assists             hidden (no eligible family)
  goals               hidden (no eligible family)
  power_play_points   hidden (no eligible family)
  blocked_shots       hidden (no eligible family)
  plus_minus          hidden (no eligible family)
  goalie_saves        ratio
  hits                hidden (no eligible family)
  time_on_ice         scaled_normal
  goals_allowed       scaled_normal
  faceoffs_won        negbin
```
- [x] Repair F-15 - `--confirm` requires `--write` so the once-only marker is always left (marked `fixed`, awaiting re-review)
- [x] Repair F-16 - the confirm run no longer prints that the holdout is unread (marked `fixed`, awaiting re-review)

- **Step 6, the one holdout read** (`python -m app.backtest.nhl_over_probability_fit --confirm --holdout --write`, 2026-11-05, run once after the owner's explicit yes in chat; read-only transaction, 48 s, seasons 2023 to 2025; run from commit `3efb746f`, whose rule is the pre-registration commit `512fe51eebd18dd3e7abd3bc15aa82e640831185`). The development selection printed before it was identical to Step 4's. Holdout report:

```
HOLDOUT 2025-26: holdout read 1 (the one read; nothing was fitted on it)
Each selected family, fitted on all of 2024-25, scored once under the same display rule.

  market / family                     cases   pairs     ECE     gap   Brier  normal  verdict
  shots_on_goal / negbin              41976  113547  0.0059  0.0121  0.2050  0.2081  show
  goalie_saves / ratio                 2735   13675  0.0108  0.0239  0.1283  0.1281  hide (brier)
  time_on_ice / scaled_normal         41976  209880  0.0028  0.0292  0.0698  0.0698  show
  goals_allowed / scaled_normal        2735   10051  0.0161  0.0237  0.1909  0.1909  show
  faceoffs_won / negbin               12607   50580  0.0121  0.0263  0.1844  0.1870  show

Shown: shots_on_goal, time_on_ice, goals_allowed, faceoffs_won

Wrote nhl_over_probability_fit.py
```

**Verdicts:** 4 of 5 selected markets show (Shots on Goal `negbin`, Time On Ice `scaled_normal`, Goals Allowed `scaled_normal`, Faceoffs Won `negbin`); Goalie Saves `ratio` is hidden on the Brier check (0.1283 against the normal's 0.1281, calibration itself passed). Seven markets were hidden on development and never touched the holdout. Margins over the normal baseline are thin for Time On Ice (0.0698 against 0.0698) and Goals Allowed (0.1909 against 0.1909): they pass at four decimals, and the check is `<=`, so a tie passes. Shots on Goal and Faceoffs Won clear it by 0.0031 and 0.0026. The generated module `api/app/core/nhl_over_probability_fit.py` was written by the CLI and is not hand-edited; a second confirm run is refused while it exists.
- **Step 7, Verify:** `npm --prefix web run verify` passed (typecheck, 1226 tests in 81 files, build) and the API suite passed (5708), both on the committed branch tip `21b5121b`. The local, ignored interview guide (`docs/SportApp-Employer-Interview-Guide.md` in the main checkout) was updated: the NHL paragraph now also describes the pre-registered selection, the single holdout read and its outcome (four shown, Goalie Saves hidden, two shown markets only tying the baseline), and says nothing is served, frozen, graded or deployed.

## Findings

### 56c2/F-15 [P2] closed - A confirm run without --write reads the holdout and leaves no once-only marker

**File:** api/app/backtest/nhl_over_probability_fit.py:248
**Found:** 2026-11-05 by /audit (scope: current; lens: all)
**Why it matters:** The read-once guard is `check_module_absent`, which only sees
the generated module. `--confirm --holdout` without `--write` scores 2025-26,
prints the verdicts and writes nothing, so the guard still passes on the next
run and the holdout can be read again, which is the accident the spec says the
refusal prevents. The real read was made with `--write`, so the holdout was read
once; this is a gap in the guard, not a recorded violation.
**Suggested fix:** Require `--write` with `--confirm` (one flag, one read, one
record), or write the module before printing. Add a flags test.
**Resolution:** `check_flags` now refuses `--confirm` without `--write`, so every holdout read leaves the generated module that the existing guard checks; two flag tests cover it. Closed 2026-11-05 by /audit (scope: current; lens: all): re-read `check_flags`, `_confirm` and the entry point; no flag combination reads the holdout without `--write`, the module check runs before any read, and the repair introduced no new defect beyond the leftover noted in F-18.

### 56c2/F-16 [P2] closed - The confirm run prints "Holdout (2025-26): not read."

**File:** api/app/backtest/nhl_over_probability_fit.py:97
**Found:** 2026-11-05 by /audit (scope: current; lens: all)
**Why it matters:** `_confirm` prints the development report first, and its
header hard-codes "Holdout (2025-26): not read." That line appears in the same
output that then reports the holdout read (line 8 of the saved run). A reader of
the full output, or a pasted copy, gets a false statement about the holdout. The
spec's Results pasted only the holdout half, so it is correct, but the tool's
output is not.
**Suggested fix:** Give `_header` a `holdout_read` argument (or leave the line
out of the confirm run) and test both outputs.
**Resolution:** `_header` takes `holdout_read`; the confirm run prints "read once in this run, reported below", the development run still prints "not read". Tests cover both. Closed 2026-11-05 by /audit (scope: current; lens: all): re-read `_header`, `report` and `_confirm`; the confirm output now says the holdout was read, the development output still says it was not.

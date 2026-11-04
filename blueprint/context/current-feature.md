# Feature: NHL over-probability fit

**From build-plan:** feature 56c2 (second of 56c's four parts; 56c1 served the projection, 56c3 serves P(over), 56c4 freezes)
**Status:** not started
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
- [ ] **Step 4 - Development CLI** - `app/backtest/nhl_over_probability_fit.py` default mode: reads 2023 and 2024 only (the same explicit-seasons rule as 56b), prints the header (pre-registration commit, rule text, seasons, "holdout not read"), per market and family cases, ECE, worst gap, Brier, normal Brier and eligibility, the selected family per market, hidden markets, and the integer-line share of synthetic lines. `--confirm` without `--holdout` is refused. *Done when:* report tests on a stub history check one market row and the selection table; the live run completes against the stored 2024-25 rows with its timing noted; no 2025 or 2026 row is read (asserted by the seasons passed to the history call).
- [ ] **Step 5 - Holdout confirmation and the generated module (code only)** - `--confirm --holdout` fits each selected family on all of 2024-25, scores 2025-26, prints verdicts and "holdout read 1"; `--write` renders `nhl_over_probability_fit.py` for shown markets from the 2024-25 fits. The confirm run refuses when the generated module already exists, so the holdout cannot be read twice by accident. *Done when:* tests cover the render (small fit, expected text), the refusal when the module exists, `--write` without a completed confirmation refused, and that a hidden market has no entry; a stubbed confirm run scores only markets selected in development.
- [ ] **Step 6 - The one holdout read (needs a separate yes in chat)** - run `--confirm --holdout --write` once, after the owner approves in chat, then paste the output under Results. *Done when:* Results holds the full printed report, every market's verdict and selected family, the generated module is committed with `PRE_REGISTRATION_COMMIT` set to Step 1's hash, and a test imports it and checks the versions match, `SHOWN_MARKETS` is a subset of the 12 markets, and every shown market has parameters while a hidden one has none.
- [ ] **Step 7 - Verify and interview guide** - Run the Verify command; update `docs/SportApp-Employer-Interview-Guide.md` if present (a pre-registered selection then one holdout read, with the outcome stated plainly, shown or hidden). *Done when:* `npm --prefix web run verify && cd api && python -m pytest` passes and the summary names the guide update or that the file is absent.

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

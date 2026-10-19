# Feature: WTA 125 blend backtest

**From build-plan:** feature 40a (parent 40, WTA 125 blend group)
**Status:** complete 2026-10-19; scored once on 2026, verdict keep pooled; 40b dropped
**Branch:** `feature/wta125-blend-backtest`

## Goal

Find out, under a rule fixed before any outcome is read, whether WTA 125
matches are forecast better by the WTA coefficients or by a 125-only fit than
by the pooled Challenger coefficients they get today. Report only: nothing the
app serves changes. 40b serves a change only if this passes.

## Background (from 26c, 26d and the code)

- livetennisapi files WTA 125 draws under `challenger`, so `matches.tour` is
  `CHALLENGER` and the served blend is `FIT_COEFFICIENTS["CHALLENGER"]`
  (`a` 1.1105, `b` +0.0833, fitted on 5,734 reliable 2022 cases).
- 26d's D4 fitted that group on Valuebetennis `Challenger`, both genders
  pooled. `ClosingLineCase.tour` still holds `ATP` or `WTA` for those rows,
  so `tour == "WTA"` identifies its women's rows. Inspection on 2026-10-19
  found that those rows include ITF events; the WTA 125 subset additionally
  needs a verified tournament-and-season allowlist.
- WTA main tour: `a` 1.4605, `b` -0.4226 (881 cases).
- Seasons: 2021 burn-in, 2022 development, 2023-2025 holdout (read twice by
  26c and 26d, so not fresh). **At spec approval, 2026 had never been scored**: 26c used 2026
  only to compare Valuebetennis prices with the app's stored moneylines, and
  every 26c and 26d run excludes it from scoring.
- The six Valuebetennis files are now available locally at the gitignored
  `api/data/valuebetennis/` path (downloaded by the user on 2026-10-19).

## Pre-registered rule (fixed at spec approval; do not edit after Step 4 runs)

| | |
|---|---|
| **Population** | Valuebetennis `Challenger` category, `tour == "WTA"`, and `(season, tournament)` on the frozen allowlist verified against official WTA 125 event metadata; scored under 26d's Challenger exclusions (`exclusion(case, CHALLENGER_CATEGORIES) is None`: main draw, completed, closing price, computed ELO present). Unlisted names never enter the population. |
| **Incumbent** | `FIT_COEFFICIENTS["CHALLENGER"]` (what the app serves) |
| **Candidate A** | `FIT_COEFFICIENTS["WTA"]` |
| **Candidate B** | the 26d form `logit(p) = a * logit(close) + b * logit(elo)`, fitted with `fit_group` on 2022 cases in the verified WTA 125 population with a reliable ELO; **fitted only if there are 300 or more such cases**, else dropped before Step 4 |
| **Served probability** | `served_prob` (the close alone when the live ELO gate drops ELO), as 26d |
| **Verdict sample** | every 2026 case in the population in the file as downloaded for Step 4, dated on or before the download; scored **once** |
| **Minimum sample** | 300 scored 2026 cases; fewer means **accruing**: nothing is scored, and a later re-download repeats only the count |
| **Gate G1 (beats the incumbent)** | candidate minus incumbent, paired log loss: `mean + 2.5 * SE < 0` (2.5, not 2, because two candidates are tested) |
| **Gate G2 (no worse than the close)** | candidate minus the close: `mean - 2 * SE <= 0` (26d's H2) |
| **Verdict** | a candidate passes when G1 and G2 both pass. If both pass, **A is adopted** (it borrows coefficients and fits nothing on 125 data). If neither passes, **keep the pooled group** and 40b is dropped |
| **Context only, never decisive** | Brier, calibration bins, the men's Challenger rows under the incumbent, flat-stake ROI at the close |

## In scope

- Downloading the Valuebetennis season files again (2021 to 2026).
- A count of women's and men's Challenger cases per season and exclusion
  reason, with no outcome or probability printed.
- A data-integrity check: refitting the pooled 2022 Challenger group
  reproduces 26d's frozen coefficients.
- Candidate B's 2022 fit, frozen as constants.
- The one scored 2026 run and its recorded result.

## Out of scope

- Any change to `blend()`, `fitted_group`, `FIT_COEFFICIENTS` or
  `app/core/tennis_market_blend_fit.py` (hook-protected, generated). Serving
  is 40b.
- Men's Challenger coefficients, the ATP and WTA groups, and `ensemble-v2`.
- The live 26a predictions: they carry the app's WTA 125 label only through
  `display_tour`, and grading them forward is not this item.
- Scoring or fitting on 2023-2025 again. Their results still feed the
  computed-ELO replay that 2026 cases need, exactly as in 26c and 26d; that
  is not an outcome read of those seasons.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Data and counts** - download the six season files into
  `api/data/valuebetennis/` (the URL in `tennis_closing_lines.DOWNLOAD_URL`);
  freeze a tournament-and-season allowlist checked against official WTA event
  levels, names and dates, including December qualifying for January events;
  add `app/backtest/tennis_wta125_blend.py` with the population filter
  (`in_wta125`) and a default `--count` mode: per season, cases in the women's
  and men's Challenger sets by exclusion reason, plus the 10 most frequent
  women's Challenger tournament names and the top 10 verified WTA 125 names.
  Audit every unlisted women's Challenger label: explicit ITF tier labels
  (`W<number>` or `W<number>+H`, followed by a space) are reported as outside
  WTA 125; any other unlisted label stops the count for metadata review.
  Report official event coverage and provider gaps. No outcome, probability or loss is
  computed in this mode. If a download fails or the file layout changed,
  stop and report rather than patching the parser. *Done when:* the count prints for 2021-2026, the
  allowlisted tournament names are verified WTA 125 events and every other
  women's Challenger label is accounted for, the
  2026 download date and row count are recorded below, and the filter tests
  pass.
- [x] **Step 2 - Integrity check and the rule in code** - `--fit` refits the
  pooled 2022 Challenger group and compares it with
  `FIT_COEFFICIENTS["CHALLENGER"]` (refuse to continue if `a` or `b` differs
  by more than 0.001, or n differs from 5,734: the re-downloaded 2022 file
  would not be 26d's, and the user decides how to proceed). Add the rule's
  constants and a pure
  `decide(n_scored: int, gates: Mapping[str, tuple[PairedDifference, PairedDifference]]) -> Verdict`
  (keys `"A"` and, when fitted, `"B"`; each value is (G1 difference, G2
  difference); `Verdict` is `accruing`, `keep pooled`, `adopt A` or
  `adopt B`) with tests, before any candidate is fitted. *Done when:* the integrity check prints a
  match, and `decide` tests cover every verdict row including the A-over-B
  tie-break and the 300-case floor.
- [x] **Step 3 - Fit candidate B on 2022** - `--fit` also fits B on the 2022
  verified WTA 125 set (only with 300+ reliable cases) and prints n,
  coefficients and SEs, plus an in-sample 2022 log-loss table for the
  incumbent, A and B, labelled IN-SAMPLE. Freeze B as module constants
  (`WTA125_FIT_N`, `WTA125_FIT`). *Done when:* the constants are in the module
  with the printed values recorded below, or B is recorded as dropped (under
  300 cases), and no 2026 case is scored.
- [x] **Step 4 - The one scored run (needs a separate go-ahead in chat)** -
  `--score --download-date YYYY-MM-DD` loads the snapshot, excludes matches
  dated after that download, counts the 2026 scored set and calls `decide`; below 300 it
  prints "accruing" and computes no loss. Otherwise it prints G1 and G2 per
  candidate, the context table and the verdict. Run once; record the full
  output below and the 2026 read count (1). *Done when:* the verdict and
  output are recorded in this spec, and the build plan notes whether 40b is
  next or dropped.

## Files / areas

- `api/app/backtest/tennis_wta125_blend.py` (new): filter, counts, fit,
  frozen B, scoring CLI. Reuses `load_valuebetennis`, `build_cases`,
  `exclusion`, `fit_group`, `served_prob` and `paired_loss_difference`.
- `api/tests/test_tennis_wta125_blend.py` (new).
- `api/app/backtest/data/tennis_wta125_events.csv` and its README (new):
  frozen provider labels by calendar season, official event IDs, years and
  dates, with source and coverage notes. No results or probabilities.
- `api/data/valuebetennis/` (gitignored, local only).
- No production module changes.

## Data / contracts

- No schema, API or UI change.
- **Load-bearing for 40b:** the winning coefficients and the population
  definition. 40b must route live matches to the same population (women's
  draws stored as `CHALLENGER`), using the player-tour rule in
  `display_tour` (`app/core/tennis_format.py`). The two definitions differ
  (Valuebetennis gender against stored player tours), so 40b checks the
  overlap on stored 2026 matches.

## Testing

- Pytest, in `api/tests/test_tennis_wta125_blend.py`:
  - `in_wta125`: an allowlisted WTA Challenger main-draw case is in; ATP
    Challenger, WTA main tour, qualifying, missing close or ELO, unfinished,
    ITF, an unlisted name, and an allowlisted name in the wrong year are out.
  - Counts agree with the existing exclusions on synthetic cases, including
    strictly prior-day ELO availability and cross-year tournament labels.
  - An unlisted non-ITF label stops the count rather than silently widening
    or shrinking the population.
  - `decide`: under 300 is accruing; neither candidate passing keeps the
    pooled group; A only, B only, and both (A wins); G2 failing blocks a G1
    pass.
  - The `--count` mode never calls the loss functions (patched to raise).
  - `--score` below 300 computes no loss.
  - Scoring uses frozen coefficients without fitting; G1/G2 compare only
    the same eligible 2026 WTA 125 rows. Prior seasons feed replay only.
  - The download cutoff applies before counting and replay. A count/replay
    population mismatch stops before any loss computation.
  - The real scoring CLI is exercised only against synthetic CSVs until the
    separate real-data authorization is given.
- The fit and the scored run are verified by their recorded output, not by
  tests (they need the downloaded data).
- Verify command as the final gate.

## Notes for the AI

- **Single read.** Step 4 runs once, after the user's go-ahead in chat. Never
  run `--score` while debugging; use a synthetic fixture.
- Keep `core/` pure: this is a backtest module, like 26c and 26d's, so file
  loading lives in `app/backtest/`.
- Do not touch `api/app/core/tennis_market_blend_fit.py` (generated; the
  `protect-files` hook refuses edits).
- Valuebetennis is CC BY 4.0; credit it in the report header as 26c and 26d
  do.
- The overview does not show the 40a/40b split yet; the next `/overview`
  picks it up.
- At `/complete`, update the interview guide if the verdict changes what can
  be said about tennis validation.

## Recorded results

### Step 1 inspection (2026-10-19, blocked before implementation)

The user downloaded all six season files after the direct download returned
HTTP 403. Their headers match the existing loader's required columns; the
parser was not changed. Download date is recorded from the user's confirmation
and local file timestamps, not from a server-provided timestamp.

| Season | Raw rows | Parsed women's Challenger rows (before exclusions) |
|---|---:|---:|
| 2021 | 63,728 | 9,459 |
| 2022 | 83,381 | 17,436 |
| 2023 | 89,826 | 20,011 |
| 2024 | 79,910 | 16,172 |
| 2025 | 80,412 | 17,398 |
| 2026 | 70,231 | 14,294 |

Across the files, the existing loader parsed 467,485 of 467,488 rows and
skipped three. No outcomes, probabilities, fits or losses were computed for
this inspection; only parsed metadata and counts were inspected.

2026 file SHA-256:
`985a861542c83c31e5b5edea297e2e953699f5a9e17d1c7e134118d8fc8a817c`.

The ten most frequent women's Challenger tournament names across all files:

| Tournament label | Parsed rows |
|---|---:|
| W35 Santa Margherita di Pula | 1,409 |
| W25 Santa Margherita di Pula | 986 |
| W25 Monastir | 894 |
| W35 Monastir | 784 |
| W25 Santo Domingo | 713 |
| W35 Antalya | 696 |
| W35 Santo Domingo | 513 |
| W35 Sharm ElSheikh | 513 |
| W25 Sharm ElSheikh | 488 |
| W25 Antalya | 457 |

The population check failed: women's `Challenger` is a mixture of tiers,
not a WTA 125 identifier. The 2026 file alone contains 463 rows labelled
`W35 Santa Margherita di Pula`. The
[official ITF event page](https://www.itftennis.com/en/tournament/w35-santa-margherita-di-pula/ita/2026/w-itf-ita-2026-016/)
and [WTA event page](https://www.wtatennis.com/tournaments/3048/santa-margherita-di-pula-2/2026)
identify this as an ITF event. WTA 125 labels such as `Austin 125 - Austin`
also occur in that category.

Stopped under Step 1's explicit mixed-tier safeguard. No product code was
written, no step was checked off, and the pre-registered rule remains
unchanged. The 2026 scored read count remains **0**.

Proposed revision for review: identify WTA 125 events using an explicit
tournament-and-season allowlist checked against official WTA records, then
apply the existing completion, main-draw, closing-price and ELO exclusions.
Audit every unmatched women's Challenger label and report tier coverage before
fitting. Do not assume that removing W-number prefixes alone identifies all
WTA 125 events. Keep the frozen incumbent, candidate definitions, fit seasons,
minimum sample, gates, tie-break and separate scoring authorization unchanged.
The population and the related filter tests must be revised before resuming.

### Population correction (2026-10-19, before any fitting or scoring)

The user invoked implement again after the proposed correction was presented.
This resumes the verified tournament-and-season approach above. The rule now
excludes ITF events explicitly; the incumbent, candidates, fit seasons, sample
floor, gates and tie-break are unchanged. Step 4 still needs its separate
go-ahead. The original broad-category inspection above remains recorded.

Source: the official WTA calendar's public `/tennis/tournaments/` endpoint,
filtered by `levels=WTA 125`, pages 0-2 of 100 records (header `account: wta`).
The response's `year` query parameter did not constrain the returned years;
the event-level `year` and `level` fields were inspected instead. Only metadata
is used for the crosswalk. The calendar source is
`https://api.wtatennis.com/tennis/tournaments/?levels=WTA+125&page=0&pageSize=100`.
Use each event's historical `level`, not its group's current level, since
some events have changed tiers.

### Step 1 implementation and evidence (2026-10-19, awaiting review)

- Added `tennis_wta125_blend.py`: exact allowlist membership plus 26d's
  exclusions, and a default count CLI (`--count` gives the same output).
- Added a frozen CSV crosswalk: 213 official event references representing
  212 unique `(season, tournament)` keys. Every reference's level and dates
  were checked against official metadata. Every corresponding provider date
  falls within its event's dates allowing three days before and two after
  for the metadata audit only; that tolerance is not a population filter.
- Added 18 tests: membership and exclusions, year-specific tier changes,
  cross-year Canberra labels, count eligibility against synthetic 26c cases,
  same-day ELO absence, unresolved tier names, changed CSV layout and missing
  files, and both CLI modes with probability, outcome and loss functions
  patched to raise.
- No candidates were fitted and no season was scored. The 2026 scored read
  count remains **0**. Production modules and coefficients are unchanged.

Count output, Challenger rows with the first applicable exclusion reason:

| Season | Tour | All Challenger | Eligible | Not WTA 125 | Qualifying | Laver Cup | Not completed | No close | Missing ELO |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2021 | WTA | 9,459 | 0 | 8,919 | 80 | 0 | 44 | 416 | 0 |
| 2021 | ATP | 6,283 | 0 | 0 | 1,735 | 0 | 478 | 4,070 | 0 |
| 2022 | WTA | 17,436 | 604 | 16,599 | 127 | 0 | 95 | 11 | 0 |
| 2022 | ATP | 8,869 | 3,926 | 0 | 3,148 | 0 | 888 | 904 | 3 |
| 2023 | WTA | 20,011 | 719 | 18,896 | 183 | 0 | 127 | 85 | 1 |
| 2023 | ATP | 9,490 | 4,728 | 0 | 3,445 | 0 | 843 | 474 | 0 |
| 2024 | WTA | 16,172 | 884 | 14,934 | 218 | 0 | 112 | 24 | 0 |
| 2024 | ATP | 8,572 | 4,193 | 0 | 3,097 | 0 | 878 | 403 | 1 |
| 2025 | WTA | 17,398 | 1,324 | 15,374 | 404 | 0 | 233 | 63 | 0 |
| 2025 | ATP | 10,350 | 5,118 | 0 | 3,713 | 0 | 1,040 | 479 | 0 |
| 2026 | WTA | 14,294 | 970 | 12,126 | 524 | 0 | 634 | 39 | 1 |
| 2026 | ATP | 9,479 | 3,473 | 0 | 3,431 | 0 | 2,358 | 217 | 0 |

2022 has 604 eligible WTA 125 cases, before the reliable-ELO fitting gate;
this does not yet establish candidate B's fitting sample. 2026 has 970
eligible cases in this download, without computing any outcome or probability.

Tier audit (every parsed women's Challenger label checked):

| Season | Verified WTA 125 labels | Verified rows | ITF labels | ITF rows | Unresolved labels |
|---|---:|---:|---:|---:|---:|
| 2021 | 15 | 540 | 138 | 8,919 | 0 |
| 2022 | 24 | 837 | 232 | 16,599 | 0 |
| 2023 | 32 | 1,115 | 279 | 18,896 | 0 |
| 2024 | 34 | 1,238 | 254 | 14,934 | 0 |
| 2025 | 53 | 2,024 | 246 | 15,374 | 0 |
| 2026 | 54 | 2,168 | 203 | 12,126 | 0 |

The 2023 label count includes qualifying for the 2024 Canberra event; the
2024 count includes the 2025 Canberra event. The crosswalk README records
official event coverage and provider gaps separately from these label counts.
2021 has no eligible matches because no completed main-draw WTA 125 case in
the file has both closing prices; its match history remains available for
later seasons' ELO availability.

Top verified WTA 125 names before match exclusions, across all six files:

| Tournament label | Parsed rows |
|---|---:|
| Open 35 de Saint-Malo - Saint-Malo | 243 |
| Dow Tennis Classic - Midland | 207 |
| BBVA Open Internacional - Valencia | 206 |
| Grand Est Open 88 - Contrexeville | 197 |
| Nordea Open - Bastad | 182 |
| Open BLS de Limoges - Limoges | 174 |
| LP Open by IND - Colina | 139 |
| Argentina Open - Buenos Aires | 136 |
| Open delle Puglie - Bari | 134 |
| Tiriac Foundation Trophy - Bucharest | 126 |

Validation:

- Focused: from `api/`, `.venv\Scripts\python.exe -m pytest tests/test_tennis_wta125_blend.py -q`: **18 passed**.
- Verify: `npm --prefix web run verify && cd api && python -m pytest`, with
  the API venv on PATH: **612 web tests, production build, 2,796 API tests
  passed**. The sandbox initially blocked esbuild's config resolution;
  the same command passed outside the sandbox. Existing Vite chunk-size and
  Starlette/anyio deprecation warnings remain.
- Check, Step 1 only: from `api/`, `.venv\Scripts\python.exe -m app.backtest.tennis_wta125_blend --count`
  and the default command both ran on all six downloads and returned identical
  reports. Local full outputs are in the ignored
  `output/wta125-research/counts.txt` and `default-counts.txt`.
- `git diff --check` passed. No commit was made. Step 1 remains unchecked
  until the user reviews and approves it.

Step 1 was approved in chat on 2026-10-19. Continuing to Step 2 without a
checkpoint commit, as the default workflow choice.

### Step 2 implementation and evidence (2026-10-19, awaiting review)

- Added the pre-registered constants and pure `decide` function. Below 300
  returns `accruing` before examining any gates. At or above 300, G1 uses a
  strict negative upper bound at 2.5 SE and G2 allows a zero lower bound at
  2 SE. A takes priority when both candidates pass, regardless of mapping
  insertion order. Invalid paired inputs (different n, missing or non-finite
  SE, non-finite mean, or negative SE) are rejected rather than adopted.
- Added `--fit`, mutually exclusive with `--count`. It builds cases only
  from the 2021 burn-in and 2022 development rows, then refits the entire
  pooled Challenger group with the existing 26d helpers. The integrity
  sample deliberately retains all tiers and both genders, as 26d did;
  the narrower WTA 125 allowlist does not redefine the frozen incumbent.
- The integrity check refuses to continue on a different sample size or
  either coefficient differing by more than 0.001. Its error includes both
  the fitted and frozen values. No coefficient file is written.
- Added 21 tests for all verdict rows, the 300-case floor, G1/G2 boundaries,
  A-over-B precedence, invalid paired evidence, integrity tolerance and
  sample-size failures, and exclusion of 2023-2026 from case construction.
  The previous count-mode tests also now block the newly imported build
  and fit functions.

Observed output from `api/`, using
`.venv\Scripts\python.exe -m app.backtest.tennis_wta125_blend --fit`:

```text
WTA 125 blend backtest (40a) - 2022 pooled Challenger integrity check
  Data: Valuebetennis open data (valuebetennis.com), CC BY 4.0.
  Integrity MATCH: n=5734, a=1.110494, b=+0.083259
  Frozen n and both coefficients match within 0.001.
  Candidate B not fitted in Step 2. No holdout season built or scored.
```

Validation:

- Focused: `.venv\Scripts\python.exe -m pytest tests/test_tennis_wta125_blend.py -q`
  from `api/`: **39 passed** (18 from Step 1 plus 21 from Step 2).
- Verify: `npm --prefix web run verify && cd api && python -m pytest`,
  with the API venv on PATH: **612 web tests, production build, and 2,817
  API tests passed**. Existing Vite chunk-size and Starlette/anyio
  deprecation warnings remain.
- The actual `--fit` CLI exited successfully and reproduced the frozen
  sample size and coefficients to six decimal places. No candidate fit or
  loss function was run on real data; 2026 scored read count remains **0**.
- Incremental diffs were shown against the approved Step 1 files preserved
  under the ignored `output/wta125-research/` directory. Diff whitespace
  checks passed. No commit was made. Step 2 remains unchecked until approval.

Step 2 was approved by the user's `continue` message on 2026-10-19.
Continuing to Step 3 without a checkpoint commit.

### Step 3 implementation and evidence (2026-10-19, awaiting review)

- `--fit` now runs the pooled integrity check before selecting candidate B's
  fitting sample. Only reliable, eligible 2022 cases in the verified WTA 125
  population reach `fit_group`; below 300 cases it drops B without fitting.
- The observed fitting sample is **336**, so B is retained. Frozen constants
  are `WTA125_FIT_N = 336` and
  `WTA125_FIT = BlendCoefficients(market=1.442269367193, elo=-0.201619489152)`.
  They match the recorded output exactly at its printed precision. The
  generated production coefficient module remains untouched.
- The in-sample log-loss table uses all **604** eligible 2022 WTA 125 cases
  for every column. `served_prob` falls back to the close for the 268 cases
  whose ELO was gated; these cases do not enter B's fit.
- Five new tests cover the 299/300 fitting boundary, the fit's season and
  population filters, comparison on the same full development set with gated
  ELO, omission of a dropped B, and stopping before B after failed integrity.
  Existing tests prove 2023-2026 never reach case construction in `--fit` and
  count mode never invokes the newly imported serving or loss functions.

Observed output from `api/`, using
`.venv\Scripts\python.exe -m app.backtest.tennis_wta125_blend --fit`:

```text
WTA 125 blend backtest (40a) - 2022 development fit, IN-SAMPLE ONLY
  Data: Valuebetennis open data (valuebetennis.com), CC BY 4.0.
  Integrity MATCH: n=5734, a=1.110494, b=+0.083259
  Frozen n and both coefficients match within 0.001.
  No holdout season built or scored. No adoption decision is made by --fit.

Candidate B: n=336 reliable 2022 WTA 125 cases (SEs in parentheses)
  a=1.442269367193 (0.356366063843)
  b=-0.201619489152 (0.328430376965)

IN-SAMPLE 2022 log loss (not a verdict; same eligible cases, gated ELO served as the close)
  blend             n     log loss
  incumbent       604     0.600182
  A               604     0.600809
  B               604     0.599439
```

These are development results, not adoption evidence. No gate or candidate
choice was changed after this output. **2026 scored read count: 0.**

Validation:

- Focused: `.venv\Scripts\python.exe -m pytest tests/test_tennis_wta125_blend.py -q`
  from `api/`: **44 passed**.
- Verify: `npm --prefix web run verify && cd api && python -m pytest`,
  with the API venv on PATH: **612 web tests, production build, and 2,822
  API tests passed**. Existing Vite chunk-size and Starlette/anyio
  deprecation warnings remain.
- The actual `--fit` CLI succeeded. Its local full output is preserved in
  the ignored `output/wta125-research/development-fit.txt`; frozen constants
  were compared with that saved output without rerunning the data fit.
- The incremental diff against approved Step 2 was shown; whitespace checks
  passed. No commit was made. Step 3 remains unchecked until approval.
- Step 4 implementation has not started. Its real 2026 run still needs a
  separate go-ahead in chat, after the scoring path is prepared and tested
  with synthetic fixtures.

Step 3 was approved by the user's `continue` message on 2026-10-19.
That message authorized preparing and testing scoring code, as offered in
chat; it did not authorize the real 2026 scored run. No checkpoint commit.

### Step 4 preparation (2026-10-19, real run not authorized)

- Added `--score --download-date YYYY-MM-DD`. Missing the date fails before
  data loading. The explicit date applies the already registered download
  cutoff without depending on the host clock. The default mode remains
  counts only, and count, fit and score modes are mutually exclusive.
- Counts the eligible 2026 WTA 125 population from metadata before case
  replay. Below 300 it calls `decide(n, {})`, prints `accruing` and performs
  no probability, outcome or loss computation. It adds zero scored reads.
- At or above 300, replays history through the cutoff, requires the replay
  population to agree with the metadata count, and uses the frozen pooled,
  A and B coefficients. It never invokes fitting. G1 is paired against the
  incumbent and G2 against the close on exactly the same WTA 125 cases.
- Reports G1/G2 means, SEs, bounds and pass/fail status; log loss and Brier;
  calibration bins; flat-stake ROI using 26c's existing 3-point rule; men's
  Challenger reference scores; and the verdict from `decide`. Context
  statistics do not change the decision. The CLI includes input SHA-256s.
- Seven new test cases cover the zero/299 sample floor, date cutoff,
  common-case comparisons and exclusion of other seasons and tiers,
  no-refit guarantee, count/replay disagreement, omission of a dropped B,
  missing CLI date and the complete CLI on synthetic CSVs.

Validation:

- Focused: from `api/`, `.venv\Scripts\python.exe -m pytest tests/test_tennis_wta125_blend.py -q`:
  **51 passed**.
- Verify: `npm --prefix web run verify && cd api && python -m pytest`,
  with the API venv on PATH: **612 web tests, production build, and 2,829
  API tests passed**. Existing Vite chunk-size and Starlette/anyio
  deprecation warnings remain.
- CLI check used only generated, artificial matches under the ignored
  `output/wta125-research/synthetic-score-data/` directory. The command was
  `.venv\Scripts\python.exe -m app.backtest.tennis_wta125_blend --score --download-date 2026-10-19 --data-dir ../output/wta125-research/synthetic-score-data`
  from `api/`. It exited successfully, printed 300 synthetic eligible cases,
  G1/G2 and all context sections, `Verdict: keep pooled`, and six source
  hashes. All ELO inputs were gated in this artificial sample, making every
  blend equal to the close; G1 failed at exactly zero, as required.
  This is test evidence only, not a result about real WTA 125 matches.
  Full synthetic output is in the ignored
  `output/wta125-research/synthetic-score-output.txt`.
- The incremental diff against approved Step 3 was shown. Whitespace checks
  passed and the generated production fit module has no diff. No commit.

**Real 2026 scored read count remains 0.** No verdict has been recorded and
40b's conditional plan state is unchanged. Step 4 remains unchecked.

Prepared real-data command (not executed; requires a separate go-ahead):

```powershell
# From api/, on the user's 2026-10-19 download:
.\.venv\Scripts\python.exe -m app.backtest.tennis_wta125_blend --score --download-date 2026-10-19
```

After authorization, run it once, preserve the full output and input hashes,
record the verdict and scored read count here, and update the build plan's
40b note as registered. Do not rerun the real score for debugging.

### Real-run authorization (2026-10-19)

The user answered `yes` to the explicit single-real-2026-run approval request
after the prepared code, tests and exact command were presented. This approves
Step 4's implementation and authorizes one execution of the prepared command.
The 2026 source SHA-256 still matches the recorded download:
`985a861542c83c31e5b5edea297e2e953699f5a9e17d1c7e134118d8fc8a817c`.
The output target `output/wta125-research/real-2026-score.txt` did not exist
before execution. The authorized execution finished successfully and its
output is recorded below. Do not invoke the scorer again on this sample.


### Step 4 real result (2026-10-19, scored once)

The authorized command completed successfully (exit 0). It ran exactly once
on the real downloads, with cutoff 2026-10-19. **2026 scored read count: 1.**
Do not score this sample again or treat it as fresh evidence for another fit.
The pre-registered population, frozen coefficients, sample floor and gates
were not changed after the result.

**Verdict: keep pooled.** Both candidates failed G1 and passed G2. Their
sample mean log losses were higher than the incumbent's, and neither cleared
the required evidence of improvement at 2.5 SE. Passing G2 is not proof that
a candidate beats the close. The context tables do not change the verdict.
The conditional serving feature 40b is dropped; no production module, routing,
model version or SPORT_STATUS change is made.

| Candidate | G1 difference vs incumbent | G1 upper bound | G1 | G2 difference vs close | G2 lower bound | G2 |
|---|---|---|---|---|---|---|
| A | +0.00279221 +/- 0.00198145 | +0.00774584 | fail | +0.00201208 +/- 0.00203485 | -0.00205762 | pass |
| B | +0.00203577 +/- 0.00150848 | +0.00580697 | fail | +0.00125563 +/- 0.00290427 | -0.00455291 | pass |

Full output, copied from the saved CLI report without recomputing any score:

```text
WTA 125 blend backtest (40a) - 2026 verdict (score at most once)
  Data: Valuebetennis open data (valuebetennis.com), CC BY 4.0.
  Download cutoff: 2026-10-19; eligible WTA 125 cases: 970; minimum: 300.
  Frozen B: fit n=336, a=1.442269367193, b=-0.201619489152.

Paired log-loss gates (candidate minus baseline; +/- one SE)
  A G1 vs incumbent: n=970, +0.00279221 +/- 0.00198145; mean + 2.5 SE = +0.00774584 -> fail
  A G2 vs close: n=970, +0.00201208 +/- 0.00203485; mean - 2 SE = -0.00205762 -> pass
  B G1 vs incumbent: n=970, +0.00203577 +/- 0.00150848; mean + 2.5 SE = +0.00580697 -> fail
  B G2 vs close: n=970, +0.00125563 +/- 0.00290427; mean - 2 SE = -0.00455291 -> pass

WTA 125 score context (same cases; only paired gates decide)
  blend             n     log loss        Brier
  close           970     0.587191     0.201721
  incumbent       970     0.586411     0.201430
  A               970     0.589203     0.202446
  B               970     0.588447     0.201962

Calibration context only (bin: mean predicted / actual p1 win rate)
  close: 0.0-0.1: 0.076/0.000 (n=9); 0.1-0.2: 0.154/0.185 (n=65); 0.2-0.3: 0.255/0.234 (n=124); 0.3-0.4: 0.351/0.403 (n=159); 0.4-0.5: 0.447/0.466 (n=146); 0.5-0.6: 0.552/0.594 (n=138); 0.6-0.7: 0.643/0.686 (n=156); 0.7-0.8: 0.749/0.773 (n=97); 0.8-0.9: 0.846/0.923 (n=52); 0.9-1.0: 0.933/0.917 (n=24)
  incumbent: 0.0-0.1: 0.076/0.077 (n=26); 0.1-0.2: 0.156/0.176 (n=74); 0.2-0.3: 0.253/0.305 (n=131); 0.3-0.4: 0.350/0.399 (n=148); 0.4-0.5: 0.449/0.477 (n=128); 0.5-0.6: 0.553/0.593 (n=118); 0.6-0.7: 0.646/0.662 (n=151); 0.7-0.8: 0.751/0.760 (n=96); 0.8-0.9: 0.847/0.894 (n=66); 0.9-1.0: 0.941/0.938 (n=32)
  A: 0.0-0.1: 0.074/0.095 (n=21); 0.1-0.2: 0.156/0.167 (n=72); 0.2-0.3: 0.254/0.287 (n=129); 0.3-0.4: 0.349/0.407 (n=135); 0.4-0.5: 0.446/0.471 (n=140); 0.5-0.6: 0.550/0.544 (n=125); 0.6-0.7: 0.643/0.673 (n=156); 0.7-0.8: 0.746/0.798 (n=99); 0.8-0.9: 0.845/0.871 (n=62); 0.9-1.0: 0.935/0.935 (n=31)
  B: 0.0-0.1: 0.070/0.147 (n=34); 0.1-0.2: 0.157/0.167 (n=84); 0.2-0.3: 0.251/0.306 (n=124); 0.3-0.4: 0.350/0.418 (n=141); 0.4-0.5: 0.449/0.467 (n=120); 0.5-0.6: 0.553/0.588 (n=114); 0.6-0.7: 0.647/0.651 (n=146); 0.7-0.8: 0.750/0.784 (n=97); 0.8-0.9: 0.845/0.843 (n=70); 0.9-1.0: 0.940/0.950 (n=40)

Flat-stake ROI context only (at the close; absolute edge >= 3%, either side)
  incumbent: picks 261, won 208, units -0.01, ROI -0.0%
  A: picks 315, won 200, units -15.77, ROI -5.0%
  B: picks 456, won 338, units -6.59, ROI -1.4%

Men's Challenger context only (never decisive)
  blend             n     log loss        Brier
  close          3473     0.602039     0.207428
  incumbent      3473     0.601619     0.207233

Verdict: keep pooled

Input files
  valuebetennis-matchs-2021.csv: SHA-256 818f722eecdfdfd4f7c1f0020623334755b44678a7a931888fa27e2005d51d34
  valuebetennis-matchs-2022.csv: SHA-256 649b349712bbb975bfa5df4229345df44d67309e22bf281496bae5f064212ca8
  valuebetennis-matchs-2023.csv: SHA-256 667cd498423a13c05634c42b43c4238803d2356f5b1999d4db3910eaaa98e882
  valuebetennis-matchs-2024.csv: SHA-256 19e6252a8019b85afa69c75ab812a96649a1e2dd76db6a947dfc46f4064c1eab
  valuebetennis-matchs-2025.csv: SHA-256 08204555cfb8cf0b6dac600bbdc57e109813671aecdc70c39830b636c1d62b3a
  valuebetennis-matchs-2026.csv: SHA-256 985a861542c83c31e5b5edea297e2e953699f5a9e17d1c7e134118d8fc8a817c
```

The full local report is also preserved at
`output/wta125-research/real-2026-score.txt` (ignored). The source hashes match
the Step 1 downloads. The 2026 file has 70,231 raw rows and 970 eligible
WTA 125 cases; men's Challenger context has 3,473 eligible cases.

Final review notes:

- The code is unchanged since the passing Step 4 preparation gate: 51 focused
  tests, 612 web tests, production build and 2,829 API tests. Only factual
  result documentation and plan notes changed after the single real run.
- The actual real-data CLI result is the behavioral evidence for Step 4.
  It will not be rerun as a verification command or manual try instruction.
- Updated the ignored, local employer interview guide in its existing
  validation discussion. It distinguishes the completed local backtest from
  production behavior and records the rejected serving change. Never stage it.
- No P0/P1 findings are open or fixed in the ledger. Existing open findings
  F-20, F-07, F-08, F-13, F-14 and F-15 are outside this feature; F-09 and
  F-12 remain unverified. None was changed by this work.
- All four implementation steps are checked. Build-plan 40a and the parent
  remain unchecked until complete logs the work; 40b is explicitly labelled
  dropped so it is not a next implementation task. No commit or merge yet.
- The generated overview still predates the 40a/40b result; refresh it through
  overview as part of later plan maintenance, not by hand-editing it.
- Safe manual paths: inspect this saved report or run the default --count
  mode. Do not rerun --score on the real 2026 dataset.


## Completion (2026-10-19)

Completed as feature 40a on `feature/wta125-blend-backtest`. This archive
preserves the pre-registered rule, correction of the mixed-tier population,
2022 fit, authorization and exact output of the single 2026 scored run.

- Final invariants review: clean. Report-only backtest code and synthetic
  tests; no SQL, request-path, provider-filter, UI signal, model-version or
  production coefficient changes. Fitting is limited to 2022; the 2026
  verdict was authorized and recorded once without retuning.
- Verify evidence: `npm --prefix web run verify && cd api && python -m pytest`
  with the API venv on PATH passed: 612 web tests, production build and
  2,829 API tests, including 51 focused WTA 125 tests. Source files did not
  change after that gate; subsequent changes are factual records and logging.
- Behavioral proof is the recorded real CLI output and the earlier synthetic
  CLI run. The real scorer was not rerun during completion.
- The conditional 40b is resolved as dropped, not implemented, under 40a's
  registered verdict. The parent 40 is closed because both outcomes are
  resolved. There is no 40b feature implementation or separate feature commit.
- Existing unresolved findings remain in the ledger. No resolved entries need
  archiving and no P0/P1 finding is open or fixed.
- The employer interview guide was updated locally and remains ignored.
  Downloads, scratch output and the guide are excluded from the commit.
- Pre-existing generated-overview edits are preserved unstaged; they include
  other prior fixes and are outside this work commit. A later overview run
  should incorporate the 40a/40b result from the build plan and archive.

Manual review: read the saved output above, or run
`python -m app.backtest.tennis_wta125_blend --count` from `api/` with the venv
active. Do not rerun `--score` on the real 2026 sample.

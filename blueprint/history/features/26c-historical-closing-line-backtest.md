# Feature: Historical closing-line backtest

**From build-plan:** feature 26c (parent: 26. Tennis model validation)
**Status:** complete (2026-10-01; holdout scored once, both candidates rejected against the close)
**Branch:** `feature/tennis-closing-line-backtest`

## Goal

Measure, over several full seasons, whether the tennis model's non-market signal
beats or adds to the closing moneyline. 26a found the market ahead of every
component on live data (the ensemble +0.0060 +/- 0.0068 behind it, ATP+WTA, at
32b's first read). 26c repeats that comparison on thousands of main-tour
ATP and WTA matches a season, from Valuebetennis results and Pinnacle odds, on
a holdout that is fixed before any number is seen.

It is a read-only report with no model change. Its verdict tells 26d whether the
hand-set ensemble weights are rejected against the close. It also locks the
holdout 26d must reuse.

## Decisions this spec makes

This spec replaces the parked tennis-data.co.uk spec of 2026-09-25 (never
built; its branch was deleted 2026-09-30). That spec's model decisions carry
over unchanged; its source, seasons and parser do not.

| Finding | Consequence |
|---|---|
| Stored ATP and WTA matches start in 2023. v6's early-stop, validation and test windows run to 2026-08-26, and its walk-forward folds cover 2023-07 to 2026-08 (checked 2026-09-25) | Every historical season is inside v6's training data or before any stored history. **v6 is not scored.** It stays graded forward by 26a. |
| The live ELO component uses scraped TennisAbstract snapshots, the earliest 2026-01-05 | **26c uses computed ELO** (`app.ml.elo_history.EloIndex`, the replay v6 already uses), rebuilt from the downloaded results alone, as a stand-in. |
| tennis-data.co.uk returns 403 even to a browser user agent (checked 2026-09-30) | **The source is Valuebetennis open data**: one CSV per season, ATP and WTA, 2021-2026, every category from ITF to Grand Slam, with Pinnacle opening odds and the last odds recorded before the match. CC BY 4.0; no account; a plain HTTP download works. |
| Valuebetennis carries its own integer player ids | **Identity is the Valuebetennis id.** No name normalization, no surname collisions, and no matching to `players`. |
| The app's own stored moneylines start 2026-03-11 | The app cannot supply historical closes, but its 2026 rows can **check what Valuebetennis's "last odds" are** (Step 1), on a season 26c never scores. |
| The data is foreign to every app table and only backtests read it | **No new table and no migration.** Files are parsed on each run; 26d reads them the same way. |

"The blend" is the **current hand-set `blend()` over ELO and the market, with
no ML component**, which is exactly how Challenger matches are predicted today.
Weights renormalize over the two present components: ATP ELO 0.583 and market
0.417; WTA ELO 0.727 and market 0.273.

**The blend keeps the live gates** (decided 2026-10-01 in Step 4, before any
blend number was computed). As `predictor.py` does, it passes
`elo_unreliable=elo_is_unreliable(elo, market, prior_matches)`, which moves
ELO's weight to the market when either player has under 10 prior matches or
the two differ by 15 points or more. It also passes `market_high_overround` when
the closing overround is above 8%. Prior matches are the player's results
before the match date in the replay. So 26c grades the blend the app serves.

**Build-plan line** (approved 2026-09-30):

> import Valuebetennis results with Pinnacle opening and closing odds (2021
> onward; tennis-data.co.uk now blocks downloads), and score computed ELO and
> the hand-set ELO-plus-market blend against the closing line on a
> pre-registered holdout (v6 cannot be scored historically: its training covers
> all stored history)

## Pre-registered holdout and rule

Written and approved 2026-09-30. **Do not edit after the holdout run.** A
changed rule invalidates the verdict.

**What had been seen when it was fixed:** the CSV header, and two rows of the
2025 file (Osaka v Grabher and Marino v Pera, Auckland, 2025-01-01), read on
2026-09-30 to confirm the format. Nothing else from any season.

**Amended 2026-10-01, before Step 2 and before any score or model number was
computed.** Step 1's 2021-2022 profile found qualifying inside the scored
categories, five-set scores truncated at 20 characters, the Laver Cup filed as
`Main tour`, and French category labels (Notes). The user approved restricting
the scored set to main draws without the Laver Cup, and counting truncated
scores as completed when every set before the cut is finished. **Seen by
then:** the 2021-2022 files' column values, odds coverage and score shapes,
and the 2026 file's prices for the timing check. No 2023-2025 row was read.
The development season is effectively 2022-03 to 2022-12, because closing odds
start in March 2022.

- **Seasons.**
  - Burn-in 2021: ELO warms up and nothing is scored.
  - Development 2022: scored freely and as often as wanted, and 26d's fit set.
  - **Holdout 2023-2025: scored once.**
  - 2026 is never scored. It is a partial season and overlaps 26a's live data;
    Step 1 uses it only for the closing-odds timing check.
- **ELO** replays every loaded match, all categories and both tours, because a
  player's lower-tier results are real information and lookups are strictly
  before the match date.
- **Scored matches (the verdict set):** `genre` ATP or WTA, `categorie`
  Main tour, Masters or Grand Slam (`Grand Chelem` in the file), main draw only
  (round code 4 or higher), and not the Laver Cup. Qualifying and the Laver
  Cup stay ELO input.
- **Eligible matches:**
  - the score is a finished match: `is_completed_score(score, best_of)`, with
    best-of-5 for ATP Grand Slam main draws and best-of-3 otherwise; or a
    score truncated at the file's 20-character limit whose sets before the
    cut are all finished sets (counted and reported)
  - both closing prices (`cote1_cloture`, `cote2_cloture`) are present and
    greater than 1.0
  - both players have a computed ELO rating before the match date
- **Market baseline:** the closing prices de-vigged by proportional
  normalization, as `app.core.odds.devig_two_way` does.
- **Primary metric:** the paired per-match log-loss difference against the
  market (`paired_loss_difference`), with its standard error, reported for
  ATP, WTA and ATP+WTA.
- **Verdict per candidate (ELO, blend), on the ATP+WTA holdout:**

  | Mean difference `d` against its standard error `se` | Verdict |
  |---|---|
  | `d + 2·se < 0` | **beats the close** |
  | `d - 2·se > 0` | **rejected against the close** |
  | anything else | **inconclusive** |

- **What each verdict means for 26d:**

  | Result | Meaning |
  |---|---|
  | Blend **rejected** | The hand-set weights are rejected. 26d is justified in replacing them with a market-anchored fit, scored on this same holdout. |
  | Either candidate **beats the close** | Treat as suspect. Audit for leakage (same-day ordering, date semantics) before 26d uses it. |
  | Blend **inconclusive** | 26d may still fit a blend, but must beat the market on this holdout by its own pre-registered rule. |

- **Secondary, reported but never decisive:**
  - **Flat-stake ROI:** one unit on the side where the blend exceeds the
    de-vigged close by at least 3 points, settled at the closing price, per
    tour, with the pick count.
  - **Open-to-close CLV:** on matches with both opening and closing prices, how
    often the close moved toward the model from the open, and the mean move in
    points, per tour (as 26a measures it live). **The model here is computed
    ELO** (decided in Step 5, before any number was computed): the blend is
    built from the close, so grading it against the close would be circular.
    A blend built from the open differs from the open by ELO's weight times
    (ELO minus open), so its direction is ELO's. Reported at any gap and at
    3 points or more.
  - **Challenger:** the same per-tour log-loss table for `categorie`
    Challenger, with the blend under whatever tour label the live predictor
    gives Challenger matches (Step 4 confirms it; the fallback weights would
    make it ELO 0.667, market 0.333). It is reported because the app serves
    Challenger matches with this blend; it never enters the verdict.

## In scope

- A gitignored data folder `api/data/valuebetennis/`, filled once in Step 1 by
  downloading `valuebetennis-matchs-<year>.csv` for 2021-2026.
- **A pure row parser** (`app/core/valuebetennis.py`): one CSV row as a
  mapping in, a `VbtMatch` out.
- **A loader** that reads every season file through the parser and reports, per
  file, rows read, parsed and skipped with reasons.
- **A case builder** that replays ELO, orients each match, and computes ELO,
  market and blend probabilities.
- **A report CLI**, run from `api/` as
  `python -m app.backtest.tennis_closing_lines`. It scores the development
  season by default; `--holdout` is required to score the holdout. Its header
  credits the data (CC BY 4.0).

## Out of scope

- v6, and the live TennisAbstract ELO (see Decisions).
- Any change to the model, weights, pick thresholds or ELO constants.
  `EloIndex` is used as is: no tuning, even on the development season.
- Fitting a blend. That is 26d.
- Doubles, and ITF matches as anything but ELO input.
- A database table, an import command, a scheduled job, an API endpoint or UI.
- Linking Valuebetennis players or matches to `players` or `matches`, except
  the one-off 2026 timing check in Step 1, which lives outside the app tree.
- Max or average market prices: Valuebetennis carries Pinnacle only.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at
   the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Data folder, download and source check.**
  - Add `api/data/valuebetennis/` to `.gitignore`.
  - Download the six season files from
    `https://www.valuebetennis.com/datasets/valuebetennis-matchs-<year>.csv`
    (2021-2026) into that folder with plain `curl`. This is a one-off; no app
    code fetches the site.
  - **From the 2021 and 2022 files only**, record in Notes below:
    - the `surface`, `categorie`, `genre` and `tour` (round) values
    - the `date` column's meaning (match date, or a time that is always
      midnight)
    - how retirements and walkovers appear in `score`, and whether
      `is_completed_score` handles the tie-break notation (`6-7(2)`)
    - the share of main-tour rows missing opening or closing prices
  - **Closing-odds timing check (2026 only):** a one-off script in the session
    scratchpad, not in `api/`, joins 2026 main-tour Valuebetennis matches to
    stored `matches` by date, tour and both surnames, and compares each side's
    de-vigged opening and closing probability with the app's last pre-start
    de-vigged moneyline from `match_odds`.

  *Done when:*
  - `git status` does not show the data files.
  - Notes below record the source facts and the timing check (matched count,
    mean absolute gap for open and for close).
  - **If the close is not clearly nearer the app's pre-start price than the
    open is, stop** and revisit "closing" with the user before Step 2. The rule
    assumes a near-start close.

- [x] **Step 2 - Pure row parser.** Add `app/core/valuebetennis.py`:
  - `VbtMatch` (below) and `parse_row(row: Mapping[str, str]) -> VbtMatch | None`
  - `genre` maps to `ATP` / `WTA`; `categorie` `Grand Chelem` maps to
    `Grand Slam`, other labels pass through
  - surfaces map `dur` and `dur intérieur` to `hard`, `terre battue` to
    `clay`, `gazon` to `grass`, and anything else (carpet) to None
  - `round_code` is the `tour` column as an int
  - `best_of` is 5 for an ATP Grand Slam main draw (round code 4 or higher)
    and 3 otherwise
  - `completed` comes from `is_completed_score`, or from the truncation rule
    (score exactly 20 characters, every set before the cut finished);
    `truncated` records which
  - odds that are blank, non-numeric, or 1.0 or below become None
  - a row with no players, no winner id, a winner id that is neither player,
    or no date returns None

  *Done when:* unit tests cover a completed WTA main-tour row, an ATP Grand
  Slam main-draw row (best-of-5) and qualifying row (best-of-3), a tie-break
  score, a truncated five-setter (completed) and a truncated score with an
  unfinished set before the cut (not completed), a retirement and a walkover
  (not completed), missing and malformed odds, each surface mapping, and each
  None-returning case.

- [x] **Step 3 - File loader.** Add `load_valuebetennis(folder: Path)` in
  `app/backtest/tennis_closing_lines.py`:
  - reads each `valuebetennis-matchs-*.csv` with pandas (`sep=";"`,
    `encoding="utf-8-sig"`, every column as text)
  - maps rows through `parse_row`
  - returns matches plus a per-file `LoadSummary` (rows, parsed, skipped by
    reason)
  - a missing or empty folder raises a clear error naming the folder and the
    Step 1 download

  *Done when:*
  - a test writes a small CSV in `tmp_path` and checks the parsed count and
    skip reasons
  - a test checks that an empty folder raises
  - a live run prints per-file counts for all six files

- [x] **Step 4 - Case builder.** Add `build_cases(matches)` returning
  `ClosingLineCase` rows (below). It:
  - replays `EloIndex` once over every loaded match
  - orients p1 as the lower player id, so p1 is not always the winner
  - takes ELO probability from surface ratings when both exist, else overall
    ratings, else None
  - takes the de-vigged close, and the de-vigged open when both opening prices
    exist
  - takes the blend from `ensemble.blend(EnsembleInput(...))` with tour `ATP`
    or `WTA` for scored categories, and for Challenger the tour label
    `app/services/tennis/predictor.py` passes for a Challenger match

  *Done when:* unit tests show:
  - a rating on a date excludes that date's matches (no same-day leakage)
  - orientation does not depend on who won
  - de-vig on a hand-worked pair
  - the ATP blend equals 0.35/0.60 ELO plus 0.25/0.60 market when ELO is
    reliable
  - the blend equals the market when a player has under 10 prior matches, or
    ELO and the market differ by 15 points or more
  - a Challenger case gets the same weights the live predictor applies
  - a player's first match has `elo_prob` None

- [x] **Step 5 - Report on the development season.** Add a pure
  `report(cases, summaries, holdout: bool) -> str` and the CLI `main()`, with
  `--holdout` and `--data-dir`. Without `--holdout`, holdout-season cases are
  never scored or printed. It prints:
  - the data credit and the pre-registered seasons
  - exclusion counts: not completed, no closing price, missing ELO, category
    not scored, qualifying, Laver Cup, and burn-in or excluded season; plus
    how many scored matches were completed by the truncation rule
  - per-tour n, log loss and Brier for ELO, blend and market
  - paired differences against the market with standard errors
  - calibration bins for ELO and the market
  - the three secondary reads
  - with `--holdout`, the verdict lines

  *Done when:*
  - a test on synthetic cases checks the section headers and exclusion counts
  - a test checks that the default run prints no holdout-season numbers
  - a test checks the verdict function on three hand-made differences (beats,
    rejected, inconclusive), including exactly 2 SE
  - the live development run is pasted under Results

- [x] **Step 6 - Holdout run, once.** Run
  `python -m app.backtest.tennis_closing_lines --holdout` a single time with
  the code as reviewed.

  *Done when:*
  - the full output and both verdicts are pasted under Results with the run
    date
  - a short reading states what the verdict means for 26d, per the rule table

## Files / areas

- `.gitignore` - ignore `api/data/valuebetennis/`.
- `api/app/core/valuebetennis.py` (new) - `VbtMatch`, `parse_row`.
- `api/app/backtest/tennis_closing_lines.py` (new) - loader, `ClosingLineCase`,
  `build_cases`, `report`, CLI, and the pre-registered constants.
- `api/tests/test_valuebetennis.py`, `api/tests/test_tennis_closing_lines.py`
  (new).

## Data / contracts

No schema change. These shapes are **load-bearing**, because 26d fits and
scores on them.

```python
@dataclass(frozen=True)
class VbtMatch:
    match_id: int
    tour: str                    # ATP | WTA (from genre)
    category: str                # ITF | Challenger | Main tour | Masters | Grand Slam | other labels as given
    round_code: int              # file's `tour`; 1-3 qualifying, 4+ main draw
    match_date: date             # date part of the start timestamp (Step 1)
    season: int
    tournament: str
    surface: str | None          # hard | clay | grass
    best_of: int
    p1_id: int                   # as in the file, not yet oriented
    p2_id: int
    winner_id: int
    score: str | None
    completed: bool              # is_completed_score, or the truncation rule
    truncated: bool              # score cut at the file's 20-character limit
    p1_open: float | None        # Pinnacle decimal odds
    p2_open: float | None
    p1_close: float | None
    p2_close: float | None

@dataclass(frozen=True)
class ClosingLineCase:
    tour: str
    category: str
    round_code: int              # for the qualifying exclusion
    tournament: str              # for the Laver Cup exclusion
    season: int
    match_date: date
    p1_id: int                   # the lower player id
    p2_id: int
    p1_won: bool
    completed: bool
    truncated: bool              # completed only by the truncation rule
    elo_prob: float | None       # computed ELO, p1-oriented
    market_prob: float | None    # de-vigged close, p1-oriented
    open_prob: float | None      # de-vigged open, p1-oriented
    blend_prob: float | None     # live blend() over elo_prob and market_prob, gates on
    p1_close_decimal: float | None
    p2_close_decimal: float | None
```

`GradedPrediction` from 26a is deliberately **not** reused: its
`generated_at` and `market_book` fields have no meaning here. The scoring
functions in `app.core.tennis_grading` (`score_component`,
`paired_loss_difference`, `calibration_bins`) are reused unchanged.

The season constants and verdict thresholds live at the top of
`tennis_closing_lines.py`, marked pre-registered, as in `nfl_game_lines.py`.

## Testing

- The test gate is on: Steps 2 to 5 each ship unit tests. Step 1 is config
  and a one-off check, shown with `git status` and the recorded numbers.
- Run with `cd api && .venv\Scripts\python.exe -m pytest`.
- Tests use hand-built rows and a tiny generated CSV, never the real
  downloads, so the suite runs without them.
- Evidence beyond the tests: Step 3's per-file counts, Step 5's development
  report and Step 6's holdout report, all pasted under Results.
- No web change.

## Notes

**Step 1 source facts (2026-10-01, from the 2021 and 2022 files only).** All
six files downloaded (9.5 to 13.7 MB each, HTTP 200). They are UTF-8 with a
BOM, `;`-separated, 147,109 rows across 2021-2022.

- **Columns:** `match_id; date; tournoi; tournoi_id; categorie; genre;
  surface; tour; joueur1; joueur1_id; joueur2; joueur2_id; cote1_ouverture;
  cote2_ouverture; cote1_cloture; cote2_cloture; vainqueur_id; score;
  duree_min`.
- **Values are French and lowercase**, unlike the spec's labels:

  | Column | Values (2021-2022 rows) |
  |---|---|
  | `genre` | `atp` 86,917, `wta` 60,192 |
  | `categorie` | `ITF` 88,282, `Challenger` 42,047, `Main tour` 8,771, **`Grand Chelem`** 3,820, `Masters` 2,959, blank 869, `Coupe Davis / BJK Cup` 361 |
  | `surface` | `terre battue` 69,218, `dur` 60,407, `dur intérieur` 13,177, `gazon` 2,953, `moquette intérieur` 1,354 (carpet) |
  | `tour` (round code) | 1, 2, 3 = qualifying rounds; 4 = first main-draw round at a Slam (R128), then 5, 6, 7, 9 (QF), 10 (SF), 12 (F); 8 is round robin. Inferred from Slam counts (512 / 256 / 128 / 512 / 256 / 128 / 64 / 32 / 16 / 8 over two years). |

- **`date` is a start timestamp, not a midnight date.** 99.2% of scored-category
  rows carry a real time (`2021-01-13 11:00:00`); 27% of all rows (mostly ITF)
  are midnight. The timezone is not stated. Every row sits in its file's year.
- **`score` is written from joueur1's side**, not the winner's (`"4-6 3-6"`
  when joueur2 won). It agrees with `vainqueur_id` on 99.94% of 10,287
  completed best-of-3 tour rows. `is_completed_score` is side-symmetric, so
  this does not matter to it.
- **Tie-break notation `7-6(3)` is handled.** 93.5% of tie-break rows count as
  completed.
- **Retirements and walkovers:** a walkover is a blank score (165 scored rows);
  a retirement is a score that stops mid-set (`"6-3 3-1"`), with `ret.` written
  only twice. 1,165 of 1,443 non-completed scored rows lasted under 30 minutes.
- **Scores are truncated at 20 characters.** 217 scored rows, 182 of them ATP
  Slam five-setters (`"7-6(3) 6-7(3) 3-6 7-"`). `is_completed_score` rejects
  them as unfinished.
- **Qualifying sits inside `Grand Chelem`, `Main tour` and `Masters`.** ATP
  Slam qualifying is best-of-3 (rounds 1 and 2 complete 89-91% as best-of-3, 0%
  as best-of-5), and round 3 is mixed (Wimbledon's final qualifying round is
  best-of-5). The ATP Slam main draw completes only 72-81% under best-of-5,
  mostly because of truncation.
- **Long final sets fail `_finished_set`:** 19 scored rows, from 2021 advantage
  sets (French Open `10-8`, Wimbledon `8-10`), match tie-breaks at three 2021
  Melbourne WTA events, and the Laver Cup (filed as `Main tour`).
- **Closing odds start in March 2022.** No 2021 row has a close, and almost no
  January-February 2022 row does (99.9% missing). From 2022-03 onward, 3.9% of
  6,072 scored rows miss a close and 1.3% miss an open. Opening prices exist
  throughout.

**Closing-odds timing check (2026).** 1,672 Valuebetennis 2026 scored-category
matches joined one-to-one to stored ATP/WTA matches with a pre-start moneyline
(date +/- 1 day, tour, both surnames; 1 ambiguous dropped). The app's last
pre-start price was a median 1.9 hours before start.

| De-vigged Valuebetennis price | Mean gap to app's pre-start price | Median gap |
|---|---|---|
| Open | 2.61 pts | 1.77 pts |
| Close | **1.57 pts** | **1.04 pts** |

The close is nearer the app's price than the open on 63.6% of matches. **The
close is clearly a near-start price**, so the rule's assumption holds.

## Results

### Development run (2026-10-01, Step 5)

`python -m app.backtest.tennis_closing_lines`, development season 2022 only.

```
Tennis closing-line backtest (26c) - development seasons 2022
  Data: Valuebetennis open data (valuebetennis.com), CC BY 4.0. Pinnacle opening and closing odds.
  Pre-registered: burn-in [2021], development [2022], holdout [2023, 2024, 2025] (scored once).
  elo (computed) is replayed from these results; it is not the live TennisAbstract ELO.
  files 6, rows 462775, parsed 462772
  Holdout seasons are neither scored nor shown; run --holdout once, after review.

Exclusions
  burn-in or excluded season    129245
  category not scored            75559
  qualifying                      2738
  Laver Cup                          8
  not completed                    788
  no closing price                1019
  missing ELO                        2
  scored                          3267  (completed by the truncation rule: 57)

Log loss and Brier (lower is better; same matches in every column)
  group          n     elo (computed)              blend             market
                       logloss  brier     logloss  brier     logloss  brier
  ATP         1706    0.6621   0.2330    0.5838   0.2004    0.5790   0.1986
  WTA         1561    0.7007   0.2503    0.5944   0.2051    0.5841   0.2010
  ATP+WTA     3267    0.6805   0.2412    0.5889   0.2026    0.5814   0.1998

Paired log-loss difference vs the close (negative = beats the close; +/- one standard error)
  ATP      n=1706   elo (computed) +0.0831 +/- 0.0095   blend +0.0048 +/- 0.0019
  WTA      n=1561   elo (computed) +0.1167 +/- 0.0109   blend +0.0103 +/- 0.0023
  ATP+WTA  n=3267   elo (computed) +0.0991 +/- 0.0072   blend +0.0074 +/- 0.0015

Calibration, ATP+WTA (bin: mean predicted / actual p1 win rate)
  elo (computed) 0.0-0.1: 0.08/0.20 (n=71)  0.1-0.2: 0.15/0.29 (n=215)  0.2-0.3: 0.25/0.36 (n=416)  0.3-0.4: 0.35/0.45 (n=496)  0.4-0.5: 0.45/0.46 (n=551)  0.5-0.6: 0.55/0.53 (n=525)  0.6-0.7: 0.65/0.61 (n=448)  0.7-0.8: 0.75/0.64 (n=346)  0.8-0.9: 0.84/0.72 (n=164)  0.9-1.0: 0.92/0.77 (n=35)
  market         0.0-0.1: 0.07/0.04 (n=57)  0.1-0.2: 0.16/0.12 (n=235)  0.2-0.3: 0.25/0.24 (n=357)  0.3-0.4: 0.35/0.35 (n=522)  0.4-0.5: 0.45/0.48 (n=467)  0.5-0.6: 0.55/0.52 (n=477)  0.6-0.7: 0.65/0.63 (n=467)  0.7-0.8: 0.75/0.73 (n=372)  0.8-0.9: 0.84/0.90 (n=245)  0.9-1.0: 0.93/0.96 (n=68)

Flat-stake ROI at the close (blend - close >= 3 pts, either side; never decisive)
  ATP      picks   636  won   270  units    -57.78  ROI -9.1%
  WTA      picks   598  won   240  units    -90.90  ROI -15.2%
  ATP+WTA  picks  1234  won   510  units   -148.68  ROI -12.0%

Open-to-close CLV toward elo (computed) (stands in for the blend; never decisive)
  ATP                   eligible   1706  moved   1704  toward    915 (53.7%)  mean move toward +0.33 pts
  ATP, gap >= 3 pts     eligible   1443  moved   1441  toward    778 (54.0%)  mean move toward +0.38 pts
  WTA                   eligible   1561  moved   1558  toward    865 (55.5%)  mean move toward +0.56 pts
  WTA, gap >= 3 pts     eligible   1359  moved   1356  toward    756 (55.8%)  mean move toward +0.60 pts
  ATP+WTA               eligible   3267  moved   3262  toward   1780 (54.6%)  mean move toward +0.44 pts
  ATP+WTA, gap >= 3 pts eligible   2802  moved   2797  toward   1534 (54.8%)  mean move toward +0.48 pts

Challenger (secondary, live Challenger blend weights; never decisive)
  group          n     elo (computed)              blend             market
                       logloss  brier     logloss  brier     logloss  brier
  ATP         3926    0.7162   0.2572    0.6199   0.2158    0.6169   0.2144
  WTA         6526    0.6475   0.2273    0.5645   0.1917    0.5592   0.1898
  ATP+WTA    10452    0.6733   0.2385    0.5853   0.2008    0.5809   0.1990

Paired log-loss difference vs the close (negative = beats the close; +/- one standard error)
  ATP      n=3926   elo (computed) +0.0993 +/- 0.0071   blend +0.0030 +/- 0.0014
  WTA      n=6526   elo (computed) +0.0882 +/- 0.0049   blend +0.0053 +/- 0.0010
  ATP+WTA  n=10452  elo (computed) +0.0924 +/- 0.0040   blend +0.0045 +/- 0.0008
```

**Reading (development only, not a verdict):**
- **The blend trails the close** by +0.0074 +/- 0.0015 ATP+WTA (about 5 SE),
  on both tours. Betting the blend's 3+ point disagreements at the close
  returned -12.0% on 1,234 picks.
- **Computed ELO is overconfident** (0.08 predicted won 0.20; 0.92 won 0.77)
  and trails the close by +0.0991. Its replay has one burn-in year, and new
  players move at K of about 130, so ratings are noisy this early. Not tuned,
  per the spec; the holdout seasons have two to four years of history behind
  them.
- **The close moved toward ELO on 54.6%** of matches, by +0.44 points on
  average, much as 26a's live 58% / +0.36.
- **Challenger** shows the same picture: the blend +0.0045 +/- 0.0008 behind
  the close.

## Notes for the AI

- **Never fetch Valuebetennis from app code.** The backtest reads local files,
  so it is reproducible from the downloads alone.
- **Do not read the 2023-2025 files** beyond what the loader needs to parse
  them, until Step 6. Step 1's source facts come from 2021 and 2022 only. Do
  not print, sample or eyeball holdout rows while building.
- **The holdout is scored once.** Do not run `--holdout` while developing, and
  do not change the constants, the eligibility filter or the ELO after it has
  run. If something is found broken afterwards, record it and the rerun under
  Results as a second, labeled run; never overwrite the first.
- **Keep `app/core/` pure.** The parser takes a mapping, not a file. pandas and
  file reading stay in `app/backtest/`.
- **Reuse, don't copy:** `EloIndex` from `app.ml.elo_history`; `blend` and
  `EnsembleInput` from `app.services.tennis.ensemble`; `devig_two_way` from
  `app.core.odds`; `is_completed_score` and the scoring functions from
  `app.core.tennis_grading`. Decimal odds become raw probabilities as
  `1 / decimal`.
- **Same-day leakage.** `EloIndex.rating(pid, before=date)` excludes matches
  on that date. If Step 1 finds every row stamped midnight, later rounds on one
  day still use only earlier days' ratings: stale, never leaked.
- **Computed ELO is a stand-in.** Label it `elo (computed)` in the output, and
  never describe its result as the live TennisAbstract ELO's.
- **Small differences matter.** With thousands of matches a season the standard
  errors are small, so phrase results by the pre-registered rule, not by eye.
- **Credit the data** (Valuebetennis, CC BY 4.0) in the CLI header and the
  module docstring.
- Standards: `X | None` in new code, no `Any`, no em dashes, comment only the
  why.

### Holdout run (2026-10-01, Step 6, the one scored run)

`python -m app.backtest.tennis_closing_lines --holdout`, run once with the code
at commit `5303944` (clean working tree for `api/app` and `api/tests`).

```
Tennis closing-line backtest (26c) - HOLDOUT seasons 2023, 2024, 2025
  Data: Valuebetennis open data (valuebetennis.com), CC BY 4.0. Pinnacle opening and closing odds.
  Pre-registered: burn-in [2021], development [2022], holdout [2023, 2024, 2025] (scored once).
  elo (computed) is replayed from these results; it is not the live TennisAbstract ELO.
  files 6, rows 462775, parsed 462772

Exclusions
  burn-in or excluded season    212626
  category not scored           227807
  qualifying                      7566
  Laver Cup                         24
  not completed                   2548
  no closing price                 132
  missing ELO                        1
  scored                         12068  (completed by the truncation rule: 100)

Log loss and Brier (lower is better; same matches in every column)
  group          n     elo (computed)              blend             market
                       logloss  brier     logloss  brier     logloss  brier
  ATP         6215    0.6480   0.2282    0.5902   0.2033    0.5864   0.2018
  WTA         5853    0.6509   0.2289    0.5934   0.2045    0.5852   0.2012
  ATP+WTA    12068    0.6494   0.2285    0.5918   0.2039    0.5858   0.2015

Paired log-loss difference vs the close (negative = beats the close; +/- one standard error)
  ATP      n=6215   elo (computed) +0.0616 +/- 0.0043   blend +0.0039 +/- 0.0011
  WTA      n=5853   elo (computed) +0.0657 +/- 0.0044   blend +0.0082 +/- 0.0013
  ATP+WTA  n=12068  elo (computed) +0.0636 +/- 0.0031   blend +0.0060 +/- 0.0008

Calibration, ATP+WTA (bin: mean predicted / actual p1 win rate)
  elo (computed) 0.0-0.1: 0.07/0.13 (n=197)  0.1-0.2: 0.16/0.22 (n=709)  0.2-0.3: 0.25/0.32 (n=1241)  0.3-0.4: 0.35/0.40 (n=1851)  0.4-0.5: 0.45/0.46 (n=2261)  0.5-0.6: 0.55/0.53 (n=2220)  0.6-0.7: 0.65/0.61 (n=1732)  0.7-0.8: 0.74/0.71 (n=1134)  0.8-0.9: 0.84/0.76 (n=602)  0.9-1.0: 0.93/0.85 (n=121)
  market         0.0-0.1: 0.07/0.04 (n=329)  0.1-0.2: 0.16/0.14 (n=752)  0.2-0.3: 0.25/0.25 (n=1283)  0.3-0.4: 0.35/0.35 (n=1785)  0.4-0.5: 0.45/0.43 (n=1862)  0.5-0.6: 0.55/0.54 (n=1933)  0.6-0.7: 0.65/0.66 (n=1826)  0.7-0.8: 0.75/0.74 (n=1299)  0.8-0.9: 0.85/0.86 (n=749)  0.9-1.0: 0.93/0.96 (n=250)

Flat-stake ROI at the close (blend - close >= 3 pts, either side; never decisive)
  ATP      picks  2514  won  1034  units   -148.38  ROI -5.9%
  WTA      picks  2700  won  1064  units   -223.52  ROI -8.3%
  ATP+WTA  picks  5214  won  2098  units   -371.90  ROI -7.1%

Open-to-close CLV toward elo (computed) (stands in for the blend; never decisive)
  ATP                   eligible   6215  moved   6209  toward   3315 (53.4%)  mean move toward +0.42 pts
  ATP, gap >= 3 pts     eligible   5173  moved   5170  toward   2782 (53.8%)  mean move toward +0.48 pts
  WTA                   eligible   5853  moved   5841  toward   3140 (53.8%)  mean move toward +0.50 pts
  WTA, gap >= 3 pts     eligible   4866  moved   4856  toward   2654 (54.7%)  mean move toward +0.61 pts
  ATP+WTA               eligible  12068  moved  12050  toward   6455 (53.6%)  mean move toward +0.46 pts
  ATP+WTA, gap >= 3 pts eligible  10039  moved  10026  toward   5436 (54.2%)  mean move toward +0.54 pts

Challenger (secondary, live Challenger blend weights; never decisive)
  group          n     elo (computed)              blend             market
                       logloss  brier     logloss  brier     logloss  brier
  ATP        14039    0.6716   0.2387    0.6229   0.2170    0.6174   0.2147
  WTA        20220    0.6528   0.2301    0.6078   0.2099    0.6019   0.2075
  ATP+WTA    34259    0.6605   0.2336    0.6140   0.2128    0.6082   0.2104

Paired log-loss difference vs the close (negative = beats the close; +/- one standard error)
  ATP      n=14039  elo (computed) +0.0543 +/- 0.0026   blend +0.0055 +/- 0.0008
  WTA      n=20220  elo (computed) +0.0509 +/- 0.0021   blend +0.0059 +/- 0.0006
  ATP+WTA  n=34259  elo (computed) +0.0523 +/- 0.0016   blend +0.0057 +/- 0.0005

Verdict (ATP+WTA holdout; pre-registered at 2 standard errors)
  elo (computed) +0.0636 +/- 0.0031  ->  rejected against the close
  blend          +0.0060 +/- 0.0008  ->  rejected against the close
```

**Verdict (pre-registered rule, ATP+WTA, 12,068 matches):**

| Candidate | Paired log loss vs close | Verdict |
|---|---|---|
| elo (computed) | +0.0636 +/- 0.0031 | **rejected against the close** |
| blend (live, gated) | +0.0060 +/- 0.0008 | **rejected against the close** (7.5 SE) |

**What it means for 26d** (per the rule table):
- **The hand-set weights are rejected.** 26d is justified in replacing them
  with a market-anchored fit, scored on this same 2023-2025 holdout under its
  own pre-registered rule.
- **Nothing beat the close, so no leakage audit is triggered.**
- **Context, never decisive:**
  - The blend trails on both tours (ATP +0.0039, WTA +0.0082) and on
    Challenger (+0.0057 +/- 0.0005).
  - Betting its 3+ point disagreements at the close lost 7.1% on 5,214 picks.
  - Computed ELO is still overconfident at the extremes (0.93 predicted won
    0.85).
  - The close moved toward ELO on 53.6% of matches, by +0.46 points on
    average: real but small, and too small to beat the close at its own price.
- **26d's likely shape:** with ELO's information this far behind the close,
  a fitted blend should lean heavily on the market. Whether any ELO weight
  survives is 26d's question, not this one.


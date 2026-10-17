# Feature: PrizePicks line settlement

**From build-plan:** feature 26b
**Status:** complete

## Goal

Answer, from data already stored, whether PrizePicks tennis lines lean one way.
Settle every stored PrizePicks line that the final match score alone decides:

- total games
- games won
- sets
- tie breaks
- first-set games and first-set games won

Report how often each stat and odds type (standard, goblin, demon) went over,
under or pushed, with the OVER hit rate set beside the break-even the app assumes
for that odds type. First, measure how often props link to a match and to a box
score. That link rate is the baseline 26e has to raise.

It is a read-only report with no model change and no schema change. It says
nothing about the app's confidence tiers. They are computed on page load from
overwritten rolling stats, so grading them after the fact would leak the result.
That is 26f.

## In scope

- **Pure settlement code** in `app/core/prop_settlement.py`:
  - parse a stored score into sets
  - compute the actual value of each score-derivable stat for one player
  - settle a line as over, under or push
- **A repository loader** that returns one row per graded line:
  - the **closing pre-start snapshot**: for each (player, match, stat, odds
    type), every line in the latest PrizePicks fetch strictly before
    `start_utc`
  - the match's score, best-of, tour, and which side the player is on
- **A coverage query** that counts, over all stored PrizePicks rows and over
  distinct player-matches:
  - how many link to a match
  - how many of those matches are settled with a finished score
  - how many join to a box score (`player_match_stats`) on the exact date, and
    how many join to exactly one within the window used on 2026-09-25
- **A command-line report**, run from `api/` as
  `python -m app.backtest.tennis_prizepicks_lines`. It prints:
  - coverage
  - exclusion counts
  - a settlement table by stat and odds type, overall and by tour

## Out of scope

- Aces, double faults, break points won and Fantasy Score settlement. These need
  box scores the stored rows cannot join to reliably (26e).
- Grading the app's projections, hit probabilities or confidence tiers (26f).
  Recomputing them now would use rolling stats that include the graded match.
- Improving prop-to-match linking. Coverage is measured here, not fixed.
- Any change to `props`, `player_match_stats`, ingest, the props page or the
  payout table in `app/core/prop_ev.py`.
- An API endpoint, UI or scheduled job. It stays a CLI, like the 26a report.

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

- [x] **Step 1 - Pure settlement core.** Add `app/core/prop_settlement.py`:
  - `SETTLEABLE_STATS`: the six normalized stat types below
  - `parse_sets(score) -> list[tuple[int, int]]`, p1-oriented
  - `actual_value(stat, sets, player_is_p1) -> int | None`
  - `settle(actual, line) -> LineOutcome`

  *Done when:* unit tests cover:
  - each of the six stats on a straight-sets score and a three-set score with a
    tie break
  - games won and first-set games won from both sides (p1 and p2)
  - a best-of-5 score
  - a whole-number line pushing and a half line never pushing
  - an unsupported stat (`aces`) returning None
  - an empty score returning no sets
- [x] **Step 2 - Closing-line loader.** Add `get_settleable_prizepicks_lines(db)`
  to `app/repositories/props.py`. It returns `PrizePicksLineRow` rows (below):
  - PrizePicks rows with a player and a match, where the player is `p1_id` or
    `p2_id`
  - match `status = 'completed'`, a winner, and a non-null `start_utc`
  - only rows with `fetched_at < start_utc`
  - a link within 12 hours of the prop's own `start_time`, the same guard the
    props page uses against a link to an earlier meeting (added while building)
  - per (player, match, stat_type, odds_type), only rows at that key's latest
    such `fetched_at`
  - distinct lines within that snapshot

  Rows flagged live, in-game or promo in `raw_json->'attributes'` (`is_live`,
  `in_game`, `is_promo`, a non-null `flash_sale_line_score`) are **returned with
  their flags**, not filtered in SQL, so the report can count them.

  *Done when:*
  - Recorded-SQL tests show:
    - the strict `fetched_at < m.start_utc`
    - the per-key latest-snapshot selection
    - the player-on-side condition
  - A live read-only run prints the row count and the split by odds type.
- [x] **Step 3 - Coverage query.** Add `get_prizepicks_link_coverage(db)` to the
  same repository, returning `PrizePicksCoverage` (below).

  *Done when:*
  - A recorded-SQL test shows the box-score joins use `player_id`, `result`
    and the date window.
  - A live run reproduces, within a few rows, the 2026-09-25 figures:
    - 201,886 rows, 57,774 linked
    - 2,858 settled player-matches
    - 111 on the exact date
    - 385 with a unique window candidate

    New fetches since then explain any drift.
- [x] **Step 4 - Report.** Add `app/backtest/tennis_prizepicks_lines.py`, with a
  pure `report(rows, coverage) -> str` and an async CLI `_main`, following
  `app/backtest/tennis_predictions.py`. It prints:
  - **Coverage**, from Step 3.
  - **Exclusions:**
    - live or in-game snapshots
    - promo or flash-sale lines
    - retirements, walkovers and inconsistent scores (`is_completed_score`
      false, with `best_of` defaulting to 3)
    - stats not score-derivable, counted by stat type
  - **Settlement by normalized stat and odds type:**
    - lines, distinct player-matches
    - over %, under %, push %
    - mean actual minus line
    - the OVER hit rate among non-push lines, with a binomial standard error
      **for standard lines only**
    - the break-even from `app.core.prop_ev` for that odds type
  - **The same table for standard lines, by tour** (ATP, WTA, CHALLENGER).

  *Done when:*
  - A test on synthetic rows checks the section headers, the exclusion counts,
    that pushes are left out of the hit rate, and that goblin and demon rows
    carry no standard error.
  - `python -m app.backtest.tennis_prizepicks_lines` runs against the live
    database, and its output is pasted under Results with a short reading.

## Files / areas

- `api/app/core/prop_settlement.py` (new) - pure settlement.
- `api/app/repositories/props.py` - `PrizePicksLineRow`,
  `get_settleable_prizepicks_lines`, `PrizePicksCoverage`,
  `get_prizepicks_link_coverage`.
- `api/app/backtest/tennis_prizepicks_lines.py` (new) - report and CLI.
- `api/tests/test_prop_settlement.py`, `api/tests/test_prizepicks_line_loader.py`,
  `api/tests/test_prizepicks_line_report.py` (new).

## Data / contracts

No schema change. These are **load-bearing**. 26e adds box-score stats to the
same settlement path, and 26f settles its stored projections through
`actual_value` and `settle`:

```python
# app/core/prop_settlement.py
SETTLEABLE_STATS = frozenset({
    "total_games",               # both players, whole match; a 7-6 set is 13
    "total_games_won",           # this player, whole match
    "total_sets",
    "total_tie_breaks",          # sets scored 7-6 or 6-7
    "1st_set_total_games",       # both players, first set
    "1st_set_total_games_won",   # this player, first set
})
LineOutcome = Literal["over", "under", "push"]

# app/repositories/props.py
@dataclass(frozen=True)
class PrizePicksLineRow:
    prop_id: int
    player_id: int
    match_id: int
    tour: str                  # matches.tour: ATP | WTA | CHALLENGER
    stat_type: str             # as stored, e.g. "1st Set Total Games"
    odds_type: str | None      # standard | goblin | demon
    line: float
    fetched_at: datetime       # the closing pre-start snapshot
    start_utc: datetime
    player_is_p1: bool
    score: str | None          # matches.score, p1-oriented
    best_of: int | None
    is_live: bool              # attributes.is_live or attributes.in_game
    is_promo: bool             # attributes.is_promo or a flash-sale line

@dataclass(frozen=True)
class PrizePicksCoverage:
    rows: int                        # all PrizePicks snapshots
    rows_linked: int                 # with player_id and match_id
    player_matches: int              # distinct linked (player, match)
    player_matches_settled: int      # completed, with a winner
    box_score_exact_date: int        # same player, result, match_date
    box_score_unique_in_window: int  # exactly one same-result row, date in [d-14, d+3]
```

Stat names are matched through `app.core.prop_projection.normalize_stat_type`
("1st Set Total Games" becomes `1st_set_total_games`).

## Testing

- The test gate is on:
  - Step 1 ships pure unit tests.
  - Steps 2 and 3 ship recorded-SQL tests, following
    `tests/test_graded_predictions.py`.
  - Step 4 ships a report test on synthetic rows.
- Run with `cd api && .venv\Scripts\python.exe -m pytest`.
- Evidence beyond the tests:
  - Step 2's live row count
  - Step 3's live coverage
  - Step 4's live report, pasted under Results
- No web change.

## Results

`python -m app.backtest.tennis_prizepicks_lines`, run 2026-09-25 against the
stored data (read-only):

```text
PrizePicks line settlement (score-derived stats)

Coverage
  PrizePicks snapshots stored:               201886
  linked to a player and a match:            57774 (28.6%)
  distinct linked player-matches:            3096
  settled (completed, with a winner):        2858
  box score on the exact match date:         111 (3.9%)
  exactly one box score in [d-14, d+3]:      385 (13.5%)

Closing pre-start lines
  lines in the last snapshot before the start: 36539
  excluded, live or in-game when fetched:      1373
  excluded, promo or flash-sale:               0
  excluded, retirement, walkover or bad score: 547
  excluded, needs a box score (26e):           16718
    double_faults                             7659
    aces                                      6502
    fantasy_score                             1679
    break_points_won                           844
    1st_set_aces                                34
  settled:                                     17901

Settlement by stat and odds type (over hit excludes pushes; b/even is the app's assumed break-even, not PrizePicks')
  stat                       lines    p-m    over  under   push  act-ln   over hit          b/even
 standard (2117 lines)
  1st_set_total_games           78     78   46.2%  53.8%   0.0%   +0.27    46.2% +/- 5.6%    57.7%
  1st_set_total_games_won      227    227   51.5%  48.0%   0.4%   -0.29    51.8% +/- 3.3%    57.7%
  total_games                 1006    970   47.9%  50.5%   1.6%   +1.09    48.7% +/- 1.6%    57.7%
  total_games_won              774    770   48.2%  51.0%   0.8%   -0.28    48.6% +/- 1.8%    57.7%
  total_sets                     6      6   50.0%  50.0%   0.0%   +0.00    50.0% +/- 20.4%   57.7%
  total_tie_breaks              26     26   19.2%  80.8%   0.0%   -0.31    19.2% +/- 7.7%    57.7%
 goblin (6636 lines)
  1st_set_total_games          420    403   74.0%  26.0%   0.0%   +1.27    74.0%             75.8%
  1st_set_total_games_won      403    402   70.2%  29.8%   0.0%   +0.05    70.2%             75.8%
  total_games                 2659   1044   67.2%  32.8%   0.0%   +3.73    67.2%             75.8%
  total_games_won             3044   1277   68.9%  31.1%   0.0%   +1.91    68.9%             75.8%
  total_sets                    59     59   61.0%  39.0%   0.0%   +0.33    61.0%             75.8%
  total_tie_breaks              51     51   64.7%  35.3%   0.0%   +0.34    64.7%             75.8%
 demon (9148 lines)
  1st_set_total_games          424    404   25.7%  74.3%   0.0%   -0.87    25.7%             41.3%
  1st_set_total_games_won       90     90   24.4%  75.6%   0.0%   -0.87    24.4%             41.3%
  total_games                 2913   1041   30.3%  69.7%   0.0%   -3.12    30.3%             41.3%
  total_games_won             3746   1525   25.3%  74.7%   0.0%   -2.65    25.3%             41.3%
  total_sets                   765    763   33.6%  66.4%   0.0%   -0.19    33.6%             41.3%
  total_tie_breaks            1210   1029   22.0%  78.0%   0.0%   -0.43    22.0%             41.3%

Standard lines, ATP
  stat                       lines    p-m    over  under   push  act-ln   over hit          b/even
 standard (917 lines)
  1st_set_total_games           37     37   43.2%  56.8%   0.0%   +0.36    43.2% +/- 8.1%    57.7%
  1st_set_total_games_won       56     56   41.1%  58.9%   0.0%   -0.64    41.1% +/- 6.6%    57.7%
  total_games                  386    371   44.8%  53.9%   1.3%   +0.44    45.4% +/- 2.6%    57.7%
  total_games_won              406    405   44.6%  53.9%   1.5%   -0.60    45.2% +/- 2.5%    57.7%
  total_sets                     6      6   50.0%  50.0%   0.0%   +0.00    50.0% +/- 20.4%   57.7%
  total_tie_breaks              26     26   19.2%  80.8%   0.0%   -0.31    19.2% +/- 7.7%    57.7%

Standard lines, WTA
  stat                       lines    p-m    over  under   push  act-ln   over hit          b/even
 standard (943 lines)
  1st_set_total_games           35     35   45.7%  54.3%   0.0%   +0.04    45.7% +/- 8.4%    57.7%
  1st_set_total_games_won      102    102   54.9%  44.1%   1.0%   -0.14    55.4% +/- 4.9%    57.7%
  total_games                  505    484   50.5%  47.5%   2.0%   +1.50    51.5% +/- 2.2%    57.7%
  total_games_won              301    298   51.2%  48.8%   0.0%   +0.09    51.2% +/- 2.9%    57.7%

Standard lines, CHALLENGER
  stat                       lines    p-m    over  under   push  act-ln   over hit          b/even
 standard (257 lines)
  1st_set_total_games            6      6   66.7%  33.3%   0.0%   +1.00    66.7% +/- 19.2%   57.7%
  1st_set_total_games_won       69     69   55.1%  44.9%   0.0%   -0.21    55.1% +/- 6.0%    57.7%
  total_games                  115    115   47.0%  52.2%   0.9%   +1.47    47.4% +/- 4.7%    57.7%
  total_games_won               67     67   56.7%  43.3%   0.0%   +0.02    56.7% +/- 6.1%    57.7%
```

**Reading. Six months of data, mostly the last month (linking was poor before
late August):**

- **The stat definitions hold.** Mean actual minus line on standard lines is
  +1.09 for total games and -0.28 for games won. Neither is anywhere near double
  the line, so "Total Games" (both players) and "Total Games Won" (this player)
  are read correctly.
- **Standard lines are close to a coin flip.** Total games overs hit 48.7% +/-
  1.6% (970 player-matches) and games won 48.6% +/- 1.8%. Neither side of either
  stat approaches the 57.7% the app assumes a standard leg needs. PrizePicks'
  main lines show no exploitable lean on their own.
- **Total games runs above the line on average but under it more often than
  not** (+1.09 games, 48.7% overs). The distribution is skewed: a three-setter
  clears the line by a lot, and straight sets miss it by a little. A projection
  that targets the mean will lean over too often.
- **ATP standard lines lean under, WTA does not.** ATP total games overs hit
  45.4% +/- 2.6% and games won 45.2% +/- 2.5%, each under 50% by about two
  standard errors. WTA sits at 51.5% and 51.2%. The ATP under hits about 54.5%,
  still short of 57.7% on its own. It is a lean to watch, not a play.
- **Standard tie-break unders hit 80.8% (21 of 26).** That clears 57.7% by
  about three standard errors, but on 26 lines. Treat it as a hypothesis for
  26f, not a result.
- **Blind goblin and demon overs lose at the assumed payouts.** Goblins hit 61%
  to 74% against an assumed 75.8% break-even; demons hit 22% to 34% against
  41.3%. These rates are over correlated lines with no error bar, and the
  break-evens are the app's hand-set table, but the gaps are wide in every
  stat.
- **Coverage is the binding limit for box-score stats.** 16,718 closing lines
  (aces, double faults, break points, fantasy) cannot be settled, and only 385
  of 2,858 settled player-matches (13.5%) have one unambiguous box score. That
  is 26e's baseline.
- **In-play leakage risk.** 1,373 pre-start lines were flagged live by
  PrizePicks, which means our stored `start_utc` is sometimes hours late. Lines
  in play but not flagged could slip through; the flagged share (about 4%) bounds
  how common that is.

## Notes for the AI

- **Repositories own SQL.** The loader and the coverage query live in
  `app/repositories/props.py`. The core and backtest modules make no queries.
- **Keep `app/core/prop_settlement.py` pure:** no database, no clock.
- **Reuse, don't copy:**
  - `is_completed_score` from `app.core.tennis_grading`
  - `normalize_stat_type` from `app.core.prop_projection`
  - `leg_decimal_odds` and `break_even_probability` from `app.core.prop_ev`
- **Scores are p1-oriented plain set scores** ("6-7 7-6 6-4"), with no tie-break
  points. A 7-6 or 6-7 set is one tie break and 13 games. Flip to the player's
  side with `player_is_p1`.
- **Stat definitions are assumed, not documented by PrizePicks:** "Total Games"
  covers both players and "Total Games Won" this player only. In Step 4, check
  mean actual minus line per stat. A mean far from zero, for example actual
  near twice the line, means a wrong definition. Stop and fix it; don't report
  it as a lean.
- **`best_of` is sometimes wrong or null.** A two-set score labeled best-of-5
  fails `is_completed_score` and is excluded, which is correct. Count it rather
  than guessing the format.
- **Snapshots are daily.** Each PrizePicks ingest run shares one `fetched_at`.
  "Latest before start" is therefore one run's lines. About 10% of linked rows
  (5,958 on 2026-09-25) were fetched at or after the start and must never be
  graded.
- **Demon and goblin lines are correlated.** One player-stat can carry up to 8
  demon lines in a snapshot. Report the line count and the distinct
  player-matches, and give no standard error for those odds types. Standard lines
  average 1.06 per key, so their error bar is fair.
- **The break-even is the app's assumption,** not PrizePicks'. The tier table in
  `prop_ev.py` is hand-encoded: standard 57.7%, goblin 75.8%, demon 41.3%. Label
  it "assumed break-even".
- **Small, early sample.** Linking was poor before late August. Report n with
  every rate, and don't call a lean settled unless it exceeds about two standard
  errors.
- Never call the PrizePicks API. Everything reads stored tables.
- Standards: `X | None` in new code, no `Any`, no em dashes, comment only the why.

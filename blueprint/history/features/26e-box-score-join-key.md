# Feature: Box-score join key

**From build-plan:** feature 26e
**Status:** complete

## Goal

Make each TennisAbstract box score joinable to exactly one stored match. Then use
that join to settle the PrizePicks stats that need a box score (aces, double
faults, break points won), both:

- in 26b's historical line report
- in 26f's daily projection snapshots, which have stored aces and double-fault
  picks since 2026-09-25

Today only 3.9% of settled prop player-matches join on the exact date, and 13.5%
to a single candidate. The reason is that `player_match_stats` rows are dated by
tournament start and carry no opponent. The source rows do have the opponent,
round, tournament and score; the parser drops them.

## Facts this spec rests on (checked 2026-09-25)

| Fact | Evidence |
|---|---|
| TennisAbstract rows carry what the join needs | Index 1 tournament, 8 round (`F`, `SF`, `R16`...), 9 score, 11 opponent full name. Seen on Sinner (ATP, classic page) and Swiatek (WTA, `jsmatches`). |
| Row dates are tournament starts | Every Sinner Wimbledon row is `20260629`, and every Swiatek US Open row is `20260831`. |
| The score is winner-first, with tie-break points | Sinner W `6-7(7) 7-6(2) 6-3 6-4`; Swiatek L `7-5 6-3`. It can be compared with `matches.score` once both are oriented winner-first. |
| The upsert key is a hash of the whole raw row | Re-ingesting the same rows updates them in place, so a backfill fills the new columns without duplicates. |
| The daily stats job only fetches players playing today or tomorrow | `tennis-ingest.yml`: `--today-only --match-days-back 0 --match-days-ahead 1`. A box score for a finished match arrives only when that player next plays, and never for a player who does not play again soon. |

## In scope

- **Migration `0035`:** nullable `opponent_name`, `round`, `tournament` and
  `score` text columns on `player_match_stats`.
- **The TennisAbstract parser stores them,** and the upsert updates them.
- **A pure join** (`app/core/box_score_join.py`). A box score belongs to a stored
  match when all of these hold:
  - same player, same result
  - dated 14 days before to 3 days after the match
  - the opponent's name matches
  - the set scores agree when both are present

  Only a single surviving candidate joins.
- **Box-score settlement** in `app/core/prop_settlement.py`: aces, double faults,
  and break points won (`break_points_converted`).
- **A repository loader** for the candidate box scores of given
  (player, match) pairs, with the match opponent's name and score.
- **26b's report** settles box-score lines through the join, and its coverage
  gains a "joined by opponent" line.
- **26f's report** does the same for snapshots.
- **A post-match fetch:** the daily player-stats cron adds `--match-days-back 1`,
  so yesterday's players are refetched after their matches.
- **A one-off backfill run** of the stats ingest, over players with a match since
  props began (2026-03-11), so the history fills the new columns. Run with
  approval: it sends several hundred TennisAbstract requests.

## Out of scope

- 1st-set aces. The box score has no per-set breakdown.
- Fantasy Score. PrizePicks' formula is not documented here.
- Switching the props page's evidence panel (`get_recent_completed_matches`,
  exact-date join) to the new join. It is the same bug in a UI path; note it and
  leave it for a `/fix`.
- Resolving `opponent_name` to a `players.id` at ingest. Names are stored raw and
  matched at read time.
- Any change to projections, tiers or the props page.
- Improving prop-to-match linking (26b's other coverage gap).

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

- [x] **Step 1 - Migration.** Add `0035_player_match_stats_join_key.py`, adding
  nullable `opponent_name`, `round`, `tournament` and `score` (text) to
  `player_match_stats`.

  *Done when:* with the user's go-ahead (the database is the shared Neon one),
  `alembic upgrade head`, `downgrade -1` and `upgrade head` all succeed, and
  `information_schema` shows the four columns.
- [x] **Step 2 - Parser and upsert.** In `app/ingest/player_stats.py`:
  - add `I_TOURNAMENT = 1`, `I_ROUND = 8`, `I_SCORE = 9`, `I_OPPONENT = 11`
  - fill the four new `PlayerMatchStat` fields (blank becomes None)

  In `app/repositories/player_match_stats.py`, insert and update them.

  *Done when:*
  - `tests/test_player_match_stats_parser.py` gains cases for the four fields
    from a Sinner-shaped and a Swiatek-shaped row, plus a row with blanks.
  - A recorded-SQL test shows the four columns in the conflict update.
  - The existing parser tests still pass.
- [x] **Step 3 - Pure join.** Add `app/core/box_score_join.py`:
  - `BoxScoreCandidate`
  - `JoinResult` (the chosen candidate or None, plus a reason: `joined`,
    `no_candidate`, `no_opponent_match`, `score_mismatch` or `ambiguous`)
  - `join_box_score(match_date, result, opponent_name, match_score_winner_first,
    candidates)`

  The opponent test is the whole-token surname rule `app.core.tennis_odds_events`
  uses, exposed there as a public `names_player`. Scores are compared set by set
  winner-first, with tie-break points stripped. The score check applies only
  when both scores exist.

  *Done when:* unit tests cover:
  - two wins in one tournament told apart by opponent
  - a surname-order difference ("Qinwen Zheng" against "Zheng Qinwen")
  - "Li" not matching "Lin"
  - a score mismatch refused
  - a missing score passing on the opponent alone
  - two survivors refused as ambiguous
  - a date outside the window ignored
- [x] **Step 4 - Box-score settlement.** In `app/core/prop_settlement.py`, add:
  - `BOX_SCORE_STATS`: `aces` to `aces`, `double_faults` to `double_faults`,
    `break_points_won` to `break_points_converted`
  - `box_score_value(stat, box) -> int | None`

  *Done when:* unit tests cover each stat, a stat outside the map returning None,
  and a None field returning None.
- [x] **Step 5 - Candidate loader.** Add `get_box_score_candidates(db, pairs)` to
  `app/repositories/player_match_stats.py`. For each (player_id, match_id) pair
  it returns the match's date and winner-first score, the player's result, the
  opponent's `players.name`, and every `player_match_stats` row for that player
  dated 14 days before to 3 days after the match.

  *Done when:*
  - A recorded-SQL test shows the window, the player filter, and the opponent
    taken from the match's other side.
  - An empty input runs no query.
- [x] **Step 6 - Backfill run.** With the user's go-ahead, run:

  ```
  python -m app.ingest.player_stats --today-only --match-days-back 198 --match-days-ahead 0 --sleep 0.5
  ```

  That covers players with a match since 2026-03-11.

  *Done when:*
  - The run's ok, skip and fail counts are recorded.
  - A SQL count shows the share of `player_match_stats` rows with
    `opponent_name` filled.
  - Rows older than TennisAbstract's 52-week window stay NULL, which is
    expected.
- [x] **Step 7 - 26b report settles box-score lines.** In
  `app/backtest/tennis_prizepicks_lines.py`:
  - load candidates for the linked pairs
  - join
  - settle `aces`, `double_faults` and `break_points_won` through
    `box_score_value`
  - move them out of "needs a box score" into the settlement tables
  - count unjoined lines by join reason
  - add a coverage line, "exactly one box score by opponent"

  *Done when:*
  - A report test on synthetic rows checks a joined ace line settles, an
    ambiguous one is counted and not settled, and the join-reason counts.
  - The live report is pasted under Results, beside 26b's 385 (13.5%)
    baseline.
- [x] **Step 8 - 26f report settles box-score snapshots.** Apply the same join
  and settlement in `app/backtest/tennis_prop_snapshots.py`. It needs the
  (player, match) pair, which `GradedPropSnapshot` does not carry, so add
  `player_id` and `match_id` to it and to its loader.

  *Done when:*
  - A report test shows a joined aces snapshot graded by tier, and an unjoined
    one counted by reason.
  - The live report runs.
- [x] **Step 9 - Post-match fetch.** In `.github/workflows/tennis-ingest.yml`,
  change the `player-stats` job's `--match-days-back 0` to `1`.

  *Done when:*
  - The workflow diff is that one argument.
  - The YAML parses.
  - The review packet states the added daily request volume (yesterday's
    players, less those already refreshed today by `--skip-computed-today`).

## Files / areas

- `api/app/db/migrations/versions/0035_player_match_stats_join_key.py` (new).
- `api/app/ingest/player_stats.py` - four indices, parser fields.
- `api/app/repositories/player_match_stats.py` - dataclass fields, upsert,
  candidate loader.
- `api/app/core/tennis_odds_events.py` - a public `names_player` alias.
- `api/app/core/box_score_join.py` (new) - pure join.
- `api/app/core/prop_settlement.py` - box-score settlement.
- `api/app/backtest/tennis_prizepicks_lines.py`,
  `api/app/backtest/tennis_prop_snapshots.py` - settle box-score stats.
- `api/app/repositories/prop_snapshots.py` - `player_id` and `match_id` on
  `GradedPropSnapshot`.
- `.github/workflows/tennis-ingest.yml` - one argument.
- Tests: `test_player_match_stats_parser.py` (extended),
  `test_box_score_join.py` (new), `test_prop_settlement.py`,
  `test_prizepicks_line_report.py`, `test_prop_snapshot_report.py`,
  `test_prop_snapshot_repository.py` (extended), and a new recorded-SQL test for
  the candidate loader.

## Data / contracts

**Migration `0035`**, on `player_match_stats`: `opponent_name`, `round`,
`tournament`, `score`, all nullable Text. NULL means "ingested before 26e", not
"unknown to the source".

**Load-bearing:** the join rule, since any later box-score feature (including the
evidence panel fix) should reuse it:

```python
# app/core/box_score_join.py
JoinReason = Literal["joined", "no_candidate", "no_opponent_match", "score_mismatch", "ambiguous"]

@dataclass(frozen=True)
class BoxScoreCandidate:
    stats_id: int
    match_date: date            # TennisAbstract tournament start
    result: str | None          # W | L
    opponent_name: str | None
    score: str | None           # winner-first, tie-break points included
    aces: int | None
    double_faults: int | None
    break_points_converted: int | None

@dataclass(frozen=True)
class JoinResult:
    candidate: BoxScoreCandidate | None
    reason: JoinReason

def join_box_score(
    match_date: date, result: str, opponent_name: str,
    match_score_winner_first: str | None, candidates: list[BoxScoreCandidate],
) -> JoinResult
```

The window is 14 days before to 3 days after the match date, taken from 26b's
measured offsets.

## Testing

- The test gate is on:
  - Steps 2, 3, 4, 7 and 8 ship unit or report tests.
  - Step 5 ships a recorded-SQL test.
- Step 1 is proven by upgrade, downgrade and upgrade.
- Step 6 is proven by run counts and a fill-rate query.
- Step 9 is proven by the YAML parse and the diff.
- Run with `cd api && .venv\Scripts\python.exe -m pytest`.
- No web change.

## Results

**Backfill (Step 6), run by the user on 2026-09-25, in two halves:**

- ATP: `--tour ATP --today-only --match-days-back 198 --match-days-ahead 0
  --skip-computed-today --sleep 0.5`, with 565 ok, 58 skipped, 0 failed.
- WTA: the same with `--tour WTA`, with 579 ok, 99 skipped, 0 failed.
- Challenger players were left out: TennisAbstract covers few of them.
- Before that, the user's local `ingest_daily` job had already run the Step 2
  parser at 17:41 local time for 124 players (see Notes).

Fill after the backfill:

| Rows | Total | With `opponent_name` | Share |
|---|---|---|---|
| All | 60,854 (from 27,051) | 55,990 | 92.0% |
| Since 2026-03-01 | 38,546 | 35,294 | 91.6% |

**Join rate (Step 7),** over the 2,555 settled player-matches with a closing
PrizePicks line:

| Group | Joined | Share |
|---|---|---|
| All | 2,190 of 2,555 | **85.7%** |
| ATP | 821 of 997 | 82.3% |
| WTA | 1,086 of 1,270 | 85.5% |
| CHALLENGER | 283 of 288 | 98.3% |

- **Baseline:** 26b's 385 (13.5%) unique-in-window candidates, before any join
  key existed.
- **Confirmation:** 2,178 of the 2,190 joins (99.4%) are confirmed by both
  opponent and exact set scores; 12 rest on the opponent alone.
- **Spot check:** nine sampled joins, three per tour, were all correct (for
  example Cilic vs Nakashima, 2-6 6-4 7-6(7)).
- **Challenger's high rate** comes from WTA 125 events filed under
  "CHALLENGER", which TennisAbstract covers.

`python -m app.backtest.tennis_prizepicks_lines`, run 2026-09-25 after the
backfill:

```text
PrizePicks line settlement (score-derived and box-score stats)

Coverage
  PrizePicks snapshots stored:               201972
  linked to a player and a match:            57881 (28.7%)
  distinct linked player-matches:            3113
  settled (completed, with a winner):        2868
  box score on the exact match date:         234 (8.2%)
  exactly one box score in [d-14, d+3]:      841 (29.3%)
  exactly one box score by opponent and score (26e), of player-matches with a closing line:
    all         2190 of  2555 (85.7%)
    ATP          821 of   997 (82.3%)
    WTA         1086 of  1270 (85.5%)
    CHALLENGER   283 of   288 (98.3%)

Closing pre-start lines
  lines in the last snapshot before the start: 36611
  excluded, live or in-game when fetched:      1375
  excluded, promo or flash-sale:               0
  excluded, retirement, walkover or bad score: 1009
  excluded, box-score stat with no join:       230
    no_candidate                               125
    no_opponent_match                           80
    score_mismatch                              14
    missing_count                               11
  excluded, no settlement source:             1603
    fantasy_score                             1570
    1st_set_aces                                33
  settled:                                     32394

Settlement by stat and odds type (over hit excludes pushes; b/even is the app's assumed break-even, not PrizePicks')
  stat                       lines    p-m    over  under   push  act-ln   over hit          b/even
 standard (2807 lines)
  1st_set_total_games           79     79   46.8%  53.2%   0.0%   +0.27    46.8% +/- 5.6%    57.7%
  1st_set_total_games_won      231    231   51.5%  48.1%   0.4%   -0.28    51.7% +/- 3.3%    57.7%
  aces                          98     97   34.7%  64.3%   1.0%   -0.45    35.1% +/- 4.8%    57.7%
  break_points_won             467    466   44.1%  47.3%   8.6%   -0.11    48.2% +/- 2.4%    57.7%
  double_faults                112    112   54.5%  45.5%   0.0%   +0.82    54.5% +/- 4.7%    57.7%
  total_games                 1009    973   48.0%  50.4%   1.6%   +1.09    48.7% +/- 1.6%    57.7%
  total_games_won              779    775   48.4%  50.8%   0.8%   -0.26    48.8% +/- 1.8%    57.7%
  total_sets                     6      6   50.0%  50.0%   0.0%   +0.00    50.0% +/- 20.4%   57.7%
  total_tie_breaks              26     26   19.2%  80.8%   0.0%   -0.31    19.2% +/- 7.7%    57.7%
 goblin (11312 lines)
  1st_set_total_games          425    408   73.9%  26.1%   0.0%   +1.27    73.9%             75.8%
  1st_set_total_games_won      404    403   70.3%  29.7%   0.0%   +0.05    70.3%             75.8%
  aces                        2268   1723   47.6%  52.4%   0.0%   +0.17    47.6%             75.8%
  break_points_won             182    182   56.6%  43.4%   0.0%   +0.39    56.6%             75.8%
  double_faults               2207   1701   55.4%  44.6%   0.0%   +0.56    55.4%             75.8%
  total_games                 2667   1049   67.2%  32.8%   0.0%   +3.73    67.2%             75.8%
  total_games_won             3049   1281   68.9%  31.1%   0.0%   +1.91    68.9%             75.8%
  total_sets                    59     59   61.0%  39.0%   0.0%   +0.33    61.0%             75.8%
  total_tie_breaks              51     51   64.7%  35.3%   0.0%   +0.34    64.7%             75.8%
 demon (18275 lines)
  1st_set_total_games          429    409   25.9%  74.1%   0.0%   -0.86    25.9%             41.3%
  1st_set_total_games_won       90     90   24.4%  75.6%   0.0%   -0.87    24.4%             41.3%
  aces                        3889   1823   16.3%  83.7%   0.0%   -2.51    16.3%             41.3%
  break_points_won             166    166   41.6%  58.4%   0.0%   -0.33    41.6%             41.3%
  double_faults               5046   1794   19.2%  80.8%   0.0%   -2.16    19.2%             41.3%
  total_games                 2923   1046   30.3%  69.7%   0.0%   -3.10    30.3%             41.3%
  total_games_won             3751   1530   25.3%  74.7%   0.0%   -2.65    25.3%             41.3%
  total_sets                   769    767   33.7%  66.3%   0.0%   -0.19    33.7%             41.3%
  total_tie_breaks            1212   1031   22.0%  78.0%   0.0%   -0.43    22.0%             41.3%

Standard lines, ATP
  stat                       lines    p-m    over  under   push  act-ln   over hit          b/even
 standard (1228 lines)
  1st_set_total_games           38     38   44.7%  55.3%   0.0%   +0.37    44.7% +/- 8.1%    57.7%
  1st_set_total_games_won       57     57   40.4%  59.6%   0.0%   -0.66    40.4% +/- 6.5%    57.7%
  aces                          70     69   31.4%  68.6%   0.0%   -0.64    31.4% +/- 5.5%    57.7%
  break_points_won             182    182   48.9%  42.9%   8.2%   +0.13    53.3% +/- 3.9%    57.7%
  double_faults                 56     56   57.1%  42.9%   0.0%   +1.09    57.1% +/- 6.6%    57.7%
  total_games                  386    371   44.8%  53.9%   1.3%   +0.44    45.4% +/- 2.6%    57.7%
  total_games_won              407    406   44.7%  53.8%   1.5%   -0.59    45.4% +/- 2.5%    57.7%
  total_sets                     6      6   50.0%  50.0%   0.0%   +0.00    50.0% +/- 20.4%   57.7%
  total_tie_breaks              26     26   19.2%  80.8%   0.0%   -0.31    19.2% +/- 7.7%    57.7%

Standard lines, WTA
  stat                       lines    p-m    over  under   push  act-ln   over hit          b/even
 standard (1284 lines)
  1st_set_total_games           35     35   45.7%  54.3%   0.0%   +0.04    45.7% +/- 8.4%    57.7%
  1st_set_total_games_won      102    102   54.9%  44.1%   1.0%   -0.14    55.4% +/- 4.9%    57.7%
  aces                          28     28   42.9%  53.6%   3.6%   +0.02    44.4% +/- 9.6%    57.7%
  break_points_won             256    255   40.6%  50.4%   9.0%   -0.26    44.6% +/- 3.3%    57.7%
  double_faults                 56     56   51.8%  48.2%   0.0%   +0.55    51.8% +/- 6.7%    57.7%
  total_games                  505    484   50.5%  47.5%   2.0%   +1.50    51.5% +/- 2.2%    57.7%
  total_games_won              302    299   51.3%  48.7%   0.0%   +0.11    51.3% +/- 2.9%    57.7%

Standard lines, CHALLENGER
  stat                       lines    p-m    over  under   push  act-ln   over hit          b/even
 standard (295 lines)
  1st_set_total_games            6      6   66.7%  33.3%   0.0%   +1.00    66.7% +/- 19.2%   57.7%
  1st_set_total_games_won       72     72   55.6%  44.4%   0.0%   -0.17    55.6% +/- 5.9%    57.7%
  break_points_won              29     29   44.8%  48.3%   6.9%   -0.22    48.1% +/- 9.6%    57.7%
  total_games                  118    118   47.5%  51.7%   0.8%   +1.50    47.9% +/- 4.6%    57.7%
  total_games_won               70     70   57.1%  42.9%   0.0%   +0.06    57.1% +/- 5.9%    57.7%
```

**Reading.** 26b's score-derived rows are unchanged, apart from new lines
fetched since:

- **The box-score stat definitions hold.** On standard lines, mean actual minus
  line is -0.45 aces, +0.82 double faults and -0.11 break points won, all near
  zero.
- **Standard aces lean under.** Overs hit 35.1% +/- 4.8% (97 player-matches),
  so unders hit about 65%, about 1.5 standard errors above the 57.7% assumed
  break-even.
  - ATP alone: overs 31.4% +/- 5.5% (69), unders about 69%, about 2 standard
    errors above break-even.
  - A lean to watch on a small sample, not a settled play.
- **Goblin aces and double-fault overs lose badly** at the assumed payout: aces
  47.6% and double faults 55.4%, against a 75.8% break-even.
- **Demon aces and double-fault overs lose too:** 16.3% and 19.2% against 41.3%.
- **Blind goblin and demon overs remain losers in every stat.**
- **Standard break points won push 8.6% of the time** (whole-number lines). Its
  over hit rate of 48.2% +/- 2.4% shows no lean.
- **The retirement exclusion rose from 547 to 1,009.** That is the reordering
  noted under Notes: box-score and fantasy lines in retired matches now count as
  retirements instead of "needs a box score".

**Follow-ups, not built:**

- The props page's evidence panel (`get_recent_completed_matches`) still joins
  box scores on the exact date and result. It should switch to
  `join_box_score` in a `/fix`.
- If `no_candidate` stays high for recent matches after Step 9's post-match
  fetch, TennisAbstract's lag is over a day; try `--match-days-back 2`.

## Notes for the AI

- **Orient scores before comparing.** `matches.score` is p1-first. Flip it to
  winner-first using `winner_id`, reusing `_flip_score` from
  `app.repositories.matches` or an equivalent pure helper. Strip `(n)` tie-break
  points from the TennisAbstract score. Compare the set list only.
- **Refuse rather than guess.** Two surviving candidates is `ambiguous` and stays
  unsettled. A wrong box score silently corrupts a hit rate, which is worse than
  a smaller sample.
- **The backfill is external load.** Ask before Step 6. Use `--sleep 0.5`, and
  rely on the ingest's existing 429 backoff. If TennisAbstract starts refusing,
  stop and report rather than retrying in a loop.
- **Box scores can lag the match.** TennisAbstract may publish a match's stats a
  day or more after it ends, which is also why Step 9 fetches yesterday's
  players. The reports count an unjoined line by reason; a `no_candidate` share
  that falls over later runs is lag, not a bug.
- **The new columns are raw source text.** Do not normalize names at ingest;
  normalize only inside the pure join.
- **Challenger coverage is thin.** TennisAbstract has fewer Challenger box
  scores, so expect lower join rates there. Report by tour.
- **The evidence-panel join stays as is** (`get_recent_completed_matches`,
  exact date and result). Record it as a follow-up in Results, not a change here.
- **The local `ingest_daily` job runs from this working folder** (found while
  building). It ran the Step 2 parser at 17:41 local time on 2026-09-25, while
  this branch was checked out. Whatever branch is checked out here is what
  runs daily against the shared database. It was harmless here, because Step 1's
  migration had already added the columns. Always migrate before changing an
  ingest writer.
- **Exclusion order changed in both reports** (while building Step 7): the
  retirement check now runs before the stat check, and every stat settles
  through `resolve_actual` in `app/core/prop_settlement.py`. Box-score and
  fantasy lines in retired matches now count as retirements. The totals are
  unchanged; only the buckets move.
- **Reuse, don't copy:**
  - `names_player` (made public) from `app.core.tennis_odds_events`
  - `is_completed_score` from `app.core.tennis_grading`
  - 26b's and 26f's settlement and report code
- Standards: `X | None` in new code, no `Any`, no em dashes, comment only the why.

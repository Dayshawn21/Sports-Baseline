# NFL finished week requires loaded stats

**Type:** Fix
**Fixes:** F-10
**Branch:** `fix/nfl-finished-week-stats`
**Deadline:** before 2026-10-20 13:00 UTC, when `nfl-scores.yml` can mark week 6
complete while only its Thursday game has stats.

## The problem

27j's pre-registered rule says a week counts only when every regular-season
game in it is completed **and its stats are loaded**
(`blueprint/history/features/27j-forward-ranking-check.md:70`). The NFL code
implements only the first half:

- `get_finished_weeks` (`api/app/repositories/nfl.py:2294`) checks
  `bool_and(status = 'completed')` alone, and
  `test_finished_weeks_are_those_with_every_regular_season_game_completed`
  (`api/tests/test_nfl_repository.py`) pins that SQL.
- NBA's `get_finished_weeks` (`api/app/repositories/nba.py:513`) already
  checks both halves.
- Settlement's `week_has_stats` is true once **any** game in the week has a
  stat row. A completed game with no stat rows then settles its lines as
  `void_dnp` (no snaps) or at 0 (snaps, no stats), while the week counts as
  finished.

So `/nfl/model/ranking` (graded live, 15-minute cache) can fix a slice's
verdict sample on a partial week, and the "fixed" sample changes after the
late stats load. Standard under (316 picks) and demon over (213) are past 200
through week 5, so week 6 finishing fixes both samples. No completed 2026 game
lacks stat or snap rows today, so no verdict is contaminated yet.

## The fix

Restore the rule as written. This is not a rule change: no new version, no
forward validation, no holdout read.

1. **Finished week** - every `REG` game in the week is `completed`, and every
   completed game has at least one `nfl_player_weekly_stats` row (NBA's
   shape). NFL games keep the `completed`-only status test; postponement is
   not added here.
2. **Per-game settlement guard** - in `get_gradeable_prop_lines` (27a) and
   `get_frozen_gradeable_lines` (27j), replace the per-week `loaded_weeks` CTE
   with a per-game check (does this line's game have any
   `nfl_player_weekly_stats` row). A line on a completed game without stats
   then reads `week_not_loaded`, never `void_dnp` or 0.

**Must not break:**

- Every query keeps `sport = 'nfl'` on `sport_*` references and
  `MODELLED_MARKET_FILTER` where it already applies.
- The outcome string `week_not_loaded` and the `week_not_loaded` field on the
  27a schema (`app/schemas/nfl.py:572`) keep their names, since the API and
  the stored `nfl_line_grading` snapshot carry them. Only the internal
  `GradeableLine.week_has_stats` field may be renamed (to `game_has_stats`),
  with its docstrings.
- With today's data (every completed game loaded), 27a, 27j, the ranking CLI
  and `/nfl/model/ranking` output are unchanged.
- No change to NBA, the ranking rule, `verdict_sample`, or any frozen row.

## Build steps

- [x] **1. Finished week checks loaded stats** - rewrite `get_finished_weeks`
  in `api/app/repositories/nfl.py` with the second `bool_and` (completed game
  implies an `EXISTS` stat row), docstring matching the 27j wording. Replace
  the pinned-SQL test with one asserting both conditions are in the SQL, and
  add a pure synthetic check through `settle_line`, `to_frozen_call` and
  `slice_results` mirroring F-10's table: weeks 3-5 at 210 picks, week 6
  excluded from the finished set while a completed game lacks stats, so the
  verdict sample stays undecided until it loads.
  **Done when:** the new tests pass, `pytest` is green, and the CLI
  `python -m app.backtest.nfl_ranking_check --season 2026` prints the same
  finished weeks and slice results as before the change (read-only).

- [x] **2. Per-game settlement guard** - swap `loaded_weeks` for a per-game
  `EXISTS` in both NFL gradeable-line loaders; rename the internal field to
  `game_has_stats`; update `settle_line`'s docstring. Add a `settle_line` test
  for a line whose game has no stats but has snaps (`week_not_loaded`, not 0)
  and SQL assertions that both loaders key the guard on `game_id`.
  **Done when:** tests pass, and `python -m app.backtest.nfl_prizepicks_lines
  --season 2026` output matches the pre-change run line for line (read-only).

## Verify

- Full Verify command from the repo root:
  `npm --prefix web run verify && cd api && python -m pytest`.
- Before/after diffs of the two read-only CLIs above, saved to the scratchpad,
  show no difference with today's data.
- `/nfl/model/ranking?season=2026` locally returns the same slices and
  `finishedWeeks` as before.
- Run the `invariants-reviewer` agent on the branch before `/complete`.
- On `/complete`, mark F-10 fixed in `blueprint/context/findings.md` with the
  evidence. The 2026-10-20 Tuesday run is the live check: week 6 must not
  appear in `finishedWeeks` until its stats load.

## Findings

### nfl-finished-week-stats/F-02 [P2] closed - Usage adjustment skews receiving projections downward

**File:** api/app/core/nfl_projection.py:58
**Found:** 2026-09-17 by /audit (scope: current; lens: all) during 19h
**Why it matters:** On the 2026 week 2 slate the median adjustment across 1,830
adjusted receiving props is -1.05%, and 223 still sit at the cap. Players who
get props are mostly starters whose yards and catches per target beat the
position-wide rate, so pulling toward that rate may systematically favor unders
rather than correcting noise. `USAGE_EFFICIENCY_REGRESSION = 0.35` is reasoned,
not fitted.
**Suggested fix:** Validate before trusting usage-adjusted edges: compare
adjusted versus unadjusted projections against settled 2025 results, or compute
the position efficiency baseline from players with a minimum target volume.
Missing validation: a held-out backtest, which 19h scopes out.
**Resolution:** Closed 2026-10-18. Settled by 27b
(`blueprint/history/features/27b-projection-backtest-harness.md`, Results):
on the 2025 holdout, removing the usage adjustment made receiving yards
+0.93% MAE (about 7 SE worse) and receptions +0.70% (about 9 SE worse). The
downward skew is real but moves projections toward results. The adjustment
stays.

### nfl-finished-week-stats/F-03 [P1] accepted - Prop board recreates moneyline recommendations despite the moneyline-off decision

**File:** web/src/utils/tennisPropBoard.ts:158; web/src/pages/TennisPropBoardPage.tsx:32; web/src/utils/tennisPropCards.ts:46
**Found:** 2026-10-18 by /audit (scope: tennis prediction system and consumers; lenses: correctness, data quality, leakage, calibration, tests)
**Why it matters:** `MONEYLINE_PICKS_ENABLED = False` in
`api/app/services/tennis/best_picks.py:34` prevents backend moneyline picks, as
required by `blueprint/history/fixes/26d-follow-ups.md`. The prop board independently
turns `/predictions/today` probabilities and odds into moneyline rows. Positive
EV sets `recommendation = 'BET'`, confidence LEAN, and positive EV styling; rows
with probability >= 50% can enter the actionable list. This bypass is reachable
on the current board, irrespective of the empty backend moneyline picks.
`tennisPropBoard.test.ts:124` explicitly expects this BET behavior, so the tests
currently preserve the contradiction. Confirmed from the page/helper call chain
and existing passing tests; no claim that a positive-EV row was present on today's
hosted slate.
**Suggested fix:** Apply the existing moneyline-off decision to this consumer:
remove its synthetic recommendations or keep strictly neutral reference rows
without BET, actionable ranking or positive signal styling. Add a regression
covering a positive-EV input while moneyline recommendations are disabled.
This is a policy/consumer bug, verified with tests and a UI check; it requires no
new modelling verdict or holdout read. Do not re-enable moneylines.
**Resolution:** Accepted by the owner on 2026-10-18 so F-10 lands before the 2026-10-20 13:00 UTC week-6 stats deadline. These are tennis findings unrelated to F-10, and will be repaired by `/fix F-03` onward right after the merge. Repaired 2026-10-18 by fix `tennis-board-moneyline-reference` and re-reviewed there as `tennis-board-moneyline-reference/F-16`.

### nfl-finished-week-stats/F-04 [P1] accepted - Best-pick props bypass the board's eligibility and data-quality gates

**File:** api/app/services/tennis/best_picks.py:225; api/app/services/tennis/best_picks.py:292; api/app/routers/props.py:397
**Found:** 2026-10-18 by /audit (scope: tennis prediction system and consumers; lenses: correctness, data quality, tests)
**Why it matters:** `generate_prop_picks` checks the match id, line, player,
first-set exclusion and availability of player stats, but does not apply
`_enrich`'s invalid-link block, best-of-five set-stat block, stale-stat cap or
missing-opponent/prediction downgrades. Its only quality flag is a positive
sample count below 10; even that does not cap unpriced confidence.
Synthetic calls with identical inputs reproduced:

| Input | Board `_enrich` | Best-pick card |
|---|---|---|
| Aces 5.5, `match_link_invalid=True` | no recommendation/tier | OVER, LOCK |
| Aces 5.5, stats computed in 2020 | OVER, LEAN, `stale_stats` | OVER, LOCK, no flags |
| BO5 Total Sets 3.5 | blocked, `bo5_unsupported_stat` | UNDER, LOCK, using a 2.5-set projection |

The card path is called by `build_best_picks`, so these are reachable contract
failures, not proposed changes to model thresholds. Existing best-pick tests
cover the first-set exclusion and BO5 games won, but not these cross-consumer
guards.
**Suggested fix:** Reuse the existing prop eligibility/capping assessment for
cards, retaining the first-set exclusion. Add parity regressions for invalid
links, BO5 set counts, stale/zero/small samples and missing inputs. Tests prove
this bug fix; no refit or historical rescore is needed. If shared snapshot
projection/tier behavior changes, use a new projection version rather than
silently changing `props-v2`. Fix together with F-05: both share one root
cause (cards duplicate the board's prop logic instead of calling it), so one
`/fix` routing cards through the canonical assessment closes both.
**Resolution:** Accepted by the owner on 2026-10-18 so F-10 lands before the 2026-10-20 13:00 UTC week-6 stats deadline. These are tennis findings unrelated to F-10, and will be repaired by `/fix F-03` onward right after the merge.

### nfl-finished-week-stats/F-05 [P1] accepted - Best-pick prop probabilities and tiers disagree with props-v2 snapshots

**File:** api/app/services/tennis/best_picks.py:263; api/app/services/tennis/best_picks.py:314; api/app/routers/props.py:323
**Found:** 2026-10-18 by /audit (scope: tennis prediction system and consumers; lenses: correctness, calibration, tests)
**Why it matters:** Cards call `prop_over_under_probs` without match format or
deciding-set probability. For total games this selects the marginal BO3 normal
instead of the board's format-aware mixture. Cards also use unconditional side
probabilities, dropping push conditioning, and tier unpriced PrizePicks lines
with `confidence_tier(prob)` instead of `assess_prop` and the existing payout
table. Sharing `compute_stat_avg` does not make the outputs equivalent.
Synthetic cases using the same mean, stats, opponent, win probability and line:

| Case | Board/snapshot | Best-pick card |
|---|---|---|
| BO3 total games, mean 22.5, line 25.5, win probability .55 | UNDER .626, LEAN | UNDER .6929, STRONG |
| Goblin aces 9.5, mean about 10.85 | OVER .643, PASS | OVER .6429, STRONG |

The goblin example is below the existing assumed 75.76% break-even, yet is
promoted as STRONG. Thus `/tennis/model/prop-tiers` does not validate best-pick
card tiers, even for the same player/stat/line. No calibration change was made.
**Suggested fix:** Make cards consume the canonical probability, push handling,
EV/tier and guards already used by the board and snapshots, while preserving
source-specific pricing and the ungraded first-set exclusion. Test half and
integer lines, BO3/BO5 totals, and standard/goblin/demon payout cases. Consumer
parity is a bug fix needing tests; changing any canonical distribution or payout
assumption is a separate versioned model change requiring forward validation.
Fix together with F-04 (same root cause). Until LOCK/STRONG `props-v2` tiers
reach a verdict, consider showing best-pick prop cards without signal color
rather than only matching the board's unvalidated tiers.
**Resolution:** Accepted by the owner on 2026-10-18 so F-10 lands before the 2026-10-20 13:00 UTC week-6 stats deadline. These are tennis findings unrelated to F-10, and will be repaired by `/fix F-03` onward right after the merge.

### nfl-finished-week-stats/F-06 [P1] accepted - Pre-match prop snapshots can admit a match already marked live

**File:** api/app/services/tennis/prop_snapshots.py:54; api/app/repositories/props.py:90; api/app/repositories/prop_snapshots.py:97
**Found:** 2026-10-18 by /audit (scope: tennis prediction system; lenses: correctness, data quality, future-data leakage, tests)
**Why it matters:** Snapshot eligibility checks the prop's start time and the
stored PrizePicks `is_live`/`in_game` payload, but ignores the linked
`match_status`. `get_today_props` prefers the prop's start time to the match's,
and its payload may have been fetched earlier. `_enrich` blocks completed and
cancelled matches but still recommends on `live`. A synthetic prop with
`match_status='live'`, a future prop start, and an earlier non-live payload
returned a recommendation and `skip_reason(...) is None`. The grading loader
later checks only `snapshot_at < s.start_time`, not the linked match start, so
that snapshot can enter the nominal pre-match evidence after completion.
This confirms the missing guard and acceptance path, not that the current
graded sample actually contains contaminated rows. Its prevalence is unknown.
**Suggested fix:** Reject known-live matches at snapshot time and retain both
source and linked-match timing provenance so pre-start eligibility can be
audited conservatively. First add a deterministic live-status regression and
fixtures for delayed/corrected start times. Do not silently drop historical
rows and reinterpret the fixed tier verdict: quantify affected existing rows
in a separate evidence-integrity review and document any correction explicitly.
The eligibility defect needs tests, not a new model fit; current verdicts stay
as reported pending evidence of contamination.
**Resolution:** Accepted by the owner on 2026-10-18 so F-10 lands before the 2026-10-20 13:00 UTC week-6 stats deadline. These are tennis findings unrelated to F-10, and will be repaired by `/fix F-03` onward right after the merge.

### nfl-finished-week-stats/F-10 [P1] closed - NFL "finished week" ignores whether stats are loaded, so 27j can fix a verdict sample on a partial week

**File:** api/app/repositories/nfl.py:2294; api/app/core/prop_ranking_check.py:62; api/app/core/nfl_line_grading.py:111; api/tests/test_nfl_repository.py:910
**Found:** 2026-10-18 by /audit (scope: NFL prediction system and consumers; lenses: correctness, data quality, leakage, tests)
**Why it matters:** The 27j archive fixed the rule before any week settled:
"A week reaches the rule only when every regular-season game in it is
completed and its stats are loaded"
(`blueprint/history/features/27j-forward-ranking-check.md:70`).
`get_finished_weeks` implements only the first half
(`bool_and(status = 'completed')`), and its test pins that SQL. NBA's
`get_finished_weeks` (`api/app/repositories/nba.py:513`) checks both halves.
Settlement checks stats per *week* (`week_has_stats` is true once any game in
the week has a stat row), not per game. So when a completed game has no stat
row, its lines are voided (no snaps) or settled at 0 (snaps loaded, stats not),
while the week still counts as finished. `verdict_sample` treats every week it
sees as whole, so the "fixed" sample can change after the late stats load.
Synthetic in-memory run through `settle_line`, `to_frozen_call` and
`slice_results` (standard under, weeks 3-5 = 210 picks at 60%, week 6 = 60
lines over three games, two of them completed without stats):

| Week 6 state | Week 6 outcomes | Verdict |
|---|---|---|
| A: one game loaded, no snaps for the others | 20 under, 40 void_dnp | reject, 146/230 |
| A: all three games loaded | 60 under | adopt, 186/270 |
| B: one game loaded, snaps loaded for the others (actual read as 0) | 60 under | adopt, 186/270 |
| B: all three games loaded (true values over the line) | 20 under, 40 over | reject, 146/270 |

**The trigger is close.** Week 6 already holds stats for its Thursday game
(loaded 2026-10-16) while the Sunday games are being played. Standard under
has 316 picks and demon over 213 over weeks 3-5, so week 6 finishing fixes
both slices' samples. `nfl-scores.yml` (13:00 UTC daily) marks the Monday
game completed on Tuesday 2026-10-20; `nfl-ingest.yml` (Tuesday 15:00 UTC,
and recent crons started 2 to 5 hours late) then loads the week's stats.
In between, `/nfl/model/ranking` is graded live (15-minute cache, no
snapshot) and would show a decided verdict built from the Thursday game
alone. The Tuesday CLI runs after the stats step, so it is not affected
unless NFLverse's file omits a game. No completed 2026 game currently lacks
stat or snap rows (read-only count), so no verdict has been contaminated yet.
**Suggested fix:** Bring `get_finished_weeks` in line with the pre-registered
wording, as NBA does: every `REG` game completed, and every completed game
with at least one `nfl_player_weekly_stats` row. Replace the pinned-SQL test
with one asserting both conditions, and add a synthetic check like the table
above. This restores the rule as written before any slice was decided; it is
not a rule change and needs no new version or forward validation. Land it
before 2026-10-20 13:00 UTC, or do not read slice verdicts until Tuesday's
stats load. Separately, `settle_line` reading snaps-without-stats as 0 is
correct only when the stats file is loaded for that game; the per-game guard
covers it for 27j, and 27a should use the same guard.
**Resolution:** Fixed 2026-10-18 on `fix/nfl-finished-week-stats`, pending
`/audit`. `get_finished_weeks` now also requires every completed `REG` game to
have an `nfl_player_weekly_stats` row (NBA's shape), and both NFL gradeable-line
loaders (27a, 27j) check stats per game (`game_has_stats`) instead of per week,
so a completed game without stats reads `week_not_loaded`, never `void_dnp` or 0.
Tests: SQL assertions for both conditions and both loaders, a `settle_line`
case for snaps without loaded stats, and a synthetic held-open week 6. With
today's data `nfl_ranking_check` and `nfl_prizepicks_lines` for 2026 print
output identical to the pre-change runs; Verify passes. Live check: week 6
must stay out of `finishedWeeks` until the 2026-10-20 stats load.
Closed 2026-10-18 by /audit (scope: current; lenses: all). Re-reviewed
`get_finished_weeks` and both loaders: the second `bool_and` makes a completed
game without stat rows hold its week open, and `settle_line` no longer reads
snaps as 0 on an unloaded game. No new defect: `sport = 'nfl'` filters kept,
`week_not_loaded` (API and stored snapshot field) unchanged, the only caller is
`NflPropSource.finished_periods`. `EXPLAIN ANALYZE` on Neon (PostgreSQL 17):
the per-game `EXISTS` is hashed to one sequential scan of
`nfl_player_weekly_stats` (loops=1), both loaders run in about 0.5 s and
`get_finished_weeks` in 0.14 s, so the missing `game_id` index costs nothing
today.

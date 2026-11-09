# Feature: Kicker scoring check

**From build-plan:** feature 27l2 (parent 27l, Kicker fantasy projection)
**Status:** not started
**Branch:** `feature/kicker-scoring-check` (worktree `.claude/worktrees/hopeful-germain-777d2d`)

## Goal

Decide, from data and under a rule fixed before any formula is scored, which
kicker fantasy formula PrizePicks uses, so 27l3 projects and settles kickers
on the right one. Read-only: nothing is stored, fitted or shown.

**What spec research found** (2026-11-08, counts and line averages only, no
formula scored against any outcome):

- **The "6.23 average" was a segment mix, not a formula gap.** The 2026
  standard K `fantasy_points` lines are two segments: full game (187 props,
  average 8.22) and first half (185 props, average 4.19). 27l1's figure
  averaged both. Full-game lines sit near the 8.5 a game kickers average
  under distance scoring, so the "every candidate is too high" puzzle is gone.
  The overview's 27l entry repeats the 6.23 figure and needs correcting.
- **There is no PrizePicks ground truth to match.** Stored snapshots are all
  `status = pre_game` with no result or score field, and the `bets` table has
  9 rows, none a kicker prop. "Match PrizePicks" therefore cannot mean "equal
  PrizePicks' settled score".
- **Over rate near 50% cannot decide it either.** 27a measured standard
  fantasy lines going over 41.7% of the time under the right formula for
  skill players, so PrizePicks' lines are not set at the median.
- **PrizePicks prices its own flat formula beside the fantasy line.** The
  `kicking_points` market (3 per FG, 1 per PAT, `nfl_line_only.py`) has a
  standard full-game line on the same kicker-game for 90 settled kicker-games
  through week 8 (105 through week 9). Both lines come from the same book,
  the same day and the same projection of the kicker, so their difference
  isolates what the fantasy formula adds over flat scoring, with PrizePicks'
  line shading cancelling out.

**The test.** For each kicker-game with both lines, the fantasy line minus
the kicking-points line should equal, on average, what candidate formula F
adds over flat scoring. Realized `F - flat` is an unbiased stand-in for what
PrizePicks expected it to add. So for the true F, the mean paired residual

    z = (fantasy line - kicking points line) - (F(game) - flat(game))

is zero within sampling error, and a wrong F leaves it offset by that
formula's average extra points (for example about 2.5 for "PAT worth 0").

**Assumptions the test rests on** (stated so a surprising verdict can be
traced): `kicking_points` is 3 per FG and 1 per PAT (guarded by the anchor
check below); PrizePicks projects both lines from one view of the kicker, so
any shading cancels in the difference; its projection of long field goals is
not biased on average. Lines move in half points, so rounding adds noise of
up to 0.25 per game but no offset.

## In scope

- **Candidate formulas and kicker scoring**, pure, in `app/core/nfl_kicking.py`.
- **The pre-registered decision rule**, pure, in
  `app/core/nfl_kicker_scoring_check.py`, committed as a checkpoint before any
  candidate is scored on real data. That commit's hash is the
  pre-registration and is cited in Results.
- **A loader** in `app/repositories/nfl.py` for matched kicker-games.
- **A read-only report**, `python -m app.backtest.nfl_kicker_scoring`.
- **One real run** (separate yes in chat), its output under Results, and on a
  `pinned` verdict the pinned formula as a named constant.

## Out of scope

- **Settling K fantasy lines in 27a.** `prizepicks_fantasy_points` stays
  offense-only and kicker fantasy lines still settle at 0. Writing kicking
  points into it needs an ingest change and a 2024-2026 re-backfill (DB
  writes, about 90 minutes), and 27l3 needs those settled actuals for its 2025
  backtest anyway, so 27l3 owns it under its version bump. See Notes for the
  side effect on 27a's over/under table.
- **Any projection, P(over), slate or UI change.** That is 27l3.
- **First-half K fantasy lines** (185 props). There are no per-half kicking
  stats, so they are counted, not used.
- **Goblin and demon lines.** Their lines are set off the standard line, so
  they add no independent evidence; standard only.
- **Formulas outside the registered grid** (yardage-based FG scoring,
  bonuses for game winners, blocked kicks). If no candidate is consistent the
  verdict is `unresolved`; a new grid is a new pre-registration.
- **Seasons before 2026.** PrizePicks K fantasy lines exist only in 2026.
- **A scheduled run.** One registered sample, one run; no weekly workflow step.

## Pre-registered decision rule

Fixed in step 2 and committed before step 5 scores anything. Changing any of
it after a candidate has been scored on real data is a new rule under a new
name, not an edit.

**Sample.** 2026 regular-season games with `status = 'completed'` in weeks 1
through 8 (`DECISION_THROUGH_WEEK = 8`). A **matched kicker-game** is a
player-game of a `K`-position player with:
- a standard full-game `fantasy_points` line and a standard full-game
  `kicking_points` line, each the latest snapshot before kickoff (27a's
  latest-per-prop rule); where a market has two props on one player-game,
  the later `fetched_at` wins (11 kicker-games have two kicking-points props);
- a weekly stat row with `fg_made`, `pat_made` and all 13 27l1 columns
  non-NULL. A kicker-game without one is excluded and counted.

**Candidates** (16, a full grid; stable names in code):

| Term | Values |
|---|---|
| Field goal made | flat 3 at every distance, or distance 3 (0-39 yds) / 4 (40-49) / 5 (50+) |
| PAT made | 1 or 0 |
| FG missed | 0 or -1 |
| PAT missed | 0 or -1 |

NFLverse bands map to the playbook's: `0_19`, `20_29`, `30_39` -> 0-39;
`40_49` -> 40-49; `50_59`, `60_` -> 50+. The anchor `flat` is
flat FG, PAT 1, no penalties, identical to `kicking_points` settlement.

**Statistic.** Per candidate, the mean of `z` over matched kicker-games and
its standard error, sample SD over the square root of n.

**Consistent.** A candidate is consistent when `|mean z| <= 1.96 x SE`.

**Verdict**, checked in this order:
1. `insufficient` when fewer than `MIN_MATCHED = 60` matched kicker-games.
2. `anchor_broken` when the `kicking_points` lines' over rate under `flat`
   on the matched sample, pushes excluded, is outside 35% to 65%. That would
   mean the kicking-points market is not 3-per-FG and 1-per-PAT, so it cannot
   anchor the test.
3. `unresolved` when no candidate is consistent.
4. `pinned` otherwise. Among consistent candidates the pin is the one with
   the fewest non-zero miss penalties, then the smallest `|mean z|`, then
   name order. Every term that differs among the consistent candidates is
   reported as **unresolved by this sample**, with its average effect per
   kicker-game on the matched sample.

**Expected resolution, stated before the run.** With about 90 kicker-games
and a per-game SD near 1.3, SE is about 0.14, so the test separates
candidates whose average extra points differ by roughly 0.4 or more. PAT
value (about 2.5 a game) and FG scoring (about 1.1) should resolve. The FG
miss penalty (about 0.27 a game) may not, and the PAT miss penalty (about
0.07) almost certainly will not; parsimony then pins "no penalty" and the
report says so. These estimates are from 27l1's per-season averages, not
from this sample.

**After the verdict.**
- `pinned`: the formula becomes `PRIZEPICKS_KICKING_FORMULA`, and 27l3 may
  start. Unresolved terms go into 27l3's spec as a known bounded error.
- `unresolved`, `anchor_broken` or `insufficient`: nothing is pinned, K and P
  fantasy lines stay hidden, and 27l3 does not start until a new
  pre-registration (for example a wider grid, or later weeks under a new
  `DECISION_THROUGH_WEEK`) is approved.

**Reported, never deciding:** each candidate's over rate on all settleable
standard full-game K fantasy lines in the sample (with pushes), and on the
matched sample beside the kicking-points over rate under `flat`; the median
gap between the two lines' `fetched_at`.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

**Exception: the step 2 checkpoint is required**, and before step 5's run.

## Build steps

- [x] **Step 1 - Candidate formulas** - in `app/core/nfl_kicking.py`:
  - `KickingFormula` (frozen dataclass): `name`, `fg_by_distance: bool`,
    `pat_points`, `fg_miss_points`, `pat_miss_points`.
  - `kicking_points(formula, row: Mapping[str, int | None]) -> float | None`:
    None when any column the formula reads is NULL, never a partial sum.
  - `FLAT_KICKING` (the anchor) and `CANDIDATE_FORMULAS` (the 16-row grid).
  - **Tests** (`test_nfl_kicking.py`): each distance band's value, including
    `60_` as 5; `flat` equals `line_only_value(KICKING_POINTS, row)` on the
    same rows; each penalty term; a NULL band returning None for a distance
    formula; 16 candidates with unique names.
  - *Done when:* tests pass and `nfl_line_only.py` and every existing reader
    are unchanged (the diff touches only `nfl_kicking.py` and its test).
- [x] **Step 2 - Decision rule (pre-registration)** - new
  `app/core/nfl_kicker_scoring_check.py`:
  - `MatchedKick` (fantasy line, kicking line, stat row), constants
    `DECISION_THROUGH_WEEK = 8`, `MIN_MATCHED = 60`, `CONSISTENT_Z = 1.96`,
    `ANCHOR_OVER_RATE = (0.35, 0.65)`.
  - `candidate_read(formula, matched) -> CandidateRead` (n, mean z, SE,
    consistent).
  - `kicker_scoring_verdict(matched) -> KickerScoringVerdict`: the four
    outcomes, the tiebreak and the unresolved terms with their average effect.
  - **Tests** (`test_nfl_kicker_scoring_check.py`), all on synthetic games:
    games built under the distance formula pin it; a constant offset of 2
    leaves nothing consistent (`unresolved`); 59 games give `insufficient`;
    kicking lines set 3 points below flat give `anchor_broken`; two
    candidates consistent pins the one with fewer penalties and names the
    differing term; an SE of zero (identical residuals) is handled.
  - *Done when:* tests pass; every constant and each of the four verdict
    branches and the tiebreak in "Pre-registered decision rule" has a named
    test; the user commits the checkpoint. **No real candidate is scored
    before this commit exists.** Record its hash under Results.
- [ ] **Step 3 - Matched kicker-game loader** - in `app/repositories/nfl.py`,
  `get_kicker_scoring_rows(db, season, through_week)`: one row per
  `K` player-game with standard full-game `fantasy_points` and
  `kicking_points` lines (latest pre-kickoff snapshot per prop, later prop
  per market when two), and the stat columns, left-joined so missing lines
  and stat rows are counted rather than dropped silently.
  - **Test:** recorded SQL in `test_nfl_repository.py` shows the K filter,
    standard and full-game filters, the pre-kickoff cutoff, completed REG
    games, the week bound and the stat left join.
  - *Done when:* the test passes and a live count prints matched,
    fantasy-only, kicking-only and no-stat-row kicker-games for weeks 1-8.
    Counts only: no formula is evaluated. Expected about 90 matched.
- [ ] **Step 4 - The report** - new `app/backtest/nfl_kicker_scoring.py`
  (read-only, takes `--season`, default 2026; the week bound is the rule's
  constant, not a flag). Prints:
  - **Coverage:** the step 3 counts and the median `fetched_at` gap between
    paired lines. (First-half props are left out of the loader; the spec
    records their count.)
  - **Candidates:** one row per formula, sorted by `|mean z|`: n, mean z,
    SE, consistent, fantasy over rate on all settleable lines and on the
    matched sample, pushes.
  - **Anchor:** kicking-points over rate under `flat`.
  - **Verdict:** the outcome, the pinned name or none, unresolved terms with
    their average effect, and the pre-registration hash (a
    `PREREGISTRATION_COMMIT` constant, set here because step 2's commit now
    exists).
  - **Test** (`test_nfl_kicker_scoring_report.py`): synthetic rows check one
    coverage count, one candidate row and the verdict line.
  - *Done when:* the test passes. No live run in this step.
- [ ] **Step 5 - The run and the pin** - after a separate yes in chat, run
  `python -m app.backtest.nfl_kicker_scoring` once and paste its output under
  Results. Then:
  - on `pinned`: `PRIZEPICKS_KICKING_FORMULA = <pinned candidate>` in
    `nfl_kicking.py`, with a test that it is a member of
    `CANDIDATE_FORMULAS`. Still read by nothing until 27l3.
  - *Done when:* Results holds the output and the verdict; the constant
    exists only on `pinned`; Verify passes. The overview's 27l entry (the
    6.23 segment mix and the verdict) is updated at `/complete`, as 27l1's was.

## Files / areas

- `api/app/core/nfl_kicking.py` - formulas, `kicking_points`, candidates, the pin
- `api/app/core/nfl_kicker_scoring_check.py` (new) - the decision rule
- `api/app/repositories/nfl.py` - `get_kicker_scoring_rows`
- `api/app/backtest/nfl_kicker_scoring.py` (new) - the report
- `api/tests/test_nfl_kicking.py` (new), `test_nfl_kicker_scoring_check.py`
  (new), `test_nfl_kicker_scoring_report.py` (new), `test_nfl_repository.py`
- `blueprint/context/project-overview.md` - the 27l entry (at `/complete`)

## Data / contracts

No schema change, no stored output.

**Load-bearing for 27l3:** `KickingFormula`, `kicking_points` and
`PRIZEPICKS_KICKING_FORMULA`. 27l3 settles and projects kickers through
`kicking_points(PRIZEPICKS_KICKING_FORMULA, row)`; the formula is never
re-derived inline.

```python
# app/core/nfl_kicking.py
@dataclass(frozen=True)
class KickingFormula:
    name: str                 # e.g. "distance_pat1_fgmiss0_patmiss0"
    fg_by_distance: bool      # False: 3 at every distance
    pat_points: int           # 1 or 0
    fg_miss_points: int       # 0 or -1
    pat_miss_points: int      # 0 or -1

def kicking_points(formula: KickingFormula, row: Mapping[str, int | None]) -> float | None: ...
```

## Testing

- Test gate is on (pytest).
- Logic tests: steps 1 and 2 (formula values, verdict paths), step 3's SQL,
  step 4's report on synthetic rows, step 5's membership test.
- Behavior: the step 3 live count and the step 5 run.
- Final gate: `npm --prefix web run verify && cd api && python -m pytest`.

## Results

Pending step 5. Pre-registration commit: pending step 2.

## Notes for the AI

- `core/` stays pure: both core modules take values, never rows from a
  session. The repository returns plain mappings and floats.
- **Order matters for honesty.** Spec research looked only at counts and
  line averages. Do not evaluate any candidate against real outcomes (not
  even in a scratch script) before step 2's checkpoint commit. The step 3
  live run prints counts only.
- **Merge fast-forward.** This feature cites a pre-registration hash, so at
  `/complete` merge with `--ff-only` (or squash plus a pushed tag), never a
  plain squash that orphans the hash.
- **Side effect left for 27l3, flag it to the user:** 27a's "Over/under by
  market and odds type" table still settles kicker fantasy lines at 0, so its
  `fantasy_points / standard` row counts every K line as an under. 27l1
  removed those lines from the model hit rate, not from this table. 27l3
  fixes it when it writes kicking points into settlement; if the user wants
  it sooner, it is a small `/fix` (void K/P fantasy lines as unscored).
- 27l2's build-plan line says "settle ... and pin the one whose results match
  PrizePicks". The rule does settle every line under every candidate, but
  decides on the paired kicking-points comparison because no PrizePicks
  results exist. Offer the user a wording tweak; the plan is theirs to edit.
- Use the API venv at `C:\dev\SportAppV2\api\.venv` and
  `asyncio.WindowsSelectorEventLoopPolicy()` for live reads. The main
  checkout runs another session: never switch, stash or merge there.
- Interview guide: update it (untracked, main checkout) at step 5 only if the
  verdict changes a claim, for example "kicker lines were compared against
  the wrong segment" as a measured lesson.
- PrizePicks playbook source for the distance bands:
  https://www.prizepicks.com/playbook-article/how-to-play-prizepicks-nfl-fantasy-scoring-system

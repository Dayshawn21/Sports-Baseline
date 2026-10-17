# Feature: First-set prop projections

**From build-plan:** feature 16e (Prop stat expansion)
**Status:** complete (first-set lines projected, capped at LEAN until graded)

## Goal

Project the two tennis PrizePicks stat types that arrive every day but show as
`unsupported_stat`: **1st Set Total Games** and **1st Set Total Games Won**.
Together they are about 3,500 lines a month (from 2026-08-28), more than
Break Points Won or Total Tie Breaks. Settlement already handles both
(`app/core/prop_settlement.py`, 26b), so once projected they are graded
forward by 26f's snapshots.

**What arrives today** (props, last 30 days to 2026-09-26):

| Stat type | Lines | Projected today |
|---|---|---|
| 1st Set Total Games | 2,178 | no |
| 1st Set Total Games Won | 1,350 | no |
| 1st Set Aces | 36 | no, and stays so (see Out of scope) |
| every other stat type | | yes |

**The model** (pre-registered here, 2026-09-27): an exact game-by-game Markov
chain over one set.
- Each game is held with the server's hold probability: `h_p` for the
  player, `h_o` for the opponent, alternating serve.
- The first server is unknown before the match, so the two serve orders are
  averaged 50/50.
- At 6-6 one tiebreak game is played, won by the player with
  `p_tb = h_p / (h_p + h_o)`.
- The set ends at 6-0 to 6-4, 7-5, or 7-6.
- The chain gives an exact probability for every final score, so both the
  total-games and the player-games-won distributions (and P(over), P(under),
  P(push) for any line) come straight from it, not from a normal or Poisson
  approximation.
- `h_p = serve_hold(stats)` and `h_o = serve_hold(opponent_stats)`, or
  `_BASELINE_HOLD_PCT` without opponent stats. These are the same hold inputs
  `total_games_won` already uses.

**Pick policy** (decided 2026-09-27): these stats are new and ungraded, so
each line carries an `ungraded_stat` flag and its confidence is capped at
LEAN. The side and hit probability are still computed and stored, so 26f can
grade them.

## In scope

- A pure first-set chain module with tests.
- A read-only level check of the chain against completed matches' first-set
  scores, before anything is shown.
- Projection, probabilities, the `ungraded_stat` flag and LEAN cap on the
  props page and in 26f snapshots, with `PROJECTION_VERSION` bumped to
  `props-v2` in the same step (26f rule).
- A per-stat section in the 26f grader, so first-set picks read separately.
- Web labels and a Review trust state for the flag.

## Out of scope

- **1st Set Aces.** 36 lines a month, and box scores are per match, so there
  is nothing per set to project from or settle against.
- **Using the win probability** in the chain. Holds already carry player
  strength; adding the ensemble would be a second model to validate.
- **Fitting or calibrating** the chain (no fudge factor like
  `_DOWNSTREAM_GAMES_CALIBRATION`). If the level check fails, stop (Step 2).
- **Best picks and the bankroll builder.** First-set stats are skipped there
  until graded.
- **Lifting the LEAN cap.** A later decision, once 26f has a first-set sample.
- Set-handicap lines (16f).

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

- [x] **Step 1 - The first-set chain (pure).** Add `app/core/tennis_first_set.py`:
  - `FIRST_SET_STATS = frozenset({"1st_set_total_games", "1st_set_total_games_won"})`
  - `@dataclass(frozen=True) FirstSetDistribution` holding
    `total_games: dict[int, float]` (6 to 13) and
    `player_games: dict[int, float]` (0 to 7), with a mean for each.
  - `first_set_distribution(player_hold, opponent_hold) -> FirstSetDistribution`,
    holds clamped to [0.01, 0.99].
  - `pmf_probabilities(pmf, line) -> PropProbabilities`, reusing the
    `PropProbabilities` type from `app/core/prop_probs.py`.

  *Done when:* unit tests cover:
  - each distribution sums to 1
  - a player who holds and breaks nearly every game (0.99 against 0.01)
    wins about 6-0, so the total is about 6
  - two near-perfect servers (0.99 each) reach a tiebreak: the total is
    about 13, and player games are 7 or 6 at about 50/50
  - equal holds give a symmetric player-games distribution with a mean equal
    to half the total mean
  - over, under and push for a .5 line and an integer line, summing to 1
- [x] **Step 2 - Level check (read-only).** `python -m app.backtest.tennis_first_set_level`
  reads completed ATP and WTA matches from 2026 whose `score` has a first set.
  A repository function returns each match's first-set games per player, the
  tour, and both players' current all-surface rolling stats (the same
  `stat_period` the props page uses). It prints:
  - observed mean first-set total games, and games won by p1 and p2, by tour
  - the chain's mean over the same matches, and the bias (chain minus actual)
  - n, and matches skipped for missing stats

  *Done when:*
  - The output is recorded under Results.
  - **Pre-registered stop:** if the total-games bias exceeds 0.5 games in
    either tour, stop and report before Step 3. Nothing is fitted.
  - A repository test pins the query's filters; `pytest` passes.
- [x] **Step 3 - Projection, probabilities and version.**
  - `compute_stat_avg` returns the chain's mean for both stats (the player's
    games for `_won`).
  - In `_enrich` (`app/routers/props.py`), first-set stats take P(over),
    P(under) and P(push) from the chain's pmf instead of `prop_probabilities`.
  - Add both stats to `_SUPPORTED_PROJECTION_STATS`, and add `player_hold`
    and `opponent_hold` to `_projection_inputs` for them.
  - Add the `ungraded_stat` flag and cap confidence at LEAN with
    `_cap_confidence`, as `stale_stats` does. It is not a hard block, so the
    side and hit probability still stand.
  - `best_picks.py` skips `FIRST_SET_STATS`.
  - Bump `PROJECTION_VERSION` to `props-v2` in
    `app/services/tennis/prop_snapshots.py`, in this same step (see Notes).

  *Done when:*
  - A router test (in the style of `test_props_router_best_of.py`) shows a
    first-set line with a projection, `projection_status="ok"`, the
    `ungraded_stat` flag, and confidence no higher than LEAN.
  - A best-picks test shows first-set props skipped.
  - `pytest` passes.
- [x] **Step 4 - Grading by stat.** Add a by-stat section to
  `app/backtest/tennis_prop_snapshots.py`: per normalized stat and odds type,
  the pick count, hit rate, and units.

  *Done when:*
  - A grader test shows the by-stat rows.
  - With the user's go-ahead (it writes to the shared database),
    `python -m app.ingest.prop_snapshots` runs once and stores `props-v2`
    rows that include first-set lines with a recommendation.
  - `pytest` passes.

  *Built:* the grader test passes. The one approved snapshot run
  (2026-09-27) wrote nothing: `loaded=210, eligible=0, inserted=0,
  skipped_missing_match=66, skipped_started=144`, since no upcoming PrizePicks
  lines were stored. **Unverified live:** check the first `props-v2` rows the
  daily job stores after merge with `python -m app.backtest.tennis_prop_snapshots`.
- [x] **Step 5 - Web.** In `web/src/utils/tennisPropBoard.ts`:
  - labels `1st_set_total_games` "1st set games" and
    `1st_set_total_games_won` "1st set games won"
  - `ungraded_stat` in `BLOCKING_FLAGS`, so trust reads Review
  - `signalSummary` notes "New stat, not yet graded" ahead of the projection text

  *Done when:*
  - `tennisPropBoard.test.ts` covers the labels, the Review trust, and the
    summary.
  - `npm run build` and `npm run test` pass.
  - A screenshot of `/` shows a first-set line with its projection and
    Review trust.

  *Built:* vitest 185 passed, build passed. The screenshot (2026-09-27, branch
  API on port 8001) shows the "1st set games" category and first-set lines at
  Model 10.3 against 9.5 with Review trust. Every stored line was for a
  finished match, so no side showed and the "not yet graded" summary is
  proven by the unit test only.

## Files / areas

- `api/app/core/tennis_first_set.py` (new) - the chain.
- `api/app/repositories/` - the level-check query (tennis matches repository).
- `api/app/backtest/tennis_first_set_level.py` (new) - the level check.
- `api/app/core/prop_projection.py` - `compute_stat_avg` branch.
- `api/app/routers/props.py` - probabilities, supported stats, inputs, flag.
- `api/app/services/tennis/best_picks.py` - skip first-set stats.
- `api/app/services/tennis/prop_snapshots.py` - version bump.
- `api/app/backtest/tennis_prop_snapshots.py` - by-stat section.
- `web/src/utils/tennisPropBoard.ts` - labels, blocking flag, summary.
- Tests: `test_tennis_first_set.py` (new), a repository test,
  `test_props_router_best_of.py` or a sibling, a best-picks test, the grader's
  test, `tennisPropBoard.test.ts`.

## Data / contracts

No schema change. `props.stat_type` already stores "1st Set Total Games" and
"1st Set Total Games Won"; normalized they are `1st_set_total_games` and
`1st_set_total_games_won`, the keys settlement uses.

**Load-bearing:**
- `ungraded_stat` is a new data-quality flag on `PropLine`: a cap, not a
  hard block. Lifting it later means removing the flag, not changing the
  chain.
- `PROJECTION_VERSION = "props-v2"`: 26f grading never pools v1 and v2.
- `FIRST_SET_STATS` is the one list of first-set keys; router, best picks and
  web normalization agree on the underscore form.

## Testing

- The test gate is on:
  - Step 1 ships unit tests.
  - Step 2 ships a repository test.
  - Step 3 ships router and best-picks tests.
  - Step 4 ships a grader test.
  - Step 5 ships vitest cases, a build, and a screenshot.
- Commands: `cd api && .venv\Scripts\python.exe -m pytest`;
  `cd web && npm run build && npm run test`.

## Results

### Step 2 - the level check

Run 2026-09-27, `python -m app.backtest.tennis_first_set_level` (completed
2026 ATP and WTA matches). **Both tours pass the 0.5-game stop, but the chain
runs high by about a third of a game in each.**

| Tour | n | Actual | Chain | Bias | p1 actual | p1 chain | p1 bias |
|---|---|---|---|---|---|---|---|
| ATP | 3,035 | 9.91 | 10.25 | +0.34 | 5.08 | 5.17 | +0.09 |
| WTA | 3,565 | 9.41 | 9.77 | +0.35 | 4.82 | 4.92 | +0.10 |

337 matches were skipped for missing stats; retirements are left out.

**Reading it:**
- **A consistent OVER lean on total games.** +0.34 games against lines that
  sit at x.5 is enough to tilt close calls to OVER. The likely cause is the
  one the Notes name: `serve_hold` is against an average returner, so two
  average holds overstate how often both servers hold. Per the spec, nothing
  is fitted; the LEAN cap and 26f's forward grading stand guard.
- **Games won is close** (+0.09 to +0.10), because the lean is shared by both
  players.
- The stats include these matches (leak), which should flatter the chain, not
  bias it high.

```
First-set level check: 6600 completed ATP/WTA matches, 337 skipped for missing stats
Stop if the total-games bias exceeds 0.5 games in either tour (pre-registered).
  tour       n   actual    model    bias   p1 act   p1 mod  p1 bias  verdict
  ATP     3035     9.91    10.25   +0.34     5.08     5.17    +0.09  proceed
  WTA     3565     9.41     9.77   +0.35     4.82     4.92    +0.10  proceed
```

## Notes for the AI

- **Pre-registered, 2026-09-27:** the chain, the 50/50 serve order, `p_tb`,
  the hold inputs, the 0.5-game level-check stop, and the LEAN cap. Do not tune
  them after Step 2.
- **Why a chain and not the match-total machinery.** Match totals mix set-count
  uncertainty with games per set (see `total_games_probs`). One set has no set
  count, so an exact chain on holds is simpler and gives a real distribution.
- **The level check leaks, on purpose and only for level.** Rolling stats are
  overwritten in place, so today's holds describe players after those matches.
  That can flatter per-match accuracy, but the check reads only the mean bias.
  Forward grading via 26f is the real test.
- **`serve_hold` is against an average returner.** The chain pairs two such
  holds, as `games_won_share_from_matchup` already does. A strong returner is
  not modelled; if the level check or grading shows a pattern, that is a later
  item.
- **Best-of-5 is fine here:** the first set is played the same way in both
  formats.
- **Why the version bump sits in Step 3.** The local `ingest_daily` task runs
  snapshots from whatever branch is checked out. If first-set projections
  existed on the branch while the version still read `props-v1`, a daily run
  would store v1 rows with new logic. Bumping in the same diff prevents that.
  The bump restarts 26f's sample for every stat, which has only accrued since
  2026-09-25, so it is cheapest now.
- Standards: `X | None` in new code, no `Any`, no em dashes, comment only the
  why, repositories own SQL, `app/core` stays pure, web imports via `~/`.

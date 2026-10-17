# Feature: PrizePicks line grading (NFL)

**From build-plan:** feature 27a
**Status:** complete

## Goal

Measure the NFL prop model against the lines it claims to beat. Settle every
stored pre-kickoff PrizePicks NFL line against the player's actual stats, then
report:

- how often each market and odds type went over, under or pushed
- how often the model's OVER/UNDER call was right, by edge size, against the
  **57.7% per-pick break-even** of a 2-pick Power entry (58.5% for a 3-pick)

This is the week-2 grade from the 2026-09-25 review (681 lines, 49.4%), made into
a repeatable report. It is read-only: nothing is fitted, stored, or fed back into
a projection. Later items judge themselves against it: 27b-27f as context, 27h
as the adoption gate.

## Design reference

None. This is a CLI report, with no UI.

## In scope

- **The slate assembly moves out of the router.** It goes into
  `app/services/nfl/slate.py`, with no behavior change, so the report replays the
  exact projection `/nfl/slate` serves without importing a router.
- **A repository loader for gradeable lines:**
  - the latest pre-kickoff snapshot of each PrizePicks prop
  - on completed regular-season games
  - with the player's stat row and offensive snaps for that game
- **A pure grading module, `app/core/nfl_line_grading.py`:**
  - settles a line from the stat row, falling back to snaps (a player with snaps
    and no stat row recorded zero; neither means did not play, which PrizePicks
    voids)
  - aggregates rates with one standard error
  - buckets model calls by edge size
- **A report, `python -m app.backtest.nfl_prizepicks_lines`,** printing:
  - coverage
  - an over/under/push table by market and odds type
  - the model hit rate on standard full-game lines, overall, by market and by
    edge bucket, against 57.7%

## Out of scope

- Any projection change (27b-27f), P(over) (27g), and adoption (27h).
- Storing frozen NFL projections. The NFL twin of 26f's snapshots is noted for
  27g/27h (see Notes); this report replays today's code.
- Settling first-half, first-quarter and season lines. There are no per-segment
  stats, so they are counted, not settled.
- Fixing the in-game moneyline input (a known follow-up, owned by 27b). The
  report counts how many graded games it touches.
- PrizePicks' own fantasy formula (27f). Fantasy lines settle against the stored
  NFLverse PPR value, with a printed caveat.
- Anytime-TD book prices (item 25).

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

- [x] **Step 1 - Slate assembly into a service (move only).**
  - Move `get_slate`'s body and its helpers (`_slate_line`, `_baseline`,
    `_baseline_label`, `_anytime_td`, `_snap_evidence`, `_history_sample`,
    `_history_value`, `_weather_schema`, `_game_model`, `_team_flags`,
    `_availability`, `_usage_input`, `_td_seasons`, `_snap_seasons`) from
    `app/routers/nfl.py` into `app/services/nfl/slate.py`.
  - Add `build_slate(db, season, week, now) -> NflSlateResponse`.
  - The `/slate` route becomes a one-line call. `/projections` keeps using the
    shared anytime-TD helper, imported from the service.
  - Tests that import helpers from `app.routers.nfl` switch to the service.

  *Done when:*
  - `pytest` passes.
  - `/nfl/slate?season=2026&week=2` and `week=3` return byte-identical JSON
    before and after (SHA-256 of the response body, captured before the move).
- [x] **Step 2 - Gradeable-line loader.** Add
  `get_gradeable_prop_lines(db, season) -> list[GradeableLine]` to
  `app/repositories/nfl.py`:
  - One row per `provider_prop_id`: its latest snapshot with `fetched_at` before
    the game's `start_utc`.
  - Only linked lines (`player_id` and `game_id` set) on REG games with
    `status = 'completed'`.
  - Left-joined to that player-game's `nfl_player_weekly_stats` and
    `nfl_player_snap_counts.offense_snaps`.
  - Also carries a per-week flag: whether the week has any stat rows at all, so
    an unloaded week is never read as every player sitting.

  *Done when:*
  - A recorded-SQL test shows the pre-kickoff cutoff, the completed-game filter,
    the latest-per-prop ordering, and both left joins.
  - A live count for 2026 prints the number of lines per week.
- [x] **Step 3 - Pure settlement and aggregation.** Add
  `app/core/nfl_line_grading.py`:
  - `settle_line(line) -> LineResult`. It takes the market's stat (anytime TD is
    `touchdowns > 0` against 0.5) and falls back to snaps. Other outcomes are
    `void_dnp`, `week_not_loaded` and `unsettleable_segment`.
  - `rate(outcomes) -> RateSummary`: n, over, under and push counts, and rates
    with one standard error over decided lines.
  - `edge_bucket(edge, reference_line) -> "small" | "medium" | "large"`:
    `|edge| / reference` below 5%, 5-15%, or 15% and above. The reference is the
    market's median standard line, as the prop board uses.
  - `model_hits(results, edges) -> dict[bucket, RateSummary]`: a hit is an OVER
    call (edge > 0) that went over, or an UNDER call that went under. Pushes are
    excluded.

  *Done when:* unit tests cover:
  - each market's stat mapping, including anytime TD
  - snaps without a stat row settling as 0
  - no snaps and no row voiding
  - an unloaded week
  - a first-half line counted but unsettled
  - a push excluded from the hit rate
  - bucket edges at exactly 5% and 15%
  - the standard error on a known sample
- [x] **Step 4 - The report.** Add `app/backtest/nfl_prizepicks_lines.py`. It:
  - loads gradeable lines
  - builds each completed week's slate through `build_slate`, using each week's
    last kickoff as `now` so staleness matches game time
  - maps `line_id` to edge and settles

  It prints:
  - **Coverage:** lines loaded, settled, voided (did not play), unsettleable
    segment, week not loaded, and graded games whose latest moneyline was fetched
    after kickoff.
  - **Over/under/push by market and odds type:** all settled lines, with a
    fantasy PPR caveat.
  - **Model hit rate:** standard full-game lines with an edge, overall, by
    market, and by edge bucket, each with ± one standard error, printed beside
    57.7% (2-pick Power) and 58.5% (3-pick).

  *Done when:*
  - A report test on synthetic rows checks the coverage counts, one market row,
    and a bucket hit rate.
  - The live report for 2026 runs.
  - Its output is pasted under Results.
  - The week-2 model hit rate is compared with the review's 49.4% on 681, and
    any gap is explained (the pre-kickoff filter and did-not-play voids are
    expected causes).
- [x] **Step 5 - Run the report weekly in GitHub Actions.** Added 2026-09-26 at
  the user's request. In `.github/workflows/nfl-ingest.yml` (Tuesday), after the
  25b holdout report, add a step that runs
  `python -m app.backtest.nfl_prizepicks_lines`:
  - it prints to the log
  - it writes the same text, in a code block, to `$GITHUB_STEP_SUMMARY`, so the
    run's Summary page shows it
  - it runs after the stats, snaps and relink steps, so the week just finished is
    graded

  *Done when:*
  - The YAML parses.
  - The workflow diff is that one step.
  - The step's shell script, run locally with a temporary summary file, fills
    that file with the report.

## Files / areas

- `api/app/services/nfl/slate.py` (new) - slate assembly moved from the router.
- `api/app/routers/nfl.py` - `/slate` delegates to the service.
- `api/app/repositories/nfl.py` - `get_gradeable_prop_lines`.
- `api/app/core/nfl_line_grading.py` (new) - pure settlement, rates, buckets.
- `api/app/backtest/nfl_prizepicks_lines.py` (new) - the report.
- Tests:
  - `test_nfl_projection.py` (import path only)
  - `test_nfl_repository.py` (the loader)
  - `test_nfl_line_grading.py` (new)
  - `test_nfl_prizepicks_line_report.py` (new)

## Data / contracts

No schema change.

**Load-bearing:** `GradeableLine` and `LineResult`. 27h grades forward on them,
and 27g's P(over) will be scored against the same settled outcomes.

```python
# app/core/nfl_line_grading.py
LineOutcome = Literal["over", "under", "push", "void_dnp", "week_not_loaded", "unsettleable_segment"]
EdgeBucket = Literal["small", "medium", "large"]

@dataclass(frozen=True)
class GradeableLine:
    line_id: int
    season: int
    week: int
    game_id: int
    player_id: int
    market: str                 # NflPropMarket value
    segment: str
    odds_type: str | None
    line: float
    fetched_at: datetime        # latest snapshot before kickoff
    stat_value: float | None    # the market's stat from nfl_player_weekly_stats; None = no row
    offense_snaps: int | None
    week_has_stats: bool

@dataclass(frozen=True)
class LineResult:
    line: GradeableLine
    outcome: LineOutcome
    actual: float | None
```

**Break-evens**, as named constants in the report: 2-pick Power 3x gives
√(1/3) = 57.7%, and 3-pick Power 5x gives (1/5)^(1/3) = 58.5%.

## Testing

- The test gate is on:
  - Steps 3 and 4 ship unit and report tests.
  - Step 2 ships a recorded-SQL test.
  - Step 1 is proven by the existing suite plus byte-identical slate JSON.
- Run with `cd api && .venv\Scripts\python.exe -m pytest`.
- No web change.

## Results

Live run, 2026-09-26, `python -m app.backtest.nfl_prizepicks_lines`:

```
PrizePicks NFL line grading, 2026 (model opponent-dvp-usage-snap-v1)

Coverage
  lines loaded (pre-kickoff)    9486
  settled                       5941
  did not play                    80  (voided by PrizePicks, never a miss)
  half, quarter or season       3465  (no per-segment stats)
  week not loaded                  0  (stats not ingested yet)
  graded games whose latest moneyline was fetched after kickoff: 0 of 18 (an input leak 27b fixes)

Over/under by market and odds type (all settled lines)
  market / odds type                 lines     over           push
  anytime_touchdown / demon            398    11.6% +/- 1.6      0
  anytime_touchdown / goblin            12    50.0% +/-14.4      0
  anytime_touchdown / standard           5    20.0% +/-17.9      0
  fantasy_points / demon               203    23.9% +/- 3.0      2
  fantasy_points / goblin              201    62.6% +/- 3.4      3
  fantasy_points / standard            218    41.7% +/- 3.3      0
  passing_attempts / demon             118    19.5% +/- 3.6      0
  passing_attempts / goblin            100    54.0% +/- 5.0      0
  passing_attempts / standard           39    31.6% +/- 7.5      1
  passing_completions / demon          120    20.8% +/- 3.7      0
  passing_completions / goblin          92    63.0% +/- 5.0      0
  passing_completions / standard        39    56.8% +/- 8.1      2
  passing_yards / demon                128    47.7% +/- 4.4      0
  passing_yards / goblin               129    73.6% +/- 3.9      0
  passing_yards / standard              32    53.1% +/- 8.8      0
  receiving_yards / demon             1035    24.0% +/- 1.3      0
  receiving_yards / goblin             637    66.2% +/- 1.9      0
  receiving_yards / standard           222    46.4% +/- 3.3      0
  receptions / demon                   626    20.3% +/- 1.6      0
  receptions / goblin                  300    67.3% +/- 2.7      0
  receptions / standard                128    42.6% +/- 4.6     13
  rushing_attempts / demon             229    19.2% +/- 2.6      0
  rushing_attempts / goblin            175    63.4% +/- 3.6      0
  rushing_attempts / standard           71    40.6% +/- 5.9      2
  rushing_yards / demon                354    21.8% +/- 2.2      0
  rushing_yards / goblin               238    58.4% +/- 3.2      0
  rushing_yards / standard              92    34.8% +/- 5.0      0
  Fantasy lines settle on NFLverse PPR, not PrizePicks' formula (27f), so treat them as approximate.

Model calls (standard full-game lines, one per player-game and market)
  break-even per pick: 57.7% (2-pick Power), 58.5% (3-pick Power)
                                     calls      hit           push
  all                                  750    48.1% +/- 1.8     18
  edge < 5%                            111    36.9% +/- 4.6      1
  edge 5-15%                           195    51.3% +/- 3.6      8
  edge >= 15%                          444    49.5% +/- 2.4      9
  market anytime_touchdown               0       --
  market fantasy_points                203    50.7% +/- 3.5      0
  market passing_attempts               35    60.0% +/- 8.3      1
  market passing_completions            32    56.2% +/- 8.8      2
  market passing_yards                  32    56.2% +/- 8.8      0
  market receiving_yards               199    40.7% +/- 3.5      0
  market receptions                    104    50.0% +/- 4.9     13
  market rushing_attempts               63    47.6% +/- 6.3      2
  market rushing_yards                  82    46.3% +/- 5.5      0
  week 1                                45    42.2% +/- 7.4      2
  week 2                               665    48.6% +/- 1.9     15
  week 3                                40    47.5% +/- 7.9      1
```

**Reading it:**

- **The model is at a coin flip, and bigger edges do not help.**
  - 48.1% +/- 1.8 on 750 calls, against 57.7% needed.
  - Edges of 15% and up hit 49.5% (444 calls).
  - Edges of 5-15% hit 51.3%; under 5%, 36.9%.
  - No bucket is near break-even.
- **Receiving yards is the worst market,** at 40.7% +/- 3.5 on 199 calls. That
  matches the review's OVER-bias finding: standard receiving-yard lines went over
  only 46.4%, while the model called OVER on most of them.
- **Passing markets read 56-60%, on 32-35 calls each** (+/- about 8.5). That is
  noise at this sample, not a signal.
- **Week 2: 48.6% on 665 calls,** against the review's 49.4% on 681. The gap has
  three causes, all expected:
  - one standard line per player-game and market here, where the review counted
    every standard line
  - players with snaps and no stat row settle as 0 here, where the review dropped
    them
  - the review's projections used kickoff times stored 4 hours early, which this
    run no longer has
- **Standard lines lean under.**
  - Standard lines went over 34.8-56.8% by market, and fantasy 41.7%.
  - Goblins went over 54-74%, and demons 12-48%, as their payout ladders imply.
- **No post-kickoff moneyline among the 18 graded games.** The week-2 "fetched
  1.6 hours after kickoff" noted in the review fix was an artifact of the
  4-hour-early kickoff times, fixed by the 2026-09-26 schedule reload. The
  review fix's follow-up 2 is moot for 2026. 27b still guards the cutoff.
- **PrizePicks' NFL `raw_json` carries no live or in-game marker.** Its keys are
  league, player, team, source and stat type. Kickoff is the only pre-game guard.

## Notes for the AI

- **Replay, not a frozen record.** The report grades today's code on past weeks
  with pre-week inputs (the slate query's `season < S OR (season = S AND week <
  W)` cutoff). That is fine for measuring, but a code change silently re-grades
  history. 27h's forward adoption needs projections frozen before kickoff, the
  NFL twin of 26f's `prop_projection_snapshots`. Raise that when speccing 27g or
  27h; do not build it here.
- **Known input leak:** the slate uses the latest moneyline even if it was
  fetched after kickoff. Count the affected graded games in coverage; do not fix
  it here (27b).
- **PrizePicks may mark a pre-kickoff snapshot as already live.** Check
  `raw_json` for a live or in-game marker on NFL lines, as 26b found for tennis.
  If one exists, exclude those rows and count them. If not, say so in Results.
- **Kickoff times are correct only since the 2026-09-26 schedule reload.** The
  pre-kickoff filter depends on them. If older seasons are ever graded, reload
  their schedules first.
- **Correlated lines.** One player carries a standard line plus goblins and
  demons. The hit rate is reported on standard lines only, one per player-game
  and market.
- **Reuse, don't copy:**
  - `settle` from `app.core.prop_settlement` for over/under/push
  - the snap fallback idea from `app.core.nfl_prop_market.settle`
  - the median reference line from the board
- Standards: `X | None`, no `Any`, no em dashes, comment only the why,
  repositories own SQL, and `app/core` stays pure.

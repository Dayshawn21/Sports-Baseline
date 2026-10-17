# Feature: Prop projection snapshots

**From build-plan:** feature 26f
**Status:** complete

## Goal

Start recording, every day, what the app projected for each upcoming PrizePicks
tennis line:

- the projection
- over, under and push probabilities
- the recommended side and its hit probability
- EV, confidence tier and quality flags

Record it before the match starts. Today all of this is computed on page load
from rolling stats that are overwritten in place, so a past tier can never be
graded without leaking the result (26b's finding). With snapshots, "do LEAN,
STRONG and LOCK picks actually hit?" becomes answerable, forward only, from the
day this ships.

A small grading report ships with it. It will show almost nothing at first. That
is expected: evidence accrues daily.

## Decisions this spec makes

| Question | Decision | Why |
|---|---|---|
| When is a snapshot taken? | **Once a day, by a scheduled job, right after the 13:30 UTC prediction run** in `tennis-ingest.yml` | Props are ingested once a day (13:00) and win probabilities at 13:30. A snapshot then has every input the page uses. A page-load snapshot would depend on when you happen to look. |
| Which props? | PrizePicks only. The line needs a resolved player and match, a start in the future at snapshot time, and no PrizePicks live or in-game flag. | A projection made after the start is not a pre-match prediction. 26b found stored start times can run hours late, so the live flag is checked too. |
| Where does the job get projections? | **It calls the props router's existing `_enrich_props` through a public alias `enrich_props`.** No refactor. | That code is about 350 lines in `app/routers/props.py`. `routers/tennis.py` and four tests already import from it. Moving it into a service is the layering-correct fix, but it is a refactor with no behavior gain here, so it is deferred to item 17. The snapshot then stores exactly what the page computes. |
| What if a snapshot's projection code later changes? | Every row carries `projection_version` (`"props-v1"`). Change the version whenever projection or tier logic changes. | Grading must never pool tiers from different logic, as 26a does with `model_version`. |
| Unsupported stats and PASS picks? | **Stored**, with their `projection_status` and flags. | Grading needs the full denominator. Filtering happens at read time. |

## In scope

- **Migration `0034`:** a new `prop_projection_snapshots` table (below).
- **A pure eligibility and mapping module**, `app/services/tennis/prop_snapshots.py`:
  - decides whether a (`Prop`, `PropLine`) pair may be snapshotted at a given
    time, and why not when it may not
  - maps an eligible pair to a `PropProjectionSnapshot`
- **A repository insert** in a new `app/repositories/prop_snapshots.py`. It is
  idempotent per (prop row, version).
- **A job**, `python -m app.ingest.prop_snapshots`. It loads today's PrizePicks
  props, enriches them exactly as the page does, filters, stores, and logs counts
  by skip reason. Add it to the `predictions` job in `tennis-ingest.yml` and to
  the Ingest commands in `AGENTS.md`.
- **A grading report**, `python -m app.backtest.tennis_prop_snapshots`:
  - settles stored snapshots of score-derivable stats through 26b's
    `app.core.prop_settlement`
  - reports, by confidence tier and odds type: n, the hit rate of the
    recommended side, mean hit probability, calibration bins, and units won at
    the app's assumed payouts
  - counts box-score stats as awaiting 26e

## Out of scope

- Moving the projection code out of the router (item 17, or a separate `/fix`).
- Any change to projections, tiers, EV, the payout table or the props page.
- Snapshotting DraftKings or sportsbook props.
- Snapshotting on page load, or storing what a particular page view showed.
- Settling aces, double faults, break points or Fantasy Score (26e). Their
  snapshots are stored now, so 26e can grade them later without a gap.
- Backfilling past days. It cannot be done without leakage, which is the reason
  this item exists.
- An adoption rule. This item stores evidence and reports it. Deciding on tiers
  comes later, once there is a sample.

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

- [x] **Step 1 - Migration.** Add `0034_prop_projection_snapshots.py`, creating
  the table below with its unique constraint and a `(match_id)` index.

  *Done when:* with the user's go-ahead (the database is the shared Neon one;
  see Notes),
  - `alembic upgrade head` creates the table
  - `alembic downgrade -1` drops it
  - `alembic upgrade head` recreates it

  with the column list confirmed from `information_schema`.
- [x] **Step 2 - Eligibility and mapping.** Add
  `app/services/tennis/prop_snapshots.py`:
  - `PROJECTION_VERSION = "props-v1"`
  - `PropProjectionSnapshot` (below)
  - `skip_reason(prop, line, now) -> SkipReason | None`, which returns one of
    `not_prizepicks`, `missing_player`, `missing_match`, `no_start_time`,
    `no_line`, `started`, `live`, or None when eligible
  - `to_snapshot(line) -> PropProjectionSnapshot`, which raises on an ineligible
    line. It takes only the `PropLine`, because everything stored comes from
    it. `no_line` was added while building: `PropLine.line` is optional in the
    schema.

  *Done when:* unit tests cover:
  - each skip reason, including a start exactly at `now` counting as started
  - a live flag on a row whose start is still in the future
  - a relinked prop, where the snapshot takes the `PropLine`'s effective
    `match_id`
  - a PASS row with no recommendation still mapping
  - `projection_inputs` and flags carried through
- [x] **Step 3 - Repository insert.** Add `app/repositories/prop_snapshots.py`
  with `insert_prop_projection_snapshots(db, snapshots) -> int`:
  - `ON CONFLICT (prop_id, projection_version) DO NOTHING`
  - returns the number of rows actually inserted
  - an empty list makes no query

  *Done when:*
  - A recorded-SQL test shows the conflict clause and the JSONB and array
    parameters.
  - A test checks that an empty input executes nothing.
- [x] **Step 4 - Snapshot job.** Add the public alias `enrich_props` in
  `app/routers/props.py` (a one-line rename, not a move). Then add
  `app/ingest/prop_snapshots.py`, following `app/ingest/predictions.py`. It:
  - loads `get_today_props(db, source="prizepicks")`
  - enriches with `enrich_props`, pairing each `Prop` with its `PropLine` by
    `id` (not by list position)
  - filters with `skip_reason` and inserts
  - commits
  - logs loaded, eligible, inserted, already stored, and skipped by reason

  *Done when:*
  - A live local run stores rows and logs the counts.
  - An immediate rerun inserts 0 and reports them as already stored.
  - A SQL check shows no stored row has `start_time <= snapshot_at`.
  - The existing props router tests still pass.
- [x] **Step 5 - Schedule and docs.**
  - Add a `python -m app.ingest.prop_snapshots` step to the `predictions` job
    in `.github/workflows/tennis-ingest.yml`, after persistence, so it runs on
    the 13:30 schedule and on manual dispatch of `predictions`.
  - Add the command to the Ingest list in `AGENTS.md`.

  *Done when:*
  - The workflow diff shows one new step in the `predictions` job and nothing
    else changed.
  - The YAML parses (`python -c "import yaml; yaml.safe_load(...)"`).
  - It will only run remotely after `master` is pushed.
- [x] **Step 6 - Graded-snapshot loader.** Add
  `get_graded_prop_snapshots(db, version)` to `app/repositories/prop_snapshots.py`,
  returning `GradedPropSnapshot` rows (below):
  - snapshots of that version, for completed matches with a winner
  - per (player, match, stat_type, odds_type, line), the **latest snapshot**
  - the match score, best-of, and which side the player is on

  *Done when:*
  - Recorded-SQL tests show the version filter, the latest-per-line
    selection, and the completed-match join.
  - A live run returns without error; on day one it is expected to return 0
    rows.
- [x] **Step 7 - Grading report.** Add `app/backtest/tennis_prop_snapshots.py`,
  with a pure `report(rows) -> str` and an async CLI, following
  `app/backtest/tennis_prizepicks_lines.py`. It prints:
  - **Totals:**
    - snapshots graded
    - awaiting settlement: stat needs a box score (26e), counted per stat
    - retirement or bad score (`is_completed_score` false)
    - no recommendation
  - **Per confidence tier (LOCK, STRONG, LEAN, PASS) and odds type:**
    - n, pushes
    - the hit rate of the recommended side, pushes excluded, with a binomial
      standard error for standard lines only
    - the mean `hit_probability`
    - the hit rate minus the mean probability
    - units won per line at the app's assumed payout (`leg_decimal_odds`)
  - **Calibration bins** of `hit_probability` against the actual hit rate,
    standard lines only.

  *Done when:*
  - A test on synthetic rows checks: an UNDER recommendation settles as a hit
    when the line goes under; pushes are excluded from the hit rate and score 0
    units; units won on a hit at standard odds is +0.732; box-score stats are
    counted as awaiting 26e; goblin and demon rows have no error bar.
  - A live run prints the report, empty or near-empty on day one, and it is
    pasted under Results.

## Files / areas

- `api/app/db/migrations/versions/0034_prop_projection_snapshots.py` (new).
- `api/app/services/tennis/prop_snapshots.py` (new) - version, dataclass,
  eligibility, mapping. Pure.
- `api/app/repositories/prop_snapshots.py` (new) - insert and graded loader.
- `api/app/ingest/prop_snapshots.py` (new) - the job.
- `api/app/routers/props.py` - one public alias, `enrich_props = _enrich_props`.
- `api/app/backtest/tennis_prop_snapshots.py` (new) - report and CLI.
- `.github/workflows/tennis-ingest.yml` - one step in the `predictions` job.
- `AGENTS.md` - one line in Ingest commands.
- `api/tests/test_prop_snapshots.py`, `api/tests/test_prop_snapshot_repository.py`,
  `api/tests/test_prop_snapshot_report.py` (new).

## Data / contracts

**Schema, migration `0034`. Load-bearing:** 26e grades box-score stats from these
rows, and any later tier change is judged on them.

`prop_projection_snapshots`

| Column | Type | Notes |
|---|---|---|
| `id` | BigInteger PK | |
| `prop_id` | BigInteger, FK `props.id` ON DELETE CASCADE, not null | the snapshotted props row |
| `projection_version` | Text, not null | `props-v1` |
| `snapshot_at` | TIMESTAMPTZ, not null, default `now()` | |
| `player_id` | BigInteger, FK `players.id`, not null | |
| `match_id` | BigInteger, FK `matches.id`, not null | the effective match, after the page's relink |
| `stat_type` | Text, not null | as stored on the prop |
| `odds_type` | Text | standard, goblin or demon |
| `line` | Numeric(6,1), not null | |
| `start_time` | TIMESTAMPTZ, not null | as the page saw it; always after `snapshot_at` |
| `recommendation` | Text | OVER, UNDER or NULL |
| `confidence` | Text | LOCK, STRONG, LEAN, PASS or NULL |
| `hit_probability` | Double | for the recommended side |
| `p_over`, `p_under`, `p_push` | Double | |
| `stat_avg` | Double | the projection |
| `ev_pct` | Double | |
| `break_even_pct` | Double | |
| `matches_count` | Integer | rolling-stats sample |
| `market_total_games` | Double | |
| `projection_status` | Text, not null | |
| `data_quality_flags` | Text[], not null, default `{}` | |
| `projection_inputs` | JSONB, not null, default `{}` | |

- **Unique** on (`prop_id`, `projection_version`).
- **Index** on (`match_id`).

```python
# app/services/tennis/prop_snapshots.py
PROJECTION_VERSION = "props-v1"
SkipReason = Literal["not_prizepicks", "missing_player", "missing_match",
                     "no_start_time", "no_line", "started", "live"]

@dataclass(frozen=True)
class PropProjectionSnapshot:   # one row of the table, minus id and snapshot_at
    prop_id: int
    projection_version: str
    player_id: int
    match_id: int
    stat_type: str
    odds_type: str | None
    line: float
    start_time: datetime
    recommendation: str | None
    confidence: str | None
    hit_probability: float | None
    p_over: float | None
    p_under: float | None
    p_push: float | None
    stat_avg: float | None
    ev_pct: float | None
    break_even_pct: float | None
    matches_count: int | None
    market_total_games: float | None
    projection_status: str
    data_quality_flags: list[str]
    projection_inputs: dict[str, float | str]

# app/repositories/prop_snapshots.py
@dataclass(frozen=True)
class GradedPropSnapshot:
    snapshot_id: int
    tour: str
    stat_type: str
    odds_type: str | None
    line: float
    recommendation: str | None
    confidence: str | None
    hit_probability: float | None
    player_is_p1: bool
    score: str | None
    best_of: int | None
```

## Testing

- The test gate is on:
  - Step 2 ships pure unit tests.
  - Steps 3 and 6 ship recorded-SQL tests.
  - Step 7 ships a report test on synthetic rows.
- Step 1 is proven by upgrade, downgrade and upgrade against the shared
  database, with approval.
- Step 4 is proven by a live run, an idempotent rerun, and the SQL check.
- Step 5 is proven by the YAML parse and the diff.
- Run with `cd api && .venv\Scripts\python.exe -m pytest`.
- No web change.

## Results

**First snapshot run** (`python -m app.ingest.prop_snapshots`, 2026-09-25 about
20:00 UTC, run by hand before the schedule existed):

| Metric | Count |
|---|---|
| loaded | 336 |
| eligible | 204 |
| inserted | 204 |
| skipped, no match | 116 |
| skipped, live | 16 |

An immediate rerun inserted 0 and reported all 204 as already stored. Every
stored row starts 5.9 to 15.5 hours after its snapshot, on a `scheduled` match.

**First grading run** (`python -m app.backtest.tennis_prop_snapshots`, same
evening):

```text
PrizePicks projection grading - props-v1
  (the daily scheduled snapshot, not necessarily what a later page view showed)
  latest pre-start snapshots of finished matches: 0
  no recommendation (blocked by the page):        0
  retirement, walkover or bad score:              0
  awaiting a box score (26e):                     0
  graded:                                         0

By confidence tier and odds type (hit excludes pushes; units per line at the app's assumed payout)
  tier                  n  push      hit            p(hit)    hit-p    units
 standard (0 picks)
 goblin (0 picks)
 demon (0 picks)

Calibration (standard lines): no decided picks yet
```

**Reading:**
- **Empty by construction.** The first snapshots are for matches not yet
  played.
- **Pace.** At about 30 to 40 standard picks a day, of which about 12 carry a
  LEAN or better tier, a per-tier standard-line read with a standard error near
  5 points needs roughly 100 decided picks per tier. Expect several weeks.
- **Goblin and demon picks accrue faster,** but carry no error bar.

## Notes for the AI

- **Pre-match only, enforced twice.** The snapshot is refused when
  `start_time <= now` or PrizePicks marks the row live or in-game. Use the start
  time the page uses: `get_today_props` returns
  `COALESCE(p.start_time, m.start_utc, relinked.start_utc)`.
- **Pair by id, not position.** `_enrich_props` preserves order today, but the
  job must not rely on it. Build a dict of `PropLine` by `id`.
- **The effective match can differ from `props.match_id`.** `get_today_props`
  relinks stale links. Store the `PropLine`'s `match_id`, which is what the page
  projected against.
- **Do not move router code.** Add only the alias. If a step starts pulling
  helpers out of `routers/props.py`, stop: that is the deferred refactor.
- **Bump `PROJECTION_VERSION`** in any later change to projection, probability,
  EV or tier logic. Note that rule in the constant's comment.
- **Reuse, don't copy:**
  - `actual_value`, `parse_sets` and `settle` from `app.core.prop_settlement`
  - `is_completed_score` from `app.core.tennis_grading`
  - `normalize_stat_type` from `app.core.prop_projection`
  - `leg_decimal_odds` from `app.core.prop_ev`
- **The recommended side is what's graded.** An OVER recommendation hits on
  "over", an UNDER on "under". Demon and goblin are OVER-only, as the page
  already sets.
- **There is one database, and it is shared.** `DATABASE_URL` points at a hosted
  Neon database (`neondb`), and the daily cron data lands in it. That makes it
  almost certainly the same database GitHub Actions writes to.
  - Step 1's upgrade, downgrade and upgrade cycle runs against it. It is
    additive and safe while the table is empty, but it is a change to shared
    data, so **ask before running it**.
  - Step 4's live run writes real snapshots there, which is the point.
  - No workflow runs migrations. Once `0034` is applied in Step 1, the
    scheduled job finds its table as soon as `master` is pushed.
- **The snapshot is the scheduled view, not the view you saw.** A page load
  hours later can show different odds-driven projections. State that in the
  report header.
- **26b's lesson on correlated lines applies.** No error bar on goblin or demon
  rates.
- Standards: `X | None` in new code, no `Any`, no em dashes, comment only the why.

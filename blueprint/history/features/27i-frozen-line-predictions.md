# Feature: Frozen line predictions

**From build-plan:** feature 27i
**Status:** complete (week 3 frozen, 9,163 rows; the rule is pre-registered; scheduled after each line snapshot once pushed)

## Goal

Record what the model said about every NFL PrizePicks line before kickoff, and
fix the rule that will decide 27h, before any of that record exists.

**Why now:**
- 27a replays today's code on past weeks, so a model change silently
  re-grades history. A rule graded that way is a moving target.
- Every week that goes unfrozen is evidence lost for good: PrizePicks has no
  history, and the projection inputs move after kickoff.
- A rule written after looking at frozen results is not pre-registered. Fixing
  it as tested constants now, with no frozen week yet, keeps 27j and 27h
  honest.

**What it delivers:**
- Each pre-kickoff line snapshot run also writes the slate's projection, edge,
  P(over), flags and model versions into the existing, unused
  `nfl_prop_predictions` table.
- The ranking rule, as pure constants and a verdict function with tests.

No report and no ranking change. 27j reads the record, and 27h acts on it.

## In scope

- **The rule (pure), first.** `app/core/nfl_ranking_rule.py`:
  - which side of which line counts as a pick
  - one pick per player, game, market, odds type and side
  - the fixed verdict sample
  - the verdict per slice
- **Migration `0037`** on `nfl_prop_predictions`:
  - `projection`, `p_over` and `p_under` become nullable
  - add `over_probability_version`
  - add a unique key on (line, model version, P(over) version)
- **A repository insert** that never overwrites (`ON CONFLICT DO NOTHING`).
- **A pure freeze selector:** which slate lines to freeze at a given moment,
  and the row for each.
- **The job,** `python -m app.ingest.nfl_prop_predictions [--dry-run]`:
  - finds the current week and builds the slate at `now`
  - freezes every slate line whose game has not kicked off
  - logs counts
- **A step in `nfl-prop-lines.yml`** that runs the job straight after each line
  snapshot (Thursday, Saturday, Sunday and Monday, pre-kickoff).
- **One local run** on the remaining 2026 week 3 games, to prove it end to end.

## Out of scope

- **Any report on frozen predictions** (27j), or any hit rate read from them.
- **Any ranking, pick or display change** (27h). The slate reads nothing from
  `nfl_prop_predictions`.
- **`nfl_prop_results`.** It stays unused; 27j settles through 27a's existing
  `settle_line`.
- **Backfilling weeks 1-3** from replay. That would store today's code as if it
  had been served, which is exactly what this feature exists to avoid.
- **Lines that are unlinked at freeze time.** They are in the slate's
  `unmatched` list, not its lines. Tuesday's `--relink` can link them later,
  but they get no frozen row, and 27j counts them as unfrozen.
- **Tennis.** 26f already freezes tennis projections in its own table. Merging
  the two tables is item 17's job.
- **Retuning the payout assumptions** in `app/core/prop_ev.py`. The rule reads
  them as they are.

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

- [x] **Step 1 - The pre-registered rule (pure).** Add
  `app/core/nfl_ranking_rule.py` with the constants and functions under Data /
  contracts:
  - `BREAK_EVEN_BY_ODDS_TYPE`, from the `prop_ev` leg decimals
  - `PLAYABLE_SIDES`
  - `MIN_PICK_MARGIN`, `MIN_PICKS`, `MIN_WEEKS` and `STANDARD_ERRORS_REQUIRED`
  - `FrozenCall` (one frozen, settled line) and `Pick`
  - `pick_side(odds_type, p_over, p_under)`
  - `one_pick_per_bet(picks)`
  - `verdict_sample(picks)`
  - `slice_verdict(picks)`

  *Done when:* unit tests show:
  - A standard line picks the over or the under, whichever clears break-even
    plus the margin; if both clear, the larger one. If neither clears, there is
    no pick. A goblin or demon line never picks the under.
  - A null P(over) never picks.
  - A goblin ladder with three rungs keeps the one rung whose probability
    clears break-even by the most.
  - The verdict sample is the shortest run of whole weeks reaching 200 picks
    and 4 weeks. Picks after it are ignored, so adding a later week never
    changes the verdict.
  - Each verdict branch at exactly the boundaries:
    - `insufficient` with 199 picks, or with 3 weeks
    - `adopt` when the hit rate minus 2 SE clears break-even
    - `reject` otherwise
- [x] **Step 2 - Migration `0037` and the insert.**
  - The migration on `nfl_prop_predictions`:
    - `projection`, `p_over` and `p_under` drop NOT NULL
    - add `over_probability_version text NULL`
    - add a unique index `uq_nfl_prop_predictions_line_version` on
      (`prop_line_id`, `model_version`, `over_probability_version`) `NULLS NOT
      DISTINCT`
  - The downgrade deletes any rows with a null projection, P(over) or P(under)
    before restoring NOT NULL, and says so in a comment. The table is empty
    today.
  - `insert_prop_predictions(db, rows) -> int` in `app/repositories/nfl.py`:
    one multi-row `INSERT ... ON CONFLICT DO NOTHING`, returning the count
    inserted. An empty list writes nothing and returns 0.

  *Done when:*
  - `alembic upgrade head`, `alembic downgrade -1` and `upgrade head` again all
    run clean.
  - A recorded-SQL repository test shows the insert columns and the conflict
    clause, and that an empty list issues no SQL.
  - `pytest` passes.
- [x] **Step 3 - The freeze selector (pure).** Add
  `app/services/nfl/prop_predictions.py` with `NflPropPredictionRow`
  (Data / contracts) and `freeze_rows(slate, now) -> tuple[list[rows],
  Counter]`. It freezes a slate line only when:
  - its game has a `start_utc`
  - that `start_utc` is after `now`

  The Counter reports `frozen`, `kicked_off` and `no_start_time`.

  *Done when:* unit tests on a hand-built `NflSlateResponse` show:
  - a line in a game after `now` is frozen with its projection, edge, P(over),
    P(under), flags, both versions and the `feature_snapshot` keys
  - a line in a game at or before `now` is counted `kicked_off`
  - a game with no `start_utc` is counted `no_start_time`
  - a hidden-market line is frozen with null P(over) and null
    `over_probability_version`
  - a line with no projection is frozen with a null projection
- [x] **Step 4 - The job, and a live run on week 3.** Add
  `app/ingest/nfl_prop_predictions.py`:
  - It gets `now` from the clock and the week from `get_current_week`.
  - It calls `build_slate(db, season, week, now)`, then `freeze_rows`, then
    the insert.
  - It logs the week, frozen and inserted counts, the skip reasons, and
    frozen lines per odds type with a P(over).
  - `--dry-run` computes and logs without writing.
  - It exits 0 when nothing is left to freeze (all games kicked off).

  *Done when:*
  - A `--dry-run` for 2026 week 3 prints counts.
  - A real run inserts rows for the week 3 games still to be played.
  - A second run straight after inserts **0** rows (idempotent).
  - A SQL check records under Results, per odds type:
    - rows written
    - rows with a P(over)
    - that every row's `generated_at` is before its game's `start_utc`
- [x] **Step 5 - Schedule it.** In `.github/workflows/nfl-prop-lines.yml`:
  - Add a step after "Snapshot PrizePicks NFL lines" that runs `python -m
    app.ingest.nfl_prop_predictions`.
  - It runs only when the snapshot step succeeded, so the default `success()`
    condition is enough.
  - Update the header comment to say the run also freezes predictions for 27j.

  *Done when:*
  - The workflow YAML parses (`python -c "import yaml; yaml.safe_load(...)"`).
  - The diff shows the new step in order after the snapshot.
  - Results notes that the schedule only takes effect after this is merged and
    pushed, and names the first scheduled run it will catch.

## Files / areas

- `api/app/core/nfl_ranking_rule.py` (new) - the rule.
- `api/app/db/migrations/versions/0037_nfl_prop_predictions_frozen.py` (new).
- `api/app/repositories/nfl.py` - `insert_prop_predictions`.
- `api/app/services/nfl/prop_predictions.py` (new) - the freeze selector.
- `api/app/ingest/nfl_prop_predictions.py` (new) - the job.
- `.github/workflows/nfl-prop-lines.yml` - the scheduled step.
- Tests:
  - `test_nfl_ranking_rule.py` (new)
  - `test_nfl_prop_predictions.py` (new)
  - `test_nfl_repository.py`

## Data / contracts

**`nfl_prop_predictions` after `0037`. Load-bearing for 27j and 27h.** One row
per line snapshot and version pair, written before kickoff and never updated.

| Column | Type | Meaning |
|---|---|---|
| `prop_line_id` | bigint FK | the `nfl_prop_lines` row, which carries market, segment, odds type, line and `fetched_at` |
| `model_version` | text | `NFL_PROJECTION_MODEL_VERSION` at freeze time |
| `over_probability_version` | text NULL | `nfl-pover-v1`, or null when the slate served no P(over) |
| `projection` | numeric(7,2) NULL | the served projection; null when there is no baseline |
| `p_over`, `p_under` | float NULL | the served P(over) and P(under) |
| `edge` | float NULL | the served edge; null where it is not comparable |
| `confidence` | float NULL | unused, left null |
| `quality_flags` | text[] | the served flags |
| `feature_snapshot` | jsonb | `games_in_sample`, `baseline_season`, `baseline_reason`, `opponent_adjustment_pct`, `usage_adjustment_pct`, `line`, `odds_type`, `market`, `segment`, `line_fetched_at` |
| `generated_at` | timestamptz | freeze time, always before the game's `start_utc` |

**Load-bearing:**
- **Never updated.** A projection change writes a new row under its new
  version, never over the old one.
- **27j grades the row on the line 27a grades,** the last pre-kickoff snapshot
  of each provider prop, joined on `prop_line_id`. Each snapshot run inserts
  fresh line rows, and the job freezes straight after, so the last pre-kickoff
  snapshot normally has a frozen row. When it does not (a failed freeze, or a
  late link), 27j counts the line as unfrozen and never falls back to replay.

**The rule, pre-registered 2026-09-26, before any frozen week exists:**

```python
# app/core/nfl_ranking_rule.py
BREAK_EVEN_BY_ODDS_TYPE = {                   # 1 / per-leg decimal in app/core/prop_ev.py
    "standard": 1 / STANDARD_LEG_DECIMAL,     # 57.7%
    "goblin": 1 / GOBLIN_LEG_DECIMAL,         # 75.8%
    "demon": 1 / DEMON_LEG_DECIMAL,           # 41.3%
}
PLAYABLE_SIDES = {"standard": ("over", "under"), "goblin": ("over",), "demon": ("over",)}
MIN_PICK_MARGIN = 0.03        # a side is picked only when its probability >= break-even + 3 points
MIN_PICKS = 200               # per slice
MIN_WEEKS = 4                 # distinct weeks in the verdict sample
STANDARD_ERRORS_REQUIRED = 2.0

Slice = tuple[str, str]       # (odds type, side): standard/over, standard/under, goblin/over, demon/over
SliceVerdict = Literal["adopt", "reject", "insufficient"]
```

1. **A pick.** A frozen full-game line whose playable side's probability is
   at least break-even plus `MIN_PICK_MARGIN`. On a standard line, if both
   sides clear, the larger one is picked. A null P(over) is never a pick.
2. **One pick per bet.** For each player, game, market, odds type and side,
   keep the single line whose probability clears break-even by the most. A
   ladder is one decision, not several.
3. **The verdict sample is fixed.** Picks are ordered by week. The sample is
   the shortest run of whole weeks from the first frozen week that holds at
   least `MIN_PICKS` settled picks and spans at least `MIN_WEEKS` weeks. Later
   weeks never change a slice's verdict, so reading the report weekly is not
   repeated testing.
4. **Verdict per slice:**
   - `insufficient` until the sample exists
   - `adopt` when the hit rate minus 2 standard errors is above the slice's
     break-even
   - `reject` otherwise
5. **Settlement is 27a's** `settle_line`. Voids and unsettleable lines are not
   picks, and x.5 lines cannot push.

27h may use a slice only after its verdict is `adopt`. A `reject` is final for
that slice under this model and P(over) version. Only a new version starts a
new sample.

## Testing

- The test gate is on:
  - Step 1 ships the rule tests.
  - Step 2 ships the migration round trip and a recorded-SQL insert test.
  - Step 3 ships the selector tests.
  - Step 4 is proven by a live dry run, a real run, and a second run that
    inserts nothing.
  - Step 5 is proven by the YAML parse.
- No web change.
- Run with `cd api && .venv\Scripts\python.exe -m pytest`.

## Notes for the AI

- **Time-sensitive.** Freezing only accrues once this is merged and pushed:
  GitHub Actions runs from `master`. The Sunday 15:00 UTC run is the one that
  catches the main slate. Step 4's local run covers week 3's remaining games
  in the meantime.
- **Multiplicity.** There are four slices, each at 2 SE (about 2.3% one-sided
  each, roughly 9% that at least one passes by chance). This is accepted
  because 27h adopts per slice and can be rolled back. Do not loosen it.
- **Expect rejects.** On week 2, goblin overs went over 64% of the time
  (break-even 75.8%), demon overs 25% (41.3%), and standard model calls hit
  47.9% (57.7%). The rule is built to say no.
- **The payout assumptions are assumptions.** PrizePicks varies its goblin
  and demon payouts per line, and `prop_ev.py` encodes one typical value per
  odds type. The rule imports them rather than copying them, so 27j and 27h
  use the same numbers. Changing them is a new version, not a re-read.
- **Reuse:**
  - `build_slate` exactly as served, with `now` passed in
  - `get_current_week`
  - `NFL_PROJECTION_MODEL_VERSION`
  - `OVER_PROBABILITY_VERSION` from `app/services/nfl/slate.py`
  - the prop_ev decimals
- **Performance.** `build_slate` for one week takes about 8 s. The job builds
  it once per run.
- Standards:
  - `from __future__ import annotations`, `X | None`, no `Any`
  - repositories own SQL
  - `app/core/` stays pure
  - migrations are never edited once applied
  - no em dashes

## Results

### Step 4 - the first frozen week

Run 2026-09-27 02:24 UTC, `python -m app.ingest.nfl_prop_predictions`
(about 14 s), on 2026 week 3:

| Run | Frozen | Inserted | Already stored | Kicked off |
|---|---|---|---|---|
| `--dry-run` | 9,163 | (nothing written) | | 543 |
| real | 9,163 | 9,163 | 0 | 543 |
| again straight after | 9,163 | **0** | 9,163 | 543 |

The 543 kicked-off lines are Thursday's ATL @ GB game, correctly skipped.

SQL check on `nfl_prop_predictions`:

| Odds type | Rows | With P(over) | Generated at or after kickoff |
|---|---|---|---|
| demon | 5,211 | 1,129 | 0 |
| goblin | 2,521 | 685 | 0 |
| standard | 1,431 | 250 | 0 |

- **Timing:** every row was generated at 02:24:38 UTC, and the first remaining
  kickoff is 17:00 UTC.
- **One model version:** all rows are `opponent-dvp-tg-blend-usage-snap-v4`.
- **By segment:** 5,478 full game, 1,847 first half, 1,838 first quarter. The
  rule only reads full-game lines; the others are kept as the served record.

**Gap for 27j to handle.** These rows are frozen on the line snapshot current
at 02:24 UTC. The Sunday 15:00 UTC snapshot will insert newer line rows. If the
freeze job does not run after it (the schedule only exists once this is merged
and pushed), those newest rows have no frozen prediction. 27a grades the
newest pre-kickoff snapshot, so they would count as unfrozen, even though an
earlier snapshot of the same provider prop was frozen. 27j decides whether to
grade the latest frozen pre-kickoff snapshot of each provider prop instead.

### Step 5 - scheduled

`nfl-prop-lines.yml` gains a "Freeze pre-kickoff predictions" step after
"Snapshot PrizePicks NFL lines". It runs `python -m
app.ingest.nfl_prop_predictions` under the default `success()` condition, so a
rate-limited snapshot (exit 75) skips it. The YAML parses, and the step order
is checkout, Python, install, snapshot, freeze.

**Takes effect only after this is merged to `master` and pushed.** The next
scheduled run is Sunday 2026-09-27 15:00 UTC, before the 17:00 UTC kickoffs.
If the push lands after that, the first run it catches is Monday 20:00 UTC
(Monday night), and Sunday's final snapshot needs a manual local run between
15:00 and 17:00 UTC.

**Database.** The job writes wherever the `DATABASE_URL` secret points.
Locally that is the Neon database, where `0037` is already applied and week 3
is already frozen. The overview says the cron and the local task share one
database, but the secret's value cannot be read to confirm it. If the first
scheduled freeze fails on a missing `over_probability_version` column, run
`alembic upgrade head` against that database.

# Props relink to the wrong match, and predictions are never persisted

**Type:** Fix

## The problem

A card on the daily slate showed "Prediction unavailable" for
Juan Manuel Cerundolo vs Dhakshineswar Suresh with 7 Locks, topped by
`Total Games Won OVER 12.5 +80.1% EV`. Neither number is real. Two independent
defects produced it.

### 1. The props relink attaches props to a finished match

PrizePicks posted Cerundolo props for today (start `2026-08-26 20:00Z`), but
`matches` holds no match for him today: livetennis ingest has not picked up his
R16 yet. His only rows are 8/24 (R64) and 8/25 (R32, `completed`). Those props
therefore store `match_id = NULL`.

The relink lateral join at `api/app/repositories/props.py:97-113` then recovers a
match within a **+/- 1 day date window**, ordered by nearest `start_utc`, with no
filter on match status. The nearest candidate is yesterday's **completed** R32
against Suresh, 23.5 hours away, so every prop gets `match_id = 39229`.

Everything downstream then runs on yesterday's match:

| Input | Value used | Where it came from |
|---|---|---|
| Win probability | 0.69 | de-vigged moneyline of the **finished** match (-263) |
| Opponent | Suresh | yesterday's opponent, not today's unknown one |
| Opponent hold | 0.872 | Suresh's rolling stats |
| Model total games | 22.4, x1.09 calibration = 24.4 | two high holds imply a long match |
| Games-won share | 0.594 | |
| **Projected games won** | **14.5** | |

`p(over 12.5) = 0.751` against a demon's 2.42x payout is `+81.8% EV`, which is
what the card showed. Suresh's own props from yesterday's board land on the same
card, which is why the header reads as a two-player matchup.

The guard rails that exist for exactly this case never fire, because the relink
fills `match_id` before they are checked: `missing_match` cannot trigger, and
`match_link_fallback` is only set from `raw_json.match_link_method` at ingest
time, not by the SQL relink. `dataQualityFlags` comes back empty.

Measured over props linked in the last 7 days: 97% sit within 6 hours of their
match's `start_utc`, with a legitimate tail to 11 hours (order-of-play slippage
on late matches), then a gap, then 36 rows at 21.8 to 23.3 hours. That gap is the
signal separating a real late link from a wrong-day one.

### 2. `insert_prediction` has zero call sites

`insert_prediction` (`api/app/repositories/predictions.py:23`) is never called
from anywhere in the repo. `predict_today` computes the ensemble live on every
request and discards it. `select max(generated_at) from predictions` returns
NULL: the table has never held a row.

Consequences:

- `_fetch_win_probs` (`api/app/routers/props.py:571`) queries that table, always
  gets nothing, and every prop silently falls back to market win probability. The
  ensemble never reaches a prop projection, which is the opposite of the intent
  encoded by preferring predictions over market probs.
- `feature_snapshot` is never captured, so build-plan item 15 (calibration
  measured on held-out results) has no data to measure against.

`predict_today` also takes a FastAPI `Request` purely to reach
`request.app.state.registry`, so nothing outside a live HTTP request can call it.
That is what blocks a scheduled job from writing predictions.

## The fix

**Relink:** keep the +/- 1 day date window (a late match's local tournament day
really can differ from the prop's UTC date), and add two guards inside the
lateral join: the candidate match must not be `completed` or `cancelled`, and its
`start_utc` must be within **12 hours** of the prop's `start_time`. 12h is taken
from the distribution above: it keeps every legitimate late link, including the
11h tail, and excludes the 22h+ wrong-day cluster. The existing
`ORDER BY ... ABS(EXTRACT(EPOCH ...))` already prefers the nearest candidate, so
only the filter changes.

**Predictions:** persist them from a new standalone ingest entry point rather
than from a GET route, so read paths stay read-only and rows land on a schedule
instead of on traffic. That requires the predictor to stop depending on
`Request`: pass `ModelRegistry` instead, which is the only thing it ever pulls
off the request.

Must not break:

- props that legitimately link late, when the match is ingested after the props
- props linked at ingest time (`p.match_id` already set); the guards live only in
  the relink lateral, which is gated on `p.match_id IS NULL`
- the four existing `predict_today` / `predict_match` call sites: two in
  `routers/tennis.py`, one in `routers/admin.py`, one in `bankroll_builder.py`
- the shape of `PredictionOutput`, which the API response schemas depend on

Out of scope, deliberately, from the same investigation:

- flagging SQL-relinked props with `match_link_fallback` so the existing
  downgrade path applies to them
- collapsing alt lines per `(player, stat_type)` so 6 lines of one bet stop
  counting as 6 independent Locks
- capturing `feature_snapshot`, which needs `PredictionOutput` to carry its
  features; it belongs with item 15

## Build steps

### Step 1 - stop the relink reaching finished or far-off matches  [x] DONE

In the lateral join in `api/app/repositories/props.py`, add to the `WHERE`:

- `mm.status NOT IN ('completed', 'cancelled')`
- `ABS(EXTRACT(EPOCH FROM (mm.start_utc - p.start_time))) <= 12 * 3600`

Update the comment above the join to say why the window is bounded, citing the
wrong-day failure this fixes.

Repository SQL is not on the unit-test list in `coding-standards.md`, and there
is no test database, so this step's evidence is a query against the real DB plus
the live endpoint, not a unit test.

**Done when:** `GET /tennis/props/prizepicks` returns Cerundolo's Total Games Won
props with `matchId: null`, `projectionStatus: "missing_match"`, and
`confidence: null`, so the fabricated card disappears from the slate; and the
count of props whose linked match sits more than 12 hours from their
`start_time` drops to 0, while props linked within the window are unchanged.

**Evidence recorded 2026-08-26:** all 15 Cerundolo props returned `match_id
None` from the real `get_today_props` (previously `39229`). Across the last 2
days of fetches, relinks went 202 to 115: 87 dropped, of which 77 pointed at a
finished or cancelled match and 37 were more than 12h away. 115 legitimate
relinks preserved. `pytest` 206 passed. The `start_utc IS NULL` escape hatch was
kept deliberately (33 such matches exist, and the `ORDER BY` already ranks them
last).

### Step 2 - pass the model registry into the predictor instead of `Request`  [x] DONE

Change `predict_match`, `_build_prediction`, and `predict_today` in
`api/app/services/tennis/predictor.py` to take `registry: ModelRegistry` in place
of `request: Request`, and drop the `fastapi` import. Update the four call sites
to pass `request.app.state.registry`.

Mechanical, no behavior change. This is what lets a script call the predictor.

**Done when:** `pytest` and `npm run build` pass, `/tennis/predictions/today`
returns the same payload as before the change, and `grep -rn "Request" predictor.py`
returns nothing.

**Evidence recorded 2026-08-26:** `pytest` passed all 206 tests, `npm run build`
completed, and all 31 web tests passed. `predictor.py` contained no `Request`
references. The existing server on port 8000 and a temporary current-code server
on port 8001 each returned 97 predictions with identical JSON and SHA-256. The
temporary server was stopped without touching the existing process.

### Step 3 - persist predictions from a scheduled ingest job  [x] DONE

Add `api/app/ingest/predictions.py`, runnable as
`python -m app.ingest.predictions`, following the existing ingest conventions
(argparse, `WindowsSelectorEventLoopPolicy` guard, tenacity not needed since
there is no network call). It builds a `ModelRegistry`, calls `predict_today` for
today and tomorrow, and writes one row per prediction via `insert_prediction`.

Record a real `model_version`. `ModelRegistry` currently discards which bundle it
loaded, so have `_load_lgbm_bundle` remember the version per tour and expose it,
then write `ensemble-v1+lgbm-<version>` (or `+lgbm-none` when only the XGB
fallback is available). `feature_snapshot` stays NULL for now; see out of scope.

The table is append-only by design (`get_latest_prediction` orders by
`generated_at DESC`), so no upsert. At ~100 matches a day, one run a day is
negligible growth.

Ship a unit test for the pure mapping: `PredictionOutput` plus a registry version
to `insert_prediction` arguments, including the `model_version` string in both
the loaded and fallback cases. Keep that mapping a module-level function so it is
testable without a DB.

Add a job to `.github/workflows/tennis-ingest.yml` scheduled after the existing
`0 13 * * *` odds and props cycle, mirroring the other jobs' setup steps.

**Done when:** `python -m app.ingest.predictions` writes one row per today's
scheduled match, `select count(*) from predictions` is non-zero,
`get_latest_prediction` returns a row for a match on today's slate, and props for
a correctly linked match now report `predictionFound: true` with a win
probability from the ensemble rather than the moneyline.

**Evidence recorded 2026-08-26:** the full API suite passed all 209 tests, the
web build completed, all 31 web tests passed, and the workflow YAML parsed. The
live ingest appended 97 predictions covering today and tomorrow, including all
92 scheduled matches today. Every row recorded
`model_version = ensemble-v1+lgbm-v5` and ensemble weights, while all 97 kept
`feature_snapshot = NULL`. `get_latest_prediction` returned a row for match
39360. The PrizePicks audit reported zero missing predictions; Otto Virtanen's
linked prop on match 39361 reported `predictionFound: true` and used ensemble
win probability 0.697061 instead of market probability 0.646715. The first live
attempt exposed the previously unused repository insert's raw-dict JSONB binding
bug and rolled back with zero rows; the repository now serializes and casts both
JSONB parameters, covered by a regression test.

## Verify

1. `cd api && pytest` and `cd web && npm run build && npm run test`
2. `python -m app.ingest.predictions`, then confirm
   `select count(*), max(generated_at) from predictions` is populated
3. Restart the API, open `http://localhost:3001`, and confirm the
   Cerundolo / Suresh card is gone from the slate
4. Confirm no remaining card shows "Prediction unavailable" alongside Lock
   badges built on a completed match
5. Spot-check one correctly linked prop in `/tennis/props/prizepicks`: `matchId`
   set, `audit.predictionFound` true, EV in a sane range
6. Confirm a first-time-linked prop still links when its match is ingested after
   the props were fetched (re-run `python -m app.ingest.livetennis --days-ahead 1`
   and re-check a prop that was previously `missing_match`)

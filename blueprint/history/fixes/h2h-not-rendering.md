# H2H never reaches the UI

**Type:** Fix

## The problem

The head-to-head strip in the player comparison modal has never rendered, for any
match. Two independent defects stack on top of each other.

### 1. The camelCase alias does not round-trip (why nothing ever shows)

`_CamelModel` in `api/app/schemas/tennis.py` uses Pydantic's `to_camel`, which
capitalizes the letter following a digit. `h2h` is the only field prefix in the
API where a digit sits inside the word, so these four fields are the only ones
that break:

| Python field | API emits | Frontend reads |
|---|---|---|
| `p1_odds_american` | `p1OddsAmerican` | `p1OddsAmerican` (ok) |
| `tour_label` | `tourLabel` | `tourLabel` (ok) |
| `h2h_p1_wins` | `h2HP1Wins` | `h2hP1Wins` (broken) |
| `h2h_p2_wins` | `h2HP2Wins` | `h2hP2Wins` (broken) |

A scan of every `_CamelModel` field found exactly these 4, across
`MatchPrediction` and `MatchBestPicksSchema`. Nothing else is affected.

Downstream, `match.h2hP1Wins` is `undefined`, so
`web/src/components/tennis/PlayerComparisonModal.tsx:259` computes
`undefined + undefined` as `NaN`, and `NaN > 0` is `false`. The strip at line 312
is gated on that, so it never renders.

TypeScript did not catch it because the response is typed at the boundary with no
runtime validation. `web/src/utils/unifiedTennis.test.ts` builds fixtures using
`h2hP1Wins`, so it tests the frontend type against itself and never against the
real API key.

### 2. The batch H2H query only looks in one direction

`get_h2h_batch` in `api/app/repositories/matches.py:377` filters with
`WHERE p1_id = ANY(:p1ids) AND p2_id = ANY(:p2ids)`. A stored row whose
`(p1_id, p2_id)` is reversed relative to the match is never returned. The
orientation handling at lines 385-389 is correct but unreachable, because the SQL
already dropped the row.

The single-match `get_h2h` at line 229 does query both directions, so the two
paths disagree. `/tennis/predictions/today` uses the batch path, so the daily
slate is what suffers.

Measured on the 2026-08-26 slate (44 matches): 3 pairs have an overall H2H row
and the batch query returns 1.

### 3. The `h2h` unique index does not fire for overall records

`idx_h2h_unique ON h2h (p1_id, p2_id, surface)` was created with Postgres's
default `NULLS DISTINCT`. Overall H2H is stored with `surface IS NULL`, and NULL
never equals NULL, so the `ON CONFLICT (p1_id, p2_id, surface)` in `upsert_h2h`
(`api/app/repositories/matches.py:486`) never matches an existing overall row.
Every ingest run inserts another copy.

| Measure | Count |
|---|---|
| Rows in `h2h` | 5,369 |
| Distinct `(p1_id, p2_id, surface)` | 2,705 |
| Distinct canonical pairs, ignoring order | 2,693 |

So there are 2,664 same-orientation duplicates, and 12 pairs stored under both
orientations. One pair is stored 9 times, and duplicates disagree: pair
(126, 201) carries both `0-1` and `2-0`.

This is the defect `player_rolling_stats` fixed with `NULLS NOT DISTINCT` in
migration `0003`. `h2h` never got the same treatment.

It matters for defects 1 and 2 because the batch read returns the first matching
row, so wherever duplicates disagree the H2H shown is arbitrary. Fixing the read
path is not enough while the table can hold contradictory rows for one pair.

## The fix

**Alias:** give the four fields an explicit `alias="h2hP1Wins"` / `"h2hP2Wins"`.
`model_config` already sets `populate_by_name=True`, so constructing the models by
field name keeps working. Do not rename the Python fields, and do not change the
frontend to `h2HP1Wins`; the existing TS name is the correct camelCase.

**Batch query:** make the SQL cover both orientations, so the existing
orientation logic at lines 385-389 receives rows to flip. Keep it one query -
this runs once per slate and must not become a per-pair loop.

**Uniqueness:** canonicalize the stored orientation rather than only fixing the
NULL handling. Storing every pair with the lower player id first collapses the
same-orientation and both-orientation duplicate classes at once, and makes the
unique index mean what it looks like it means: one row per pair per surface.
Half-fixing this with `NULLS NOT DISTINCT` alone would leave the 12
both-orientation pairs contradicting each other.

Both read paths already reorient, so canonical storage needs no read changes.
The step 2 fix stays necessary regardless: lookups arrive in match order, which
is not always canonical.

Must not break:

- the single-match `get_h2h` path, which is already correct
- `p1`/`p2` ordering anywhere else; only the H2H read changes
- any other camelCase alias, all of which round-trip correctly today
- existing H2H values: dedupe keeps the newest row per pair by `updated_at`,
  reoriented rather than discarded

## Build steps

### Step 1 - fix the alias so H2H reaches the frontend  [x] DONE

Add explicit aliases to `h2h_p1_wins` and `h2h_p2_wins` on both `MatchPrediction`
and `MatchBestPicksSchema` in `api/app/schemas/tennis.py`.

Ship a test in `api/tests/` asserting the **serialized JSON key** is literally
`h2hP1Wins` and `h2hP2Wins` for both schemas. This is the check that was missing:
assert the wire format, not the Python field.

**Done when:** dumping either schema with `by_alias=True` produces `h2hP1Wins`,
and the modal shows `2 - 0` for Potapova vs Bartunkova on the 2026-08-26 slate.

### Step 2 - make the batch H2H query bidirectional  [x] DONE

Rewrite the `WHERE` clause in `get_h2h_batch` so rows stored in either
orientation are returned, in a single query.

Ship a test covering a pair whose stored row is reversed relative to the request,
asserting the returned `p1_wins` / `p2_wins` are flipped to match the requested
orientation.

**Done when:** `get_h2h_batch` agrees with `get_h2h` for every pair on the current
slate, with zero disagreements.

### Step 3 - make the h2h uniqueness constraint real  [x] DONE

Alembic migration `0013`, in this order inside one upgrade:

1. Normalize orientation: rewrite every row whose `p1_id > p2_id` to the swapped
   ids with `p1_wins` and `p2_wins` exchanged.
2. Dedupe: keep the newest row per `(p1_id, p2_id, surface)` by `updated_at`,
   with `id` as the tiebreak, and delete the rest.
3. Drop `idx_h2h_unique` and recreate it with `NULLS NOT DISTINCT` so overall
   records (`surface IS NULL`) actually conflict. Requires PostgreSQL 15+, which
   the project already depends on.
4. Add a `CHECK (p1_id < p2_id)` constraint so the canonical form cannot drift.

Give `downgrade()` an honest implementation: it can drop the check constraint and
restore the old index, but it cannot resurrect deleted duplicates. Say so in a
comment rather than pretending the migration is reversible.

Then update `upsert_h2h` (`api/app/repositories/matches.py:482`) to swap ids and
wins before writing when `p1_id > p2_id`, so new writes satisfy the constraint.
It is the only writer, called from `app/ingest/livetennis.py:642` and `:647`.

Ship a test for the canonicalizing behavior of `upsert_h2h`: given a reversed
pair, the values sent to the database are the swapped ids with exchanged wins.

**Done when:** `SELECT count(*) FROM h2h` equals the distinct canonical pair
count (2,693 at time of writing), no row has `p1_id > p2_id`, re-running the
livetennis ingest inserts no duplicate, and `get_h2h` still returns 2-0 for
Potapova vs Bartunkova.

## Verify

1. `cd api && alembic upgrade head` - migration `0013` applies cleanly
2. `cd api && pytest` - all green, including the new alias, batch, and upsert tests
3. `cd web && npm run build` and `npm run test`
4. Start both servers, open `http://localhost:3001`, pick the current slate
5. Open **Potapova vs Bartunkova**. The H2H strip reads `2 - 0`
   (ground truth: they met 2022-04-20 and 2026-05-05)
6. Confirm the other pairs with H2H data now show a strip
7. Confirm a first-time meeting still shows no strip rather than `0 - 0`
8. Re-run `python -m app.ingest.livetennis --days-back 1 --days-ahead 1` and
   confirm `SELECT count(*) FROM h2h` is unchanged, proving the upsert now
   updates instead of inserting

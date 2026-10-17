# Player stats ingest dies on a Postgres deadlock

**Type:** Fix

## The problem

The daily ingest run on 2026-09-14 crashed roughly 30 players into a 346-player
slate, so most of the day's rolling stats were never written:

```
psycopg.errors.DeadlockDetected: deadlock detected
DETAIL:  Process 765 waits for ShareLock on transaction 3654677; blocked by process 925.
CONTEXT:  while locking tuple (41,6) in relation "players"
SQL: SELECT 1 FROM ONLY "public"."players" x WHERE "id" = $1 FOR KEY SHARE
```

That `FOR KEY SHARE` is the foreign-key check from `player_rolling_stats.player_id`
to `players.id`, fired by `upsert_rolling_stats` in
`api/app/repositories/players.py:264`.

Two things are wrong, and the second is what turns a survivable collision into a
lost run:

1. **The lock window is minutes long.** `run()` in
   `api/app/ingest/player_stats.py:655-678` opens one session around the entire
   loop and commits only every 50 players. Each iteration does a blocking HTTP
   fetch plus a `time.sleep`, and TennisAbstract 429s add 10s to 30s of backoff
   on top. So a single transaction holds FK key-share locks on dozens of
   `players` rows for minutes, which is a large window for any concurrent writer
   to collide with.

2. **A deadlock kills the process.** Nothing catches the abort, so the traceback
   escapes `asyncio.run` and every player after the collision is skipped.

The project already solved this exact problem elsewhere. `app/db/retry.py`
exists for it, its docstring names this collision, and `app/ingest/livetennis.py:958`
already routes its writes through `run_in_session_with_retry`. `player_stats.py`
simply never adopted it.

## The fix

Adopt the existing retry helper in `player_stats.run()`, and shrink the
transaction to one player.

The wrinkle: the HTTP fetch currently lives inside `ingest_single_player`
alongside the write. Wrapping that whole call in `run_in_session_with_retry`
would re-fetch from TennisAbstract on every deadlock retry, burning rate limit
on a source that is already returning 429s. So split the fetch from the write and
retry only the write, which is a pure idempotent upsert and safe to replay.

**Must not break:**

- `ingest_single_player`'s signature and behavior. `app/routers/admin.py:159`
  calls it with a request-scoped session and `commit=True`; that path stays
  exactly as it is.
- Per-player skip and failure accounting. A player that 404s on TennisAbstract
  still counts as a skip and the run continues.
- `--skip-computed-today` selection, which is resolved before the loop and is
  untouched.

## Build steps

### [x] Step 1 - separate the write from the fetch

Extract the persistence half of `ingest_single_player` into a
`_persist_player_stats(db, player_id, raw_rows, tour, today)` helper. Have
`ingest_single_player` call it, so its behavior and signature are unchanged.

Pure refactor, no behavior change.

**Done when:** `pytest` passes unchanged, and the admin
`players/{id}/fetch-stats` route still writes stats for one player.

### [x] Step 2 - one transaction per player, retried on deadlock

Rewrite the loop in `run()`:

- Fetch and aggregate one player outside any open transaction.
- Persist that player through `run_in_session_with_retry`, so each player is its
  own short transaction and a 40P01 replays only the write, never the HTTP call.
- Drop the every-50 batch commit and the single loop-wide session. Keep the
  progress log line on the same cadence.

Ship a test at `api/tests/test_player_stats_deadlock.py`, following the fake
session and monkeypatch conventions in `api/tests/test_db_retry.py`:

- A 40P01 on the first write attempt is retried and the player is persisted.
- The retry does **not** trigger a second TennisAbstract fetch.
- A player whose write keeps failing does not abort the remaining players.

**Done when:** `pytest` passes including the new test, and a simulated deadlock
on one player leaves the rest of the slate ingested.

## Verify

1. `cd api && .venv\Scripts\python.exe -m pytest` passes.
2. Run `.venv\Scripts\python -m app.ingest.player_stats --today-only --match-days-back 0 --match-days-ahead 1 --skip-computed-today`
   and confirm it reaches `Done. N ok, N skipped, N failed.` rather than a traceback.
3. Start a second copy of the same command while the first is mid-run. Both
   should finish. Any collision should log a
   `retrying in ...` warning from `app.db.retry` instead of crashing.
4. Confirm in Postgres that `player_rolling_stats.computed_at` is today's date
   for the full selected slate, not just the first 30 players.

## Out of scope

- `time.sleep()` in the loop blocks the event loop. Pre-existing, and unrelated
  to the deadlock.
- The mojibake em dash in the "Rate limited for X" log line.
- TennisAbstract 429 backoff tuning.

## Result

Completed 2026-09-14. `pytest` 580 passed, up from a 573 baseline captured before
any edit, so the 7 new tests in `api/tests/test_player_stats_deadlock.py` are the
entire difference and no existing test moved.

The web build was not run: this change touches no file under `web/`.

### What changed

`run()` no longer holds a session across the slate. Each player is fetched
outside any transaction, then written through `run_in_session_with_retry` with
its own session and its own commit. The every-50 batch commit is gone. The lock
window per player drops from minutes to the duration of one upsert.

`_persist_player_stats` was extracted so the retry replays only the write.
`ingest_single_player` keeps its exact signature and now delegates to it, which
leaves the admin `players/{id}/fetch-stats` route untouched.

### The failing test that changed the design

The first version caught bare `DBAPIError` around the retry call. A test
asserting that a non-conflict error still propagates failed, and it was right to:
that clause swallowed every database error as a deadlock. A schema fault such as
a missing column would have logged `write aborted after deadlock retries` for all
346 players and exited 0, hiding a real bug behind a plausible message.

It now re-raises anything `is_retryable_conflict` rejects, so only genuine 40P01
and 40001 conflicts are absorbed into the per-player failure count. Reusing that
already-tested predicate from `app/db/retry.py` rather than writing a second
classifier keeps one definition of "retryable" in the codebase.

### What this fix does not prove

Verify steps 2 through 4 were **not** run. The tests exercise the retry against
fake sessions; no live Postgres deadlock was observed, no concurrent pair of runs
was executed, and `player_rolling_stats.computed_at` was not inspected. The logic
is proven in isolation, not in the real nightly run. Confirm against the database
before trusting it.

### Still unexplained

The other side of the original deadlock, process 925, was never identified.
`ingest_daily.bat` runs its four steps strictly sequentially, so the collision
came from outside that script: an overlapping scheduled run, a manual run, or the
API server. This fix makes such collisions survivable rather than fatal, but if
an unexpected second job writes `players` nightly, that is worth finding
separately.

### Related non-fatal warnings in the same log

Noted and deliberately left alone: livetennis `/h2h` 429s that retried and
recovered, TennisAbstract 429 backoffs of 10s and 20s, 4 matches skipped for
unresolved initials-only player stubs, 2 players genuinely absent from
TennisAbstract, and the mojibake em dash in the rate-limit log line.

# Prop board caches: one key per board date, and serve stale while rebuilding

**Type:** Fix
**Fixes:** F-43, F-44
**Branch:** `fix/prop-board-cache`

## The problem

The NBA and NHL prop boards (`/nba/props`, `/nhl/props`) are built on request
and cached for 5 minutes in a `SerialBuildCache`. Two problems make loads slow
(production timings, 2026-11-13):

- **F-43, duplicate keys.** `cached_prop_board_json` keys on
  `(requested, today)`, so the default request and the same date asked for
  explicitly are two separate builds. The previous/next links always send a
  date, so stepping back to today rebuilds the board while the default copy
  is still warm: 1.14 s for NBA and 0.52 s for NHL, against 0.18 s warm.
- **F-44, rebuild inside the request.** When an entry expires,
  `SerialBuildCache.get` rebuilds it inside the request that finds it expired.
  The first visitor after each 5-minute TTL waits for a full build (0.99-1.95 s
  for NBA, 1.03 s for NHL), and every other date queues behind the same lock.

## The fix

1. **Stale-while-revalidate in `SerialBuildCache`, opt-in.** A new keyword
   argument, `max_stale_seconds` (default `0`, which keeps today's behavior
   for the four caches that don't opt in). Once an entry is past its TTL but
   still within `max_stale_seconds`, `get` returns the stale value at once and
   starts one background rebuild for that key. The rebuild goes through the
   same build lock, so builds still run one at a time and memory stays bounded
   on the 512 MB plan.
   - Only one background rebuild per key at a time. Keep a strong reference to
     each task so it isn't garbage-collected mid-run.
   - If the background rebuild fails, keep the stale value, log it, and retry
     no sooner than `failure_ttl_seconds` later.
   - Failures are never served stale: a cached `None` behaves as it does now.
   - Past `max_stale_seconds`, or with no entry at all, `get` builds inside the
     request, exactly as now.
2. **Prop board caches key on the resolved date.** The cache key becomes the
   board's resolved date (plus `today`, which still matters for the NBA
   injury/as-of view). A default request resolves its date from the game-date
   list. That resolution is memoized per `today` for the same 5 minutes, so a
   warm hit costs no extra database read. Both caches pass
   `max_stale_seconds=30 * 60`.
3. **Builds open their own session.** A background rebuild outlives the
   request, so the request's `AsyncSession` is closed by then. The board build
   opens a session from `SessionLocal` instead of using the request's `db`.
   The request's `db` is used only for resolving the date.

**Must not break:**

- The response body is byte-for-byte what the response model sends (the
  existing `board_json` tests).
- A burst of requests for one date still runs exactly one build.
- The NFL slate, NBA slate, NBA slate gaps and NHL slate caches keep their
  current behavior: no `max_stale_seconds`, no change.
- A failed build still returns `None` (the router's 503) and is retried after
  10 s.

**Out of scope:** prewarming after a deploy or restart (the first request after
a restart, or after 30 idle minutes, still builds inline), and the F-45 to F-48
client and payload findings.

## Build steps

- [x] **1. Serve stale while one background rebuild runs.** Add
  `max_stale_seconds` to `SerialBuildCache` with tests in a new
  `tests/test_serial_build_cache.py`, using a fake clock.
  **Done when** these tests pass, and the existing cache suites
  (`test_slate_caches.py`, `test_nfl_slate_cache.py`,
  `test_nba_slate_gaps_service.py`, both board-cache tests) pass unchanged:
  - an expired-but-fresh-enough entry returns the old value with no wait, and
    a later call sees the rebuilt value
  - two stale hits start only one rebuild
  - a failed rebuild keeps the stale value and does not retry until the
    failure TTL has passed
  - past `max_stale_seconds`, the request builds inline
  - the default `0` behaves exactly as before
- [x] **2. Key boards on the resolved date and opt in to stale serving.** In
  `nba/prop_board_cache.py` and `nhl/prop_board_cache.py`: resolve the date
  (memoized per `today`), key on it, open a fresh session for builds, and pass
  `max_stale_seconds`. Update both board-cache tests. The current
  `test_explicit_dates_and_the_default_are_separate_keys` becomes "the
  default and its explicit date share one build". Add a stale-serving case.
  **Done when** both test files pass and the full `pytest` suite passes.
- [x] **3. Prove it locally against the shared database.** Run the API
  locally (selector-loop launcher) and time
  `/nba/props` → `/nba/props?date=<that date>` → the same again after the TTL
  is shortened (for example via a temporary local override, not a committed
  change). **Done when** the explicit-date request after a default request is
  a warm hit, and a request after expiry returns at warm speed while the log
  shows a background rebuild.

## Verify

- The Verify command from the repo root passes:
  `npm --prefix web run verify && cd api && python -m pytest`.
- Local timings from step 3, before and after.
- After deploy (separate approval), repeat the 2026-11-13 production curls
  from F-43 and F-44: an explicit-today request right after a default one
  should be warm (~0.2 s), and no request should wait the 1-2 s build once
  the process has built a date.

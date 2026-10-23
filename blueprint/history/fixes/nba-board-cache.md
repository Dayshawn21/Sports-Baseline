# NBA board server cache

**Type:** Fix

**Completed:** 2026-10-23. Approved by the user's `/complete` request.

## The problem

`GET /nba/props` (`api/app/routers/nba.py:38`, `build_prop_board` in
`api/app/services/nba/prop_board.py`) has no server cache. Every request
rebuilds the whole Eastern date: game dates, games, date-wide modelled and
line-only lines, prior games and recent box scores for every player, injuries
and team stats, then validates and serializes a response of about 4.9 MB
(8,097 raw lines on 2026-10-21).

Measured in the earlier client investigation: about 1.5 s warm server time
(2.2 s end to end), 5-14 s when the API or database is cold. The client is
not the bottleneck; the main thread never blocks.

Constraint: the hosted API (`sportapp-api`) has 512 MB. A cache must hold a
small, fixed number of dates and must not keep large Pydantic object graphs
alive when bytes would do.

## The fix

Cache the **serialized JSON bytes** of the board per request, with the
existing `SerialBuildCache` that already serves `/nfl/slate`
(`api/app/services/nfl/slate_cache.py`). It builds **one key at a time**,
which matters because Step 1 measured each build peaking about 90 MB above
the idle process, and it drops the least recently built key past a limit.

*Amended at Step 2 (was `TimedSingleFlight` with a date window):* the serial
lock bounds concurrent build memory, and the entry limit bounds stored bytes
without a date window or pruning code.

- **Move `SerialBuildCache`** unchanged to `api/app/services/serial_build_cache.py`
  so NBA code never imports an NFL module; `nfl/slate_cache.py` and its test
  import it from there. No NFL behavior change.
- **New module** `api/app/services/nba/prop_board_cache.py`:
  - `CACHE_TTL_SECONDS = 5 * 60` (the web's 5-minute `staleTime` in
    `web/src/hooks/useNba.ts`), `FAILURE_TTL_SECONDS = 10`,
    `MAX_ENTRIES = 5` (about 32 MB at Step 1's 6.5 MB body).
  - Key `(requested, today)`: the default date depends on Eastern today.
  - `cached_prop_board_json(db, requested, today) -> bytes | None` builds
    with `build_prop_board` and stores `model_dump_json(by_alias=True)`.
- **Router:** `get_prop_board` returns `Response(content=..., media_type="application/json")`,
  keeping `response_model=NbaPropBoardResponse` for the OpenAPI schema, and
  a 503 ("try again shortly") when the build failed, as `/nfl/slate` does.
  The body must be byte-for-byte what FastAPI serializes today.

**Must not break:**

- Board/game parity (42a): the cached body is the same response the game
  endpoints agree with; only its age changes, by at most 5 minutes.
- Injury freshness (42c) is computed at build time with `as_of`; a 5-minute
  cache cannot cross the six-hour freshness boundary meaningfully, but the
  spec accepts that a cached body's `as_of` is up to 5 minutes old.
- No projection, gap, sort, ordering, probability, version or color change.
- Rate limits and headers unchanged; `/nba/props` is not a heavy path.
- `app/core/` stays pure; SQL stays in repositories.

**Out of scope:** response compression (the API has no GZip middleware, so
the 6.5 MB travels uncompressed), shrinking the payload, and caching other
NBA endpoints. Each is its own `/fix` if wanted.

## Build steps

- [x] **Step 1 - Measure the baseline.** With the local API (see memory
  `local-api-selector-loop`), time five cold and five warm `/nba/props`
  requests for a populated date (2026-10-21) and record the process RSS
  before and after. Save the body for parity. Record numbers in
  `blueprint/reference/fix-nba-board-cache/measure.md`.
  **Done when:** the baseline timings, body size and RSS are recorded.
- [x] **Step 2 - Cache module and router.** Add `prop_board_cache.py` and
  switch the router to return cached bytes. `SerialBuildCache` keeps its
  existing tests. New tests in `api/tests/test_nba_prop_board_cache.py`
  cover a burst for one date building once, the key separating explicit
  dates and the default date per `today`, TTL expiry, a failure returning
  None (router 503), and a parity test
  that the cached bytes equal FastAPI's own serialization of the same
  response.
  **Done when:** the tests pass and the local endpoint body for 2026-10-21
  is byte-identical to Step 1's saved body.
- [x] **Step 3 - Measure the result.** Repeat Step 1's timings and RSS with
  the cache, including the second request within 5 minutes and Step 1's
  other dates (six distinct keys, so one eviction).
  **Done when:** a cached hit returns in well under 1.5 s, the RSS growth
  with all five keys filled is recorded and fits comfortably inside 512 MB,
  and the numbers are added to `measure.md`.

## Verify

- Verify command: `npm --prefix web run verify && cd api && python -m pytest`.
- Open `/nba/board` locally, load it, reload within 5 minutes: the second
  load is fast and shows the same rows; change market and date, then return.
- Compare one game's board rows against `/nba/games/{id}/props` (parity).

## Outcome

- `SerialBuildCache` moved unchanged to `api/app/services/serial_build_cache.py`;
  `/nfl/slate` behaviour is unchanged.
- `/nba/props` serves cached bytes from `api/app/services/nba/prop_board_cache.py`
  (5-minute TTL, 10-second failure TTL, at most 5 entries, one build at a
  time); a failed build returns 503.
- Measured locally (`blueprint/reference/fix-nba-board-cache/measure.md`):
  a cached repeat takes about 0.01 s against about 1.7 s; the 6,455,505-byte
  body for 2026-10-21 kept the baseline sha256 in every run; peak working set
  287-288 MB against 305-307 MB. Hosted Render latency and memory, and a burst
  across different dates, are not measured.
- Verify passed: web typecheck and build, 815 web tests, 3,764 API tests.
- No projection, gap, ordering, probability, version or color change. Existing
  F-09 (P3) and F-12 (P2) remain unverified; no P0/P1 blocker.
- Not done: response compression (6.5 MB uncompressed) is a possible later fix.

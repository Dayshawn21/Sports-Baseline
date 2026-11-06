# Current Feature

## P3 test clocks, rate-limit and rerun tests, props line cast

**Type:** Fix
**Branch:** `claude/fix-p3-tests-clocks-fb33db`
**Status:** Completed 2026-11-06. Verify passed after merging `master` (web 82 files / 1,242 tests and build; API 5,928 tests). Mutation runs showed each new test fails on the old behavior. F-31 stays open for its `api/app/routers/` part (props staleness check, Ask route clock), owned by a sibling session this round.
**Fixes:** F-31, F-36, F-37 (and the `repositories/props.py` part of F-32)

### The problem

- **F-31:** `history()` in `web/src/utils/nflPropDetail.ts` reads `new Date()`
  though its caller is passed `now`. `player_stats._fetch_matches` reads
  `date.today()`, so `test_player_stats_sources.py` builds its dates from the
  wall clock. The props staleness check and the Ask route clock live in
  `api/app/routers/`, which a sibling session owns this round.
- **F-36:** the two `X-Forwarded-For` rate-limit tests pass on the old code
  because TestClient never runs uvicorn's proxy-headers middleware. Nothing
  tests that a failed league skips the prune. The rerun tests never tie the
  refresh key to the `get_today_props` DISTINCT ON key.
- **F-37:** the refresh compares `props.line` (`numeric(6,1)`) with
  `CAST(:line AS numeric)` on the raw float, so a two-decimal line would never
  match its stored, rounded row. The per-line refresh subquery has no index.
- **F-32 (part):** `Any` in `repositories/props.py`.

### The fix

1. **Clocks.** `history()` takes `now: Date`; `nflPropDetail` passes
   `new Date(now)` and `DetailGameLog` passes its own. `_fetch_matches` takes a
   keyword `today: date | None = None`; the two callers pass their `today`.
   Tests pass a fixed date.
2. **Tests.** Rate-limit spoof tests run through
   `ProxyHeadersMiddleware(app, trusted_hosts="*")`. Extract
   `_fetch_league_props(client, league_ids)` from `run()` and test that a
   failed league is counted and that `run()` then stores with
   `prune_pulled=False`. Add a test parsing the DISTINCT ON key of
   `get_today_props` and asserting each term is in `_SAME_TODAY_LINE`.
3. **Props.** `CAST(:line AS numeric(6,1))`; replace `Any` with a concrete
   JSON type. The `(source, fetched_at)` index is proposed, not applied
   (migrations are manual against Neon).

Must not break: the board's DISTINCT ON, the F-20 snapshot-keeping refresh,
the F-19 rate-limit key. Do not touch `api/app/routers/` or the other
sibling-owned files.

### Build steps

- [x] **1. Clock injection (F-31).** Done when `nflPropDetail.test.ts` and
  `test_player_stats_sources.py` pass with fixed dates and no wall-clock read
  remains in `history()` or `_fetch_matches`.
- [x] **2. Tests that can fail (F-36).** Done when the spoof tests fail if
  `client_key` is changed to read `request.client.host` only, the league test
  fails if `run()` always prunes, and the key test fails if a DISTINCT ON term
  is dropped from `_SAME_TODAY_LINE`.
- [x] **3. Line cast and types (F-37, F-32 part).** Done when the refresh SQL
  casts to `numeric(6,1)`, a test asserts it, and `repositories/props.py` has
  no `Any`.

### Verify

`npm --prefix web run verify` and `pytest` from `api/` (dummy `DATABASE_URL`).

## Findings

### p3-test-clocks-props-line/F-36 [P3] closed - The prizepicks-rerun-snapshots/F-19 and prizepicks-rerun-snapshots/F-20 tests mostly cannot fail on the old code

**File:** api/tests/test_rate_limits.py; api/tests/test_prizepicks_rerun.py:80
**Found:** 2026-11-06 by /audit (scope: current; lens: tests)
**Why it matters:**
- `test_x_forwarded_for_alone_is_ignored` and `test_rotating_forwarded_for_does_not_reset_the_limit` pass before and after the fix, because TestClient never runs uvicorn's proxy-headers middleware. Only `test_each_cloudflare_address_gets_its_own_bucket` exercises the change.
- The rerun tests assert SQL substrings and grep the ingest's source, so they cannot catch a key mismatch with `get_today_props` or a rounding mismatch.
- Nothing tests that `run()` passes `prune_pulled=False` after a failed league fetch.
**Suggested fix:**
- Exercise the spoof path in the rate-limit tests by wrapping the app in `ProxyHeadersMiddleware(trusted_hosts="*")`.
- Extract the league-fetch loop so the failure count is unit-testable.
- Keep the SQL checks, but add one assertion that the refresh key matches the `get_today_props` DISTINCT ON expression.
**Resolution:** Fixed 2026-11-06. The rotating `X-Forwarded-For` test runs through `ProxyHeadersMiddleware(app, trusted_hosts="*")` with a fixed `CF-Connecting-IP`, as production sees it, and a second test shows the middleware puts the forwarded address in `request.client`; with the limiter keyed on the peer again, the rotating test fails. `run()`'s league loop is `_fetch_league_props`; tests show a failed league is counted and that `run()` then stores with `prune_pulled=False` (fails if `run()` always prunes). A new test parses `get_today_props`' DISTINCT ON and requires each term in `_SAME_TODAY_LINE` (fails when `p.stat_type` is dropped). The `from tests.test_x import` cross-imports stay with F-32. Closed by /audit current 2026-11-06 after mutation runs confirmed each new test fails on the old behavior. Known limit: the refresh matches the board identity's first two terms (player id, feed name), not its `player_display_name` / `description` fallbacks; the ingest already fills the feed name from `player_display_name`, so only a line with neither name could duplicate.

### p3-test-clocks-props-line/F-37 [P3] closed - The refresh matches a rounded column with an unrounded float, and scans per line

**File:** api/app/repositories/props.py:364
**Found:** 2026-11-06 by /audit (scope: current; lenses: quality, performance)
**Why it matters:**
- **Rounding:** `props.line` is `Numeric(6,1)` (migration `0001:156`), but the match compares `CAST(:line AS numeric)` on the raw float. A line with two decimals would be stored rounded and never matched again, so every re-run would insert a fresh row.
- **Scans:** each feed line runs a subquery on `COALESCE(player_id::text, ...)` that no index serves (the only props index is `(player_id, stat_type, fetched_at)`). That is one scan per line where the old code ran one delete.
- Neither is observed: tennis lines appear to be .0/.5, and the table size and run time were not measured.
**Suggested fix:** cast to `numeric(6,1)`; if run time grows, add an index on `(source, fetched_at)`.
**Resolution:** Fixed 2026-11-06. The refresh compares `p.line = CAST(:line AS numeric(6,1))`, the column's precision, so a two-decimal line matches its rounded row; a test asserts the cast. Scan: the one run on the per-line refresh (Actions run 42283777225 at `f9f5ab4e`, 113 lines, 30 pulled) took 41s in the ingest step, against 10s to 3.5 min for the previous five runs on the old delete (235 lines took 42s), so no slowdown is visible and the time is mostly round trips to Neon. No index added; if run time grows, an index on `props (source, fetched_at)` would need a new migration applied by hand to Neon. Closed by /audit current 2026-11-06.

### p3-test-clocks-props-line/F-35 [P3] invalid - prizepicks-rerun-snapshots/F-19's key relies on Cloudflare always setting CF-Connecting-IP on Render

**File:** api/app/core/rate_limits.py:27
**Found:** 2026-11-06 by /audit (scope: current; lens: security)
**Why it matters:** `client_key` falls back to `request.client.host`, which under `--forwarded-allow-ips '*'` is still the client-written leftmost `X-Forwarded-For` entry. If a request reaches the API without `CF-Connecting-IP`, or Cloudflare passes a client-sent one through, the prizepicks-rerun-snapshots/F-19 bypass returns. Neither is verified; sources are a Render community thread and a blog post.
**Suggested fix:** after deploy, send 11 requests to a heavy route with rotating fake `CF-Connecting-IP` and `X-Forwarded-For`; the 11th must be a 429. If the header is ever missing in production, key on `"unknown"` there rather than the peer (`is_production()`).
**Resolution:** Invalid 2026-11-06, verified on production (`sportapp-api-ftsf.onrender.com`, running `9960c720`): 11 requests with a client-set `CF-Connecting-IP` were rejected by Cloudflare with a 403 before reaching Render, so a client cannot supply that header; 11 requests to `/nfl/slate` with a different fake `X-Forwarded-For` each were limited as one client (429 from the 10th, one earlier request had counted), so the deployed key is not taken from `X-Forwarded-For` and Cloudflare's header is present. The fallback hardening is not needed. Note: `sportapp-api.onrender.com`, still named in some docs, is an old suspended service.

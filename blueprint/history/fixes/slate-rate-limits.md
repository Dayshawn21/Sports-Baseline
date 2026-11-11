# Heavy rate-limit bucket for the cached NBA and NHL slates

**Type:** Fix
**Fixes:** F-45
**Completed:** 2026-11-11
**Branch:** `fix/slate-rate-limits`

### The problem

`/nba/slate`, `/nhl/slate` and `/nba/slate/gaps` build through a
`SerialBuildCache` since `b6dee2f4`. A cache hit skips the lock, but a miss
waits behind every other miss on that cache, and each cache keeps 5 dates.
`date` is client input, and these paths share the 120/minute default bucket in
`app/core/rate_limits.py`. One client cycling 6 or more dates can keep evicting
today's entry, so ordinary home loads miss and wait behind gap builds (about
3.4 s each). `/nfl/slate`, the other serial cache, is already in `HEAVY_PATHS`
(10/minute per path per client) for this reason.

### The fix

Add `/nba/slate`, `/nhl/slate` and `/nba/slate/gaps` to `HEAVY_PATHS`.

Why 10/minute is enough for people: every web caller (home, the slate pages,
the game pages, the NBA prop board) keys these queries on the date with a
5-minute `staleTime`, so a request only goes out for a date not seen in the
last 5 minutes. Each path has its own heavy bucket, so the home page's three
calls never count against each other.

Must not change:

- The default bucket for every other route, including `/nba/props`,
  `/nhl/props` and the game detail routes.
- `/health` staying exempt.
- `rule_for_path` itself: `HEAVY_PATHS` matches the path without the query
  string, so `?date=` does not create new buckets.

Accepted cost: a client that opens more than 10 new dates on one of these paths
within a minute gets a 429 with `Retry-After`, as `/nfl/slate` does today.

### Build steps

- [x] **1. Move the three paths to the heavy bucket.** Add them to
  `HEAVY_PATHS`, move `/nba/slate` from the default-bucket test case to the
  heavy one in `tests/test_rate_limits.py`, and add `/nhl/slate` and
  `/nba/slate/gaps` there. Keep a default-bucket case that sits beside them
  (`/nba/props`) so a prefix match cannot creep in unnoticed.
  *Done when:* `test_rate_limits.py` passes with the moved and added cases.

### Verify

- Verify: `npm --prefix web run verify && cd api && python -m pytest`
- After deploy, run 11 quick `/nba/slate/gaps?date=...` requests with distinct
  dates from one client: the 11th returns 429 with `Retry-After`, and a request
  to `/nba/slate` in the same minute still returns 200 (its own bucket).

### Outcome

- Verify passed on the branch: `npm --prefix web run verify` (1540 tests,
  typecheck, build) and `python -m pytest` (6090 passed).
- Not observed yet: the production 429 after deploy. F-45 stays `fixed` in
  the ledger until an `/audit` re-review closes it.

## Findings

### slate-rate-limits/F-45 [P3] closed - The newly serialized NBA and NHL slate builds sit in the default rate-limit bucket

**File:** api/app/core/rate_limits.py:16; api/app/services/nba/slate_gaps.py:39
**Found:** 2026-11-11 by /audit (scope: b6dee2f4 latency fix; lenses: all)
**Why it matters:**
- `/nba/slate`, `/nhl/slate` and `/nba/slate/gaps` now build through a `SerialBuildCache`: a hit skips the lock, but a miss waits behind every other miss on that cache. Each cache keeps 5 dates.
- `date` is client input, and these paths share the 120/minute default bucket. One client cycling 6 or more dates can keep evicting today's entry, so a normal home load misses and waits behind 3.4 s gap builds. `/nfl/slate`, the other serial cache, is in `HEAVY_PATHS` (10/minute) for this reason.
- Before the fix the same client could already load the instance (every gaps request was a full build), so this is a shift in who waits, not a new hole. Not reproduced.
**Suggested fix:** add `/nba/slate/gaps` to `HEAVY_PATHS`, and the two slates if a heavier bucket does not hurt date browsing on the slate pages; update `test_rate_limits.py`.
**Resolution:** Fixed on `fix/slate-rate-limits` (2026-11-11), awaiting re-review. `/nba/slate`, `/nba/slate/gaps` and `/nhl/slate` are in `HEAVY_PATHS` (10/minute per path per client); `test_rate_limits.py` covers them and keeps `/nba/props`, `/nhl/props` and `/nba/slate/other` in the default bucket. Closed 2026-11-11 by /audit after re-reading `20f03e56`: exact-path match on the root-mounted routers, one bucket per path, no new defect. Production after deploy: 11 rapid `/nba/slate/gaps` requests from one client gave ten 200s then a 429 with `Retry-After: 55`, while `/nba/slate`, `/nhl/slate` and `/nba/props` still returned 200 in the same minute.

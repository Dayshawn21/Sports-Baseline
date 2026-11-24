# Bound the model-route rate limit and caches, and drop `/nfl/prospects`

**Type:** Fix
**Fixes:** F-25, F-28

## The problem

- **F-25 (rate rule).** `HEAVY_PREFIXES` in `api/app/core/rate_limits.py` covers
  the NFL, tennis and NBA model routes but not `/nhl/model/`, so
  `/nhl/model/ranking`, which replays grading on a cold cache, shares the
  default bucket.
- **F-25 (caches).** `TimedSingleFlight` (`api/app/services/tennis/live_odds_cache.py`)
  never drops an entry or a lock. The NFL ranking, CLV and prop-line caches, the
  NFL volume ranking, and the NBA and NHL rankings key it by the raw `season`
  query int, so any season a client sends adds an entry and its own parallel
  build on the 512 MB Render API.
- **F-28.** `/nfl/prospects` runs `get_latest_prop_lines`, a `DISTINCT ON` over
  every NFL `sport_prop_lines` row with no bound. Nothing calls it: the web only
  redirects the old `/nfl/prospects` page to `/nfl` (`web/src/App.tsx:170`), and
  `NflProspectsResponse` and `NflPropLineSchema` are used only by that route.

## The fix

- Add `"/nhl/model/"` to `HEAVY_PREFIXES`. Keep `client_key` (F-19) as it is.
- Give `TimedSingleFlight` an optional `max_entries`. Beyond it, the least
  recently stored key is dropped, along with its lock when no build holds it.
  The default stays unbounded, so the tennis date-keyed caches are unchanged.
- Set `max_entries` on every season-keyed cache.
- Add a pure `is_model_season(season, today)` in `app/core/` (a first season
  through the current calendar year) and return 422 from the NFL, NBA and NHL
  model routes for any other season, before the cache is touched. The web only
  ever asks for the current season.
- Remove `/nfl/prospects`, `get_latest_prop_lines`, `NflProspectsResponse` and
  `NflPropLineSchema`. Keep the web redirect so old bookmarks still land.

Must not break: the F-19 `client_key` rule, existing cache single-flight and
failure-TTL behavior, and the season the web sends today.

## Build steps

- [x] **Step 1 - rate rule and cache bound.** `/nhl/model/` is heavy;
  `TimedSingleFlight` takes `max_entries` and the season-keyed caches set it;
  model routes reject an unknown season with 422.
  Done when: tests show `/nhl/model/ranking` gets its own heavy bucket, a bounded
  cache keeps at most `max_entries` keys and locks, and an out-of-range season
  returns 422 without a build.
- [x] **Step 2 - remove `/nfl/prospects`.** Route, repository function and the
  two schemas go.
  Done when: `grep` finds no reference outside history and the redirect, and
  `GET /nfl/prospects` is 404.

## Verify

`npm --prefix web run verify && cd api && python -m pytest` passes (API half
with a dummy `DATABASE_URL`, since no test connects).

## Findings

### model-limits-caches/F-25 [P2] closed - `/nhl/model/` is not rate-limited as heavy, and season-keyed caches never evict

**File:** api/app/core/rate_limits.py:8; api/app/services/tennis/live_odds_cache.py:47
**Found:** 2026-11-06 by /audit (scope: full; lens: performance)
**Why it matters:** `HEAVY_PREFIXES` lists the NFL, tennis and NBA model routes but not `/nhl/model/ranking`, which replays on a cold cache. `TimedSingleFlight` only grows its `_entries` and `_locks`, is keyed by the raw `season` query int (NFL, NBA, NHL track records, NFL volume ranking), and builds different keys concurrently, so arbitrary seasons add entries and parallel builds. Memory impact unmeasured.
**Suggested fix:** add `"/nhl/model/"` to `HEAVY_PREFIXES`; bound `season` in the routers to known seasons, or give `TimedSingleFlight` a `max_entries` like `SerialBuildCache`.
**Resolution:** fix/f25-f28-limits-caches: `"/nhl/model/"` added to `HEAVY_PREFIXES`; `TimedSingleFlight` takes `max_entries` (LRU, drops the idle lock too) and every season-keyed cache sets it (NFL 8, NBA/NHL/NFL volume 4); the NFL, NBA and NHL model routes 422 any `season` outside `is_model_season` (2020 through this year) before the cache. Closed 2026-11-06 by /audit (scope: current): all six season-keyed caches pass `max_entries` (raised to 16, 32 for the NFL ranking, after the audit found 4/8 below the accepted key count), all five season-taking model routes go through `model_season`, OpenAPI keeps `season`, and the web never sends a season outside the window. Tests cover the heavy NHL bucket, LRU eviction, a held lock surviving eviction, and the 422 on NFL, NBA and NHL.

### model-limits-caches/F-28 [P2] closed - `/nfl/prospects` scans every stored NFL prop line and nothing calls it

**File:** api/app/routers/nfl.py:129; api/app/repositories/nfl.py:2390
**Found:** 2026-11-06 by /audit (scope: full; lens: performance)
**Why it matters:** `get_latest_prop_lines` runs `DISTINCT ON` over all NFL `sport_prop_lines` with no season, time or `LIMIT` bound, on a public route that the web only redirects (`App.tsx:170`). It grows with every ingest and is not in the heavy rate limit.
**Suggested fix:** remove the endpoint (and the repository function if unused), or bound it to upcoming games.
**Resolution:** fix/f25-f28-limits-caches: no caller (the web only redirects the old page), so `/nfl/prospects`, `get_latest_prop_lines`, `NflProspectsResponse` and `NflPropLineSchema` are removed; the redirect stays for old bookmarks. Closed 2026-11-06 by /audit (scope: current): grep over api/ and web/src finds only the redirect and the 404 test; the route is absent from OpenAPI; no unused imports remain.

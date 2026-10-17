# Remove the Live Odds page

**Type:** Fix

## The problem

The owner decided on 2026-10-15 to drop the Live Odds page. It is the only
public page where any visitor triggers an Odds-API.io fetch on demand, and it
adds code to secure before the public demo. The tennis best-picks fallback
already gives the slate live moneylines where stored odds are missing.

## The fix

**Remove:**

| Area | What goes |
|---|---|
| Web page | `web/src/pages/LiveOddsPage.tsx` |
| Web helpers | `web/src/utils/liveOdds.ts` and `liveOdds.test.ts` (only the page imports them) |
| Web nav and route | the `/live-odds` entry in `web/src/utils/sportNav.ts`, its two lines in `sportNav.test.ts`, and the import and `<Route>` in `web/src/App.tsx` |
| API endpoint | `GET /tennis/props/live-odds` in `app/routers/props.py`, with its page cache (`_LIVE_ODDS_PAGE`, `_LIVE_ODDS_PAGE_TTL_SECONDS`, `_LIVE_ODDS_DEFAULT_HOURS`) and `_fetch_live_odds_page` |
| Dead helper | `rate_limit_retry_at` in `app/services/tennis/live_odds_cache.py`; only the page cache used it |
| Dead setting | `demo_mode` in `app/config.py`; it only pinned this endpoint's window (added by the API hardening fix) |
| API tests | `tests/test_live_odds_page.py`: the page-cache tests, the demo-mode tests and `TestRateLimitRetryAt` |

**Keep:**
- **The fetch:** `_fetch_live_tennis_odds` and `_provider_status_error`. The
  best-picks fallback (`_overlay_live_moneyline` in `app/routers/tennis.py`)
  calls them through its own fixed-key 15-minute cache.
- **The rate-limit error:** `LiveOddsRateLimited`, which the fetch still raises.
  Its test (`test_a_provider_429_becomes_a_rate_limit_error`) moves into
  `tests/test_live_odds_overlay.py`.
- **Shared code:** `TimedSingleFlight` (used by track-record caches),
  `bookmaker_scope_param`, and the `live_odds_bookmakers` setting (the tennis
  odds ingest reads both).

**Must not break:**
- best picks on the tennis slate and prop board
- the tennis odds ingest
- every other nav entry and route

The router has no catch-all, so `/live-odds` redirects to `/`, as the retired `/props` already does (added during step 1).

## Build steps

- [x] **1. Remove the web page.** Delete the page, its helpers and their tests,
  the nav entry and the route.
  - **Done when:** `grep -rn "live-odds\|LiveOdds\|liveOdds" web/src` finds only the redirect.
  - **Done when:** `npm run build` and `npm run test` pass.
- [x] **2. Remove the endpoint.** Delete the endpoint, its cache,
  `rate_limit_retry_at`, `demo_mode` and the page tests. Move the 429 test.
  - **Done when:** `grep -rn "_LIVE_ODDS_PAGE\|rate_limit_retry_at\|demo_mode\|/live-odds" api/app api/tests`
    finds nothing.
  - **Done when:** `pytest` passes, including `test_live_odds_overlay.py` and `test_best_picks_live_odds.py`.

## Verify

- Both suites and the web build pass.
- **Manual:** with the dev servers running:
  - the nav has no Live Odds
  - the tennis slate still shows best picks
  - `curl localhost:8000/tennis/props/live-odds` returns 404

## Follow-up (not in this fix)

`project-overview.md` still lists `/live-odds` in the web routes and
`live-odds` in the `/tennis/props` API row. It is generated, so record the
removal through the plans and `/overview`, not by hand.

## Outcome (2026-10-15)

- **Checks:**
  - `npm run build` succeeded, before and after the redirect.
  - `npm run test` passed 43 files and 511 tests. The 9 tests for the deleted `liveOdds.ts` helpers went with them.
  - `pytest` gave 2570 passed: the 17 page tests were removed, and the 429 test moved to `test_live_odds_overlay.py`.
  - `GET /tennis/props/live-odds` returns 404, and the route is no longer registered.
- **Added beyond the spec:** `/live-odds` redirects to `/` (owner's choice), like the retired `/props`.
- **Left alone:** five unused `app.core.prop_projection` imports in `app/routers/props.py` that predate this fix.
- **Interview guide:** unchanged. It never named the page, and its quota claim (shared cache on provider lookups) still holds through the best-picks fallback.
- **Follow-ups:**
  - `project-overview.md` still lists `/live-odds`; refresh it through the plans and `/overview`.
  - Caching `predict_today` per date: a 20-visitor burst measured a median of 4.0 s and a slowest of 6.1 s on `/tennis/predictions/today` plus best picks, uncached.

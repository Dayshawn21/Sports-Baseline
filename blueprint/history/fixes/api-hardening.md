# Harden the API for a public read-only demo

**Type:** Fix

Portfolio plan, Phase 2. Phase 3 (the admin-only login) builds on this.

## The problem

The API is safe today only because it runs on localhost. Exposed publicly:

| Gap | Where |
|---|---|
| Admin POSTs and bets POST/PATCH/DELETE are open to anyone. `require_api_key` exists but nothing uses it. | `app/security.py`, `app/routers/admin.py`, `app/routers/bets.py` |
| `ADMIN_API_KEY` empty means the routes are open, and nothing stops a production deploy with it empty. | `app/config.py` |
| CORS is hardcoded to `http://localhost:3000`. | `app/main.py` |
| No rate limiting. The model pages replay `build_slate` (`/nfl/model/prop-lines` takes 22 s cold), so a few requests can tie up the server. | all routers |
| `/tennis/props/live-odds` caches per `(bookmakers, hours_ahead)`, and `hours_ahead` accepts 1 to 72. A visitor cycling it gets up to 72 fresh provider fetches in 15 minutes, against a 100-an-hour Odds-API.io quota shared with ingest. | `app/routers/props.py:928` |
| No security response headers. | `app/main.py` |
| `test_arms_score_only_the_common_subset` compares floats exactly (`0.20000000000000007 == 0.2`) and fails on master, so the suite is red. | `tests/test_nfl_prop_market.py:118` |

## The fix

- **Production is `API_ENV=production`.** Reuse the existing `api_env` setting
  (default `dev`, as `/health` already reports) instead of adding a new one.
- **New settings** in `app/config.py`:
  - `cors_origins: list[str]`, default `["http://localhost:3000", "http://localhost:3001"]`, read from JSON in `.env`
  - `demo_mode: bool = False`
  - `rate_limit_default: str = "120/minute"`, `rate_limit_heavy: str = "10/minute"`
- **Startup check:** a pure `validate_production_settings(settings) -> list[str]`
  in `app/core/` returns the problems. Lifespan raises if any are found:
  - `admin_api_key` is empty or under 32 characters
  - `cors_origins` contains `*` or a `localhost` origin

  A non-production env is never checked.
- **Guard the writes:**
  - `dependencies=[Depends(require_api_key)]` on the whole admin router (`include_router` in `main.py`)
  - `Depends(require_api_key)` on the three bets write routes; the bets GETs stay open
  - `require_api_key` keeps its local behavior, open with a warning when the key is empty
- **Rate limiting** with `slowapi` (new dependency, pinned in
  `requirements.txt`), keyed by client IP:
  - a global default limit
  - the stricter heavy limit on every `/nfl/model/*`, `/tennis/model/*` and `/nba/model/*` route, plus `/nfl/slate`
  - over the limit returns 429 with a `Retry-After` header
  - storage is in-memory, which is enough for one instance
- **Demo mode for live odds:** when `demo_mode` is true, `hours_ahead` is pinned
  to its default (12) before the cache lookup. That leaves one cache key, so at
  most one provider fetch per 15 minutes whatever visitors send. Phase 3 lets a
  logged-in admin bypass the pin.
- **Security headers:** a small middleware in `main.py` sets:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Strict-Transport-Security` (production only)
- **The float test:** `pytest.approx(0.2)`.

**Must not break:**
- **Local dev with the current `.env`:** `API_ENV=dev` and an empty key keep every route open, and CORS still allows the Vite origin.
- **The GitHub Actions ingest jobs:** they call ingest modules directly, not the HTTP API, so they are unaffected.
- **The web Admin and My Bets pages:** they send no `X-API-Key`, so they only fail when a key is set. That is the production case, and Phase 3's login replaces it.

## Build steps

- [x] **1. Green suite.** Fix the float comparison.
  - **Done when:** `pytest` is fully green.
- [x] **2. Settings, startup check, CORS, headers.** Add the new settings,
  `validate_production_settings` with tests, the lifespan check, CORS from
  settings, and the headers middleware.
  - **Done when:** tests cover every validation rule.
  - **Done when:** a `TestClient` response carries the headers.
  - **Done when:** startup with `API_ENV=production` and an empty key fails with a clear message.
- [x] **3. Guard the writes.** Apply `require_api_key` to the admin router and
  the bets writes.
  - **Done when:** with a key set, a write without the header returns 401, a wrong key returns 401, and the right key passes.
  - **Done when:** bets GETs need no key.
  - **Done when:** with the key empty, writes stay open.
- [x] **4. Rate limiting.** *Built with `limits==5.8.0` (slowapi's own engine)
  in one middleware, instead of slowapi: slowapi applies per-route limits by
  decorator, which needs a `request: Request` parameter added to each of the
  nine heavy endpoints. `/health` is exempt (platform probes); each heavy route
  has its own bucket per client.* Add `slowapi`, the default and heavy limits, and the
  429 handler.
  - **Done when:** a test with a tiny configured limit gets 429 plus `Retry-After` on the request past the limit.
  - **Done when:** the full suite stays green, so the limit doesn't break tests.
- [x] **5. Demo-mode live odds.** Pin `hours_ahead` when `demo_mode` is on.
  - **Done when:** a test with the provider fetch mocked shows two different `hours_ahead` requests in demo mode cause one fetch, and two in normal mode.

## Verify

- `cd api && .venv/Scripts/python.exe -m pytest` passes fully.
- `cd web && npm run build && npm run test` passes. No web change is expected.
- **Manual:** run `uvicorn app.main:app` with the normal `.env`. `/health`, the
  tennis slate and Admin all work as before. Then set `ADMIN_API_KEY` and confirm:
  - `curl -X POST localhost:8000/admin/players/1/fetch-elo` returns 401
  - the same request with `-H "X-API-Key: <key>"` passes
  - `curl -I localhost:8000/health` shows the security headers

## Outcome (2026-10-15)

- **Checks:** `pytest` gives 2586 passed (45 new tests; 2540 passed, 1 failed
  before step 1). `npm run build` succeeded and `npm run test` passed 44 files
  and 520 tests, with no web change.
- **Smoke test:** with `uvicorn` in dev, `/health` carries the three headers
  and a preflight from `http://localhost:3001` is allowed. With
  `API_ENV=production` and no key, startup is refused with every problem listed.
- **Changes from the spec:**
  - rate limiting uses `limits` directly, not `slowapi` (step 4 note)
  - the guard covers the whole admin router, so `GET /admin/players/flagged` also needs the key
- **Deploy notes for later phases:**
  - Render must run uvicorn with `--proxy-headers`, or every visitor shares one rate-limit bucket
  - the web Admin and My Bets pages send no key, so they fail once one is set until the Phase 3 login
- **Superseded next:** the owner chose to delete the Live Odds page and its
  `/tennis/props/live-odds` endpoint in a separate fix, which removes step 5's
  demo-mode pin with it. The best-picks fallback keeps its own fixed-key
  15-minute cache (`_LIVE_ODDS` in `app/routers/tennis.py`), at most 4
  provider calls an hour.

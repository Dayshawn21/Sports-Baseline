# Live Odds quota and rate-limit message

**Type:** Fix

**Branch:** `fix/live-odds-quota`

## The problem

The Live Odds page (`/live-odds`) spends Odds-API.io quota on every load, and
the plan allows only 100 requests an hour.

- `GET /tennis/props/live-odds` (`api/app/routers/props.py`) calls
  `_fetch_live_tennis_odds` directly on each request: one `/events` call plus
  one `/odds/multi` call per 10 events, about 3 requests for the default
  12-hour window.
- **Auto** refreshes every 60 seconds, so about 180 requests an hour.
  **Refresh** and every window change spend more.
- The quota ran out twice on 2026-09-25. The earlier fix
  (`blueprint/history/fixes/tennis-odds-quota-and-stale-lines.md`) cached only
  the best-picks overlay and left this page uncached on purpose.
- On a 429 the page prints the provider's raw JSON body
  (`Events fetch failed: {...}`), with no hint of when it will work again.
- The "last fetched" time in the top bar is the browser's request time, not
  when the odds were fetched.

## The fix

1. **Cache the page endpoint.** Serve `/tennis/props/live-odds` through its own
   `TimedSingleFlight` (`app/services/tennis/live_odds_cache.py`), 15 minutes,
   keyed by `(bookmakers, hours_ahead)`. Concurrent requests share one fetch.
   - Its own instance, not the best-picks `_LIVE_ODDS` one in
     `app/routers/tennis.py`: the two store different value shapes, and the
     overlay must keep treating a failure as `None`.
   - Each window the user picks costs at most one fetch per 15 minutes, so
     worst case (all five windows, Auto on) stays well under 100 an hour.
2. **Remember failures, with a retry time.** A failed fetch is cached for the
   same window, so Auto and Refresh cannot hammer a rate-limited API.
   - On a provider 429, `_fetch_live_tennis_odds` raises a rate-limit error
     that still subclasses `HTTPException(429)`, so the overlay's behavior is
     unchanged. It carries the parsed `x-ratelimit-reset` header.
   - A small pure helper turns that header into a UTC `retry_at`, falling back
     to the cache entry's expiry when the header is missing or unparseable.
     Accept epoch seconds and ISO 8601; anything else uses the fallback.
   - The route answers a cached rate limit with `429` and a structured detail:
     `{"message": "...", "retry_at": "<ISO UTC>"}`. Other cached failures keep
     their status code and a short message, never the raw provider body.
3. **Report when the odds were fetched.** Success responses gain `fetched_at`
   (ISO UTC), set when the provider was actually called, so a cached response
   keeps its original time.
4. **Page changes** (`web/src/pages/LiveOddsPage.tsx`):
   - The status bar shows "Odds as of HH:MM" from `fetched_at`, replacing the
     browser-time stamp.
   - A 429 shows "Odds-API.io hourly limit reached. Try again after HH:MM."
     (local time from `retry_at`), not the raw body.
   - The Auto button's tooltip says the server refreshes every 15 minutes.
     Auto keeps polling every 60 seconds; a cache hit costs no quota.
   - Error parsing moves to a typed helper in `web/src/utils/liveOdds.ts`,
     which also removes the page's `catch (e: any)`.

**Must not break:**
- The best-picks live moneyline overlay and its cache (`tennis.py`), and
  `test_live_odds_overlay.py`.
- The `hours_ahead` clamp (1 to 72) and the `LIVE_ODDS_BOOKMAKERS` scope.
- The dynamic book columns from 16d.

**Out of scope:** a manual cache bypass, a longer or configurable TTL,
widening one fetch to serve every window, moving the page to a TanStack Query
hook, and any restyle (item 31 owns that).

## Build steps

- [x] **Step 1 - API: cache and rate-limit detail.** Add the rate-limit error
  and the pure `retry_at` helper, route `/live-odds` through its own
  `TimedSingleFlight`, add `fetched_at`, and return the structured 429 detail.
  Tests in `api/tests/` with a fake fetch and a fake clock, no network:
  - `retry_at` from epoch, ISO, missing and garbage headers
  - a second request inside the window does not call the fetch, and keeps the
    first `fetched_at`
  - a rate-limited fetch is cached: a second request returns 429 with the same
    `retry_at` and no new fetch
  - after the window expires, the next request fetches again

  **Done when:** those tests and the existing `pytest` suite pass, and
  `test_live_odds_overlay.py` passes unchanged.

- [x] **Step 2 - Web: as-of time and friendly message.** Add the error and
  as-of helpers to `web/src/utils/liveOdds.ts` with Vitest tests (429 with
  `retry_at`, 429 without it, other status, network error with no response),
  then wire them into the page and update the Auto tooltip.

  **Done when:** `npm run test` and `npm run build` pass, and the page shows
  "Odds as of HH:MM" and the friendly 429 message against a mocked response.

## Verify

- `cd api && pytest` and `cd web && npm run test && npm run build`.
- **Quota-free check:** with the API running, stub `_fetch_live_tennis_odds`
  (or mock the endpoint in the browser, as 31a did) rather than calling
  Odds-API.io. Load `/live-odds`, then Refresh: the "Odds as of" time does not
  change and the API log shows one fetch. Force a 429 from the stub: the page
  shows the friendly message with a time, and a Refresh makes no new fetch.
- **Optional, spends about 3 requests:** one real load of `/live-odds` on the
  12-hour window, then several Refreshes, confirming a single provider call in
  the API log.

## Outcome (2026-09-28)

- `pytest` in `api/`: 1785 passed, 16 of them new in `tests/test_live_odds_page.py`.
- `npm run test` (236 passed) and `npm run build` in `web/`.
- The page was checked in a browser against mocked responses, spending no quota:
  "Odds as of 01:05 PM" for a fetch at 18:05 UTC, and after a mocked 429,
  "Odds-API.io hourly limit reached. Try again after 01:40 PM."
- Every cached failure, not only a 429, returns `detail` as
  `{"message", "retry_at"}`, so the page parses one shape.
- **Known limit:** a cache entry lasts 15 minutes even when the provider's reset
  is later, so a long rate limit can still cost one request per 15 minutes.
- The optional real-API check (about 3 requests) was not run.

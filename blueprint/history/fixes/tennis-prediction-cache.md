# Cache tennis predictions per date

**Type:** Fix

Portfolio plan, item 2: keep a burst of visitors from slowing the tennis pages
before the public demo.

## The problem

Every load of the tennis slate calls `/tennis/predictions/today` and
`/tennis/predictions/best-picks`. Both run `predict_today` from scratch: batch
queries plus ELO and LightGBM for every match on today and tomorrow. Best picks
then loads props, rolling stats and market inputs and builds picks for every
match, again per request. Nothing is shared between visitors.

Measured in the Live Odds removal fix (2026-10-15): a burst of 20 visitors
against both endpoints took a median of **4.0 s** and a slowest of **6.1 s**,
uncached.

## The fix

Two short in-process caches built on the existing `TimedSingleFlight`, so a
burst computes each answer once and everyone else waits for that one result.

| Cache | Key | TTL | Serves |
|---|---|---|---|
| Predictions | the sorted tuple of target dates | 5 min | `/predictions/today` and best picks |
| Best picks | the sorted tuple of target dates | 5 min | `/predictions/best-picks` |

- **New module** `app/services/tennis/prediction_cache.py`:
  - `cached_predictions(db, registry, dates)` wraps `predict_today`
  - `cached_best_picks(dates, build)` caches the built `BestPicksResponse`
  - both return copies (`copy.deepcopy`), so a caller that mutates a result
    never changes the cached one. This matters: `_overlay_live_moneyline`
    writes live odds into `PredictionOutput` in place.
- **The `tour` filter runs after the cache,** so ATP, WTA and unfiltered
  requests share one entry. Best picks filters the cached response's matches by
  tour, the same `upper()` comparison as today.
- **Only near dates are cached:** every target date from yesterday to two days
  ahead. Any other `match_date` computes uncached, so a visitor cycling dates
  can't fill memory. The rate limiter already bounds those requests.
- **Failures are not cached for long.** `TimedSingleFlight` gains an optional
  `failure_ttl_seconds` (default: the same as `ttl_seconds`, so the track
  record and live-odds caches are unchanged). Both prediction caches use 10 s.
  When a cache returns None, the endpoint returns 503 "Tennis predictions are
  temporarily unavailable."
- **5 minutes** matches the web's 5-minute `staleTime` for slate data. Odds
  ingest runs far less often, and the live-odds overlay already caches for
  15 minutes.

**Must not break:**
- The match page: it predicts one match through `predict_matches`, not the
  cache, so it stays exact.
- Admin's flagged-players list, the bankroll builder and the predictions
  ingest: they keep calling `predict_today` directly. Admin needs fresh
  results, and ingest stores what it computes.
- Response shapes: unchanged for both endpoints.

**Known trade-off:** a slate can be up to 5 minutes behind a fresh odds or
status ingest. The cache is per process, which is fine for one instance.

## Build steps

- [x] **1. Measure the baseline.** A throwaway burst script in the scratchpad
  (not the repo): 20 concurrent `httpx` clients, each requesting both
  endpoints against local uvicorn, printing the median and slowest total time.
  - **Done when:** the baseline numbers are recorded in this spec.
  - **Baseline (2026-10-15, 51 matches on the slate, uncached):**

    | Run | Median | Slowest |
    |---|---|---|
    | 1 visitor | 2.16 s | 2.16 s |
    | 20 visitors, first burst after startup | 18.12 s | 20.12 s |
    | 20 visitors, warm | 4.42 s | 6.11 s |
- [x] **2. Prediction cache.** `failure_ttl_seconds` on `TimedSingleFlight`,
  `cached_predictions`, the near-date rule, and both endpoints switched to it,
  with the 503 path.
  - **Done when:** tests (fake clock, `predict_today` stubbed with a call
    counter) show:
    - 20 concurrent calls compute once
    - a result mutated by a caller leaves the cache unchanged
    - an out-of-window date is never cached
    - a failure is retried after 10 s, not 5 minutes
    - the existing `TimedSingleFlight` callers keep the failure TTL they had
  - **Done when:** `pytest` passes.
- [x] **3. Best-picks cache.** `cached_best_picks` around the body of
  `get_best_picks`, keyed by dates, with the tour filter applied after.
  - **Done when:** a test shows two best-picks calls with different `tour`
    values build once and each returns only its tour's matches.
  - **Done when:** `pytest` passes, and the burst script's median and slowest
    times are recorded after the change, with the second burst served from
    cache.
  - **After (2026-10-15, same 51-match slate):**

    | Run | Before | After |
    |---|---|---|
    | 20 visitors, first burst after startup | 18.12 s / 20.12 s | 5.23 s / 5.25 s |
    | 20 visitors, warm | 4.42 s / 6.11 s | 0.26 s / 0.26 s |
    | 1 cached call, today / best picks | about 2 s together | 0.007 s / 0.021 s |

    Median / slowest. The first burst after startup still pays one cold
    compute, which every visitor waits on together.

## Verify

- `pytest` passes; `npm run build` and `npm run test` pass (no web change).
- The burst script shows the cached run well under the 4.0 s / 6.1 s baseline.
- **Manual:** open the tennis slate and switch the tour filter; the matches and
  best picks match the uncached response from before the change.

## Outcome (2026-10-15)

- **Checks:** `pytest` 2562 passed (12 new in
  `tests/test_tennis_prediction_cache.py`); `npm run build` succeeded and
  `npm run test` passed 43 files and 511 tests, with no web change.
- **Result:** a warm 20-visitor burst fell from 4.42 s / 6.11 s to 0.26 s /
  0.26 s (median / slowest), and the first burst after startup from 18.12 s /
  20.12 s to 5.23 s / 5.25 s. Cached calls take 0.007 s (today) and 0.021 s
  (best picks).
- **Live consistency:** ATP and WTA responses equal the full best-picks list
  filtered by tour, and a repeated call is identical. The cached output was not
  diffed against the pre-change code.
- **Added beyond the spec:** the `TimedSingleFlight` failure log now reads
  "Cached lookup" instead of "Live odds lookup", since the class serves more
  than live odds.
- **Investigated:** one early burst after step 2 spiked to a 28 s median. The
  copies were ruled out (20 deepcopies of 51 predictions take 0.087 s); the
  cause was 20 concurrent uncached best-picks builds against the remote
  database, which step 3 removed.
- **Interview guide:** the public-access answer now includes the burst
  measurement and the caching trade-off.
- **Follow-ups:**
  - The first burst after a restart still waits on one cold compute (about
    5 s); a startup warm-up call would remove it.
  - The cache is per process, which suits one Render instance only.

# Fix: Preconnect to the API and lighten the home prefetch

**Type:** Fix
**Branch:** `fix/api-preconnect` (worktree `.claude/worktrees/sharp-elbakyan-f84efc`, cut from `master` at `31bcf582`)
**Status:** complete (2026-11-23)

## The problem

The home page's LCP is still the tennis card's next-match link. Lighthouse 13.6
(mobile, production, `13684411`, run 25: score 83, simulated LCP 3.82 s,
observed 895 ms) shows its data request is held up twice:

1. **No preconnect to the API origin.** The API is
   `sportapp-api-ftsf.onrender.com`, another origin, and nothing opens a
   connection to it early. The first API requests pay DNS, TCP and TLS after
   the JS wave: `/tennis/predictions/today` took 354 ms (475-829 ms) against
   about 115-200 ms for later calls on the open connection. Lighthouse lists the
   origin as the only preconnect candidate, **est. 345 ms LCP savings**.
2. **The prefetch waits for the hooks' dependencies.** `homePrefetch` imports
   `useNba`, `useNfl`, `useNhl` and `useTennisSlate` for four query options, and
   those modules pull `modelRankingQuery`, `nflTrackRecord`, `trackRecord`,
   `slatePeriod` and more. The prefetch fires at 475 ms instead of about 360 ms,
   right after its own 0.8 KB chunk.

## The fix

- **Preconnect** (main): a small Vite plugin in `vite.config.ts`
  (`transformIndexHtml`) adds
  `<link rel="preconnect" href="<origin>" crossorigin>` to `index.html` when
  `VITE_API_BASE_URL` is set at build time, using the same validation as
  `resolveApiBaseUrl` (an http(s) origin; the origin part only). Dev, where the
  value is unset and Vite proxies `/api`, gets no link. `crossorigin` because
  the API calls are CORS requests without credentials, so the preconnected
  socket is the one they use.
- **Lighter prefetch**: `hooks/homeQueries.ts` holds the four query-option
  builders the home page prefetches (`tennisSlateQuery`, `nflCurrentWeekQuery`,
  `nbaSlateQuery`, `nhlSlateQuery`), importing only the API functions,
  `queryTimes` and `slateDates`. The hooks import them from there (one
  definition of each key); `homePrefetch` imports only `homeQueries`.

**Must not change:** query keys, options, endpoints, what any page shows, the
dev proxy. The Render `VITE_API_BASE_URL` value is already set (the API origin).

## Build steps

- [x] **Step 1 - Preconnect plugin.** Done 2026-11-23: `src/utils/apiPreconnect.ts`
  (reuses `resolveApiBaseUrl`, returns the origin) with 3 Vitest cases;
  `vite.config.ts` reads `VITE_API_BASE_URL` through `loadEnv` and injects the
  link at the top of `<head>`. `tsc -b` clean. `VITE_API_BASE_URL=https://example.test`
  build: `<link rel="preconnect" href="https://example.test" crossorigin="">`;
  plain build: none. Pure helper `apiPreconnectTag(value)`
  (returns the `<link>` or nothing) with Vitest cases: unset, blank, trailing
  slash or path stripped to the origin, invalid value throws like
  `resolveApiBaseUrl`. *Done when:* tests pass; `VITE_API_BASE_URL=https://example.test npm run build`
  puts the link in `build/index.html` and a plain build does not.
- [x] **Step 2 - `homeQueries`.** Done 2026-11-23: the four builders moved
  verbatim to `src/hooks/homeQueries.ts`; `useNba`, `useNfl`, `useNhl` and
  `useTennisSlate` import and re-export them; `homePrefetch` and its test import
  only `homeQueries`. `tsc -b` clean, hook tests 50/50, Verify passed (web 1890,
  API 6635). Prefetch static graph (non-entry chunks): master 15 chunks, 31.1 KB;
  branch 9 chunks, 22.8 KB. `modelRankingQuery` (8.5 KB), `useTennisSlate`,
  `gameState` and the hook chunks are gone. **Not met as written:** `trackRecord`
  (1.3 KB) and `nflTrackRecord`'s code still load, through `api/nfl.ts`'s
  `rankingParams` import; the API modules' own utils (`nhlLineOnly`,
  `slatePeriod`, `format`) stay too. *Done when (as specced):* `tsc -b` and the hook tests pass (keys
  unchanged), and the built `homePrefetch` chunk's static imports no longer
  include `modelRankingQuery`, `nflTrackRecord` or `trackRecord`.
- [x] **Step 3 - Local A/B.** Done 2026-11-23: master `31bcf582` (A, :4173)
  against this branch (B, :4174), both built with
  `VITE_API_BASE_URL=http://127.0.0.1:8000`, one local API with CORS for both
  ports, one warm-up run each, then 12 Lighthouse 13.6 mobile runs in A B B A
  order. Medians (6 each):

  | | Score | FCP | LCP (sim.) | TBT | LCP (obs.) | Tennis request starts |
  |---|---|---|---|---|---|---|
  | A master | 66 | 2.27 s | 6.32 s | 376 ms | 716 ms | 317 ms |
  | B branch | 62 | 2.33 s | 6.31 s | 494 ms | 833 ms | 399 ms |

  **No measurable difference.** The spread follows TBT (286 to 1392 ms on the
  same build), which is host CPU noise. Two findings:
  1. The preconnect cannot show locally: a connection to `127.0.0.1` costs about
     nothing, and Lighthouse lists no preconnect candidate or preconnected
     origin in either build. Only the production runs can measure it.
  2. The lighter prefetch did not move the prefetch's start. In B every
     prefetch dependency had arrived by 130 ms, yet the tennis request started
     at about 300 ms, after `/ask/status` (250 ms), in A and B alike. The main
     thread (first render of the shell) gates the prefetch here, not its chunk
     graph. Production, with slower chunk loads, may still differ.

  Previously specced: production builds of `master` (A) and this branch
  (B), both with `VITE_API_BASE_URL=http://127.0.0.1:8000` so the API is a
  separate origin from the `localhost` page (Lighthouse simulates a new
  connection per origin), the dev API started with `CORS_ORIGINS` allowing both
  preview ports; 12 runs in A B B A order. *Done when:* the medians are
  recorded here and Verify passes.

## Verify

- Verify: `npm --prefix web run verify && cd api && python -m pytest`.
- After deploy (outside this fix): eight production Lighthouse runs.

## Post-deploy Lighthouse (2026-11-23)

Production after `38e8d8cb` deployed (the live `index.html` starts its head with
`<link rel="preconnect" href="https://sportapp-api-ftsf.onrender.com" crossorigin="">`).
Lighthouse 13.6 mobile, eight runs:

| Run | Score | FCP | LCP (sim.) | TBT | LCP (obs.) | Tennis request |
|---|---|---|---|---|---|---|
| 1 | 55 | 2.38 s | 5.68 s | 708 ms | 3.91 s | 906-3873 ms (cold API cache) |
| 2 | 83 | 2.06 s | 3.65 s | 248 ms | 856 ms | 482-560 ms |
| 3 | 74 | 2.07 s | 4.67 s | 312 ms | 843 ms | 486-565 ms |
| 4 | 62 | 2.41 s | 4.01 s | 1033 ms | 1.21 s | 851-930 ms |
| 5 | 74 | 2.08 s | 4.67 s | 318 ms | 923 ms | 515-591 ms |
| 6 | 80 | 2.10 s | 3.82 s | 322 ms | 921 ms | 452-532 ms |
| 7 | 71 | 2.14 s | 4.61 s | 424 ms | 881 ms | 458-536 ms |
| 8 | 72 | 2.15 s | 4.61 s | 395 ms | 843 ms | 476-569 ms |
| **Median** | **73** | **2.12 s** | **4.61 s** | **358 ms** | **901 ms** | **484-567 ms (79 ms)** |

Against run 25 (before, one run: score 83, LCP 3.82 s, observed 895 ms, tennis
request 475-829 ms):

- **The preconnect works.** Lighthouse lists the API origin under "Preconnected
  origins", and the first tennis request takes 79 ms (median) instead of 354 ms,
  so its data arrives about 260 ms sooner.
- **LCP did not move.** Observed LCP stays at about 900 ms: about 330 ms passes
  between the tennis data arriving and the card's paint, so the page is now
  waiting on rendering, not on data.
- **The prefetch still starts at about 480 ms,** as before, matching the local
  A/B finding that the first render, not the chunk graph, gates it.
- Scores ran 62-83 outside the cold run 1, and run 25 was a single good run, so
  the lower median is not read as a regression.

## Out of scope

- The API's own response time, HTTP caching, `dns-prefetch` fallbacks, other
  origins (Google Fonts is gone; `espncdn.com` logos are below the fold).

## Notes for the AI

- Vite reads `VITE_*` env at build time; Render's static site build sets
  `VITE_API_BASE_URL`, so the link only appears in that build.
- Keep the local A/B fair: same API process and warm caches for both builds.

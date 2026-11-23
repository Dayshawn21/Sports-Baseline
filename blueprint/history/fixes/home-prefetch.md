# Fix: Start the home page's data and chunk at startup

**Type:** Fix
**Branch:** `fix/home-prefetch` (worktree `.claude/worktrees/sharp-elbakyan-f84efc`, cut from `master` at `dbb69de5`)
**Status:** completed 2026-11-23 (step 3, the post-deploy Lighthouse runs, reported after the push)

## The problem

The home page's LCP is the tennis card's next-match link (`a.home-card__match`),
drawn when `/tennis/predictions/today` answers. Lighthouse 13.6 (mobile) puts
TTFB at 0.15-0.18 s and the element's render delay at 2.8-3.8 s; LCP 4.6-7.8 s
over four runs on 2026-11-23 (scores 34-55).

The tennis endpoint is not slow (about 0.1 s in the trace, 0.26-0.54 s cold
alone). Its request starts late. Observed timeline of the cleanest run:
document 0-161 ms, `index` and `react-vendor` 237-316 ms, then the lazy
`HomePage` chunk (`App.tsx:27`) and about 45 chunks it imports 544-660 ms, and
the **first data request at 916 ms**, because every home query fires from the
hooks in `useHomeData` after React renders `HomePage`. Under simulated mobile
throttling each of those serial rounds costs a round trip plus 4x CPU, so the
1.1 s observed LCP becomes about 4.6 s.

## The fix

At startup, when the page opens on the home route, start the home page's
queries and its chunk together, before React renders anything:

- `hooks/homePrefetch.ts`: `isHomeRoute(hash)` (pure: `''`, `'#'`, `'#/'`, with
  or without a query string) and `prefetchHome(queryClient, now)`, which calls
  `queryClient.prefetchQuery` with the **same query options the hooks use**:
  tennis today for each default slate date first, then `nflCurrentWeekQuery`,
  `nbaSlateQuery(null)`, `nhlSlateQuery(null)`. Shared keys mean the hooks
  find the requests in flight and never send a second one.
- `useTennisSlate`: its per-date options move into an exported
  `tennisSlateQuery(kind, fetchPage, date, tour)` that both the hook and
  `prefetchHome` use (load-bearing: one key definition).
- `App.tsx`: the home route's `lazy` import becomes an exported
  `loadHomePage`; `main.tsx` calls it alongside `prefetchHome`, so the chunk
  wave overlaps the fetches instead of preceding them.

**Must not change:** query keys, `staleTime`, retry, any response or endpoint,
other routes (no prefetch off the home route), what the home page renders.
Prefetch failures stay silent; the hooks surface errors as today.

**Trade-off:** the entry bundle gains the small query-option modules it imports
(a few KB); measure it in the build output.

## Build steps

- [x] **Step 1 - Shared tennis options and `homePrefetch`.** Done 2026-11-23:
  11 new Vitest cases in `hooks/homePrefetch.test.ts`; the four hook suites
  pass (46) and `tsc -b` is clean. Nothing calls `prefetchHome` yet. Extract
  `tennisSlateQuery`; add `isHomeRoute` and `prefetchHome`. Vitest: route
  matching; with fetchers mocked, `prefetchHome` then the hooks' options via
  `fetchQuery` call each fetcher once per key (no duplicate requests), and the
  tennis keys equal `useTennisSlate`'s for the default dates. *Done when:* tests
  pass.
- [x] **Step 2 - Wire startup.** Done 2026-11-23: a static import of
  `homePrefetch` grew the entry 365.9 to 394.4 KB raw (+8.4 KB gzip, the hook
  modules), so `main.tsx` imports it on demand and `isHomeRoute` moved to
  `utils/homeRoute.ts`: entry 366.3 KB raw / 123.5 KB gzip (+0.15 KB gzip).
  Verify passed (1,887 web tests and build; API unchanged). Local production
  preview: the five prefetched queries start at 165 ms, the page's other
  queries at 448 ms, no request sent twice; a cold `#/nhl` load fetches no
  home chunk or home query. Planned: `loadHomePage` in `App.tsx`; `main.tsx` calls
  `prefetchHome` and `loadHomePage` when `isHomeRoute(location.hash)`. *Done
  when:* Verify passes; in a local production preview the home page's data
  requests start before or alongside the `HomePage` chunk (Network timings),
  each sent once, and other routes send none at startup; entry bundle size
  change noted.
- [ ] **Step 3 - Measure after deploy (no code).** Open at `/complete`
  (2026-11-23): it needs the deploy, so the runs are reported after the push. Four or more Lighthouse
  13.6 mobile runs; compare medians with the 2026-11-23 01:21 runs (median
  score 46, LCP 5.03 s). *Done when:* the medians are recorded in the archive.

## Verify

- Verify: `npm --prefix web run verify && cd api && python -m pytest`.
- Local preview (`web-preview`): Network shows `/tennis/predictions/today`
  starting before `HomePage-*.js` finishes; no duplicate data requests.

## Out of scope

- `react-vendor`/`index` evaluation cost (TBT), bundle splitting.
- CLS (0.131 to 0.16), the tennis endpoints themselves, other pages.

## Notes for the AI

- Read `web/src/main.tsx`, `App.tsx`, `hooks/useHomeData.ts`,
  `hooks/useTennisSlate.ts`, `hooks/useTennisToday.ts`, `hooks/useNfl.ts`,
  `hooks/useNba.ts`, `hooks/useNhl.ts` first.
- `HashRouter`: the route is in `location.hash`, not the path.
- Lighthouse runs vary a lot (34-55 on one build): never judge on one run.

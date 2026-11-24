# Fix: Render the home page without the route fallback on first load

**Type:** Fix
**Branch:** `fix/home-first-render` (worktree `.claude/worktrees/sharp-elbakyan-f84efc`, cut from `master` at `dccf6290`)
**Status:** complete (2026-11-23)

## The problem

On a fresh load of the home page, React holds the page back for about 300 ms
after its code and data are ready. Debug note: `home-render-gap-debug.md`
(shared notes, 2026-11-23).

- `App.tsx` renders the routes in `<Suspense fallback={<RouteFallback />}>`, and
  the home route is `lazy(loadHomePage)`. The first render always suspends on
  it and commits `RouteFallback`.
- React 19.2.4 then delays revealing the boundary's content until 300 ms after
  that fallback commit (`globalMostRecentFallbackTime + 300` in
  `react-dom-client.production.js`, scheduled through `commitRootWhenReady`).
- Warm production trace (score 83, observed LCP 986 ms): the `HomePage` chunk
  had loaded by 461 ms and the prefetched data by 700 ms, React's reveal timer
  fired at 821 ms, `HomePage` mounted at about 825 ms, and LCP was 986 ms. Run 3
  of the post-deploy runs: shell at 439 ms, home queries at 732 ms (+293), LCP
  843 ms.

## The fix

- `App.tsx` keeps a module-level slot for an already-loaded home page:
  `preloadHomePage()` awaits `loadHomePage()` and stores its `default`. The `/`
  route renders that component directly when it is set, and the `lazy` one
  otherwise (a later client-side navigation to `/` from another route, before
  any home load).
- `main.tsx`, on the home route only (`isHomeRoute`), starts the prefetch as now,
  then calls `root.render(...)` after `preloadHomePage()` settles. A failed chunk
  load is caught and the app renders anyway: the `lazy` route then retries and
  shows the existing error path. Other routes render at once, as now.
- The home page's first render therefore never commits `RouteFallback`, so
  there is no throttle. Cost: the first paint on `/` waits for the `HomePage`
  chunk, which loads in parallel with the entry (461 ms against the shell's
  first commit at about 530 ms in the trace), so FCP may move by a few tens of
  ms either way.

**Must not change:** what any page shows, other routes' lazy loading and
fallbacks, the home prefetch, query keys, `StrictMode`, the entry bundle's size
beyond a few hundred bytes (no static import of `HomePage`).

## Build steps

- [x] **Step 1 - Preloaded home route.** Done 2026-11-23: `tsc -b` clean; entry
  chunk 119,567 B gzip against master's 119,560 (+7 B), no `home-card` code in
  it. Playwright `MutationObserver` on local production previews (same API):
  master `/` showed the fallback at 197 / 114 ms and the home page at 511 / 418 ms
  (+314 / +304); the branch's `/` never mounted the fallback and showed the home
  page at 189 / 167 ms. The branch's `/nfl` still showed its fallback (141 ms),
  and a click to Home from `/nfl` rendered the 4 home cards. Specced:
  `preloadHomePage` and the route switch in
  `App.tsx`; `main.tsx` waits for it on the home route only. *Done when:*
  `tsc -b` passes; the build's entry chunk stays within +0.3 KB gzip of master
  and does not contain `HomePage`'s code; in the local production preview, a
  load of `/` never shows `RouteFallback` (checked with a Playwright
  `MutationObserver` init script that records whether `.page-shell .nfl-slate`
  or the skeleton ever mounts before `.home-card`), while `/nfl` still shows its
  fallback; a direct load of `/nfl` followed by a click to Home still renders
  the home page.
- [x] **Step 2 - Local A/B.** Done 2026-11-23: master `dccf6290` (A, :4173) against
  this branch (B, :4174), both built with `VITE_API_BASE_URL=http://127.0.0.1:8000`,
  one local API with CORS for both ports, one warm-up each, then 12 Lighthouse 13.6
  mobile runs in A B B A order. Medians (6 each):

  | | Score | FCP | LCP (sim.) | TBT | LCP (obs.) | Tennis request | Home mounts |
  |---|---|---|---|---|---|---|---|
  | A master | 70 | 2.18 s | 6.34 s | 283 ms | 666 ms | 277 ms | 567 ms |
  | B branch | 86 | 2.65 s | 2.65 s | 302 ms | 478 ms | 165 ms | 347 ms |

  Every B run beat every A run on score (85-89 against 56-71), simulated LCP and
  observed LCP. The home page mounts 220 ms sooner, and the simulated LCP now
  equals FCP (the card paints with the first paint). Trade-off: simulated FCP is
  0.46 s later, because the first paint now waits for the `HomePage` chunk instead
  of drawing the placeholder; observed FCP is not worse in the Playwright check
  (home at 167-189 ms against the placeholder at 114-197 ms). Verify passed (web
  1890, API 6661). Specced: production builds of `master` (A) and this branch (B)
  against one local API (`VITE_API_BASE_URL=http://127.0.0.1:8000`, CORS for both
  preview ports), one warm-up run each, then 12 Lighthouse runs in A B B A order.
  Record the median score, FCP, LCP (simulated and observed), and when
  `/tennis/props/prizepicks` starts (the home page's mount). *Done when:* the
  medians are recorded here and Verify passes.

## Verify

- Verify: `npm --prefix web run verify && cd api && python -m pytest`.
- After deploy (outside this fix): eight production Lighthouse runs, compared
  with the preconnect's eight (median score 73, LCP 4.61 s, observed 901 ms).

## Post-deploy Lighthouse (2026-11-23)

Production after `6e65ba59` deployed (the live entry `index-CrpYte7K.js` ends
with the new boot: `preloadHomePage().catch(...).finally(render)`). Lighthouse
13.6 mobile, eight runs. "Home mounts" is the start of the home page's first
own query, `/tennis/props/prizepicks`.

| Run | Score | FCP | LCP (sim.) | TBT | LCP (obs.) | Home mounts |
|---|---|---|---|---|---|---|
| 1 | 54 | 2.59 s | 5.44 s | 742 ms | 2.75 s | 1254 ms (cold API cache) |
| 2 | 84 | 2.04 s | 3.75 s | 209 ms | 663 ms | 496 ms |
| 3 | 83 | 2.03 s | 3.66 s | 142 ms | 562 ms | 470 ms |
| 4 | 86 | 2.04 s | 3.74 s | 151 ms | 636 ms | 509 ms |
| 5 | 83 | 2.11 s | 3.63 s | 273 ms | 645 ms | 522 ms |
| 6 | 83 | 2.10 s | 3.72 s | 240 ms | 680 ms | 539 ms |
| 7 | 79 | 2.14 s | 3.65 s | 356 ms | 706 ms | 562 ms |
| 8 | 85 | 2.07 s | 3.67 s | 185 ms | 590 ms | 471 ms |
| **Median** | **83** | **2.08 s** | **3.70 s** | **224 ms** | **654 ms** | **515 ms** |

Against the preconnect's eight (`api-preconnect.md`: median score 73, FCP
2.12 s, LCP 4.61 s, TBT 358 ms, observed LCP 901 ms, home mounting at about
730-830 ms):

- **Score 73 to 83, simulated LCP 4.61 to 3.70 s, observed LCP 901 to 654 ms.**
  The home page mounts about 250 ms sooner; React's 300 ms reveal hold is gone.
- **Steadier:** outside the cold run 1, scores ran 79-86, against 62-83.
- **No FCP cost in production** (2.08 s against 2.12 s), unlike the local A/B's
  0.46 s.
- What remains of the simulated LCP is mostly loading and running the entry JS
  and the shell's first render under mobile throttling.

## Testing

No new pure logic: the change is boot order and one component choice, which the
standards leave to running-app evidence (step 1's Playwright check, step 2's
A/B), not unit tests.

## Out of scope

- The shell's 120 ms first-render task (432-553 ms in the trace) that also holds
  the prefetch; the home page's own render cost; other routes' fallbacks.

## Notes for the AI

- Do not rely on preloading the `lazy` module alone: a fresh `import()` promise is
  pending at first render, so `lazy` may still suspend once and commit the
  fallback. Render the loaded component itself.
- Keep `homePrefetch` starting before the wait, so the data requests are not
  delayed by the chunk.

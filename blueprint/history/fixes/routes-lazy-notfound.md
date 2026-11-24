# Current Feature

## Route splitting, not-found route, reduced motion

**Type:** Fix
**Branch:** `fix/routes-lazy-notfound`
**Status:** Completed 2026-11-07. Web Verify passed (83 files / 1,250 tests and build). API pytest locally: 5,935 passed, 2 failed on CRLF registry CSVs in this worktree (F-42, unrelated); CI on PR #6 green (`verify`, `secret-scan`).
**Source:** Impeccable UI audit, `/impeccable optimize` (P1) and `/impeccable harden` (P2).

### The problem

- Every page was imported eagerly in `App.tsx` and `routes/sportPages.tsx`,
  so the app shipped one 1,672 KB JS bundle (510.5 KB gzip) and one 156 KB CSS
  file.
- An unknown hash route such as `#/nfl/props` rendered a blank page, and
  `documentTitle` titled it "NFL props" because any lowercase segment under a
  sport counted as a detail kind.
- Ant Design animations ignored `prefers-reduced-motion`.

### The fix

1. **Route splitting.** All pages in `App.tsx` and `sportPages.tsx` are
   `React.lazy`, inside one `Suspense` with the shared `LoadingState`. The
   shell (header, nav, drawer, Ask launcher) stays eager.
2. **Not found.** `Route path="*"` renders `NotFoundPage`: `PageHead` titled
   "Page not found" with the missing path and a link home; it registers the tab
   title "Page not found - Lineform". `SPORTS` now lists each sport's detail
   kinds, and `documentTitle` names only those.
3. **Reduced motion.** `usePrefersReducedMotion` (`matchMedia` via
   `useSyncExternalStore`) feeds `appAntdTheme(reducedMotion)`, which sets
   `token.motion: false`.

### Done when

- [x] Verify passes (web Verify; API pytest per the note above, CI green).
- [x] Unknown hash routes show the not-found page: checked in a `vite preview`
  of the production build at `#/nfl/props` (h1, link to `#/`, tab title).
- [x] Bundle numbers reported: entry JS 687.3 KB (226.2 KB gzip), entry CSS
  25.6 KB (6.0 KB gzip); largest lazy chunk `AdminPage` 308 KB (95 KB gzip).
- [x] Tests: unknown sport paths in `sportNav.test.ts`, routed detail kinds
  match `SPORTS` in `sportPages.test.ts`, `antdTheme.test.ts`.

### Not verified

- Reduced motion in a browser (the preview tool cannot emulate the media
  query); covered by the unit test only.

### How to try it

1. Open `#/nfl/props`: "Page not found" with a link home; the tab reads
   "Page not found - Lineform".
2. In DevTools Network, navigate Home to How it works: `HowItWorksPage-*.js`
   loads only then.

# Fix: Skeleton while a slate or board page's code loads

**Type:** Fix
**Status:** complete (2026-11-13)
**Follows:** 68c (skeleton loaders)

## Problem

Every page is lazy-loaded, and `App.tsx` wraps the routes in one
`<Suspense fallback={<LoadingState />}>`. On a first visit to a slate or prop
board, the spinner shows while the page's code downloads, and the 68c skeleton
only appears afterwards, while the data loads. On the hosted site the spinner
phase is the part users see, so 68c reads as not working.

## Fix

- A pure helper `routeLoadingShape(pathname)` in `web/src/utils/routeLoading.ts`
  returns `'slate'` for a sport's slate path, `'board'` for its props path, and
  `'spinner'` for everything else (game, player, model, home, tools, admin),
  read through the existing `sportViewForPath`.
- A small `RouteFallback` component (in `App.tsx`) reads the location and renders
  a `TableSkeleton` inside the page shell for slates and boards, and the
  existing `LoadingState` otherwise.

## Out of scope

- Pages that keep the spinner by 68c's decision, and in-panel loaders.
- Preloading page chunks.

## Steps

- [x] **Step 1 - Helper and fallback** - the helper with `routeLoading.test.ts`
  and the `RouteFallback` swap. *Done when:* the test covers each sport's slate
  and props path, a game or player path, the model page, home and an unknown
  path; with a page chunk held open in Playwright, `/nba` and `/nba/props` show
  `.table-skeleton` and no `.ant-spin`, and `/nba/game/<id>` still shows the
  spinner; Verify passes.

## Outcome

Completed 2026-11-13 on `fix/route-fallback-skeleton`, web only.

- `routeLoadingShape` (4 Vitest cases) maps slate paths to `'slate'`, props paths
  to `'board'` and everything else to `'spinner'`; `RouteFallback` in `App.tsx`
  is the app-wide `Suspense` fallback and renders a `TableSkeleton` in the page
  shell for the first two.
- Proof (Playwright, the page's chunk request held open after a full reload):
  `/nba` and `/nba/props` show the skeleton and no spinner at 1440 and 375 (77px
  and 175px stacked rows at 375), `/nba/game/21149` keeps the spinner, and
  releasing the chunk renders the page. Screenshots:
  `blueprint/reference/68/route-fallback-*.png`.
- Known: the code-loading skeleton has no page head, so it shifts down by the
  head's height when the page arrives.
- Verify: `npm --prefix web run verify` (115 files, 1,827 tests, build) and
  `python -m pytest` (6,433 passed).

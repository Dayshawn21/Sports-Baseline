# Feature: View transitions

**From build-plan:** feature 68b (under 68. Interface polish)
**Status:** complete (2026-11-13)
**Branch:** `feature/68b-view-transitions`

## Goal

A short crossfade when moving between sport pages (slate, props, model, game,
match and player), through the View Transitions API. Display only: skipped
under `prefers-reduced-motion`, skipped where the browser has no
`document.startViewTransition`, and a new navigation cuts a running transition
short instead of waiting behind it.

## In scope

- A pure helper `shouldViewTransition` that decides, from the old and new
  path, the navigation type and the two environment flags, whether a change
  gets a transition. Tested.
- A hook `useViewTransitionLocation` that holds the location `<Routes>`
  renders, and moves it forward inside `document.startViewTransition` when the
  helper says yes. It skips a running transition before starting the next one.
- `App.tsx` passes that location to `<Routes location={...}>`. Every way of
  navigating (links, `navigate()`, the keyboard shortcuts, the phone menu,
  the slate command field) goes through one place, so none of them need
  changes.
- CSS in `src/index.css`: a short crossfade (about 180ms) on the root
  snapshots, and `animation: none` on them under `prefers-reduced-motion` as a
  second guard.

## Out of scope

- Shared-element morphs (a row growing into the game hero). Plain crossfade only.
- Back and forward (`POP`). Phone browsers draw their own swipe-back
  animation, and Back restores the opened row (`useRestoreOpenedRow`); a
  crossfade on top would double up. Back stays instant.
- Query-string-only changes (filters, tabs, periods kept in the URL). Same
  path means no transition, so filter clicks never fade.
- Pages outside a sport (home, tools, parlays, how it works, admin, not
  found). A transition needs both ends inside a sport.
- Skeleton loaders (68c) and drawer swipes (68d).
- Any API, model, rank, sort, version or gray-color change.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Decision helper** - `web/src/utils/viewTransition.ts` exports
  `shouldViewTransition({ from, to, navigationType, supported, reducedMotion })`
  returning a boolean: true only when the browser supports it, motion is not
  reduced, the navigation is not `POP`, the pathname changed, and both
  pathnames belong to a sport (`sportForPath` is not null). Plus
  `viewTransitionsSupported(doc)` reading whether `startViewTransition` is a
  function. *Done when:* `viewTransition.test.ts` covers each skip reason
  (unsupported, reduced motion, POP, same path with a different search, a
  non-sport end) and the yes cases (slate to game, game to player, tennis
  slate to NFL model, slate to props), and `npm run test` passes.
- [x] **Step 2 - Hook and wiring** - `web/src/hooks/useViewTransitionLocation.ts`:
  keeps the shown location in state and the latest target in a ref. On a
  location change (layout effect) it skips any running transition, then either
  shows the new location at once or calls
  `document.startViewTransition(() => flushSync(() => setShown(latest.current)))`.
  Every update callback reads the ref, so a skipped transition's late callback
  can never put an older page back. `App.tsx` renders
  `<Routes location={shownLocation}>`. *Done when:* `npm run build` passes; in
  the browser pane, clicking from a slate to a game and to a player renders
  the right page; a spy on `document.startViewTransition` records one call per
  sport-page click and none for a filter change, a Back, or a trip to Tools;
  firing two navigations back to back ends on the second page with the first
  transition's `finished` settled (skipped).
- [x] **Step 3 - Crossfade CSS and reduced-motion proof** - in `src/index.css`,
  `::view-transition-old(root)` and `::view-transition-new(root)` get a 180ms
  ease duration, and an `@media (prefers-reduced-motion: reduce)` block sets
  them to `animation: none`. *Done when:* computed style read during a
  transition (`getComputedStyle(document.documentElement, '::view-transition-new(root)')`)
  shows the 180ms duration; with the pane emulating reduced motion (or the
  hook's input forced), the spy records zero calls on a sport-page click and
  the page still changes; Verify passes.

## Files / areas

- `web/src/utils/viewTransition.ts` (new) and `viewTransition.test.ts` (new)
- `web/src/hooks/useViewTransitionLocation.ts` (new)
- `web/src/App.tsx` (one hook call, one `location` prop)
- `web/src/index.css` (the view-transition pseudo-element rules)

Not touched: 68c's `TableSkeleton`, `utils/skeleton.ts`, the slate and prop
board loading branches.

## Data / contracts

- None stored or served. The helper's input shape is local to this feature:
  `{ from: string, to: string, navigationType: 'POP' | 'PUSH' | 'REPLACE', supported: boolean, reducedMotion: boolean }`.

## Testing

- Test gate on: `viewTransition.test.ts` covers the helper (Step 1). The hook
  and CSS are integration and ride on browser evidence.
- The browser pane pauses animations while hidden (seen in 68a), so the proof
  is the API being called (a spy wrapping `document.startViewTransition`) and
  computed styles, not watching the fade.
- Final gate: `npm --prefix web run verify && cd api && python -m pytest`
  (API venv).

## Notes for the AI

- The app uses `HashRouter`, so React Router's `viewTransition` prop (data
  routers only) is unavailable; that is why the hook drives
  `document.startViewTransition` itself.
- `<Routes location>` gives descendants that location through context, so
  pages read the shown location, not the one a frame ahead. The `Nav` keeps
  the real `useLocation()`; it updates before the old snapshot is taken, so
  the header looks the same in both snapshots and does not visibly fade.
- Lazy pages suspend inside the `flushSync`; the crossfade then lands on the
  existing `LoadingState` fallback (later the 68c skeleton). That is expected.
- Read reduced motion through `usePrefersReducedMotion`, and feature-detect
  with `typeof document.startViewTransition === 'function'`; check whether
  TypeScript 5.9's DOM lib already types it before adding any declaration.
- No em dashes in new comments or docs.
- 68c edits `blueprint/build-plan.md` and `project-overview.md` too; whichever
  merges second needs a small merge there.

## Outcome

Completed 2026-11-13 on `feature/68b-view-transitions`.

- Step 3 also sets `::view-transition-group(root)` to 180ms: Chrome's default
  250ms group kept the transition overlay, which takes clicks, open longer than
  the fade.
- Evidence (headless Playwright, since the hidden browser pane draws no frames
  and a transition never reaches `ready` there): slate to game, game to player,
  player to model and slate to props each made one `startViewTransition` call
  with old, new and group animations at 180ms, finishing 236-437ms after the
  click. Under emulated `prefers-reduced-motion: reduce`, two sport-page clicks
  made zero calls and both pages changed. In the browser pane, Back, home and
  setting the hash directly (all POP or non-sport) made zero calls, and a
  second click during a fade stretched to 5s ended the first at the moment the
  second began (skipped, not queued), landing on the second page.
- Verify: `npm --prefix web run verify` (112 files, 1806 tests, build) and
  `python -m pytest` in `api/` (6433 passed; run with CI's placeholder
  `DATABASE_URL=postgresql://localhost/ci` because the worktree has no
  `api/app/.env`).

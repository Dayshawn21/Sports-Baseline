# Feature: Swipe-to-dismiss drawers

**From build-plan:** feature 68d (under 68. Interface polish)
**Status:** complete (2026-11-13)

## Goal

On a touch screen, dragging a drawer toward the edge it came from closes it,
the way native sheets do: the phone menu and the Ask drawer slide off to the
right, and the sport switcher slides down. The panel follows the finger. A
release that is far or fast enough closes it; anything less springs back. Taps,
scrolling and typing inside the drawers keep working. Display only.

## In scope

- A pure, tested helper `web/src/utils/swipeDismiss.ts`:
  - `swipeAxisLock(dx, dy, direction, slop)`: decides once per gesture whether
    the finger is moving along the dismiss axis in the dismiss direction
    ("along"), across it or backwards ("across"), or has not passed the slop yet
    ("pending").
  - `shouldDismiss({ distance, velocity, size })`: true when the release is past
    a share of the panel's size, or faster than a speed floor and past a minimum
    distance; false for any release against the dismiss direction.
- A hook `web/src/hooks/useSwipeToDismiss.ts` that takes the drawer panel element
  (from Ant Design's `panelRef`), the dismiss direction (`'right' | 'down'`),
  `open`, `enabled` and `onDismiss`, and listens to pointer events on the panel:
  - ignores mouse and pen, a second finger, and gestures that start in an
    `input`, `textarea`, `select` or `[contenteditable]`, or (for right swipes) in
    an element that scrolls horizontally
  - lets vertical scrolling win once the lock says "across"
  - for a down swipe, engages only when the panel body is scrolled to the top
  - while engaged, moves the drawer wrapper with an inline `transform` and fades
    the mask in step, with no transition
  - on release, a dismiss slides the wrapper the rest of the way off and then
    calls `onDismiss`; anything else springs back
  - inline styles are cleared once the drawer has closed or settled, and when
    `open` turns false mid-drag (closed by X, mask or Escape)
  - under `prefers-reduced-motion` the finger still moves the panel (direct
    manipulation), but the slide-off and spring-back are instant
- Wired into the three drawers through `panelRef`:
  - `App.tsx` phone menu (right)
  - `AskDrawer` (right, enabled only when `isMobile`)
  - `MobileSportSwitcher` (down)

## Out of scope

- Mouse and trackpad drags. The desktop Ask drawer (440px) keeps closing by its
  X, the mask and Escape only.
- Edge swipes to open a drawer.
- Other overlays: modals, popovers, the shortcuts panel, select dropdowns.
- Any change to what the drawers contain or how they open.
- Haptics.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Gesture helpers** - `swipeDismiss.ts` with `swipeAxisLock` and
  `shouldDismiss`, plus `swipeDismiss.test.ts`. No UI change. *Done when:* the
  tests cover:
  - "pending" inside the slop
  - "along" for a rightward (right) or downward (down) move past the slop
  - "across" for a mostly perpendicular move, and for a move against the
    dismiss direction
  - dismiss past the distance share
  - dismiss on a fast flick above the minimum distance
  - no dismiss on a fast flick below the minimum, a slow short drag, or a
    backward release
  - a zero-size panel never divides by zero

  Verify passes.
- [x] **Step 2 - Hook on the sport switcher** - `useSwipeToDismiss` and its use in
  `MobileSportSwitcher` (down). *Done when:* in the browser pane with the mobile
  preset, synthetic `PointerEvent` sequences (`pointerType: 'touch'`) on the
  sheet show:
  - while dragging, the wrapper's inline `transform` follows the finger
  - a short slow drag springs back, the sheet stays open, and the inline
    `transform` and `transition` are gone afterwards
  - a drag past the threshold closes it (the switcher button's `aria-expanded`
    turns false)
  - reopening after a swipe close shows the sheet in its normal place, with no
    leftover offset
  - a tap on a sport row still navigates
  - the same drag with `pointerType: 'mouse'` does nothing

  Verify passes.
- [x] **Step 3 - Phone menu and Ask drawer** - wire the hook into `App.tsx`'s
  phone menu and `AskDrawer` (right). *Done when:*
  - a rightward swipe closes each one
  - a vertical drag in Ask's turns list does not move the panel
  - a swipe that starts in the Ask textarea does not move the panel
  - a tap on a menu item still navigates and closes the menu
  - at desktop width the Ask drawer ignores touch swipes
  - after a swipe close, Ask's `afterOpenChange` reset still runs (the draft
    clears as it does after an X close), and the next open focuses the input

  Verify passes.

## Files / areas

- New: `web/src/utils/swipeDismiss.ts`, `web/src/utils/swipeDismiss.test.ts`,
  `web/src/hooks/useSwipeToDismiss.ts`
- Changed: `web/src/components/shared/MobileSportSwitcher.tsx`,
  `web/src/App.tsx`, `web/src/components/ask/AskDrawer.tsx`
- Possibly `web/src/index.css`, for `touch-action` on a panel if the browser
  claims the gesture for scrolling before the lock decides

## Data / contracts

- No API, type or stored-shape change.
- Helper (local, not load-bearing):
  - `swipeAxisLock(dx: number, dy: number, direction: 'right' | 'down', slop?: number): 'pending' | 'along' | 'across'`
  - `shouldDismiss(input: { distance: number, velocity: number, size: number }): boolean`
  - named constants for the distance share (start near 35% of the panel), the
    speed floor (near 0.5 px/ms) and its minimum distance (near 24px), tuned at
    375x812 in Step 2
- Hook (local): `useSwipeToDismiss(panel: HTMLElement | null, options: { direction, open, enabled?, onDismiss })`.
  `panelRef` points at `.ant-drawer-content`; the hook moves its parent
  `.ant-drawer-content-wrapper`, the element Ant Design's open and close motion
  moves.

## Testing

- Vitest: `swipeDismiss.test.ts` covers both helpers (Step 1), the logic where
  a wrong answer is possible.
- The hook and wiring are UI. Prove them in the browser pane with the mobile
  preset by dispatching `PointerEvent`s and reading `aria-expanded`, inline and
  computed styles, and the URL. The pane pauses animations while hidden (seen in
  68a), so read state from the DOM rather than watching it.
- An emulator cannot prove real-phone feel (thresholds, scroll conflicts).
  Record that limit, and give a manual try path on a phone over the local network.

## Notes for the AI

- Display only: no navigation, data, rank, color or version change.
- Use pointer events, not touch events. Call `setPointerCapture` once engaged so
  the gesture survives the finger leaving the panel; wrap it in try/catch, since
  synthetic test pointers may not be capturable. Call `preventDefault` only after
  the lock says "along", never on `pointerdown`, or taps and scrolling break.
- Ant Design animates the wrapper with motion classes. An inline `transform` left
  on it would override the close animation and could leave the next open offset,
  so always clear inline styles after close or settle, and test open, swipe
  close, open.
- Ask is full width on phones, so its swipe crosses the whole panel; its turns
  list scrolls vertically, which the lock must leave alone.
- The sport switcher is `placement="bottom"` with `height="auto"`. It normally
  does not scroll, but keep the scroll-at-top rule for when it does.
- `usePrefersReducedMotion` already exists in `web/src/hooks/`.
- Escape, the X button and the mask click must keep working unchanged.

## Outcome

Completed 2026-11-13 on `feature/68d-swipe-dismiss-drawers`, web only, no API or model change.

- `swipeDismiss.ts` holds the pure gesture rules (12 Vitest cases): a 10px slop,
  an axis lock that needs 1.2x more travel along the dismiss axis than across it,
  and a release that closes past 35% of the panel or on a flick of at least
  0.5 px/ms over 24px, never on a backward release or a flick back.
- `useSwipeToDismiss` takes the panel from Ant Design's `panelRef`, follows touch
  pointers only, sets `touch-action` so the browser keeps the cross-axis scroll,
  skips gestures that start in inputs (and, for right swipes, in sideways
  scrollers), moves the wrapper and fades the mask, slides off over 200ms then
  closes, or springs back. Inline styles stay until Ant Design's close motion has
  finished (400ms) and are cleared before the next open paints. Under reduced
  motion the finger still drags; the slide-off and spring-back are instant.
- Wired into the sport switcher (down), the phone menu (right) and Ask (right,
  phones only; a swipe close stops a running answer like the X does).
- Proof (Playwright, synthetic touch pointers at 375x812): short slow drag springs
  back and clears, 200px drag and 40px flick close, mouse drags ignored, reopen
  shows no offset, taps on rows and menu items navigate, vertical drags in the
  menu and Ask's answers and drags from the Ask textarea leave the panel alone,
  Ask at 1280px ignores swipes, reduced motion closes instantly.
- Spec correction: closing Ask by X keeps the typed draft; a swipe close keeps it
  the same way.
- Not proven: real-phone feel (thresholds, scroll competition). Try path: run the
  web dev server with `--host`, open the LAN address on a phone, swipe each drawer.
- Verify: `npm --prefix web run verify` (114 files, 1,823 tests, build) and
  `python -m pytest` (6,433 passed).

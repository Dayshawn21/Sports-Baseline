# Fix: Bankroll Builder page clean-up (F-70 reopen)

**Type:** Fix
**Fixes:** F-70
**Branch:** `fix/parlays-page-cleanup`
**Completed:** 2026-11-18. Merged to master by PR at the user's request; Verify passed (1846 web tests, build, 6553 API tests).

### The problem

The 2026-11-18 re-review reopened F-70. The first repair moved the page onto
`PageHead` and split out its subcomponents, but `web/src/pages/ParlaysPage.tsx`
still has banner and narration comments (`:37,81,87,97,108,119`), an empty
fragment around the toolbar (`:38-79`) and an IIFE inside the JSX
(`:88-132`). The moved components in `components/tennis/parlays/` carry
what-comments (`{/* Rank */}`, `{/* Row 1: ... */}`).

### The fix

- A pure `splitByTour(data)` in `web/src/utils/bankrollTours.ts` returns the
  main-tour and Challenger singles and parlays, with tests. The page computes
  it before `return` instead of inside an IIFE.
- Delete the empty fragment and every what-comment in the page and the five
  parlay components.

No visible change: same sections, order, filters and empty state. Stays inside
`web/`.

### Build steps

- [x] **Step 1 - split helper and page.** Done when: `ParlaysPage.tsx` has no
  JSX comments, fragment or IIFE, `splitByTour` has tests (ATP/WTA vs
  Challenger, case, a mixed-tour parlay counted as Challenger), and Verify
  passes.
- [x] **Step 2 - component comments.** Done when: no `{/* */}` comment remains
  in `components/tennis/parlays/`, Verify passes, and the page renders the
  same sections in the app.

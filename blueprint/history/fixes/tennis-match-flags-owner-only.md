# Fix: hide quality flags from visitors on the tennis match page

**Type:** Fix

## The problem

38c1 made tennis quality flags an owner-only diagnostic: the slate shows them
only when `useAdminView()` is true (signed in with the admin key, or a Vite dev
build). The match page (32a) never got the same rule, so every visitor sees the
flag chips (`market stale`, `elo unreliable` and so on) under "Where the number
comes from" (`MatchComponents`,
`web/src/components/tennis/match/MatchComponents.tsx`). It is the only place on
the tennis detail pages that renders them.

## The fix

Display only. No probability, weight, flag computation or API response
changes.

- In `MatchComponents`, read `useAdminView()` (`web/src/hooks/useAdmin.ts`) and
  render the `.tennis-match-flags` row only when it is true. This is the same
  hook and the same rule as the slate.
- **Must not change:** the component rows, the weights or "coef" column, the
  flag tooltips the owner sees, and the slate's own flag handling.

## Build steps

- [x] **1. Gate the match page's flags on the owner view.** **Done when** a
  production build opened as a visitor (not signed in) shows no flag chips on
  `/tennis/match/:matchId`, while the dev build or a signed-in owner still sees
  them with their tooltips. `npm run build` passes.

## Verify

- **Owner view:** `npm run dev`, open a match whose prediction carries flags
  (for example a stale-market match). The chips and their tooltips still
  show, because a dev build is the owner's view.
- **Visitor view:** run a production build with `VITE_API_BASE_URL` pointed at
  the local API, open the same match without signing in, and confirm the flag
  row is gone. Once deployed, the live demo shows the same thing.
- Run the Verify command: `npm --prefix web run verify && cd api && python -m pytest`.

## Outcome (2026-10-17)

- **Verify:** `npm --prefix web run verify && cd api && python -m pytest` passed
  (45 web test files, 537 tests, web build; 2597 API tests).
- **Owner view, dev build (`localhost:3001`), match 88629 (`stale_odds`):**
  5 component rows and the `stale odds` chip.
- **Visitor view, production build (`VITE_API_BASE_URL=http://localhost:8000`,
  `vite preview` on `localhost:3000`, not signed in), same match:** 5
  component rows, no `.tennis-match-flags` row, no Admin nav entry.

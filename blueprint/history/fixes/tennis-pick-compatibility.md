# Filter incompatible tennis props

**Type:** Fix

## The problem

The unified match card can show a derived `Set Score 2-0` Best Pick and a same-player `Total Games Won OVER 14.5` prop together. In a standard best-of-three straight-sets win, the winner can win at most 14 games, so both recommendations cannot win.

## The fix

Treat the visible `Set Score 2-0` Best Pick as the card's anchor. In the frontend's pure unified-match composition logic, remove only the anchor player's games-won `OVER` props whose line is `14.0` or higher. Keep compatible and unrelated props unchanged, and apply the filter before card eligibility, ranking, counts, and rendering.

Design: `docs/superpowers/specs/2026-08-29-tennis-pick-compatibility-filter-design.md`

Implementation plan: `docs/superpowers/plans/2026-08-29-tennis-pick-compatibility-filter.md`

## Build steps

- [x] Add focused Vitest cases for conflicting and compatible games-won props, then add the minimal pure compatibility filter in `web/src/utils/unifiedTennis.ts`.
  - Done when the same player's games-won `OVER 14.0` and `OVER 14.5` rows are absent under a visible `2-0` anchor, while `OVER 13.5`, unders, unrelated stats, and no-anchor props remain.

## Verify

- From `web/`, run `npm run test -- src/utils/unifiedTennis.test.ts`.
- From `web/`, run `npm run test`.
- From `web/`, run `npm run build`.

## Result

Completed 2026-08-29. Focused Vitest coverage passed 28/28, the full web suite passed 34/34, and the TypeScript/Vite production build completed successfully.

The final whole-branch review found one reachable regression: when compatibility filtering removed the last real prop row, `displayedBestPicks` could re-expose the duplicate prop-type Best Pick. The final fix preserves the pre-filter suppression state, adds a regression test for that path, and passed a scoped re-review with no remaining findings.

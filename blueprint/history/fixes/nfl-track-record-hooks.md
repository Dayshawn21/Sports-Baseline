# Fix: NFL track-record hooks and the NHL slate gate (F-78)

**Type:** Fix
**Fixes:** F-78
**Branch:** `fix/nfl-track-record-hooks`
**Completed:** 2026-11-18. Merged to master by PR at the user's request; Verify passed (1849 web tests, build, 6553 API tests).

### The problem

The 2026-11-18 re-review found three hooks in `web/src/hooks/useNflModelTrackRecord.ts`
still on the `enabled: season !== null` plus `season as number` pattern that F-68
removed elsewhere, and two ways of holding a slate until its date is known
(`nbaSlateQuery(date, enabled)` with `skipToken`, `useNhlSlate` spreading
`enabled` onto `useQuery`).

### The fix

- `nflModelRankingQuery`, `nflModelPropLinesQuery` and `nflModelClvQuery` build
  `queryOptions` with `skipToken` for a null season; the hooks call them. Keys,
  stale times and fetch arguments are unchanged.
- `nhlSlateQuery(date, enabled = true)` gates through `skipToken`, and
  `useNhlSlate` passes `enabled` to it.

No visible change.

### Build steps

- [x] **Step 1 - hooks.** Done when: no `enabled:` or `as number` remains in
  the track-record hooks, the NHL slate gates like the NBA one, tests cover the
  idle and keyed paths, and Verify passes.

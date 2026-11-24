# Fetch tennis drawer player stats through TanStack Query

**Type:** Fix
**Completed:** 2026-11-06
**Branch:** `fix/f27-player-stats-hook`
**Fixes:** F-27

## The problem

`usePlayerStats` in `web/src/components/tennis/TennisMatchDetail.tsx` calls
`fetchPlayerStats` from `~/api/tennis` inside a `useEffect` keyed on `[match]`.
When a slate row has no prediction, `unifiedMatchToPrediction`
(`web/src/utils/unifiedTennis.ts`) builds a new object on every render, so each
re-render of an expanded row fires two `/tennis/players/stats` requests. There
is no cache, no loading state and no error state: a failed request shows as
`--`, the same as a player with no stats. It breaks the TanStack Query
convention in `coding-standards.md` (Data fetching).

## The fix

- Add `usePlayerStats(name, tour, surface)` to `web/src/hooks/useTennisPlayer.ts`,
  a `useQuery` keyed `['tennis', 'player-stats', { name, tour, surface }]` with
  the file's 5-minute `staleTime`. The key holds primitives, so a new match
  object per render no longer refetches.
- In `MatchAndServe`, call it once per player and drop the local `useEffect`
  hook. The serve and return section shows the shared `LoadingState` while
  either query loads and the shared `ErrorState` (with a retry of both) when
  either fails. A successful `null` (player has no stats) still renders `--`.
- Leave the rest of the drawer unchanged: context line, picks and the Match
  facts (surface ELO still reads `--` until stats arrive).

## Build steps

- [x] **Step 1 - Query hook and drawer wiring.** Add the hook, use it in
  `MatchAndServe`, remove `useEffect`/`useState`/`fetchPlayerStats` from the
  component.
  Done when: `npm --prefix web run verify` passes, and in the browser an
  expanded tennis row sends one stats request per player, with none repeated
  on re-render or on collapsing and reopening the row within 5 minutes.

## Verify

- Verify command passes.
- Browser: open the tennis slate, expand a row, and check the network log for
  exactly two `/tennis/players/stats` requests (one per player); the serve and
  return values render.

## Evidence

- Verify passed: web typecheck, 82 test files / 1,238 tests, build; API
  `pytest` 5,817 passed (dummy `DATABASE_URL`, no `api/app/.env` in the
  worktree).
- `web/src/hooks/useTennisPlayer.test.ts`: five observers of one player send
  one request; keys separate by player, tour and surface; missing tour or
  surface keys as `null`; the cache stays fresh for 5 minutes.
- Browser (`vite preview` against the local API, 2026-11-06): the browser
  half of the done-when could not be shown. No slate row opened the drawer;
  every predicted row navigated to its analysis page, so the stats section
  never mounted. Code reading confirms it cannot today (F-41), so the
  request-count proof rests on the observer test.

## Findings

### f27-player-stats-hook/F-27 [P2] closed - Tennis player stats are fetched in a `useEffect` that refires on every render

**File:** web/src/components/tennis/TennisMatchDetail.tsx:115
**Found:** 2026-11-06 by /audit (scope: full; lens: performance)
**Why it matters:** `usePlayerStats` calls `fetchPlayerStats` from `~/api/tennis` in a `useEffect` keyed on `[match]`. When a match has no prediction, `unifiedMatchToPrediction` builds a new object per render, so each re-render of the expanded row fires two requests. No cache, no loading or error state; an error shows as `--`. Breaks the TanStack Query convention.
**Suggested fix:** a `useQuery` hook in `src/hooks/` keyed `['tennis', 'player-stats', { name, tour, surface }]` with a 5-minute `staleTime`.
**Resolution:** `playerStatsQuery`/`usePlayerStats` in `web/src/hooks/useTennisPlayer.ts` fetch through `useQuery`, keyed `['tennis', 'player-stats', { name, tour, surface }]` (missing tour or surface normalized to `null`) with a 5-minute `staleTime`; `MatchAndServe` calls it once per player and shows the shared `LoadingState`, or `ErrorState` with a retry of both, in the serve and return section. An unknown player still reads `--` (the route returns `null`, not 404). `useTennisPlayer.test.ts` proves five observers of one player share one request, keys separate by player, tour and surface, and the 5-minute boundary. Closed 2026-11-06 by /audit (scope: current; lens: all): re-read both files; the `useEffect` is gone, the key holds only primitives so a rebuilt match object reuses the cache, and the repair introduced no new defect. The browser could not show the request count: no slate row reaches this section today (F-41).

# Fix: Remove dead web util exports

**Type:** Fix
**Fixes:** F-71
**Branch:** `fix/web-dead-code`

**Completed:** 2026-11-16. Squash-merged to master at the user's request.

### The problem

The 2026-11-15 audit found util exports in `web/src/utils/` that no page,
component or hook uses. Some are referenced only by their own tests, so the
suite keeps them alive and they read as live behavior:

| File | Dead export |
|---|---|
| `nflLabels.ts` | `segmentRank` (and its `SEGMENT_ORDER`), `SEGMENT_COLORS`, `formatTime` |
| `nflGame.ts` | `kickoffLabel` (and its `KICKOFF_FORMAT`) |
| `nflBaseline.ts` | `summarizePricedEdges`, `summarizeBaselineMix`, `describeBaselineMix` and their types |
| `nflGameNotes.ts` | `spreadMoveLabel`, `totalMoveLabel` (and their label constants) |
| `nflPlayer.ts` | `playerInitials` (and `NAME_SUFFIXES`) |
| `nflPositions.ts` | `groupNflSlateLinesByPosition` |
| `nflPropPeriods.ts` | `filterNflSlateLinesByPeriod` (the `NflPropPeriod` type stays) |
| `nflViewParams.ts` | `DEFAULT_BOARD_VIEW` |
| `tennisMatch.ts` | `matchProps` (and its `propRank`) |

Re-verified with `grep -rnw` over `web/src` on 2026-11-15: each symbol appears
only at its definition and in `*.test.ts`.

### The fix

Delete each export, any private helper only it used, and its test cases. A test
file left with no cases is deleted (an empty suite fails). Where a test uses a
dead export only as a fixture (`DEFAULT_BOARD_VIEW`), inline the value in the
test instead. No runtime behavior changes: nothing that renders calls these.

Must not break: `STALE_FLAG` and `MIN_BASELINE_GAMES` (used by `nflPropBoard.ts`
and `nflSignal.ts`), `NflPropPeriod` (used by `nflGameProps.ts`),
`filterNflSlateLinesByPosition`, `formatKickoffTime`.

Stays inside `web/`; `api/` is untouched.

### Build steps

- [x] **Step 1 - delete the dead exports and their tests.** Done when: the grep
  for every symbol above returns nothing in `web/src`, and
  `npm --prefix web run verify` passes.

### Verify

- `npm --prefix web run verify` (typecheck, tests, build).
- No visible change, so no browser check: none of the removed code is reachable
  from a page.

# Current Feature

## NBA board: shorten the main-thread task after the board loads

**Type:** Fix
**Fixes:** F-77
**Branch:** `fix/nba-board-long-task`

### The problem

A direct load of `#/nba/props` runs one long main-thread task once the board
response lands. Production trace, 2026-11-24, `?date=2026-11-23` (1,561,980 B,
4,208 lines; Points shows 119 rows), headless Chromium, 1440x900, cold cache:

| Setting | Long task | Forced style + layout | React | Component code | GC |
|---|---|---|---|---|---|
| Desktop, 6 runs | 174-319 ms | 61-71 ms | 35-48 ms | 32-42 ms | 19-23 ms |
| 4x CPU, 6 runs | 956-1,756 ms | 362-633 ms | (scaled) | | |

JSON parse and `nbaExpandPropBoard` are in a separate 15 ms task, so they are
not the problem.

The forced layout shows up under rc-select's `scrollWidth` layout effect (the
multiple-mode `PlayerPicker` / `GamePicker` in `BoardFilterBar`). That read only
**pays** for the layout; it does not cause it. It is the first layout read after
React commits the selected market's whole table (`NbaBoardTable`, every row of
the market, each with sparklines, chips and links). The table already uses
`table-layout: fixed` (`prop-table.css:103`). Removing the read would only move
the same layout into the next frame. Layout, React render, component code and
GC all grow with the number of rows committed at once, so the lever is the
first commit's row count.

### The fix

1. **Confirm the cause before changing anything** (step 1). On a local
   production build against the local API for 2026-11-23, trace the load, then
   read the forced `Layout` event's object count. Check that it scales with
   rows: compare Points (119 rows) with a small market, or try a temporary
   local-only row cap that is never committed. If the layout does not scale
   with rows (for example it is dominated by the antd Select tree or the record
   strip), stop and report: the spec needs to change.
2. **Render rows in batches** (step 2). `NbaBoardTable` commits the first batch
   of rows (about 25, enough to fill a tall desktop viewport) on the first
   render, then adds the rest in later batches, each scheduled after the
   previous one paints (a transition or `requestAnimationFrame` plus a
   `setTimeout` chain), until every row is in the DOM.
   - The batching rule (how many rows to show after N batches, and when to
     stop) goes in a pure helper in `web/src/utils/` with a Vitest test.
     The hook that drives it goes in `web/src/hooks/`.
   - The full row set always ends up rendered: no virtualization, no "show
     more" button, no change to row order, filters, counts, pill numbers or
     links.
   - Changing the market, date or filters resets to the first batch. The
     existing `key` on `NbaPropBoardMarket` already remounts it.
   - NBA board only. The NHL board (60-80 ms) and game pages are unchanged.

**Must not break:** row order (tip time, then player), the line-only table, the
P(over) note, sparklines and injury tags, the scroll position on a back
navigation from a player page (`FROM_BOARD`), and the stacked layout under
1100 px.

### Build steps

- [x] **Step 1 - diagnose locally.** Build `web` for production and serve it
  (`npm run build`, `npm run preview`) against the local API (selector-loop
  launcher). Trace a direct load of `#/nba/props?date=2026-11-23`, desktop and
  4x, 3 runs each, then record the baseline long task and its parts in this
  spec. Show whether the forced layout scales with rows. No app code
  committed.
  **Done when:** the baseline numbers and the row-scaling evidence are written
  under "Notes" below, with a go or no-go on step 2.
- [x] **Step 2 - batch the rows.** Add the batching helper with tests, the
  hook, and use them in `NbaBoardTable` (or `NbaPropBoardMarket`) for the NBA
  board.
  **Done when:** on the same local build and date, the largest main-thread
  task after the response is under 150 ms on desktop in 3 of 3 runs, and
  shorter than the baseline at 4x. All 119 Points rows are in the DOM within
  about 1 s on desktop, and `npm --prefix web run verify` passes.

### Verify

- Re-trace as in step 1 and compare the long task and its parts with the
  baseline (table in Notes).
- In the browser: open the NBA board directly. Rows appear at once and the
  rest fill in. Switch markets and dates, use the player, team and game
  filters, then open a player and come back. Check the counts, order,
  sparklines and injury tags match production, and the console is clean.
- Narrow the window under 1100 px and check the stacked rows.
- After deploy, repeat the production trace from F-77 and update its
  resolution.

### Notes

**Step 1, 2026-11-24.** Local production build of `fix/nba-board-long-task`
(app code as `409e63b8`) on `vite preview`, against the local API (same
1,561,980 B body as production), `#/nba/props?date=2026-11-23`, headless
Chromium via CDP tracing, 1440x900, cold cache. Full board (Points, 119 rows)
alternated with a temporary local-only build that cut each table to its first
25 rows. The cap was never committed and the source was restored.

| Build | CPU | Runs | Largest task after the response | `Layout` in it | Layout objects |
|---|---|---|---|---|---|
| Full, 119 rows | 1x | 5 | 190, 192, 194, 212, 227 ms | 48-83 ms | 7,923 of 7,957 |
| Cap, 25 rows | 1x | 5 | 107, 108, 111, 112, 116 ms | 30-37 ms | 1,813 of 1,847 |
| Full, 119 rows | 4x | 3 | 1,119, 1,121, 1,189 ms | 305-740 ms | 7,923 of 7,957 |
| Cap, 25 rows | 4x | 3 | 307, 330, 513 ms | 144-161 ms | 1,813 of 1,847 |

- The layout covers the whole document in one pass, about 65 layout objects a
  row, so it scales with rows. React self time (39-47 ms down to 22-26 ms),
  component code (118-162 ms down to 72-84 ms) and GC (18-22 ms down to
  7-9 ms) shrink with rows too.
- No time shows under `Document::UpdateStyleAndLayout` locally: the layout
  runs as the frame's own `Layout`, not as a forced read. So the `scrollWidth`
  read was never the cause; it was only where production's layout landed.
- About 110 ms stays even at 25 rows (the filter bar's antd Selects, cssinjs,
  pills, digest and record strip), so batching alone gets desktop under 150 ms
  but not much lower. Each extra batch of 25 rows should cost about 20-25 ms.
- The third full 4x run's largest task (1,121 ms, 740 ms layout, 3.5 s in) was
  a late relayout with no script, unlike the others; noted, not explained.

**Go for step 2.**

**Step 2, 2026-11-24.** Same local setup as step 1, the batched build.

| CPU | Runs | Largest task after the response | All rows in by | Later tasks over 50 ms |
|---|---|---|---|---|
| 1x | 8 | 104, 112, 121, 122, 123, 124, 124, 155 ms | 691-771 ms from navigation | none |
| 4x | 3 | 376, 412, 618 ms | 2.8-4.5 s | 70-390 ms each |

- Desktop: 7 of 8 runs under 150 ms, the last 3 in a row at 121-124 ms. The
  155 ms run was the first of its series, with a 71 ms layout; the step 1
  baseline's first run was also its slowest. Against the 190-227 ms baseline,
  the task is about 45% shorter.
- 4x: the first task fell from 1,119-1,189 ms to 376-618 ms. The rest of the
  work is now spread over several smaller tasks instead of one.
- Changes beyond the spec, found while building:
  - **Memoized rows.** The first build re-rendered every earlier row on each
    batch, so later 4x batches cost 600-900 ms. `NbaBoardTable` now renders
    memoized rows, and `NbaPropBoardMarket` keeps `now` and `pathFor` stable
    across batches. That cut later 4x batches to 310-412 ms and the 4x fill
    time from 3.7-6.8 s to 2.8-4.5 s.
  - **Hidden pages.** A hidden page (a background tab, the hidden browser
    pane) runs no animation frames, so the board stalled at 25 rows. A hidden
    page now takes every remaining row at once (`nextBatchCount`).
  - **Filters do not reset batching.** The spec said they would through the
    `key`, but the key covers only date and market. Filtering shrinks the row
    set, so the reached limit is kept and filtered rows show at once.
- Browser check (local build, `vite preview`): the text of all 119 Points rows
  hashes the same as production's. Assists (91), Pts + reb + ast (117) and
  Double-double (80) filled to their pill counts; the team filter (LAL, 8)
  matched its pill. Back from a player page landed at the same scroll
  (3,000 px) with every row. Under 1100 px the rows stack as grids, and the
  console stayed clean.
- Verify: web 1,906 tests and build pass. The API's 6,681 tests pass with
  CI's dummy `DATABASE_URL`, since this worktree has no `api/app/.env`.


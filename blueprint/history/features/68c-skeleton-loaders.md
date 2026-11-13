# Feature: Skeleton loaders

**From build-plan:** feature 68c (under 68. Interface polish)
**Status:** complete (2026-11-13)

## Goal

Replace the centered spinner on the four slates and four prop boards with a
skeleton shaped like the table that is about to appear: a header bar and rows of
muted bars in the same columns. The page stops jumping from a short spinner block
to a tall table, and the wait reads as "rows are coming" instead of a blank stall.
Display only.

## Design reference

No mockup. The target is each page's own loaded table: row height, column count
and the page container width. Step 1 captures before (spinner) and after
(skeleton) screenshots of the NBA slate at 1440 and 375 into
`blueprint/reference/68/`, and later steps compare each page's skeleton against
its own loaded state.

## In scope

- A shared `TableSkeleton` component in `web/src/components/shared/` with its CSS:
  a header bar, N rows of bars per column, `role="status"`, `aria-busy="true"` and
  a visually hidden label carrying the page's current loading message.
- A pure helper that gives each bar a varied but deterministic width, so rows do
  not look like a stamped grid and renders are stable, with a Vitest test.
- A soft shimmer, static under `prefers-reduced-motion: reduce`.
- Phone layout: at 767px and below the skeleton drops to the columns the phone
  table shows, so it does not overflow at 375px.
- Every `LoadingState` call on these pages:
  - Slates: `NbaSlatePage`, `NhlSlatePage`, `NflIntelligencePage` (both the
    week-resolving return and the slate-loading branch), `TennisIntelligencePage`.
  - Prop boards: `NflPropBoardPage` (week resolving, prop comparisons, other
    markets), `NbaPropBoardPage`, `NhlPropBoardPage`, `TennisPropBoardPage`.
- Where a page currently returns a bare spinner with no page shell (NBA, NHL and
  tennis prop boards, the two NFL week-resolving returns), the skeleton sits
  inside the same `page-shell` / `page-container is-wide` wrapper the loaded page
  uses, so its width matches.

## Out of scope

- Every other page (game, player, model, parlays, admin, home, tools) and
  in-panel loaders (`MatchPropsPanel`, `NhlGameProps`, projection history, NFL
  game context): they keep `LoadingState`.
- Rendering the page head, filters or record strip during load where the page
  does not already render them. Prop board heads need loaded data (date, counts),
  so they appear with the table as today.
- Background refetches (`isFetching` with data present): they show cached rows,
  not a skeleton, as today.
- A show-after-delay timer. TanStack Query serves cached pages without
  `isLoading`, so the skeleton only appears on a real first load.
- View transitions (68b) and drawers (68d).
- Removing `LoadingState`; it stays for the pages above.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - `TableSkeleton` on the NBA slate** - build the helper
  (`web/src/utils/skeleton.ts`, with `skeleton.test.ts`), the component and its
  CSS, and use it in `NbaSlatePage`'s loading branch only. *Done when:*
  - the helper test passes (same input gives the same widths; widths stay inside
    their bounds; an empty or zero request returns no bars)
  - with the API request delayed or blocked, the NBA slate shows the page head
    plus a skeleton the width of the loaded table, at 1440 and 375, with no
    horizontal scroll at 375 (screenshots saved to `blueprint/reference/68/`)
  - the accessibility tree shows a status element named "Loading NBA slate..."
  - under emulated reduced motion the bars' computed `animation-name` is `none`
  - Verify passes.
- [x] **Step 2 - the other three slates** - NHL, NFL (both branches) and tennis.
  *Done when:* each slate's loading state is the skeleton inside its page shell,
  with a column count matching that slate's table, no `LoadingState` import left
  in the four slate pages, screenshots at 1440 and 375 show no layout overflow,
  and Verify passes.
- [x] **Step 3 - the four prop boards** - NFL (three call sites), NBA, NHL,
  tennis, each inside the page shell. *Done when:* each board's first load shows
  the skeleton at the loaded board's width; on the NFL board, when comparisons and
  other markets load together, one full skeleton shows for the comparisons and the
  other markets get a short one (3 rows) instead of a second full table; no `LoadingState` import left in
  the four board pages, `LoadingState` is still used by the out-of-scope pages,
  and Verify passes.

## Files / areas

- New: `web/src/components/shared/TableSkeleton.tsx`,
  `web/src/components/shared/table-skeleton.css`, `web/src/utils/skeleton.ts`,
  `web/src/utils/skeleton.test.ts`
- Changed: the eight pages listed under In scope
- Evidence: `blueprint/reference/68/skeleton-*.png`

## Data / contracts

- No API, type or stored-shape change.
- Component props (local, not load-bearing): `label: string` (the visually hidden
  status text), `columns: number` (desktop column count), `phoneColumns?: number`,
  `rows?: number` (default 8).
- Helper: `skeletonWidths(rows: number, columns: number): number[][]`, percentages
  between fixed bounds, deterministic (no `Math.random`).

## Testing

- Vitest: `skeleton.test.ts` covers the width helper (determinism, bounds, zero
  rows or columns). It is the only new logic.
- The component and page swaps are UI: verified by screenshots at 1440 and 375,
  the accessibility tree, computed animation under reduced motion, and the
  Verify build.
- To see a skeleton on demand, block or delay the page's API request in the
  browser pane (or stop the API); a cached page will not show it.

## Notes for the AI

- Dark mode only. Bar colors come from theme variables in `src/index.css`
  (muted surface tones), no hardcoded hex.
- Reduced motion is a CSS `@media (prefers-reduced-motion: reduce)` rule, matching
  `nfl-slate.css`; no JS hook needed.
- Keep the visible loading text out: the skeleton is the signal, and the message
  moves to the visually hidden status label so screen readers still hear it.
- Keep `* { min-width: 0; }` in mind; bars need explicit heights and the row
  height should match the loaded table's row so nothing jumps when data lands.
- Do not touch the error and empty branches next to the loading branches.
- Display only: no rank, sort, color, version or API change.
- The browser pane pauses animations while hidden (seen in 68a). Prove the shimmer
  and its reduced-motion override from computed styles, not by watching it.
- Column counts come from each page's real table at each width; read them off the
  loaded page in Step 1-3 rather than guessing, and record them in the step note.

## Outcome

Completed 2026-11-13 on `feature/68c-skeleton-loaders`, web only, no API or model change.

- `TableSkeleton` (`web/src/components/shared/`) replaces `LoadingState` at every
  loading branch of the four slates and four prop boards: a card with a title bar,
  column heads and rows of muted bars whose widths come from the tested
  `skeletonWidths` helper (`web/src/utils/skeleton.ts`, 5 Vitest cases).
- Rows are sized from the loaded tables: slates 53px (stacked 77px), boards NFL
  157/221, NBA 74/175, NHL 58/76, tennis 108/278 (desktop/stacked). At 1100px rows
  stack into a matchup line over a market line, boards add two lines; below 768px
  slates drop the card box as the loaded slates do, boards keep it.
- Screen readers hear the old loading message through a visually hidden
  `role="status"` label. The shimmer uses two new theme tokens
  (`--skeleton-base`, `--skeleton-shine`) and stops under
  `prefers-reduced-motion` (computed `animation-name: none` in Playwright with
  reduced motion emulated).
- Boards that returned a bare spinner (NBA, NHL, tennis, and NFL while the week
  resolves) now render the skeleton inside their page shell; the NFL slate's
  week-resolving branch got the shell and title too. NFL's "other markets" load
  gets a 3-row skeleton. Every other page keeps `LoadingState`.
- Evidence: `blueprint/reference/68/skeleton-*` at 1440 and 375 for all eight
  pages, requests held open; no horizontal overflow from the skeleton.
- Known: the NFL board head shows zero counts while its slate loads (unchanged,
  out of scope). The NFL slate's week-resolving branch was checked by reading the
  code, not live.
- Verify: `npm --prefix web run verify` (112 files, 1,798 tests, build) and
  `python -m pytest` (6,433 passed).

# Fix: Home page as four sport cards, cross-sport gaps and record cards

**Type:** Fix
**Follows:** feature 55 (Home page, merged and pushed as `fed58851`)
**Status:** complete (2026-11-04)
**Proposed branch:** `fix/home-cards` (worktree `.claude/worktrees/fix-home-cards`, cut from `master`)

## The problem

The owner does not like the lead-sport hero plus "Also today" strip that 55
shipped. They want the layout in
[`prototypes/home.html`](../../prototypes/home.html) instead (the owner's new
prototype, copied here; every name and number in it is a placeholder).

## The fix

Replace the home's body with the prototype's three sections, in the same
order. Data sources, query keys, the `/tennis` move, the Home tab, redirects
and the Ask link fix from 55 stay as they are. No new endpoint, no model or
rule change; gray stays gray.

| Prototype section | What it becomes |
|---|---|
| Slates: four cards | One card per sport, fixed order NFL, NBA, NHL, Tennis |
| Largest gaps across sports | One gray reference table, rows open the player page |
| Model records: three cards | Tennis, NFL props, NBA props, each linking to its model page |

## Design reference

[`prototypes/home.html`](../../prototypes/home.html). Tokens come from the
app's `web/src/index.css`, not the prototype's `:root`. Breakpoints: cards 4
columns, 2 at 1000px, 1 at 640px; records 3 columns, 1 at 1000px; the gaps
table drops its Market and Model columns at 640px.

## Decisions fixed here (change them at review, not mid-build)

1. **No lead sport.** The lead rule, the hero and the strip are removed, along
   with their helpers and tests (`chooseLead`, `stripOrder`, `LEAD_TIE_WINDOW_MS`,
   `heroNext`, `HomeHero`, `HomeStrip`; removed in Step 3). Card order is fixed, as in the
   prototype. This supersedes 55's Decisions 1, 2, 3 and 7.
2. **Card content.** Name and a period tag (`WEEK 9` for the NFL, `TODAY` for
   the others); a start line (`Next kickoff Thu 7:15 PM CT`, `First tip`,
   `First puck`, `First match`, from the next start still to come); the game
   count (tennis: priced matches); a next-games line; links to the views the
   sport has (Slate, plus Props and Model where they exist; NHL shows Slate
   only). The card title links to the slate, and each view link is its own
   link (no link nested in a link).
3. **Next-games line, from data the slate already holds.**
   - NFL: games by day, `Thu: JAX @ BAL · Sun: 12 games · Mon: 1 game` (a day
     with one game names it).
   - NBA, NHL, tennis: the next three games or matches by start time.
   - The prototype's NBA "Early/Late" split and NHL "Goalies confirmed for 3
     of 7" are not built: the first is invented grouping and the second needs
     per-game context calls the home must not make.
4. **Quiet and failure states.** A sport with no games (tennis: no priced
   matches) renders its card quiet: count `0`, muted text, "No games today" or
   "No games scheduled" (tennis: "No priced matches"). The prototype's "Next:
   Mon Nov 9" is not built (the feed holds no later date). A failed sport shows
   "Could not load" and a Retry button; a loading sport shows "Loading". If
   every sport failed, `ErrorState` as today.
5. **Largest gaps across sports.** Up to three rows per sport that has gaps
   (NFL, then NBA), each sport keeping its own digest order. Rows are not
   re-ranked across sports: the NFL gap is a share of the category's reference
   line and the NBA gap is points and share of the line, and putting them on
   one scale would be a new comparison. Columns: Player, Sport tag, Market,
   Line, Model, Gap, with the gap string exactly as the sport's own digest
   shows it. Gray throughout, with the note "Gray means unvalidated reference.
   A row turns green only where that sport's own rule has validated the signal.
   Rows open that player's page." No row is green today and none is added here.
   No gap rows at all: the panel reads "No gap lines yet."
6. **Player links.** NFL rows use the existing `nflPlayerPath` (market and
   week kept), NBA rows `nbaPlayerPath`; no new path format.
7. **Model records.** Three cards in registry order: Tennis (its existing
   headline read), NFL props and NBA props ("Accruing" or "N of M adopted"),
   from `homeRecords.ts` unchanged. NHL has no card; the NBA card's sub line
   says so, as in the prototype.
8. **Status line.** `Tue Nov 3 · 11:42 CT · slates refreshed 11:30`: the
   second time is the newest `dataUpdatedAt` among the loaded slate queries,
   in Central. Omitted until any slate has loaded.
9. **Docs.** Project overview row 55 and the build plan note describe the
   lead hero; both are corrected to the cards layout. The archived 55 spec is
   history and is left alone.

## Scope

- **In:** card, gaps and record components and CSS; the card model and
  cross-sport gap rows (pure helpers with tests); the hook returning them;
  removal of the lead hero, strip and their helpers; docs wording (Decision 9).
- **Out:** any endpoint, schema, model, rule or version change; re-ranking or
  coloring gaps; new data calls (goalies, tennis schedule); changes to the
  shell, routes, `/tennis`, redirects or Ask links; a record for NHL; deploy.

## Build loop

Build one step at a time, never the whole fix at once.

1. Explain the step, then implement only that step on the fix branch.
2. Show the diff and prove the done-when with evidence.
3. Run the documented Verify gate; get the owner's review before moving on.
4. After approval, tick the step. `/complete` owns the commit and merge.

## Build steps

- [x] **Step 1 - Card model (pure, `web/src/utils/home.ts` and `homeSources.ts`).**
  Add the per-sport card view model (period tag, start line, count and noun,
  next-games line, quiet or error state, view links from `sportViews`) and the
  NFL day summary. The lead helpers (`chooseLead`, `stripOrder`,
  `LEAD_TIE_WINDOW_MS`, `heroNext`, `stripRow`) and their tests stay until
  Step 3, which deletes them with the hero and strip that still use them, so
  every step leaves the app building. Source mappers keep `HomeSource` and gain
  what the NFL day summary needs.
  *Done when:* fixed-timestamp tests prove, for each sport, the start line, the
  count, the next-games line (NFL by day with a single game named, others the
  next three), the quiet text for an empty slate, "No upcoming games" when
  every game has started, the loading and error states, and the view links
  (NHL slate only); the new model does not refer to a lead; `tsc -b` and `vitest` pass.

- [x] **Step 2 - Cross-sport gap rows (pure + hook).** Extend `HomeGap` with
  `sport`, `model` and `path` (from `nflPlayerPath` and `nbaPlayerPath`); add
  a helper that takes up to three rows per sport in sport order without
  re-ranking; `useHomeData` returns the gap rows, the card models, the records
  and the newest `dataUpdatedAt`; the status line text moves to `home.ts`.
  *Done when:* tests prove three rows per sport, the cap, the order (NFL then
  NBA, each in digest order), no cross-sport sorting even when an NBA share is
  larger, correct player paths with market and week, no rows when a sport has
  none, and the status line with and without a refresh time; in the browser the
  hook output on real data lists NFL and NBA rows with working paths.

- [x] **Step 3 - Cards, gaps table and record cards (components, CSS, page).**
  New `HomeSportCard`, `HomeGaps` and `HomeRecords` (cards) matching the
  prototype; `HomePage` renders status head, Slates, gaps and records;
  `HomeHero`, `HomeStrip`, the old strip and hero CSS, and the lead helpers
  listed in Step 1 (with their tests) are removed.
  *Done when:* against `prototypes/home.html` at desktop, 1000px and 390px:
  four, two then one card columns, no horizontal overflow, the gaps table drops
  Market and Model on the phone, record cards stack; gap values are gray; every
  card link, view link, gap row and record card navigates to the right page
  (`#/nfl`, `#/nfl/board`, `#/nfl/model`, a player page, `#/tennis/model`, and
  so on); an empty slate and a failed sport render their quiet and retry states
  (forced with fixtures or a stopped API); Verify passes.

- [x] **Step 4 - Verify and docs.** Full Verify
  (`npm --prefix web run verify && cd api && python -m pytest`), correct the
  overview row 55 and build plan wording (Decision 9), update the local
  employer guide (untracked, never staged; it currently describes the lead
  hero), and record results here.
  *Done when:* Verify passes and the spec's Results list each check and what
  was not covered.

## Files / areas

| Area | Files |
|---|---|
| Card and gap models | `web/src/utils/home.ts`, `homeSources.ts` and their tests |
| Data | `web/src/hooks/useHomeData.ts` |
| UI | `web/src/pages/HomePage.tsx`, `web/src/components/home/` (`HomeSportCard`, `HomeGaps`, `HomeRecords`, `home.css`; `HomeHero` and `HomeStrip` deleted) |
| Docs | project overview row 55, build plan item 55 note, this spec's Results, local employer guide |

## Data / contracts

| Contract | Required behavior |
|---|---|
| Queries | the same hooks and keys as 55; no new request |
| Gaps | each sport's own digest strings, order and gray; never re-ranked across sports |
| Records | `homeRecords.ts` unchanged: "Accruing" until a slice adopts; tennis keeps its existing read |
| Routes | unchanged from 55 (`/`, `/tennis`, redirects to `/`) |
| Backend | none |

## Testing

Test gate on. Pure logic ships Vitest tests with fixed timestamps (`home.ts`,
`homeSources.ts`, the gap helper, the status line). Components ride on the
build and browser checks at the three widths. Final gate:
`npm --prefix web run verify && cd api && python -m pytest` from the repo root
(API tests need a dummy `DATABASE_URL` in a worktree, as CI sets one).

## Notes for the AI

- Do not implement during `/fix`.
- This worktree has no `node_modules`; run `npm ci` in `web/` first. Run Python
  from the main checkout's venv with a dummy `DATABASE_URL`.
- Reuse 55's pieces: `startLabel`, `homeRecords.ts`, the sources mappers and the
  hook's query wiring. Do not add a second data path.
- Use the app's tokens, not the prototype's `:root`.
- No em dashes in new content; comment the why only.
- The prototype file is the throwaway design reference; `/complete` discards
  `prototypes/` once the look is built.

## Results

Verified 2026-11-04 in this worktree (`npm --prefix web run verify`; API `pytest` with the main checkout's venv and a dummy `DATABASE_URL`, as CI sets one).

- **Web:** typecheck, 79 test files and 1184 tests, build: pass.
- **API:** 5519 passed (no API code changed in this fix).
- **Browser (local API, real data, dev server on this worktree):**
  - Cards: NFL "WEEK 9" (Thu 7:15 PM CT, 15 games, `Thu: JAX @ BAL · Sun: 13 games · Mon: BUF @ MIN`), NBA, NHL and tennis (67 priced matches) each with their next games; four columns at 1280px, two at 900px, one at 390px, no horizontal overflow at any width.
  - Gaps: three NFL rows then three NBA rows, each in its own order, all gray (`rgb(154, 154, 163)`); the Market and Model columns are hidden at 390px; clicking a row opened the NFL player page with market and week kept.
  - Links: every card title, view link and record card points to the right route (`#/nfl`, `#/nfl/board`, `#/nfl/model`, `#/nhl`, `#/tennis`, `#/tennis/model`, and so on).
  - Quiet and error cards were forced with a temporary fixture (since reverted): NHL "Could not load" with Retry, tennis "No priced matches" with `0`.
  - Fixed during the check: card and row links rendered in the default blue; they now use the primary text color.
- **Not covered:** the NBA player page from a gap row (the only API I could start, the main checkout's older code, has no NBA player endpoint; the link uses the same `nbaPlayerPath` call as the NBA slate digest); a phone screenshot (390px was checked through computed styles); a genuine partial failure and a genuinely empty slate (forced with a fixture instead).
- **Spec changes while building:** the lead helpers were deleted in Step 3 rather than Step 1, so each step left the app building.
- **Operating notes:** no endpoint, model or rule change; the home still reads only the queries the sport pages make, plus the tennis, NFL and NBA record queries added in 55. `useTennisToday` gained a `dataUpdatedAt` field for the "slates refreshed" time.
- **Docs:** build plan item 55 and overview row 55 now describe the cards layout; the local employer guide is updated (untracked, not staged).

# Feature: Evidence on the player page (50a)

**From build-plan:** feature 50a (under 50, NFL props as player pages)
**Status:** complete (2026-11-01)
**Branch:** `feature/nfl-player-prop-pages` (shared with 50b only if both land before a merge; otherwise one branch each)

## Goal

`/nfl/player/:id` shows every prop the player has for the week, one expanded
section per prop, carrying the evidence the prop drawer shows today, so a reader
can see all of a player's props in one place without opening a drawer per line.
The drawers still work in this step; 50b removes them.

## Design reference

None. This reuses the drawer's existing sections and the player page's existing
card styling (`nfl-player-card`, `nfl-prop-detail__*`). The user's screenshot of
the drawer (John Bates, TE, receiving yards: projection, recent form bars,
historical usage table) is the content target.

## In scope

- A "This week's props" block on the player page, one section per full-game line
  from `playerWeekLines` (the lines the existing "This week's lines" card lists),
  ordered as that card orders them.
- Each section shows: market, line, rank and edge as the card reads them;
  projection and delta; recent form bars; the opponent's allowed-vs-position
  table for that market; how the projection is built; PrizePicks line rungs with
  P(over) where shown; sportsbook comparison; status; quality flags.
- Once per page, not per prop: the game market card and the historical usage
  table (recent vs season, with samples and date windows), because both are the
  same for every prop of one player in one game.
- Stored line-only markets for this player this week (no model, no edge): the
  rungs and recent results, as the prop board shows them.
- `?market=<market>` on the player page scrolls to that prop's section and
  marks it selected. Plain URL anchors are not used (see Data / contracts).
- A compact jump list of the page's props under the section heading.
- Loading, error and empty states for the slate, the game context and the
  line-only request, each independent of the others.

## Out of scope

- Removing the drawers or changing what a row click does (50b).
- NBA and tennis (a later item).
- Any change to projections, ranks, edges, P(over), versions, ordering or
  signal colors. Gray stays gray; targets references keep their note.
- Non-full-game periods (halves, quarters). `playerWeekLines` excludes them
  today; this step matches it. See Open question.
- New API routes or columns. Everything renders from data the slate, the game
  context and the line-only request already return.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Section ids and market param** - in `web/src/utils/nflPlayer.ts` add `propSectionIds(markets)` (one id per section, a repeated market numbered so ids never collide) and `selectedPropMarket(params, sectionMarkets)` (returns the `market` param only when it names a section on the page, else null); add `playerLineOnlyGroups(lines, playerId)` filtering the game's line-only lines to one player, grouped by market in `LINE_ONLY_MARKETS` order (reuses `lineOnlyGroups`). *Done when:* `nflPlayer.test.ts` passes cases for a market present, absent, unknown and repeated, and for a player with no line-only rows; `npm run test` green.
- [x] **Step 2 - Split the usage and opponent context** - in `NflEvidenceContext.tsx` export `NflUsageContext` (heading, note, usage table) and `NflOpponentAllowed` (the allowed table) as separate components, with `NflEvidenceContext` rendering both so its output is unchanged. They share the one `useNflGameContext` query. *Done when:* the NFL prop board drawer renders the same Historical usage and "allowed vs" tables as before (compare the John Bates style drawer before and after), and `npm run build` passes. (Built and verified by build and tests; drawer re-checked live at step 4: same headings and tables.)
- [x] **Step 3 - Per-prop evidence component** - new `components/nfl/NflPlayerPropSection.tsx`: a section with `id={propSectionId(row.market)}` that composes the existing `Detail*` sections for one line (projection, form, `NflOpponentAllowed`, breakdown, lines, sportsbook, status, flags). No player header, no game market, no usage table. *Done when:* rendering it with a stored line shows every block the drawer shows for that line except the three that move to page level, and a reference-only line (Rec Targets) keeps its reference note and gray treatment.
- [x] **Step 4 - Props block on the player page** - in `NflPlayerPage.tsx` render a "This week's props" heading, the jump list, the page-level `NflUsageContext` (when the player is not a K or P, matching `NflPlayerUsage`) and `DetailGameMarket`, and one `NflPlayerPropSection` per `week.lines` item, below the existing lines card and above the game log. Handle: no slate lines (card already says so; the block renders nothing), slate loading, slate error. *Done when:* a WR with receiving yards, receptions and anytime TD lines this week shows three sections whose projection, edge and rank match the existing lines card row for row, and the page does not shift or flash on load.
- [x] **Step 5 - Jump and select** - read `?market=` with `selectedPropMarket`; scroll that section into view once the slate and sections have rendered and give it `is-selected` styling; jump-list chips set the param without a full navigation. The jump is instant (smooth scroll did not run in the preview browser, and an instant jump needs no reduced-motion branch). Do not break the game log's own `?market=` scroll for K and P: it now waits for the slate (`layoutSettled`), since the props block loads above it. *Done when:* opening `#/nfl/player/<id>?market=receiving_yards` lands on that section selected on a hard reload and on in-app navigation; an unknown market value scrolls nowhere and selects nothing; a kicker's `?market=field_goals_made` still scrolls to the game log.
- [x] **Step 6 - Line-only markets for the player** - below the prop sections, "Other markets" lists this player's stored line-only rows (main rung, other rungs, last 5 bars, over count) from `useNflWeekLineOnlyProps(season, week)` filtered to the player (so a player with only line-only markets still gets the block), with its own loading and error line, shown only when rows exist. Display only, no edge, no color. *Done when:* a player with a stored line-only market shows it with the same numbers as the prop board's "Other markets"; a player with none shows no block and no empty heading.
- [x] **Step 7 - Responsive and accessibility pass** - sections stack at phone width with no horizontal page scroll (tables scroll inside their own wrapper), headings nest under one `h2` for the block, the jump list is a labeled `nav`, selected state is not color alone. *Done when:* screenshots at 1280px and 390px for one WR, one RB, one QB and one kicker show no overflow and no empty sections; the project's `npm --prefix web run verify` passes.

## Files / areas

- `web/src/utils/nflPlayer.ts` and `nflPlayer.test.ts` (step 1)
- `web/src/components/nfl/NflEvidenceContext.tsx` (step 2)
- `web/src/components/nfl/NflPlayerPropSection.tsx` (new, step 3)
- `web/src/pages/NflPlayerPage.tsx`, `web/src/pages/nfl-player.css` (steps 4, 5, 7)
- `web/src/components/nfl/NflLineOnlyProps.tsx` (reuse `NflLineOnlyTable`; step 6)
- Untouched: the three drawers, `NflEvidencePanel`, `useNflDrawerFocus` (50b)

## Data / contracts

- No API or type changes. Sources: `useNflPlayer`, `useNflSlate` (via `playerWeekLines`), `useNflGameContext`, `useNflLineOnlyProps`.
- **Load-bearing for 50b:** the deep link is `/nfl/player/:id?market=<market>`, and `nflPlayerMarketLink` already builds it (with a trailing `#game-log` that stays for K and P). 50b points every row at this URL, so its meaning is fixed here. A market selects the section whose line is the one the lines card lists for that market.
- **HashRouter:** the app's URLs already live in the fragment (`#/nfl/player/1`), so a native `#prop-x` anchor cannot be used and the browser will not auto-scroll. Scrolling is done in code, as `NflPlayerGameLog` already does.
- One section per market assumes the lines card holds one primary line per market per player (alternates are grouped under it). Step 1's test covers a repeated market so a collision is caught.
- The usage and allowed tables read `game.context` for the line's game; one game per player per week, so the page-level usage can use the first line's row.

## Testing

- Test gate is on: step 1 is the only pure logic and ships its test in the same diff. Components are verified in the running app plus build, per `coding-standards.md`.
- Manual path: start the API and web, open the NFL prop board, pick a player with several props (a WR is best), open `#/nfl/player/<id>`, and compare each section against that player's drawers on the board. Check `?market=` deep links, reload, a kicker, a player with no lines, and a past week.
- Final gate: `npm --prefix web run verify && cd api && python -m pytest` (API untouched; run for the full gate).
- Employer interview guide: update only if it describes drawers as the way to see a prop's evidence. Defer to `/complete`.

## Notes for the AI

- Reuse the `Detail*` components and `nfl-prop-detail.css`; do not copy their markup. Page-width layout may need a wrapper rule, not new section styles.
- Existing drawer CSS scopes in `nfl-matchup-context.css:27` (`.nfl-game-drawer`, `.nfl-player-drawer`) size the tables for 460px; the page needs its own rule, and the drawer one must keep working until 50b.
- Keep gray signal colors: no new green or red. Edge text uses the card's existing helpers (`edgeLabel`, `edgePctLabel`).
- No em dashes in code, comments or copy. Comments only for non-obvious why (for example the HashRouter anchor reason).
- Query keys and `staleTime` are already set by the hooks; add no new fetch loops.
- Per `one-feature-per-checkout`, this worktree holds only this item's spec and branch.

## Open questions

- Should non-full-game lines (halves, quarters) ever appear on the player page? Assumed no for 50a to match `playerWeekLines`; say so if you want them.

## Outcome

Built and checked live on the worktree dev server (Josh Allen, Puka Nacua, Rhamondre Stevenson, Malik Willis, John Bates, Bryce Young, Trey Smack) at 375px and 1280px, with `npm --prefix web run verify` (994 tests, build) and API `pytest` (5192 passed, CI's dummy `DATABASE_URL`).

Deviations from the draft spec:

- Helper names: `propSectionIds` and `playerLineOnlyGroups`.
- The jump is instant, not smooth: smooth scroll did not run in the preview browser.
- `NflPlayerGameLog` takes `layoutSettled`, so a kicker's market scroll waits for the props block that loads above it.
- Other markets read the whole-week line-only board filtered to the player, so a player with only line-only markets still gets the block.
- The drawers, rows and `useNflDrawerFocus` are untouched; 50b removes them.

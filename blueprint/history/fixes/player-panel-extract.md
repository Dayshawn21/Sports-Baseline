# Player pages: shared panel styles and extract pass

**Type:** Fix

**Source:** the 2026-11-09 cross-sport critique of the NBA, NHL, NFL and tennis
player pages (`.impeccable/critique/2026-11-09T23-31-38Z__web-src-components-shared-playerpageshell-tsx.md`),
ranks 1, 3, 4, 5, 7, 11, 12, 16, 18 and 20. The layout ranks (Season form
frame, record grid, tennis head chips) and the clarify ranks (names, chart
line) are a later pass.

## The problem

PRs #33 to #35 shared the frame, the market tabs and Evidence, but the rest of
each player page is still drawn by sport-specific components:

1. **P0, tennis cold load.** `TennisMarketPanel.tsx` uses the
   `nfl-prop-detail__*` classes but never imports `components/nfl/nfl-prop-detail.css`,
   and `.tennis-prop-seg` lives in `pages/tennis-prop-board-filters.css`, which
   only `TennisPropBoardPage.tsx` imports. Opened first, the tennis panel's
   lines table, section heads and Last 5/Last 10 switch render unstyled.
2. Tennis draws its own recent-form bars (`TennisRecentBars`) and its own
   window/match switch; the other three use `GameLogBars` and `FormSwitch`.
3. Tennis's game log uses `tennis-player-table`; the others use `nfl-player-table`.
4. NFL's projection block is `DetailProjection`, not the shared `PlayerProjectionHero`.
5. Four lines-table implementations, three availability-tag styles, and a
   source footer on NFL and tennis only.
6. Constraint breaches on the way: NFL Goblin/Demon tags are gold and
   orange-red (`nflLabels.ts:41-42`), the prop title `<small>` renders at 10.4px
   (`nfl-player.css:84`).

## The fix

Move the panel primitives into shared files, then point each sport at them.
Display only: no probability, edge, rank, sort, pick, line choice or query
changes. Gray stays gray; the only green allowed is tennis's existing adopted
margin. Class names may stay `nfl-prop-detail__*` / `nfl-player-*` where a
rename would only churn; the point is one stylesheet and one component per job.

Must not break: deep links (`?market=`, `?match=`, `?prop=`, the form window
param), the tennis match switch (legitimate: two matches on one slate), the
tennis Side/Hit/EV columns and NHL's Updated time (kept as optional trailing
columns), per-sport game-log columns, the NBA double-double yes/no list.

## Build steps

- [x] **1. Shared panel stylesheet (P0).** Move the panel primitives
  (section, section-head, lines table, odds-type tag, switch, form chart) out of
  `nfl-prop-detail.css` into `components/shared/player-panel.css`, imported by
  `PlayerPageShell`. Remove the per-sport `.nfl-prop-detail__table td`
  padding overrides in `nba-player.css` / `nhl-player.css` in favor of one
  shared rule. Set `.nfl-player-prop__title small` to 11px.
  *Done when:* a fresh tab opened straight on the tennis player URL shows the
  lines table and section heads styled the same as NBA, and no player page
  shows text under 11px in the panel.
- [x] **2. One switch.** Add `components/shared/SegmentSwitch.tsx` (the
  `FormSwitch` look: squared, gray selected state, at least 44px tall at phone
  width) taking options, value and onChange. `FormSwitch` renders through it;
  tennis's window and match switches and the serve/return surface toggle use it.
  *Done when:* all four pages show the same switch, and the URL params still
  drive it.
- [x] **3. Tennis recent form on the shared chart.** A pure adapter in
  `utils/` turns tennis `recentStatBars` output into the sample shape
  `GameLogBars` reads (opponent short name, date, value, line), with a unit
  test. `PlayerPropTabs` renders `GameLogBars` under the shared
  "Recent form" section head; `TennisRecentBars` stays for the props board.
  *Done when:* the tennis aces chart matches NBA/NFL in height, bar width,
  value labels and axis (opponent plus date), and the adapter test passes.
- [x] **4. NFL projection on the shared hero.** A pure `nflProjectionHero`
  builds a `PlayerProjectionHero` from `NflPropDetailModel` (label, value,
  facts: Model version and Sample, gray delta), with a unit test.
  `NflPlayerPropSection` renders `PlayerProjectionHero`; drop the card-head
  caption that repeats it. `DetailProjection` stays only where the NFL game
  page still uses it.
  *Done when:* the NFL projection block is pixel-identical in structure to
  NBA's, with the same numbers it showed before.
- [x] **5. One lines table.** Add `components/shared/PlayerLinesTable.tsx`:
  fixed core columns (Type, Line, Gap, P(over), P(under)) plus optional
  trailing columns and a selected-row flag, scroll-wrapped on phone, odds-type
  tag always gray. NBA, NHL, NFL and tennis panels render it; NFL's colored
  tags go away.
  *Done when:* the four lines tables share header style, column order and
  row treatment; tennis keeps Side/Hit/EV, NHL keeps Updated.
- [x] **6. Game log, tags and footer.** Tennis `PlayerMatchLog` renders the
  `nfl-player-table` style (sport columns unchanged). Add a shared
  `PlayerTag` (tones: default, caution, out) used by `NbaInjury`, the NHL
  injury and goalie tags and NFL's tags. Add a shared `PlayerFooter` and render
  it on NBA and NHL too.
  *Done when:* the game-log tables and availability tags look the same on all
  four pages, and all four end with the source footer.

## Verify

- `npm --prefix web run verify` and the API tests (the Verify command), with
  new unit tests for the step 3 adapter and the step 4 hero builder.
- Open each player in a fresh tab at 1440 and 375 (Jamal Murray rebounds,
  Adam Fox shots on goal, Josh Allen passing yards week 9, Quentin Halys
  aces) and compare against the critique screenshots: same panel, switch,
  chart, lines table, game log, tags and footer styling; projection numbers,
  P(over), gaps and tennis adopted margins unchanged.
- Re-run `/impeccable critique` on the four pages; Consistency should move
  off 1.

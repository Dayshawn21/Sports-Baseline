# Fix: critique polish (link contrast, tennis reference label, NFL date note, goblin/demon explainer)

**Type:** Fix

## The problem

Small items left by the 2026-11-10 design critique
(`.impeccable/critique/2026-11-10T02-52-21Z__*.md`):

1. **Link contrast.** Bare links (the tennis player "Open match" link in
   `TennisMarketPanel.tsx`) render Ant Design's dark-algorithm default link
   blue `#1668dc` on `#0d0d0f`: 3.7:1, under 4.5:1, and off-palette.
   `antdTheme.ts` sets no link color.
2. **Tennis lines read as picks.** The tennis player lines table shows Hit and
   EV (for example "41%", "+2.0%") with no label saying they are reference.
3. **NFL "dates are UTC".** The Historical usage note on the NFL player page
   says dates are UTC; the app's rule is CT.
4. **Goblin/demon never explained.** The PrizePicks payout tiers appear as type
   tags on every sport's lines table without a word on what they mean.

## The fix

1. Set `colorLink`, `colorLinkHover` and `colorLinkActive` in `APP_ANTD_THEME`
   from the gray tokens in `index.css`. A theme-wide `linkDecoration` would
   underline the nav and tab links, so the underline (meaning not by color
   alone) is scoped to links inside `.nfl-player-muted` in `nfl-player.css`.
   Check other bare links and the tennis ATP pill for regressions.
2. Add a gray text caption above the tennis lines table saying Model, Hit and
   EV are reference, not picks, and that a side to take appears only on an
   adopted line. No number, sort or color changes. The caption shows only when
   every row is a PrizePicks line (`payoutTier` non-null): moneyline and
   sportsbook rows can still carry a colored side, where the text would be
   false (found by `/invariants-review`).
3. The usage window dates are UTC calendar dates computed in the API
   (`app/core/nfl_matchup_context.py`, `start_utc.astimezone(UTC).date()`); no
   kickoff time reaches the web, so a display-only CT conversion is not
   possible. Rewrite the note so it is accurate and plain: dates are UTC
   kickoff dates, so a night game can show the next day. Game pages
   (`NflGameContext`, `NflTeamStatsMatchup`) are out of scope (a later
   game-shell session owns them).
4. In the shared `PlayerLinesTable`, show one fixed caption under the table
   whenever a row is a goblin or demon line. The text comes from a pure helper
   in `web/src/utils/playerPage.ts` with a unit test, so it reads the same on
   every sport.

Must not change any probability, edge, rank, sort or pick. No text under 11px.
Do not touch Home, NHL game props, or game pages/heroes.

## Build steps

- [x] **1. Theme link color.** Done when "Open match" renders gray and
  underlined with at least 4.5:1 contrast, and the ATP pill keeps its color.
- [x] **2. Tennis reference caption.** Done when the tennis lines table shows
  the reference caption above the rows.
- [x] **3. NFL date note.** Done when the Historical usage note no longer reads
  as if UTC were the app's display zone, and explains the UTC date.
- [x] **4. Goblin/demon caption.** Done when any player lines table with a
  goblin or demon row shows the same explainer, and the helper has a passing
  test.

## Verify

- Tennis player page (`/#/tennis/player/36?market=total_tie_breaks&match=98430&prop=336408`)
  and NFL player page (`/#/nfl/player/1477?market=passing_yards&season=2026&week=9`)
  at 1440 and 375.
- `npm --prefix web run verify && cd api && python -m pytest`.

## Outcome

- Item 3 is a copy fix, not a CT conversion: the dates are UTC calendar dates
  computed in the API. Showing CT would need a change in
  `api/app/core/nfl_matchup_context.py`. The NFL game pages still say "UTC";
  left for the game-shell work.
- Verify passed (web 1445 tests and build, API 6043 tests with CI's dummy
  `DATABASE_URL`). Checked in the running app at 1440 and 375 on the tennis
  and NFL player pages, plus the tennis Moneyline tab (no caption).

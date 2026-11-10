# NHL game props: "Other lines" column renders 0px wide

**Type:** Fix

**Branch:** `fix/nhl-props-columns`

## The problem

The NHL game page's Player Props tab (the default tab) draws one table per
market. `web/src/pages/nhl-game.css:27-31` sets widths for six columns that sum
to 100%, but `web/src/components/nhl/NhlGameProps.tsx:26` draws seven when the
market shows P(over) (`covers`). Under `table-layout: fixed`, column 6 ("Other
lines") gets 0 width and prints one character per line: rows near 869px tall,
about 40,000px of page on phone. On phone (`nhl-game.css:66-72`) both Other
lines and Updated get 0px.

Found by the 2026-11-10 design critique
(`.impeccable/critique/2026-11-10T02-52-21Z__web-src-pages-nflgamepage-tsx.md`, P0).

## The fix

Display only. No probability, edge, rank, sort or pick changes; no text below
11px; signal colors stay gray. Hero rules in `nhl-game.css` (lines 2-3, 58-59)
are left alone: a later GamePageShell session owns them.

- A `nhl-prop-table--covers` class on the 7-column table, with its own widths
  (22/9/9/8/12/26/14). The 6-column table keeps a split that sums to 100%.
- Phone (640px and below): "Other lines" moves under the player cell as a
  second line (a `nhl-prop-alt-mobile` block shown only on phone); the Other
  lines and Updated columns are hidden, so the remaining columns share 100%.
- When every row in a market shares the same displayed Updated time, show it
  once in the market's caption and drop the per-row Updated column and the
  phone per-row time. Times stay CT through `nhlTimeLabel`.
- A pure helper `nhlSharedFetchedAt(rows)` in `web/src/utils/nhlLineOnly.ts`
  returns the shared `fetchedAt` when every row's CT label matches, else null,
  with a Vitest test.

## Build steps

- [x] **1. Widths, phone layout, shared timestamp.** Helper plus test, the
  covers class and width rules, the phone second line, and the caption
  timestamp. Done when: at 1440 and 375 every visible props column has nonzero
  width, the NHL game page is a normal length on phone, and Verify passes.

## Verify

- `npm --prefix web run verify && cd api && python -m pytest`
- In the running app, open an NHL game (`/#/nhl/game/57146` or one from
  `/#/nhl`) at 1440 and 375: measure each `th` width and `document.body.scrollHeight`.

## Result (2026-11-09)

- `/#/nhl/game/57146` (12 markets, 165 rows), 1440: every column nonzero,
  Other lines 494-675px, tallest row 76px.
- 375: visible columns all at least 48px, no horizontal scroll, page 20,913px
  (was about 40,000px).
- Verify: `npm --prefix web run verify` (1436 tests, build) and
  `python -m pytest` with CI's dummy `DATABASE_URL` (6043 passed).

# 42b step 3 browser evidence

Checked locally on 2026-10-21 using the running Vite app on port 3001 and
read-only API on port 8000. Hash routes are required by the existing app.

## Live data

- Pass: `http://127.0.0.1:3001/#/nba/board` resolves to October 21, 2026,
  defaulting to Points (157 grouped rows). A fresh document issued exactly
  one application API request, `/api/nba/props`. No slate or per-game fetches.
- Pass: title is `NBA props` with the Lineform suffix; NBA Props is active
  in desktop/mobile view navigation. Phone menu includes NBA Slate / Props /
  Model. Screenshot: `step3-phone-navigation.png`.
- Pass: the date has 11 games and 1,383 player-market rows. Assists has
  136 rows and mounts one table. Counts represent grouped player rows,
  not alternate line counts.
- Pass: AJ Green opens the modelled evidence panel, showing main line 1.5,
  projection 2.0, gap +0.5 and P(over) 59%, with all alternate rungs.
- Pass: Double-double has plain Player, Line, Also, Last 5, Recent, Game,
  Tip / status headers; its drawer says recent results only.
- Pass: selecting a new market updates the URL; browser Back from an open
  assists drawer to Double-double closes the drawer. Date navigation retains
  the market. Previous from October 21 reaches October 20 and shows 33
  Double-double rows; reload preserves that selection. Back and Forward
  restore the corresponding date/market URLs.
- Pass: phone evidence drawer width is 390 pixels at a 390-pixel viewport.
- Pass: final clean default-page reload had no page errors or HTTP errors;
  only the selected market's table was mounted.
- Screenshots: `step3-board-1440.png`, `step3-board-390.png`,
  `step3-drawer-1440.png`, `step3-drawer-390.png`.

An initial interaction script read state before React completed navigation.
Rechecking with URL and destination-table waits confirmed the cases above.
HMR briefly reported missing modules while new source files were being written;
the final clean reload passed. Neither observation is a runtime failure of
the completed step.

## Controlled response cases

These checks intercepted only the board endpoint inside the browser. They
did not change stored data or add product test routes. Intercepts were
removed and the live default board was restored afterward.

- Pass: `date=bad&market=invalid` falls back to Points and requests
  `/api/nba/props` without a date parameter.
- Pass: empty games renders `No NBA games on this date.` A fixture with no
  previous date disables Previous. Screenshot: `step3-fixture-no-games.png`.
- Pass: a game with both line arrays empty displays the no-prop-lines state.
- Pass: a game with only a Double-double line and Points selected displays
  `No points lines on this date.` All known empty markets remain selectable.
- Pass: holding the board response displays `Loading NBA prop board...`.
- Pass: controlled HTTP 503 responses reach the shared error state with Retry;
  releasing a valid response and clicking Retry restores the board.
  Screenshot: `step3-fixture-error.png`. The expected 503 console messages
  belong to this controlled case.
- Pass: with a fixture assists drawer open, a stale-query reconnect refetch
  updated projection 2.0 to 4.0 and gap +0.5 to +2.5 without reopening it.
  To trigger the real query refresh, the browser temporarily advanced
  `Date.now` by six minutes and toggled TanStack's online manager. The original
  clock was restored, then a clean live reload was performed. Model version
  in this fixture was `fixture-refetch-v1`; it is not a validation claim.

## Automated gate and remaining scope

- `npm.cmd --prefix web run verify`: typecheck, 659 tests and production build
  passed. Existing bundle-size warning remains.
- From `api/`, `.venv/Scripts/python.exe -m pytest`: 3,470 passed with the
  existing Starlette deprecation warning.
- `git diff --check`: passed.

Step 4 remains: full board/game parity cases, all target widths, keyboard
focus-return and recorded large-date performance. This step does not claim
Render memory or hosted deployment verification. No commit, push, merge or
deployment was performed.

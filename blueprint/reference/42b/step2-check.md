# 42b step 2 browser evidence

Checked locally on 2026-10-21 with Playwright against Vite on port 3001
and the already-running API on port 8000. The app uses hash routes:
`http://127.0.0.1:3001/#/nba/game/21316`.

## Existing game page

- Pass: modelled table retains Player, Line, Model, Gap, P(over), Last 5,
  Sample headers, with no board-only columns.
- Pass: modelled player opens its evidence panel; Escape closes it.
- Pass: line-only player opens the recent-results-only evidence panel.
- Pass: clean reload at 390 pixels followed by opening both drawer kinds
  produced no page errors or failed network requests. Document width equals
  the 390-pixel viewport. The session's initial favicon 404 is unrelated.
- Screenshots: `step2-game-1440.png`, `step2-game-390.png`.

## Board-table harness

The board route is step 3 work. For step 2 only, a browser-local React root
mounted the real `NbaBoardTable`, inside a MemoryRouter, without writing a
harness file or adding a product route. It used the first 12 modelled raw
lines and first two line-only lines fetched from game 21316. These became
two Points rows and two Double-double rows. A duplicate game with id 99999
and status postponed intentionally repeated those players, producing four
rows in each table. This is controlled fixture evidence, not another real
NBA game or a full-board performance claim.

- Pass: Enter on the first player selected `modelled:21316:points:322612`.
- Pass: the repeated player in the second game selected
  `modelled:99999:points:322612`, independently of the first row.
- Pass: a game link navigated the MemoryRouter to `/nba/game/21316` and
  retained the existing selection instead of opening the clicked row.
- Pass: Enter on the first line-only player selected
  `line-only:21316:double_double:322702`.
- Pass: modelled rows add Game and Tip / status after the existing columns;
  line-only rows remain plain, without projection/gap/probability columns.
- Pass: scheduled fixture tips show `Wed 6:00 PM CT`; postponed fixtures
  show Postponed underneath. Existing row content remains grayscale.
- Pass: document widths equal viewport widths at 1440, 1000 and 390 pixels.
  Screenshots: `step2-board-harness-1440.png`,
  `step2-board-harness-1000.png`, `step2-board-harness-390.png`.

The initial harness setup imported an unversioned router module, creating a
separate router context and causing a harness-only render error. Importing
the same Vite module version as the component fixed the harness. Reloading
restored the real app and the clean-page checks above passed.

## Automated gate

- `npm.cmd --prefix web run verify`: typecheck, 655 tests and production build
  passed. Existing bundle-size warning remains.
- From `api/`, `.venv/Scripts/python.exe -m pytest`: 3,470 tests passed.
  Existing Starlette deprecation warning remains.
- `npm.cmd --prefix web run test -- src/utils/nbaPropBoard.test.ts`: 11 tests
  passed, including fixed-time CT daylight/standard-time, terminal-status
  precedence and missing/invalid tips.

No merge, commit, push, deployment or data mutation was performed.

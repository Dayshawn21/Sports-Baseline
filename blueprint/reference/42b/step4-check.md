# 42b final browser proof

Verified locally on 2026-10-21 on `feature/nba-prop-board-page` with the Vite
development app at `http://127.0.0.1:3001` and the existing local API on port
8000. Read-only requests used the configured database. No provider quota,
database mutation, holdout evaluation or remote action was involved.

## Live board/game parity

For each case, the browser compared all shared table-cell text, every
alternate rung and the complete evidence body, excluding the board's added
game/tip cells and drawer game link. All three comparisons passed in each case.

| Case | Player | Game | Rungs | Result |
|---|---|---|---:|---|
| Eligible assists probability | AJ Green | 21317 | 5 | Pass |
| Projection without probability | Anthony Black, Points | 21316 | 8 | Pass |
| Ineligible projection | Aaron Wiggins, Points | 21316 | 8 | Pass |
| Line-only market | Desmond Bane, Double-double | 21316 | 1 | Pass |

AJ Green showed line 1.5, projection 2.0, gap +0.5, P(over) 59%.
Anthony Black's Points showed line 11.5, projection 9.4, gap -2.1, no
probability. Aaron Wiggins had no projection because of low prior minutes.
Double-double remained recent-results-only. No synthetic cases were needed
for these comparisons.

The first exploratory comparison selected a game's first prop table rather
than the requested market, and read before a market transition completed.
Exact table-label and selected-market waits corrected the checker; the
market-specific comparisons above all matched without changing display logic.

## Responsive and keyboard proof

Both Assists and Double-double were checked at 1440, 1000 and 390 pixels.
Screenshots follow `step4-<assists|double_double>-<rows|drawer>-<width>.png`.
Final drawer captures wait for the opening animation to finish.

- Pass: Enter opens the selected player's drawer; Escape closes it and
  returns focus to that player's button at all six width/market combinations.
- Pass: closing immediately after opening also restores focus. Opening by
  clicking another cell in the row and using the Close button restores focus
  to the corresponding player button.
- Pass: repeated Tab cycles within the open drawer (sentinel, Close button,
  game link, sentinel), and Escape then returns to the player button.
- Pass: desktop/tablet drawers are 460 pixels wide; phone drawers are 390
  pixels wide with left edge x=0. Every drawer's right edge matches its viewport.
- Pass: document widths were 1425, 985 and 375 pixels for 1440, 1000 and 390
  viewports, respectively; the remaining 15 pixels are the scrollbar gutter.
  There was no horizontal page overflow.
- Pass: final clean reload and interaction session recorded no page errors
  or HTTP errors.

The check found a real focus-return gap: rc-drawer can restore its saved
target after the application callback, and an early Escape can close before
the opening animation completes. The fix captures the row's player button,
restores it on close, and repeats restoration after the drawer's close motion
on the next animation frame. Disconnected targets are ignored after navigation.
The UI behavior was verified in the browser, as required for component work.

Navigation, date/market reload/history, invalid URL fallbacks, missing adjacent
dates, loading/error/retry and the three empty states passed in
`step3-check.md`; the focus fix changes none of those data/control paths.

## Completeness and ordering

For each market, browser DOM row keys exactly equaled the full ordered
assembler output. Each mounted one table, and its final row was reachable
by scrolling. No truncation or pagination was introduced.

| Market | Grouped rows |
|---|---:|
| Points | 157 |
| Rebounds | 151 |
| Assists | 136 |
| 3-pointers made | 145 |
| Blocks | 116 |
| Points + rebounds + assists | 155 |
| Points + rebounds | 147 |
| Points + assists | 132 |
| Rebounds + assists | 135 |
| Double-double | 109 |
| Total | 1,383 |

## Local performance observations

The actual October 21 response contained 11 games, 7,986 modelled raw lines
and 111 line-only raw lines, totaling 4,877,159 UTF-8 bytes. These are the
same payload size/counts recorded by 42a.

- A separate browser fetch/read took 1,787 ms; parsing JSON took 6.5 ms.
- Five direct pure-assembly timings were 4.0, 4.3, 3.8, 3.3 and 3.5 ms.
- In a separate fresh navigation, the API resource took 1,606 ms. The first
  row's next animation-frame observation was at 2,584 ms from navigation,
  433 ms after the API response ended. This includes JSON processing,
  development React rendering and browser scheduling.
- Without precise coverage enabled, three market click-to-next-frame samples
  were 207, 199 and 361 ms. The drawer-content next-frame observation was
  239 ms. These are local development observations, not production benchmarks
  or guaranteed latency bounds.
- A separate Chrome precise-coverage session observed four assembler calls
  during initial loading (empty and loaded inputs under React StrictMode).
  Taking and resetting coverage, then switching market and opening a drawer,
  recorded no further `nbaPropBoard` calls. Memoization prevents full-data
  assembly during those interactions. An initial profiled timing run was
  slower (564 ms pill, 379 ms drawer) and was excluded from unprofiled figures.

The page remained usable, with only the selected market mounted and all
rows accessible. No backend contract change, virtualization or cache was
needed for the observed case. Render's 512 MB memory and hosted response
performance have not been exercised; this frontend check does not clear
42a's production-memory follow-up.

## Final automated gate and handoff

- `npm.cmd --prefix web run verify`: typecheck, 659 tests and production build
  passed after the focus fix. Existing large-bundle warning remains.
- From `api/`, `.venv/Scripts/python.exe -m pytest`: 3,470 passed with the
  existing Starlette deprecation warning.
- `git diff --check`: passed.
- Findings ledger: no open/fixed P0 or P1. F-09 (P3) and F-12 (P2) remain
  unrelated unverified follow-ups; this feature changes no model or verdict.
- The ignored local employer interview guide was updated to describe the
  board as implemented and locally verified, with final review/deployment
  pending. It must never be staged.

Manual try: open `http://127.0.0.1:3001/#/nba/board?date=2026-10-21&market=assists`,
open AJ Green, inspect alternate rungs, close with Escape, select Double-double,
open a player, then navigate dates. Expect gray reference rows, CT tips and
the market preserved in adjacent-date links.

Step 4 was approved on 2026-10-21 and completion was requested. At the end of
verification, no commit, merge, push or deployment had been performed.
`/complete` archives and commits the feature after review and requires
approval for merge and a separate approval for push.

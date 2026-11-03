# Fix: NFL player link carries the week it was opened from

**Type:** Fix
**Status:** complete (2026-11-03)
**Branch:** `fix/nfl-player-week-context` (this worktree, off master `76e4cf68`)
**Follows:** 50b (NFL rows open the player page)

## The problem

`nflPlayerMarketLink(playerId, market)` returns `/nfl/player/:id?market=...` with no
season or week. `NflPlayerPage` then loads the slate and other-markets for
`detail.data.season/week`, and the API's `GET /nfl/players/:id` always resolves
`get_current_week(now)`. So a row opened from the prop board with a past or future
week picked (or from that week's game page) lands on the current week's lines: wrong
lines, wrong "other markets", and a Back crumb that points at the wrong game or slate.

## The fix

Carry the week in the link and read it on the page. Backend untouched.

- `nflPlayerMarketLink(playerId, market, week?)` where `week` is `{ season, week } | null`.
  When given it appends `season` and `week` params; when null the link is unchanged, so
  existing callers and links keep working.
- `NflPlayerPage` reads `season` and `week` from the query (both must parse as integers,
  otherwise ignored) and passes them to `useNflSlate` and `useNflOtherMarkets` in place of
  `detail.data.season/week`. With no params it behaves exactly as today.
- Every caller passes the week it is showing:
  - `NflPropBoardPage` (board table and line-only table): its `activeSeason`/`activeWeek`
  - `NflGameProps` (digest links and rows): the game page's `detail.season/week`
- `playerSearch` already preserves unknown params, so `season`/`week` survive a market or
  form change on the player page.

**Must not break**
- Links with no week (bookmarks, other pages) still open the current week.
- The profile, depth chart, injury and season game log stay "as of the current week"; the
  API still serves them that way. The header keeps saying so and does not claim the
  linked week for them.
- HashRouter: params go in the query string, never a `#anchor`.

## Build steps

- [x] **Step 1 - Link and page.** Extend `nflPlayerMarketLink`, add a small
  `playerWeekParams(params)` parser in `nflPlayer.ts`, use it in `NflPlayerPage`, and pass the
  active week from the callers (`NflPropTable`, `NflLineOnlyTable`, `NflGameProps`). Tests in
  `nflPlayer.test.ts`: link with and without a week, `market` still encoded, parser accepts
  valid integers, rejects missing, partial (season without week) and non-numeric values.
  *Done when:* `npm --prefix web run verify` passes and the new tests cover the link and
  the parser.

## Verify

1. Run the web dev server and API. On `/nfl` pick a past week on the prop board, click a row:
   the URL has `season` and `week`, and the lines and Back crumb belong to that week's game.
2. From a game page of a different week, click a digest item and a row: same.
3. Open `/nfl/player/<id>?market=receptions` by hand: unchanged, current week.
4. Edit the URL to `week=abc` or drop `season`: falls back to the current week, no error.

## Notes for the AI

- Do not touch the API or add a route param; the backend week is out of scope.
- If the header's "Week N" and the linked week can differ visibly, say which is which; do
  not silently relabel the profile as the linked week.
- No em dashes in code, comments or the commit message.

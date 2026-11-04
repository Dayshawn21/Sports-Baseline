# Feature: NHL prop board

**From build-plan:** feature 56a (item 56 added to `build-plan.md` and `project-overview.md` on 2026-11-04 with owner approval)
**Status:** complete (2026-11-04)
**Type:** Feature
**Branch:** `feature/nhl-prop-board`

## Goal

Give NHL a Props view at `/nhl/board`, the NBA board's counterpart: one Eastern
date's stored PrizePicks full-game lines, one market at a time, as dense gray
rows that open the NHL player page. NHL has no projection, so every row is
line-only: no gap, no P(over), no rank, no pick wording. This is the first
sub-feature of proposed item 56 (NHL prop board and model); the projection and
Model page come later (see Sizing).

## Sizing and the Model page (decision for the owner)

A Model page grades something, and NHL has nothing to grade: no projection, no
frozen predictions (`NhlPropSource` is line-only and not in `PROP_SOURCES`), no
NHL backtest under `api/app/backtest/`. Building the page first would mean a
placeholder. Recommended order, each its own branch, spec and merge:

| Sub-item | Delivers | Size |
|---|---|---|
| **56a** (this spec) | `GET /nhl/props?date=` and `/nhl/board`, line-only, registers the `props` view | Medium, 5 steps |
| 56b | NHL projection backtest harness: reference arm (plain recent average), a pre-registered adoption rule fixed before any variant is scored, 2024-25 development, 2025-26 holdout scored once; backtest only, nothing served | Large, its own spec |
| 56c | Serve the reference projection (and P(over) only for markets that pass a pre-registered calibration check) on the board and game page; `NhlPropSource` becomes a full `SportPropSource`, joins `PROP_SOURCES`, a freeze workflow | Large |
| 56d | NHL forward ranking check through the shared `prop_ranking` pipeline, `GET /nhl/model/ranking`, `/nhl/model` registering the `model` view; home record card and the NBA card's "NHL has no model page" line change | Medium |

**Recommendation:** register no `model` view until 56d. Until then the NHL nav
and home card show Slate and Props only, and the NBA record card keeps saying
NHL has no model page, which stays true. The alternative, a "no model, line-only"
Model page with data coverage now, is cheap (one page, no endpoint) but is
exactly a placeholder, and it would have to be rewritten in 56d. If the owner
wants it anyway, it is a small separate item, not part of 56a.

Forward accrual limits 56d: PrizePicks NHL lines exist only from 45c's first
snapshots (October 2026), so the ranking check starts "Accruing" like NBA's did
and cannot adopt a slice for weeks after 56c freezes predictions. Do not
promise an NHL record date.

## Plan changes (approved and written 2026-11-04)

`blueprint/build-plan.md`, after item 55 (next unused whole number), unchecked:

```
- [ ] 56. **NHL prop board and model** - NHL gets a Props view at `/nhl/board` and, once there is a record to grade, a Model view at `/nhl/model`, on the NBA pattern (42, 20g): the board is stored PrizePicks lines only; a projection is added only through a pre-registered backtest, then served, frozen and graded by the shared forward ranking check; everything stays gray reference until a slice reads `adopt`
  - [ ] 56a. **NHL prop board** - `GET /nhl/props?date=` and `/nhl/board` as NHL's Props view: one Eastern date's linked full-game lines by market, ordered by puck drop then player, gray and unranked, rows open the player page; no projection
  - [ ] 56b. **NHL projection backtest harness** - reference arm, pre-registered adoption rule, 2024-25 development and 2025-26 holdout scored once; backtest only, nothing served
  - [ ] 56c. **NHL projection served and frozen** - the reference projection (and P(over) where a pre-registered check passes) on the board and game page; full `SportPropSource`, `PROP_SOURCES`, freeze workflow
  - [ ] 56d. **NHL ranking check and Model page** - forward ranking check through the shared pipeline and `/nhl/model` registering the `model` view; home record card
```

`project-plan.md`: no change (no new direction, users, data source, stack,
monetization or deployment). `project-overview.md`: regenerate with `/overview`
after approval so item 56 and the 45 line ("model page and prop board are
added as later sub-items") agree.

## Design reference

None to capture: it copies `/nba/board` and the NHL game page's prop tables.
Pattern files: `web/src/pages/NbaPropBoardPage.tsx`,
`web/src/components/nba/NbaPropBoardMarket.tsx`, `web/src/utils/nbaPropBoard.ts`,
`web/src/pages/nfl-prop-board.css` and `nba-prop-board.css`,
`web/src/components/nhl/NhlGameProps.tsx`, `web/src/utils/nhlLineOnly.ts`.

## In scope

- Read-only `GET /nhl/props?date=YYYY-MM-DD` returning the date's served games
  (REG/PST, as the slate) with each game's line-only lines and the slate's
  date default and previous/next dates.
- `/nhl/board` page: shared `PageHead` with date navigation, market pills with
  counts, rows ordered by puck drop then player name, game and puck-drop columns,
  Standard line plus other rungs as on the game page, a link to the player page
  at the row's date and market, empty and loading and error states.
- `props: '/nhl/board'` in `SPORTS` and `SPORT_PAGES`, so the top bar, drawer,
  document title and the home NHL card's view links pick it up (their links come
  from `sportViews`, so the home needs no code change).
- Docs: `docs/nhl-display.md` route and endpoint tables.

## Out of scope

- Any projection, gap, P(over), rank, sort by value, flag, color or "pick"
  wording; mini form bars and the evidence drawer (they need history reads and
  belong with 56c).
- The Model view, `/nhl/model`, ranking endpoint, home record card (56d).
- Injury or goalie tags on board rows (the game page already shows them; a
  later display item can add them).
- A board response cache. NBA's exists because modelled assembly is heavy; the
  NHL board is one date-wide read. Step 4 records size and timing, and a cache
  is added only if the numbers call for it.
- Ingest, migrations, workflows, any holdout read.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.

Never accept a step you haven't read. If a diff is too big to review, split it.

## Build steps

- [x] **Step 1 - Date-wide read and board service (API)** - `get_date_line_only_lines(db, date)` in `app/repositories/nhl.py` using the same `_latest_props` predicate as the game read (NHL sport, PrizePicks, full-game, linked, non-null offering id, strictly before a known puck drop), grouped by game id; `app/services/nhl/prop_board.py` building the board from the slate's `slate_date` / `adjacent_dates`, the date's served games and `line_only_props` per game; schemas `NhlPropBoardGameSchema` and `NhlPropBoardResponse`. *Done when:* a unit test over fixed rows proves each board game's lines equal what `line_only_props` returns for that game (parity), ordering is stable, a game with no lines has an empty list, and a game with an unknown start still serves its latest lines; `pytest` passes.
- [x] **Step 2 - Route** - `GET /nhl/props` in `app/routers/nhl.py` (public read like the slate, camelCase, 422 on a bad date, 200 with empty games on an empty date). *Done when:* `curl` on a stored 2026-10-23 and 2026-10-24 date returns the games with line counts equal to the slate's `propLineCount` per game; a bad date gives 422; the response carries no projection field; the route is registered in the same router test the other NHL reads use.
- [x] **Step 3 - Web types, transport, hook, board util** - `NhlPropBoardResponse` in `types/nhl.ts`, `fetchNhlPropBoard` in `api/nhl.ts`, `useNhlPropBoard` (key `['nhl','prop-board',date]`, 5 minute `staleTime`), `utils/nhlPropBoard.ts` (market groups reusing `nhlPropListGroups`, puck-drop-then-player order with null starts last, `nhlBoardPath`, default market, game labels in CT). *Done when:* `nhlPropBoard.test.ts` covers ordering, null start last, an unknown `?market=` falling back to the default, a market with zero rows still listed, alternates grouping per player, and the path builder; `npm run test` passes.
- [x] **Step 4 - Page and registration** - `NhlPropBoardPage`, a market table component and `nhl-prop-board.css` (reusing the NFL/NBA board classes), `props: '/nhl/board'` in `SPORTS` and `SPORT_PAGES`, updates to `sportNav.test.ts` expectations. Legend reads "Reference only, no picks. Stored PrizePicks lines, no projection; rows follow puck drop, then player name, and are not ranked." *Done when:* `npm run build` and `sportPages.test.ts` pass; in the running app `/#/nhl/board?date=2026-10-24&market=points` shows the date's rows with pill counts equal to the API, every value gray, a row opens `/nhl/player/:id?date=&market=`, an empty date shows its empty message, an API failure shows `ErrorState`, no horizontal overflow at 375 px; the top bar and drawer list NHL Slate and Props, the home NHL card links Slate and Props, and the NBA record card still says NHL has no model page. Record response bytes and timing for the busiest stored date.
- [x] **Step 5 - Docs and verify** - add `/nhl/board` and `GET /nhl/props` to `docs/nhl-display.md`; update the local employer interview guide if present (NHL now has a props board, still line-only); run the Verify command. *Done when:* Verify passes and `/invariants-review` reports no sport-filter, provider-filter or gray-color violation.

## Files / areas

- API: `app/repositories/nhl.py`, new `app/services/nhl/prop_board.py`, `app/schemas/nhl.py`, `app/routers/nhl.py`, new `tests/test_nhl_prop_board.py`.
- Web: `src/types/nhl.ts`, `src/api/nhl.ts`, `src/hooks/useNhl.ts`, new `src/utils/nhlPropBoard.ts` (+ test), new `src/pages/NhlPropBoardPage.tsx`, new `src/components/nhl/NhlPropBoardMarket.tsx`, new `src/pages/nhl-prop-board.css`, `src/utils/sportNav.ts` (+ test), `src/routes/sportPages.tsx`.
- Docs: `docs/nhl-display.md`.

## Data / contracts

- `NhlPropBoardResponse { date, previousDate, nextDate, games: NhlPropBoardGame[] }`; `NhlPropBoardGame { gameId, awayTeam, homeTeam, startUtc, status, lines: NhlLineOnlyLine[] }`. **Load-bearing:** `lines` is the game endpoint's `NhlLineOnlyLine` unchanged, so 56c can add optional projection fields on both without reshaping the board.
- Every query is NHL-scoped (`sport = 'nhl'`) and PrizePicks-scoped; the odds provider filter is not involved (no odds on the board). No history is read, so no history floor applies; no holdout season is read; no migration.
- Dates are Eastern calendar dates; times display in CT, as the slate and game page.

## Testing

- Python: parity and ordering test for the board service (pure, fixed rows, no DB), per the logic-test gate; repository SQL is verified live, not unit tested.
- Web: Vitest for `nhlPropBoard.ts` and the `sportNav` registry expectations; `sportPages.test.ts` already forces a page for every promised view. Page and table are verified by running the app and `npm run build`.
- Live: API from this worktree with the selector-loop launcher and the database URL passed through the environment (never printed); `npm ci` in `web/` first.

## Notes for the AI

- Gray reference only: no green, no "pick", "edge", "value" or "best" wording, no sort by anything but puck drop then name. NHL has no adopted slice.
- Reuse, do not copy, `nhlPropListGroups`/`nhlOddsTypeCounts`; follow the `/nba/board` page structure, not its modelled-row code.
- No em dashes in code, docs or commits; comment the why only; ask before committing; no AI attribution lines beyond the project's rule.
- Keep the 512 MB API in mind: one date-wide query, no per-game fan-out, no model or history work on the request path.

## Results

- Step 1 to 5 built; Verify passed (web `npm run verify`: `tsc -b`, 1,204 tests, build; API `pytest`: 5,527 passed). `/invariants-review` reviewer: no findings.
- Live check on stored dates 2026-10-23 (2 games, 495 lines, 111 KB) and 2026-10-24 (12 games, 3,416 lines, 764 KB, about 0.57 s): per-game line counts equal the slate's `propLineCount`, game 57029's lines equal its own endpoint, `?date=nope` gives 422, no projection field in the response.
- Browser: pill counts sum to the API's 1,781 rows for 2026-10-24; rows open `/nhl/player/:id?date=&market=`; empty date and API failure states render; 375 px has no overflow; no green; top bar and home NHL card list Slate and Props; the NBA record card still says NHL has no model page.
- No response cache was added (764 KB, sub-second). The NHL player page does not read the board arrival marker, so its Back goes to the slate (out of scope).
- The employer interview guide is not present in this checkout, so it was not updated.

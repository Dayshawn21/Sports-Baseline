# Feature: NHL starting-goalie filter

**From build-plan:** feature 64c (parent 64, Context filters on the prop boards)
**Branch:** `feature/nhl-starting-goalie` (worktree `.claude/worktrees/board-filters-3c35d4`)
**Status:** complete (2026-11-11)

## Goal

Let a user narrow `/nhl/props` to games where the starting goalie is known:
"Starting goalie: Confirmed" keeps skater rows whose opponent's starter is
confirmed and goalie rows for that game's confirmed starter. The idea comes
from PickFinder's context filters. Display only: it chooses which rows show,
never a projection, gap, P(over), rank, sort or color.

## In scope

- One pure util, `web/src/utils/nhlGoalieFilter.ts`, with tests: the URL
  param, a per-game goalie lookup built from the slate, and the row filter.
- A "Starting goalie" control on the NHL board (Any / Confirmed / Confirmed or
  expected), held in the URL as `?goalie=confirmed|known`, so reload and Back
  from a player page keep it. It composes with the player, team and game
  filters, and the empty state names it.
- The goalie context comes from the slate the app already serves for the same
  date (`useNhlSlate`, cached `GET /nhl/slate`), joined to the board by
  `gameId`.

## Out of scope

- **Adding goalies to `/nhl/props`.** The board body is a cached JSON snapshot;
  the slate already carries the same context, so no API change. If a later
  feature needs it on the board itself, that is its own change.
- **Filtering by a named goalie** ("vs Shesterkin") or by goalie quality: new
  evidence, not a status filter.
- The opposing-goalie projection adjustment (item 67, another session's
  backend work). This filter changes no projection.
- The NHL game page, player page and slate; the NBA and NFL boards.
- Any API, ingest or schema change.

## Data source (checked 2026-11-11)

- `NhlSlateGame.context.goalies` (`NhlGoalieContext`): `freshness`,
  `fetchedAt`, and `away` / `home` sides, each `{ team, playerId, playerName,
  status }` with `status` one of `confirmed`, `expected`, `unknown`,
  `not_reported`, `unavailable`. Side `team` uses the game's own codes (the
  player page already matches `goalies.away.team === player.opponent`).
- The board's games and the slate's games share `gameId` (both `sport_games`).
- The client already grades report age with `nhlContextFreshness(report,
  startUtc, now)` in `utils/nhlContext.ts` (stale after 6 hours, unavailable
  when missing or fetched after puck drop). The filter uses it, so a side
  counts only from a `fresh` report.
- Last report before puck drop, last 30 days (read-only query, 2026-11-11):
  188 sides `confirmed`, 92 `expected`. So both choices narrow the board in
  practice.
- Goalie rows are the `goalie_saves` and `goals_allowed` markets, the set
  `utils/nhlPlayer.ts` already holds as `GOALIE_MARKETS`.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - The util and its tests** - export the existing
  `GOALIE_MARKETS` from `utils/nhlPlayer.ts` (no other change there), and add
  `nhlGoalieFilter.ts` exporting:
  - `NhlGoalieFilter = 'any' | 'confirmed' | 'known'` and
    `NHL_GOALIE_FILTERS` (labels Any, Confirmed, Confirmed or expected).
  - `parseGoalieFilter(params)`: an unknown or missing value reads as `any`.
  - `goalieSides(slateGames, now)`: a map from `gameId` to its two sides, each
    game kept only when `nhlContextFreshness` of its goalie report is `fresh`.
  - `filterStartingGoalie(markets, filter, sides)`: for `any` returns the
    markets unchanged. Otherwise a skater row passes when its opponent side
    (the side that is not `gameSideTeam(row.team, game)`) has an allowed
    status; a goalie-market row passes when its own side has an allowed
    status and that side's `playerId` is the row's player. `confirmed` allows
    `confirmed`; `known` allows `confirmed` and `expected`. A row whose side
    cannot be resolved, or whose game is not in the map, never passes. Every
    market stays, emptied ones included.

  *Done when:* `nhlGoalieFilter.test.ts` covers each status under each choice,
  a skater judged by the opponent's goalie (not his own), a goalie row kept
  only for the listed starter (the backup dropped), a goalie row whose starter
  is unlinked (`playerId` null) dropped, stale and unavailable reports never
  passing, a game missing from the slate never passing, an unresolved team
  never passing, `any` returning the input unchanged, unknown params reading
  as `any`, and composition after `filterBoardMarkets`; fixed `now` only;
  `npm run test` passes. No UI yet.
- [x] **Step 2 - Control, slate join and URL** - `NhlPropBoardPage` loads
  `useNhlSlate(board date)` once the board has resolved its date, builds the
  sides map, reads `goalie` from the URL, applies `filterStartingGoalie` after
  `filterBoardMarkets`, counts it in the `visibleMarket` filtering flag, lists
  player names from the narrowed rows, and passes a "Starting goalie" antd
  `Select` into the `BoardFilterBar` slot 64b added. While the slate is
  loading or has failed, the select is disabled with the placeholder "Goalie
  reports loading" or "Goalie reports unavailable" and the filter is not
  applied (a `goalie` value in the URL is kept, not dropped). The no-match
  empty state adds "or starting goalie".
  *Done when:* on a live date with reports, Confirmed and Confirmed or expected
  each narrow the board, the URL shows `goalie=`, reload and Back from a player
  page keep it, Any restores the board, it combines with the team and game
  filters, a goalie market shows only listed starters, the NBA board looks
  unchanged, the bar wraps at 375px with no horizontal scroll, the network tab
  shows one `/nhl/slate` request per date (not one per filter change), and the
  console has no errors.
- [x] **Step 3 - Verify** - *Done when:*
  `npm --prefix web run verify && cd api && python -m pytest` passes and
  `invariants-review` finds no gray-color, rank or sort change.

## Files / areas

- New: `web/src/utils/nhlGoalieFilter.ts`, `web/src/utils/nhlGoalieFilter.test.ts`.
- Edit: `web/src/pages/NhlPropBoardPage.tsx`; `web/src/utils/nhlPlayer.ts`
  (add `export` to `GOALIE_MARKETS` only).
- No API, schema, migration or ingest file; `BoardFilterBar` already has the
  slot from 64b.

## Data / contracts

- **Load-bearing:** URL param `goalie` is `confirmed` or `known`; absent or
  anything else means Any. Same rules as 64a and 64b.
- The board now makes one extra cached request, `GET /nhl/slate?date=`, which
  is on the heavy rate-limit list but served from `cached_slate`; TanStack
  Query caches it for 5 minutes like the board.

## Testing

- Logic with tests: Step 1 (listed in its done-when), fixed timestamps only.
- No component tests (project standard): Step 2 is checked in the browser on a
  live board, including 375px and the network tab.
- Final gate: the Verify command in `AGENTS.md`.

## Notes for the AI

- A goalie side in a stale report reads as unknown here, matching how the
  projection treats stale context (`context_stale` in `core/nhl_projection.py`).
- Another session (nhl-goalie-skaters, item 67) is changing NHL backend
  backtest files; this feature touches only web files, so there is no overlap.
- This worktree has no `api/app/.env` or `api/.venv`: run pytest with the main
  checkout's venv and `DATABASE_URL=postgresql://localhost/ci`, and for the
  browser check start an API on a free port from a scratchpad launcher that
  reads the main `.env`.
- No em dashes; gray means reference; TanStack Query hooks only (reuse
  `useNhlSlate`, no new hook).

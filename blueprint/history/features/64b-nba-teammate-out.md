# Feature: NBA teammate-out filter

**From build-plan:** feature 64b (parent 64, Context filters on the prop boards)
**Branch:** `feature/nba-teammate-out` (worktree `.claude/worktrees/board-filters-3c35d4`)
**Status:** complete (2026-11-11)

## Goal

Let a user narrow `/nba/props` to the players whose teammate is not playing
tonight: pick "Teammate out: Joel Embiid (PHI)" and the board shows only the
other Philadelphia players in that game. The idea comes from PickFinder's
"without teammate" filter. Display only: it chooses which rows show, never a
projection, gap, P(over), rank, sort or color.

## In scope

- One pure util, `web/src/utils/nbaTeammateOut.ts`, with tests: the option
  list, the URL param, and the row filter.
- A "Teammate out" select in the NBA board's filter bar, held in the URL as
  `?out=<espnAthleteId>`, so reload and Back from a player page keep it.
- It composes with the existing player, team and game filters, and the empty
  state names it.

## Out of scope

- **"Key" ranking.** The board carries no minutes or usage, so the filter does
  not decide who is key. It lists every player ESPN has as not playing, with
  their team, and the user picks. A usage-based shortlist would need new data.
- **With-or-without history** (how a player did in past games without that
  teammate). That is new evidence, not a filter over loaded data.
- Choosing more than one teammate at once. One `out` value; a later change
  could allow several.
- Day-To-Day players: ESPN's only other status, and not a confirmed absence.
- NHL (64c), the NFL board, the NBA game page and player page.
- Any API, ingest or schema change.

## Data source (checked 2026-11-11)

- `GET /nba/props` already returns `games[].injuryReport` (`NbaInjuryReport`:
  `freshness`, `fetchedAt`, `injuries[]` with `espnAthleteId`, `playerId`,
  `playerName`, `team`, `athleteTeam`, `status`).
- The server (`app/services/nba/injuries.py` `injury_report`) already keeps
  only entries on the game's two teams, already writes `team` in the game's
  own codes (the ones in `awayTeam` / `homeTeam`), and already returns an
  empty, `unavailable` report when the snapshot is missing or taken after tip.
- Statuses stored in the last 200 snapshots (read-only query, 2026-11-11):
  `Out` 5,610, `Day-To-Day` 1,621, `Suspension` 3. So "not playing" means
  `Out` or `Suspension` (compared case-insensitively); about 28 such entries
  a snapshot across the league.
- Board rows carry `playerId` and a PrizePicks `team` code, mapped to the
  game's side with the existing `gameSideTeam`.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - The util and its tests** - `nbaTeammateOut.ts` exporting:
  - `NbaTeammateOutOption = { id, playerId, playerName, team, gameId, status, stale }`,
    where `id` is the `espnAthleteId`.
  - `teammateOutOptions(games)`: one option per not-playing entry, skipping
    entries whose `athleteTeam` is set and differs from `team` (ESPN filed a
    moved player under another team; the server's `injury_index` skips them
    too), entries whose `team` is not one of the game's two codes, and reports
    that are `unavailable`; `stale: true` when the report is `stale`;
    deduplicated by `id` and `gameId`; sorted by team, then name.
  - `parseOutFilter(params)` (digits only, else none) and
    `activeOutFilter(value, options)`: an id that is not among today's options
    (an old link) reads as no filter.
  - `filterTeammateOut(markets, option)`: keeps rows in the option's game whose
    `gameSideTeam(row.team, game)` equals the option's team, dropping the out
    player's own rows by `playerId` when it is linked; every market stays,
    emptied ones included, as `filterBoardMarkets` does; a null option returns
    the markets unchanged.

  *Done when:* `nbaTeammateOut.test.ts` covers `Out` and `Suspension` kept
  (any letter case), `Day-To-Day` dropped, the moved-athlete and wrong-team
  entries dropped, an unavailable report giving no options, a stale report
  marked, the sort, the dedupe, a garbage or unknown `out` id reading as none,
  the row filter keeping only that team's teammates in that game (other game,
  other team and the player himself dropped, a PrizePicks code that differs
  from the game's code still matched through `gameSideTeam`), a null
  `playerId` entry dropping nobody by id, and composition after
  `filterBoardMarkets`; `npm run test` passes. No UI yet.
- [x] **Step 2 - Control and URL** - `BoardFilterBar` takes an optional
  `children` slot after the game picker (NFL and NHL pass nothing, so their
  bars are unchanged). `NbaPropBoardPage` reads `out` from the URL, renders an
  antd `Select` labeled "Teammate out" (allowClear; options read like
  `Joel Embiid (PHI, Out)`, with ", stale report" added when stale; disabled
  with the placeholder "No players listed out" when there are no options),
  applies `filterTeammateOut` after `filterBoardMarkets`, counts it in the
  `visibleMarket` filtering flag, lists player-picker names from the narrowed
  rows, and adds "or teammate out" to the no-match empty state.
  *Done when:* on a live date with listed absences, choosing a player narrows
  the board to his teammates in that game, the URL shows `out=`, reload and
  Back from a player page keep it, clearing restores the board, it combines
  with the team and game filters, the NFL and NHL boards look unchanged, the
  bar wraps at 375px with no horizontal scroll, and the console has no errors.
- [x] **Step 3 - Verify** - *Done when:*
  `npm --prefix web run verify && cd api && python -m pytest` passes and
  `invariants-review` finds no gray-color, rank or sort change.

## Files / areas

- New: `web/src/utils/nbaTeammateOut.ts`, `web/src/utils/nbaTeammateOut.test.ts`.
- Edit: `web/src/components/shared/BoardFilterBar.tsx` (optional slot only),
  `web/src/pages/NbaPropBoardPage.tsx`, and `nfl-prop-board.css` only if the
  new select needs a width rule.
- No API, schema, migration or ingest file.

## Data / contracts

- **Load-bearing:** URL param `out` holds one ESPN athlete id (digits); absent,
  unknown or not on today's board means no filter. Same rules 64a set for its
  params.
- `NbaTeammateOutOption` stays inside the util and the page; nothing stores it.

## Testing

- Logic with tests: Step 1 (listed in its done-when), fixed timestamps only.
- No component tests (project standard): Step 2 is checked in the browser on a
  live board, including 375px.
- Final gate: the Verify command in `AGENTS.md`.

## Notes for the AI

- ESPN filed-under-team versus athlete-team disagreements are real (the game
  page explains them); skip those entries rather than guess a side.
- Sibling worktrees are editing the prop boards in parallel (board-ui-polish,
  record strip, prop reasons). Keep the `BoardFilterBar` change to an optional
  slot and expect a rebase on `NbaPropBoardPage.tsx`.
- This worktree has no `api/app/.env` or `api/.venv`: run pytest with the main
  checkout's venv and `DATABASE_URL=postgresql://localhost/ci`, and for the
  browser check start an API on a free port from a scratchpad launcher that
  reads the main `.env` (port 8000 may be another session's API).
- No em dashes; gray means reference; TanStack Query hooks only (no new hook).

# Feature: NBA teammate-out split on the player page

**From build-plan:** feature 69 (added 2026-11-12, owner-approved)
**Branch:** `feature/69-nba-teammate-split` (worktree `.claude/worktrees/silly-noether-01b517`)
**Status:** complete (2026-11-12)

## Goal

Move "how does this player do when teammate X is out" from the NBA prop
board to the NBA player page, where it belongs to one player. In each market
tab, the user picks a teammate the game's ESPN report lists as Out or
Suspension and sees this season's played games split into with him and
without him: games, average, times over tonight's standard line, and the
without games as bars. The props-page "Teammate out" filter (64b) is removed.
Display only and gray reference: no projection, P(over), rank, sort, version
or color change.

## In scope

- One optional, read-only field `teammateSplit` on `GET /nba/players/{id}/props`.
- A pure `app/core/` classifier (with, without, before he joined) with tests.
- A tested web util for the per-market split and the `?out=` param.
- A "Teammate out" picker and a split section in each NBA player market tab.
- Removing the props-page filter and its util and tests.
- Phone layout of the shared board filters (owner request 2026-11-12): every
  dropdown the same width and height, labels aligned the same way, and a clear
  control that is easy to tap.

## Out of scope

- Last season's games (owner kept this season only; small samples are labelled).
- Teammates not on today's report (no free roster picker), Day-To-Day players,
  and ESPN entries with no linked `playerId` (there are no rows to split).
- Choosing more than one teammate at once.
- Any projection, P(over) or minutes change (65 tried that and was rejected).
- NFL, NHL and tennis player pages; the NBA game page.
- Any migration, ingest or snapshot change.

## Data source (checked 2026-11-12, read-only)

- Of 13,053 completed-game cases where ESPN listed a linked player Out or
  Suspension, the box score held **no row** for him in 12,962 (99.3%), a
  did-not-play row in 54 and a played row in 37. So "with" means the teammate
  has a played row (`NOT did_not_play`) for this team in that game, and
  "without" means he does not.
- Because a missing row also means "not on the team yet", "without" counts only
  games dated on or after the teammate's first `nba_player_game_stats` row (any
  row, any season) for this team. Earlier games are "before" and excluded. A
  teammate with no row for this team gets no split and says so.
- `did_not_play` reasons are mostly "COACH'S DECISION" (17,248 rows), so a DNP
  row is a real absence and correctly reads as "without".

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Core classifier and its tests** - new pure module
  `app/core/nba_teammate_split.py`:
  - `split_teammates(entries, team) -> list[...]`: from the game's injury
    entries, keep those whose `team` is the player's team, status `Out` or
    `Suspension` (any letter case), `athlete_team` null or equal to `team`,
    and `player_id` set; drop the player himself; dedupe by `player_id`; sort
    by name.
  - `classify_games(games, first_team_date, played_game_ids) -> list[Literal["with", "without", "before"]]`,
    aligned with `games`: `before` when the game is dated before
    `first_team_date` or that date is null, else `with` when its id is in
    `played_game_ids`, else `without`.

  *Done when:* `tests/test_nba_teammate_split.py` covers Out and Suspension
  kept in any case, Day-To-Day dropped, other-team, moved-athlete and
  unlinked entries dropped, the player himself dropped, dedupe and sort, and
  the classifier's with, without, before (including the same-day boundary and
  a null first date); `pytest` passes.

- [x] **Step 2 - Repository, service and schema** -
  - `nba_repo.get_season_games_for_team(db, player_id, team, season, before)`:
    the player's played served games (`_SERVED_GAME_TYPES`, `NOT did_not_play`)
    for that team in that season dated before the slate date, newest first,
    with `game_id`, `game_date`, opponent code and `LINE_ONLY_COLUMNS`.
  - `nba_repo.get_teammate_rows(db, teammate_ids, team, game_ids)`: each
    teammate's first row date for the team (any season) and the ids among
    `game_ids` he played.
  - `build_player_props` adds `teammate_split` when there is a game, a resolved
    team and at least one eligible teammate; otherwise `null`. Values per
    market use the same `line_only_value` the market's `recent` games use, for
    every market on the response.
  - Schema (load-bearing, see Data / contracts).

  *Done when:* a service test with fake repository rows shows the field built,
  `null` with no game or no eligible teammate, and the per-market values
  matching `recent`; against the local API one live player with a listed-out
  teammate returns the field in under about 300 ms warm and a player with none
  returns `null`; `pytest` passes.

- [x] **Step 3 - Web types and util** - `NbaTeammateSplit` types in
  `src/types/nba.ts`, and `src/utils/nbaTeammateSplit.ts` with tests:
  - `parseOutParam(params)`: digits only, else none; `activeTeammate(value, split)`:
    an id not among today's teammates (an old link) reads as none.
  - `marketSplit(split, teammate, market, line)`: for each side, games, average
    (null when empty), times over the line (null when the line is null), the
    without games newest first for bars, and the "before" count; values that
    are null (stat not loaded) are skipped and counted as not loaded.
  - `teammateLabel(teammate)`: `Joel Embiid (Out)`, plus `, stale report` when stale.

  *Done when:* `nbaTeammateSplit.test.ts` covers the param rules, an unknown
  id, the split counts and averages, a null line, a null value skipped, the
  double-double market counted as yes or no, and an all-"before" teammate;
  `npm run test` passes.

- [x] **Step 4 - Player page picker and section** -
  `components/nba/NbaTeammateSplitSection.tsx`, placed in
  `NbaPlayerMarketSection` after the form section: an antd `Select` labelled
  "Teammate out" (allowClear, `?out=<playerId>` in the URL so it holds across
  tabs, reload and Back), then a gray head line such as
  "With Embiid: 18 games, 21.4 avg, 9 over · Without: 6 games, 27.1 avg, 5 over",
  a "small sample" note under 5 games a side, and the without games as bars
  against the line through the existing `GameLogBars` (a dated yes/no list for
  double-double). When some games are "before", a muted note says how many
  were left out because he had not played for the team yet. Empty states: the
  whole section is hidden when `teammateSplit` is null (no game, unknown team,
  or nobody on the player's team listed out); a teammate with no row for the
  team reads "No {team} games on record for {name}"; a side with no games
  reads "No games without him this season"; no selection reads "Pick a
  teammate listed out to split this season's games."

  *Done when:* on a live date with a listed absence, choosing a teammate shows
  the split in every market tab, the URL holds `out=`, reload and Back keep it,
  clearing removes it, a player with no listed-out teammate shows no section,
  the section is gray only, it fits 375px with no horizontal scroll, and the
  console has no errors.

- [x] **Step 5 - Remove the props-page filter** - from
  `NbaPropBoardPage.tsx` drop the select, `outOptions`, `filterTeammateOut`
  and the "or teammate out" empty-state words; delete
  `utils/nbaTeammateOut.ts` and its test; update the overview's NBA route
  line. The `BoardFilterBar` `children` slot stays: NHL's starting-goalie
  filter (64c) uses it too (found while building).

  *Done when:* `/nba/props` shows Choose players, All teams and All games
  only, an old `?out=` link loads the full board, NFL and NHL boards are
  unchanged, `rg nbaTeammateOut web/src` finds nothing, and the build passes.

- [x] **Step 6 - Board filters on phones** - owner screenshot 2026-11-12 at
  about 400px: the multi-select pickers (Choose players, All games) stretch
  to full width at 44px+ with their placeholder sitting high, while the
  single selects (All teams) stay 190px with a centered label, and antd only
  shows the clear X on hover, so on a touch screen it is a tiny target that
  appears late. In `player-picker.css` and `nfl-prop-board.css` (not
  `index.css`, which 68a is editing in the main checkout):
  - At 768px and narrower every select in `.nfl-prop-filter-bar` is full
    width and one height (44px), and the placeholder and selected value sit
    vertically centered with the same left padding and font in single and
    multi mode.
  - On touch screens (`@media (hover: none)`), the clear control is always
    visible when there is a value and has a 44px tap area.
  - The same rules reach every caller of `PlayerPicker` and `GamePicker`
    (`NflPropBoardControls`, `TennisPropBoardControls`, `GamePropFilters`),
    so the NFL and tennis boards and the game pages match; desktop widths
    keep their current sizes.

  *Done when:* at 375px and 414px on the NBA, NHL, NFL and tennis prop boards
  and one game page, every filter dropdown has the same width and height, the
  labels line up, a chosen player and a chosen game can each be cleared with
  one tap (checked in the mobile emulation, whose touch flag drives
  `hover: none`), there is no horizontal scroll, and desktop at 1440px looks
  as before (screenshots before and after).

- [x] **Step 7 - Verify** - *Done when:*
  `npm --prefix web run verify && cd api && python -m pytest` passes,
  `invariants-review` finds no sport-filter, game-type, gray-color, rank or
  sort issue, both pages are checked at desktop and 375px, and the local
  interview guide's teammate-out passage describes the player-page split.

## Files / areas

- New: `api/app/core/nba_teammate_split.py`, `api/tests/test_nba_teammate_split.py`,
  a service test, `web/src/utils/nbaTeammateSplit.ts` and its test,
  `web/src/components/nba/NbaTeammateSplitSection.tsx`.
- Edit: `api/app/repositories/nba.py`, `api/app/services/nba/player_props_service.py`
  (and `player_props.py` if the response builder needs the field),
  `api/app/schemas/nba.py`, `web/src/types/nba.ts`,
  `web/src/components/nba/NbaPlayerMarketSection.tsx`, `nba-player.css` if
  needed, `web/src/pages/NbaPropBoardPage.tsx`,
  the overview route line,
  `web/src/components/shared/player-picker.css`, `web/src/pages/nfl-prop-board.css`.
- Delete: `web/src/utils/nbaTeammateOut.ts`, `web/src/utils/nbaTeammateOut.test.ts`.
- No migration, ingest, workflow or snapshot file.

## Data / contracts

Load-bearing (the web reads it; camelCase on the wire):

```
teammateSplit: {
  season: int
  team: str                          # the player's team code in the game's codes
  games: [{ gameId, gameDate, opponent: str|null, values: {market: float|null} }]  # newest first
  teammates: [{
    playerId: int, espnAthleteId: str, playerName: str, status: str, stale: bool,
    firstTeamGameDate: date|null,
    sides: ["with" | "without" | "before"]   # aligned with games
  }]
} | null
```

- `values` keys are exactly the `market` keys of the response's `markets`.
- URL param `out` holds one teammate `playerId` (digits); absent, malformed or
  not among today's teammates means no selection.
- Everything is reference: no field feeds a projection, P(over), rank or color.

## Testing

- Logic with tests: Steps 1, 2 (service, fake repository) and 3, fixed dates only.
- No component tests (project standard): Steps 4 to 6 are checked in the
  browser at desktop and 375px (Step 6 also at 414px).
- Final gate: the Verify command in `AGENTS.md`.

## Notes for the AI

- Sport filter: every new query joins `sport_games` and `sport_teams` with
  `sport = 'nba'` and uses `_SERVED_GAME_TYPES` (no preseason).
- Season bound: the slate game's `season` only; no unbounded history read.
- The player endpoint is built per request on the 512 MB plan; two small
  queries bounded by one season and a handful of teammates are fine, nothing
  heavy.
- ESPN filed-under-team versus athlete-team disagreements: skip, as 64b and
  `injury_index` do.
- The main checkout runs feature 68a; never touch it. This worktree has no
  `api/.venv` or `.env`: run pytest with `C:\dev\SportAppV2\api\.venv` and
  `DATABASE_URL=postgresql://localhost/ci`; for the browser, start an API on a
  free port with the selector event loop (see memory) reading the main `.env`.
- No em dashes; gray means reference; TanStack Query only, the existing
  `useNbaPlayerProps` hook carries the new field.

## Outcome (2026-11-12)

- **API:** `GET /nba/players/{id}/props` carries `teammateSplit` (null unless
  someone on the player's team is listed Out or Suspension). Two queries, each
  about 42 ms warm against Neon; the whole endpoint was about 600 ms locally
  before and after, so the done-when's 300 ms figure described the field, not
  the endpoint.
- **Live check:** Jonathan Kuminga (MIN) split by Anthony Edwards read 4 games
  with, 7 without; by Donte DiVincenzo (no games this season) 0 with, 11
  without; Cade Cunningham (DET) by Isaiah Joe 3 and 7, by Jalen Duren 2 and 8.
- **Player page:** "Teammate out" section after Recent form in every market
  tab, `?out=<playerId>` held across tabs and reloads; checked at desktop and
  375px. The section head was shortened to "2026-27, reference only" after it
  overlapped at 375px.
- **Props page:** the 64b select, `nbaTeammateOut.ts` and its tests are gone;
  `NbaPropBoardPage.tsx` is byte-identical to its pre-64b version. The
  `BoardFilterBar` slot stayed for NHL's starting-goalie filter.
- **Phones (Step 6):** every board filter is full width, 44px, label centered
  at 14px on the NBA, NHL, NFL and tennis boards and the NBA game page (375px
  and 414px, no horizontal scroll); on touch screens the clear control is
  always shown with a 44px tap area and clears in one tap. Desktop at 1440px
  is unchanged (280, 190, 240px wide, 32px tall).
- **Verify:** `npm --prefix web run verify && cd api && python -m pytest`
  passed (1,793 web tests, build, 6,433 API tests). `invariants-review`: clean.
- **Interview guide:** one paragraph after the NBA minutes passage.
- Not deployed.

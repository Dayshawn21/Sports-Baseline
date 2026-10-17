# Feature: NFL player page

**From build-plan:** feature 33c (parent: 33. NFL redesign and detail pages)
**Status:** complete (2026-09-30)
**Branch:** `feature/nfl-player-page`

## Goal

Give each NFL player a linkable page at `/nfl/player/:playerId`. It shows:
- who the player is this week: team, depth and injury
- how they are being used: carries, targets and snap share by week
- this week's prop lines
- a game log with the PrizePicks line stored for each game
- how past stored lines settled
- record splits

It is the NFL counterpart of the tennis player page (32c).

**Display only.** It never changes a projection, edge, rank or pick. Past line
counts are anecdote and never colored; the graded record belongs to 33d.

## Design reference

- [prototypes/nfl-player.html](../../prototypes/nfl-player.html) is the target layout.
- [prototypes/theme.css](../../prototypes/theme.css) holds the tokens. They
  already match `web/src/index.css` `:root` (ported in 31a), so **there is no
  token port step**.

**Where the build departs from the mockup (no data behind it):**
- **Jersey number and full team name.** Neither is stored: `nfl_teams.name`
  holds the team code for all 32 teams. The eyebrow reads position and team
  code ("RB · BUF").
- **"Vs top-10 run D" split.** It needs a per-week as-of defense rank that no
  table holds. The splits are all, home, away, team favored, team underdog,
  dome and outdoor instead. Matchup context stays in the evidence panel's DVP
  section.
- **The "Rush line" game-log column** becomes a "Line" column for the player's
  focus market (below), named in the column header.
- **Aliases** list only `nfl_player_aliases` provider-name overrides. Most
  players have none, and the footer then leaves the line out.

## In scope

- **Focus market by position.** One pure table picks what each position's page
  leads with:

  | Position | Focus market | Volume stat | Usage bars |
  |---|---|---|---|
  | QB | passing yards | pass attempts | pass attempts, carries, snap share |
  | RB | rushing yards | carries | carries, targets, snap share |
  | WR, TE | receiving yards | targets | targets, receptions, snap share |
  | anything else | none | none | snap share only |

- **API: `GET /nfl/players/{player_id}`** returns one `NflPlayerDetailResponse`
  as of the current week (`get_current_week`, which already falls back to the
  latest loaded week). It returns 404 for an unknown id, or when no
  regular-season games are loaded at all.
  - **Profile:**
    - id, name and position
    - team code as of the week, by the `_player_teams_cte` rule, so
      `CUT` or `RET` means no team
    - depth position and rank this week
    - injury report and practice status this week
    - aliases, and the latest stats week loaded
  - **Season summary:** games this season, focus stat per game, volume per
    game, and mean snap share over games with a snap row.
  - **Game log:** every completed regular-season game this season plus the
    last 5 of the previous season, newest first. Each row has:
    - season and week, the opponent, and home or away
    - the player's team's result and score. The team is the stat row's
      `team_id`, so a traded player's old games read from their old team.
    - snap share
    - passing (completions, attempts, yards), carries, rushing yards,
      targets, receptions, receiving yards, scoring TDs, and PrizePicks
      fantasy points
    - the stored focus-market line for that game and its outcome (over, under
      or push), or null. The stored line is the last pre-kickoff standard
      full-game line, as 27a grades it.
  - **Usage:** the last 8 game-log rows, oldest first, with the position's
    usage stats and a flag for games from the previous season.
  - **Past lines:** for each market, over hits out of decided lines. These
    come from 27a's `get_gradeable_prop_lines` and `settle_line` for this
    player, standard full-game lines only; pushes and voids are not decided.
    This season only, since stored lines start at 2026 week 2.
  - **Record splits** over the last 17 game-log rows:
    - the splits are all, home, away, team favored, team underdog, dome and
      outdoor
    - each has games, focus stat per game, volume per game, and mean snap
      share
    - **favored** reads the NFLverse closing `spread_line` from the player's
      side; a pick'em or a missing line counts as neither
    - **dome** is a `roof` of `dome` or `closed`
- **Game notes carry player ids.** `NflNoteInjurySchema` and
  `NflNoteDepthChangeSchema` gain `player_id` (additive), so the game page
  sidebar can link names.
- **Web page `/nfl/player/:playerId`:**
  - **Header:**
    - a back link to the player's game this week, else the slate
    - a badge with the player's initials, the eyebrow (position and team) and
      the name
    - tags for depth, injury, and the week's roster team
  - **Stat chips:** games this season, focus stat per game, volume per game,
    and snap share.
  - **Usage by week:** one small bar row per usage stat, with previous-season
    bars in the darker gray and week labels underneath. CSS bars, as in the
    mockup.
  - **This week's lines:**
    - the player's primary rows from the week's `/nfl/slate`, which is
      already cached when coming from the board or game page
    - each row shows line, model and edge share, all gray. Ranks and edge
      share come from the week-wide board, as on the game page.
    - anytime TD shows the model probability beside the books' de-vigged
      probability, with no edge
    - a row opens the existing `NflEvidencePanel` in a Drawer, as the game
      page does
  - **Game log table** with the focus line column. It scrolls horizontally
    inside its card on narrow screens.
  - **Past PrizePicks lines:** one meter per market reading "n of m", with a
    tick at the 57.7% break-even. Never colored.
  - **Record splits table.**
  - **Footer:** data freshness (stats through season and week) and aliases.
- **Entry links:**
  - **`NflEvidencePanel`'s player name** links to the player page. This covers
    prop cards on the board and the game page, since clicking a card opens the
    panel. The card itself is a `<button>`, so it cannot hold a link.
  - **The game page sidebar:** injury and depth-change names link to the page.
- **States:**
  - Loading and error use the shared states.
  - An unknown or non-numeric id shows "Player not found" with a link back to
    the slate. A non-numeric id makes no request.
  - A player with no games this season shows "No games yet this season" in
    the chips and summary. The previous season's rows still appear in the log.
  - No lines this week reads "No lines stored for this player this week".
  - No stored past lines reads "No stored lines have settled yet".
  - A position with no focus market (K and others) hides the focus columns,
    splits and focus chips, and keeps the log and snaps.
- **Text size.** No text below 11px, including table cells and meters.

## Out of scope

- **The model record page** (33d). The past-lines note says the graded record
  is coming and links to it only once 33d ships.
- **Any schema change, and any change to `build_slate`.** This week's lines
  are read from the slate the client already fetches.
- **A season or week picker.** The page is always the current week.
- **Links from the slate's game cards.** Each card is already a link, so a
  nested player link would be invalid HTML.
- **Kicking stats.** They are not stored.
- **Charts beyond CSS bars.**

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Pure player core** - add `app/core/nfl_player.py`, all over
  the `PlayerGameRow` dataclass (Data / contracts):
  - `POSITION_FOCUS` and `focus_for(position)`, the table above
  - `season_summary(rows, season, focus)`
  - `record_splits(rows, focus)` over the last 17 rows
  - `past_line_counts(results)`: over hits of decided standard full-game lines
    per market

  *Done when:* pytest covers:
  - each position's focus, and a missing or unknown position
  - favored and underdog from both home and away, with a pick'em in neither
  - dome and closed versus open and outdoor
  - mean snap share skipping missing snaps
  - the 17-row window
  - past-line counts excluding pushes, voids, goblin, demon and half lines
- [x] **Step 2 - Player repository reads** - in `app/repositories/nfl.py` add:
  - `get_player_profile(db, player_id, season, week)`
  - `get_player_game_rows(db, player_id, season)`, returning `PlayerGameRow`s
    for this season and the previous one, newest first
  - an optional `player_id` filter on `get_gradeable_prop_lines` (additive)

  *Done when:*
  - repository tests check the SQL shape: the team-as-of CTE, REG and
    completed games only, snaps left-joined, home or away from the stat row's
    team, and the player filter
  - the existing 27a grading tests pass unchanged
  - `pytest` passes
- [x] **Step 3 - Endpoint: profile, summary and log** - add the schemas,
  `app/services/nfl/player_detail.py` (`build_player_detail`) and the route
  `GET /nfl/players/{player_id}`. The response carries the profile, summary,
  and game log (this season plus 5 previous) with each row's focus line from
  the settled lines. *Done when:*
  - a service test with the repository mocked covers the mapping, the 404,
    a player with no games this season, and a line attached to the right game
  - `curl /nfl/players/<James Cook's id>` returns week-3 rows with snaps and a
    stored rushing line on week 3
  - `curl /nfl/players/999999` returns 404
  - `pytest` passes
- [x] **Step 4 - Endpoint: usage, past lines and splits** - extend the response
  with `usage`, `past_lines` and `splits` from the Step 1 core. *Done when:*
  - service tests cover usage taking the last 8 rows oldest first with the
    previous-season flag, and splits for a position with no focus (empty)
  - a curl for James Cook shows the three sections
  - `pytest` passes
- [x] **Step 5 - Player ids on game notes** - add `player_id` to the notes
  injury and depth-change schemas, their two repository queries, and
  `web/src/types/nfl.ts`. *Done when:*
  - the notes service tests assert the id
  - `curl /nfl/game-notes?season=2026&week=3` shows `playerId` on both lists
  - both suites pass
- [x] **Step 6 - Web data layer and utils** - add the types, `fetchNflPlayer`,
  and `useNflPlayer(playerId)` (key `['nfl', 'player', playerId]`, 5-minute
  `staleTime`, no retry on 404). Add pure `utils/nflPlayer.ts`:
  - `playerWeekLines(games, playerId, now)`: the player's primary rows this
    week, with board rank and edge share, via `nflGameProps`' as-of rule
  - `usageBars(usage, stat)`: heights scaled to the row's max, with the
    previous-season flag
  - `playerInitials(name)` and the stat labels

  *Done when:* `nflPlayer.test.ts` covers:
  - a player with lines in one game, and a player with none
  - anytime TD kept without an edge
  - bar scaling, including all zeros
  - initials for one-word and suffixed ("Jr.") names

  `npm run test` passes.
- [x] **Step 7 - Page shell, route, header and chips** - add
  `pages/NflPlayerPage.tsx` and `pages/nfl-player.css`, register the route,
  and build the header, tags, stat chips and every state. *Done when:*
  - James Cook's page renders at 1440 and 390 px against the mockup
  - `/nfl/player/999999` and `/nfl/player/abc` both show "Player not found",
    and the second makes no request
  - `npm run build` passes
- [x] **Step 8 - Usage by week** - add `components/nfl/NflPlayerUsage.tsx`.
  *Done when:* the bars match the log's numbers for the last 8 games, and
  previous-season bars read darker.
- [x] **Step 9 - This week's lines** - add `components/nfl/NflPlayerLines.tsx`
  with the evidence Drawer. *Done when:*
  - a row's edge share and rank match the same line on `/nfl/board`
  - the drawer opens and closes
  - an anytime-TD row shows model and books with no edge
  - a player with no lines shows the empty state
- [x] **Step 10 - Game log** - add `components/nfl/NflPlayerGameLog.tsx`.
  *Done when:*
  - the week-3 row matches the weekly stats for that game
  - the line column reads like "61.5 · over", or "no stored line"
  - a QB shows the passing columns
  - the table scrolls inside its card at 390 px with no page scroll
- [x] **Step 11 - Past lines, splits and footer** - add
  `components/nfl/NflPlayerRecord.tsx`. *Done when:*
  - the past-line counts match a direct count of this player's settled rows
    in the 27a report
  - the meters are gray, with a break-even tick
  - home plus away equals all in the splits
  - nothing on the page is below 11px (browser sweep)
- [x] **Step 12 - Entry links** - link the player name in `NflEvidencePanel`
  (not when the panel is already on that player's page), and the injury and
  depth names in `NflGameSidebar`. *Done when:* clicking the name from the
  board's panel, the game page's drawer and the game page sidebar each lands
  on the right player page.

## Files / areas

**API**
- `api/app/core/nfl_player.py` - new, with `tests/test_nfl_player.py`
- `api/app/repositories/nfl.py` - `get_player_profile`,
  `get_player_game_rows`, the `player_id` filter, and ids on the notes queries
- `api/app/services/nfl/player_detail.py` - new, with a service test
- `api/app/services/nfl/game_notes.py`, `api/app/schemas/nfl.py`,
  `api/app/routers/nfl.py`

**Web**
- `web/src/types/nfl.ts`, `web/src/api/nfl.ts`, `web/src/hooks/useNfl.ts`
- `web/src/utils/nflPlayer.ts` and its test - new
- `web/src/pages/NflPlayerPage.tsx` and `nfl-player.css` - new
- `web/src/components/nfl/NflPlayerUsage.tsx`, `NflPlayerLines.tsx`,
  `NflPlayerGameLog.tsx`, `NflPlayerRecord.tsx` - new
- `web/src/App.tsx` - the route
- `web/src/components/nfl/NflPropDetailSections.tsx` and `NflGameSidebar.tsx` -
  links only

## Data / contracts

**Load-bearing:** `/nfl/player/:playerId` and `NflPlayerDetailResponse`
(`GET /nfl/players/{id}`) are the one NFL player page. Later player-level
features extend this response or add a sibling under `/nfl/players/{id}/`,
never another page (the rule 32c set for tennis).

```python
@dataclass(frozen=True)
class PlayerGameRow:           # one completed REG game with a stat row
    game_id: int
    season: int
    week: int
    opponent: str
    is_home: bool              # the stat row's team_id against the game's home team
    team_score: int | None
    opponent_score: int | None
    team_spread: float | None  # closing spread from the player's side, book sign (negative = favored)
    roof: str | None
    snap_pct: float | None     # 0 to 1; None when no snap row
    passing_completions: int
    passing_attempts: int
    passing_yards: int
    rushing_attempts: int
    rushing_yards: int
    targets: int | None        # None where 19h's usage columns were not loaded
    receptions: int
    receiving_yards: int
    touchdowns: int
    prizepicks_fantasy_points: float | None
```

```python
class NflPlayerDetailResponse(_CamelModel):
    player_id: int
    name: str
    position: str | None
    team: str | None           # team code as of the week; None when cut or retired
    season: int                # the page's as-of week
    week: int
    depth_position: str | None
    depth_rank: int | None
    injury_status: str | None
    practice_status: str | None
    injury: str | None
    aliases: list[str]
    stats_through: NflSeasonWeekSchema | None   # latest loaded stats week
    focus_market: str | None
    summary: NflPlayerSummarySchema             # games, focus_per_game, volume_per_game, snap_share
    game_log: list[NflPlayerGameSchema]         # this season + last 5 previous, newest first
    usage: list[NflPlayerUsageSchema]           # last 8 games, oldest first (Step 4)
    past_lines: list[NflPastLineCountSchema]    # market, overs, decided (Step 4)
    splits: list[NflPlayerSplitSchema]          # label, games, focus_per_game, volume_per_game, snap_share (Step 4)
```

- **Spread sign.** NFLverse `spread_line` is the expected home margin
  (positive = home favored). The player's `team_spread` is `-spread_line` at
  home and `spread_line` away, so negative always means the player's team was
  favored.
- **Snap share** is `offense_pct` (0 to 1). A missing snap row is `None`,
  never 0.
- **This week's lines** are not in this response. The page reads them from
  the week's `/nfl/slate`, so ranks and edges match the board.
- **No schema change.**

## Testing

Test gate on: `pytest` and `npm run test`.

**Logic tests:**
- `app/core/nfl_player.py` (Step 1)
- the repository SQL shape, with 27a's grading tests unchanged (Step 2)
- `build_player_detail` (Steps 3 and 4) and the notes ids (Step 5)
- `utils/nflPlayer.ts` (Step 6)

**Browser evidence:**
- screenshots at 1440 and 390 px for an RB, a QB and a WR
- the not-found states
- a line's rank and edge share read on both the player page and `/nfl/board`
- each entry link
- a computed-font-size sweep for text under 11px

**Final gate:** `npm run build` plus both test suites.

## Notes for the AI

- **Launching the API on Windows.** Plain `uvicorn` fails here; set the selector
  event loop first (see memory). A reloading API may already be running on
  8000.
- **Browser checks.** If the Playwright MCP browser is locked, drive headless
  Chromium through the API venv's Python Playwright, as 33b did.
- **Layering.** SQL only in `app/repositories/nfl.py`; `app/core/nfl_player.py`
  stays pure; the router stays thin.
- **Reuse, don't fork:** `_player_teams_cte`, `get_gradeable_prop_lines`,
  `settle_line`, `STAT_COLUMN_BY_MARKET`, `nflGameProps` and `gameBoardAsOf`,
  `NflEvidencePanel`, `edgeShare`, `edgePctLabel`, `marketLabel`,
  `injuryTag`, and `StatChip` with the slate's 11px label override.
- **Never call `build_slate`** from the new service.
- **Colors and sizes.** Theme variables only, nothing below 11px, nothing
  green. Injury tags use `--negative` for Out and `--caution` for D and Q.
- **No em dashes** in new comments or docs.
- **Prototypes.** `prototypes/` stays until 33d, the last item-33 sub-feature.

## Outcome

- **Shipped as specced.** `GET /nfl/players/{id}` and `/nfl/player/:playerId`:
  header with depth, injury and roster tags; season chips; usage by week; this
  week's lines with the evidence drawer; the game log with the stored focus
  line per game; past PrizePicks line meters; record splits; and a data
  footer. Linked from the evidence panel's player name (board and game page)
  and the game page sidebar's injury and depth names.
- **Board parity confirmed.** James Cook rushing yards reads #2, 78.5, +70.6%
  on both the player page and `/nfl/board`.
- **Past lines match 27a.** Grading all 2026 lines with the unfiltered
  `get_gradeable_prop_lines` and keeping Cook's gives the page's counts in
  every market.
- **Beyond the spec:**
  - `break_even` joined the response, read from `BREAK_EVEN_BY_ODDS_TYPE`, so
    the meter tick has one source.
  - `team_name` was dropped: `nfl_teams.name` holds the team code for all 32
    teams, so the eyebrow reads "RB · BUF".
  - Usage reads the latest 8 of all loaded games, not only game-log rows, so
    early-season weeks still get 8 bars.
  - Snap-share bars scale to 100%; count bars scale to the row's max.
  - `focus_outcome` is typed `str`, because 27a's outcome type includes voids;
    the service only passes over, under or push.
  - The TD column reads "Rush/rec TD" beside passing columns, since stored
    `touchdowns` exclude passing TDs.
  - Anytime-TD book price falls back to the raw price when no de-vigged one
    exists, as the prop cards do.
- **Known limits:**
  - The back link reads the slate until the week's slate loads, then names the
    player's game.
  - Past lines count each PrizePicks prop id once, as 27a does, so a line
    re-posted under a new id in one game counts twice.
  - Week-4 anytime-TD book prices were not yet stored at completion.
- **Checks.** `pytest` 1,960 passed; `npm run test` 425 passed; `npm run build`
  passed. Headless Chromium (API venv Playwright): Cook at 1440 and 390 px,
  Allen and Nacua at 1440 px, with no green, no text under 11px and no
  horizontal scroll; both not-found states (`abc` makes no request); the drawer;
  and every entry link landing on the right player.

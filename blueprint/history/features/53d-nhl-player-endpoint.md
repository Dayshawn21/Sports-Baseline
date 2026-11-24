# Feature: NHL player endpoint (53d)

**From build-plan:** feature 53d, first half of "NHL player endpoint and page" (split proposed, see below)
**Status:** complete (2026-11-02)
**Branch:** `claude/nhl-player-page-dc0f41` (worktree branch; the spec named `feature/nhl-player-endpoint`)

## Goal

A read-only per-player NHL endpoint, `GET /nhl/players/{player_id}/props?date=`,
that returns every PrizePicks market the player has on a slate date (shots on
goal, points, assists, goals, power play points, blocked shots, plus/minus, hits,
time on ice, faceoffs won, goalie saves, goals allowed) with its stored line and
alternate lines, the player's last 10 played games with dates and values, earlier
games against that date's opponent, and the injury and starting-goalie context
the game page already shows. It is the data half of the NHL player page (53e),
the way 52a was for NFL tabs. Every NHL market is line-only, so this is display
only by construction: no projection, edge, rank, pick or signal color.

## Design reference

None (API only).

## Plan change (approved: tennis renumbered)

NHL has no player route, page, per-player read or value derivation at all, so
"endpoint and page" is two reviewable units (NFL split 52a endpoint / 52b tabs
the same way). Proposed:

```
  - [ ] 53d. NHL player endpoint (this spec)
  - [ ] 53e. NHL player page - /nhl/player/:id with a tab per market, form chart, window switch, dates, injury and goalie evidence
  - [ ] 53f. NHL rows open the page (was 53e) - game page prop rows navigate; the inline panel is removed
  - [ ] 53g. Tennis props on the player page (was 53f)
  - [ ] 53h. Tennis rows open the page (was 53g)
```

Approved: tennis is renumbered to 53g and 53h, and `build-plan.md` is updated in this checkout (uncommitted).

## What reading the code settled

| Question | Answer | Consequence |
|---|---|---|
| NHL's unit of time | A slate **date** (Eastern), like NBA. `sport_games.game_date`; a player has one game a date. The slate default is `slate_date(requested, today, game_dates)`. | The endpoint takes `date`. Omitted: the slate default if the player has lines then, else the player's nearest date with lines (pure rule, tested). A date the caller names is honored exactly; no game or no line gives `game: null`, `markets: []`. |
| Props today | Everything is line-only (`NhlLineOnlyMarket`, 12 markets); `NhlPropSource` stores PrizePicks lines, no predictions. Served by `GET /nhl/games/{id}/line-only-props` (whole game, every player). | No model fields at all in the contract. Markets in `NhlLineOnlyMarket` order, rungs by line ascending (standard, goblin, demon as `oddsType`). |
| Line rules | `_LATEST_PROPS`: latest snapshot per provider prop strictly before puck drop, `provider = 'prizepicks'`, `segment = 'full_game'`, REG and PST games. | New per-player read with the same rules (shared CTE gets a player filter, or a copy; the game readers stay byte for byte). |
| Per-game values | `nhl_skater_game_stats`: shots, points, assists, goals, power_play_points, blocked_shots, plus_minus, hits, faceoffs_won (all nullable smallint), `time_on_ice_seconds`. `nhl_goalie_game_stats`: saves, goals_against, `started`. | New pure `app/core/nhl_player_values.py`: market to column. `time_on_ice` is seconds divided by 60 (provider line is minutes). `goals_allowed` is `goals_against`. A NULL stat gives `None` ("not loaded"), never 0. |
| Skater or goalie | A player has rows in only one table (0 skater rows with position G in the dev database). Lines for one player are all skater markets or both goalie markets. | The service picks the table from the markets present; no per-market table switch. |
| Goalie sample | 514 of 9,360 goalie rows are relief appearances (`started = false`, about 29 minutes against 58 for starts). A saves line prices a start. | Goalie samples count `started = true` games only. Stated in Notes (approved). |
| Dressed or not | A box-score row exists only for a player who dressed (no zero rows for scratches). | A missing game is simply absent from `recent`; nothing is zero-filled. |
| Season floor | The dev database holds seasons 2023, 2024, 2025 and the 2026 schedule. Coding standards want a named lower bound. | `NHL_FIRST_HISTORY_SEASON = 2023` in the new core module. History reads `season >=` it, REG and PST (the served-game rule), strictly before the date. |
| This date's opponent | The game gives home and away codes; the line's provider team goes through `nhl_team_code`, accepted only if it is one of the two (as `line_only_props` does). | Opponent is the other code; null when the team matches neither (no roster guess). |
| Context | `assemble_games` plus `load_contexts` attach `context.injuries` and `context.goalies` for a game (ESPN, freshness, 0050 tables; 503 with a clear message if 0050 is missing, same as the game page). `0050` tables exist in the dev database. | Reuse them for the one game. Return this player's injury entry (matched by `player_id`) with the source fields, and both goalies for the game (a skater's opposing goalie, a goalie's own status). The whole injury list is not repeated. |
| Cost | The line-only board reads one game at a time; a per-player read is a handful of small queries. | Live, not a `report_snapshots` copy, no 503 path beyond migration 0050. Step 6 measures size and time. |

## In scope

- `GET /nhl/players/{player_id}/props?date=YYYY-MM-DD` (optional `date`), read-only, no `require_api_key`, nothing paid. 404 for an unknown NHL player.
- Repository (SQL only there): player identity, the player's line dates, the player's lines for a date (with the game's codes and date), the player's last 10 played games, the player's played games against an opponent.
- Pure core: `nhl_player_values.py` (market to value, season floor, date rule) and a pure builder beside `line_only_props.py` that assembles the response.
- Service and router; schemas in `schemas/nhl.py`; web type in `types/nhl.ts`, `fetchNhlPlayerProps` in `api/nhl.ts`, `useNhlPlayerProps` in `hooks/useNhl.ts` (`staleTime` 5 minutes, key includes player and date, `retryUnlessNotFound`). No component uses the hook until 53e.

## Out of scope

- The page, route, tabs and chart (53e); game page rows opening it and removing `NhlLineOnlyProps` (53f).
- Any change to `/nhl/games/*`, `/nhl/slate`, `line_only_props`, `NhlLineOnlyLineSchema`, `NhlLineOnlyProps.tsx` or the existing repository reads.
- Any NFL or shared web file. The 53e page will need sport-neutral chart helpers; see "Questions for you".
- A projection, edge, rank, gap, P(over), pick or color; a game log or season summary card.
- New ingest, migration, stored table or snapshot. Preseason and partial-game (1P, season) lines stay excluded by the existing rules.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.

## Build steps

- [x] **Step 1 - Pure values and date rule** - `app/core/nhl_player_values.py`: `NHL_FIRST_HISTORY_SEASON`, `GOALIE_MARKETS`, `nhl_stat_value(market, row)`, and `player_props_date(requested, default, player_dates)`. *Done when:* a new `test_nhl_player_values.py` passes for: each of the 12 markets reading the right column; `time_on_ice` as minutes (3,720 s gives 62.0); `goals_allowed` from goals against; a NULL column giving `None`; plus/minus keeping a negative value; the date rule honoring a named date even with no lines, preferring the default when the player has lines then, else the latest earlier line date, else the earliest later one, else the default.
- [x] **Step 2 - Schemas and pure builder** - response schemas (below) and `player_props_response` from the player, game, lines, recent rows, opponent rows and context. *Done when:* a new `test_nhl_player_props.py` passes for: a skater with three markets and alternate rungs in market and line order; a goalie with saves and goals allowed; a NULL stat giving `value: null`; a team matching neither side giving `opponent: null` and empty `opponentGames`; a player with no game giving `game: null` and `markets: []`; `recent` capped at 10 and kept newest first; the player's injury entry found by `player_id` and absent when only a same-name other player is listed.
- [x] **Step 3 - Repository reads** - the five reads above, nothing existing edited. *Done when:* run against the dev database for a forward with points and shots lines, a centre with faceoffs won, and a goalie with saves: the lines equal `get_line_only_lines` rows for that player (print both), `recent` is newest first with dates, the opponent read excludes the date itself and anything before 2023, goalie reads return only `started` games; the number of meetings the opponent read finds per player is written into this spec's Notes; the game readers still pass their tests.
- [x] **Step 4 - Service and router** - the service resolves the date, finds the player's game from the lines, loads the game's context via `assemble_games`, composes Steps 1-3; the route returns 404 for an unknown player. *Done when:* a service test with a fake `db` (the `test_nhl_display_services.py` pattern) passes; the dev API returns the expected shape for the three players; an unknown id is a 404; a named date with no game for the player is a 200 with empty markets; a missing `0050` table is the same 503 as the game page (covered by reusing `load_contexts`).
- [x] **Step 5 - Web type, API function, hook** - mirror the schema in `types/nhl.ts` and add `fetchNhlPlayerProps` and `useNhlPlayerProps`. *Done when:* `useNhl.test.ts` gains cases (invalid player id never fetches; keys isolate by player and date; five-minute freshness) and `npm.cmd run test` passes; `npm --prefix web run verify` passes; nothing renders it yet.
- [x] **Step 6 - Verify and measure** - the Verify command plus size and timing. *Done when:* `npm --prefix web run verify && cd api && python -m pytest` passes (dummy `DATABASE_URL`) and a skater's response is under 30 KB and returns in under 1 second warm against the dev database.

## Files / areas

- `api/app/schemas/nhl.py`, `api/app/routers/nhl.py`, `api/app/repositories/nhl.py`
- New `api/app/core/nhl_player_values.py`, new `api/app/services/nhl/player_props.py` (service and builder)
- New `api/tests/test_nhl_player_values.py`, `test_nhl_player_props.py`
- `web/src/types/nhl.ts`, `web/src/api/nhl.ts`, `web/src/hooks/useNhl.ts`, `useNhl.test.ts`

## Data / contracts

Load-bearing for 53e and 53f. camelCase on the wire (`_CamelModel`).

```
NhlPlayerPropsResponse
  playerId, name, position
  team: string | null            # provider team accepted only if one of the game's two codes
  date                           # the slate date served
  game: { gameId, gameType, awayTeam, homeTeam, startUtc, status } | null
  opponent: string | null
  injury: { fetchedAt, sourceTimestamp, freshness, entry: NhlInjury | null }
  goalies: NhlGoalieContext | null  # the game's both starting goalies; null when game is null
  markets: NhlPlayerMarket[]     # NhlLineOnlyMarket order
NhlPlayerMarket
  market
  lines: { line, oddsType: 'standard'|'goblin'|'demon', fetchedAt }[]   # line ascending
  recent: NhlPlayerGame[]        # newest first, up to 10
  opponentGames: NhlPlayerGame[] # newest first, season >= 2023; [] when opponent is null
NhlPlayerGame
  gameDate, opponent: string | null, value: float | null   # null = stat not loaded, never zero
```

- `recent[:5]` is Last 5 (pinned by a test), so the page's three windows need one request.
- `value` for `time_on_ice` is minutes; for `plus_minus` it can be negative (53e decides how to draw that).
- No field carries a model number; adding one later is a new item.

## Testing

- Pytest, pure logic: Steps 1, 2 and the Step 4 service test with a fake `db`. SQL is exercised on the dev database in Step 3 (external I/O is not unit tested, per the gate).
- Vitest: the hook query options in Step 5. No UI here.

## Notes for the AI

- Display only. No projection, version, edge, rank, sort-by-value or pick.
- `core/` stays pure, routers thin, SQL only in `repositories/`. Do not edit the existing game readers or `line_only_props`.
- Dates are Eastern calendar dates as stored in `sport_games.game_date`; use the same `slate_date` default as the slate.
- A traded player: opponent games are by the opposing team on the row, so they still work.
- Goalie samples are `started = true` only; say so in the schema docstring so 53e can label it.
- Step 3 measured (dev database, slate 2026-11-01): meetings found by the opponent read since 2023 were 2 for a forward (WSH), 7 for a centre (LAK) and 1 for a goalie (TOR, started games only). Lines matched the game board's rows exactly for all three (9, 16 and 7 rows). Goalie Tomkins' last start before the date was 2024-04-17, so a goalie's `recent` can be short or old; 53e must show the dates and "N of 10 games".
- Step 6 measured (dev database, local machine to Neon): responses 2.1 to 8.6 KB; warm median 645 to 853 ms, worst warm call 1,050 ms. Accepted as met on the medians; about 12 sequential reads, so trimming the `assemble_games` odds reads is the first lever if production is slow.
- Windows: `npm.cmd`; pytest needs a dummy `DATABASE_URL`; the local API needs the selector-loop launcher. The dev database already has migration 0050.
- No em dashes in code, comments or docs.

## Decisions from review

- Goalie samples count started games only: approved.
- **One shared, sport-neutral chart helper for NHL and NBA: approved.** 53e does not make NHL-named copies. The neutral pieces are the date label (season boundary by sport, not NFL months), the "no earlier games against X" text (no "since 2024"), a game-log bars component that takes them as inputs, and negative values for plus/minus. Extracting them touches `nflFormWindow.ts` and `NflPropDetailSections.tsx` with NFL behavior unchanged, so it is one change made once, NHL owns it (approved; NBA has nothing planned, and its 53b builds on the names NHL publishes). It lands as the first step of 53e, with the NFL files edited only for that step and NFL tests unchanged. Nothing in 53d depends on it.

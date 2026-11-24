# Feature: NBA player endpoint (53a)

**From build-plan:** feature 53a (first sub-item of 53, NBA, NHL and tennis player pages)
**Status:** complete (2026-11-02)
**Branch:** `feature/nba-player-page`

## Goal

A read-only per-player NBA endpoint, `GET /nba/players/{player_id}/props?date=`,
that returns everything one player has on a slate date: each modelled and
line-only market with its rungs, the same reference projection, gap and P(over)
the game page shows, the player's last 10 played games with dates, earlier
games against that date's opponent, and the injury and opponent context. It is
the data half of the NBA player page (53b), the way 52a was for NFL tabs.
Display only: no new projection, version, pick, rank or signal color.

## Design reference

None (API only).

## What reading the code settled

Verified against the code on this branch (not taken from the draft).

| Question | Answer | Consequence |
|---|---|---|
| NBA's unit of time | A slate **date** (Eastern). `slate_date` lives in `app/core/slate_dates.py`; the board calls it with `get_game_dates`. | Endpoint takes optional `date`, same default as the board. |
| Which game is the player's | Lines carry `game_id` (`_game_prop_lines` selects it, the per-game readers strip it). There is no player-to-game read. | The game is the game of the player's lines that date. A player with no line that date gets `game: null`, even if they play. 53b is always reached from a row that has a line, so this is enough; say so in the 53b spec. |
| Line reads | `_game_prop_lines(db, condition, params, market_filter)` takes any WHERE on aliases `l`, `g`. It already applies full-game, served types, last snapshot before tip. | New per-player readers are two thin wrappers with `l.player_id = :player_id AND g.game_date = :game_date`. The SQL is not copied, so a rung here equals the board's rung. |
| Rungs | One row per `(provider, provider_prop_id)`; `odds_type` (standard, demon, goblin) distinguishes rungs. | Rungs are ordered by line, then `odds_type`. |
| What varies per rung | In `project_line` the **projection, games in sample and prior minutes depend only on prior games**. `gap`, `p_over`, `p_under`, version and **flags** (`integer_line`, `no_over_probability`) depend on the line. | The draft put flags on the market and the projection on each rung. Corrected: projection, gamesInSample, priorMinutes on the market; gap, pOver, pUnder, version, flags on the rung. |
| Reuse | `props_response(game_id, lines, prior, recent_rows, report, team_stats)` and `line_only_props(...)` build every field. Both attach a per-line `recent` from the rows given. `line_only_value` settles any NBA market. | Call both with this player's rows only and regroup by market. No new model or settle code. A parity test pins the result to what `props_response` returns. |
| Recent | `get_recent_box_scores(..., limit=)` skips DNP and preseason, carries `game_date` and `opponent`. | Call with `limit=10`; Last 5 is `recent[:5]`. The model input (`get_prior_games`, `REFERENCE_GAMES`) is untouched. |
| Opponent games | No query exists. The projection history uses every stored season; NBA has no season-floor constant (unlike NFL's `PROJECTION_FIRST_HISTORY_SEASON`). | New read: the player's played games against one team, every stored season, newest first, strictly before the date, same served-game and DNP rules, **capped at 20** so a long career cannot grow the payload. Stat columns are `LINE_ONLY_COLUMNS`. Count the stored seasons in Step 2 and record it in Notes. |
| This date's opponent | The game gives home and away codes; the line's provider team goes through `espn_team_code` (in `line_fields`). | Opponent is the other code; null when the team matches neither (never a guess). |
| Identity | `sport_players` has `name`, `position` and `team_id` (team of the latest loaded game). | Identity read gives 404 for an unknown NBA id and a team fallback when the lines carry none. The line's ESPN team wins when present. |
| Injury | `injury_index(report)` keys `(player_id, team)`. | `injury` is that entry for the player, null if none or the team is unknown. |
| Cost | `load_team_stats` runs `get_team_box_games(season, before)`, a **league-wide** box-score read per call (the board runs it once and caches 6.5 MB). Everything else here is small. | This is the one expensive piece. Step 5 times it; if the endpoint is not under 1 s warm, drop `teamStats` from the response and let 53b fetch it from the game endpoint. Decide on the measurement, not now. |

## In scope

- `GET /nba/players/{player_id}/props?date=YYYY-MM-DD` (optional `date`), read-only, no `require_api_key`, nothing paid. 404 for an unknown NBA player; 200 with `game: null` and `markets: []` when the player has no line that date.
- Repository: player identity, the player's lines for the date (modelled and line-only, wrappers over `_game_prop_lines`), the player's last 10 played games (existing reader, `limit=10`), the player's played games against the opponent (new, capped at 20).
- A pure builder that regroups `props_response` / `line_only_props` output into markets and sets `opponent`.
- Schemas, web type in `types/nba.ts`, `api/nba.ts` function, a typed `useNbaPlayerProps` hook (`staleTime` 5 minutes, key `['nba', 'player', playerId, 'props', date]`). No component uses the hook until 53b.

## Out of scope

- The page, route, tabs and chart (53b); rows opening the page and drawer removal (53c).
- Any change to the board, game endpoints, `props_response`, `line_only_props`, `_game_prop_lines`, the projection or its version.
- A game log, usage or season summary card (the NFL page's other cards). 53b's first cut is the prop tabs.
- New ingest, migrations, stored tables or snapshots.
- Preseason and partial-game lines (already excluded by `_SERVED_GAME_TYPES` and `segment = 'full_game'`).
- Any NFL file. 53b reuses the NFL chart and window helpers; whether that needs a sport-neutral extraction is a 53b question, not decided here.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.

## Build steps

- [x] **Step 1 - Schemas and pure builder** - the response schemas (Data / contracts) and a pure `player_props_response` taking the identity, game, `props_response` and `line_only_props` output for the player's lines, and the opponent rows. *Done when:* a new `test_nba_player_props.py` passes for: a modelled market with three rungs whose projection, gap, pOver and flags equal `props_response` for the same input (parity); a double-double market with null model fields; a null stat giving `value: null`, never zero; a team matching neither side giving `opponent: null` and `opponentGames: []`; no game giving `game: null, markets: []`; two rungs with one integer line carrying `integer_line` on that rung only; markets in `NBA_MARKETS` order; Last 5 equal to `recent[:5]`.
- [x] **Step 2 - Repository reads** - identity, the two per-player line wrappers, and the capped opponent read; the last-10 read is the existing function. *Done when:* run against the dev database for a guard with points and PRA lines, a big man and a player with only a double-double line: the lines equal that player's rows in `get_date_modelled_lines` / `get_date_line_only_lines` (print both), `recent` is newest first with 10 rows, `opponentGames` excludes the date itself, DNP and preseason, and never exceeds 20; the number of stored seasons the opponent read reaches is written into Notes; the board's reads are unchanged (`git diff` shows only additions to the repository).
- [x] **Step 3 - Service and router** - the service resolves the date (`slate_date`), finds the player's game from their lines, loads injury and team-stats context for it, composes Steps 1-2; the route returns 404 for an unknown player. *Done when:* a service test with a fake `db` (the `test_nba_prop_board.py` pattern) passes, including the unknown-player path; the service on the dev database for the three players returns the expected shape; the route gives 404 for an unknown id, 200 with empty markets for a date with no line, and 422 for a malformed `date`.
- [x] **Step 4 - Web type, API function, hook** - mirror the schema in `types/nba.ts`, add `fetchNbaPlayerProps` and `useNbaPlayerProps`. *Done when:* `npm --prefix web run verify` passes; nothing renders it yet.
- [x] **Step 5 - Verify and measure** - the Verify command, plus size and timing, plus the `teamStats` decision above. *Done when:* `npm --prefix web run verify && cd api && python -m pytest` passes (dummy `DATABASE_URL`), and a typical player's response over HTTP on the local API (selector-loop launcher) is under 40 KB and under 1 second warm, against the board's 6.5 MB and 1.7 s; the measurements and the `teamStats` outcome are written into Notes.

## Files / areas

- `api/app/schemas/nba.py`, `api/app/routers/nba.py`, `api/app/repositories/nba.py` (additions only)
- New `api/app/services/nba/player_props.py` (service and pure builder)
- New `api/tests/test_nba_player_props.py`
- `web/src/types/nba.ts`, `web/src/api/nba.ts`, `web/src/hooks/useNba.ts`

## Data / contracts

Load-bearing for 53b and 53c. camelCase on the wire.

```
NbaPlayerPropsResponse
  playerId, name, position, team          # team as the ESPN code, null when unknown
  date                                    # the slate date served
  game: { gameId, awayTeam, homeTeam, startUtc, status } | null
  opponent: string | null
  modelVersion
  injury: NbaInjury | null                # this player's entry
  injuryReport                            # the game's, for the evidence component
  teamStats: NbaTeamStatsContext | null   # may be dropped in Step 5, see Cost
  markets: NbaPlayerMarket[]              # NBA_MARKETS order; only markets with a line
NbaPlayerMarket
  market, kind: 'modelled' | 'line-only'
  projection: float | null, gamesInSample: int | null, priorMinutes: float | null   # null for line-only
  lines: NbaPlayerRung[]                  # line ascending, then oddsType
  recent: NbaPlayerGame[]                 # newest first, up to 10
  opponentGames: NbaPlayerGame[]          # newest first, up to 20; [] when opponent is null
NbaPlayerRung
  line, oddsType, fetchedAt
  gap, pOver, pUnder, overProbabilityVersion   # null for line-only
  flags: NbaPropFlag[]                          # per rung; [] for line-only
NbaPlayerGame
  gameDate, opponent: string | null, value: float | null   # null = stat not loaded, never zero
```

- `recent[:5]` equals the board's `recent` for the same line; a test pins it.
- Model fields come from `props_response`, so the board, game page and this endpoint cannot disagree.
- Reused types: `NbaInjury`, `NbaInjuryReport`, `NbaTeamStatsContext` exist in `types/nba.ts` and are not redefined.

## Testing

- Pytest, pure logic: Step 1 (including parity) and the Step 3 service test with a fake `db`. SQL is exercised on the dev database in Step 2 (external I/O is not unit tested, per the gate).
- No UI here; the web half is types and a hook, covered by `tsc`.

## Notes for the AI

- Display only. Never add a projection, version, edge, rank, sort-by-value or pick; model fields stay gray in 53b.
- `core/` stays pure, routers thin, SQL only in `repositories/`. Do not edit `props_response`, `line_only_props`, `_game_prop_lines`, the defaults of `get_recent_box_scores`, or the board's reads.
- Date handling: use `slate_date` with the Eastern "today" the router already computes, so the default date and the board agree.
- A player traded mid-season: opponent games are by the opposing team on the row, so they still work.
- Check DNP (`did_not_play`) and preseason exclusions in every new read.
- Windows: `npm.cmd`; pytest needs a dummy `DATABASE_URL`; the local API needs the selector-loop launcher; this worktree has no venv, use `C:\dev\SportAppV2\api\.venv`.
- No em dashes in code, comments or docs.

## Step 2 findings (dev database, 2026-11-02)

- Stored served seasons: 4 (2023 to 2026), so the opponent read can reach four seasons; a sampled big man had games against the opponent in 2 of them (2023 onward only for that career), a rookie guard had none.
- Per-player lines equal the board's rows for that player (modelled and line-only) for a guard (55 modelled rungs, 1 double-double) and a big man (28, 1). `recent` at limit 10 is newest first; the opponent read excludes the date, DNP rows, and is capped at 20.
- No player in the stored data has only a double-double line on any date, so that done-when case could not be exercised; the builder test covers it.
- Rung counts are large (55 for one guard), so Step 5's size check matters.
- Step 3 built the service as `services/nba/player_props_service.py` (the pure builder stays in `player_props.py`). Local HTTP check on the dev database: a guard 19.7 KB in 0.66 s and a big man 17.0 KB in 0.72 s warm, both with `teamStats`; unknown id 404, date with no line 200 with empty markets, bad date 422. Step 5 re-measures.
- Step 5: Verify passes (web typecheck, 1032 web tests, build; 5223 API tests). Measured in process through the real app against the dev database (not over a socket), 3 warm calls each, `teamStats` included: 10 markets 23.2 KB at 0.61 to 0.74 s; 8 markets 16.3 KB at 0.83 to 0.95 s; 1 market 5.0 KB at 0.73 to 0.80 s. Under the 40 KB and 1 s targets, so `teamStats` stays in the response (its league-wide read is most of the cost; the 0.7 to 0.9 s floor is that read plus the prior-games read). Timings on a 512 MB Render instance are unmeasured.

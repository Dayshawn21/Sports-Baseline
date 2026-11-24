# Feature: Other markets for one player (52a)

**From build-plan:** feature 52a (first half of 52, split approved 2026-11-02)
**Status:** complete (2026-11-02)
**Branch:** `feature/nfl-other-markets-tabs`

## Goal

A read-only per-player endpoint that returns every line-only market the player
has for a week (pass TDs, interceptions, combo yards, kicker and punter markets)
with its stored line and alternate lines, the player's last 10 values with game
dates, and earlier games against this week's opponent since 2024. 52b builds the
tabs on top of it. Display only: no projection, edge, rank, sort, pick, version
or color.

## Design reference

None (API only). 52b reuses the form chart from item 51.

## What reading the code settled

| Question | Answer | Consequence |
|---|---|---|
| Can the board payload carry longer history? | No. `/nfl/line-only-props` for week 8 2026 is 1,011 line rows over 213 player-market pairs (470 KB), and every rung row repeats the player's recent values. | New per-player endpoint; board and game endpoints unchanged. |
| Can `player.gameLog` serve it? | No: it has no pass TDs or interceptions. | Values come from `nfl_player_weekly_stats` through `line_only_value`. |
| Does `get_recent_stat_rows` serve it? | No: last 5, no dates, no season floor, no opponent filter, and it is shared with the board. | New repository query; the old one stays as is. |
| Where do the values come from? | `line_only_value` (`app/core/nfl_line_only.py`): FG made = `fg_made`, kicking points = `3*fg_made + pat_made`, punts = `punts`. A NULL input gives `None` ("not loaded"), never 0. | Reuse it. A kicker or punter uses the same rule, so there is no separate derivation. |
| Which lines? | `get_line_only_lines` shape: latest pre-kickoff snapshot per provider prop, `segment = 'full_game'`, joined to the game. Partial-game lines stay out. | New query for one player and week that returns the same fields plus the game's home and away codes. |
| This week's opponent | The line's game gives home and away codes; the player's team is `raw_json ->> 'player_team'`. Opponent = the other code. | If the player's team matches neither (alias or stale), `opponent` is null and vs Opponent is unavailable, with no guess. |
| Season floor | `PROJECTION_FIRST_HISTORY_SEASON` (2024) bounds the history, per `coding-standards.md`. | Both the last 10 and the opponent sample read `season >= 2024`, regular season, before (season, week). |
| Stored snapshot in production? | `/nfl/line-only-props` and the game variant are live queries, not `report_snapshots`. This endpoint is small (one player) and does the same kind of read, so it is live too. | No snapshot job, no 503 path. |

## In scope

- `GET /nfl/players/{player_id}/other-markets?season=&week=` (read-only, no
  `require_api_key`, nothing paid).
- Repository: one query for the player's line-only lines that week, one for the
  player's stat rows (last 10, with `game_date`, season floor 2024), one for
  earlier games against the opponent (same columns, same floor, no limit).
- A pure builder (in `app/core/` or beside `line_only_props.py`) that turns lines
  and rows into the response.
- Schemas, web types in `types/nfl.ts`, `api/nfl.ts` function and a `useNfl.ts`
  hook (typed, `staleTime` 5 minutes, key includes player, season, week). The hook
  has no component caller until 52b.

## Out of scope

- Any tab or UI change (52b). The Other markets section stays until 52b.
- The board and game endpoints, `NflLineOnlyLine`, `NflLineOnlyRecent`, the game
  page table and `get_recent_stat_rows`.
- Any new ingest, migration, stored table or snapshot.
- Playoff games and partial-game lines.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.

## Build steps

- [x] **Step 1 - Pure builder and schemas** - response schemas (below) and a pure function from lines, the player's recent rows and the opponent rows to the response: groups lines by market, orders markets by `NflLineOnlyMarket` order and rungs by line ascending, computes each value with `line_only_value`, keeps `None` values, sets `opponent` from the home and away codes and the player's team. *Done when:* a new `test_nfl_other_markets.py` passes for: one market with three rungs; a kicker market (FG made, kicking points); a punter (punts); a NULL stat giving `value: null`; a team matching neither code giving `opponent: null` and an empty opponent sample; a bye or first-game player giving empty `recent`; game dates carried through newest first.
- [x] **Step 2 - Repository queries** - the three reads above. *Done when:* the SQL runs against the dev database for a quarterback, a kicker and a punter in week 8 2026 (spot-check printed rows against `nfl_player_weekly_stats`), the stat query excludes the week itself and anything before 2024, and `get_recent_stat_rows` is unchanged.
- [x] **Step 3 - Router and service** - the service composes steps 1 and 2; the route returns 404 for an unknown player and an empty `markets` list (200) for a player with no line-only line that week. *Done when:* a service test with a fake `db` (same pattern as `test_nfl_line_only_props_service.py`) passes, `curl` on the hosted-data dev API returns the expected shape for one quarterback, one kicker and one punter, and the response for a running back is `markets: []`.
- [x] **Step 4 - Web type, API function, hook** - mirror the schema in `types/nfl.ts` and add the typed function and hook. *Done when:* `npm --prefix web run verify` passes; nothing renders it yet.
- [x] **Step 5 - Verify** - run the Verify command. *Done when:* `npm --prefix web run verify && cd api && python -m pytest` passes (dummy `DATABASE_URL`), and a size check shows a quarterback's response well under the board's 470 KB (target under 15 KB).

## Files / areas

- `api/app/schemas/nfl.py`, `api/app/routers/nfl.py`, `api/app/repositories/nfl.py`
- New `api/app/services/nfl/other_markets.py` (service) and a pure module for the builder
- New `api/tests/test_nfl_other_markets.py` (and a service test)
- `web/src/types/nfl.ts`, `web/src/api/nfl.ts`, `web/src/hooks/useNfl.ts`

## Data / contracts

Load-bearing for 52b. camelCase on the wire.

```
NflOtherMarketsResponse
  playerId, season, week
  opponent: string | null          # this week's opponent team code
  markets: NflOtherMarket[]        # NflLineOnlyMarket order
NflOtherMarket
  market: string                   # NflLineOnlyMarket value
  gameId: int
  lines: { line: float, oddsType: string | null, fetchedAt: datetime }[]   # line ascending
  recent: NflOtherMarketGame[]     # newest first, up to 10, season >= 2024
  opponentGames: NflOtherMarketGame[]   # newest first, all since 2024, [] when opponent is null
NflOtherMarketGame
  season, week, gameDate: date | null, opponent: string | null, value: float | null
```

- `value` is null when a needed stat is not loaded, never 0. 52b shows "not
  loaded" for it, not a zero bar.
- Last 5 is `recent[:5]` (pinned by a test), so 52b's three windows need one request.
- The market's "standard" line for the headline and the alternates split is a
  display choice for 52b, not part of this contract.

## Testing

- Pytest, pure logic: the builder cases in Step 1 and the service test in Step 3.
  The SQL is checked against the dev database in Step 2 (external I/O is not unit
  tested here, per the gate).
- No UI in this feature; the web half is types and a hook, covered by `tsc`.

## Notes for the AI

- Display only. Never add a projection, edge, rank, sort-by-value, pick or color.
- `core/` stays pure; routers stay thin; SQL only in `repositories/`.
- Do not touch `get_recent_stat_rows` or the board and game payloads; the game
  page table (`NflLineOnlyProps.tsx`) must keep working.
- Edge case to confirm in Step 2: a player traded mid-season has older games for
  another team; the opponent sample is by the opposing team on the row, so it
  still works. A kicker with no row for a week (bye or inactive) simply has no
  entry; do not zero-fill.
- Windows: use `npm.cmd`; run pytest from `api/` with the venv python and a dummy `DATABASE_URL`.
- No em dashes in code, comments or docs.

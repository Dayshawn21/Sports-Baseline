# Feature: NBA game API

**From build-plan:** feature 20e1 (first of 20e's three parts)
**Status:** complete (2026-10-06)

## Goal

Serve everything 20e2's slate and 20e3's game page need from a new `/nba`
router, read-only, from data 20b to 20d already store: one Eastern date's games
with scores, records, the latest market and line movement; one game with its
spread and total history; and one game's line-only PrizePicks lines with each
player's recent results. No UI in this part.

## In scope

- `GET /nba/slate?date=YYYY-MM-DD` (date optional).
- `GET /nba/games/{game_id}`.
- `GET /nba/games/{game_id}/line-only-props`.
- A pure `app/core/nba_slate.py` for the date choice and team records.
- Schemas in a new `app/schemas/nba.py`, services under `app/services/nba/`,
  SQL in `app/repositories/nba.py`, router `app/routers/nba.py` registered in
  `app/main.py` under `/nba`.

## Out of scope

- Any web change (20e2, 20e3).
- Preseason (`PRE`) games: never on the slate, never a game page, never a
  recent result (20b's rule).
- Projections, edges, P(over), any signal (20g).
- An NBA player page or player endpoint.
- Injuries (20a names ESPN's feed for display; no ingest exists yet).
- Rest days, team stats, or other game notes NFL's page shows.
- Unlinked prop lines (no `player_id`) on the line-only endpoint; they count
  toward the slate's prop line count only.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Slate date and team records (pure)** - `app/core/nba_slate.py`:
  - `slate_date(requested, today, game_dates)`: the requested date when given
    (even with no games); else `today` if it has games, else the next date
    with games, else the latest date with games, else `today`.
  - `adjacent_dates(date, game_dates)`: the nearest earlier and later dates
    with games (each None at the ends).
  - `team_records(results, before)`: W-L per team from completed `REG` games
    of the same season dated before `before`. A team with no game reads 0-0.

  *Done when:* tests pass for: requested date kept; today with games; today
  without games picks the next; after the last game picks the latest; no
  games at all gives today; adjacent dates at both ends; records count only
  completed `REG` games of the season strictly before the date (play-in,
  playoffs, last season, a game on the date itself and a scheduled game are
  all excluded).

- [x] **Step 2 - `GET /nba/slate`: games, records, market** - schemas, the
  repository reads (dates with games, a date's games with team names and
  scores, the season's completed results, the latest row per market), a pure
  builder in `app/services/nba/slate.py`, the router and its registration.
  `lineMovement` is `[]` and `propLineCount` 0 until Step 3. An unparseable
  `date` is a 422 (FastAPI's `date` type).

  *Done when:* builder tests pass (sides oriented home/away, win probability
  from the stored de-vigged moneyline, a market with no row gives null);
  against the running API on 2026-10-06, `/nba/slate` with no date returns
  2026-10-20 with its 3 games, DraftKings markets matching 20d's rows (BOS at DET -125/+105, home spread
  -2.5, total 221.5), records 0-0, `previousDate` 2026-06-13 (the 2025-26
  Finals' last stored date) and `nextDate` 2026-10-21; `?date=2026-10-10`
  returns `games: []` with the same adjacent dates; `?date=bad` is a 422.

- [x] **Step 3 - Slate line movement and prop counts** - two more repository
  reads folded into the builder: pre-tip line movement per game (one book per
  market, NFL's rule; a single stored row gives open = current) and the
  number of stored full-game PrizePicks lines per game (latest snapshot per
  provider prop, linked or not).

  *Done when:* builder tests cover movement mapping and a game with no
  movement or lines; the running API's 2026-10-20 games show `lineMovement`
  for spread and total from `draftkings` with open = current (one stored run
  so far), and `propLineCount` 61, 65 and 68 (the 194 opening-night lines stored
  by 20c, all on these 3 games).

- [x] **Step 4 - `GET /nba/games/{game_id}`** - the slate's game shape for one
  game (same repository reads, filtered to the id) plus spread and total line
  history (every pre-tip row from one book per market, reduced to changes by
  NFL's `line_history_steps`).

  *Done when:* tests cover the history mapping; the running API returns
  BOS at DET (id 21320) with the same market, records and movement as its
  slate entry and one history per market with one step; a `PRE` game id, an
  NFL game id and a missing id each return 404.

- [x] **Step 5 - `GET /nba/games/{game_id}/line-only-props`** - each linked
  full-game line-only line at its latest pre-tip snapshot, ordered by market
  (`NbaLineOnlyMarket` order), player name, line; each with the player's last
  5 played games (`did_not_play` false, `REG`/`PIN`/`PST`, dated before the
  game), newest first, valued by `line_only_value`.

  *Done when:* builder tests cover ordering, a NULL stat giving a null value,
  and double-double as 1 or 0, and the repository SQL excludes DNP and `PRE`
  rows; the running API returns game 21320's 61 lines (all linked), every
  market in `NbaLineOnlyMarket`, players with prior NBA games showing up to 5
  recent 2025-26 results and rookies an empty `recent`; a 404 as in Step 4.

## Files / areas

- New: `api/app/core/nba_slate.py`, `api/app/schemas/nba.py`,
  `api/app/services/nba/slate.py`, `api/app/services/nba/game_detail.py`,
  `api/app/services/nba/line_only_props.py`, `api/app/routers/nba.py`,
  `api/tests/test_nba_slate.py`, `api/tests/test_nba_game_api.py`
- Changed: `api/app/repositories/nba.py`, `api/app/main.py`
- Read only: `api/app/core/nfl_game_notes.py` (`line_history_steps`),
  `api/app/core/nba_line_only.py`, `api/app/nba/markets.py`

## Data / contracts

All responses camelCase (the `_CamelModel` convention). **Load-bearing for
20e2 and 20e3**; later NBA game-level display extends these responses or adds a
sibling under `/nba/games/{id}/`, never another page (33a's rule).

```
NbaSlateResponse
  date: date                    # the Eastern date served
  previousDate, nextDate: date | null   # nearest dates with games, any season
  games: NbaSlateGame[]          # by startUtc, then gameId

NbaSlateGame
  gameId, season, week (int | null), gameType ('REG' | 'PIN' | 'PST')
  gameDate, startUtc (datetime | null), status
  awayTeam, homeTeam            # ESPN codes
  awayTeamName, homeTeamName
  awayScore, homeScore          # null until completed
  awayRecord, homeRecord: { wins, losses }   # completed REG games this season before gameDate
  propLineCount: int            # stored full-game PrizePicks lines on the game, linked or not
  moneyline: { book, homeOdds, awayOdds, homeWinProbability, fetchedAt } | null
  spread:    { book, homeLine, homeOdds, awayOdds, fetchedAt } | null
  total:     { book, line, overOdds, underOdds, fetchedAt } | null
  lineMovement: [{ market: 'spread' | 'total', book, openLine, currentLine,
                   openFetchedAt, currentFetchedAt }]

NbaGameDetailResponse = NbaSlateGame + lineHistory: [{ market, book, steps: [{ fetchedAt, line }] }]

NbaLineOnlyPropsResponse
  gameId
  lines: [{ playerId, playerName, position, team, market, oddsType, line,
            fetchedAt, recent: [{ gameDate, opponent, value (float | null) }] }]
```

- **Market rule:** each market independently takes DraftKings' latest row,
  else the latest row from any lowercase book, so a card can mix books; each
  block names its own. `homeLine` is book sign (negative = home favored);
  `homeWinProbability` is the stored de-vigged `first_market_prob` (home is
  the first side, 20d).
- **Movement and history rule (NFL's):** pre-tip rows only (`fetched_at <
  start_utc`), one book per market (DraftKings when it has a row, else the book
  with the most rows), so a switch between books never reads as movement.
- **Records** count completed `REG` games only, so they read like a standings
  record; play-in and playoff games are excluded.
- **Postponed and canceled games** stay on their date with their `status`;
  20e2 decides how to show them.
- No schema change.

## Testing

- Test gate is on. Pure tests: `tests/test_nba_slate.py` (Step 1) and
  `tests/test_nba_game_api.py` (the builders in Steps 2 to 5, fed fixed rows).
- Endpoints are proved against the running API (`uvicorn app.main:app`, with
  the selector event loop on Windows per memory) and the real database, with
  response excerpts in each step's review.
- Run `cd api && .venv\Scripts\python.exe -m pytest` after each step.

## Notes for the AI

- Routers thin, services orchestrate, SQL only in `app/repositories/nba.py`,
  every `sport_*` reference with a `'nba'` literal (including joins through
  `sport_game_odds`, `sport_prop_lines`, `sport_teams`, `sport_players`).
- Every reader filters `game_type IN ('REG', 'PIN', 'PST')`; never `PRE`.
- `game_date` is the Eastern date; compute "today" with
  `ZoneInfo("America/New_York")`, never the server's local date.
- Reuse, don't copy: `line_history_steps` from `app/core/nfl_game_notes.py`
  and `line_only_value` from `app/core/nba_line_only.py`.
- Skip capitalized book keys (`o.book = lower(o.book)`), as NFL does.
- Read-only routes: no `require_api_key`.
- `X | None` hints, no `Any`, dataclasses inside, Pydantic only at the boundary.

## Results

Proved against the running API (a separate uvicorn on port 8001, selector
event loop) and the real database on 2026-10-06; the owner's own API on 8000
served the same responses.

- **Slate, no date:** `date` 2026-10-20, `previousDate` 2026-06-13,
  `nextDate` 2026-10-21; 3 games (BOS at DET, PHI at NY, OKC at SA), all
  records 0-0. BOS at DET on DraftKings: -125/+105 (home win probability
  0.532), home spread -2.5 (-105/-115), total 221.5 (-110/-110).
  `propLineCount` 61, 65, 68 (194). `lineMovement` spread and total from
  `draftkings` with open = current (one stored odds run). `?date=2026-10-10`:
  `games: []`, same adjacent dates. `?date=bad`: 422.
- **Records on a past date:** 2026-04-12 (last 2025-26 regular-season day)
  shows each team's record through 81 games (BOS 55-26, DET 59-22); market
  blocks null there (no 2025-26 odds stored).
- **Game 21320:** the response minus `lineHistory` equals its slate entry;
  one history step per market from `draftkings`.
- **Line-only props:** games 21320, 21319, 21318 return 61, 65 and 68 lines,
  every market in `NbaLineOnlyMarket`, team codes in ESPN form. PrizePicks'
  opening board has 2 players a game (Cunningham, Tatum; Brunson, LeBron
  James under PHI; Gilgeous-Alexander, Wembanyama), each with 5 recent
  played games (Cunningham's are May 2026 playoff games).
- **404s:** a `PRE` id (22521), an NFL id (1) and a missing id on both game
  endpoints.
- **Timing (warm):** slate 0.43 to 0.57 s, game 0.38 s, line-only props
  0.25 s. The first request after a restart took about 4 s.
- **Tests:** 25 new (`test_nba_slate.py` 8, `test_nba_game_api.py` 12, plus
  the builder additions); full suite 2,389 passed.

**Beyond the spec:**
- `assemble_games` (in `app/services/nba/slate.py`) is shared by the slate and
  game endpoints, so a game page can never disagree with its slate card.
- Market rows stored away- or under-first are reoriented home- or over-first
  (20d never stores them that way).
- `team_records` skips a completed game with a tied or missing score.
- `app/nba/markets.py` docstring: line-only markets are now shown gray, not
  "never shown".

**Not exercised live:** a rookie with no earlier games (empty `recent`); no
rookie has a line yet. Covered by a builder test.

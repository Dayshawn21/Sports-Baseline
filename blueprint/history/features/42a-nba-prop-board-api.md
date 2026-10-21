# Feature: NBA prop board API

**From build-plan:** 42a (parent 42, NBA prop board)
**Status:** complete (approved 2026-10-21; local implementation verified, deployment pending)
**Branch:** `feature/nba-prop-board-api`

## Goal

Serve every linked full-game NBA prop line for one Eastern date in one
response, so 42b's `/nba/board` can show a date's props across games without
a request per game. Each game's lines are built by the same functions the game
page uses (`props_response`, `line_only_props`), so a board row can never
disagree with the game page it came from.

Display only: no projection, P(over), edge, rank, sort or signal change.

## In scope

- `GET /nba/props?date=YYYY-MM-DD` (date optional) returning the date, its
  previous and next game dates, the model version, and each served game
  with its modelled and line-only lines.
- Date default and adjacent dates use the slate's own `slate_date` and
  `adjacent_dates` (`app/core/nba_slate.py`), so `/nba` and `/nba/board`
  open on the same date.
- One date-wide read per line kind (modelled, line-only), sharing the
  per-game query's SQL, instead of two queries per game.
- Pure response assembly with a parity test against the game-page builders.

## Out of scope

- The web page, registry entries, route, market pills and drawer (42b).
- Any ordering by gap, P(over) or edge. The API returns games in tip order
  (`_served_games` order) and each game's lines in the game page's
  `ordered_lines` order; 42b orders rows by tip time, then player.
- Moving `build_slate_gaps` onto the date-wide read (it works today; not
  this feature's job).
- Caching, report snapshots or a heavy rate-limit bucket. The build is
  bounded (one date, about 6 queries, a few hundred lines), like
  `/nba/slate/gaps`, which also builds on request.
- Schema, ingest, provider requests, projection or fit changes.

## Build loop

1. Explain the step and its checks before editing.
2. Implement only that step, with its tests.
3. Show the diff and evidence; wait for review before the next step.
4. Checkpoint commits are optional and need passing checks; `/complete` makes
   the feature commit.

## Build steps

- [x] **Step 1 - Date-wide line reads.** In `app/repositories/nba.py`, change
  `_game_prop_lines` to take a SQL condition and params (the `_served_games`
  pattern) and also select `l.game_id`. Keep `get_modelled_lines` and
  `get_line_only_lines` with unchanged signatures and returned keys (strip
  `game_id` so their callers see the same dicts). Add
  `get_date_modelled_lines(db, game_date)` and
  `get_date_line_only_lines(db, game_date)` returning
  `dict[int, list[dict]]` keyed by game id. Every query keeps `l.sport = 'nba'`,
  `g.sport = 'nba'`, `p.sport = 'nba'`, `segment = 'full_game'`,
  `_SERVED_GAME_TYPES`, the strict pre-tip `fetched_at < g.start_utc` cutoff
  and its market filter.
  *Done when:* the existing `tests/test_nba_repository.py` cases pass
  unchanged; new recording-session tests show that the date readers bind
  `:game_date`, carry every filter above, use the right market filter each,
  group rows by game id, and leave no `game_id` key on the line dicts.

- [x] **Step 2 - Board response.** Add `NbaPropBoardGameSchema` and
  `NbaPropBoardResponse` to `app/schemas/nba.py` and a new
  `app/services/nba/prop_board.py` with pure
  `prop_board_response(date, previous_date, next_date, games, modelled_by_game,
  line_only_by_game, prior_by_player, recent_rows)` that, for each game, takes
  `lines` from `props_response(...)` and `line_only_lines` from
  `line_only_props(...)`.
  *Done when:* `tests/test_nba_prop_board.py` shows that each game's `lines` and
  `lineOnlyLines` equal `props_response` / `line_only_props` output for the
  same inputs (parity); games keep input order; a game with no lines appears
  with two empty lists; no games gives `games: []`; the response serializes
  camelCase with `modelVersion` `nba-reference-v1`.

- [x] **Step 3 - Service and route.** Async `build_prop_board(db, requested,
  today)`: `get_game_dates` -> `slate_date` -> `adjacent_dates` ->
  `get_games_on`, then the two date-wide reads, then `get_prior_games` and
  `get_recent_box_scores` once each for all players on the date (skipped when
  there are none), then `prop_board_response`. Route
  `GET /nba/props` in `app/routers/nba.py` with the slate's Eastern `today`.
  *Done when:* a service test with a mocked repository shows the call order,
  one prior and one recent read for all players, no player reads on a date
  without lines, and the resolved date and adjacent dates passed through; a
  local `curl "http://127.0.0.1:8000/nba/props?date=<a game date>"` returns the
  date's games, and for one of them its `lines` match
  `/nba/games/{id}/props` and its `lineOnlyLines` match
  `/nba/games/{id}/line-only-props` exactly (compare with `jq`); a date
  with no games returns 200 with `games: []` and its adjacent dates.

## Files / areas

- `api/app/repositories/nba.py` - shared prop-line SQL, two date readers
- `api/app/schemas/nba.py` - board schemas
- `api/app/services/nba/prop_board.py` - new: pure assembly plus async build
- `api/app/routers/nba.py` - `GET /nba/props`
- `api/tests/test_nba_repository.py`, `api/tests/test_nba_prop_board.py` (new)

## Data / contracts

**Load-bearing for 42b:** `GET /nba/props?date=` (`NbaPropBoardResponse`, camelCase):

```text
NbaPropBoardResponse
  date: date                    # resolved Eastern date (slate_date rule)
  previousDate: date | null     # adjacent served game dates (adjacent_dates)
  nextDate: date | null
  modelVersion: str             # NBA_PROJECTION_MODEL_VERSION
  games: NbaPropBoardGameSchema[]   # tip order, as get_games_on

NbaPropBoardGameSchema
  gameId: int
  awayTeam: str                 # ESPN codes, as the slate
  homeTeam: str
  startUtc: datetime | null
  status: str                   # scheduled | completed | postponed | canceled
  lines: NbaPropLineSchema[]          # == /nba/games/{id}/props lines
  lineOnlyLines: NbaLineOnlyLineSchema[]  # == /nba/games/{id}/line-only-props lines
```

- Lines reuse the existing schemas unchanged; null still means not served,
  never zero.
- Lines are the last snapshot before tip-off, so a started or final game
  still shows the lines the game page shows. 42b labels status; the API
  never drops a game for having tipped.
- No database change.
- **Extension rule:** 42c (injuries) and 42d (team stats) add their board
  context by extending these schemas with new nullable fields (for example a
  per-line injury status, a per-game opponent stats block), never by
  changing existing fields or adding a second board endpoint. 42a adds no
  placeholder fields for them.

## Testing

Test gate is on (`AGENTS.md`). Logic tests per step:

- Step 1: SQL shape and grouping, through the existing recording-session
  pattern in `tests/test_nba_repository.py`.
- Step 2: parity and edge cases for the pure `prop_board_response`.
- Step 3: service orchestration with mocked repository calls; the route and
  live parity are proved with `curl` against the local API (not unit-tested,
  per the standards).

Final gate: `npm --prefix web run verify && cd api && python -m pytest`
(from `api/`, use `.venv\Scripts\python.exe -m pytest`).

## Notes for the AI

- Step 1 approved (2026-10-21): date-wide readers and compatibility
  tests implemented on `feature/nba-prop-board-api`. Focused repository
  tests: 23 passed. Full Verify passed: 644 web tests, production build,
  and 3,461 API tests. User chose Continue without a checkpoint commit.
- Step 2 approved (2026-10-21): board schemas and pure assembly
  implemented with five board tests for parity, ordering, empty results,
  nullable fields, and camelCase serialization. Focused tests: 23 passed.
  Full Verify passed: 644 web tests, production build, and 3,466 API tests.
  User chose Continue without a checkpoint commit.

- Step 3 approved (2026-10-21): async board service and public
  `GET /nba/props` implemented. Four orchestration cases cover call order,
  combined deduplicated player reads, resolved dates/navigation, and skipping
  history reads without lines. Focused tests: 32 passed. Full Verify passed:
  644 web tests, production build, and 3,470 API tests.
- Live `/check` passed using the selector-loop API on port 8003 with the
  configured database (read-only requests). `curl.exe` fetched JSON and
  Python compared full arrays because `jq` is unavailable. For 2026-10-20,
  games 21320, 21319, 21318 matched both game endpoints exactly (2,922
  modelled lines and 36 line-only lines total). Game 21316 on 2026-10-21
  also matched. Default board/slate dates, adjacent dates, and game order
  matched (11 games). Explicit 2026-10-19 returned HTTP 200 with `games: []`,
  previous date 2026-06-13 and next date 2026-10-20.
- Operational observation: 2026-10-21 actually serves 7,986 modelled and
  111 line-only lines, exceeding the spec's few-hundred-lines estimate.
  A local curl measured 4,877,159 bytes and 1.91 seconds. Render's 512 MB
  production service has not been exercised; payload and memory review is
  a follow-up. No pagination, truncation or cache was added to this contract.
- All three steps approved. No checkpoint commits.
  Findings ledger has no open or fixed P0/P1; F-09 and F-12 remain
  unverified, unrelated P3/P2 follow-ups.

- Layering: SQL only in the repository; the service orchestrates; assembly
  stays pure and testable. `app/core/` is untouched.
- Every `sport_*` read carries `sport = 'nba'`; NBA readers exclude `PRE`
  through `_SERVED_GAME_TYPES`; modelled reads use
  `NBA_MODELLED_MARKET_FILTER` (invariants).
- One pre-tip cutoff per date is correct because `get_prior_games` and
  `get_recent_box_scores` cut at the game's Eastern date, which every game
  on the board shares (`build_slate_gaps` relies on the same fact).
- Do not change `props_response`, `line_only_props`, `ordered_lines` or the
  per-game endpoints' output. Parity depends on calling them, not
  reimplementing them.
- Run the local API with the selector-loop launcher (memory:
  local-api-selector-loop); plain uvicorn fails on Windows.
- The interview guide needs no update for 42a alone; reconsider at 42b's
  `/complete` when the board ships.

## Completion review

- Invariants review: clean for sport/game-type/market filters, repository
  boundaries, unchanged versions and projections, secrets, and display rules.
  The request builds one date using existing lightweight projection functions;
  the measured payload and unverified production memory are recorded above.
- Final gate: `npm --prefix web run verify && cd api && python -m pytest`
  with the API venv on PATH passed in this session (644 web tests, production
  build, 3,470 API tests). Existing bundle-size and Starlette deprecation
  warnings remain. No deployment or remote change was performed.
- Manual try: run the selector-loop API launcher from README.md, then
  `curl.exe http://127.0.0.1:8000/nba/props?date=2026-10-20`. Expect the
  three games and both line arrays per game. `date=2026-10-19` returns
  an empty games list with adjacent dates.
- The interview guide is unchanged as specified for 42a alone; revisit at
  42b completion. No workflow adapters changed.

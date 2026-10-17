# Feature: NBA game odds

**From build-plan:** feature 20d
**Status:** complete (2026-10-06)

## Goal

Store NBA moneyline, spread and total from The Odds API in `sport_game_odds`
(`sport = 'nba'`), de-vigged, twice a day, without ever spending the credits
NFL's anytime-TD runs depend on. This is the market 20e's slate and game page
show, and the early and near-tip line history any later NBA CLV check needs.

## In scope

- A pure `app/core/nba_odds.py`: The Odds API NBA team names mapped to ESPN
  `team_code`s, and matching a provider event to one stored NBA game.
- Reusing `parse_game_markets` from `app/core/nfl_odds.py` unchanged (it is
  sport-agnostic: `h2h`, `spreads`, `totals`, oriented to the stored home
  team, de-vigged by `implied_prob_from_american`).
- NBA repository reads and writes in `app/repositories/nba.py`, every one with a
  `sport = 'nba'` literal.
- `python -m app.ingest.nba_odds [--days-ahead 2] [--min-credits 100] [--dry-run]`:
  one paid `/odds` call (3 credits), guarded by a free credit check before it.
- `nba-odds.yml`, daily at 15:00 and 22:30 UTC, October to June (20a's
  schedule, about 180 credits a month).
- `AGENTS.md` Commands entry.

## Out of scope

- Any display: the slate, game page and line movement are 20e.
- Preseason odds (`basketball_nba_preseason`); `PRE` games are never matched.
- NBA player props from The Odds API (20a: about 210 credits a month, not
  affordable).
- A CLV check or any model use of the stored lines.
- Refactoring NFL's odds ingest or repository into a shared module. NFL code is
  imported, not edited.
- Schema changes: `sport_game_odds` already takes any sport, and its market
  check (`moneyline | spread | total`) already fits.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Team map and game matching (pure)** - `app/core/nba_odds.py`:
  - `odds_api_team_code(name)`: the 30 The Odds API full names
    (`"Los Angeles Clippers"`, `"Golden State Warriors"`, ...) to ESPN codes
    (`LAC`, `GS`, `NY`, `SA`, `NO`, `UTAH`, `WSH`, ...), casefolded and
    whitespace-normalized; unknown names give None, never a guess.
  - `match_nba_game(event, games)`: both teams match (either orientation) and
    the provider `commence_time` is within 6 hours of the stored `start_utc`;
    returns `(game_id, provider_home_is_stored_home)` only when exactly one game
    qualifies. A malformed `commence_time`, an unknown team, a game with no
    `start_utc`, or two candidates gives None.

  *Done when:* the map's 30 names are checked against one free
  `GET /v4/sports/basketball_nba/events` call (0 credits, `x-requests-last` 0;
  every listed team name maps), and tests pass for: the map covers exactly
  `NBA_TEAM_CODES`; a normal match; a reversed home/away event; a provider
  time 10 minutes off the stored tip (20a's observed offset) still matches; a
  game 7+ hours off does not; the same teams on consecutive nights each match
  their own game; two synthetic candidates inside the window give None; an
  unknown team, a missing `start_utc` and a bad timestamp give None.

- [x] **Step 2 - Repository and ingest** -
  - `nba_repo.get_upcoming_odds_games(db, days_ahead)`: `sport = 'nba'`,
    `game_type IN ('REG', 'PIN', 'PST')`, `status = 'scheduled'`,
    `start_utc` not null, `game_date` from yesterday to today + `days_ahead`,
    returning game id, `start_utc`, home and away `team_code`.
  - `nba_repo.insert_game_odds_snapshot(...)`: the NFL insert's columns with a
    `'nba'` literal.
  - `app/ingest/nba_odds.py`, reusing `BASE_URL`, `_provider_key`,
    `_remaining_requests` and `_bookmaker_sets` from `app/ingest/nfl_odds.py`
    (`nfl_prop_odds` already imports them):
    1. Load upcoming games; with none, log and exit **without any provider call**.
    2. Free `GET /v4/sports` to read `x-requests-remaining`; below
       `--min-credits` (default 100), or header missing, log a warning and exit
       without the paid call.
    3. One `GET /v4/sports/basketball_nba/odds/` (`us`, `h2h,spreads,totals`,
       American, ISO).
    4. Match, parse, insert per book; count `matched`, `unmatched`, `stored`;
       one commit. `--dry-run` writes nothing.
    5. HTTP errors (401, 429, 5xx) raise, so the workflow run fails visibly.

  *Done when:* tests pass for the sport key, request params, and a pure
  `credit_gate(remaining, floor)` (None and below-floor block; at-floor
  allows); `pytest` is green; no provider call has been made yet.

- [x] **Step 3 - Live run (spends credits; ask first)** - with approval, confirm
  2026-27 regular-season games are stored (opening night 2026-10-20), then run
  `python -m app.ingest.nba_odds --days-ahead 16 --dry-run` (3 credits), then
  without `--dry-run` (3 credits). Do this only after both steps above are
  approved.

  *Done when:* the free pre-check reports remaining credits and costs 0
  (`x-requests-last` 0); the dry run reports matched games and 0 rows written;
  the real run stores rows, and a query shows `sport = 'nba'` rows in
  `sport_game_odds` for opening-night games: moneyline, spread and total from
  at least one book per matched game (DraftKings where offered),
  `first_market_prob + second_market_prob` = 1 on every row, and a line on
  every spread and total row. Unmatched
  events, if any, are listed and explained (expected: games beyond the
  window). NFL row counts in `sport_game_odds` are unchanged.

- [x] **Step 4 - Schedule and docs** - `.github/workflows/nba-odds.yml`
  (`cron: "0 15 * 1-6,10-12 *"` and `"30 22 * 1-6,10-12 *"`,
  `workflow_dispatch`, `contents: read`, `DATABASE_URL` and
  `THE_ODDS_API_KEY` secrets, `python -m app.ingest.nba_odds`), with a header
  comment stating the credit cost and the floor, and that a manual dispatch
  also spends 3 credits. Do not trigger it from here. Add the command to
  `AGENTS.md` under Ingest.

  *Done when:* the workflow YAML parses, its times avoid every
  `nfl-prop-odds.yml` run, and `AGENTS.md` lists the command with its flags.

## Files / areas

- New: `api/app/core/nba_odds.py`, `api/app/ingest/nba_odds.py`,
  `api/tests/test_nba_odds.py`, `.github/workflows/nba-odds.yml`
- Changed: `api/app/repositories/nba.py`, `AGENTS.md`
- Read only: `api/app/core/nfl_odds.py`, `api/app/ingest/nfl_odds.py`

## Data / contracts

- **No schema change.** Rows go to `sport_game_odds` with `sport = 'nba'`,
  sides `home`/`away` (moneyline, spread) and `over`/`under` (total), `line`
  in book sign (negative home spread = home favored), `book` as The Odds API's
  lowercase key.
- **Load-bearing for 20e:** an NBA game's market is read from these rows, the
  same shape NFL's slate reads (latest per market, DraftKings preferred).
  Append-only: one row per book per market per run.
- **Load-bearing for the budget:** `--min-credits 100` is checked before any
  spend, so NBA stops with at least 100 credits left; NFL's anytime-TD floor is
  50, leaving it room for its weekly runs. Changing either floor means
  reviewing both.

## Testing

- Test gate is on. `api/tests/test_nba_odds.py` covers Step 1's map and matcher
  and Step 2's params and `credit_gate`. The HTTP and DB path is proved by Step
  3's live run, not mocked integration tests.
- Run `cd api && .venv\Scripts\python.exe -m pytest` after Steps 1 and 2.
- No web change, so no web build is needed.

## Notes for the AI

- **Never call `/odds` without explicit approval in the current chat.** Each
  call is 3 credits from a 500-a-month shared plan. `/sports` and `/events`
  are free.
- Every `sport_*` query carries `sport = 'nba'` as a literal, even across the
  game foreign key (`sport_game_odds.game_id` is not sport-scoped).
- NBA `game_date` is the Eastern date; match on `start_utc`, not on date.
- Never match `PRE` games; filter `game_type IN ('REG', 'PIN', 'PST')`.
- Keep `app/core/nba_odds.py` pure (no DB, no HTTP).
- Do not edit NFL's odds modules; import from them, as `nba_resolution`
  imports `nfl_resolution`.
- Windows: set `WindowsSelectorEventLoopPolicy` in `__main__`, as `nfl_odds`
  does.

## Results

- **Free events probe (2026-10-06):** 46 `basketball_nba` events, exactly 30
  team names, all mapped; credits 466 before and after (`x-requests-last` 0).
- **Dry run** (`--days-ahead 16`): `games=16 matched=16 unmatched=30
  stored=260`, nothing written; credits 466 to 463, so the free `/sports`
  pre-check cost 0. All 30 unmatched events tip off 2026-10-23 or later,
  outside the window.
- **Real run:** 260 rows, `sport = 'nba'`, 16 opening-week games, 7 books
  (draftkings, fanduel, betrivers, betmgm 42 each; bovada 36; betonlineag,
  lowvig 28). Every game has all three markets from at least one book;
  DraftKings prices 14 of 16. 0 rows with probabilities off 1, 0 spread or
  total rows without a line, 0 rows on a non-NBA game. NFL rows unchanged
  (3,491). Credits 463 to 460.
- **Orientation check:** BOS at DET on DraftKings: DET -125 (0.532 de-vigged),
  home spread -2.50, total 221.5.
- **Tests:** 13 in `tests/test_nba_odds.py`; full suite 2,369 passed.
- **Additions beyond the spec:** unmatched events log at debug with teams and
  commence time; `--dry-run` help text warns it still spends 3 credits.
- **Known risk:** GitHub can start scheduled runs 2 to 3 hours late, which
  would cost the 22:30 UTC run its near-tip line for 7 pm ET games.

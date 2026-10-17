# Feature: Bet365 and DraftKings NFL odds from Odds-API.io, plus Pinnacle

**From build-plan:** feature 36a (first of 36's two parts)
**Status:** complete (2026-10-07)

## Goal

Store fresh Bet365 and DraftKings NFL game prices (moneyline, main spread, main
total) from Odds-API.io several times a day, and Pinnacle's from The Odds API,
in `sport_game_odds`, each row tagged with the feed it came from. 36b then shows
each side's best price beside a Pinnacle fair price.

**Why:** the stored NFL prices are days old (week 5's latest are from
2026-10-01; the line has since moved from DAL -9.5 to -8.5), and Bet365 is
not available from The Odds API at all. Odds-API.io's free plan is limited by
the hour, not the month, so a full slate costs 3 requests a refresh and no
credits.

**Nothing is displayed yet.** No reader changes what it shows; 36b adds the
display.

## In scope

- A `provider` column on `sport_game_odds`, every existing row tagged
  `the_odds_api_us`, and every existing reader filtered to that value, so
  item 28's frozen CLV sample, the NFL slate market, line movement, game
  notes and the NBA slate cannot see new rows.
- A pure parser for Odds-API.io NFL events: moneyline, main spread and main
  total per book, in book sign and American odds, de-vigged.
- `python -m app.ingest.nfl_odds_io [--days-ahead 7] [--min-requests-remaining 20] [--dry-run]`,
  storing provider `odds_api_io` rows for Bet365 and DraftKings.
- `python -m app.ingest.nfl_odds --pinnacle`, one The Odds API request for
  Pinnacle only, storing provider `the_odds_api_eu` rows.
- A new `nfl-odds-io.yml` workflow (every 3 hours, September to February) and
  a Pinnacle step in the Tuesday `nfl-ingest.yml` job.

## Out of scope

- Any display, best-line rule or fair-price rule (36b).
- Player props from Odds-API.io (the prop-comparison item after 36; the
  same request returns them, so the parser leaves room but stores none).
- NBA from Odds-API.io, and changing the Odds-API.io book selection
  (DraftKings and Bet365 are locked across sports and tennis relies on them).
- Half, quarter, team-total and alternate lines.
- Why Tuesday's 2026-10-06 `nfl_odds` run stored nothing (open question 44):
  Step 4's real run will show whether the local command still works; the
  GitHub-side cause is a `/debug`.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Provider column and reader filters** - migration `0044`
  adds `provider text NOT NULL DEFAULT 'the_odds_api_us'` to
  `sport_game_odds` (every existing row takes it), with a check constraint on
  the three values, and ends with `ANALYZE sport_game_odds`. Both writers
  (`nfl_repo.insert_game_odds_snapshot`, `nba_repo.insert_game_odds_snapshot`)
  pass `provider` explicitly. Every reader adds `o.provider = 'the_odds_api_us'`:
  NFL `get_latest_game_odds`, `get_game_line_clv_games`,
  `get_week_line_movement`, `get_game_line_history`,
  `get_slate_market_probabilities`, `get_slate_matchup_context`,
  `get_settled_prop_prices`; NBA `get_game_line_history`,
  `get_latest_market_rows`, `get_line_movement`. A guard test fails if any
  SQL string in `app/` that reads `sport_game_odds` lacks a `provider`
  filter. *Done when:* `alembic upgrade head` reaches `0044`; every existing
  row reads `the_odds_api_us`; `pytest` passes; and these outputs are
  byte-identical before and after the migration:
  `python -m app.backtest.nfl_game_line_clv --season 2026`,
  `GET /nfl/game-notes?season=2026&week=5`, `GET /nfl/slate?season=2026&week=5`
  (odds and model blocks) and `GET /nba/slate?date=2026-10-20`.
- [x] **Step 2 - Odds-API.io NFL parser** - pure
  `app/core/nfl_odds_io.py`: from one Odds-API.io event's `bookmakers`, one
  row per book per market (`moneyline`, `spread`, `total`) in the same shape
  `parse_game_markets` returns, so `insert_game_odds_snapshot` takes it
  unchanged. Decimal strings become American with `decimal_to_american`; the
  main spread and total are the ladder rung with the lowest overround, then
  the one closest to even (alternates carry more vig than the line the book
  sets: Bet365's DAL -9.5 at 1.050 against about 1.09 beside it); `hdp` is the home handicap in book sign; sides flip when the provider's
  home is the stored away team. Markets other than `ML`, `Spread` and `Totals`
  are ignored. *Done when:* tests on a trimmed recording of the 2026-10-07 TB
  at DAL payload give DraftKings DAL -8.5 (-116 / -105), total 47.5, ML -476 /
  +360, and Bet365's main spread from its 77-rung ladder (DAL -9.5, -108 /
  -114); a flipped home, a missing or
  zero price, and a one-sided rung are covered.
- [x] **Step 3 - Odds-API.io ingest** - `app/ingest/nfl_odds_io.py`: list
  `american-football` events, keep `usa-nfl` events still `pending`, match
  each to a stored scheduled game with `match_scheduled_game` (skipping and
  counting unmatched or already-started games), fetch `/odds/multi` in
  batches of at most 10 events for `Bet365,DraftKings`, and store each parsed
  row with provider `odds_api_io` and the book lowercased (`bet365`,
  `draftkings`). It reads the `x-ratelimit-remaining` header and stops before
  a request that would leave fewer than `--min-requests-remaining` (default
  20), so tennis keeps its share of the hour. No retries. *Done when:* the
  batching and floor helpers have tests; a `--dry-run` prints matched games,
  rows and requests used; a real run stores up to 90 rows (15 games x 2
  books x 3 markets) in 3 requests; and Step 1's identity outputs are still
  byte-identical.
- [x] **Step 4 - Pinnacle from The Odds API** - `nfl_odds --pinnacle` makes
  one request with `bookmakers=pinnacle` (instead of `regions=us`) and stores
  provider `the_odds_api_eu` rows through the same matcher and parser, under
  the same credit floor. The default run is unchanged and stores
  `the_odds_api_us`. *Done when:* a real `--pinnacle` run stores Pinnacle
  moneyline, spread and total rows for this week's games, the response's
  `x-requests-last` reads 3, and Step 1's identity outputs are unchanged.
- [x] **Step 5 - Schedules** - new `nfl-odds-io.yml` (`ODDS_API_KEY` secret,
  every 3 hours September to February, `python -m app.ingest.nfl_odds_io`),
  and a "Refresh Pinnacle NFL odds" step (`nfl_odds --days-ahead 14
  --pinnacle`, `continue-on-error`) after "Refresh NFL game odds" in the
  Tuesday `nfl-ingest.yml` and after the anytime-TD fetch in all four
  `nfl-prop-odds.yml` runs (option B, chosen 2026-10-07 so the fair price is
  under a day old at bet time). *Done when:* the three files parse as YAML,
  each step runs the exact command Steps 3 and 4 proved locally, and the
  budget comments match: about 24 Odds-API.io requests a day, 15 credits a
  week for Pinnacle (3 Tuesday plus 12 across the prop-odds runs).

## Files / areas

- `api/app/db/migrations/versions/0044_sport_game_odds_provider.py` (new)
- `api/app/repositories/nfl.py`, `api/app/repositories/nba.py` (writers and
  readers)
- `api/app/core/nfl_odds_io.py` (new, pure)
- `api/app/ingest/nfl_odds_io.py` (new), `api/app/ingest/nfl_odds.py`
  (`--pinnacle`), `api/app/ingest/nba_odds.py` (passes provider)
- `api/tests/test_sport_game_odds_provider.py` (guard), `api/tests/test_nfl_odds_io.py`
  and `api/tests/fixtures/` (recorded payload)
- `.github/workflows/nfl-odds-io.yml` (new), `.github/workflows/nfl-ingest.yml`

## Data / contracts

**`sport_game_odds.provider`** (load-bearing for 36b and every later odds
reader):

| Value | Feed | Books |
|---|---|---|
| `the_odds_api_us` | The Odds API `regions=us` (every row before `0044`) | draftkings, fanduel, betrivers, offshore books |
| `the_odds_api_eu` | The Odds API `bookmakers=pinnacle` | pinnacle |
| `odds_api_io` | Odds-API.io `/odds/multi` | bet365, draftkings |

- **Every reader names its provider.** A new reader that wants several feeds
  lists them; none reads the table unfiltered. The guard test enforces it.
- **Item 28 and line movement stay on `the_odds_api_us`.** DraftKings now
  exists under two providers; they are never merged.
- **The default stays.** `DEFAULT 'the_odds_api_us'` is kept so the GitHub
  workflows running pre-36a code (`nba-odds.yml` twice a day) keep inserting
  valid rows until this branch is pushed.
- **Row shape is unchanged:** book-sign `line` (negative home spread = home
  favored), American `first_odds`/`second_odds`, de-vigged probabilities,
  `fetched_at` = our fetch time. Odds-API.io's per-market `updatedAt` is kept
  in `raw_json`: a market can be unchanged for a day (the 2026-10-07 total
  read 2026-10-06) and still be the current price.

**Probe findings (2026-10-07) this spec relies on:**
- Odds-API.io's free plan allows exactly DraftKings and Bet365 ("max 2
  bookmakers"); sharp books return 403.
- `/odds/multi` takes at most 10 `eventIds`; a 15-game slate is 2 calls plus
  `/events`, about 611 KB and 0.4 s.
- DraftKings prices match The Odds API's at the same moment (game lines and
  14 of 14 anytime TD prices); gaps of a few cents are decimal rounding.
- Bet365 sends spreads as a ladder (+11.5 at 1.02 down to +3 and beyond), so
  the main line must be chosen, the mistake the tennis Bet365 parser made
  (open question 33).

## Testing

Test gate is on (`pytest`, `npm run test`).

- **Logic with tests:** the parser (Step 2: main-rung choice, decimal
  conversion, home flip, missing prices), the batching and rate-floor helpers
  (Step 3), the `--pinnacle` request parameters (Step 4), and the provider
  guard (Step 1).
- **Proved by running:** the migration, identity of the four reader outputs
  (Steps 1, 3, 4), and real ingest runs with request and credit counts.
- No web change, so no web tests or build change; run `npm run build` once at
  the end anyway.

## Notes for the AI

- Run `alembic upgrade` and `downgrade` one at a time, never chained (a
  chained downgrade wiped data once). The `0044` downgrade deletes non-`us`
  rows before dropping the column, so pre-36a code never reads them.
- Every SQL on `sport_*` carries its sport filter; the new provider filter is
  in addition, never instead.
- Never retry an Odds-API.io or The Odds API request; log and continue, as
  the existing ingests do.
- Odds-API.io returns events with status `pending`; a started or settled game
  is never stored as pre-kickoff.
- The Odds API's `bookmakers` parameter replaces `regions`; Pinnacle may lag
  ("odds are from public website which may incur a delay"), so 36b shows its
  age.
- Item 28's rule text ("any lowercase The Odds API book") is unchanged:
  `the_odds_api_us` is exactly the set it was written against.

## Results

Built 2026-10-07 on `feature/nfl-best-line-odds`.

- **Step 1.** `alembic upgrade head` ran `0043 -> 0044`; every existing row
  read `the_odds_api_us` (3,491 NFL, 260 NBA). The guard test finds all 10
  readers (7 NFL, 3 NBA). Seven outputs were byte-identical before and after:
  `nfl_game_line_clv --season 2026` (1,119 bytes), `/nfl/game-notes` week 5
  (34,652), `/nfl/slate` week 5 odds and model blocks (5,325),
  `/nfl/games/65` (375), `nfl_prop_market` (1,909), `/nba/slate?date=2026-10-20`
  (3,400) and `/nba/games/21320` (1,329). They stayed identical after Steps 3
  and 4 stored the new feeds.
- **Step 2.** The recorded TB at DAL payload parses to DraftKings ML -476 /
  +360, spread DAL -8.5 (-116 / -105), total 47.5; Bet365's 77-rung ladder
  gives DAL -9.5 (-108 / -114). **Changed from the draft:** the main rung is
  the lowest overround, then the one closest to even. Bet365 offered no -8.5
  rung; its -9.5 carried 1.050 against about 1.09 beside it.
- **Step 3.** `python -m app.ingest.nfl_odds_io`: 3 requests, 15 games
  matched, 90 rows (15 games x 2 books x 3 markets); the 14 skipped events
  were week 6, outside the 7-day window. `raw_json` keeps the chosen rung,
  `updatedAt` and the rung count, not the ladder (about 90 MB a season saved).
- **Step 4.** `python -m app.ingest.nfl_odds --pinnacle`: 3 credits a run
  (dry run included, 455 -> 452 -> 449); Pinnacle priced all 15 week 5 games,
  none of week 6 yet.
- **Step 5.** Option B: Pinnacle refreshes Tuesday and in all four
  `nfl-prop-odds.yml` runs (about 15 credits a week).
- **Suites:** `pytest` 2,483 passed; `npm run build` clean (no web change).

**TB at DAL, 2026-10-07, all three feeds:**

| Feed | Moneyline | Spread | Total |
|---|---|---|---|
| Pinnacle | DAL -446 / TB +353 | DAL -8 (-103 / -110) | 47.5 (-108 / -106) |
| DraftKings | -476 / +360 | DAL -8.5 (-116 / -105) | 47.5 (-116 / -105) |
| Bet365 | -500 / +370 | DAL -9.5 (-108 / -114) | 47.5 (-111 / -110) |

**Found while building, not fixed here:** the newest NBA odds row is
2026-10-06 14:34 UTC and the newest NFL `us` row 2026-10-01, so both
scheduled The Odds API workflows stopped storing (open question 44, now
covering NBA as well). A `/debug` should run before relying on the new
schedules.

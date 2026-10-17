# Feature: NFL sportsbook anytime TD odds

**From build-plan:** feature 19i
**Status:** complete (2026-09-18)

## Goal

Pull sportsbook `player_anytime_td` prices from The Odds API once per game week,
turn them into one market probability per player, and show it next to the
model's anytime-TD baseline on the NFL slate. PrizePicks TD lines are nearly all
goblin or demon, so today the slate cannot say whether a TD baseline is
optimistic. A sportsbook price can.

The Odds API key is on the free plan (500 credits a month; 490 left on
2026-09-18). Every request that costs credits must be bounded and stop at a
safety floor.

## In scope

- Append-only storage of per-book, per-player anytime-TD prices (migration `0023`).
- A pure parser plus a probability rule for Yes-only and Yes/No markets.
- An ingest command that lists events for free, then fetches prices per upcoming
  game, one market, `us` region, stopping at a credit floor.
- A configured market map, so adding `player_rush_yds` later is a config change
  plus its own parser rule, not a new ingest.
- Scheduled runs: Thursday before the Thursday game, and Sunday morning for the
  Sunday and Monday games.
- The latest consensus probability and book count on each anytime-TD slate line,
  shown in the row's expandable evidence panel.

## Out of scope

- Any market other than `player_anytime_td` (`player_rush_yds` is next only if TDs prove useful).
- Changing the slate `edge`, sort order, or the anytime-TD projection. The book
  probability is displayed beside the model, not blended into it.
- Settling or grading TD bets, or tracking closing-line value.
- A player-alias admin flow. Unresolved book names are stored with a NULL
  `player_id` and counted in the log, the same way PrizePicks lines are handled.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - storage.** Migration `0023_nfl_player_prop_odds` creating
  `nfl_player_prop_odds` (shape under Data / contracts), plus
  `insert_player_prop_odds_snapshot` in `app/repositories/nfl.py`. Player
  candidates reuse the existing `get_player_candidates`.
  *Done when:* `alembic upgrade head` reaches `0023`, `alembic downgrade -1`
  then `upgrade head` round-trips cleanly, and the full `pytest` suite passes.

- [x] **Step 2 - parse and price.** New pure module `app/core/nfl_prop_odds.py`:
  - parse one event-odds payload into per-book rows (book, provider player name,
    Yes price, No price or None), ignoring outcomes with a missing or non-integer price;
  - per-book probability: two-way de-vig through `core/odds.devig_two_way` when a
    No price exists, otherwise the raw Yes implied probability with
    `includes_margin=True`;
  - consensus per player: median of per-book probabilities, book count, and
    `includes_margin` if any contributing book was Yes-only.
  Tests in `api/tests/test_nfl_prop_odds.py` use a fixture built from the
  2026-09-18 capture shape (`name: "Yes"`, `description: <player>`, American `price`).
  *Done when:* tests cover Yes-only, Yes/No, a malformed outcome, a single book,
  and an even book count median, and `pytest` passes.

- [x] **Step 3 - bounded ingest.** New `app/ingest/nfl_prop_odds.py`:
  - `GET /events` (0 credits), keep events that match a scheduled game through
    `match_scheduled_game`, have not started, and start within `--hours-ahead`
    (default 96);
  - before each paid request, stop if the last seen `x-requests-remaining` minus
    the market count would fall below `--min-credits` (default 50); also cap with
    `--max-events` (default 16);
  - `GET /events/{id}/odds` with markets from `PROP_MARKETS` (default
    `{"player_anytime_td": NflPropMarket.ANYTIME_TOUCHDOWN}`), and resolve players
    with `resolve_player`. The book gives no team per player, so resolve with no
    team first; on `AMBIGUOUS`, retry with each of the matched game's two team
    codes and accept only if exactly one team resolves. Insert snapshots;
  - `--dry-run` still spends credits, so it prints the planned event count and
    estimated cost and exits before any paid request unless `--confirm-spend` is passed;
  - log credits used, credits remaining, events fetched, rows stored, and
    resolution outcomes.
  Unit tests cover the event filter and the credit-floor stop, with HTTP mocked.
  *Done when:* tests pass; `python -m app.ingest.nfl_prop_odds --dry-run` prints
  the event count and cost without spending credits; one real run with
  `--max-events 1` stores rows for one game, costs 1 credit, and logs the
  remaining balance.

- [x] **Step 4 - schedule.** Add a `nfl-prop-odds.yml` workflow (or a job in
  `nfl-ingest.yml`) with two crons: Thursday 22:00 UTC with `--hours-ahead 6`
  (Thursday game only) and Sunday 14:00 UTC with `--hours-ahead 36` (Sunday and
  Monday games). Same secrets, `contents: read`, September through February only.
  Known gap: an international Sunday game (09:30 ET kickoff) starts before the
  Sunday run and is skipped as already started; accepted, not worth a third run.
  *Done when:* the workflow file passes a YAML parse, runs the same command as a
  local run, and the weekly cost estimate is written in a comment (about 16 to 17
  credits a week, about 70 a month).

- [x] **Step 5 - slate API.** `get_slate_prop_odds(db, season, week)` returns the
  latest snapshot per (game, player, book) for the week's games (no kickoff
  window: prices are per game, so they cannot leak across weeks, and the UI shows
  their age instead), and the
  router attaches the Step 2 consensus to anytime-TD full-game lines as
  `book_probability`, `book_count`, `book_includes_margin`, and
  `book_fetched_at` (all nullable). Test the attach logic as a pure function.
  *Done when:* `GET /nfl/slate?season=2026&week=<current>` shows non-null
  `bookProbability` on anytime-TD lines for the game stored in Step 3, null on
  every other market, and `pytest` passes.

- [x] **Step 6 - slate UI.** Add the four fields to the web type, and show a
  "Sportsbooks" row in the anytime-TD evidence panel: consensus percentage, book
  count, age, a "includes book margin" note when flagged, and model minus books
  in percentage points. A formatter in `web/src/utils/` gets a Vitest test.
  *Done when:* `npm run build` and `npm run test` pass, and a screenshot of an
  expanded anytime-TD row shows the Sportsbooks row next to the model baseline.

## Files / areas

- `api/app/db/migrations/versions/0023_nfl_player_prop_odds.py` (new)
- `api/app/repositories/nfl.py`
- `api/app/core/nfl_prop_odds.py` (new), `api/tests/test_nfl_prop_odds.py` (new)
- `api/app/ingest/nfl_prop_odds.py` (new), `api/tests/test_nfl_prop_odds_ingest.py` (new)
- `.github/workflows/nfl-prop-odds.yml` (new) or `nfl-ingest.yml`
- `api/app/schemas/nfl.py`, `api/app/routers/nfl.py`
- `web/src/types/`, `web/src/pages/NflIntelligencePage.tsx`, `web/src/utils/nflLabels.ts` (or a new util) plus its test

## Data / contracts

**`nfl_player_prop_odds`** (load-bearing: `player_rush_yds` and later markets reuse it)

| Column | Type | Notes |
|---|---|---|
| `id` | BigInteger PK | |
| `game_id` | FK `nfl_games.id`, cascade, not null | |
| `player_id` | FK `nfl_players.id`, set null, nullable | NULL when the book name does not resolve |
| `provider_player_name` | text, not null | the outcome `description` |
| `provider_event_id` | text, not null | The Odds API event id |
| `market` | text, not null | an `NflPropMarket` value; check constraint allows `anytime_touchdown` only for now |
| `book` | text, not null | bookmaker key, e.g. `draftkings` |
| `line` | numeric(7,2), nullable | NULL for yes/no markets |
| `yes_odds` | int, not null | American; for over/under markets this is the Over price |
| `no_odds` | int, nullable | NULL when the book posts only Yes |
| `market_prob` | float, not null | per-book probability from Step 2 |
| `includes_margin` | boolean, not null | true when `no_odds` is NULL |
| `fetched_at` | timestamptz, default now | |
| `raw_json` | JSONB | the book's raw market object |

Index on (`game_id`, `market`, `player_id`, `fetched_at`).

**Slate line additions** (camelCase over the API): `bookProbability: number | null`,
`bookCount: number | null`, `bookIncludesMargin: boolean | null`,
`bookFetchedAt: string | null`. Null means "no sportsbook price", never zero.

**Config:** `PROP_MARKETS: dict[str, NflPropMarket]` in the ingest module maps
provider market keys to app markets. It is the one place a new market is enabled.

## Testing

Test gate is on (`pytest`, `npm run test`).

- **Needs tests:** the payload parser, the per-book and consensus probability rule,
  the event filter, the credit-floor stop, the slate attach function, the web formatter.
- **Rides on evidence:** the migration (upgrade/downgrade round trip), the real
  1-credit ingest run, the workflow file, and the UI (screenshot plus build).
- No test may hit the network. Real credits are spent only in Step 3's single
  `--max-events 1 --confirm-spend` run.

## Notes for the AI

- **Credit safety comes first.** Never loop over events without checking the
  floor first. The `/events` listing is free, and `/events/{id}/odds` costs
  (markets × regions). Read `x-requests-remaining` and `x-requests-last` from every
  response. Never retry a paid request automatically; log and move on.
- **Two providers.** This uses The Odds API (`api.the-odds-api.com`,
  `settings.the_odds_api_key`), the same as `ingest/nfl_odds.py`. Do not touch
  the tennis Odds-API.io client.
- **Yes-only prices.** In the 2026-09-18 test, DraftKings posted only "Yes"
  outcomes. Summing Yes probabilities across players does not give a margin,
  because several players can score. So a Yes-only book stays flagged
  `includes_margin`, and the UI says so. See the review question below.
- `core/nfl_prop_odds.py` stays pure: no DB, no HTTP. SQL lives in `repositories/nfl.py`.
- Reuse `match_scheduled_game`, `resolve_player`, `devig_two_way`, and
  `american_to_prob`; do not write parallel versions.
- Migrations are numbered sequentially; the current head is `0022`, not the
  `0019` the overview's data model section still states.
- No em dashes in new comments, docs, or commit messages.

## Decision: Yes-only books

**Decided 2026-09-18: option 1.** A Yes-only book contributes its raw implied
probability and the consensus is flagged `includes_margin`; the UI says so.

Options considered:

1. **Show it with a "includes book margin" flag (spec default).** Honest, no
   invented number, but it overstates the TD chance by the book's margin.
2. **Remove an assumed margin** (for example divide by 1.05). Closer to a fair
   price, but the constant is a guess until Yes/No data shows the real margin.
3. **Use only books that post both sides.** Most accurate, but may leave few or
   no books if most are Yes-only.

## Deviations from the spec

- `--confirm-spend` is required for every paid request, not only with
  `--dry-run`. `--dry-run` now means "fetch if confirmed, but write nothing".
  The scheduled workflow passes `--confirm-spend`.
- Step 5 dropped the 36-hour kickoff window. The Step 3 test fetch was about 44
  hours before kickoff and would have been hidden; prices are keyed by game, so
  they cannot leak across weeks, and the UI shows their age.

## Verification evidence

- `pytest`: 795 passed. `npm run build` passed (includes `tsc -b`).
  `npm run test`: 73 passed.
- `alembic upgrade head` to `0023`, `downgrade -1`, `upgrade head` round-trip clean.
- `python -m app.ingest.nfl_prop_odds --dry-run` (no `--confirm-spend`): 15
  events, estimated 15 credits, balance unchanged at 490.
- `--max-events 1 --confirm-spend`: CAR @ ATL, 1 credit (490 to 489), 148
  prices from 6 books (draftkings, fanduel, betmgm, betrivers, betonlineag,
  bovada), 140 resolved; the 8 unresolved were team defenses. Every book was
  Yes-only.
- `GET /nfl/slate?season=2026&week=2`: 26 lines carry `bookProbability`, all
  full-game `anytime_touchdown`; none on other markets.
- Playwright screenshot of the expanded Chuba Hubbard anytime-TD row showed
  "54.0% · 6 books · 10m ago" and "Model -32.0 pts vs books · includes book margin".

## Follow-ups

- The model's anytime-TD baselines disagree with books by 18 to 32 points for
  several players (Hubbard 22% vs 54%, Brooks 6% vs 24%, Waller 49% vs 19%).
  Worth a `/fix` or `/debug` on the TD baseline.
- The "Last 5 games" evidence row for anytime TD shows per-game values such as
  "86.0% vs CHI"; pre-existing and out of scope here.
- Add `player_rush_yds` to `PROP_MARKETS` only after a few weeks of TD results.
- `project-overview.md` data model still says revision `0019` and omits the
  0020 to 0023 tables; refresh on the next full `/overview`.

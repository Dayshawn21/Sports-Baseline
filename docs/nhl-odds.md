# NHL game odds

Feature 45d stores pre-game DraftKings and Bet365 prices from Odds-API.io in
the existing `sport_game_odds` table. NHL market display and line movement
are 45e; projections and betting recommendations are separate future work.

## Run locally

From `api/`, with its Python environment active:

```powershell
python -m app.ingest.nhl_odds_io --dry-run
python -m app.ingest.nhl_odds_io
```

The default window is the next two days. `--days-ahead` accepts integers 1-14;
`--min-requests-remaining` accepts 0-99 and defaults to 20. The command reads
`DATABASE_URL` and `ODDS_API_KEY` through Settings. It uses existing schema
including migrations 0044 (provider) and 0049 (NHL); no new migration is needed.

Dry run still makes provider requests and uses the shared hourly quota. It
does not insert or commit. With no eligible stored games, either mode skips
all provider calls and needs no odds key. Real runs append snapshots, including
unchanged prices, so repeated successful runs create observation history.

## Stored market contract

Every reader must filter `sport='nhl'` and `provider='odds_api_io'`. The provider
is distinct from The Odds API, which supplies other sports on a monthly budget.
`book` is exactly `bet365` or `draftkings`. Fair probabilities remove each
book's own two-way margin; they are not a multi-book consensus or model edge.

| Provider market | Stored market | Sides and line |
|---|---|---|
| `ML` | `moneyline` | home/away, NULL line; full game with OT and shootout included |
| `Spread` | `spread` | home/away; stored home team's signed +/-1.5 puck line |
| `Totals` | `total` | over/under; positive full-game goal line |

Only exact full-game names are accepted. Draw No Bet, draw-bearing and explicit
regulation/period markets, props and team totals are skipped. A missing complete
+/-1.5 puck-line rung is skipped rather than replaced by another handicap.
Totals select a complete rung by lowest overround, then closest prices, then
stable provider order. Opposite sides always come from the same rung. American
prices and proportional de-vig probabilities are stored together.

The NHL schedule's official final scores include the shootout winner's goal.
The moneyline, puck line and total contract is full game; a later grading
feature must preserve that meaning. This ingest does not settle or score bets.

Event matching requires both normalized full team names, exactly one stored
NHL game and aware starts within six hours. Both starts must remain in the
future. Stored games must be scheduled REG/PST; missing starts and preseason
are excluded. Reversed home/away prices and the puck-line sign are restated
for the stored home team. Conflicting duplicate events or markets are skipped.

`raw_json` retains the selected provider-oriented rung, exact market name,
full-game marker, provider update time when supplied and provider event id.
`fetched_at` records database statement time, separately from the provider's
update time. Inserts recheck the target sport, game type, status and start.

## Shared quota and failure behavior

The existing account contract is 100 Odds-API.io requests/hour and two books
shared with tennis and NFL. A run makes one ice-hockey event-discovery request,
then one odds request per ten matched NHL games. A 16-game window costs three
requests, about 24 daily at eight runs. NHL spends no The Odds API credits.

Discovery is the bounded first request that obtains the remaining balance.
Every later request must leave at least the configured floor. Unknown or
invalid balances stop additional requests. The floor and staggered times reduce
contention, but independent sports jobs can overlap and do not reserve quota.

HTTP errors (including 429), timeouts, malformed JSON and invalid top-level
responses stop further requests without retry. Already accepted complete
snapshots can commit before a later provider failure; the command still exits
1. A quota-floor stop exits 75. Invalid CLI configuration exits 2. Missing
events/books/markets are coverage gaps, not fabricated odds or a failed run.
Database failure exits 1 and the transaction rolls back.

Summaries distinguish requests, matches, candidates, writes, remaining balance,
missing events/books/markets, and rejected records. A balance of -1 means
unknown. No credential-bearing URL or HTTP exception text is logged. A dry
run's candidate count is not a stored-row count.

## Scheduled operation and freshness

`.github/workflows/nhl-odds.yml` runs at minute 40 every three UTC hours,
September-June (`40 */3 * 1-6,9-12 *`), with manual dispatch. Runs at 00:40,
03:40, 06:40, 09:40, 12:40, 15:40, 18:40 and 21:40 UTC translate to:

- Central daylight time: 7:40 PM, 10:40 PM, 1:40 AM, 4:40 AM, 7:40 AM,
  10:40 AM, 1:40 PM and 4:40 PM CT.
- Central standard time: 6:40 PM, 9:40 PM, 12:40 AM, 3:40 AM, 6:40 AM,
  9:40 AM, 12:40 PM and 3:40 PM CT.

The workflow uses Python 3.11, `contents: read`, only the database and odds
secrets, a ten-minute timeout and its own non-canceling concurrency group.
Render runs no ingest cron. Tennis and NFL workflow schedules are unchanged.

These are periodic snapshots, not a live or guaranteed closing price. GitHub
can delay schedules, the provider can omit a game/book/market, and quota or
failures can leave older history. 45e should show observation times and missing
coverage. This feature adds no request-time report or served cache.

Workflow registration, first runner acceptance and hosted deployment remain
pending an approved push and actual execution. No dispatch or deployment has
been performed under this feature.

## Local verification

On 2026-10-23 the final Step 3 dry run matched 15 games and parsed 84 market
candidates in three requests: 14 moneylines, 14 puck lines and 14 totals for
each book. One requested event was missing from the odds response. An enforced
read-only database transaction proved the dry run could not write.

Step 4's two real runs each appended 84 snapshots, taking the NHL/provider
count from 0 to 84 to 168. Read-back checked all 168 rows for NHL identity,
book, market, sides, puck-line sign/range, event provenance, paired fair
probabilities and capture before puck drop. All 84 market keys appeared again
in the second run. A hash of every first-run row stayed unchanged, including
payloads and timestamps. A following dry run parsed 84 candidates and left
the count and hash of all 168 rows unchanged. Each run used three hourly
requests; the final observed balance was 78. One requested event remained
absent, so coverage was 14 of 15 matched games, with all three markets at
both books for those 14. No validation sample, holdout or outcome scoring
was part of these storage checks.

Focused tests, from `api/`:

```powershell
python -m pytest tests/test_nhl_odds.py tests/test_nhl_odds_repository.py tests/test_nhl_odds_io_ingest.py
```

The final automated gate is the root Verify command documented in `AGENTS.md`.

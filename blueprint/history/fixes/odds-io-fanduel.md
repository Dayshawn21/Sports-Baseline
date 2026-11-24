# Fix: Replace Bet365 with FanDuel on Odds-API.io

**Type:** Fix
**Status:** complete (2026-10-27)
**Branch:** `fix/odds-io-fanduel`

## The problem

Odds-API.io moved Bet365 to paid plans on 2026-10-26 at 19:00 UTC. Free keys
now get a 403 on Bet365 requests. Every Odds-API.io request the app makes asks
for both books in one call, so a 403 can also cost the DraftKings prices in
that call:

| Caller | Where | What a 403 does today |
|---|---|---|
| Tennis odds ingest (`tennis-odds.yml`) | `DEFAULT_BOOKMAKERS` in `app/ingest/odds_api.py`, `live_odds_bookmakers` in `app/config.py` | Logs "blocked by plan" and returns; the workflow passes with nothing stored |
| Tennis best-picks live moneyline | Hardcoded `"DraftKings,Bet365"` in `app/routers/tennis.py` (cache key and fetch) | Live lookup fails |
| NFL best line (`nfl-odds-io.yml`) | `BOOKMAKERS` in `app/ingest/nfl_odds_io.py` | Each batch logs `failed` and is skipped |
| NHL odds (`nhl-odds.yml`) | `BOOKMAKERS` in `app/ingest/nhl_odds_io.py` | Run exits 1; NHL has no other odds source |

The free plan still allows two recreational books. The owner chose
**DraftKings + FanDuel**, and switches the key's second book from Bet365 to
FanDuel in the Odds-API.io dashboard before Step 1.

## The fix

- Request `DraftKings,FanDuel` everywhere Odds-API.io is called, from one
  setting for tennis (the router reads it instead of a literal).
- Store FanDuel under the lowercase book key `fanduel` with
  `provider='odds_api_io'`, as Bet365 was.
- **Stored Bet365 rows stay readable.** No row is deleted or renamed. Readers
  that list allowed books add `fanduel` and keep `bet365` (and its
  `betonline.ag` aliases) so history, closing lines and movement still show.
- **A plan block is a failure.** The tennis ingest exits nonzero when every
  odds batch is refused with 402/403, so a scheduled run shows red.

**Must not break:**
- Provider separation (36a): every `sport_game_odds` reader still names its
  provider. FanDuel rows from The Odds API (`the_odds_api_us`) and from
  Odds-API.io (`odds_api_io`) stay distinct by provider. Item 28's CLV entry
  line reads `the_odds_api_us` only and is untouched.
- NFL best line's rule (one quote per book, newest across providers) is
  unchanged. A FanDuel quote from either provider is one book.
- Tennis book tie order for existing rows: DraftKings, then Bet365 (and its
  old names), then Betfair. FanDuel is added after Bet365, so no historical
  tie flips.
- NHL's display rule stays "DraftKings preferred, else the other book".
- The shared hourly quota: same number of requests per run.

## Build steps

- [x] **Step 1 - Probe FanDuel (no code change)** - after the owner switches
  the dashboard, run
  `python -m app.ingest.odds_probe --books "DraftKings,FanDuel"` from `api/`
  (a few hourly requests). Record in this spec the exact bookmaker key
  Odds-API.io returns for FanDuel, its tennis market names (moneyline, totals,
  spread) and whether it covers Challenger. *Done when:* the probe shows
  FanDuel odds on a tennis event, or shows it has none, and the findings are
  written below under Probe results. If FanDuel is missing or still 403s, stop
  and report before Step 2.
- [x] **Step 2 - Tennis** - `live_odds_bookmakers` and `DEFAULT_BOOKMAKERS`
  become `DraftKings,FanDuel`. `tennis.py` uses the setting for its cache key
  and fetch. A `fanduel` `BookConfig` reuses the existing parsers where the
  probe shows the same market names (a FanDuel parser only if they differ).
  `fanduel` joins the book tie order after `bet365` in
  `app/repositories/matches.py` and `web/src/utils/matchOdds.ts` (with a
  FanDuel label). The ingest raises `SystemExit(1)` when the plan blocks every
  batch. `odds_probe`'s default books follow. *Done when:* tests cover the
  FanDuel parse from a probe-shaped fixture, the tie order, and the nonzero
  exit on an all-403 run; `python -m app.ingest.odds_api --hours-ahead 4`
  stores DraftKings and FanDuel rows (owner approves the real write first).
- [x] **Step 3 - NFL and NHL** - both `BOOKMAKERS` swap Bet365 for FanDuel.
  NHL: the insert check accepts `fanduel` (and still `bet365`), the reader's
  `IN` list adds `fanduel`, the schema `Literal` and web `NhlBook` gain
  `fanduel`, and `nhlBookLabel` names all three books. NFL needs no reader
  change (`fanduel` is already labelled). **Main-rung rule (added
  2026-10-27, owner-approved):** FanDuel sends spread and total ladders whose
  extreme rungs carry almost no margin, so least-vig picked NHL totals of
  11.5 and NFL totals of 20.5 at -50000. In `app/core/nfl_odds_io.py` and
  `app/core/nhl_odds.py`, rungs where either side's implied probability is
  above 0.75 are dropped first (all rungs kept when none remain), then
  today's least-vig, closest-to-even choice applies. On the captured
  2026-10-27 responses this matched DraftKings' total in 6 of 6 games and
  left spreads unchanged. *Done when:* tests cover NHL FanDuel insert/read
  and labels, the main-rung rule on FanDuel ladders trimmed from the real
  2026-10-27 responses (Bet365 fixture tests still pass), and the ingest
  tests request `DraftKings,FanDuel`; `nfl_odds_io --dry-run` and `nhl_odds_io --dry-run` report FanDuel
  markets matched (owner approves the requests).
- [x] **Step 4 - Docs and checks** - workflow names and comments in
  `nfl-odds-io.yml` and `nhl-odds.yml`; `AGENTS.md` NHL odds line;
  `docs/nhl-odds.md`, `docs/nhl-display.md`; CLI descriptions and docstrings.
  Note in this spec that the generated overview still says Bet365 until the
  next `/overview`. Update the local interview guide if present (provider
  change). *Done when:* `grep -ri bet365` in `app/`, workflows and docs shows
  only stored-history readers, the tennis Bet365 props page, and dated
  history; Verify passes.

## Notes

- **Overview:** `blueprint/context/project-overview.md` is generated and still
  names Bet365 as the second Odds-API.io book (tennis, 36a, 45d) until the
  next `/overview`.
- **Left as history:** `docs/nfl-odds-market-inventory.md` and
  `docs/odds-market-inventory.md` are dated captures; the
  `_parse_bet365_spread` parser and the Bet365 config read stored rows only
  through their aliases and are not requested.
- **Follow-up, not in this fix:** the tennis ingest checks its quota floor
  only after an odds batch, so a run that starts with 0 requests left still
  sends its batches (seen on the 2026-10-27 429 run).

## Out of scope

- The tennis "Bet365" props source (`/tennis/props/bet`, `props.py`, and the
  `bet` tab on the tennis pages). It reads stored rows and will empty as they
  age; removing or replacing it is a separate change.
- Deleting or migrating stored Bet365 rows.
- Any model, probability, pick, ranking or color change.
- Paid plans or adding a third book.

## Verify

- Verify command passes.
- After merge and push, the next `tennis-odds.yml`, `nfl-odds-io.yml` and
  `nhl-odds.yml` runs succeed and store `draftkings` and `fanduel` rows
  (checked the next day; push needs a separate yes).
- The NHL slate, NFL game page best-line card and a tennis match page show
  FanDuel where DraftKings is missing, and older Bet365 history still renders.

## Probe results

Run 2026-10-27, after the owner switched the key's second book to FanDuel:

- **Name:** Odds-API.io lists `FanDuel` among 447 valid tennis bookmakers and
  returns it keyed `FanDuel` in `bookmakers`, the same casing pattern as
  `DraftKings`. Stored key: `fanduel`.
- **No 403:** `/odds/multi` with `DraftKings,FanDuel`, `FanDuel` alone and
  `DraftKings` alone all returned 200.
- **Coverage:** on five ATP Paris events (2026-10-27, 14:30-16:30 UTC,
  doubles included) both books returned the same single market, `ML`. Neither
  book sent `Totals` or `Spread` on those events at that time, so total-games
  and game-spread coverage for FanDuel is unconfirmed.
- **Same market name as DraftKings:** FanDuel's moneyline is `ML`, which the
  DraftKings parser (`_parse_draftkings`) already reads.
- **Not checked by the probe:** Challenger and WTA 125 coverage, and
  FanDuel's totals shape.
- **Step 2 ingest (2026-10-27, 15:25 UTC, `--hours-ahead 4`):** 31 of 32
  upcoming matches matched, 29 returned odds, 55 `match_odds` rows stored.
  Moneyline only from both books: DraftKings 5 ATP and 23 Challenger matches,
  FanDuel 5 ATP and 22 Challenger (2 Challenger matches had DraftKings only).
  No totals or spreads from either book in that window. 5 Odds-API.io
  requests used.
- **Step 3 dry runs (2026-10-27, no writes):** NFL matched 14 games and
  parsed 84 markets, all three markets from both books for every game. NHL
  matched 15 games: DraftKings all three markets in 15, FanDuel in 11 (4
  games had no FanDuel book yet). 3 requests each.
- **Quota cost:** `odds_probe` tries up to 30 events per run, and it ran
  twice before the raw check, which left 1 request in that hour. Later
  checks use one batched request, never the probe.

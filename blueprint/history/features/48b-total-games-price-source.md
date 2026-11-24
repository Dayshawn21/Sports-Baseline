# Feature: 48b. Total-games price source

**From build-plan:** feature 48b (parent 48, Tennis prop rebuild)
**Status:** complete 2026-10-28 (Path B1: The Odds API tennis totals)
**Branch:** `feature/48b-total-games-price-source`

## Goal

Give totals-based tennis props a book total-games line again after Bet365's
exit (paid-only on Odds-API.io since 2026-10-26), within the provider quotas,
or prove there is no free source and record that so 48c anchors on the
moneyline alone. Today 289 of 355 eligible prop lines carry
`no_market_total` and can never be a pick (48a local check).

## What is already known (read-only, 2026-10-28)

- **DraftKings has never stored a tennis total.** `match_odds` over the last
  120 days: `draftkings` stored `moneyline` only, 300 to 450 matches a week,
  every week. Every `total_games` row came from Bet365 (`betonline.ag` before
  2026-09-25). FanDuel, requested since 2026-10-26, stored 260 `moneyline`
  rows and no total.
- **The parser is not the obvious cause.** `_parse_draftkings` accepts market
  names `total games`, `totals games`, `totals`, `total` (after punctuation is
  stripped) and stores the closest-to-even two-sided rung. FanDuel uses the
  same parser and its config already lists `total_games`.
- **No raw DraftKings tennis market list has ever been captured with data.**
  `docs/odds-market-inventory.md` (2026-09-16) returned no markets. The
  2026-10-27 probe (fix `odds-io-fanduel`) saw only `ML` from both books, on
  five ATP Paris events (doubles included), 14:30 to 16:30 UTC; Challenger,
  WTA, and the hours just before start were not checked. A book may post
  totals late, and the scheduled job runs every 4 hours over 14 hours ahead.
- **Constraints.** Odds-API.io: 100 requests an hour, two books per key,
  shared with NFL and NHL (both use DraftKings and FanDuel); sharp books and
  exchanges are paid. The Odds API: 500 credits a month, about 397 already
  committed in season (NFL, Pinnacle, NBA), one credit per market per region
  per odds request, event and sport listings free; it has never been used
  for tennis.

## In scope

- A raw, owner-approved capture of what DraftKings and FanDuel send for
  tennis on Odds-API.io, across tours and close to start time.
- If either book sends a match total under a name or shape the ingest
  rejects: a parser fix with a fixture test, so the scheduled job stores it.
- If neither does: a decision gate with the owner on the next source,
  using measured costs, then a spec amendment before any code.
- Docs saying where tennis totals come from (or that none exist).

## Out of scope

- Any projection, tier, flag or pick logic change; `props-v3` stays as is.
  Rows that arrive simply reach the existing reader
  (`_fetch_market_totals` in `app/routers/props.py`).
- Game spreads and set handicaps (16f stays parked).
- Paid plans of either provider.
- Changing the key's two Odds-API.io books without an owner decision at the
  gate (it would change NFL and NHL too).
- Sportsbook player props (48d) and the match simulation (48c).

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Raw market capture (no app code, owner approves the
  requests)** - a scratchpad script (not committed) reuses
  `app.ingest.odds_api` helpers: one `/events` call, then one `/odds/multi`
  call for up to 10 tour-singles events (`odds_event_tour` not None) that
  start within the next 3 hours, mixing ATP or WTA main tour with
  Challenger where available, books `DraftKings,FanDuel`. Run at a busy
  hour; if the first capture has no main-tour events in range, a second
  capture later the same day needs a second OK. It records, per event and
  book: tour, minutes to start, every raw market name, and for any market
  containing `total` or `games`, one raw entry's keys. It logs the hourly
  quota left after each call and refuses to send the odds call when
  remaining is at or below 20. *Cost:* 2 Odds-API.io requests per capture,
  no The Odds API credits. *Done when:* the findings are written under
  **Probe results** below, saying for each book and tour whether a match
  total arrives, under what name and shape, and how far before start.
- [x] **Step 2 - Gate: pick the path (no code)** - read Step 1 against the
  parser.
  - **Path A** - a book sends a match total the ingest drops (unknown name,
    odd shape, one-sided rungs): go to Step 3.
  - **Path B** - neither book sends any match total: stop and give the owner
    the options, each with its measured or quoted cost, then amend Steps 3
    and 4 to the choice before any code:
    1. **The Odds API tennis totals.** First a free `/sports` listing to see
       which tennis keys are active (it lists tournaments, not Challengers);
       with an OK, one `totals` request on `us` and `eu` for one active key
       (2 credits) to see which books price tennis totals. A running cost is
       about 1 credit per active key per region per run, from the roughly
       100 credits a month left.
    2. **Swap the key's second book** to one that sends tennis totals on the
       free plan, if one is found. NFL and NHL lose FanDuel.
    3. **Accept no book total.** Record it; 48c anchors on the de-vigged
       moneyline and a model total, and the `no_market_total` cap stays.
  *Done when:* the path (and, for Path B, the owner's choice) is written
  under **Decision** below, with Steps 3 and 4 amended if needed.
*Path A (a parser fix in `odds_api.py`) was dropped at the Step 2 gate:
no free Odds-API.io book sends a tennis total. Steps 3-6 below are the B1
amendment, pending owner approval.*

- [x] **Step 3 - Parse and pick a total (pure)** - new
  `app/core/tennis_totals.py`: from one The Odds API event, the main
  `totals` line per book (two-sided, closest to even, as
  `_main_total_line` does), decimal prices to American; then one book per
  match by a fixed preference, `pinnacle` first, then `marathonbet`,
  `betsson`, `nordicbet`, `onexbet`, `coolbet` (the `eu` books that priced
  all or most of the Basel probe). Matching to a stored match reuses
  `match_event` from `app/core/tennis_odds_events.py` (it already reads
  "Hubert Hurkacz"-style names). *Done when:* `api/tests/test_tennis_totals.py`
  passes on a fixture trimmed from the 2026-10-28 Basel response: Pinnacle
  chosen where present (Michelsen v Fils 22.5, -111 / -103), the fallback
  book where Pinnacle is absent (Fritz v Shapovalov), a split-line book
  ladder resolved to the main line, an event with no totals giving nothing,
  and a name that fits both orientations refused.
- [x] **Step 4 - Ingest with a credit floor** - new
  `app/ingest/tennis_totals.py`, runnable as
  `python -m app.ingest.tennis_totals [--hours-ahead 24] [--min-credits 150] [--dry-run]`.
  A free `/sports` call lists active `tennis_*` keys; a free `/events` call
  per key keeps only keys with an event that matches a stored upcoming
  match within the window; then one paid `/odds` call per kept key with
  `regions=eu&markets=totals` (1 credit each), checking
  `x-requests-remaining` before every paid call and stopping at the floor.
  Writes go through `upsert_odds` as `market = 'total_games'`, the chosen
  book's key, `line`, `p1_odds` = over, `p2_odds` = under. `--dry-run`
  parses and reports without writes (it still spends the credits). The
  floor (150) sits above NBA's (100), so tennis is the first to stop when
  the month runs low. *Done when:* tests with a fake client show keys
  without matched events are never sent a paid call, the floor stops
  before a paid call, and the stored rows have the contract shape; then,
  with an owner OK (one credit per kept key), a `--dry-run` reports matched
  events and parsed totals, and a real run (another OK) stores at least one
  `total_games` row, checked by a read-only query.
- [x] **Step 5 - Schedule** - new `.github/workflows/tennis-totals.yml`,
  daily at 12:45 UTC (before the 13:00 PrizePicks lines and 13:30
  predictions and snapshots) plus manual dispatch, `contents: read`,
  `THE_ODDS_API_KEY` and `DATABASE_URL` secrets as `nba-odds.yml` uses.
  *Done when:* the workflow file mirrors an existing one's setup and the
  command line matches Step 4; it registers only after the owner pushes.
- [x] **Step 6 - Docs and checks** - `docs/commands.md` (odds line and a
  tennis totals line with cost and floor), `docs/tennis-actions.md` (a
  seventh workflow, and that totals cover ATP and WTA tour-level events
  only), the `AGENTS.md` ingest list, the `odds_api.py` docstring and
  `BOOK_CONFIGS` FanDuel comment (no tennis totals from either free book),
  and the local interview guide (provider change, recorded finding).
  `project-overview.md` updates at the next `/overview`. *Done when:* no
  doc says tennis totals are unavailable without the tour-level caveat,
  the `invariants-reviewer` agent has run on the branch, and Verify passes.

## Files / areas

- New: `api/app/core/tennis_totals.py`, `api/app/ingest/tennis_totals.py`,
  `api/tests/test_tennis_totals.py`, `.github/workflows/tennis-totals.yml`.
- Docs: `docs/commands.md`, `docs/tennis-actions.md`, `AGENTS.md`.
- Comments only: `api/app/ingest/odds_api.py`.
- Probe scripts stay in the scratchpad; nothing diagnostic lands in `api/`.

## Data / contracts

- No schema change. Tennis totals stay in `match_odds` as
  `market = 'total_games'`, `line` = main line, `p1_odds` = over,
  `p2_odds` = under (American), book lowercase. This is the shape
  `_fetch_market_totals` reads and 48c will anchor on: **load-bearing**.
- `match_odds` has no `provider` column. The reader picks the newest row
  across all books (ties DraftKings, Bet365, FanDuel, other). B1 rows use
  The Odds API's lowercase book key, one row per match per run, no
  provider marker (no stored key collides; see **Decision**).

## Testing

- Test gate is on. Path A adds parsing logic, so it ships fixture tests
  (`pytest`) from a trimmed real response, never a hand-invented shape.
- Steps 1 and 2 add no code; evidence is the probe output recorded here.
- Final gate: `npm --prefix web run verify && cd api && python -m pytest`
  (venv active).

## Notes for the AI

- **No paid quota without an OK in chat**, per capture or run: Odds-API.io
  (dry runs and inventory spend requests) and The Odds API (any odds call).
  Check `x-ratelimit-remaining` from the events call before the odds call;
  NFL and NHL jobs share the hour.
- Read-only queries against the shared Neon DB are fine; no writes outside
  an approved ingest run, no migrations.
- One-off diagnostic scripts stay in the scratchpad (`coding-standards.md`).
- Never push, merge or change the Odds-API.io dashboard books; the owner does
  that.
- Run the `invariants-reviewer` agent before `/complete` (odds-provider
  filters).

## Probe results

**Capture 1** (2026-10-28 21:19 UTC, owner-approved, 2 Odds-API.io requests,
94 then 93 of 100 left in the hour):

- 803 tennis events listed; 4 tour-singles events started within 3 hours
  (no ATP main tour in range): WTA 125 Queretaro x2 (100 and 170 min out),
  Challenger Sioux Falls x2 (35 and 105 min out).
- **DraftKings and FanDuel each sent one market, `ML`, on all four.** No
  total, spread, set or games market of any name. Event keys: `id`, `home`,
  `away`, `date`, `league`, `status`, `bookmakers`, `bookmakerIds`, `urls`;
  `bookmakers` is `{"DraftKings": [{"name": "ML", "updatedAt", "odds":
  [{"home", "away"}]}], "FanDuel": [...]}`.

**Stored history** (read-only, last 120 days): DraftKings priced 1,238
matches within 3 hours of start (ATP 305, Challenger 660, WTA 273) and never
stored a total. With capture 1 and the 2026-10-27 ATP Paris probe, timing,
tour and parser are ruled out: **neither free book sends tennis totals
through Odds-API.io.** No second capture is needed.

**The Odds API** (free `/sports` listing, 0 credits; 265 of 500 used this
month, 235 left): three active tennis keys, `tennis_atp_swiss_indoors`,
`tennis_atp_vienna_open`, `tennis_wta_pan_pacific_open`. Tour-level events
only; no Challenger or WTA 125 keys. Free `/events` listings: 7, 6 and 6
events.

**The Odds API totals probe** (2026-10-28, owner-approved, 2 credits, 233
left): `tennis_atp_swiss_indoors`, `regions=us,eu`, `markets=totals`.
**All 7 events had totals**, from 6 to 15 books each. `pinnacle` (eu)
priced 5 of 7, missing the live match and Fritz v Shapovalov;
`marathonbet`, `betsson` and `nordicbet` priced all 7. Books mostly agree
on the line (22.5 on four matches); `bovada`, `betus` and `pinnacle` sometimes
quote a whole-number line (22.0, 23.0, 25.0). Shape per book:
`markets: [{"key": "totals", "outcomes": [{"name": "Over", "point",
"price"}, {"name": "Under", ...}]}]`, one rung per book. One region is
enough: `eu` alone carries Pinnacle and every fallback book.

**Coverage that matters** (prop snapshots, last 28 days): ATP 4,631 lines
(223 matches), WTA 4,550 (246, WTA 125 included), Challenger 1,418 (180).

**Step 4 dry run** (2026-10-28 ~22:00 UTC, owner-approved, 3 credits, 230
left): 49 stored upcoming matches, 3 active keys (Basel, Vienna, Tokyo), all
3 paid, 12 totals parsed, 7 events unmatched, 0 unpriced, no floor stop. The
7 unmatched (checked with free listings and a read-only query) are next-round
matches not stored yet (the match ingest runs at 06:30 UTC) plus Hurkacz v
Rune, stored with a past start, so it is outside the upcoming window. None is
a name-matching miss.

**Step 4 real write** (2026-10-28 21:37 UTC, owner-approved, 3 credits, 227
left): same 12 totals, all stored as `pinnacle` `total_games` rows (ATP 8,
WTA 4), lines 19.5 to 25.0, checked by a read-only query.

## Decision

**Path B** (no free Odds-API.io book sends tennis totals). Owner chose
**B1, The Odds API** (2026-10-28) and approved the 2-credit probe, which
found totals. Steps 3-6 are amended to a B1 ingest, pending approval.

**What B1 means (read before approving):**

- **Coverage.** ATP and WTA tour-level events only. Challenger (1,418 lines
  in 28 days) and WTA 125 keep `no_market_total`.
- **Cost.** One credit per active tennis key that has a matched event, once
  a day: usually 1 to 4 a day, about 30 to 120 a month. The month has about
  100 credits free after NFL, Pinnacle and NBA (about 397), so tennis stops
  at a 150-credit floor before NBA's 100 floor and goes dark late in a
  heavy month.
- **Rows reach every existing reader.** `match_odds` has no provider
  column, and every tennis reader takes the newest `total_games` row from
  any book: prop projections (`_fetch_market_totals`), best picks, and the
  bankroll builder's priced Total Games pick. Those priced picks stopped
  on 2026-10-27 and **resume for covered matches**, as they ran on Bet365
  before. No pick, tier or color logic changes. Book keys are The Odds
  API's own (`pinnacle`, `marathonbet`, ...); none collides with a stored
  key, and the reader's tie order puts them last (they never share a run
  with another book).
- **Totals only.** No moneyline or spread from The Odds API; the moneyline
  stays on Odds-API.io.

**Invariants review (2026-10-28, Step 6)** corrected and added to the above:

- **Best picks stays off.** `get_today_match_odds_as_props` filters to
  `settings.live_odds_bookmakers` (DraftKings, FanDuel), so Pinnacle rows
  never become priced best-picks Total Games picks. Only the prop
  projections (`_fetch_market_totals`) and the retired bankroll builder
  (`get_all_market_odds_batch`, any book; `/tennis/bankroll-builder` and
  `/parlays/suggested`, hidden from nav) read them.
- **Fixed:** the ingest logged `httpx` errors whose text carries the
  request URL and `apiKey`; it now logs only the status code, and a failed
  `/sports` listing fails the run without the URL.
- **Open for the owner:** the bankroll builder will again emit Over/Under
  picks priced at Pinnacle or eu-book odds that US users cannot bet, with no
  book label, on the unvalidated `2p(1-p)` set weight. Left unchanged here
  (no pick logic change in scope).
- **For 48e and set-weight work:** `props-v3` snapshots now hold two input
  regimes (tour-level lines anchored on Pinnacle or eu books from the first
  12:45 run; Challenger and WTA 125 unanchored), and the snapshot records
  `market_total_games` but not its book. 48e's rule should split by
  `projection_source` or start after 48b ships. The "clean totals" sample
  (rows on or after 2026-09-25 18:17 UTC) now mixes Bet365 and Pinnacle;
  filter by book before refitting the set weight.
- **Minor:** match research's book freshness (`get_book_freshness`) will
  list `pinnacle`; a fresh daily total can sit beside stale moneylines.

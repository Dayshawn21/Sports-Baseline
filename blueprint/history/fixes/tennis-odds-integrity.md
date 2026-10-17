# Tennis odds integrity

**Type:** Fix

## The problem

The tennis review (2026-09-25, item 2) found that the moneyline price behind
every prediction and pick is unreliable in three ways.

1. **The book is effectively random.**
   - `get_latest_odds` and `get_latest_odds_batch`
     (`api/app/repositories/matches.py:295,446`) take the newest `match_odds`
     moneyline row with `ORDER BY fetched_at DESC`.
   - One odds run commits once (`api/app/ingest/odds_api.py:728`), so every book
     in that run shares the same `fetched_at`. `DISTINCT ON` then picks
     DraftKings or Bet365 arbitrarily.
   - The market probability, EV and Kelly can therefore change between two
     requests with no new data.
2. **Bet365 is stored as "betonline.ag".**
   - The `BookConfig` for Bet365 has the canonical name `betonline.ag`
     (`odds_api.py:451`).
   - The Tennis and Tennis Props pages label that source "BetOnline"
     (`web/src/pages/TennisIntelligencePage.tsx:26`,
     `web/src/utils/tennisPropBoard.ts:24`).
3. **Event matching is loose.**
   - `_event_matches` (`odds_api.py:268`) accepts any Odds-API.io event whose
     home/away names contain the two last names. It does not check the date,
     and it does not filter out doubles or ITF events.
   - `home_is_p1` is a separate substring test (`odds_api.py:648`). It can get
     the orientation wrong for shared or nested surnames, which swaps p1 and p2
     odds.
   - The live router already filters leagues to ATP/WTA/Challenger singles
     (`api/app/routers/props.py:519-534`), but the ingest does not.

## The fix

- **Moneyline selection:** order by `fetched_at DESC`, then a fixed book
  priority (DraftKings, then Bet365 with its legacy `betonline.ag` rows, then
  Betfair Exchange, then anything else), in both moneyline queries.
  - This mirrors the priority already used for total games
    (`routers/props.py:715-719`).
  - The latest run still wins, so a fresher price from a lower-priority book
    beats a stale DraftKings row.
- **Bet365 name:** store new Bet365 rows as `bet365`.
  - Readers already accept `bet365`, `betonline.ag` and `betonline`
    (`routers/props.py:717,894`, `routers/tennis.py:259`), so history rows
    still read.
  - Relabel the "BetOnline" source to "Bet365" on both pages.
- **Event matching:**
  - Move the router's league test into one shared pure helper, and use it in
    the router and the ingest.
  - Require the event start within 12 hours of the match's `start_utc` when
    both are known (the window prop linking already uses).
  - Match surnames as whole name tokens, not substrings.
  - Take `home_is_p1` from the pairing that matched, instead of a second
    substring test.

**Must not break:**
- The live-odds router's output.
- The existing odds market inventory and quota tests.
- Total-games and spread reads of old `betonline.ag` rows.

**Out of scope:**
- A consensus or sharp-book market probability, and which book you actually
  bet at. Review items 6 to 8 revisit the market baseline.
- Backfilling or rewriting stored `betonline.ag` rows.

## Build steps

1. [x] **Deterministic moneyline book and the Bet365 label.**
   - Add the book-priority tiebreak to both moneyline queries.
   - Change the canonical name to `bet365`, keeping the legacy aliases.
   - Relabel the web source.
   - Update `test_odds_market_inventory.py`, which expects `betonline.ag`.
   - Done when:
     - Tests pass.
     - Two successive `GET /tennis/predictions/today` calls return identical
       `p1MarketProb` and odds for every match.
     - A read-only SQL check shows the chosen book is DraftKings wherever the
       latest run has a DraftKings moneyline row.
2. [x] **Stricter event matching.**
   - Add the shared league helper and use it in the router and the ingest.
   - Add the start-time window and whole-token surname matching, with
     orientation returned from the match.
   - Tests:
     - A doubles or ITF league is rejected.
     - An event more than 12 hours from the match start is rejected.
     - A reversed home/away pairing returns `home_is_p1 = False`.
     - A surname contained in another (e.g. "Li" vs "Lin") does not match.
     - Normal matches still match.
   - Done when these tests and the existing odds tests pass.

## Verify

- `cd api && .venv\Scripts\python.exe -m pytest`
- `cd web && npm run test && npm run build`
- Call `GET /tennis/predictions/today` twice and compare the odds and
  `p1MarketProb`: they should be identical.
- The Tennis page source picker and the Tennis Props board show "Bet365", not
  "BetOnline".
- Optional, spends a few Odds-API.io requests:
  `python -m app.ingest.odds_api --hours-ahead 14`. The log's
  "Matched N / M" line should be close to the previous run's, and new rows
  should carry `book = 'bet365'`.

## Completion evidence

- `cd api && .venv\Scripts\python.exe -m pytest` passed, 1191 tests.
- `cd web && npm run test` passed, 167 tests; `npm run build` passed.
- Before the fix, 100 of 107 matches with moneyline odds in the prior 3 days had
  DraftKings and Bet365 tied on the latest `fetched_at`. After it, two
  successive `GET /tennis/predictions/today` calls returned identical odds and
  `p1MarketProb` for all 22 priced matches, and DraftKings was chosen for every
  match whose latest run carried it (106 of 107; the other had Bet365 only).
- The first step-2 build matched 1 of 16 matches live: the league filter copied
  from the live-odds router assumed "ATP - ATP <event>", while Odds-API.io
  names leagues "ATP - Chengdu, China", "WTA 125K - ...", "Challenger - ...".
  Some stored names also carry non-breaking spaces, and the feed sometimes
  writes "Surname, First". Both were fixed and pinned with tests using real
  league names.
- Replayed on one saved event snapshot, the old matcher found 13 of 15 and the
  new one 14 of 15. It gained two names with non-breaking spaces. It dropped
  Jodar v Bublik, listed as "Exhibition - Laver Cup, Singles Matches", which
  the user chose to exclude. The other 12 matched the same event with the same
  orientation.
- Live `python -m app.ingest.odds_api --hours-ahead 14`: 152 tour singles
  events of 484, matched 14 of 15, inserted 40 rows under `bet365` and
  `draftkings`. DraftKings and Bet365 agreed on the favourite in 12 of 13
  matches; the 13th was a Bet365 pick'em (-120/-120), not a swap.
- `/#/tennis/board` source bar shows Bet365.

## Follow-ups

- `get_all_market_odds_batch` has the same same-run book tie for total games,
  set markets, and spreads.
- The best-picks live moneyline overlay (`routers/tennis.py` `_match_event`)
  still uses last-name substring matching; it could reuse `match_event`.

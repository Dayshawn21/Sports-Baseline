# Tennis frontend display

**Type:** Fix

## The problem

The tennis review (2026-09-25, item 4) listed display problems on the tennis
pages. Each was re-checked in the source before this spec.

1. **Evening matches vanish from a chosen date.**
   - With a date picked, `useTennisToday`, `useBestPicks` and
     `useBankrollBuilder` fetch only that UTC `match_date`
     (`web/src/hooks/useTennisToday.ts:18`).
   - The page then keeps only matches whose Central-time date equals it
     (`web/src/utils/unifiedTennis.ts:577`).
   - A match at 7pm CT or later is stored under the next UTC date, so it is
     never fetched.
2. **The same moneyline bet can appear twice.**
   - Best picks and the bankroll builder both produce "X ML (odds)" for the same
     side.
   - `mergeBankrollPicks` only removes overlaps with derived set picks
     (`unifiedTennis.ts:237`), and the dedupe key includes `pickType`
     (`unifiedTennis.ts:128`), so both copies survive.
3. **Moneyline edge means two different things.**
   - The Tennis Props board computes a moneyline row's edge as percentage
     points, model minus market (`web/src/utils/tennisPropBoard.ts:179`).
   - The backend's moneyline pick uses relative edge, (model − market) ÷ market
     (`api/app/services/tennis/best_picks.py:142`).
   - The same bet therefore shows a different edge on each page.
4. **EV is sorted by its absolute value.** `compareLines` sorts on
   `Math.abs(evPct)` (`tennisPropBoard.ts:285`), so within a tier a −30% EV line
   ranks above a +5% one.
5. **Props for finished or mislinked matches can still be rated.**
   - The board's `BLOCKING_FLAGS` (`tennisPropBoard.ts:56`) lacks
     `match_finished` and `match_link_invalid`.
   - The backend only strips those from PrizePicks rows, so a sportsbook row for
     a finished match stays rateable.
6. **Kelly is shown without saying which Kelly.** The backend returns
   quarter-Kelly, but `/parlays` labels it "% Kelly"
   (`web/src/pages/ParlaysPage.tsx:221,593`).
7. **A parlay's edge always gets a plus sign.**
   ``value={`+${edgePct}%`}`` (`ParlaysPage.tsx:411`) shows "+-3.0%" when the edge
   is negative.
8. **`/bets` shows made-up month-to-date numbers.**
   - `MonthSnapshotCard` renders a hardcoded `MONTH_TO_DATE_SNAPSHOT`: 6 bets,
     +$8.37 (`web/src/pages/BetsPage.tsx:44,147,758`).
   - No API backs it, and you track bets outside the app.
9. **Live Odds names books it may not have fetched.** The status bar hardcodes
   "DraftKings · Bet365" (`web/src/pages/LiveOddsPage.tsx:955`), while the
   response carries the real `bookmakers` value.

**Checked and left alone:** the evidence panel labels a moneyline row's
de-vigged probability "Market probability". That label is accurate.

## The fix

- **Dates.** When a date is chosen on `/`, fetch that UTC date and the next one,
  then filter by the Central date as today. Put the date pair in one pure
  helper, used by the predictions and best-picks hooks.
  - The bankroll hook gets an opt-in `centralDay` mode that fetches both dates
    and merges them. Only the Tennis page turns it on, because it filters
    bankroll singles by Central date afterwards.
  - `/parlays` keeps its UTC-day date picker. Parlay legs carry no start time,
    so merged parlays cannot be filtered to a Central day on the client. Fixing
    that needs the endpoint to filter by Central day, which is noted as a known
    limitation.
- **Duplicates.** Drop a bankroll moneyline pick when best picks already has
  the moneyline for the same player. Keep the best-picks copy, because it
  carries the quality flags the bankroll conversion drops.
- **Edge.** Compute the board's moneyline edge as relative edge, matching the
  backend.
- **EV sort.** Sort by signed EV, highest first, with missing EV last.
- **Blocking flags.** Add `match_finished` and `match_link_invalid` to
  `BLOCKING_FLAGS`.
- **Labels.** "¼ Kelly" wherever `/parlays` shows a Kelly fraction; the parlay
  edge shows its real sign; the hardcoded `/bets` month-to-date card is removed;
  the Live Odds status bar shows `data.bookmakers`.

**Must not break:**
- The default today-plus-tomorrow view.
- NFL pages.
- Derived-pick overlap handling.
- The Win a Set rows staying unrateable.
- Existing web tests.

**Out of scope:**
- The backend follow-ups from the odds and parser fixes:
  - `_fetch_market_total_games` ordering
  - the same-run book tie in `get_all_market_odds_batch`
  - the best-picks overlay's old matcher
- "Stats as of" and "odds as of" timestamps. That is new display work, not a
  fix.

## Build steps

1. [x] **Fetch the right dates.**
   - Add a pure helper returning the UTC dates that cover a Central-time day.
   - Use it in the predictions and best-picks hooks, and in the bankroll
     hook's `centralDay` mode for the Tennis page.
   - Tests: the helper returns the chosen date and the next, including across
     a month end.
   - Done when the test passes, and choosing today's date on `/` shows the
     same late-evening matches as the default view.
2. [x] **Consistent picks on the board and command center.**
   - Moneyline dedupe, relative moneyline edge, signed EV sort, blocking flags.
   - Tests in `unifiedTennis.test.ts` and `tennisPropBoard.test.ts`:
     - one moneyline pick survives a best-picks and bankroll pair
     - the board's moneyline edge equals (model − market) ÷ market
     - +5% EV ranks above −30% within a tier
     - a `match_finished` row is not rateable
   - Done when these pass.
3. [x] **Honest labels.**
   - The ¼ Kelly labels, the signed parlay edge, removing `MonthSnapshotCard`,
     and the Live Odds books from the response.
   - Done when `npm run build` passes, and screenshots of `/parlays`, `/bets`
     and `/live-odds` show the new labels and no month-to-date card.

## Verify

- `cd web && npm run test && npm run build`
- On `/`, pick today's date: late-evening Central matches still appear.
- A match with both a best-picks and a bankroll moneyline pick shows it once.
- `/parlays` shows "¼ Kelly", and a negative edge shows its minus sign.
- `/bets` has no month-to-date card; `/live-odds` lists the books that were
  actually requested.

## Completion evidence

- `cd web && npm run test` passed, 173 tests; `npm run build` passed. The API was
  not touched.
- Step 1: Central 2026-09-25 held 36 matches in `GET /tennis/predictions/today`
  for UTC 09-25 and 09-26.
  - The old single-date fetch kept 32. The four it dropped started 7:30 to
    10:30pm CT (Andrade v Basavareddy, Bondar v Ruse, Tararudee v Joint,
    Korneeva v Preston).
  - In the browser, with 2026-09-25 picked, Bondar, Tararudee, and Korneeva
    are listed and the next day's Chengdu matches are not. Basavareddy's match
    has no picks and is absent from the default view too.
- Step 2: each of the 4 new tests fails with its source change removed and
  passes with it.
- Step 3, in the browser:
  - `/parlays` shows "¼ Kelly" 11 times and no bare "% Kelly".
  - `/bets` has no month-to-date card.
  - `/live-odds` reads "Books: DraftKings · Bet365" from the response's
    `bookmakers` field.
  - No parlay had a negative edge that day, so the signed display was not
    seen live.

## Known limitation

- The `/parlays` date picker still means a UTC day. Parlay legs carry no start
  time, so a Central-day filter needs the endpoint.

## Follow-ups

- `_fetch_market_total_games` ranks DraftKings above Bet365 before recency.
- The same-run book tie in `get_all_market_odds_batch`.
- The best-picks live overlay's old name matcher.

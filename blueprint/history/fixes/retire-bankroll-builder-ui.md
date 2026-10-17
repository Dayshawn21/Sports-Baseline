# Retire the Bankroll Builder from the tennis UI

**Type:** Fix

## The problem

Decided with the user on 2026-09-25: the Bankroll Builder does not fit how the
user bets.

- It ranks moneyline, straight-sets, underdog set-cover and total-games singles,
  and builds 2-leg parlays.
- The user bets moneylines and game spreads at books and props on PrizePicks.
  - Its moneyline singles duplicate best picks. The frontend display fix had to
    remove that duplicate.
  - It has no game-spread picks.
  - It does not cover PrizePicks.
- Its parlays compound an edge the model has not yet shown against the closing
  line (review items 6 and 7).
- Its "(odds from ML)" picks are priced at an imputed fair price, with no
  bookmaker margin, so their EV reads high.
- The Tennis page still merges its singles in, and waits on it before rendering:
  `useBankrollBuilder` in `web/src/pages/TennisIntelligencePage.tsx:101,117,122,152,239`.
  It is the slowest endpoint on the page.

## The fix

A reversible UI retirement. The backend stays in place.

- Remove the `Bankroll` item from the nav (`web/src/App.tsx:23`). Keep the
  `/parlays` route, so the page still opens by URL.
- Stop fetching and merging bankroll singles on the Tennis page. Drop the hook
  call, its loading gate, and its retry notice, and pass no bankroll picks to
  `composeUnifiedMatches`. Its `bankrollPicks` argument already defaults to
  `[]`.
- Remove the `centralDay` option from `useBankrollBuilder`, returning it to one
  query. Only the Tennis page used that option; `/parlays` never did.
- Drop the `/bets` empty-state sentence that points to "Track" on Bankroll
  Builder picks (`web/src/pages/BetsPage.tsx:642`).

**Must not break:**
- `/parlays` still loading by URL.
- Best-picks moneyline, spread, and set picks on the Tennis page.
- The PrizePicks, DraftKings, and Bet365 prop sources.
- The `composeUnifiedMatches` bankroll tests. The merge path stays and is
  tested; only the page stops feeding it.

**Out of scope:**
- Deleting `ParlaysPage`, the `/tennis/bankroll/today` and
  `/tennis/parlays/suggested` endpoints, or `bankroll_builder.py`.
- Reviving stake sizing as singles-only once review items 6 and 7 show an edge.
  That is a later decision.

## Build steps

1. [x] **Hide the Bankroll Builder.**
   - The nav item, the Tennis page wiring, the `centralDay` option, and the
     `/bets` sentence.
   - Done when:
     - `npm run test` and `npm run build` pass.
     - The nav no longer shows Bankroll.
     - `/#/parlays` still loads.
     - The Tennis page loads without calling `/tennis/bankroll/today` (seen in
       the browser's network requests) and still lists moneyline and spread
       picks.

## Verify

- `cd web && npm run test && npm run build`
- Open `/`: no Bankroll tab, and no request to `/api/tennis/bankroll/today`.
  Best-picks moneyline and Game Spread picks still show.
- Open `/#/parlays` directly: the page still loads.

## Completion evidence

- `cd web && npm run test` passed, 173 tests; `npm run build` passed. The API
  was not touched.
- In the browser, the nav reads Tennis, Tennis Props, NFL, Prop Board, Live
  Odds, My Bets, Admin.
- `/` issued predictions and best-picks requests for 2026-09-25 and 09-26, the
  three prop sources, and player stats, but no `/tennis/bankroll/today`. It
  listed 20 matches with Game Spread picks.
- `/#/parlays` still loaded by URL, with 11 singles.

## Notes

- While verifying, Odds-API.io returned 429: 100 requests per hour exceeded,
  resetting about 19:12 UTC.
- `_overlay_live_moneyline` calls the live API from every best-picks and
  bankroll request whose predictions lack stored odds, and it swallows the
  failure. Matches beyond the 14-hour stored-odds window then get no moneyline
  pick. Vacherot v Harris was missing one on the Tennis page for this reason,
  not because of this change: both paths share the overlay.
- Follow-up: stop calling the live API per request (cache it, or rely on the
  scheduled ingest), and replace the overlay's last-name substring matcher with
  `app/core/tennis_odds_events.match_event`.

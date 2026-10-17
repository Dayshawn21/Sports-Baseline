# Switch NFL book odds to The Odds API

**Type:** Fix

## The problem

NFL game odds used the tennis provider and `ODDS_API_KEY`, consuming the same
budget as Tennis.

## The fix

NFL now uses `https://api.the-odds-api.com/v4` with its dedicated
`THE_ODDS_API_KEY`. Tennis remains on `api.odds-api.io` and `ODDS_API_KEY`.
The existing `nfl_game_odds` snapshots and de-vigged moneyline model input stay
unchanged.

## Build steps

- [x] **Step 1 - Add isolated NFL provider configuration and request contract.**
  Added dedicated local and workflow configuration, with a US-only request for
  `h2h,spreads,totals` American odds.

- [x] **Step 2 - Parse, match, and persist The Odds API NFL events.** Adapted
  parsing for events, bookmakers, outcomes, home/away orientation, spreads, and
  totals. Added JSONB serialization at the snapshot repository boundary after
  live verification exposed the missing cast.

- [x] **Step 3 - Run one bounded live verification.** The corrected live ingest
  matched 29 games, skipped 0, stored 560 snapshots, and left 491 credits.
  The Week 3 slate reported zero `market_missing` flags.

## Verify

- `cd api && .venv\Scripts\python.exe -m pytest tests/test_nfl_odds.py` - 10 passed.
- `cd api && .venv\Scripts\python.exe -m pytest` - 766 passed.
- `cd web && npm run test` - 61 passed.
- `cd web && npm run build` - passed.
- Live ingest - matched 29, skipped 0, stored 560, with 491 credits remaining.

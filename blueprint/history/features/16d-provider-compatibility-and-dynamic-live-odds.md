# Provider compatibility and dynamic Live Odds

**From build-plan:** feature 16d
**Completed:** 2026-09-16

## Delivered

- Added server-owned, validated `LIVE_ODDS_BOOKMAKERS` configuration, preserving
  the existing `DraftKings,Bet365` default.
- Removed the browser-controlled bookmaker query parameter from Live Odds.
- Reused 16c's approved no-market evidence for the identical configured scope;
  the user explicitly declined a duplicate provider request.
- Replaced fixed bookmaker columns with the stable union of books actually
  returned by the Live Odds response.

## Verification

- `api/.venv/Scripts/python.exe -m pytest` - 720 passed.
- `web/npm run build` - passed.
- `web/npm run test` - 54 passed.

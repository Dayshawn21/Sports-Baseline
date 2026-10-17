# Feature: Odds free-tier rate-budget hardening

**From build-plan:** feature 16b
**Status:** complete

## Goal

Keep tennis odds ingestion useful during Grand Slam volume on a free Odds-API.io plan by reducing scheduled request volume and making quota pressure visible before the API cuts off requests.

## In scope

- Reduce the scheduled odds refresh cadence from every 2 hours to every 4 hours.
- Log rate-limit headers returned by Odds-API.io on successful events and odds calls.
- Stop fetching additional odds batches when the provider reports the remaining request budget is at or below a small safety floor.
- Add focused tests for header parsing and low-quota stop decisions.

## Out of scope

- Expanding bookmaker coverage.
- Switching providers.
- Adding a UI quota monitor.
- Changing match, odds, or prop schemas.

## Build steps

- [x] **Step 1 - Add quota helpers** - parse Odds-API.io rate-limit headers and decide when remaining quota is too low to continue. *Done when:* tests cover missing, valid, invalid, and low remaining header values.
- [x] **Step 2 - Apply quota guard to odds ingest** - log quota state after events and batch odds responses, and stop batch fetching when remaining quota reaches the safety floor. *Done when:* the ingest loop uses the helper and preserves existing behavior when headers are absent.
- [x] **Step 3 - Reduce scheduled cadence** - change the GitHub Actions odds cron and comments from every 2 hours to every 4 hours. *Done when:* the schedule estimates lower busy-day call volume and still uses the existing 14-hour odds window.

## Files / areas

- `api/app/ingest/odds_api.py`
- `api/tests/test_odds_api_quota.py`
- `.github/workflows/tennis-ingest.yml`
- `blueprint/build-plan.md`

## Data / contracts

- No schema, API route, or stored data contracts changed.
- CLI keeps existing defaults and adds `--min-requests-remaining`, defaulting to 5.

## Testing

- `.venv\Scripts\python.exe -m pytest tests\test_odds_api_quota.py -p no:cacheprovider --basetemp=C:\Users\dayshawn\AppData\Local\Temp\sportapp-odds-quota` - 6 passed.
- `.venv\Scripts\python.exe -m pytest -p no:cacheprovider --basetemp=C:\Users\dayshawn\AppData\Local\Temp\sportapp-full-odds-quota` - 573 passed.

## Notes for the AI

- Do not add bookmakers in this slice.
- Missing rate-limit headers should not break ingest.
- Prefer stopping early with partial odds over triggering provider cutoff during a Grand Slam slate.

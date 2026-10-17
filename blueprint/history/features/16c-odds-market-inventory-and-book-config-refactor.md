# Odds market inventory and book-config refactor

**From build-plan:** feature 16c
**Completed:** 2026-09-16

## Goal

Make the tennis odds ingest explain exactly which bookmaker and market names the
current Odds-API.io tier returns, then replace its duplicated per-book write
blocks with one declarative bookmaker configuration. This gives 16d a reliable
inventory for deciding which books and stored markets to surface next.

## Delivered

- Added pure, deterministic inventory extraction and report rendering for both
  supported bookmaker payload shapes.
- Added one typed configuration for DraftKings, Betfair Exchange, and
  BetOnline/Bet365 aliases, preserving their existing stored markets and player
  orientation behavior through a single persistence loop.
- Added a bounded `--inventory-only` capture command that makes one tennis
  events lookup and at most one ten-event odds batch, without opening a database
  session or writing odds rows.
- Captured the approved live result in `docs/odds-market-inventory.md`. The
  requested `DraftKings,Bet365` batch returned no bookmaker-market payloads;
  the report records that result and the exact request scope.

## Verification

- `api/.venv/Scripts/python.exe -m pytest` - 714 passed.
- `web/npm run build` - passed.
- `web/npm run test` - 52 passed.

## Build steps

- [x] **Step 1 - add a pure bookmaker and market inventory** - Normalize the
  existing dict and list bookmaker payload shapes into a deterministic inventory,
  and render a durable report without storing provider payloads or secrets.

- [x] **Step 2 - move supported books into one configuration table** - Introduce
  a typed configuration for the three currently supported book sources and route
  their existing parser output, canonical names, aliases, stored markets, and
  player-order correction through one generic ingest loop.

- [x] **Step 3 - add and run a read-only current-tier capture** - Add a bounded
  inventory-only command that uses at most one active-tennis event batch, writes
  no database rows, and renders `docs/odds-market-inventory.md` from the response.
  The approved capture ran once without retries.

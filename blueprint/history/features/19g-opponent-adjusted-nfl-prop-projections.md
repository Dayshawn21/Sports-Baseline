# Opponent-adjusted NFL prop projections

**Type:** Feature
**From build-plan:** 19g
**Status:** complete

## Goal

Make each eligible NFL full-game prop projection account for the scheduled
opponent's historical allowance to that offensive position and prop metric. The
adjustment must use only data available before the slate week, be deliberately
bounded, and remain explainable in the NFL slate.

## In scope

- Defense-versus-position (DVP) averages from existing weekly NFL player stats.
- A shared pre-week cutoff for player and opponent aggregates.
- A pure capped DVP adjustment layered on player-history and moneyline input.
- Sample safeguards, quality flags, API fields, and compact slate display.

## Out of scope

- Player usage inputs such as targets, target share, routes, red-zone work, or injuries. These belong to 19h.
- Individual coverage matchups, personnel, weather, rest, spreads/totals, trained ML, historical profitability backtests, betting automation, provider changes, migrations, and settlement.

## Data and behavior contract

The slate projection input receives optional scheduled-opponent and league
position averages plus an opponent player-game count for the matching prop
metric. The API exposes `opponentAdjustmentPct` and `opponentSampleGames`; the
model version is `opponent-dvp-v1`.

All player, position, opponent, and league aggregates use only regular-season
rows from an earlier season or from the requested season before the requested
week. Missing, invalid, or undersized DVP evidence leaves the projection
unchanged and carries an explicit quality flag. The full-game standard-line edge
gate remains unchanged.

## Build steps

- [x] **Step 1 - Define the opponent-adjustment model contract.** Added pure
  sample-shrunk, capped DVP projection math, model version, flags, and
  deterministic unit coverage.
- [x] **Step 2 - Supply batched, as-of player and opponent inputs.** Added one
  repository query for player, position, scheduled-opponent, and league inputs
  using a shared pre-week regular-season cutoff.
- [x] **Step 3 - Surface the adjustment on the NFL slate.** Returned adjustment
  percentage and sample count through API types and rendered a compact opponent
  signal in the NFL slate.
- [x] **Step 4 - Verify behavior against the app.** Focused and full API tests,
  web tests/build, and live slate inspection passed.

## Files and areas

| Path | Change |
|---|---|
| `api/app/core/nfl_projection.py` | Pure DVP adjustment, safeguards, model version, and flags. |
| `api/app/repositories/nfl.py` | Batched pre-week player, position, opponent, and league aggregates. |
| `api/app/routers/nfl.py` | Typed slate projection input and output mapping. |
| `api/app/schemas/nfl.py` | Opponent adjustment and evidence response fields. |
| `api/tests/test_nfl_projection.py` | Projection and API-wiring coverage. |
| `api/tests/test_nfl_repository.py` | As-of and opponent-position query coverage. |
| `web/src/types/nfl.ts` | Slate contract additions. |
| `web/src/pages/NflIntelligencePage.tsx` | Opponent adjustment display. |

## Verification

- `api/.venv/Scripts/python.exe -m pytest tests/test_nfl_projection.py tests/test_nfl_repository.py` - 43 passed.
- `api/.venv/Scripts/python.exe -m pytest` - 747 passed.
- `npm run test` from `web/` - 54 passed.
- `npm run build` from `web/` - passed.
- Live `/#/nfl` check for 2026 Week 2: the table displayed signed opponent
  adjustments and an explicit no-data fallback. The API reported 2,746 adjusted
  lines, one missing-opponent row, and zero non-standard or non-full-game rows
  with a bettable edge.

## Notes

- Historical defense allowance uses the weekly-stat opponent team, not the
  last-write-wins `nfl_players.team_id`.
- Targets and other volume signals remain deferred to 19h.

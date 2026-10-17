# NFL player usage inputs

**Type:** Feature
**From build-plan:** 19h
**Status:** complete

## Goal

Persist NFLverse receiving-usage signals and apply a transparent, bounded usage
adjustment to eligible NFL receiving-prop projections. The model must tell the
user when usage data is missing or too thin instead of treating unbackfilled
history as zero opportunity.

## In scope

- Store NFLverse `targets`, `target_share`, `air_yards_share`, and `wopr` in
  `nfl_player_weekly_stats` with a forward migration.
- Parse and idempotently upsert those fields, preserving a real zero separately
  from a missing source column.
- Re-import the currently loaded NFL seasons so historical projection inputs are
  populated after the migration.
- Add pre-week player and position usage aggregates to the existing batched NFL
  slate query.
- Apply a capped, sample-aware target-volume and target-share adjustment only to
  full-game receiving yards and receptions projections.
- Return and display the usage adjustment and supporting sample on the NFL slate.
- Add focused parser, repository, pure-model, and API-contract coverage.

## Out of scope

- Route participation, red-zone opportunities, snap counts, individual coverage
  matchups, injuries, weather, player news, or a trained ML model.
- Using receiving usage to adjust passing, rushing, anytime-touchdown, or fantasy
  points props. Those require market-specific feature work rather than a blanket
  multiplier.
- New providers, PrizePicks changes, historical profitability backtests, or bet
  automation.

## Data and behavior contract

**Load-bearing schema change:** migration `0021` adds nullable `targets`
(`smallint`), `target_share` (`float`), `air_yards_share` (`float`), and `wopr`
(`float`) to `nfl_player_weekly_stats`. All are nullable so previously imported
rows and missing source fields remain distinguishable from real zero values.

`NflversePlayerWeek` and `upsert_weekly_stat` carry the same optional fields.
Conflict updates must replace the stored usage fields, allowing a normal seasonal
re-import to backfill existing rows without duplicating games.

For an upcoming slate, usage inputs use the same regular-season, strictly
pre-week predicate as player and opponent aggregates. The projection receives a
player target average, player target-share average, matching position averages,
and a count of usage-bearing player-games. It computes a named, conservative
usage adjustment from target volume and target share, shrunk for thin evidence
and capped at a named maximum. The adjustment applies only to `receiving_yards`
and `receptions`; every other market remains unchanged and has no misleading
missing-data flag.

The slate adds nullable `usageAdjustmentPct` and `usageSampleGames`. A receiving
market with unavailable, invalid, or undersized usage evidence keeps its prior
projection and returns a quality flag. A non-receiving market returns `null` for
both fields because usage is not applicable to it in this feature.

## Build steps

- [x] **Step 1 - Add nullable usage storage and parser coverage.** Create
  migration `0021`, extend the NFLverse transfer object and parser, and update
  the idempotent weekly-stat repository write.
  *Done when:* parser tests prove real `targets`, `target_share`,
  `air_yards_share`, and `wopr` values are read from the published-header fixture,
  missing columns stay `null`, and repository-boundary coverage proves all four
  fields are included on insert and conflict update.

- [x] **Step 2 - Backfill the loaded seasons and aggregate usage as of the slate.**
  Re-import the locally supported NFL seasons after the migration, then extend
  the batched slate query with player and position target/target-share averages
  and a usage-bearing sample count.
  *Done when:* the import remains idempotent, repository coverage proves
  current-week/future rows and null usage rows do not count as evidence, and a
  local query confirms historical rows received usage values without duplicating
  player-game rows.

- [x] **Step 3 - Apply and surface receiving-usage adjustments.** Extend the
  pure model with named usage safeguards and deterministic math, wire the inputs
  through the NFL slate API, and add a compact Usage column beside Opponent.
  *Done when:* unit tests prove favorable, unfavorable, neutral, capped,
  missing, and thin usage behavior; receiving yards/receptions change only when
  safe; other markets remain unchanged; the slate returns the adjustment and
  sample with matching TypeScript types.

- [x] **Step 4 - Verify the completed usage path.** Run focused and full API
  tests, web tests, and the production build, then inspect a live NFL slate with
  one adjusted receiving prop and one ineligible or unavailable-usage row.
  *Done when:* the rendered Usage column matches the API response, missing usage
  remains explicit, the new adjustment never creates an edge for non-standard or
  non-full-game lines, and browser console/network checks are clean aside from
  documented unrelated assets.

- [x] **Step 5 - Keep unparseable target counts unknown.** *Fixes:* F-01.
  Make `_as_optional_int` return `None` for a value that does not parse, matching
  `_as_optional_float`, and extend the missing-column parser test with an `NA`
  token.
  *Done when:* an `NA` usage row parses to `null` for all four usage fields, real
  integer and float-formatted target counts still parse, and the API tests pass.

## Files and areas

| Path | Change |
|---|---|
| `api/app/db/migrations/versions/0021_nfl_player_usage.py` | Nullable weekly-stat usage columns and downgrade. |
| `api/app/ingest/nflverse.py` | NFLverse usage parsing and re-import path. |
| `api/app/repositories/nfl.py` | Usage upsert and batched pre-week player/position aggregates. |
| `api/app/core/nfl_projection.py` | Pure, capped receiving-usage adjustment and flags. |
| `api/app/routers/nfl.py`, `api/app/schemas/nfl.py` | Slate projection input/output contract. |
| `api/tests/test_nflverse.py`, `api/tests/test_nfl_repository.py`, `api/tests/test_nfl_projection.py` | Parser, persistence, as-of, and model coverage. |
| `web/src/types/nfl.ts`, `web/src/pages/NflIntelligencePage.tsx` | Usage contract and data-first slate display. |

## Testing

- Use fixed NFLverse fixture values and no live provider calls in automated tests.
- Run `api/.venv/Scripts/python.exe -m pytest` from `api/`.
- Run `npm run test` and `npm run build` from `web/`.
- Check migration state before the re-import and record stored-row counts before
  and after it; no duplicate player-game rows are acceptable.
- Use the running `/nfl` slate for final display and network evidence.

## Notes for the AI

- Keep nullable unknown values nullable through parser, repository, aggregate,
  model input, API, and UI. Do not coerce them to `0`.
- `targets` and `target_share` drive the 19h adjustment. Persist
  `air_yards_share` and `wopr` now for later market-specific work, but do not add
  an unvalidated extra multiplier in this feature.
- Apply the usage adjustment after the existing market and opponent adjustments
  only for receiving yards and receptions. Preserve the existing full-game and
  standard-line edge gate.
- Re-importing public NFLverse data writes to the local database. Do not run it
  in tests; run it once as an explicit implementation verification step.

## Implementation notes

- Usage math converts targets and target share into position-typical production
  and applies part of the gap to the player's actual average
  (`USAGE_EFFICIENCY_REGRESSION = 0.35`), shrunk for sample and capped at 8%. A
  full pull capped 1,016 of 1,830 adjusted week 2 receiving props; 0.35 capped
  223 with a -1.05% median.
- Backfill of 2024-2026 kept row counts unchanged (18,112 / 18,522 / 1,117) and
  populated usage on every row. Migration state `0021 (head)`.
- Verification: API tests 766 passed, web tests 54 passed, web build passed, and
  the `/nfl` week 2 slate matched the API for adjusted, invalid-usage, and
  not-applicable rows with no edge on non-standard or non-full-game lines.
- Open follow-up: F-02 (unverified) - usage adjustment may skew receiving
  projections downward; needs a settled-results backtest.

## Findings

### 19h/F-01 [P3] closed - Optional int parser turns an "NA" target count into zero

**File:** api/app/ingest/nflverse.py:96
**Found:** 2026-09-17 by /audit (scope: current; lens: all)
**Why it matters:** `targets` used `_as_optional_int`, which returned `None` only
for `None` or `""`, so a token such as `NA` was stored as `0` while
`target_share` with the same token became `None`.
**Suggested fix:** Return `None` from `_as_optional_int` when the value does not
parse, and add an `NA` case to the parser test.
**Resolution:** Step 5 routed `_as_optional_int` through `_as_optional_float`.
Re-review found that repair regressed `NaN` to an uncaught `ValueError` and that
`NaN`/`inf` floats passed through; `_as_optional_float` now returns `None` for
non-finite values. `NA`, `NaN`, `inf`, `-inf`, and empty parse to `None`; `6.0`
parses to `6`; API tests 766 passed; local DB holds 0 `NaN` values. Closed.

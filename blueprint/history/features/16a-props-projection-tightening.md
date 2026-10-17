# Feature: Props projection tightening

**From build-plan:** feature 16a
**Status:** complete

## Goal

Tighten existing tennis prop projections before adding broader book coverage, so the top prop list is less noisy and uses signals already present in the data model.

## In scope

- Use opponent allowed double-fault rate when projecting double faults.
- Pass match closeness into total-games probability estimates so total-games confidence reflects deciding-set likelihood, including ATP Grand Slam best-of-5 matches.
- Add focused tests for both projection changes.
- Preserve the Odds-API.io documentation note as later input for book expansion, without changing source integration in this slice.

## Out of scope

- Adding new bookmakers or changing Odds-API.io ingestion.
- Adding new prop stat types.
- UI changes.
- Schema or migration changes.

## Build steps

- [x] **Step 1 - Double-fault matchup adjustment** - incorporate opponent `allowed_df_per_sp` into double-fault expected values with conservative bounds and test it. *Done when:* a player facing an opponent who allows more double faults projects higher than the same player facing a low-DF opponent, and existing double-fault behavior remains stable when opponent data is missing.
- [x] **Step 2 - Total-games deciding-set probability** - pass win-probability-derived deciding-set probability into total-games prop probabilities and test the closer-match distribution. *Done when:* total-games `p_over` changes when win probability changes around the same mean and line, while best-of-5 behavior remains routed through the existing best-of-5 mixture with closeness-weighted 3/4/5-set weights.

## Files / areas

- `api/app/core/prop_projection.py`
- `api/app/core/prop_probs.py`
- `api/app/routers/props.py`
- `api/tests/test_props_audit_projection.py`
- `api/tests/test_total_games_mixture.py`

## Data / contracts

- No schema, API route, or stored data contract changed.
- Existing response fields stay the same; only projected means and probabilities may change.

## Testing

- `.venv\Scripts\python.exe -m pytest tests\test_props_audit_projection.py tests\test_total_games_mixture.py -p no:cacheprovider --basetemp=C:\Users\dayshawn\AppData\Local\Temp\sportapp-props-tightening-bo5` - 40 passed.
- `.venv\Scripts\python.exe -m pytest -p no:cacheprovider --basetemp=C:\Users\dayshawn\AppData\Local\Temp\sportapp-full-props-bo5` - 567 passed.

## Notes for the AI

- Keep coefficients conservative and bounded; do not fit new constants from live guesses.
- Prefer pure `core/` changes with direct tests.
- Do not touch Odds-API.io integration in this slice; the docs are evidence for a later book-expansion feature.

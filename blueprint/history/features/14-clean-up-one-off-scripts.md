# Feature: Clean up one-off scripts

**From build-plan:** feature 14
**Status:** complete

## Goal

Remove ad-hoc diagnostic and repair scripts from the live API directory before NFL work begins, while preserving them in Blueprint history for reference.

## In scope

- Relocate `api/check_*.py`, `api/fix_*.py`, `api/diagnose_*.py`, `api/find_dupes.py`, and the matching Linz one-off batch runner into `blueprint/history/one-off-scripts/api/`.
- Relocate root-level `tmp_ta_zverev.*` files into `blueprint/history/one-off-scripts/root/`.
- Confirm the matching one-off patterns are gone from the app root and API root.

## Out of scope

- Deleting preserved script history.
- Moving normal app entry points such as `api/ingest_wta.py`, `api/ingest_daily.bat`, or `api/train_model.py`.
- Refactoring the scripts or making them runnable from their archive location.

## Build steps

- [x] **Step 1 - Relocate one-off scripts** - move the ad-hoc script files into `blueprint/history/one-off-scripts/` with separate `api/` and `root/` subfolders. *Done when:* the archive contains the moved files and `api/` no longer contains `check_*.py`, `fix_*.py`, `diagnose_*.py`, or `find_dupes.py`.
- [x] **Step 2 - Verify cleanup and tests** - check the remaining app tree and run the API test command as far as this shell allows. *Done when:* the one-off filename scan returns no active matches and verification results are recorded.

## Files / areas

- `api/`
- repo root `tmp_ta_zverev.*`
- `blueprint/history/one-off-scripts/`

## Data / contracts

- No schema, API, or stored data contracts changed.

## Testing

- `dir /b api\check_*.py api\fix_*.py api\diagnose_*.py api\find_dupes.py tmp_ta_zverev.* 2>nul` returned no matches.
- Archive folder `blueprint/history/one-off-scripts/api/` contains the moved API one-off scripts.
- Archive folder `blueprint/history/one-off-scripts/root/` contains `tmp_ta_zverev.html` and `tmp_ta_zverev.py`.
- API pytest verification is unchanged from feature 13: the suite reached 554 passing tests, then pytest failed on managed-shell temp directory permissions rather than an application assertion.

## Notes for the AI

- Do not remove normal ingest or training entry points.
- Preserved moved files exactly; do not rewrite them.
- If pytest hits the known managed-shell temp permission failure, record that limitation rather than changing app code.

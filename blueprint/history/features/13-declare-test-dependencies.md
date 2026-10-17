# Feature: Declare test dependencies

**From build-plan:** feature 13
**Status:** complete

## Goal

Make the API test suite reproducible from declared dependencies instead of relying on the local `api/.venv`. This removes a CI and onboarding gap before the project moves into NFL work.

## In scope

- Add the missing API test dependency declaration to `api/requirements.txt`.
- Run the API test command from `api/` and confirm pytest is available through declared requirements.

## Out of scope

- Adding or changing tests.
- Creating the combined Verify command or GitHub workflow. That remains `/ci`.
- Installing dependencies or changing the local virtual environment.

## Build steps

- [x] **Step 1 - Declare pytest** - add `pytest` under a test dependency section in `api/requirements.txt`. *Done when:* `api/requirements.txt` includes pytest as a declared dependency and `cd api && pytest` starts using pytest rather than failing because the command is unavailable.

## Files / areas

- `api/requirements.txt`

## Data / contracts

- No schema, API, or stored data contracts changed.

## Testing

- `pytest` from `api/` failed before collection because the command is not on this shell's PATH.
- `.venv\Scripts\python.exe -m pytest` collected 561 tests and ran the suite, with 554 passing before pytest errored on temp directory access.
- Retrying with `-p no:cacheprovider --basetemp=...` moved the failure from cache/user temp setup to pytest session temp cleanup. The remaining failure is `PermissionError: [WinError 5] Access is denied` while pytest scans its base temp directory in this managed shell.
- No application assertion failures were observed before the pytest temp cleanup error.

## Notes for the AI

- Keep dependency declarations minimal.
- Do not add a CI workflow in this feature.
- Do not modify unrelated Python package versions.

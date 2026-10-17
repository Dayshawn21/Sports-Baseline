# Props link to finished or wrong-day matches

**Type:** Fix

## The problem

PrizePicks props can link to the wrong tennis match when local PrizePicks start
times cross a UTC date boundary. That can attach a prop to a prior-day match
instead of the intended upcoming match.

The read path also trusts stored `props.match_id` too much. If a prop is already
linked to a completed or cancelled match, or to a match far from the prop start
time, the UI can keep surfacing scored or stale recommendations.

## The fix

Rebuild the parked props-link work from `stash@{0}` and finish the missing
read-path guard.

The fix must:

- normalize PrizePicks link dates through UTC before deriving the match date
- keep string start-time fallback behavior for malformed or partial payloads
- prevent exact start-time linking to completed or cancelled matches
- reject exact start-time links more than 12 hours away from the prop start time
- keep the existing `start_utc IS NULL` escape for matches with unknown start time
- expose linked match status on props returned by the read path
- suppress recommendation and confidence when the linked match has already
  finished or been cancelled
- leave unrelated local state such as `.claude/settings.json` untouched

## Build steps

- [x] Restore and validate PrizePicks UTC link-date handling.

  Done when `api/app/ingest/prizepicks.py` has a small UTC-normalizing helper,
  string fallback behavior is preserved, and `api/tests/test_prizepicks_link_date.py`
  proves the date-boundary cases.

- [x] Guard match linking against finished and far-away matches.

  Done when `api/app/repositories/matches.py` filters exact start-time matches
  away from completed or cancelled records and rejects links more than 12 hours
  from the prop start time, while preserving matches with unknown `start_utc`.

- [x] Guard the props read path against stale stored match links.

  Done when props returned to the API include linked match status, props linked
  to completed or cancelled matches are marked as finished, and finished props do
  not surface recommendation or confidence values as active plays.

## Also included: LightGBM CRLF guard

Carried in the same commit, separate from the props-link scope above.

A `core.autocrlf` checkout rewrote `api/models/*` with CRLF endings. LightGBM
parses model files as parallel byte-offset chunks, so CRLF shifts every chunk
boundary mid-token and aborts the process at load, which no `try`/`except` can
catch. Two changes:

- `.gitattributes` marks `api/models/**` as `-text`, so git stops converting them.
- `ModelRegistry._has_crlf` checks before loading and skips the bundle with a
  warning, so an already-converted working copy degrades instead of crashing.

Covered by `api/tests/test_registry_guards.py`.

## Verify

- `cd api && .venv\Scripts\python.exe -m pytest`
- `cd web && npm run build`
- `cd web && npm run test`
- Re-run `python -m app.ingest.prizepicks` from `api/` and confirm Mertens props
  link to the upcoming match instead of the old completed match.
- Query for props linked to completed or cancelled matches, or matches more than
  12 hours from prop start time, and confirm the read path no longer surfaces
  them as active scored picks.
- Restart the API and confirm stale prop cards are gone while valid upcoming
  props still show confidence and EV.

## Result

Completed 2026-08-29. Verify passed: `pytest` 486 passed, `npm run build` clean
(includes `tsc -b`), `npm run test` 31 passed.

Behavioral evidence against the live database:

- 32,570 props were linked to completed or cancelled matches, the stale-card
  population this fix targets.
- `get_today_props` returns `match_status` (2,159 of 5,245 props carry one; 94
  resolve to a finished or cancelled match).
- `match_finished` and `match_link_invalid` join the `hard_blocks` set in
  `app/routers/props.py`, so those props return `recommendation` and
  `confidence` as `None`.

# Fix: Move the flagged-players queue out of the admin router

**Type:** Fix

**Fixes:** F-66 (API part; the web part landed in `eaadc9bd`)

**Branch:** `fix/flagged-players-service`

**Status:** complete 2026-11-17 (merged as PR #43, `ad464fc0`; archived 2026-11-17 because the merge left it unarchived)

## The problem

`GET /admin/players/flagged` (`api/app/routers/admin.py:48-139`) does all its
work in the router: it runs predictions, maps each prediction's quality flags
to players, joins ELO and rolling stats, and builds the rows. It does this with
function-local imports, one of them the private
`app.ingest.player_stats._slug`, which also drags the ingest module (and its
`requests` session) into the API process.

## The fix

- **`app/core/ta_slug.py` (new):** `TA_SLUG_OVERRIDES` and a public
  `ta_slug(name)`, moved verbatim from `ingest/player_stats.py`. The ingest
  imports both, so its slugs are unchanged.
- **`app/services/tennis/flagged_players.py` (new):** a pure
  `collect_flags(predictions, match_map)` (the flag-to-player loop), and
  `load_flagged_players(db, registry, today)` returning a list of
  `FlaggedPlayerRow` dataclasses. The logic is the router's, moved as is.
- **Router:** calls the service and maps rows to `FlaggedPlayer`. Module-level
  imports only.

Must not break: the response shape and values (same fields, same player
order, same sorted flags), and the ingest's TennisAbstract slugs.

## Build steps

- [x] **1. Move `_slug` to core.** Done when `ingest/player_stats.py` imports
  `ta_slug` from core and a test pins the override and plain cases.
- [x] **2. Move the endpoint body to the service.** Done when the router
  handler is a few lines, `collect_flags` and `load_flagged_players` have tests
  (fixed dates, stubbed repositories), a route test pins the response JSON,
  and the full API suite passes.

## Verify

- `cd api && python -m pytest` passes.
- The route test's golden JSON matches the old handler run on the same stubs
  (checked once on `master` before the move).

## Completion evidence

- `tests/test_admin_flagged_players.py` was written first against the old handler; its golden JSON is the old response for the stubbed inputs, and it passes unchanged after the move. It also covers `collect_flags` and `load_flagged_players` directly.
- `tests/test_ta_slug.py` covers the plain and override slug cases.
- Full API suite: 6460 passed locally; CI passed. The web app is untouched.
- Left as found: `admin.py` still imports the unused `get_latest_elo` and `get_rolling_stats` (already unused on `master`), and a comment in `schemas/admin.py` still says `_slug(player_name)`.

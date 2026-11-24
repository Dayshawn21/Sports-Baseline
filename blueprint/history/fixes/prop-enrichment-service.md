# Fix: Move tennis prop enrichment out of the props router

**Type:** Fix

**Fixes:** F-49

**Branch:** `fix/prop-enrichment-service`

**Status:** complete 2026-11-17 (merged as PR #42, `1de17587`; archived 2026-11-17 because the merge left it unarchived)

## The problem

`api/app/routers/props.py` (lines 72-575) holds the tennis prop projection and
enrichment engine: `_DEFAULT_EXPECTED`, `_SUPPORTED_PROJECTION_STATS`,
`_deciding_set_probability`, `_projection_inputs`, `_compute_opponent_allowed`,
`_enrich`, `enrich_with`, `_enrich_props` and the audit summary. Routers are
meant to be thin (coding standards, Backend architecture), yet:

- `app/ingest/prop_snapshots.py` imports `enrich_with` from the router, so an
  ingest job depends on a FastAPI module.
- `services/tennis/prop_sim.py` documents its contract against the router.
- About twelve tests import `_enrich` / `enrich_with` from the router.
- A comment at `props.py:552` defers the move "to item 17", which is done.

## The fix

Move the code verbatim into `app/services/tennis/prop_enrichment.py`. The
router keeps its four endpoints and calls `enrich_props` and `audit_summary`
from the service. The `enrich_props = _enrich_props` alias and its stale
comment go away: `enrich_props` is defined directly.

Must not break:

- The page, the reasons route, the audit route and the snapshot ingest keep
  calling the same function on the same inputs, so `props-v3` snapshot rows
  and the `props-v4` shadow are unchanged.
- No function body changes. Duplicated helpers (`_f`, `_clamp`) stay as they
  are here; F-72/F-73 dedupes them in a later spec.

## Build steps

- [x] **1. Create the service and thin the router.** New
  `services/tennis/prop_enrichment.py` holds lines 72-575 unchanged apart from
  the alias collapse and `_audit_summary` becoming `audit_summary`. The router
  imports from it. Re-point `ingest/prop_snapshots.py`, the `prop_sim.py`
  docstrings, `core/tennis_prop_check.py`'s comment, and test imports and
  monkeypatch targets.
  Done when: `grep "routers.props" app` finds only `main.py`, and the full API
  suite passes with no test body changed beyond import paths and patch
  targets.

## Verify

- `cd api && .venv\Scripts\python.exe -m pytest` passes.
- `git diff -M --stat` shows the moved block as a move, and a word diff of the
  moved functions against `master` shows no body changes.

## Completion evidence

- The projection and enrichment engine moved from `routers/props.py` to `services/tennis/prop_enrichment.py`; the router keeps its endpoints, and the snapshot ingest and tests import from the service.
- Test changes are import paths and monkeypatch targets only.
- Full API suite: 6441 passed locally; CI (Verify and Secret scan) passed.

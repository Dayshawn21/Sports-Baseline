# NHL stored-context API verification

Step 4 adds a required `context` object to NHL slate games and game detail.
It contains independent injury and goalie metadata and away/home observations.
All existing market, movement and line-only-prop fields retain their behavior.

## Selection contract

- Two batched SQL reads serve any number of selected games. An indexed,
  ordered LIMIT 1 lookup chooses each game's latest qualifying header before
  its entries are joined. No current-roster join or external fetch runs on reads.
- Each feed requires source ESPN, the correct kind/scope, fetch time strictly
  before puck drop and no later than the one captured response clock. Headers
  break timestamp ties by ID. Empty slates skip context reads entirely.
- Injuries use the global header, then filter entries to the game's teams.
  Unresolved players and source team disagreements remain visible.
- Goalies use the game's stored Eastern date and frozen game link. The latest
  batch's absent event never falls back to an older starter. Stored source
  teams/date/start must still match the game after a reschedule, with the same
  60-minute inclusive rule. Ambiguous events and incomplete pairs are unavailable.
- Freshness uses min(response clock, puck drop). Exactly six hours is fresh;
  more is stale. Historical pages retain pre-game observations. TBD starts
  return unavailable with null timestamps.
- An empty injury success retains its source time and empty team lists. A
  missing goalie event retains the selected batch's times and unavailable
  sides. Explicit not_reported competitor rows remain distinct from missing data.
- Undefined storage tables (PostgreSQL 42P01) produce a sanitized 503 asking
  for migration 0050. Other database failures propagate; none become empty success.

## Evidence

| Changed file | Purpose |
|---|---|
| `api/app/core/nhl_context_snapshots.py` | Immutable stored observations and pure freshness rule |
| `api/app/schemas/nhl_context.py` | Typed injury/goalie source and side response shapes |
| `api/app/schemas/nhl.py` | Required context inherited by slate games and detail |
| `api/app/repositories/nhl_context.py` | Batched latest-header selection and frozen row decoding |
| `api/app/services/nhl/context.py` | Team reports, reschedule validation and operational errors |
| `api/app/services/nhl/slate.py` | Attach context through one shared batch assembler |
| `api/app/services/nhl/game_detail.py` | Preserve the same fields and response clock in detail |
| `api/app/routers/nhl.py` | Capture one clock for date selection and context eligibility |
| `api/tests/test_nhl_context_reads.py` | Execute selection SQL on isolated read-only fixtures |
| `api/tests/test_nhl_context_service.py` | Temporal, missing-data, identity and parity cases |
| `api/tests/test_nhl_display_services.py` | Keep existing builders isolated from storage in legacy tests |
| `api/tests/test_nhl_display_schemas.py` | Include the new required field in existing contract fixtures |

The focused SQL/service/existing-display suite passed 102 tests. Selection
queries execute against isolated SQLite tables with query_only enabled for
reads, not a mocked SQL result. Pure service cases cover cutoff/freshness
boundaries, current vs historical clocks, independent feeds, frozen links,
source names, reschedules, missing events, unknown labels and slate/detail parity.
The fixture intentionally has no current sport_players table, so a read-time
roster join would fail. PostgreSQL-specific migration constraints are not
executed by these portable read tests.

The check skill then ran the actual FastAPI app through uvicorn on localhost
with isolated context tables and controlled schedule/market/prop fixtures.
External HTTP was blocked. Eight real HTTP requests passed; three nonempty
slate/detail reads issued exactly six context queries in total. Server shutdown
completed after the probe. No shared database was accessed or changed.

| Observed request | HTTP | Bytes | Local milliseconds |
|---|---:|---:|---:|
| October 24 slate | 200 | 1,367 | 65.21 |
| Game 1 detail | 200 | 1,316 | 22.19 |
| Game 1 line-only props | 200 | 440 | 15.09 |
| Empty date | 200 | 76 | 14.74 |
| Missing game | 404 | 35 | 13.33 |
| Malformed date | 422 | 193 | 12.24 |
| Game after newer empty batches | 200 | 1,031 | 19.57 |
| Simulated missing migration | 503 | 70 | 14.17 |

Observed checks:

- Slate game equals detail except for lineHistory, including identical context.
- Existing moneyline fields and the count/order of two prop offerings remain
  consistent between their responses.
- A newer empty injury batch clears the prior list while retaining a timestamp.
  A newer goalie batch without that event reports unavailable with its timestamp
  and never revives the earlier Confirmed starter.
- The controlled 42P01 failure yields the migration-required 503 without the
  underlying SQL/error message in the body. Empty, 404 and 422 cases remain explicit.

Local artifacts: `output/45f-step4-http-probe.py`, `output/45f-step4-http.json`
and the incremental `output/45f-step4.diff`. These are controlled API fixtures,
not live NHL reports or measurements of production latency/peak memory.

## Remaining operational acceptance

Migration 0050 is still unapplied by this work. Real stored-context reads,
snapshot writes, PostgreSQL execution of these reads, Actions and deployment
acceptance remain pending. This is the spec's isolated-fixture verification
path while the shared migration is pending. UI display belongs to Steps 5/6.

The exact root Verify command passed with the API venv on PATH:
`npm --prefix web run verify && cd api && python -m pytest`.
Typecheck, 878 web tests, production build and 4,462 API tests passed. Existing
Vite bundle-size and Starlette deprecation warnings remain. `git diff --check`
and separate whitespace checks for new/changed files passed.

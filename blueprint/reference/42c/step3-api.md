# 42c Step 3: shared injury API context

## Changes

| Area | Change |
|---|---|
| `core/nba_injuries.py` | Typed linked/snapshot records and pure pre-tip eligibility and six-hour freshness logic. |
| `repositories/nba_injuries.py` | One batched stored-snapshot query for all requested games, with NBA/team/game-type filters and NBA-only player linkage. |
| `services/nba/injuries.py` | Shared report assembly, team filtering, and matching index that excludes unlinked or report/current-team mismatches from prop tags. |
| `schemas/nba.py` | CamelCase injury/report contracts; explicit nullable line injury and unavailable defaults. |
| NBA board, modelled props, line-only props and game detail builders | Capture one aware response clock, load shared reports, and preserve original model and line fields. Reports load even when a game has no props. |
| Tests | Freshness/cutoff boundaries, empty replacement, identity/team handling, model-value preservation and board/game/both-prop-kind parity. Existing exact-key expectations include the additive fields. |

The snapshot query uses `LEFT JOIN LATERAL` to select the last successful
ESPN batch with `fetched_at < start_utc` and `fetched_at <= as_of`. It then joins
only the game's two teams and NBA player IDs. A successful snapshot with no
injuries for those teams still produces a report timestamp. No matching snapshot
or an unknown tip produces unavailable context. It does not query per player or
line, download ESPN, or invoke prediction/freezing code.

All alternate rungs inherit the same matching injury. A reported player with
no stored internal identity stays in the team report with `playerId: null`.
An entry whose nested athlete team differs from the outer report team keeps
both codes for later UI explanation, but never attaches to a prop.

## Running API proof

The `/check` path used a temporary Uvicorn server on `127.0.0.1:8042`, mounting
the real NBA FastAPI router with its real response schemas and service builders.
Schedule, line, history and market repository reads were controlled fixtures.
The real injury repository query executed against PostgreSQL through the
configured connection in `SET TRANSACTION READ ONLY` transactions. CTEs supplied
all five referenced relations (`sport_games`, `sport_teams`, `sport_players`,
`nba_injury_snapshots`, `nba_player_injuries`) as synthetic VALUES data. No
physical application table was read by those fixture SELECTs, and no tables or
stored records were created or changed. Sessions rolled back after reading.

Captured fixture clock: `2026-10-21T18:11:30+00:00`. The server was stopped after
verification. Complete saved response and assertion metadata:
[step3-api-responses.json](step3-api-responses.json).

Requests exercised:

- `GET /nba/props?date=2026-10-21`: seven fixture games, with one injury query
  carrying all seven IDs.
- For each game, `GET /nba/games/{id}`, `/props` and `/line-only-props`:
  21 successful HTTP responses with exact injury-report and line parity to the
  board, using the real route/service/schema path.
- `GET /nba/games/999`: existing 404 behavior.
- A direct injury query for fixture preseason and NFL games: neither returned
  injury snapshots.

| Fixture game | Expected and observed result |
|---|---|
| 7, upcoming | Fresh report; both alternate modelled rungs tagged Out, line-only player tagged Day-To-Day; player without props retained; traded-team player has no prop tag. |
| 8, already started | Same fresh pre-tip batch, not a newer/future batch. |
| 9, successful empty | Fresh timestamped report with an empty injury list; no old status retained. |
| 10, before first captured batch | Unavailable, null timestamp and empty list. |
| 11, unknown tip | Unavailable, null timestamp and empty list. |
| 12, old pre-tip batch | Stale report, retaining the original pre-tip entries. |
| 15, exactly-at-tip batch exists | Excludes that batch, serves the preceding stale empty report. |

A newer future ESPN batch and a newer non-ESPN batch were also present in the
fixture relations. The query ignored both. An NFL player shared an ESPN source
ID with an injury-only athlete; the athlete still serialized `playerId: null`,
proving that the player join remained NBA-scoped.

The seven-game fixture board was 10,970 response bytes. This is a functional
fixture observation, not a production payload, latency or Render memory result.

## Automated verification

From `api/`:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_nba_injury_context.py tests/test_nba_prop_board.py tests/test_nba_props.py tests/test_nba_game_api.py tests/test_nba_injuries.py tests/test_nba_injury_ingest.py -q
```

Result: 118 passed, including 24 new context tests. The parity test includes an
eligible assists projection with P(over), compares all original modelled/plain
line fields before and after injury enrichment, and checks every alternate rung.
Boundary tests cover exactly six hours, just over six hours, future snapshots,
equal/after-tip snapshots, missing tips, historical pre-tip freshness and naive
timestamp rejection. No component or route-integration tests were added to the
unit suite; HTTP evidence above covers the route path.

Full project Verify passed with the API venv active:
`npm --prefix web run verify && cd api && python -m pytest`. Web typecheck,
659 web tests, production build and 3,561 API tests passed. Existing
large-bundle and Starlette/AnyIO deprecation warnings remain.

## Remaining boundaries

- The HTTP/SQL proof uses controlled fixture relations. It does not establish
  real stored snapshot persistence, migration execution, production index plans,
  production payload size, hosted latency or memory acceptance.
- Migration `0048` remains unapplied to the shared database. The normal endpoints
  need it before reading real injury snapshots; a missing schema is not silently
  treated as an empty ESPN report.
- No shared-database writes, provider ingest writes, commit, deployment or workflow
  dispatch were performed in this step.
- UI tags, evidence presentation, team panels and scheduled refresh remain later
  steps. Step 3 remains unchecked until review approval.

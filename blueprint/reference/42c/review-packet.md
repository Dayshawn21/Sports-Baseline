# Feature 42c review packet

Implementation was completed on `feature/nba-injuries`. Steps 1-3 were
individually approved. The remaining implementation
was completed following the user's request to finish. After the owner reported
the missing-table error and asked to continue, migration 0048 was manually
applied and a real 80-entry snapshot stored and checked. Runner acceptance and
hosted deployment remain unverified. The owner invoked `$complete` in response
to the feature-commit/local-merge approval request on 2026-10-21. The spec is
archived as `blueprint/history/features/42c-nba-injuries.md`, 42c is checked off
and the current-feature stub is restored. The pre-existing overview edits are
excluded from the work commit. Push still requires separate approval.

## What changed

| Area | Result |
|---|---|
| `api/app/core/nba_injuries.py` | Strict ESPN parser, typed injury records, team discrepancy preservation and pure freshness/eligibility logic. |
| Migration `0048` and `repositories/nba_injuries.py` | Immutable complete/empty snapshot storage, exact-content retry checks, NBA-only linkage and one batched pre-tip read per date/game. |
| `ingest/nba_injuries.py` | Keyless bounded/retried fetch, read-only dry run, atomic write orchestration and safe error output. |
| NBA schemas and services | Shared report and line context across board, both prop kinds and game detail, preserving original model fields and ordering. |
| `web/src/types/nba.ts` and NBA grouping helpers | Typed nullable context retained through player/market grouping and all alternate rungs. |
| `NbaInjury.tsx`, prop table/evidence and related CSS | Neutral status/stale tags, source/detail/CT timestamps, honest missing/empty wording and unchanged reference values. Drawer payout cells also fit without colliding with the gap. |
| Game prop components | Selection uses current response rows instead of stale captured card objects; game changes reset selection. |
| `NbaGameInjuries.tsx` and `NbaGamePage.tsx` | Both teams' reports, including players without props, readable long details and explicit provider team-mismatch context. |
| `.github/workflows/nba-injuries.yml` | Independent two-hour October-June schedule at minute 43 UTC, manual dispatch, read-only repository permissions, serialized writes and a job timeout. |
| `AGENTS.md`, `docs/nba-injuries.md` | CLI, cadence, freshness, manual migration and operational acceptance boundaries. |
| Local ignored employer interview guide | Updated the NBA explanation with the implemented injury display, identity discrepancy example and remaining validation/deployment limits. Never staged. |

The pre-existing modification to `project-overview.md` was preserved. No
projection, probability fit, model version, freeze, grading, market filter,
game-type filter, row order or pick was changed by this feature.

## Automated and live verification

- Final documented Verify passed with the API venv active:
  `npm --prefix web run verify && cd api && python -m pytest`.
  Web typecheck, 673 web tests, production build and 3,561 API tests passed.
  The new coverage comprises 91 API tests and 14 web helper tests.
- Focused UI helper run: 49 passed. An approval-service usage failure initially
  prevented an elevated rerun; a sandbox/native-loader run passed, and the full
  documented Verify later passed through the normal approval path. No bypass
  of an approval decision was used.
- Live ESPN dry run: 80 entries, 28 report teams, two unresolved stored NBA
  identities and one report/current-athlete team discrepancy. No writes.
  See [step2-storage.md](step2-storage.md).
- Actual injury SELECT executed against PostgreSQL read-only CTE fixtures,
  with no physical injury-table reads or writes. Seven games' real local HTTP
  responses matched board/game/modelled/line-only context, including cutoff
  boundaries. See [step3-api.md](step3-api.md) and
  [saved API responses](step3-api-responses.json).
- Workflow YAML parsed with the existing PyYAML dependency; cron, dispatch,
  permission, concurrency and ingest command checked locally. No workflow run
  was dispatched.
- Impeccable detector: no findings on the changed injury components/styles.
  `git diff --check` passed. Existing large-bundle and Starlette/AnyIO
  deprecation warnings remain.

## Browser evidence

The real Vite app on port 3001 ran with controlled API fixtures from Step 3.
These are synthetic injury scenarios, not a claim about current players or
hosted data. The fixture routes were removed and the QA tab cleared afterward;
the pre-existing development server was left running.

| Claim | Evidence |
|---|---|
| Neutral status rows; original ordering and reference values | `step4-board-rows-{1440,1000,390}.png` |
| Out and Day-To-Day in both drawer kinds, board and game | `step4-board-{out,daytoday}-drawer-{1440,1000,390}.png`, `step4-game-{out,daytoday}-drawer-{1440,1000,390}.png` |
| Payout/gap columns fit in the final desktop drawer | [Final drawer](step4-rungs-confirm-1440.png) |
| Both teams, injury-only player, provider mismatch explanation | `step5-game-teams-{1440,1000,390}.png` |
| Fresh empty, unavailable and stale team reports | `step5-game-state-{9,10,12}-390.png` |
| Long prose and an unbroken 180-character detail wrap on phone | [Team list](step5-long-detail-390.png), [drawer](step4-long-detail-drawer-390.png) |

Keyboard Enter opens a board drawer, Escape closes it and restores the opener's
focus. All three tested widths had no horizontal page/tag overflow. Injury tags
use the existing secondary text token at 11px. No new API request occurred on
board market changes or board/game drawer selection. The completed fixture
checks recorded no page errors. See [browser-checks.json](browser-checks.json).

Initial drawer captures occurred before their slide animation settled. Final
board/game drawer captures were replaced after waiting for the visible position,
with animations disabled for capture. `step4-rungs-confirm-1440.png` is the final
column-layout confirmation; earlier captures preserve the preceding state.

## Local payload/timing observation

The controlled seven-game, 16-raw-line response was 10,970 bytes; removing the
new injury/report fields produced 5,348 bytes, an addition of 5,622 bytes.
Pure report assembly averaged 0.0392 ms for those seven games over 1,000
iterations, excluding I/O and existing projection work. The board made one
injury query for all seven games. These are small-fixture observations only,
not a production payload, latency, index-plan or Render memory benchmark.
See [step6-local-observations.json](step6-local-observations.json).

## How to try and what remains

1. For a safe current CLI check, run from `api/`:
   `.venv\Scripts\python.exe -m app.ingest.nba_injuries --dry-run`.
2. The configured database is now at migration `0048`, with the first real
   80-entry snapshot stored. See [live acceptance](live-acceptance.json) and
   [operations](../../../docs/nba-injuries.md). Other databases still need their
   own deliberate migration and initial ingest.
3. Once data is prepared, run the documented API and web dev commands, open
   `/#/nba/board` or `/#/nba/game/<served-game-id>`, open a tagged player and
   compare the same line and injury across both pages. The game shows both
   teams' lists, and source/fetch times remain readable in CT.
4. Missing tip/no qualifying batch must show unavailable; a successful empty
   report must say no injuries reported by ESPN; a stale report must retain its
   timestamp and stale label. No state means confirmed healthy.

First GitHub workflow registration and runner execution, hosted deployment and
Render memory remain unverified. The shared migration and first snapshot write
were performed during the follow-up repair; no commit, merge, push, dispatch or
deploy was performed. The findings ledger has only existing unverified P2/P3 follow-ups
(F-09, F-12), with no open/fixed P0/P1 blocker. `/complete` is the next workflow
step for final review, archive/bookkeeping and a work-level commit; merge and
push still need explicit approval.

## Real missing-table repair and acceptance

The reported `UndefinedTable: nba_injury_snapshots` came from a confirmed
0047 database with both new tables absent. Alembic `upgrade 0048` created only
the reviewed injury tables, then the normal ingest stored snapshot 1 with
80 entries at `2026-10-21T19:52:03.805522+00:00`. A read-only check confirmed
revision 0048, one snapshot header and 80 entry rows.

The real local board returned HTTP 200 with 11 games, 8,097 raw lines and 332
tagged lines; every served report was fresh. Its 5,129,575-byte response took
1.492 seconds in this one local request. Game IDs 21316 and 21317 each returned
200 for detail, modelled props and line-only props, with exact board/game line
and injury-report parity. This establishes current local serving from real
persisted data, not hosted memory or latency guarantees. No failure-injection
or rollback experiment was performed on the shared database.

Invariants review: clean. Sport/team/player filters remain NBA-scoped; served
game types and existing prop filters are preserved; core remains pure; no odds
provider reader, model version, fit, holdout, freeze or grading rule changed.
New injury UI uses neutral theme colors and text at least 11px. The request
addition is one bounded stored-context query; production memory acceptance is
still unverified. The pre-existing overview edits remain separate from the
feature's completion changes.

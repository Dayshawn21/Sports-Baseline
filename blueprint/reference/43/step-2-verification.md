# Feature 43, Step 2 review evidence

Implemented and verified locally on 2026-10-22 on
`feature/nfl-matchup-usage-context`. Step 1 was approved in chat; Step 2 awaits
review. Nothing committed, pushed or deployed.

## Changed files

| File | Change |
|---|---|
| `api/app/repositories/nfl.py` | Typed context transfers plus four read functions. SQL aggregates position totals per defense game and team usage denominators; batches roster player histories. |
| `api/app/services/nfl/matchup_context.py` | Shares the same pre-week calculation path between game context and week notes; orders players by team, name, ID. |
| `api/app/services/nfl/game_notes.py` | Attaches matchup context after existing notes loads, outside the slate/model path. |
| `api/app/schemas/nfl.py` | Adds nullable matchupContext to game notes, using Step 1's typed response contracts. |
| `api/app/routers/nfl.py` | Adds GET /nfl/games/{game_id}/context with 404 for an unknown/non-NFL/non-REG target. |
| `api/tests/test_nfl_matchup_context_reads.py` | 28 isolated SQL and API fixtures, executing the actual queries against in-memory SQLite. No shared fixture writes. |
| `blueprint/context/current-feature.md` | Records Step 1 approval, Step 2 implementation and verification, leaving Step 2 unchecked for review. |
| `blueprint/reference/43/check-stored-context.py` | Reproducible, read-only Postgres smoke check; stores only aggregate evidence in step-2-stored-read.json. |

`step-2.diff` shows only this step, relative to the approved Step 1 working
state. It excludes the pre-existing build-plan/overview changes and Step 1's
code, schemas, tests and evidence.

## Contracts proved

- Normal game-context request: four SQL reads, including histories for 104
  roster players in the scaling fixture. No prop or odds reads. Unknown
  targets stop after one query; an empty roster or unknown kickoff skips
  unnecessary history work.
- Week matchup extension: two SQL reads for the whole week, no player-history
  fetches. Every target re-applies its own kickoff cutoff to the shared league
  rows, including a controlled postponed pre-week game between target kickoffs.
- Both endpoints serialize identical matchupContext. Existing notes fields
  match the original pure notes assembler when the new field is excluded.
  Slate source, JSON schema, stored snapshots, models, projections, probability
  versions and frozen/grading readers have no changes.
- All game, team and player joins are NFL-scoped. Only completed REG games
  from the same season, strictly before the target week and kickoff, count.
  Fixtures cover wrong sports/teams/players, unknown kickoff, current/future
  weeks, prior seasons, PRE/POST and uncompleted games.
- Membership requires a unique roster row in the exact target season/week.
  No latest-team or previous-week fallback. CUT, RET, missing and ambiguous
  memberships do not assign a player; only QB/RB/WR/TE are returned. Historical
  team identity is from the stat/snap game, preserving trades.
- Known zero-snap DNPs are excluded even if a zero stat row exists. Positive
  snap-only games stay in the played-game window with unavailable stat metrics.
- A position aggregate requires at least one participant and coverage of that
  metric for every known participant in the position. Absent groups stay null;
  known observed zero remains zero. A known participant with unknown position
  makes position sums unavailable. Team denominators include recorded QB carries
  and all other teammate positions; missing stats on a known participant or a
  null metric invalidate only the affected denominator. No inferred zeros.

The completeness checks use known stored participation, not a claim that a
provider loaded every actual player. Position labels are the stored player
position; the existing weekly stat schema has no historical position snapshot.
Both are source limits, not new inference rules.

## Automated verification

Documented Verify gate run as PowerShell halves, using the API venv:

1. `npm.cmd --prefix web run verify`: typecheck, 706 tests and production build
   passed. npm.cmd avoids Windows' npm.ps1 execution-policy restriction. The
   web gate used approved filesystem access for esbuild.
2. From `api/`, `.venv\Scripts\python.exe -m pytest -q`: all 3,669 tests passed,
   including 28 new reads/endpoint cases and 27 Step 1 calculation cases.
3. `git diff --check`: passed.

Existing warnings: the web bundle exceeds Vite's size advisory, and Starlette
reports an anyio alias deprecation. No check was skipped or suppressed.

## Stored Postgres smoke check

The script enforces `SET TRANSACTION READ ONLY`, a 15-second per-statement
timeout and session rollback. It reads 2026 Week 7 only, with no provider,
model, frozen-record, grading or historical holdout query.

Final recorded sample in `step-2-stored-read.json`:

- Game ID 94: 39 roster players, 28 with season target shares, all 16 matchup
  allowed measures available across the two teams.
- Game response: 59,925 bytes; about 0.406 seconds on the final run. The earlier
  first connection/sample took about 1.847 seconds. These are local samples,
  not a hosted latency guarantee or a full load/memory test.
- Shared week matchup batch: 14 games, about 0.146 seconds. Game and week
  calculations match exactly for the sampled game.

Windows reproduction from `api/`:

```powershell
$env:PYTHONPATH = (Get-Location).Path
.venv\Scripts\python.exe ..\blueprint\reference\43\check-stored-context.py
```

The managed shell needed approved network access to reach Postgres. Windows
uses the selector event-loop policy required by psycopg. No shared writes were
performed, and no credentials or player-level data were saved in evidence.

## How to try and remaining work

With the local API running, request
`http://127.0.0.1:8000/nfl/games/94/context` and compare matchupContext with
game 94 in `/nfl/game-notes?season=2026&week=7`. Swagger lists the new route.
The endpoint uses the stored game's metadata; no season/week guess is required
from the client. Unknown games return 404.

UI work starts in Step 3. Drawer behavior, browser evidence, broader current-data
sampling and the 512 MB allocation/resource assessment remain in Steps 4-5.
The local employer guide update remains in Step 5's documented final pass;
this step makes no shipped/deployed feature claim.

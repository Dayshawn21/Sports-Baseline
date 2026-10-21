# 42d final verification

Date: 2026-10-21. Branch: `feature/nba-team-stats`.
Local implementation and verification only. No deployment or shared writes.

## Real database and memory observations

Used a read-only transaction with a 20-second statement timeout. The historical
sample is the development season (2024 start year), before 2025-04-13; no
backtest, validation scoring or adoption report was run.

| Measurement | Observation |
|---|---|
| Grouped prior REG games | 1,216 |
| Grouped team/opponent/DNP sides | 4,541 |
| EXPLAIN ANALYZE planning / execution | 2.156 ms / 38.285 ms |
| Grouped repository read plus pure math | 0.384 seconds |
| Peak traced Python allocation during read/math | 4.27 MiB |
| Historical game | 25794, DEN at HOU |
| Sample HOU points coverage | 81 usable of 81 completed prior games |
| Opening-night game | 21318, 2026-10-20 |
| Actual selected-game modelled / line-only lines | 1,150 / 13 |
| Actual date-wide board | 3 games, 1,868,118 serialized JSON bytes |
| Four response assemblies together | 1.639 seconds |

The selected game's full modelled and line-only line arrays and all four
`teamStats` objects matched. The opening-night context correctly has no prior
regular-season observations and does not borrow the previous season's data.

These are local warm-database observations, not hosted latency, process RSS or
a Render capacity guarantee. Traced allocations exclude imported libraries and
native memory. SQL returns grouped sides, not the raw season's player rows.

Raw measurements: `step6-data-results.json`. The database check script is
`step6-real-data.py`. Run from `api/`, with that directory on `PYTHONPATH`,
using its venv. It uses the configured database through app settings, never
prints credentials, performs no schema changes and ends with rollback.

## Running browser

Used the actual Vite app and isolated headless Edge, with captured real API
responses served by the browser harness. Player fixtures retain all rungs for
one assists player and one line-only player, rather than storing the complete
board. The direct database parity check above compared the complete arrays.

At both 1440px and 390px, all 12 final checks passed:

- Historical team table shows the stored rates and counts.
- Opening-night game shows two explicit no-history team tables.
- Board and game assists evidence show identical opponent context.
- A delayed game response shows loading, then the table after success.
- Controlled 503 responses reach the existing error panel; Retry recovers to
  the real stored game response and table.
- No page runtime errors occurred. Expected 503 requests were deliberate.

Screenshots:

- [Historical desktop](step6-stored-historical-1440.png)
- [Historical phone](step6-stored-historical-390.png)
- [Opening-night phone](step6-stored-game-390.png)
- [Stored board drawer](step6-stored-board-drawer-390.png)
- [Stored game drawer](step6-stored-game-drawer-390.png)
- [Controlled error](step6-error-390.png)

Step 4's eight fixture cases also cover missing/partial/zero values. Step 5's
48 cases cover all five supported measures, unsupported markets, unknown teams,
parity, row order, injury evidence and keyboard focus. Their reports and images
remain alongside this file. The final harness is `step6-browser.cjs`; use an
existing `playwright-core` or set `PLAYWRIGHT_MODULE` to its module directory.

## Source invariants and handoff boundaries

Invariants review: clean for 42d. Every new shared-table join is literally NBA
scoped. Display history deliberately uses completed REG only, as specified.
Odds-provider filters, modelled-market filters, projection/freezing/grading
paths, fits, versions and rules are unchanged. Core has no I/O. New signal
content stays gray and the measured new table text is at least 11px. No schema,
provider, workflow, secret or public write route was added.

The ledger has no open/fixed P0/P1 findings. Existing F-09 (P3 unverified) and
F-12 (P2 unverified) remain outside scope. The local ignored employer guide was
updated with the implemented behavior and measured example, retaining pending
local owner-approval and unverified-deployment boundaries. It was not staged.

The existing dirty `project-overview.md` was preserved. No commits, merges,
pushes, migrations or deployments were performed. The owner approved Step 6
with Continue on 2026-10-21; all implementation steps are approved.

## Final automated gate

`npm --prefix web run verify && cd api && python -m pytest`, with the API venv
active: 700 web tests, production build and 3,611 API tests passed. Existing
Vite large-bundle and Starlette/AnyIO deprecation warnings remain.
`git diff --check` also passed. No source repair was needed in Step 6.

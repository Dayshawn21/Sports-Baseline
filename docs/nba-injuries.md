# NBA injury display and refresh

Feature 42c adds ESPN injury context to NBA prop rows, both evidence drawers and
the game page's two team lists. It is display only: injury status never changes
a projection, P(over), gap, model version, row order, pick, freeze or grade.

## Run locally

From `api/`, with the API venv active:

```powershell
python -m app.ingest.nba_injuries --dry-run
```

Dry run fetches the keyless ESPN feed, validates the complete response and reads
stored NBA athlete IDs to report unresolved identities. It writes nothing and
does not need the injury tables. A player without a stored NBA identity is
reported as unresolved, but their injury will still be retained on real writes.

After migration `0048` has been deliberately applied:

```powershell
python -m app.ingest.nba_injuries
```

The default command writes one immutable snapshot with all parsed injuries in
one transaction. Successful empty feeds get a zero-entry snapshot marker.
Malformed feeds and failed writes leave the last successful batch intact. HTTP
reads have a 30-second per-operation timeout and up to three attempts for
transport failures, HTTP 429 or 5xx. Other HTTP/parser errors fail the command.

## Migration boundary

`0048_nba_injuries.py` adds `nba_injury_snapshots` and `nba_player_injuries` after
revision `0047`. The normal injury-reading API routes and default ingest writes
require these tables. A missing migration is not silently treated as an empty
report. Apply migrations manually, one command at a time, with the reviewed
Alembic configuration described in AGENTS.md; do not apply or downgrade against
the shared database as part of a smoke test.

Migration `0048` was manually applied to the configured shared database on
2026-10-21 after the owner reported the missing-table error. One real ESPN
snapshot containing 80 injuries was stored successfully, and local board/game
API responses were checked against those persisted rows. No existing table
data was modified. Earlier read-only CTE fixtures also exercised snapshot
selection boundaries; rollback/concurrency failure cases remain unit/fixture
checks, not destructive shared-database experiments.

## Scheduled operation

`.github/workflows/nba-injuries.yml` runs at minute 43 of every even UTC hour,
October through June (`43 */2 * 1-6,10-12 *`), and supports manual dispatch.
The UTC run times translate to:

- During Central daylight time: 7:43 PM, 9:43 PM, 11:43 PM, then every two
  hours through 5:43 PM CT.
- During Central standard time: 6:43 PM, 8:43 PM, 10:43 PM, then every two
  hours through 4:43 PM CT.

The workflow needs only `DATABASE_URL`, uses read-only repository permissions
and serializes runs with its own concurrency group. It does not depend on
PrizePicks succeeding and spends no paid odds-provider credits. The job has a
ten-minute timeout. Apply the migration before enabling real writes. The new
workflow's registration and first successful runner execution remain pending
publication and deliberate acceptance checks; no dispatch was run during
implementation. Public repository schedules may pause after 60 quiet days.

GitHub schedules are best effort, including delayed starts and missed refreshes.
The two-hour cadence cannot guarantee the last scratch before every tip.

## Snapshot selection and display

- Select the latest successful ESPN snapshot fetched strictly before tip and
  no later than the response's captured clock. Started/final games keep pre-tip
  context instead of showing today's injuries as historical facts.
- A report more than six hours old at `min(response time, tip)` is stale.
  Exactly six hours remains fresh. Stale statuses remain visible and labeled.
- An unknown tip or no qualifying snapshot means unavailable context, with a
  null timestamp. A successful empty report means no injuries reported by ESPN,
  not confirmed availability. Do not infer healthy from an absent athlete.
- Fetch time and ESPN entry update time are displayed separately in dated CT.
  Expected return values are ESPN context, not a promised return date.
- ESPN IDs alone link players. The report's team and nested athlete team are
  both retained. A disagreement is shown on the team list and prevents a prop
  tag; no name guess or silent reassignment is allowed.
- Team lists include athletes with no prop and no stored internal player ID.
  Board rows remain in tip/name order and every alternate rung is retained.

All API reads use stored context, with one batched injury query for a board
date or a game. Neither page fetches ESPN or creates snapshots on request.

## Acceptance evidence

See `blueprint/reference/42c/` for the live dry run, migration SQL, read-only
PostgreSQL fixture checks, HTTP parity and browser screenshots. Browser injury
cases use controlled API fixtures; they do not prove hosted data or deployment.
The API's Render memory/latency acceptance and first scheduled runner acceptance
remain separate operational checks. The real local acceptance summary is in
`blueprint/reference/42c/live-acceptance.json`.

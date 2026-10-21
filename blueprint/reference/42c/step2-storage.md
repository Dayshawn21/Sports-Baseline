# 42c Step 2: snapshot storage and ingest

## Changes

- Migration `0048`, following `0047`, adds `nba_injury_snapshots` and
  `nba_player_injuries`. It changes no existing model, prediction or stat table.
  The unique fetch-time index supports snapshot selection; the entry primary
  key indexes snapshot/team/athlete lookup. Source timestamps and both provider
  team identities are preserved.
- The repository appends complete batches with parameterized bulk inserts.
  Successful empty feeds receive a header with zero entries. Missing internal
  player IDs never discard injuries; the only roster lookup is NBA-scoped.
- The ingest commits the header and entries together, rolls back on failure,
  and never updates or deletes an old snapshot. Reusing the same fetch timestamp
  compares stored header metadata and every entry, independent of row order;
  differing contents raise an error instead of overwriting the old batch.
- HTTP reads have a 30-second per-operation timeout and at most three attempts
  for transport errors, 429 or 5xx responses, with short exponential waits.
  Other HTTP errors, malformed JSON and invalid feeds fail without writing a
  snapshot. The CLI reports errors without printing database connection details.

## Live dry run

Executed from `api/`, with approved network access:

```powershell
.venv\Scripts\python.exe -m app.ingest.nba_injuries --dry-run
```

Observed on 2026-10-21, fetch time `2026-10-21T18:02:03.330419+00:00`:

```text
ESPN NBA injuries dry run: 28 teams with reports, 80 entries, 2 unresolved athlete IDs, 1 team mismatches; fetched 2026-10-21T18:02:03.330419+00:00
```

This exercised the real ESPN fetch/parser and an NBA-player-ID SELECT against
the configured database. Dry run calls neither snapshot insertion nor commit;
the session closes its read transaction. No migration or shared-database write
was run. The team count denotes teams with injury entries, not every league
team or empty group. An unresolved ID denotes a missing stored player identity,
not a discarded report entry.

## Verification and limits

- Focused command from `api/`:
  `.venv\Scripts\python.exe -m pytest tests/test_nba_injuries.py tests/test_nba_injury_ingest.py -q`.
  Result: 67 passed, including 18 new storage/ingest tests.
- Tests cover NBA-only linkage, retaining unresolved entries, dry-run write
  exclusion, an empty marker, rollback on an entry-write failure, exact retry
  reuse, conflicting retry rejection, duplicate/naive-time rejection, HTTP
  transient retries, retry exhaustion and permanent/malformed feed failure.
- Transaction tests use mocked sessions and injected failures. They establish
  which writes/commit/rollback the code requests, not actual PostgreSQL atomicity
  or concurrent visibility.
- Alembic's ScriptDirectory reports sole head `0048`. Both new tables compile
  through Alembic's PostgreSQL offline dialect; the SQL is in
  [step2-migration.sql](step2-migration.sql). No migration environment or
  application database connection is used to produce that file.
- No local PostgreSQL executable or Docker command was found on PATH, and the
  standard PostgreSQL installation directory is absent. Migration execution,
  real persisted-batch reads and concurrent/repeated-batch behavior against an
  isolated PostgreSQL server remain unverified. No substitute database result
  is presented as PostgreSQL evidence.
- Full project Verify passed: with the API venv active,
  `npm --prefix web run verify && cd api && python -m pytest` completed web
  typecheck, 659 web tests, production build and 3,537 API tests. Existing
  large-bundle and Starlette/AnyIO deprecation warnings remain.

The default CLI writes snapshots once the migration has been deliberately
applied. Use `--dry-run` for review. The API, UI and scheduled workflow changes
remain later steps; runner acceptance and deployment remain unverified.

# NHL context storage verification

Step 2 adds migration `0050_nhl_context.py` after `0049`, plus repository writes.
No shared database connection, migration, snapshot write or downgrade was run.
Existing request paths still do not read these new tables.

## Review artifacts

- `0050-upgrade.sql`: SQL produced by Alembic's offline `0049:0050` upgrade
  with a password-free local dummy connection URL. Trailing whitespace from
  Alembic's renderer is removed. This is for review; it has not been executed.
- Local `output/45f-step2.diff`: additions for this step, excluding earlier
  approved parsing/matching work and the existing overview edit.

The upgrade creates three NHL-only tables and their indexes. No existing
application table is altered. Alembic's emitted version-row update advances
0049 to 0050 only when the migration is deliberately applied. The current code
head is 0050; this does not establish the shared database's current revision.

## Write contract

- Batch identity is source/kind/scope date/fetch time. PostgreSQL 15's NULLS
  NOT DISTINCT makes the global injury scope participate in uniqueness.
- The header and all entries are written in a savepoint. The repository never
  commits; the later ingest command owns the outer commit per component.
- A matching retry returns the stored ID after comparing metadata, all source
  fields and frozen links without relying on entry order. A conflicting retry
  raises an error; no existing observation is updated or deleted.
- Frozen player links are validated against NHL players. Goalie player links
  additionally require position G; game links require NHL REG/PST. Share locks
  keep validated FK rows stable during the write transaction.
- Explicit link maps must cover source entries/events exactly. Unresolved
  source names are retained. Empty success stores a zero-entry header.
- Constraints check scope/kind, status, link-reason/null relationships, goalie
  announcement fields, valid times and team orientation. Foreign keys use
  restrictive deletion behavior rather than cascading away experiment evidence.

## Evidence and limits

The 43 focused tests pass in `test_nhl_context_repository.py` and
`test_migration_0050.py`. They cover empty/nonempty writes and retries,
changed status/source time/count/rows/frozen links, partial or duplicate source
identities, naive timestamps, unresolved names, NHL-scoped FK queries,
unknown-start vetoes and failures exiting the savepoint through rollback.

Repository tests use recording AsyncSession/savepoint doubles, not a database.
The migration test compiles real PostgreSQL DDL through Alembic offline
operations and checks upgrade/downgrade ordering without executing either.
These tests establish application transaction handling and emitted SQL; actual
PostgreSQL constraint/rollback and shared-database acceptance remain pending.
No local PostgreSQL server or container executable was available for an
isolated database run. Do not substitute destructive shared-database tests.

To repeat the focused check from `api/`:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_nhl_context_repository.py tests/test_migration_0050.py -q
```

The exact root Verify command passed with the API venv on PATH:
`npm --prefix web run verify && cd api && python -m pytest`.
Web typecheck, 878 web tests, production build and 4,379 API tests passed.
Existing Vite bundle-size and Starlette deprecation warnings remain.
`git diff --check` and separate whitespace checks for the new files passed.

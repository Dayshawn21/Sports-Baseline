# NHL context ingest and schedule verification

Step 3 adds `python -m app.ingest.nhl_context [--dry-run] [--date YYYY-MM-DD]`
and the independent `nhl-context.yml` workflow. Migration 0050 has not been
applied by this work, and no real snapshot writes or workflow dispatches ran.

## Behavior

- Injuries always use the current feed. Default goalie reads cover Eastern
  today and tomorrow; `--date` selects exactly one goalie date and does not
  turn the injury feed into historical data.
- Each component receives a fetch timestamp after its HTTP body is received.
  Its parsing, candidate resolution, optional snapshot write and commit happen
  independently. A failed component does not undo earlier successful commits.
  The process reports all components and exits 1 if any failed.
- Dry runs set each transaction READ ONLY, with a 15-second statement timeout,
  before resolving against existing NHL roster/schedule tables. They never
  read new snapshot tables, store snapshots or commit. Session close ends the
  read transaction. There is no migration prerequisite for dry runs.
- Existing NHL player candidates are reused. Game candidates include the
  requested date and adjacent dates so matching near Eastern midnight still
  applies the exact 60-minute rule. All game/player SQL remains NHL scoped.
- HTTP operations time out after 30 seconds, with an additional 32-second
  request wall limit. Fetch/retries have a 90-second component budget; DB
  processing has 30 seconds. Transport/timeout, 429 and 5xx failures allow at
  most three attempts. Permanent HTTP and parser failures do not retry.
- Retry-After accepts seconds or aware HTTP dates. A pending wait up to 30
  seconds also applies before the next component's request. A longer or invalid
  header blocks further ESPN calls for that run; remaining components report
  provider_cooldown instead of calling during the requested cooldown.
- Console summaries contain counts, source athlete/event IDs and safe failure
  categories, never provider bodies, raw exceptions or database URLs.

## Live read-only acceptance

On October 24, 2026, the real CLI `--dry-run` exited 0 against ESPN and the
configured database using enforced read-only transactions. No context tables
were accessed and no snapshots were stored. The recorded source timestamps
below are HTTP fetch-completion times, not ESPN entry-update times.

| Component | Fetched UTC | Entries | Linked entries | Unresolved athlete IDs | Unmatched events |
|---|---|---:|---:|---:|---:|
| Current injuries | 2026-10-24 19:23:33 | 131 | 108 | 23 | 0 |
| October 24 goalies | 2026-10-24 19:23:36 | 24 | 23 | 1 | 0 |
| October 25 goalies | 2026-10-24 19:23:36 | 10 | 10 | 0 | 0 |

All three components reported zero nested team disagreements. These are dated
coverage observations, not current inventory counts or a claim that unresolved
players are absent/healthy. Counts establish real parser and matching acceptance,
not snapshot writes, API display, predictive value or deployment.

## Schedule and operational boundary

The local workflow runs at minute 17 of every UTC hour, September-June,
supports manual dispatch, uses contents: read, serializes runs without canceling
an active run, and has a ten-minute timeout. It needs only DATABASE_URL.
It spends no odds-provider or PrizePicks quota and depends on neither workflow.

Apply migration 0050 deliberately before enabling real writes. The workflow
does not apply migrations. GitHub registration, first runner acceptance and
deployment remain pending publication and deliberate verification. The hourly
cadence is best effort and cannot guarantee the last scratch/goalie change.

To repeat the read-only command from `api/`:

```powershell
.venv\Scripts\python.exe -m app.ingest.nhl_context --dry-run
```

Focused tests use mock HTTP transports, typed roster/game candidates and
session/store doubles. They verify independent commits/rollbacks, read-only
dry-run routing, safe error reporting, CLI nonzero exit, exact date requests,
bounded retries, fetch deadlines and cooldown behavior. They do not execute
real PostgreSQL snapshot writes or claim runner acceptance.

## Final automated checks

- Focused ingest/repository suite: 74 passed.
- Exact root command with the API venv on PATH:
  `npm --prefix web run verify && cd api && python -m pytest`.
  Typecheck, 878 web tests, production build and 4,411 API tests passed.
- The workflow parsed with the installed YAML reader. Schedule, permissions,
  concurrency, environment, timeout and invocation were inspected locally.
- `git diff --check` and new-file whitespace checks passed. Existing Vite
  bundle-size and Starlette deprecation warnings remain.

Incremental review diff since Step 2: local `output/45f-step3.diff`.

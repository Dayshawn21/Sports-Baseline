# NHL injuries and starting goalies

Feature 45f adds stored ESPN context to the NHL slate and game Matchup tab.
It is display only: no projections, probabilities, picks, ranking, grading or
model versions change. Expected and Confirmed describe ESPN's report, not a
recommendation or guarantee that a goalie will start.

## Acceptance status

Implemented and verified locally on October 24, 2026. Parser/linking tests,
offline migration SQL, persistence doubles, isolated SQL/HTTP fixtures and
desktop/phone browser checks pass. A real read-only ingest dry run succeeded.
Migration 0050 was applied to the shared database on October 24, 2026, and
Alembic reports `0050 (head)`. The initial real ingest stored three batches at
20:41:52-20:41:55 UTC: 131 injury entries (108 player links), 24 goalie entries
for October 24 and 10 for October 25 (33 player links, all 34 game links).
Read-only PostgreSQL queries confirmed those counts. The local API returned
HTTP 200 with 12 slate games and HTTP 200 for game 57033; its context showed
the stored fetch times, fresh injuries and two confirmed goalies. Unresolved
players retain source names. This is initial local acceptance against shared
storage; first workflow execution and hosted API/UI acceptance remain unverified.

See `blueprint/reference/45f/` for evidence by implementation step. Local
screenshots, HTTP measurements and incremental diffs are under ignored `output/`.

## Commands and activation order

Run from `api/` using the API venv:

```powershell
python -m app.ingest.nhl_context --dry-run
python -m app.ingest.nhl_context --dry-run --date 2026-10-24
```

Dry run fetches ESPN and reads existing NHL player/game candidates in read-only
transactions with a 15-second statement timeout. It does not access the new
context tables, insert, update or commit. It works before migration 0050.

Default goalie scope is Eastern today and tomorrow. `--date YYYY-MM-DD`
selects one goalie scoreboard, but injuries are always current. The date is
not permission to reconstruct historical injuries or pre-game knowledge.

For deliberate operational activation, in order:

1. Review `blueprint/reference/45f/0050-upgrade.sql` and migration 0050. Apply
   the shared migration manually, one command at a time, using the local
   Alembic config described in `AGENTS.md`:
   `python -m alembic -c <local-config> upgrade 0050`.
2. Run `python -m app.ingest.nhl_context` for an initial real write. Omitting
   `--dry-run` writes and independently commits each successful feed/date.
3. Read back batch/entry counts and sampled frozen player/game links, then
   check nonempty slate and detail responses against the stored batches.
   Keep exact fetch times and acceptance evidence. A post-start write cannot
   supply context to a game that has already started.
4. After separately approved publication, verify the workflow registers and
   its first actual run succeeds. Check hosted API/UI acceptance separately.

Activation steps 1-3 were executed on October 24, 2026, as recorded above.
Step 4 remains unverified. There is no automatic migration step and no shared
downgrade test.

## Refresh and failure handling

`.github/workflows/nhl-context.yml` proposes `17 * * 1-6,9-12 *`: every hour
at minute 17 UTC, September-June, plus manual dispatch. It has read-only
repository permissions, a non-canceling concurrency group and a ten-minute job
timeout. Only `DATABASE_URL` is needed. It spends no odds credits and makes no
PrizePicks request. This job is independent of schedule, odds and prop jobs.

Each HTTP operation has a 30-second timeout and a 32-second wall bound; a
component's complete fetch/retry budget is 90 seconds and DB work is bounded
to 30 seconds. At most three attempts handle transport/timeouts, 429 and 5xx.
Retry-After seconds or aware HTTP dates are honored up to a 30-second wait,
including across components. A malformed or longer header blocks further ESPN
requests for that run. Other HTTP/parser errors fail the component directly.

The command attempts independent components after a failure, keeps successful
commits and exits nonzero if any failed. Safe summaries include entry/link
counts, unresolved source IDs and unmatched events, never raw errors or secrets.
A failed feed writes no success marker; prior successful reports age stale.
Hourly best-effort refresh can miss a late scratch or goalie change.

## Source and identity rules

Injuries come from ESPN's NHL injuries endpoint; goalies come from its dated
scoreboard, requested with `dates=YYYYMMDD&limit=100`. Only the
`probableStartingGoalie` report is used. No season leader or post-game starter
flag is substituted. Unknown status remains unknown; only source Confirmed is
Confirmed. A valid competitor without a probable is explicitly Not reported.

Malformed/conflicting feeds fail. Explicit preseason events are excluded;
unknown season types fail. The scoreboard has no verified root date/count, so
each event's Eastern date is checked and a response reaching 100 events fails
as potentially truncated. Silent upstream omissions cannot be detected.

Explicit ESPN aliases map to canonical NHL teams, including TB/TBL, LA/LAK,
NJ/NJD, SJ/SJS and UTAH/UTA. Players link only on unique normalized full name
and matching team. Goalies additionally require stored position G. No fuzzy,
initial-only or cross-sport fallback creates a match. Source/athlete team
disagreement vetoes linking. Unresolved source names remain visible and count
in their reported team's injuries; no placeholder player is created.

Events link only to a unique NHL REG/PST game with ordered away/home teams
and start within 60 minutes, inclusive. An unknown/invalid source start,
ambiguity or larger reschedule leaves the event unresolved. Source event/team
and athlete IDs remain distinct from internal IDs.

## Storage and read contract

Migration 0050 adds `nhl_context_snapshots`, `nhl_player_injuries` and
`nhl_goalie_observations`. Source names/statuses/timestamps and internal link
IDs/reasons are frozen together. Repository savepoints make a batch atomic;
the caller owns its outer commit. An exact retry of the same timestamp/content
returns the existing batch. Conflicting content fails without replacing rows.
There is no automatic cleanup, rewrite or read-time roster relink.

Both `/nhl/slate` and `/nhl/games/{id}` add camelCase `context.injuries` and
`context.goalies`, each with source, fetchedAt, sourceTimestamp, freshness and
away/home values. No new endpoint or per-row request is added. Two batched
context queries select the newest successful header independently per feed,
with `fetched_at < start_utc` and `fetched_at <= response_as_of`, timestamp ties
broken by ID. NHL/REG/PST and team sport filters apply. Reads do no provider
I/O or writes and do not load current player rows.

Goalies use the game's Eastern date and frozen event link. The latest header
is selected before seeking its event. A missing event, duplicate linked events
or invalidated team/start match yields Unavailable, retaining known batch
timestamps. It never revives an older named/Confirmed goalie. Not reported is
reserved for a valid event with no announcement. Missing start or no eligible
batch means Unavailable with null times.

Age is measured at `min(response_as_of, start_utc)`: exactly six hours is Fresh,
more than six hours is Stale. Historical pages retain eligible pre-game reports;
later downloads cannot backfill them. The browser can age valid reports further
and preserves the server's Unavailable decisions. Stale reports stay visible.

A successful empty injury batch displays No injuries reported by ESPN. Missing
reports display Unavailable, never zero or an assertion of health. Fetch time
and source update time stay separate; absent source times are not invented.
The UI uses dated Central time and gray labels at least 11px. Player Props
remains the game's default tab.

Missing migration tables produce a sanitized HTTP 503 on nonempty slate/game
reads, not fabricated empty context. Empty slates need no context query.

## Measured local request cost

The actual FastAPI app served a synthetic twelve-game slate with 144 injuries
and 24 goalie sides through isolated read-only SQLite context queries. Its
response was 51,163 bytes; three local HTTP samples took 58.40, 13.66 and
11.15 ms, each using two context queries. One detail response was 4,274 bytes
and 10.41 ms, also two queries. Schedule/market reads were controlled fixtures;
no shared DB or provider call was used. See
`blueprint/reference/45f/final-verification.md` and local
`output/45f-step7-http.json`.

These measurements check payload scale and batch behavior. They do not measure
PostgreSQL plans, production latency, concurrent load or peak memory on Render's
512 MB API. Keep heavy reports off request paths. Snapshot provenance provides
no evidence of predictive value or permission for a later model experiment.

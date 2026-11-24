# Feature: NHL injuries and starting goalies

**From build-plan:** feature 45f (parent 45)
**Type:** Feature
**Status:** completed on feature branch; merge to local master pending approval
**Branch when implementing:** `feature/45f-nhl-injuries-starting-goalies`

## Goal

Show ESPN injuries and Expected/Confirmed starting goalies on the NHL slate
and game page. Preserve forward snapshots of what was known before puck drop
for historical display and a later, separately reviewed model experiment.
All context is display only.

45a selected the sources; 45b-45e are complete on master. The generated
overview still calls 45e upcoming; use its archive and `docs/nhl-display.md`
for current display contracts. Preserve the existing overview working edit.
This is one bounded feature, following the NBA injury-display precedent,
with separate review steps for ingestion, storage, API and each UI surface.

## Design reference

Extend `web/src/components/nhl/NhlSlateTable.tsx` and the Matchup tab in
`web/src/pages/NhlGamePage.tsx`, using the current NHL styles and
`web/src/index.css`. There is no external replication target or `prototypes/`.

- Slate: compact away/home goalie names with source statuses, injury counts,
  fetch time and freshness. Preserve readable phone layout and game links.
- Game Matchup: Starting goalies block and two team injury lists, with names,
  statuses, detail, source timestamps and explicit empty/unavailable states.
- Retain Player Props as the default tab, gray context styling and 11px floor.
  Expected/Confirmed describes ESPN's report, not a betting recommendation.

## In scope

- Pure parsers for ESPN NHL injuries and dated scoreboard goalie probables.
- Conservative NHL name/team linking, retaining unresolved source identities.
- Immutable snapshots with provenance and internal links frozen at ingestion.
- Standalone dry-run/write ingest and independent best-effort refresh workflow.
- Batched stored-context reads in existing slate/detail responses, typed web
  presentation, tests, local evidence and operating documentation.
- Update the ignored employer interview guide after implementation is verified.

## Out of scope

- Projections, P(over), model inputs/versions, signals, picks, ranking, grading,
  frozen predictions, NHL model/prop-board/player pages or new paid sources.
- Inferring starters from season leaders, odds or post-game starter flags;
  inferring healthy status from absence; reconstructing history from today's feed.
- Broad cross-sport injury abstraction or changing shared resolver behavior.
- Automatic shared migrations, destructive tests, remote dispatch, deployment,
  merge or push. Implementation prepares SQL and dry-run evidence first;
  shared migration and initial real writes are deliberate operational actions.

## Build loop

Build one step at a time, never the whole feature at once.

1. Lay out the next step before changing code.
2. Implement that step with tests for its logic.
3. Show its diff and evidence; split any diff too large to read in full.
4. The user reviews and approves before the next step. Checkpoint commits
   are optional; `/complete` owns the final work-level commit and merge.

## Build steps

- [x] **Step 1a - Parse injuries and verify team identities.** Verify bounded
  keyless injury, scoreboard and team-directory samples; save a minimal injury
  fixture; document aliases and implement pure injury parsing.
  *Done when:* passing tests cover status/detail/date parsing, successful empty
  vs malformed feeds, source athlete IDs, duplicate conflicts and team
  disagreement; source-field and alias evidence is recorded for review.
- [x] **Step 1b - Parse goalies and resolve identities.** Save a minimal dated
  scoreboard fixture, parse goalie observations and implement conservative NHL
  player/event matching against the verified team identities.
  *Done when:* tests cover Expected/Confirmed/unknown and absent announcements,
  malformed/truncated scoreboards, full-name/team matching, ambiguity, goalie
  position and event start/orientation boundaries. If live shapes contradict
  45a, revise this contract before persistence work.
- [x] **Step 2 - Store immutable observations.** Add the next migration
  (expected `0050`, recheck head) and repository writes for batch headers,
  injury rows and goalie observations, with indexed keys and atomic writes.
  *Done when:* offline Alembic SQL is reviewable; deterministic tests or
  isolated transaction fixtures prove exact retry, conflicting retry,
  rollback and successful-empty behavior. Existing reads do not depend on
  the new tables yet; no migration is implicitly applied to the shared DB.
- [x] **Step 3 - Ingest and schedule.** Add
  `python -m app.ingest.nhl_context [--dry-run] [--date YYYY-MM-DD]` and
  `.github/workflows/nhl-context.yml`. Default goalie reads cover Eastern
  today and tomorrow; explicit date selects one scoreboard. Injuries are
  always current, even with an explicit goalie date. Proposed cron:
  `17 * * 1-6,9-12 *` (hourly, September-June), plus manual dispatch,
  read-only repository permissions, serialized runs and ten-minute timeout.
  *Done when:* dry run requires no new tables and writes nothing; mocked
  transport tests prove bounded retries, independent per-feed commits and
  nonzero exit on any component failure. Summary reports unresolved players,
  unmatched events and feed failures safely. Workflow needs only DATABASE_URL
  and spends no odds credits or PrizePicks requests.
- [x] **Step 4 - Serve pre-game context.** Add batched repository selection,
  API schemas and one shared service assembler for slate/detail context.
  *Done when:* fixed-clock logic tests and read-only SQL/HTTP fixtures prove
  strict pre-start selection, independent feeds, no stale starter resurrection,
  empty/missing distinction, historical/TBD/rescheduled games and NHL isolation.
  Slate/detail agree with a fixed clock, and no read calls providers or writes.
  Missing migration is an operational error, never an empty report. If shared
  migration is pending, use isolated fixtures and record live acceptance pending.
- [x] **Step 5 - Display slate context.** Extend web types and pure context
  helpers; add compact away/home goalie reports and injury counts to the table.
  *Done when:* helper tests pass and desktop/390px browser evidence covers
  fresh/stale/unavailable, unresolved names, no announcement and empty reports.
  Search, dates, game links and market columns still work without horizontal
  page overflow; labels are readable without interpreting color.
- [x] **Step 6 - Display game context.** Add Starting goalies and team injury
  lists to Matchup, with independent timestamps and meaningful empty states.
  *Done when:* desktop/phone evidence covers both teams, changed goalies,
  unknown labels, unresolved identities, long lists, stale/missing context,
  historical context and API loading/error/retry. Default tab, direct refresh,
  back navigation and existing prop/odds values, counts and order are unchanged.
- [x] **Step 7 - Verify and document.** Run the exact project Verify command;
  capture API payload/timing and browser evidence; add `docs/nhl-context.md`;
  update `docs/nhl-display.md`, AGENTS commands, How It Works and the ignored
  employer guide if present. *Done when:* checks pass and docs distinguish
  fixtures, local real-data checks, migration/write acceptance, Actions and
  deployment. No unverified capability is described as deployed.

## Files / areas

| Area | Expected files |
|---|---|
| Pure parsing/linking | `api/app/core/nhl_context.py`, `api/app/core/nhl_context_resolution.py`, existing NHL name helpers as appropriate |
| Persistence | next `api/app/db/migrations/versions/0050_*.py`, `api/app/repositories/nhl_context.py` |
| Ingest | `api/app/ingest/nhl_context.py`, `.github/workflows/nhl-context.yml` |
| API | `api/app/schemas/nhl.py`, `api/app/services/nhl/context.py`, `slate.py`, `game_detail.py` |
| Web | NHL response types, `utils/nhlContext.ts`, NHL components/pages/styles |
| Tests/evidence | focused `api/tests/test_nhl_context*.py`, minimal fixtures, adjacent Vitest helper tests, `blueprint/reference/45f/` |
| Documentation | NHL docs, AGENTS commands, existing How It Works page, ignored employer guide if present |

## Data / contracts

These are load-bearing for later snapshot-based research. Aware timestamps
use UTC in storage/API and dated Central time in the UI.

### Sources and parsing

- Injury source: [ESPN NHL injuries](https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/injuries).
  Retain source status, detail, update time and return-date text when supplied.
  Missing source timestamps stay null rather than becoming fetch timestamps.
- Goalie source: [ESPN NHL scoreboard](https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard),
  requested with `dates=YYYYMMDD&limit=100`. Parse
  `competitions[].competitors[].probables` named `probableStartingGoalie`.
  Preserve raw status and normalize only to `expected | confirmed | unknown |
  not_reported`. Only source Confirmed earns Confirmed.
- Validate complete response shape/date coverage. Missing required collections,
  malformed identities/events and conflicting duplicates fail that component.
  Require the injury root's successful status and timestamp as in the NBA
  precedent; an error body with an empty collection is not a valid empty feed.
  Identical duplicates may deduplicate. Unknown status remains visible as
  unknown. A valid event without a probable records each competitor explicitly
  as not_reported; valid zero-event scoreboards get a successful empty marker.
  Detect response truncation rather than silently treating it as full coverage.
  ESPN supplies no root date/count on the verified scoreboard: validate each
  event's Eastern date against the requested date and fail when the response
  reaches the requested limit (100). An empty response's requested date is
  caller provenance, not a provider-confirmed date. Silent upstream omissions
  cannot be detected from this feed alone. Ignore explicitly typed preseason
  events; unknown season types fail rather than being silently skipped.
- Verify ESPN team IDs/codes from samples, mapping explicit aliases (including
  TB to TBL). Preserve source team and nested athlete-team disagreements.
  Do not assume the PrizePicks alias map covers every ESPN difference.

### Identity and events

- Only link existing NHL players on unique normalized full name plus canonical
  team; allow accent/punctuation normalization, not fuzzy/initial-only guesses.
  Goalie matches must have goalie position. Preserve unresolved entries with
  nullable internal IDs and explicit reasons. Never create placeholder players
  or store ESPN athlete IDs as NHL `source_player_id`.
- Reuse normalization pieces without accepting the shared resolver's permissive
  unique-name/team behavior or changing it for other callers. Stale roster
  teams after trades may leave a player unresolved; their source report still
  appears under its reported team and contributes to counts.
- Match an ESPN event only to a unique NHL REG/PST game with ordered home/away
  teams and starts within 60 minutes. Missing starts, ambiguous matches and
  larger reschedule differences remain unresolved. Retain ESPN event ID,
  date, start and both teams independently of nullable internal game link.
- Freeze links/reasons at ingestion. Corrected links appear in new snapshots;
  never rewrite old observations or relink them using today's roster on reads.

### Storage

| Table | Grain and fields |
|---|---|
| `nhl_context_snapshots` | Header: id, source ESPN, kind injuries/goalies, scope_date (null for global injuries; requested Eastern date for goalies), fetched_at, nullable source_timestamp, entry_count |
| `nhl_player_injuries` | Batch/team/athlete: ESPN IDs, canonical team, source name, raw status/detail, update/return date, nested athlete team, nullable player FK and link reason |
| `nhl_goalie_observations` | Batch/event/team: ESPN event/team IDs, event date/start, home/away teams, nullable game/player FKs, nullable athlete ID/name, raw/normalized status and link reasons |

Goalie observations also preserve nullable nested athlete team and source
position, so disagreements can prevent linking without hiding the source name.
An event with `timeValid=false` retains its source scheduled timestamp but is
ineligible for game matching; store `time_valid` alongside that timestamp.

- Header uniqueness: `(source, kind, scope_date, fetched_at)` with NULLS NOT
  DISTINCT. Constraints enforce kind/date relationship and nonnegative count.
  Entry uniqueness: batch/team/athlete for injuries, batch/event/team for goalies.
  A not_reported competitor row has null athlete/raw-status fields.
- Header and entries commit together. Exact timestamp/content retry returns
  the existing batch; differing content fails without changing it. No replacing
  updates, historical cleanup or automatic relinking. Index latest-batch and
  batch/team/game lookups. Repository writes validate linked FK sport because
  shared-table foreign keys alone cannot enforce NHL ownership.
- Repository writes use one savepoint per batch and never commit the caller's
  transaction. The ingest command commits successful components independently.
  Frozen link maps must cover each source row/event exactly; changing source
  fields or frozen links at the same batch identity is a conflicting retry.
- Each feed/date commits independently. Failed downloads/parses write no success
  marker. Successful empty batches are real observations, not failures.

### Response and temporal selection

- Add `context: { injuries: InjuryContext, goalies: GoalieContext }` to
  `NhlSlateGameSchema`, inherited by game detail, camelCase on wire.
- Each component exposes `source: 'ESPN'`, `fetchedAt: datetime | null`,
  `sourceTimestamp: datetime | null`, `freshness: fresh | stale | unavailable`,
  and `away`/`home`. Injury sides are arrays of `{espnAthleteId, playerId:
  int | null, playerName, team, status, detail: string | null, sourceUpdatedAt:
  datetime | null, returnDate: string | null, linkReason, teamMismatch: boolean}`.
- Goalie sides are `{espnAthleteId: string | null, playerId: int | null,
  playerName: string | null, team, status: expected | confirmed | unknown |
  not_reported | unavailable, rawStatus: string | null, linkReason: string |
  null}`. Player link-reason enum: `matched | no_candidate | ambiguous |
  team_mismatch | missing_team | position_mismatch | not_reported`.
  Stored event link reasons: `matched | no_game | ambiguous | missing_start |
  start_mismatch`. Preserve these typed codes across storage/API; extending
  them requires a spec update. They are never stack traces.
- Capture one aware response clock. Independently select the newest successful
  batch per kind with `fetched_at < start_utc` and `fetched_at <= response_as_of`,
  breaking timestamp ties by ID. Injuries use global batches filtered to the
  game teams; goalies use the game's Eastern-date scope and frozen event link.
- Select the latest qualifying goalie batch before seeking the event. Missing
  event means unavailable; an event without a probable means not_reported.
  Neither resurrects an older named or Confirmed starter. Source names remain
  visible with null player IDs. Require stored event teams/start still match
  the game's current teams/start under the matching rule after reschedules.
- If multiple distinct source events in that batch link to the same game,
  report goalie context unavailable instead of arbitrarily picking one event.
  Missing migration 0050 yields an explicit 503 for nonempty slate/game reads,
  never a fabricated empty report. Empty slates need no context query.
- Unknown game start or no eligible batch means unavailable with null times.
  For goalies, a successful selected batch with no matching event is unavailable
  but retains its batch timestamps to distinguish a missing announcement from
  a missing download. Both sides use unavailable; do not count it as an event
  with two not_reported competitors.
  Successful empty injuries means 'No injuries reported by ESPN', never
  'Everyone available'. Injury arrays alone cannot imply availability.
- Measure age at `min(response_as_of, start_utc)`: over six hours is stale,
  exactly six is fresh. Keep stale reports visible and labeled. Started/final
  games retain pre-game context. Post-start downloads cannot backfill it.
- Batch queries across games; no per-game SQL loop. All shared reads filter
  NHL and REG/PST. No new public endpoint, live fetch or request-time report.
  Existing sport/provider/market/prop predicates remain unchanged.

### Refresh and failure behavior

- Hourly September-June refresh is best effort, independent of odds/props.
  It cannot guarantee the last scratch or goalie change before every start.
- Thirty-second per-operation HTTP timeout, at most three attempts for transport
  failures, 429 and 5xx. Honor Retry-After within the job bound; other HTTP/parser
  errors fail the component. Timestamp each response after completion.
- Bound each component's fetch/retries to 90 seconds and DB processing to 30
  seconds. Retry-After accepts seconds or an aware HTTP date. Waits up to 30
  seconds carry across components; a longer or malformed header blocks further
  ESPN calls in the current run, with explicit per-component failure summaries.
- Attempt independent components even after one fails; exit nonzero if any
  fails. Prior successful batches remain to age stale. Log safe counts/reasons,
  never keys, database URLs or environment dumps. Dry run performs reads only.
- These snapshots establish provenance, not predictive value or permission
  for later historical scoring or model adoption.

## Testing

- Test gate is on. Each logic-bearing step ships passing pytest/Vitest tests
  using fixed clocks, minimal fixtures and mocked network dependencies.
- Parsers: root/status validation, injury athlete-ID paths, source dates,
  missing probables, Expected/Confirmed and unknown values, duplicate conflicts,
  team disagreement, empty vs malformed/truncated response.
- Linking: accents/aliases, exact full-name/team match, same-name ambiguity,
  missing/stale team, goalie position, event orientation, 60-minute boundary,
  wrong sport and ambiguous events.
- Persistence/selection: identical/conflicting retries, rollback, empty marker,
  strict start cutoff, future exclusion, timestamp ties, independent failures,
  no prior-starter resurrection, TBD/reschedules and six-hour boundary.
- Observe SQL/API/browser integration with isolated or read-only fixtures;
  do not add a new component/route test suite or mutate the shared DB to test
  rollback. Capture desktop/phone and keyboard evidence for all done-whens.
- Final gate with API venv active:
  `npm --prefix web run verify && cd api && python -m pytest`.
  Record busy-slate response size/timing; keep reads suitable for Render's
  512 MB API. Local measurements do not prove production peak memory.

## Notes for the AI

- Implement the approved spec one reviewable step at a time.
- Keep core pure, SQL in repositories, orchestration in services and routers
  thin. Continue typed transport and TanStack Query; context arrives in existing
  responses, so no new per-row fetch hooks are needed.
- Review offline migration SQL before any authorized shared migration. Apply
  manually, one command at a time; never downgrade the shared DB for testing.
- Keep 44b parked and untouched; no holdout reads or scoring. Do not edit the
  user-owned plans or regenerate the overview under this feature invocation.
- Update `docs/SportApp-Employer-Interview-Guide.md` only after verified
  implementation changes its claims, skip if missing, and never stage it.
- Source basis: 45a archive Step 2; completed 45e archive and
  `docs/nhl-display.md`; NBA precedent `docs/nba-injuries.md`. Spec research
  reached ESPN's scoreboard through the web tool. The injury URL was not
  accessible there and direct Python requests were blocked by managed-shell
  networking. This establishes neither an outage nor a new successful injury
  probe. Step 1 revalidates both source shapes before implementation proceeds.

## Implementation evidence

- 2026-10-24: the three keyless ESPN reads (injuries, dated scoreboard and team
  directory) succeeded through a bounded shell probe. Raw responses are local
  ignored artifacts under `output/45f-source-probe/`. No DB/provider-quota writes.
- Step 1 was split into 1a/1b to keep the injury parser and goalie/linking diffs
  individually reviewable. No persistence or UI scope was added.
- Step 1a parser accepted the full saved injury response (135 entries, 29
  teams); 67 focused tests pass. Source paths and fixture provenance are in
  `blueprint/reference/45f/source-shapes.md`. Approval is pending, so Step 1a
  remains unchecked and Step 1b has not started.
- Step 1a automated gate passed: exact root Verify command with API venv on
  PATH; web typecheck, 878 web tests, production build and 4,240 API tests.
  Existing Vite bundle-size and Starlette deprecation warnings remain.
  `git diff --check` passed. Review diff: local `output/45f-step1a.diff`.
- Step 1a approved by the user's Continue response; no checkpoint requested.
- Step 1b parses the complete saved dated scoreboard (24 observations: 11
  Confirmed, 13 Expected). No new provider request or DB operation was needed.
  The focused injury/goalie/resolution suite passes 163 tests. Full-name/team
  and source-team mismatch checks are enforced by observation-level wrappers.
  Step 1b remains unchecked pending review; persistence has not started.
- Step 1b exact root Verify passed with the API venv on PATH: web typecheck,
  878 web tests, production build and 4,336 API tests. Existing Vite bundle-size
  and Starlette deprecation warnings remain. `git diff --check` passed. Local
  review diff relative to approved Step 1a: `output/45f-step1b.diff`.
- Step 1b approved by the user's Continue response; no checkpoint requested.
- Step 2 adds migration 0050 (single local Alembic head) and savepoint-based
  repository writes. Forty-three focused repository/DDL tests pass. Offline
  `0049:0050` upgrade SQL is in `blueprint/reference/45f/0050-upgrade.sql`;
  it was generated with a local dummy URL and never executed.
- Step 2 exact root Verify passed with API venv on PATH: web typecheck, 878
  web tests, production build and 4,379 API tests. `git diff --check` and
  whitespace checks on new files pass; existing bundle/deprecation warnings
  remain. Repository transaction tests use session/savepoint doubles, not
  PostgreSQL. Shared migration and actual database acceptance remain pending.
  Details: `blueprint/reference/45f/storage-verification.md`; local review diff:
  `output/45f-step2.diff`. Step 2 remains unchecked pending user approval.
- Step 2 approved by the user's Continue response; no checkpoint requested.
- Step 3 adds the CLI, existing-table candidate reads and hourly workflow.
  A real `--dry-run` exited 0 with enforced read-only transactions: 131 injury
  entries (108 linked), 24 October 24 goalie observations (23 linked), and 10
  October 25 observations (all linked); every goalie event matched. These are
  dated observations from 2026-10-24 19:23 UTC, not current inventory counts.
- Step 3 focused ingest/repository suite passes 74 tests. Exact root Verify
  passes with the API venv on PATH: typecheck, 878 web tests, production build
  and 4,411 API tests. Workflow YAML parses; schedule, permissions, concurrency,
  environment and command were checked. Existing warnings remain.
- Step 3 `git diff --check` and separate new-file whitespace checks pass.
  Evidence: `blueprint/reference/45f/ingest-verification.md`; incremental local
  diff: `output/45f-step3.diff`. No migration, real snapshot write, push or
  dispatch was run. Step 3 remains unchecked pending user approval.
- Step 3 approved by the user's Continue response; no checkpoint requested.
- Step 4 adds typed context schemas, frozen snapshot decoding, indexed batched
  header/entry selection and one shared assembler/response clock for slate and
  detail. The focused SQL/service/existing-display suite passes 102 tests.
- Step 4 check: the actual FastAPI app served eight localhost requests using
  isolated SQLite context tables and controlled schedule/market/prop fixtures.
  Slate/detail and existing-field parity, no prior-starter resurrection,
  empty/404/422 behavior and a sanitized controlled 503 all passed. Three
  nonempty reads used six context queries; external HTTP was blocked.
- Step 4 exact root Verify passed with API venv on PATH: typecheck, 878 web
  tests, production build and 4,462 API tests. Existing warnings remain.
  `git diff --check` and new/changed-file whitespace checks pass.
- Step 4 evidence: `blueprint/reference/45f/api-verification.md`; local HTTP
  output `output/45f-step4-http.json`; incremental diff `output/45f-step4.diff`.
  Migration 0050 and real PostgreSQL/stored-context acceptance remain pending;
  no shared database connection/write or provider fetch was used in this step.
  Step 4 remains unchecked pending user approval.

## Draft critique

Step 7 approved by the user's Continue response. All implementation steps are
approved; no checkpoint was requested. Handoff to /complete is ready using the
final review packet below. This approval did not invoke /complete or authorize
a commit, merge, push, migration, real snapshot write, dispatch or deployment.
Operational acceptance remains pending as documented.

Step 6 approved by the user's Continue response; no checkpoint requested.
Step 7 adds the NHL operating guide, links it from display docs and AGENTS,
updates conditional ESPN coverage in How It Works and updates the ignored local
interview guide without staging it. A twelve-game isolated FastAPI HTTP fixture
returns 144 injuries/24 goalie sides in 51,163 bytes, with two context queries;
three samples took 58.40/13.66/11.15 ms. This is not PostgreSQL/production load
or memory acceptance. How It Works desktop/390px checks pass with no API calls,
page exceptions or horizontal overflow. The focused invariants review is clean;
F-09/F-12 remain unrelated unverified research follow-ups, with no open/fixed
P0/P1 findings. Exact final root Verify passed with API venv on PATH: typecheck,
903 web tests, production build and 4,462 API tests. Existing warnings remain.
Final evidence/review packet: `blueprint/reference/45f/final-verification.md`.
Incremental local public diff: `output/45f-step7.diff`; ignored guide diff:
`output/45f-step7-guide.diff`. Step 7 remains unchecked pending approval.
Migration 0050, real stored-write/PostgreSQL acceptance, Actions and deployment
remain pending; the spec's isolated-fixture acceptance path was used. No commit,
merge, push, dispatch or deployment was performed. The overview working edit
was preserved. Approval hands off to /complete, without automatically invoking it.

Step 5 approved by the user's Continue response; no checkpoint requested.
Step 6 adds Starting goalies and two team injury lists in Matchup, with source
update/fetch timestamps kept separate, explicit unresolved identities and
empty/unavailable reports. Six additional helper cases pass (65 focused NHL
tests total). Controlled desktop/390px checks cover long lists, changed/unknown
goalies, missing/TBD reports, historical context, default tab/direct refresh,
props/market parity, back navigation, keyboard tab activation and real UI
loading/error/retry. Evidence and per-file explanation:
`blueprint/reference/45f/game-ui-verification.md`; local incremental diff:
`output/45f-step6.diff`. Exact root Verify passed with API venv on PATH:
typecheck, 903 web tests, production build and 4,462 API tests. Existing warnings
remain; whitespace checks pass. No checkpoint, shared migration/write, push or
deployment occurred. Step 6 remains unchecked pending review; Step 7 has not
started.

Step 4 approved by the user's Continue response; no checkpoint requested.

Step 5 adds typed frontend context, nineteen fixed-clock helper cases and a
gray context band beneath each slate game. The seven market columns remain.
Desktop/390px controlled browser checks cover independent freshness, missing
reports, no announcement, empty injuries, unresolved/long names and unknown
statuses. Search, dates, keyboard game links, phone context clicks and existing
loading/empty/retry states pass. Minimum context font is 11px; no page overflow.
Exact root Verify passed with API venv on PATH: typecheck, 897 web tests,
production build and 4,462 API tests. Existing bundle/deprecation warnings
remain. Focused NHL tests: 59 passed. Evidence and per-file explanation:
`blueprint/reference/45f/slate-ui-verification.md`; incremental local diff:
`output/45f-step5.diff`; desktop/phone screenshots are under `output/45f-step5-*`.
Step 5 remains unchecked pending review. No checkpoint, migration, shared
snapshot write, push or deployment was performed. Step 6 has not started.

Checked coverage, unhappy paths, step size, ordering, contracts and test scope.
Kept this as one feature with separately reviewable storage/API/UI steps.
Tightened independent feed success markers, no resurrection of older starters,
reschedule validation and frozen identity links. Added explicit unknown-status,
empty-report and unresolved-name behavior, fixed link-reason enums, and made
shared-migration acceptance distinct from isolated fixture verification.

## Completion

Completed locally on 2026-10-24 through the complete skill. All implementation
steps were approved. The exact root Verify command was rerun with the API venv
on PATH: `npm --prefix web run verify && cd api && python -m pytest`. Typecheck,
903 web tests, production build and 4,462 API tests passed. Existing warnings
remain. Local completion gate log: `output/45f-complete-verify.log`.

The work-level commit includes the implementation, evidence, operational docs,
this archive, build-plan checkboxes and reset active-spec stub. The pre-existing
`blueprint/context/project-overview.md` edit is excluded and preserved. The
updated employer guide remains ignored and unstaged. No resolved findings
needed archiving; F-09/F-12 stay unverified in the ledger, with no open/fixed
P0/P1 findings. No prototypes were consumed. No skill-adapter behavior changed.

All currently listed 45a-45f sub-items are complete, so parent 45 is checked.
This marks implementation complete, not operational activation or model
adoption. Migration 0050, initial real context write/PostgreSQL acceptance,
Actions registration/runner acceptance and deployment remain pending. The
reviewed migration must precede deploying the backend change. No shared
migration/write, merge, push, dispatch or deployment was authorized or run by
this completion invocation. Merge is a separate explicit approval gate.

Manual review: see `docs/nhl-context.md` and the final evidence packet at
`blueprint/reference/45f/final-verification.md`, or run `/try latest`.

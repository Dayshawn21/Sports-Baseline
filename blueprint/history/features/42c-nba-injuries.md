# Feature: NBA injuries

**From build-plan:** 42c (parent 42, NBA prop board)
**Status:** complete (approved 2026-10-21); migration 0048 and first real snapshot verified; hosted deployment and runner acceptance unverified
**Branch:** `feature/nba-injuries`

## Goal

Show timestamped ESPN injury status and detail on NBA prop rows and evidence,
with both teams' injury lists on the game page. Readers can distinguish a
reported injury, an empty report, stale information and unavailable information.
This is display context only. It never changes a projection, gap, probability,
model version, row order, pick or frozen prediction.

## Design reference

Extend the existing NBA surfaces and theme; no redesign or prototype token port.
Use the current components and these local captures for layout continuity:

- [Board](../../reference/42b/step4-assists-rows-1440.png)
- [Evidence drawer](../../reference/42b/step4-assists-drawer-1440.png)
- [Phone board](../../reference/42b/step4-double_double-rows-390.png)
- [Game page](../../reference/42b/step2-game-1440.png)

Injury tags are neutral gray text, with visible status words. Full detail and
timestamps must be readable without hovering. Preserve row links, drawer focus
restoration, the palette and CT display times.

## In scope

- Keyless ESPN NBA injury ingest, immutable timestamped snapshots, and an
  explicit successful-snapshot marker, including successful empty reports.
- ESPN athlete/team identity, including injured players without a stored box
  score or PrizePicks line. Never create or match a player by name alone.
- Shared stored context for modelled and line-only game endpoints and the
  date-wide board. Both teams' lists include players without props.
- Status tags on shared prop rows and status/detail/source time in both kinds
  of evidence drawer; team injury panels on `/nba/game/:gameId`.
- An independent scheduled/manual workflow and a dry-run CLI, operational
  documentation and appropriate unit and running-app evidence.

## Out of scope

- Team statistics (42d), depth charts, official-report PDF ingest, historical
  availability backfills, model inputs, training, grading or adoption decisions.
- Filtering out injured players, changing rungs, ranking or sorting by injury,
  injury-based picks, adding injury values to prediction flags or freezes.
- NBA slate injury summaries, WNBA support, paid provider calls, public ingest
  endpoints, broad board payload optimization or new report generation.
- Merge, push, workflow dispatch, deployment or automatic shared-DB migration.
  Local verification and hosted/runner acceptance remain distinct.

## Build loop

1. Explain the next small step before editing source.
2. Implement that step and its logic tests, then prove its done-when.
3. Show the diff and evidence for review; wait for approval before the next step.
4. Checkpoints require approval. `/complete` owns final logging and merge.

## Build steps

- [x] **Step 1 - Verify the feed and implement the pure parser.** Re-probe the
  ESPN URL below, save a small representative sanitized fixture, document actual
  field paths and define typed internal records. Extract athlete IDs from
  explicit IDs or validated ESPN athlete links as the payload requires; record
  team IDs and normalize codes with verified ESPN mappings. Preserve source
  status, update time, detail and return-date text when present. Validate feed
  completeness before treating omissions as an empty report. Add parser tests.
  *Done when:* captured evidence documents the current schema; fixed fixtures
  cover Out, Day-To-Day, unknown status, missing optional detail/date, athlete
  link IDs, duplicate/conflicting entries, malformed data and valid emptiness.
  No database or production call is needed to run the tests. If the live feed
  cannot be verified, report that limit before implementing a guessed parser.

- [x] **Step 2 - Add snapshot storage and ingest.** Create migration `0048`
  (recheck head first), repository writes, and
  `python -m app.ingest.nba_injuries [--dry-run]`. Use bounded HTTP timeout and
  transient retry, then atomically write a completed batch and all its entries.
  Reject structurally incomplete or conflicting snapshots without advancing the
  successful batch. Dry run parses and reports counts but writes nothing.
  *Done when:* dry run reports teams, entries and unresolved identities;
  isolated local/test database evidence shows complete, empty and repeated
  batches are readable, old rows remain immutable, and failure leaves the last
  successful snapshot intact. No shared Neon migration is run implicitly.

  Step 2 evidence: `blueprint/reference/42c/step2-storage.md`. Live dry run,
  67 focused tests and full Verify pass. PostgreSQL DDL compiles offline;
  actual migration/persistence execution remains unverified because no isolated
  PostgreSQL server is available. Step 2 approved with that verification limit.

- [x] **Step 3 - Share injury context across the API.** Add bounded batched
  repository reads and a shared injury service/selector for the board, both
  game prop builders and game detail. Extend camelCase schemas as below.
  Add tests for selection, identity and board/game parity. Do not fetch ESPN
  on a GET request or query per player/line.
  *Done when:* local API responses agree on injury context for the same
  game/player and snapshot; team lists include a player with no props. Empty,
  stale, historical-without-snapshot and missing-tip cases match the contract.
  Existing projection/line/probability/flags/order fields remain identical.

  Step 3 evidence: `blueprint/reference/42c/step3-api.md` and saved fixture
  responses. Seven games agree across real local HTTP routes; the actual injury
  SQL passed PostgreSQL read-only CTE fixture checks, without migrations or
  stored-data writes. Focused tests: 118 passed. Full Verify: 659 web tests,
  typecheck/build and 3,561 API tests passed. Step 3 approved.

- [x] **Step 4 - Prop row tags and evidence.** Carry nullable injury context
  through TypeScript types and the existing modelled/line-only grouping helpers.
  Add one reusable neutral injury presentation for board and game prop rows,
  and both shared evidence variants. Keep status separate from model flags.
  Add tests for helper derivations, including all alternate rungs.
  *Done when:* browser evidence shows Out and Day-To-Day rows and drawers on
  both pages, with source/detail and stale/unavailable wording, for modelled
  and line-only fixtures. No new requests occur on drawer/market selection;
  keyboard interaction and 1440/1000/390-pixel layouts remain usable.

- [x] **Step 5 - Both teams' game-page reports.** Render the game response's
  home and away reports in a small shared component, including players with
  no prop. Show freshness and successful-empty/unavailable states separately.
  *Done when:* a local game page shows both lists and timestamps, long detail
  wraps on a phone, and changing injury fixtures changes no market or model
  value. Fixture evidence covers empty, stale and unavailable reports.

- [x] **Step 6 - Schedule, document and verify.** Add an independent
  `nba-injuries.yml` with manual dispatch and `43 */2 * 1-6,10-12 *` UTC
  (every two hours, October through June). Use Python 3.11 and the existing
  dependency-install pattern, `contents: read`, and the database secret only.
  Use workflow concurrency to avoid overlapping writes. Document cadence,
  freshness, CLI and manual migration in AGENTS.md and an NBA operations note;
  update the local employer guide if present after implementation is verified.
  *Done when:* final Verify passes, API/browser evidence is recorded under
  `blueprint/reference/42c/`, and local timing/payload observations show a bounded
  stored-context addition without per-player queries. Hosted memory and first
  runner acceptance are explicitly pending until separately observed.

  Steps 4-6 were completed under the user's request to finish the remaining
  implementation. Final Verify passed: 673 web tests, typecheck/build and
  3,561 API tests. Board/game drawers and team reports were checked at
  1440/1000/390 pixels, including empty/stale/unavailable reports, long detail,
  injury-only players, team mismatches and no drawer/market API calls. The
  workflow YAML was parsed and its schedule/permissions/concurrency checked.
  Operations docs and the ignored local employer guide were updated.
  See `blueprint/reference/42c/review-packet.md` for the final proof and limits.
  No migration, real snapshot write, dispatch, commit, merge, push or deploy
  was performed. `/complete` bookkeeping remains a separate approved step.

  Follow-up on 2026-10-21: the owner reported the real API's missing injury
  table and asked to continue. Read-only inspection confirmed revision 0047
  with both injury tables absent. The reviewed additive migration was then
  manually applied, and one real ESPN batch stored 80 injuries. The board
  and two sampled games' detail/modelled/line-only routes returned 200 with
  exact injury/report parity. Current revision is 0048. Earlier fixture-only
  limits above describe those earlier checks; live persistence is now observed.
  Rollback/concurrency failure cases remain isolated unit/fixture checks.
  Evidence: `blueprint/reference/42c/live-acceptance.json`.

## Files / areas

- `api/app/ingest/nba_injuries.py`: HTTP/CLI orchestration and parser entry point.
- `api/app/core/nba_injuries.py`: typed records and pure normalization/selection.
- `api/app/db/migrations/versions/0048_nba_injuries.py`: snapshot storage.
- `api/app/repositories/nba_injuries.py`: all injury SQL and NBA-scoped linkage.
- `api/app/services/nba/injuries.py`: shared batched display assembly.
- `api/app/services/nba/{prop_board,props,line_only_props,game_detail}.py` and
  `api/app/schemas/nba.py`: additive context; thin routers as needed.
- `api/tests/test_nba_injuries*.py`, existing board/prop tests and feed fixtures.
- `web/src/types/nba.ts`, `web/src/utils/nbaProps.ts`, `nbaLineOnly.ts`,
  `nbaPropBoard.ts`, injury presentation helper and relevant helper tests.
- `web/src/components/nba/`: shared injury display, prop table/evidence,
  game injury list; `web/src/pages/NbaGamePage.tsx` and related styles.
- `.github/workflows/nba-injuries.yml`, `AGENTS.md`, NBA operations note,
  `blueprint/reference/42c/`, local ignored employer guide if present.

## Data / contracts

### Source and snapshot storage

Source: `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries`.
The 20a archive documents a keyless current snapshot, Out/Day-To-Day, ESPN team
IDs and athlete IDs in links. It has no historical availability archive.
The initial sandbox probe on 2026-10-21 could not connect. Step 1 subsequently
verified the live feed with approved network access: 80 entries in 28 team
groups, source timestamp `2026-10-21T17:52:32Z`. See
`blueprint/reference/42c/step1-feed.md` for field paths and evidence limits.

Use two small related tables so an empty successful report is representable:

| Table | Required fields and constraints |
|---|---|
| `nba_injury_snapshots` | `id` bigint PK, `fetched_at` aware UTC unique, `source` fixed ESPN identifier, `source_timestamp` aware UTC from the feed root, `entry_count` nonnegative. A row becomes visible only with its full committed entry set. |
| `nba_player_injuries` | `snapshot_id` FK, `espn_team_id`, `team_code`, `espn_athlete_id` as text, `player_name`, `status`, nullable `detail`, `source_updated_at`, `return_date` and `athlete_team_id`; unique `(snapshot_id, espn_team_id, espn_athlete_id)`. |

Index snapshot lookup by fetch time and entry lookup by snapshot/team/athlete.
Store provider identity independently of internal player FKs so a rookie or
injured player with no box score is retained. Link nullable internal `playerId`
at read time using `sport_players.sport = 'nba'` and `source_player_id` only;
team mappings must use verified ESPN IDs/codes. Team membership must match the
game side, avoiding a stale injury tag after a trade. No fuzzy/name fallback.

The verified feed contains one outer-report-team/current-athlete-team mismatch.
Preserve both provider IDs: the outer group owns the reported team, while
`athlete_team_id` records the nested current team when present. Do not attach a
mismatched entry to a prop, or silently move it to the athlete's new team.
Team lists retain the entry under its reported team with an explicit provider
team-mismatch note. The parser exposes this discrepancy without rejecting the
otherwise valid full feed. Persist the extra ID in Step 2 and carry it through
Step 3 so this safeguard survives storage.

Each successful fetch is a new immutable snapshot, even if content is unchanged,
because it establishes freshness. A retry of the same batch timestamp is
idempotent. Absence in the next complete feed removes a previous injury from
that new report, while preserving the old snapshot. Never carry an old player
entry into a newer complete batch. Invalid required identity or conflicting
duplicates fail the batch; identical duplicates can collapse. Missing optional
text/time stays null; unknown statuses stay visible as provider text.

### Time selection and freshness (load-bearing)

- Capture one aware UTC `asOf` per response. For a known tip use the latest
  successful batch with `fetched_at < startUtc` and `fetched_at <= asOf`.
  For future tips this selects the latest currently available pre-tip batch.
  Started/final games retain pre-tip context; never show today's injuries as
  historical game-day facts. No qualifying batch means unavailable.
- Missing tip: show unavailable context instead of guessing a historical cutoff.
- Compare freshness against `min(asOf, startUtc)`. A batch older than six hours
  is stale; exactly six hours is fresh. For completed games label it pre-tip
  context, rather than comparing it to today's clock.
- Both successful-empty and stale-empty reports carry their real timestamp.
  Empty means "No injuries reported by ESPN", never confirmed healthy.
  Unavailable means "Injury report unavailable". Stale entries remain visible
  with a stale label. Do not manufacture a player status for absent entries.
- Provider update time and fetch time are distinct. Show both when present;
  expected return is provider context, not a promised return date.
- Schedule timing is best effort; delayed GitHub jobs cannot guarantee a report
  immediately before every tip. Freshness remains visible even after failures.

### Additive API shape (load-bearing)

Keep existing endpoints and fields. Use Python snake_case and existing camelCase
serialization; all new nullable fields are explicitly serialized as null.

```text
NbaInjury:
  espnAthleteId: string
  playerId: number | null
  playerName: string
  team: string
  athleteTeam: string | null      # nested ESPN athlete team, for mismatch context
  status: string
  detail: string | null
  sourceUpdatedAt: string | null
  returnDate: string | null
  fetchedAt: string

NbaInjuryReport:
  source: "ESPN"
  fetchedAt: string | null
  freshness: "fresh" | "stale" | "unavailable"
  injuries: NbaInjury[]

NbaLineOnlyLine (and inherited NbaPropLine):
  injury: NbaInjury | null

NbaPropsResponse, NbaLineOnlyPropsResponse, NbaPropBoardGame:
  injuryReport: NbaInjuryReport

NbaGameDetailResponse:
  injuryReport: NbaInjuryReport
```

Each report contains the selected snapshot's entries for the game's two teams.
The UI filters these by the existing away/home team codes; it does not duplicate
team lists on every rung. Line `injury` carries only a matching player/team's
entry. Report metadata explains a null injury even when no entries exist.
Use the same enrichment function and batch selection in board and game builders;
parity is measured against the same stored batch and captured response time.
Future snapshots may legitimately update scheduled games between requests.

Read stored data in a bounded number of queries per date or game, batching all
game cutoffs and player IDs. No provider I/O, JSON feed parsing or model work on
the request path. Add no injury fields to the freeze, projection or grading
contracts. Preserve sport/game-type/full-game/market and pre-tip line filters.

## Testing

- Parser fixtures: provider status/detail/time handling, IDs from links,
  missing optional data, unsupported/malformed root shape, invalid required IDs,
  duplicates and complete empty reports. Completeness behavior must follow the
  verified payload, not assume a missing key is an empty list.
- Pure selection/enrichment: before/equal/after tip, future batch exclusion,
  six-hour boundary, no snapshot, missing tip, empty replacement, stale report,
  no internal player, team mismatch/trade and unknown status.
- API assembly tests: one shared context for board/game modelled and line-only
  payloads, multiple games/cutoffs, injury-only player in team list, all rungs,
  and equality of pre-existing model values/flags/order. Mock I/O in unit tests.
- Web helper tests: context survives grouping, alternate rungs and line-only
  rows; null never becomes healthy and stale labeling uses a supplied clock.
- Real local API and browser checks cover the integration and React rendering;
  use controlled local fixtures for otherwise unavailable live cases. Record
  which evidence is fixture-based versus observed ESPN data.
- Validate migration/atomic writes only against an explicitly isolated database;
  if unavailable, report migration execution unverified. Do not run downgrade
  or schema experiments against the shared database.
- Final automated gate: `npm --prefix web run verify`, then from `api/`,
  `.venv\Scripts\python.exe -m pytest`, equivalent to the documented Verify
  command with the venv active. No new runner or component test suite.

## Notes for the AI

- This is one reviewable feature with six gated steps; 42d stays separate.
- Core remains pure; repositories own SQL; all configuration uses Settings.
- Network failure or malformed feed must preserve the last successful report.
- The existing board response was about 4.88 MB in 42b local evidence. Keep
  team lists at game scope and record the added bytes/queries; do not repeat a
  full team report per prop line or claim hosted memory acceptance.
- Preserve user changes already present in `project-overview.md`; do not
  regenerate it, edit the user-owned plans or mark 42c complete during spec work.
- Update relevant existing employer-guide explanations only once evidence
  supports implementation claims. Never stage that ignored local guide.
- Review the draft against missing/empty data, historical leakage, identity,
  scope, step size and observable acceptance criteria before presenting it.

## Spec critique

- Added a completed-batch table so successful emptiness clears old injuries
  without confusing a failed/malformed feed with an empty report.
- Locked pre-tip selection and a six-hour freshness rule to prevent current
  injuries appearing as historical context; unknown tips are unavailable.
- Preserved ESPN-only identity, injury-only players and team matching.
- Kept team reports at game scope and shared enrichment for both line kinds.
- Split row/drawer UI from both-team game panels to keep diffs reviewable.
- Made live payload verification a first-step requirement because today's
  initial network probe failed; Step 1 later verified it with network access.
- Step 1's live feed exposed a report/current-team mismatch. Preserve both IDs,
  label it in team lists, and suppress prop attachment instead of guessing.

# Feature: NHL prop lines

**From build-plan:** feature 45c (parent 45)
**Status:** complete locally (2026-10-23); merge pending
**Size:** one feature, five reviewable steps

## Goal

Snapshot PrizePicks full-game NHL player lines through the shared 17c pipeline,
link them to the NHL players and games loaded by 45b, and retain line history.
Every market is line-only. No projection, probability or recommendation is
created by this feature.

## In scope

- NHL market and league configuration, using the names observed in 45a.
- Pure NHL name/team normalization and conservative player/game resolution.
- A `PropLineSource` adapter, NHL-scoped player-candidate query and thin CLI
  for fetch, dry-run and provider-free relink.
- One bounded live check of the board and Time On Ice units, then a real
  snapshot and relink verification against the existing shared database.
- A separate NHL prop workflow and relink after daily NHL schedule/stat ingest.
- Command and operational documentation, with local and hosted status distinct.

## Out of scope

- Models, baselines, P(over), edges, ranking, settlement, frozen predictions,
  model versions or registration in `PROP_SOURCES`.
- NHL routes, pages, sport navigation and gray prop display (45e).
- Game odds (45d), injuries and expected/confirmed starters (45f).
- First/second/third period, season-long, series, unknown-suffix leagues,
  multi-player combos and Fantasy Score.
- Migrations, roster creation from provider names, automatic alias creation,
  or changing other sports' ingest cadence or resolver behavior.
- Push, deploy or remote workflow dispatch. Runner acceptance is a later check.

## Build loop

Build one step at a time, never the whole feature at once.

1. Lay out the next step before editing code.
2. Implement just that step, including its logic tests.
3. Show the diff and the evidence for its done-when.
4. Wait for review before the next step. Checkpoint commits are optional and
   require approval and passing verification; `/complete` owns the final log
   and feature commit.

## Build steps

- [x] **Step 1 - Confirm provider contracts and define markets.** Use the
  existing PrizePicks helpers for one bounded leagues/board probe, honoring
  their retry budget. Record observed stat names, team codes, odds types and
  representative Time On Ice raw lines. Confirm the TOI unit from provider
  evidence, not just a plausible numeric range; consult provider rules if the
  payload is insufficient. Add `app/nhl/markets.py` with `NhlLineOnlyMarket`
  and `NHL_PROPS`, plus market/league-selection tests. *Done when:* the exact
  twelve-name map below is tested, only the full-game NHL league is selected,
  unsupported stat names remain logged/skipped, and the evidence records TOI's
  unit or explicitly keeps that one market unmapped until it can be confirmed.
  An empty board or exhausted 429 budget is recorded honestly, never called a
  successful live check. Existing 45a evidence can establish the other names.

- [x] **Step 2 - Resolve NHL names, teams and game dates.** Add pure NHL
  normalization/resolution helpers and tests. Reuse the existing
  `nfl_resolution` primitives as NBA does, without importing NBA code or
  changing NFL behavior. Fold accents on provider and stored candidate names;
  use NHL team codes, never provider positions. *Done when:* tests prove
  `TB` maps to `TBL`, observed remaining codes map correctly, folded names
  and explicit aliases resolve, same-initial surnames remain conservative,
  F versus C/L/R never causes a position rejection, and missing/ambiguous
  players and absent team/date inputs retain nullable links with reasons.
  A late evening game's next-day UTC timestamp links to its Eastern game day.
  Unknown team codes are not guessed into another NHL team; `ARI` and `UTA`
  remain distinct.

- [x] **Step 3 - Plug into shared storage and relink.** Add
  `nhl.get_player_candidates`, `NhlPropSource` implementing only
  `PropLineSource`, and `app.ingest.prizepicks_nhl`. Mirror the NBA CLI's
  flags and exit behavior and delegate persistence/relink to
  `prizepicks_props`. *Done when:* offline fixture tests prove NHL config
  reaches the shared pipeline, supported lines preserve provider id, decimal
  line, odds type and raw payload, unresolved lines are retained, and
  `--dry-run` writes nothing. `--relink` makes no provider request and
  changes only linkage/odds-type fields. An empty successful board stores
  zero rows; exhausted rate limiting exits 75. NHL-specific SQL filters
  every shared-table alias to literal `sport = 'nhl'`; shared SQL receives
  `sport='nhl'`. No projection/version/ranking code is added.

- [x] **Step 4 - Prove a live snapshot and relink.** Run dry-run, then one
  normal snapshot against the existing 0049 database, and then relink twice.
  Use read-only SQL through the repository or session scratch tooling to
  compare counts and links. *Done when:* record timestamp, supported count,
  stored count, per-market and odds-type counts, separate player/game link
  rates, and reasons for unresolved rows. Verify every non-null linked player
  and game belongs to NHL, all inserted segments are `full_game`, no NHL
  prediction rows were created, and relink preserves line values, original
  payloads, fetch timestamps and row counts. The second unchanged relink
  reports zero changes. Inspect one skater and one goalie linkage when posted.
  Explain legitimate missing roster/game rows; repair confirmed name variants
  only through reviewed aliases or normalizers. If no live board is available,
  leave this step pending and retain fixture evidence without claiming live
  acceptance. Do not repeatedly fetch to force a passing sample.

- [x] **Step 5 - Schedule snapshots and document operation.** Add
  `nhl-prop-lines.yml`: daily 17:15 and 22:45 UTC, September through June,
  plus manual dispatch. Use the existing Python 3.11 install pattern,
  `contents: read`, `DATABASE_URL` secret and explicit exit-75 error handling.
  Run only line ingest, with no prediction/freezing step. Add
  `prizepicks_nhl --relink` after the successful load in `nhl-ingest.yml`.
  Document commands and schedule in `AGENTS.md`, and keep implementation
  evidence in this spec. *Done when:* workflow commands succeed locally,
  schedule syntax and spacing from existing tennis/NFL/NBA PrizePicks jobs
  are reviewed, relink uses no provider call, and the final Verify gate passes.
  State that GitHub registration/runner acceptance remains unverified until
  an approved push and actual run. Update the local interview guide only if
  its existing claims about NHL ingestion need correction; keep it untracked.

## Files / areas

- New: `api/app/nhl/__init__.py`, `api/app/nhl/markets.py`.
- New: `api/app/core/nhl_names.py`, `api/app/core/nhl_resolution.py`.
- New: `api/app/services/nhl/__init__.py`,
  `api/app/services/nhl/prop_source.py`, `api/app/ingest/prizepicks_nhl.py`.
- Extend: `api/app/repositories/nhl.py` with the player-candidate query.
- Tests: NHL market, name/resolution and ingest/adapter tests under
  `api/tests/`, reusing existing shared-pipeline fixture conventions.
- Operations: `.github/workflows/nhl-prop-lines.yml`,
  `.github/workflows/nhl-ingest.yml`, `AGENTS.md`.
- Evidence and handoff: this spec; local ignored employer guide if applicable.
- Shared pipeline files are reference implementations. Change them only if a
  demonstrated NHL requirement cannot fit the existing interface, with review
  and regression tests first.

## Data / contracts

**Load-bearing: storage and market names.** Use `sport_prop_lines` with
`sport='nhl'`, `provider='prizepicks'`, `segment='full_game'`. Snapshots append;
repeated fetches intentionally produce history, not a unique provider-id row.
No schema migration is needed. Preserve the original numeric line in provider
units; never silently convert Time On Ice to the box-score seconds unit.

| Exact provider stat name | Stored market | Line unit |
|---|---|---|
| Shots On Goal | `shots_on_goal` | count |
| Points | `points` | count |
| Assists | `assists` | count |
| Goals | `goals` | count |
| Power Play Points | `power_play_points` | count |
| Blocked Shots | `blocked_shots` | count |
| Plus/Minus | `plus_minus` | signed count |
| Goalie Saves | `goalie_saves` | count |
| Hits | `hits` | count |
| Time On Ice | `time_on_ice` | minutes, confirmed by provider display label |
| Goals Allowed | `goals_allowed` | count |
| Faceoffs Won | `faceoffs_won` | count |

Map lowercase exact names through `SportPropConfig.market_aliases`.
`league_prefix='NHL'`, recognized suffixes `1P -> p1`, `SZN -> season`,
`board_segments={full_game}`, `period_label='week'`. Other suffixes return
None. Do not hardcode league id 8 as the selector. Combo names and Fantasy
Score remain unsupported even if posted. Do not add new aliases just because
a future market sounds similar.

**Load-bearing: linking.** NHL ids are already seeded by 45b. Candidates
come from NHL `sport_players` joined to NHL `sport_teams`; game index and
stored aliases come from `sport_props` with the NHL scope. Resolve each line
in memory after loading these once per run. Alias keys must use the same
folded-name key as lookup; preserve the existing alias table contract.
Player and game resolution remain independent: either id can be NULL.
Do not create players or games from PrizePicks hashes. Name resolution uses
no position because provider F differs from NHL C/L/R. Team normalization
maps only supported variants to NHL tri-codes. Preserve the existing
conservative resolution reasons and UTC-date/day-before game lookup.

**Load-bearing: line-only.** `NhlPropSource` has only config and resolver
loading. It is not a `SportPropSource` and joins no freezing/ranking registry.
`odds_type` is stored unchanged; do not infer allowed wager sides from demon
or goblin labels (45a observed some allowing both). Preserve raw provider
attributes for future review. Goalie lines are stored even when the starter
is unknown; ingest makes no claim that the goalie will play.

## Testing

- Each logic step ships passing pytest coverage in its own diff: market and
  league selection, normalization, ambiguity, aliases, game-date boundaries,
  and adapter delegation using mocked provider/database dependencies.
- Exercise actual existing parser/storage code with fixtures for skater and
  goalie lines, all odds types, unsupported combos, missing linkage, empty
  boards and exhausted 429 handling. Do not call external APIs in unit tests.
- Verify repository sport scoping and workflow commands through focused review
  and the live Step 4 checks; do not add a new test framework or browser suite.
- Focused regressions include existing sport-pipeline, sport-repository,
  NBA-resolution and NFL ingest tests. No frontend code changes are expected.
- Final gate from the repo root: `npm --prefix web run verify && cd api &&
  python -m pytest`, with the API venv active. In PowerShell run the two
  halves sequentially, using `api/.venv/Scripts/python.exe` for the API half.
- Manual try from `api/`: `.venv/Scripts/python.exe -m
  app.ingest.prizepicks_nhl --dry-run`; normal invocation stores a snapshot;
  `--relink` repairs existing linkage without fetching.

## Notes for the AI

- 45a and 45b are complete in the build plan and their archives. The generated
  overview still says 45b is next; the completed archive supersedes that stale
  progress text. 0049 and the four-season data load are recorded as applied.
- Branch from `master` as `feature/45c-nhl-prop-lines` during implementation.
  Leave parked 44b and all model evidence untouched. Read no holdout for model
  evaluation; this feature needs only identity and schedule data for linking.
- Keep SQL in repositories, pure helpers in core, and secrets in Settings or
  the existing workflow secret pattern. No NBA-module imports from NHL code.
- Use the existing provider retry helpers and Windows event-loop setup from
  `prizepicks_nba.py`. The existing dry-run counts supported fetched lines;
  it does not promise to calculate link rates or require a database session.
- Probe evidence goes here or in session scratch space, not an ad-hoc script
  under `api/`. Record any unresolved provider contract rather than guessing.
- No em dashes in new docs, comments or commit messages.

## Implementation evidence

### Step 1 - Provider contract (2026-10-23)

- Branch: `feature/45c-nhl-prop-lines`. Spec approved by invoking `/implement`.
- One successful leagues read and one full-game board read through the existing
  helpers. The initial sandboxed attempt could not connect; the network-enabled
  probe succeeded without a 429. No database writes were made.
- Catalog: NHL (8), NHL1P (227), NHL2P (234), NHL3P (226), NHLSZN (236),
  NHLP (282), NHL SERIES (251). Only NHL is selected for storage.
- Board: 880 parsed lines, 864 supported and 16 unsupported. Odds types across
  the whole board: standard 70, demon 717, goblin 93.

| Provider stat | Lines |
|---|---:|
| Shots On Goal | 154 |
| Points | 210 |
| Assists | 158 |
| Goals | 197 |
| Power Play Points | 42 |
| Blocked Shots | 35 |
| Plus/Minus | 19 |
| Goalie Saves | 26 |
| Hits | 9 |
| Time On Ice | 8 |
| Goals Allowed | 4 |
| Faceoffs Won | 2 |
| Shots On Goal (Combo), Goals (Combo), Goalie Saves (Combo) | 7, 3, 2 |
| Goalie Fantasy Score | 4 |

- Single-player team codes: ANA, BUF, CHI, COL, MTL, NSH, PHI, PIT, TB,
  WSH. Combo teams include CHI/MTL, COL/TB and MTL/CHI; combo stats remain
  unmapped. Goalie Fantasy Score is newly observed and remains unmapped.
- **TOI unit confirmed by primary provider payload:** all eight Time On Ice
  projection attributes say `stat_display_name="Minutes"`. Examples:
  Spencer Knight (CHI, G), projection `16126764`, line 59.25;
  Artyom Levshunov (CHI, D), `16095539`, 20.75;
  Cale Makar (COL, D), `16095542`, 22.75. Preserve numeric minutes, never
  reinterpret 20.75 as a clock reading or convert storage to seconds.
  Source: `https://api.prizepicks.com/projections?league_id=8&per_page=250&single_stat=True`.
- TOI is posted for goalies as well as skaters, refining 45a's smaller sample.
  Configuration does not restrict any market by position. No settlement or
  claim about TOI overtime treatment is introduced here.
- Offline tests cover twelve exact mappings, league exclusions, unsupported
  logging counts and preservation of TOI lines/raw unit labels for F/D/G.
- Verification passed: focused `test_nhl_markets.py` (31 tests), web Verify
  (815 tests, typecheck and production build), and API pytest (3,896 tests).
  Used `npm.cmd --prefix web run verify` because PowerShell blocks npm.ps1,
  then `.venv/Scripts/python.exe -m pytest` from `api/`. Existing Vite chunk
  size and Starlette deprecation warnings remain. `git diff --check` passed.
- Step 1 approved in chat; owner chose to continue to linking without a
  checkpoint commit.

### Step 2 - NHL linking helpers

- Added pure `nhl_names` helpers for accent folding and the observed TB to
  TBL mapping. Other codes pass through uppercased, with ARI and UTA kept
  distinct. No speculative team aliases were added.
- Added `index_nhl_candidates` and `resolve_nhl_line`, reusing the existing
  resolver with folded provider/candidate names, pre-normalized NHL teams and
  no provider position. Explicit aliases use the existing provider-name key
  after folding. Player and game ids can be resolved independently.
- No NBA imports, I/O, SQL, provider requests or changes to shared NFL logic.
- Added 42 tests covering observed codes, accent folding on both sides,
  aliases, initial/surname ambiguity, name/team conflicts, missing inputs,
  position-label mismatch, independent links and local/UTC date boundaries.
- Focused NHL market/resolution and NFL/NBA resolver regression run:
  110 passed. Full gate: `npm.cmd --prefix web run verify` passed (815 web
  tests, typecheck, build), followed by `.venv/Scripts/python.exe -m pytest`
  from `api/` (3,938 passed). Existing build chunk-size and Starlette
  deprecation warnings remain; `git diff --check` passed.
- Manual check from `api/`: `.venv/Scripts/python.exe -m pytest
  tests/test_nhl_resolution.py -q`. It proves the resolver against fixed
  fixture identities/dates; live stored linkage is Step 4.
- Step 2 approved in chat; owner chose to continue. No commit made.

### Step 3 - Shared storage adapter and CLI

- Added the NHL-scoped player-candidate read to `repositories/nhl.py`;
  player and joined team aliases both carry literal NHL filters.
- Added `NhlPropSource` with only configuration and resolver loading. It
  loads candidates, game index and stored aliases once per run, then links
  in memory. No model versions, freeze/grade methods or registry entry.
- Added the `prizepicks_nhl` CLI with normal ingest, `--dry-run` and
  provider-free `--relink`. Exhausted provider rate limiting returns exit 75.
  Shared parser, persistence and relink code remain unchanged.
- Seven offline tests exercise the actual shared parser and SQL writers
  against fixture data and a mocked session: skater/goalie lines, nullable
  player links, decimal minutes, raw payloads, three odds types, skipped
  combos, no-session dry-run, empty successful board, provider-free relink
  with odds-type backfill, unchanged relink, empty catalog and exhausted 429.
- Focused NHL ingest plus shared ingest/pipeline tests: 11 passed. Final
  gate: `npm.cmd --prefix web run verify` passed (815 tests, typecheck and
  build), then `.venv/Scripts/python.exe -m pytest` from `api/` passed
  (3,945 tests). Existing chunk-size and Starlette warnings only.
- CLI `--help` succeeded; `git diff --check` passed. Manual dry-run from
  `api/`: `.venv/Scripts/python.exe -m app.ingest.prizepicks_nhl --dry-run`.
  Actual board/database execution remains Step 4, after this step's review.
- Step 3 approved in chat; owner chose to continue. No checkpoint commit made.

### Step 4 - Live snapshot and relink acceptance

- Checked through the real ingest entry point and shared storage pipeline on
  2026-10-23. Snapshot verification ran 19:52:35 to 19:53:24 UTC
  (2:52:35 to 2:53:24 pm America/Chicago).
- CLI dry-run succeeded with 942 supported lines. One subsequent normal
  snapshot returned and stored 941 lines; the live board changed between
  reads. This is not a dropped insert: the normal run's count exactly matched
  the newly stored row count. No additional snapshot was fetched.
- Before: zero NHL prop rows, zero NHL predictions. After: 941 NHL prop rows,
  ids 190854 through 191794, zero NHL predictions.
- Player links: 941/941 (100%). Game links: 941/941 (100%). Resolution reasons:
  unique_name 917, full_name 24. Unresolved rows: none; no aliases needed.
- Odds types stored: standard 61, demon 783, goblin 97. Unsupported types
  logged and skipped: Shots On Goal (Combo) 7, Goals (Combo) 3, Goalie Saves
  (Combo) 2, Goalie Fantasy Score 4.

| Stored market | Rows |
|---|---:|
| shots_on_goal | 154 |
| points | 226 |
| assists | 182 |
| goals | 234 |
| power_play_points | 42 |
| blocked_shots | 35 |
| plus_minus | 19 |
| goalie_saves | 26 |
| hits | 9 |
| time_on_ice | 8 |
| goals_allowed | 4 |
| faceoffs_won | 2 |

| Acceptance criterion | Observed result |
|---|---|
| Snapshot count matches inserts | Pass: 941 returned, 941 new rows |
| Linked ids belong to NHL | Pass: scoped player/game joins found zero invalid links |
| Full-game only | Pass: all 941 inserted segments were full_game |
| No projection/prediction writes | Pass: NHL prediction count stayed zero |
| Skater sample | Pass: Cole Caufield, source player 8481540, MTL, shots_on_goal 7.50, game 2026020166 |
| Goalie sample | Pass: Spencer Knight, source player 8481519, CHI, goalie_saves 38.50, game 2026020166 |
| Local-date linkage | Pass: both samples have game_date 2026-10-23 and matching provider/game start 2026-10-24 00:00 UTC |
| First relink | Pass: zero rows changed |
| Second relink | Pass: zero rows changed |
| Preservation | Pass: row count, complete-row hash and immutable-field hash unchanged after each relink |

- The preservation comparison included original raw payloads, numeric lines,
  start/fetch timestamps, provider ids, markets and segments. Immutable-field
  SHA-256: `8c2e288bd16f14468b47fc5fdf3f889d8bf30b71d86e6cd0ef7a2e12d6350098`.
  Complete-row SHA-256, also including links and odds types:
  `1b7464a9c8d22125c7c4a6c62243676e64603aed245e7878a41beeb2d3f8a38b`.
- Verification used session scratch Python through stdin, the actual `run`
  and `relink` functions, NHL-scoped read-only SQL and assertions. No scratch
  script was added under `api/`. The check skill's Step 4 criteria all passed.
- Only this evidence/spec changed in Step 4; Step 3's passing full Verify
  still covers the unchanged application code. `git diff --check` passed.
- Step 4 approved in chat; owner chose to continue. No commit, push,
  workflow dispatch or deploy made. Scheduling and documentation are Step 5.

### Step 5 - Workflow configuration and handoff

- Added `nhl-prop-lines.yml`: manual dispatch plus `15 17 * 1-6,9-12 *`
  and `45 22 * 1-6,9-12 *`, Python 3.11, dependency caching, contents-read
  permission and only the database secret. Ingest failures retain their exit
  code; exit 75 emits a visible rate-limit error. No freezing/prediction step.
- Reviewed against existing PrizePicks schedules: tennis 13:00 UTC; NBA
  16:30/22:15; NFL Thursday 20:00, Saturday 23:00, Sunday 15:00, Monday
  20:00. NHL times are offset, but GitHub delays can still cause overlap.
- Added provider-free NHL relink after the daily schedule/box-score load.
  Ran the exact relink module command locally: 941 linked, zero changed,
  exit 0. The snapshot command's shared run implementation was exercised
  once in Step 4; no extra snapshot or schedule/stat reload was needed.
- Parsed both workflows with installed PyYAML BaseLoader, retaining the `on`
  key as text. Git Bash syntax check passed for the snapshot shell block;
  mocked provider-process exits 0, 75 and 1 each preserved their status, and
  only 75 emitted the rate-limit annotation. This is local syntax and exit
  behavior evidence, not GitHub runner acceptance.
- Updated AGENTS commands and operational limits. Updated the local ignored
  employer guide's identity-resolution examples with the measured NHL result
  and explicit publication/display/model boundaries. `git check-ignore`
  confirms the guide remains ignored; it is not staged.
- Final Verify halves ran sequentially: `npm.cmd --prefix web run verify`
  passed (815 tests, typecheck, production build), then
  `.venv/Scripts/python.exe -m pytest` from `api/` passed (3,945 tests).
  Existing Vite chunk-size and Starlette deprecation warnings remain.
  `git diff --check` passed.
- Ledger reviewed: F-09 (P3) and F-12 (P2) remain unverified; no P0/P1
  blocker and no finding repaired or reclassified by this feature.
- All five steps are implemented, locally verified and approved in chat.
  No checkpoint commit, merge, push, remote dispatch or deployment has
  occurred before completion. GitHub workflow
  registration and first runner acceptance remain unverified.
- After Step 5 approval, `/complete` owns the final safety/invariants pass,
  archive, build-plan checkbox, feature commit and explicitly approved merge.
  Pushing requires separate approval.

## Completion review (2026-10-23)

- All five steps approved. The feature adds line-history ingestion only;
  45d-45f and the parent NHL item remain unchecked.
- Final safety and invariants review: clean. NHL-specific SQL filters both
  players and teams, shared queries receive the NHL scope, core helpers are
  pure, shared pipeline code and model registries are unchanged, and no
  secret or heavy request-time work was introduced. No Blueprint adapter
  skill changed, so no matching adapter edit is needed.
- Verify passed in this session: `npm.cmd --prefix web run verify` (815
  tests, typecheck and production build), then the API venv's
  `python -m pytest` (3,945 tests). These are the documented Verify halves
  for PowerShell. Live behavior and workflow shell checks are recorded above.
- No model fit, scoring or holdout evaluation ran. Identity and game-index
  reads include stored prior-season players and schedules for linking, not
  outcomes or projection evaluation. Existing model versions, evidence and
  sample rules remain unchanged.
- F-09 (P3) and F-12 (P2) remain unverified in the findings ledger; neither
  was resolved, reclassified, removed or archived by 45c.
- The ignored employer interview guide was updated locally with the measured
  NHL identity-resolution example and remains excluded from the commit.
- Manual try from `api/`: `.venv/Scripts/python.exe -m
  app.ingest.prizepicks_nhl --dry-run`. It fetches/counts supported full-game
  lines without opening a DB session. `--relink` uses stored data only.
- GitHub workflow registration/runner acceptance and deployment remain
  unverified. No remote operation is authorized by this completion request.

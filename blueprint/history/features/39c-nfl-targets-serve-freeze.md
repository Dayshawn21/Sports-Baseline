# Feature: Serve and freeze NFL Rec Targets

**From build-plan:** feature 39c
**Status:** completed implementation; work commit prepared, merge awaiting approval
**Branch:** `feature/nfl-targets-serve-freeze`
**Dependencies:** completed 39a and 39b

## Goal

Show PrizePicks Rec Targets beside its fixed `nfl-targets-v1` reference
projection across the existing NFL slate, prop board, game and player flows,
and freeze that same projection before kickoff after each line snapshot.
Keep the nine v4 markets and their forward-check sample unchanged.

39b's verdict was **hide**, so Rec Targets has no served P(over), no P(under)
and no betting recommendation. A projection-line gap describes the difference
between a season average and a stored line; it does not establish an edge.

## Design reference

Extend the existing Lineform NFL tables, prop rows and evidence drawer. This
is a data addition, not a visual replication or redesign; no new mockup or
theme port is needed. No `prototypes/` directory exists at specification time.
Reuse the current fonts, spacing and gray NFL reference styling.

## In scope

- Project linked Rec Targets lines for RB, WR and TE on REG weeks 1-18,
  full-game, standard payout only. Store other provider lines as before,
  but do not project or freeze unsupported Rec Targets positions, segments
  or payouts.
- Serve exactly `project_targets(input)` with its selected defaults and
  pre-week valid target history. Preserve missing/thin baselines as null.
- Promote `receiving_targets` from the line-only market enum into
  `NflPropMarket`, preserving its stored string and provider alias. Keep
  the eight other line-only markets intact.
- Separate the nine v4 markets from the widened modelled-market universe
  wherever existing projection, replay or grading code assumes v4.
- Append independently assembled Rec Targets rows to `build_slate`; keep
  them out of v4's `_slate_line` and adjustment pipeline.
- Freeze mixed-model slate rows using each line's own versions and the
  existing insert-only storage and pre-kickoff guards.
- Display a neutral Rec Targets reference row and truthful evidence on all
  existing consumers of slate lines. Remove its duplicate line-only section.
- Prove v4 output/sample parity on fixed inputs and verify the new flow in
  the running app. Update the local employer guide when implementation is
  verified, if the guide exists.

## Out of scope

- 39d's Rec Targets settlement/ranking report, version selector, CLI/report
  expansion or `/nfl/model` slices. Those remain a separate feature.
- Changing 27i's ranking rule, any v4 coefficients, `nfl-pover-v1`, existing
  fit tables, or historical frozen rows.
- Fitting another targets distribution, showing the failed fit, re-reading
  the 2025 holdout, rerunning either targets backtest, or tuning projections.
- Targets DVP, usage, wind, game environment, moneyline or recent-form
  adjustments; recent games are descriptive evidence only.
- New providers, schedules, routes, database tables or migrations. Existing
  nullable fields and frozen-row keys already support this feature.
- Deploy, push, remote workflow runs or production database writes during
  verification. Operational refreshes are documented for release.
- Unrelated findings cleanup and changes to the user-owned plans or the
  pre-existing modified overview.

## Build loop

Build one step at a time, never the whole feature at once.

1. Explain the step, then implement only that step on the feature branch.
2. Show the diff, explain the changes and prove the done-when.
3. Run the documented Verify gate; obtain the owner's review before moving on.
4. After approval, check off the step and offer an optional checkpoint.
   `/complete` handles the work-level commit, archive and merge approval.

## Build steps

- [x] **Step 1 - Pin the existing v4 boundaries (server).** Define an explicit
  set of the current nine v4 markets rather than deriving v4 behavior from
  every member of `NflPropMarket`. Use it in v4 slate inputs, legacy
  `/nfl/projections`, replay/fit market iteration, 27a grading, the existing
  frozen ranking loader and coverage. Retain the general modelled-market
  allowlist for the wider serving universe. Apply market restrictions before
  latest-row selection so targets can never displace a v4 row. Do not change
  existing version-selection semantics or historical scoring.
  *Done when:* synthetic mixed-market fixtures exclude targets and all
  line-only markets from v4 readers; existing v4 outputs, ranking inputs,
  coverage and version strings equal their before-change values. The current
  nine-market paths still work before targets is promoted.

- [x] **Step 2 - Load live Rec Targets inputs separately (repository).** Add
  typed serving inputs in `repositories/nfl_targets.py`, separate from the
  completed-game replay driver. Select each provider prop's latest eligible
  linked standard/full-game targets line for the requested REG season/week,
  with deterministic timestamp/id ties and a strict pre-kickoff line cutoff
  when kickoff is known. Batch-load completed REG targets history strictly
  before the target week for those player IDs. Reuse the existing history
  semantics without requiring a future game's outcome or current-week stats.
  Supply identity, as-of team/opponent and display availability metadata;
  preserve the existing unmatched-line reporting convention for unresolved
  targets without trying to project them. Keep this loader dormant for now.
  *Done when:* recorded-SQL and row-mapping tests prove sport, game type,
  position, market, segment, payout, season/week and timestamp restrictions;
  future scheduled games load without outcome stats; no per-player queries
  or 2025 replay is needed. Null/negative/nonfinite history is never turned
  into a valid zero, and current/future-week history is excluded.

- [x] **Step 3 - Assemble the reference row and its freeze contract (server).**
  Add a dedicated targets row assembler, preferably in
  `services/nfl/targets.py`, using `project_targets` defaults. Return the
  existing `NflSlateLineSchema` with accurate baseline fields, descriptive
  targets history, null inapplicable adjustments and the targets model
  version. Add a guarded targets probability reader which checks the existing
  generated fit's display flag and projection-version compatibility; the
  checked-in hidden fit always yields null probabilities and null served
  probability version. Exercise the existing `prediction_row` serializer on
  these rows without activating serving yet.
  *Done when:* fixed input tests show round(mean, 2) with at least four valid
  counts in the chosen season, null below four, a valid zero projection,
  correct previous-season flags and exact parity with `project_targets`.
  The hidden, absent-position and version-mismatch probability cases return
  null, never 0.5. Frozen serialization preserves targets identity, versions,
  baseline evidence, line and fetch time without fabricating v4 adjustments.

- [x] **Step 4 - Publish and freeze mixed-model slate lines (server).** Move
  targets into the modelled enum and alias, remove its line-only rule and
  keep the other eight rules unchanged. Wire the targets reader/assembler
  into `build_slate` alongside the untouched v4 assembly, including accurate
  line/unmatched counts. Keep the existing `NflPropSource`'s report identity
  as v4, while its freeze input contains both models through each row's own
  version. Do not add a second sport registration or grade targets yet.
  *Done when:* a mixed fixture returns both models and the current freezer
  produces targets rows under `nfl-targets-v1`, with null probability fields
  and probability version, while v4 rows are byte-for-byte equal after
  filtering out targets. Started and unknown-start games are not frozen;
  reruns use the existing insert-on-conflict-do-nothing behavior, including
  the null probability-version key. Targets is absent from the line-only
  endpoint and existing v4 grading/coverage inputs. A no-targets slate is
  unchanged and legacy projection/replay entry points do not raise on the
  expanded enum.

- [x] **Step 5 - Show targets as a reference across the existing UI (web).**
  Include Rec Targets in the prop board and the game/player current-line
  flows and remove it from the web line-only list. Give it neutral reference
  and gap wording, suppress OVER/UNDER pick badges and recommendation ranks,
  and keep its gap gray. Ensure usable reference rows are discoverable in
  the normal board flow rather than visible only behind an unrelated
  alternate-line toggle. Adapt the evidence drawer's method/breakdown text
  to the season-average model: inapplicable v4 adjustments read as not used,
  and a brief note explains that P(over) is unavailable because validation
  did not pass. Preserve the behavior of every v4 row.
  *Done when:* helper tests cover targets labels, grouping, null projection,
  zero projection and no pick/rank/probability text; unchanged v4 fixtures
  retain their values and presentation. Browser checks on `/nfl`,
  `/nfl/board` (the Props tab), `/nfl/game/:id` and `/nfl/player/:id` show the reference via
  their existing prop rows/details, with no duplicate line-only block.
  A missing baseline shows an unavailable value and its reason, not zero.

- [x] **Step 6 - Prove integration and document operation.** Run the full
  Verify gate and `/check` for the behavioral criteria. Inspect one fixed
  current-week slate with and without targets using the same inputs/clock;
  compare v4 payloads and report inputs, not outcomes for a new verdict.
  Use `python -m app.ingest.nfl_prop_predictions --dry-run` when configured
  data is available; exercise insert idempotency with test doubles rather
  than writing the shared database. Confirm the existing workflow still
  runs ingest, freeze, then slate snapshot, and document that an updated
  snapshot is required before hosted pages can show targets. Update the
  local employer guide to describe verified reference serving/freezing and
  the still-deferred grading, never claiming deployment.
  *Done when:* the spec records exact automated results, browser/API
  evidence, v4 parity and dry-run counts or the explicit environmental gap.
  If no eligible real line is available, use a deterministic API fixture in
  the running UI, label it as fixture evidence, and leave real-data proof
  pending. Read-only verification never writes frozen rows or snapshots.

## Files / areas

| Area | Expected files and purpose |
|---|---|
| Market boundary | `api/app/nfl/markets.py`, `api/app/core/nfl_line_only.py`, explicit v4 iterations in `api/app/routers/nfl.py` and affected replay/fit modules |
| Repository | `api/app/repositories/nfl.py` for preserved v4 filters; `api/app/repositories/nfl_targets.py` for dedicated live line/history inputs |
| Targets serving | New `api/app/services/nfl/targets.py`; existing pure targets projection and generated probability modules are consumed, not refitted |
| Slate/freezing | `api/app/services/nfl/slate.py`, `prop_predictions.py`, `prop_source.py`; change the shared freezer/storage only if required by a demonstrated contract gap |
| Web | `web/src/utils/nflLineOnly.ts`, `nflPropBoard.ts`, `nflPropCards.ts`, `nflPropDetail.ts`, `nflSignal.ts`, affected row/drawer consumers and adjacent helper tests |
| Tests | Targets repository/serving tests; existing market, line-only, slate, freeze, ranking-loader and coverage tests; focused web helpers |
| Operations | Inspect `.github/workflows/nfl-prop-lines.yml` and existing snapshot path; no new job or schedule expected |
| Documentation | This spec's evidence; `docs/SportApp-Employer-Interview-Guide.md` if present, always untracked and unstaged |

## Data / contracts

These contracts are load-bearing for 39d.

| Contract | Required behavior |
|---|---|
| Stored market | `receiving_targets`, alias `rec targets`; never rename existing line rows |
| Modelled membership | Ten modelled markets after promotion; targets and the eight remaining line-only markets are disjoint; v4's explicit market set stays at nine |
| Eligibility | RB/WR/TE, REG weeks 1-18, full game, odds type exactly `standard`; unsupported targets lines remain stored without projected/frozen output |
| Input history | Completed REG games strictly before `(season, week)`; count finite, nonnegative targets only, including real zeros; apply `choose_baseline_season` to valid counts |
| Projection | `project_targets(input)` defaults; no selected moneyline/recent arm and no v4 adjustment; at least four valid observations in the chosen season; rounded to two decimals |
| Slate shape | Existing camelCase `NflSlateLineSchema`/`NflSlateLine`, no new endpoint or mandatory response field; baseline season/reason/count and quality flags come from targets' own evidence |
| Gap | Existing nullable `edge` field is projection minus line for eligible usable rows; zero is a valid projection; no usable projection means null gap; UI identifies this as a reference gap |
| Inapplicable evidence | Opponent/usage adjustments and their sample counts, sportsbook and snap-model fields are null; opponent-allowed history is empty unless independently supported as descriptive targets evidence; never copy v4 yards/receptions evidence |
| Probability | `NFL_TARGETS_OVER_PROBABILITY_VERSION = nfl-targets-pover-v1` identifies 39b's candidate, but is not a served version while `SHOWN = False`; `p_over`, `p_under`, `over_probability_version` are all null today |
| Projection version | API `projectionModelVersion` and frozen `model_version` are `nfl-targets-v1`; never the v4 version |
| Frozen key | Existing `(prop_line_id, model_version, over_probability_version)` with NULLS NOT DISTINCT and insert-only semantics; targets with null P(over) still freeze |
| Freeze evidence | Existing feature snapshot captures baseline count/season/reason, nullable adjustments, line, odds type, market, segment and fetched time; `generated_at` and line fetch time must precede a known kickoff |
| v4 sample | `opponent-dvp-tg-blend-usage-snap-v4`, `nfl-pover-v1`, current latest-row selection, counts and verdict inputs stay unchanged; targets is filtered before legacy grading/coverage selection |
| Future grading | 39d must settle targets on the `targets` stat and select each model/version's own frozen sample; 39c does not widen v4's 27a/27j reports or pass targets through the missing-stat fallback |

No history is backfilled into frozen predictions. Old stored slate copies
remain readable with their existing shape. Production continues to serve
stored snapshots and return the established unavailable response when missing;
it must never build this expanded slate inside the 512 MB request process.

## Testing

- Both existing runners are enabled. Every step that adds logic includes its
  focused pytest or Vitest tests in the same diff; no new runner is needed.
- Repository tests record SQL and use fixed rows/clocks. Cover targets line
  tie-breaking, no current/future-week history, cross-sport and non-REG
  rejection, supported positions/payouts/segments, kickoff cutoff, empty
  input and unmatched linkage. Do not query provider APIs in tests.
- Serving tests cover four versus three valid observations; missing, NaN,
  negative and zero counts; current versus prior-season baseline; all-zero
  history; correct targets recent history; null adjustments; failed-display
  and wrong-fit-version suppression. Never rerun 39b to prove its gate.
- Mixed slate/freezing tests compare the same fixed inputs before/after,
  filter targets out, and assert every remaining line and report input is
  identical. Include no games/no targets, missing baseline, kickoff equal
  to now, already-started games, unknown start and duplicate freeze attempts.
- Web helper tests cover neutral reference wording, target row discovery,
  no recommendation rank/badge, hidden probability, and intact v4 grouping
  and sorting. Browser evidence covers actual row/drawer behavior and the
  existing loading/error/empty states; no component test suite is added.
- Final automated gate from the root with the API venv active:
  `npm --prefix web run verify && cd api && python -m pytest`.
  On this PowerShell host run the two documented halves sequentially when
  needed: `npm --prefix web run verify`, then from `api/`,
  `.venv\Scripts\python.exe -m pytest`; stop if either fails.
- Manual path: start the API on 8000 and web on 3001; open the NFL slate,
  Props board, an eligible game's page and its player's page; inspect the
  Rec Targets row and drawer, baseline count and gray gap. Inspect the
  `/nfl/slate?season=<season>&week=<week>` payload for the targets version
  and three null probability fields. Use `/try` for a fuller walkthrough.

## Notes for the AI

- Small enough for one feature spec with six reviewed steps; no build-plan
  split or new product decision is needed. Do not implement during `/feature`.
- 39a chose season average on 2024; 39b failed its one 2025 display check.
  This work deploys neither a newly validated model nor a betting edge.
- `NflPropMarket` currently drives filters, legacy projection loops and
  several fit/replay market lists. Promotion alone breaks assumptions and
  can relabel a mixed-model report as v4. Pin those boundaries first.
- `baseline_projection` cannot project targets. Never add a placeholder
  value there to make an enum iteration pass; use the dedicated function.
- The freezer already serializes each line's own model version; the source's
  single model-version property belongs to its existing report identity.
  Do not redesign the sport-agnostic protocol just to freeze another model.
- The shared web card helper currently labels every nonnull gap as a pick.
  Targets must bypass that recommendation wording, while its reference row
  remains easy to find. Preserve other markets' behavior.
- Repositories own all SQL; services orchestrate; core remains pure. Use
  concrete types, batched history loads and fixed clocks in tests.
- No shared Neon migration/write, production refresh, deploy or remote run
  is part of the read-only proof step. Document pending operational actions.
- The overview is a pre-existing dirty file and predates completed item 40.
  Item 40 does not change any 39c contract; use the 39a/39b archives and
  current source for this spec. Preserve that overview edit.
- Existing P2/P3 findings are not permission to widen scope. Any finding
  genuinely repaired by the required market boundary work is recorded as
  fixed only after implementation/review and must later be re-audited.

## Spec critique

- Separated the ten-market serving universe from the nine-market v4
  readers before promotion; prevented targets from changing legacy report
  counts, coverage, fit loops or latest-row selection.
- Locked null served probability versions as well as null probabilities;
  naming a failed candidate version is not serving its distribution.
- Added a dedicated valid-count history loader because v4's averages and
  short recent-history windows cannot reproduce 39a's baseline eligibility.
- Added neutral web copy and default discovery criteria because generic
  gap rows currently emit OVER/UNDER labels or can disappear behind filters.
- Kept 39d grading out while requiring the minimal legacy-reader isolation
  needed to make freezing a second model safe.
- Added snapshot-aware browser proof and dry-run-only database verification;
  a fixture check does not claim that hosted data or deployment is updated.
- Browser verification corrected the Props path to the existing `/nfl/board`
  hash route (`/#/nfl/board` locally); `/nfl/props` is not registered. No route
  or navigation behavior was changed.

## Operational handoff

- `.github/workflows/nfl-prop-lines.yml` already runs the existing commands
  in order: `app.ingest.prizepicks_nfl`, `app.ingest.nfl_prop_predictions`,
  then `app.ingest.nfl_slate_snapshot`. The last step has `!cancelled()` so
  it can refresh the stored slate even after an earlier failure. No new
  schedule, second freezer or workflow edit is required.
- After separately approved rollout, the line workflow on the updated code
  can ingest, freeze eligible new lines and store the updated slate. Targets
  has no historical freeze backfill. Frozen inserts remain insert-only.
- Hosted `/nfl/slate` reads `report_snapshots`; it cannot expose targets from
  an old stored copy. A separately authorized snapshot refresh must use the
  updated backend code. From `api/`, the existing command is
  `python -m app.ingest.nfl_slate_snapshot --weeks current` (current week and
  previous week); name `--season <year> --weeks <week>` for another week.
  These are operational write commands documented here, not run by this work.
- The API caches serialized slates for five minutes. Allow that cache to
  expire after a refresh, then reload the web data. A stored copy also wins
  in dev, so merely starting the updated code does not prove it is visible.
- Production still returns unavailable for a missing snapshot rather than
  building this heavy report inside its 512 MB request process. No migration
  or new environment variable is needed. Rollout/deployment is unverified.
- Future 39d must grade targets under its own model/version sample. This
  work keeps the nine v4 grading/coverage inputs isolated and does not
  adopt targets, expose its failed P(over), or re-read the 2025 holdout.

## Implementation evidence

### Step 1 (2026-10-19), approved

- Branch: `feature/nfl-targets-serve-freeze`; no checkpoint commit made.
- Added `NFL_V4_PROP_MARKETS` as the explicit nine-market boundary, retained
  the general modelled-market filter, and pinned legacy projections and the
  two enum-derived fit/replay market lists to v4.
- V4 slate, unmatched, 27a, frozen grading and coverage readers restrict
  markets before latest-row selection. Coverage also requires the frozen
  line's market to match the gradeable line's market.
- Seven new tests pin membership and fit order, exercise query predicates
  on synthetic mixed markets, and check the coverage market join. Existing
  projection, ranking and coverage expectations still pass. These are
  synthetic/recorded-SQL checks, not a shared-database before/after report.
- Focused command from `api/`:
  `.venv\Scripts\python.exe -m pytest tests/test_nfl_v4_markets.py tests/test_nfl_repository.py tests/test_nfl_game_environment.py tests/test_nfl_projection_harness.py tests/test_nfl_track_record_service.py tests/test_nfl_prop_source.py -q`:
  **142 passed**.
- Full Verify with API venv on PATH:
  `npm --prefix web run verify && cd api && python -m pytest`:
  **612 web tests, production build, 2,836 API tests passed**. Existing
  bundle-size and dependency-deprecation warnings only. The first restricted
  run could not load Vite config; the same gate passed with filesystem access.
- No new serving/UI behavior exists yet; no browser criterion applies to
  this boundary-only step. No provider request, backtest, shared database
  write or production refresh was performed.
- The owner approved Step 1 and continuation without a checkpoint. F-15 is
  marked fixed for the required frozen-loader guard; re-audit remains pending.
- The pre-existing overview edit is
  preserved; no employer-guide claim changes are warranted at this stage.

### Step 2 (2026-10-19), approved

- Added typed live line, history/opponent and unmatched-line records in
  `repositories/nfl_targets.py`. The two live readers remain uncalled by
  production services until Step 4.
- Eligibility and the pre-kickoff cutoff apply before latest-snapshot
  selection. The live line query requires no outcome/stat row. History is
  fetched once for distinct players, with the same completed REG pre-week
  observation semantics as the existing replay. A shared history mapper
  adds optional opponent labels without changing replay projection inputs.
- Added 12 tests in `test_nfl_targets_serving_repository.py`, covering query
  restrictions, scheduled/no-stat games, roster and availability metadata,
  batched history, missing/invalid/zero counts, current/future-week exclusion
  by the pure projection, missing start/line values and unresolved players.
- Focused command from `api/`:
  `.venv\Scripts\python.exe -m pytest tests/test_nfl_targets_serving_repository.py tests/test_nfl_targets_repository.py tests/test_nfl_targets_projection.py tests/test_nfl_v4_markets.py -q`:
  **68 passed**.
- Full Verify with API venv on PATH:
  `npm --prefix web run verify && cd api && python -m pytest`:
  **612 web tests, production build, 2,848 API tests passed**. Existing
  bundle-size and dependency-deprecation warnings only.
- Actual PostgreSQL probe: `SET TRANSACTION READ ONLY`, 15-second statement
  timeout, current-week lookup, both new readers, explicit rollback. For
  2026 week 6 it returned **132 eligible lines, 132 players, 132 lines with
  history, 0 unresolved lines**. The first restricted-shell connection
  failed; the read-only probe succeeded with network access. Only counters
  were printed; no projection scoring, model selection or backtest ran.
- No write, provider call, freeze, snapshot refresh or browser/UI change.
  The owner approved Step 2 and continuation without a checkpoint commit.

### Step 3 (2026-10-19), approved

- Added the dormant `services/nfl/targets.py` assembler. It calls
  `project_targets` with its selected defaults, builds valid pre-week recent
  and opponent history, retains availability metadata and leaves v4-only
  adjustment, book and snap fields null.
- Added a targets probability reader gated on eligibility, minimum baseline,
  `SHOWN`, matching projection version and position quantiles. The actual
  hidden fit yields null P(over), P(under) and served probability version.
  No fit, projection constant or existing freezer module was edited.
- Added 32 tests in `test_nfl_targets_service.py`: exact baseline parity,
  rounding, four versus three observations, real zeros, prior-season fallback,
  invalid/future history, descriptive opponent evidence, unavailable lines,
  availability flags, probability suppression and frozen serialization.
- Focused command from `api/`:
  `.venv\Scripts\python.exe -m pytest tests/test_nfl_targets_service.py tests/test_nfl_targets_projection.py tests/test_nfl_prop_predictions.py -q`:
  **67 passed**.
- Full Verify with API venv on PATH:
  `npm --prefix web run verify && cd api && python -m pytest`:
  **612 web tests, production build, 2,880 API tests passed**. Existing
  bundle-size and dependency-deprecation warnings only.
- Actual PostgreSQL probe: read-only transaction, 15-second statement timeout,
  current-week inputs, in-memory assembly and `prediction_row` serialization,
  explicit rollback. For 2026 week 6, **132 rows assembled, 132 projections,
  132 records serialized, 0 probabilities supplied**. Assertions checked the
  targets model version, all three null probability fields, and null v4
  adjustments in serialized evidence. Nothing was inserted or frozen.
- The assembler is not called by `build_slate` yet. No new endpoint or browser
  behavior exists at this step. No backtest, fit, outcome scoring, provider
  request, snapshot refresh or deployment ran.
- The owner approved Step 3 and continuation without a checkpoint commit.

### Step 4 (2026-10-19), approved

- Promoted `receiving_targets` and its existing alias into `NflPropMarket`;
  the stored string is unchanged. Removed its line-only rule; the eight
  remaining line-only rules and the nine-market v4 boundary remain intact.
- `build_slate` loads and independently assembles targets alongside v4,
  including accurate line/unmatched counts. The existing freezer and
  `NflPropSource` were not edited: per-row model versions flow through the
  shared pipeline, while the source's grading identity stays v4.
- Added mixed-slate/source/freezing tests and a mixed-model insert/rerun SQL
  test double. Updated enum, alias, line-only and v4 grading expectations to
  reflect the intentional membership change. No targets settlement was added.
- Focused command from `api/`:
  `.venv\Scripts\python.exe -m pytest tests/test_nfl_targets_slate.py tests/test_prizepicks_nfl.py tests/test_nfl_line_only.py tests/test_nfl_line_grading.py tests/test_nfl_repository.py tests/test_sport_props_repository.py tests/test_nfl_prop_source.py tests/test_nfl_v4_markets.py -q`:
  **181 passed**.
- Full Verify with API venv on PATH:
  `npm --prefix web run verify && cd api && python -m pytest`:
  **612 web tests, production build, 2,888 API tests passed**. Existing
  bundle-size and dependency-deprecation warnings only.

`/check` evidence for Step 4:

| Criterion | Observed evidence |
|---|---|
| Mixed slate and v4 parity | Read-only 2026 week 6 probe captured v4 inputs once, built without and with targets using the same clock, then compared the full JSON after stripping targets: identical. 9,317 v4 lines plus 132 targets, total 9,449. |
| Separate frozen versions | In-memory freeze preview: 645 rows, 638 v4 and 7 `nfl-targets-v1`; v4 rows identical to the targets-disabled build. Targets probabilities and served probability versions null. |
| Started/unknown starts | Real preview excluded 8,804 kicked-off rows. Focused mixed-model tests exclude both models at kickoff, after kickoff and with unknown start; missing-baseline targets remain freezable with nulls. |
| Nullable rerun key | Read-only `pg_indexes` inspection confirmed the existing unique `(prop_line_id, model_version, over_probability_version)` index uses NULLS NOT DISTINCT. SQL test double verifies unchanged keys/payload and ON CONFLICT DO NOTHING on rerun. No real insert was attempted. |
| Real CLI | `python -m app.ingest.nfl_prop_predictions --dry-run` with connection-level `default_transaction_read_only=on`: 645 rows previewed, 8,804 kicked-off rows excluded; nothing written. |
| Real API | Temporary Uvicorn server on loopback port 8013 with connection-level read-only DB access. GET health, current-week, slate, legacy projections and one game's line-only endpoint all returned 200. Slate: 9,449 lines, 132 targets, null probability fields. Legacy: nine markets. Line-only: no targets. |
| Snapshot contract | Only the temporary server's stored-slate lookup was bypassed in memory to exercise the existing dev live fallback. No source config or stored snapshot changed; hosted serving is not claimed. |

- The first temporary API harness used Windows' incompatible Proactor loop
  (health 200, DB route 500). Restarting only that harness with the selector
  loop required by Psycopg resolved it; the subsequent HTTP checks passed.
  Both temporary API processes were stopped after checking.
- Step 4's server criteria pass. Step 5's neutral reference wording and UI
  checks remain pending. Do not deploy this intermediate UI state.
- No provider call, paid request, database write, snapshot refresh, migration,
  refit, backtest, outcome-based adoption decision or deployment ran.
- The owner approved Step 4 and continuation without a checkpoint commit.

### Step 5 (2026-10-19), approved

- Added targets-specific reference helpers and 13 focused web test cases.
  Standard full-game targets appear in the default board rows, including
  missing baselines, sorted by player name rather than gap. They carry no
  recommendation rank or OVER/UNDER label and do not inflate rateable counts.
- Shared board/game tables use Reference and descriptive gray gaps; the
  player row and slate digest identify targets as references. Removed targets
  from the web line-only list, retaining the eight other markets and rejecting
  stale duplicate targets payloads. Existing v4 helper fixtures still pass.
- The evidence drawer shows the season average, its valid-game baseline and
  descriptive history. Matchup and usage read Not used. It suppresses P(over)
  values and explains the failed calibration check, even if a malformed
  targets payload carries an old probability or v4 adjustment.
- Focused NFL helper run: **139 passed**. Final full Verify with API venv on
  PATH, `npm --prefix web run verify && cd api && python -m pytest`:
  **625 web tests, production build, 2,888 API tests passed**. Existing
  bundle-size and dependency-deprecation warnings only. `git diff --check`
  passed, with the existing overview line-ending warning.

`/check` evidence for Step 5:

| Criterion | Observed evidence |
|---|---|
| Default board discovery | Actual read-only 2026 week 6 slate: Rec targets pill has seven upcoming reference rows with Show all lines off; no numbered ranks or OVER/UNDER badges. The summary separates 39 v4 rateable rows across nine markets from seven reference rows. |
| Drawer method | Actual Antonio Williams row: reference 4.4 versus line 3.5, descriptive +0.9 gap, five-game 2026 season average, Matchup and Usage Not used, hidden P(over) explanation. |
| Game/player navigation | Followed the drawer's existing game link to `/#/nfl/game/93`, then Antonio Williams to `/#/nfl/player/58997`. Targets appear through their prop rows and open the same reference evidence. The game has one targets table and no duplicate line-only section. |
| Slate consumer | Actual `/#/nfl` renders normally. A temporary browser-only enlarged-gap fixture makes targets enter the existing largest-gap digest and displays Rec targets reference and reference value, without a pick or rank. No stored data changed. |
| Missing and zero | Temporary browser-only fixtures on the real board: null projection and three valid games show -- and the fewer-than-four reason; a real zero shows 0.0 with a neutral -3.5 reference gap. Both remain visible by default with no rank or pick. |
| Responsive layout | Checked 1440px desktop and 390px mobile board, drawer and navigation flows. No horizontal document overflow. Corrected a narrow mobile table caption discovered during inspection. |
| Loading/empty/error | Browser-only delayed response shows Loading NFL prop board; empty slate shows no upcoming lines; intentional 503 shows Failed to load data and Retry. Fixtures were removed and actual data restored afterward. |
| Runtime errors | Successful missing/zero/digest fixture flows captured zero page errors and zero failed API responses. The separate error-state check intentionally returns 503. Earlier harness-only wrong-route warnings are not counted as clean-run evidence. |

- Visually inspected screenshots retained locally in ignored `.playwright-mcp/`:
  `39c-step5-board-drawer-desktop.png`,
  `39c-step5-player-drawer-desktop.png` and
  `39c-step5-board-drawer-mobile.png`.
- The temporary API used read-only connections and bypassed only its in-memory
  slate snapshot lookup to exercise dev live fallback. Hosted snapshots and
  deployment remain unchanged. No database write, provider call, fit, backtest,
  commit or push ran. Step 6 operational proof/documentation remains pending.
- The owner approved Step 5 and continuation without a checkpoint commit.

### Step 6 (2026-10-19), approved

- Added the Operational handoff above after inspecting the actual line
  workflow, slate snapshot CLI, stored-snapshot selection and five-minute
  serialized-response cache. The existing ingest, freeze, snapshot order
  already supports mixed models. No workflow or production path was edited.
- Updated the existing targets explanation in the local employer interview
  guide. It describes locally verified reference serving, separate-version
  freeze preview, unchanged v4 output and the missing/zero distinction. It
  explicitly keeps deployment and snapshot refresh pending, and targets
  settlement/grading deferred to 39d. Confirmed ignored, untracked, unstaged.
- Final exact Verify command, API venv first on PATH:
  `npm --prefix web run verify && cd api && python -m pytest`:
  **48 web test files, 625 web tests, production build and 2,888 API tests
  passed**. Only the existing large-bundle warning and dependency deprecation
  warning appeared. No source changes followed this run. `git diff --check`
  passes; the pre-existing overview has its existing line-ending warning.

Final behavioral `/check` review uses the actual Step 4 API/CLI and Step 5
browser evidence recorded above; those checks remain applicable to the same
product source. No repeat shared-database read or browser session was needed
for this documentation-only step.

| Acceptance item | Final result |
|---|---|
| Current-week v4 parity | Pass: same captured inputs/clock; 9,317 v4 lines byte-identical after removing 132 targets from the 9,449-line slate. No new model verdict was computed. |
| Mixed freezing and guards | Pass: actual read-only CLI preview 645 rows (638 v4, seven targets); 8,804 kicked-off rows excluded. Unit fixtures cover equal/after kickoff, unknown start and missing baseline. |
| Idempotency | Pass at the authorized boundary: mixed-model insert/rerun test double and actual read-only NULLS NOT DISTINCT index inspection. Real shared-database inserts were intentionally not exercised. |
| API and UI | Pass locally: actual endpoints, neutral reference rows and drawer, game/player navigation, no duplicate line-only targets, desktop/mobile and missing/zero/loading/empty/error fixtures. Exact routes and screenshots are recorded in Step 5. |
| Operations | Pass by source inspection: existing workflow order and stored-snapshot requirement documented. No workflow was dispatched and no hosted snapshot was refreshed. |
| Hosted behavior | Unverified: rollout and fresh hosted snapshots require separate authorization. The local API proof used read-only DB connections and an in-memory dev snapshot bypass. |

- Invariants review verdict: **clean for the feature diff**, using the
  repository's invariant checklist. Checked new/shared NFL SQL sport filters,
  the targets-specific market/eligibility restriction and explicit nine-market
  v4 subset before latest selection, unchanged odds-provider readers, pure
  core/shared import boundaries, separate model versions, hidden probability,
  unchanged fit/ranking constants, neutral reference colors and unchanged
  production snapshot-only serving. No NBA behavior, credential/admin path or
  generated fit was changed. This is not an independent general code audit.
- Findings remain unchanged by this step. Open: F-07 (P3), F-08 (P2), F-13
  (P3), F-14 (P3), F-20 (P3). Fixed: F-15 (P3), awaiting independent `/audit`.
  Unverified: F-09 (P3), F-12 (P2). No open/fixed P0 or P1 blocker exists.
- Branch remains `feature/nfl-targets-serve-freeze`; all feature work is
  uncommitted. The pre-existing overview edit is preserved. No provider
  request, paid call, shared-database write, migration, fit, backtest,
  snapshot refresh, deploy, commit or push was performed in this step.
- The owner approved Step 6. All six implementation steps are checked off;
  no checkpoint commit was requested. `/complete` is the next action for
  the work-level commit, archive and build-plan bookkeeping, and merge only
  with approval. Push remains a separate approval.

### Approved operational follow-up (2026-10-19)

- The owner's normal localhost page initially received the old stored 2026
  Week 6 snapshot: 9,317 lines and zero targets. A read-only comparison
  confirmed that the HTTP response was byte-identical to that stored copy.
- The owner explicitly approved refreshing this shared snapshot after being
  told it also affects the hosted demo. Ran from `api/`:
  `.venv\Scripts\python.exe -m app.ingest.nfl_slate_snapshot --season 2026 --weeks 6`.
  The CLI stored exactly one week: 14 games, 9,449 lines, 15.1 MB.
- Read back the committed snapshot with read-only connections and confirmed
  132 targets rows, all `nfl-targets-v1`, with null P(over), P(under) and
  probability version. This separately approved snapshot write does not
  change the earlier read-only verification record. No frozen prediction
  inserts, provider requests, code deployment, commit or push were run.
- After the existing five-minute API cache expired, the normal localhost
  proxy returned all 9,449 lines including 132 targets. Reloading the normal
  `http://localhost:3001/#/nfl/board` now shows the Rec targets category and
  seven unranked reference rows without enabling Show all lines. This check
  used the saved snapshot directly, with no fixture or snapshot bypass.
- The normal WAS @ SF game page also shows exactly one Rec targets table;
  selecting WR displays Antonio Williams, Mike Evans, Stefon Diggs and
  Terry McLaurin in that reference table.

## Completion

- All six steps approved by the owner. Final Verify passed: 625 web tests,
  production build and 2,888 API tests. The owner also confirmed targets
  visible on localhost after the approved Week 6 snapshot refresh.
- 39c is complete in the build plan; parent 39 remains open for 39d.
- No resolved findings need archival. Unresolved ledger entries retain
  their IDs and statuses, including F-15 fixed pending independent audit.
- The pre-existing overview edit is excluded from the work commit. The
  interview guide remains local, ignored and unstaged.
- No code deployment or push is included. Merge awaits explicit approval.

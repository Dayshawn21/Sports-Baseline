# Feature: Rec Targets in the forward check

**From build-plan:** feature 39d
**Status:** completed implementation; owner approved local squash merge
**Branch:** `feature/nfl-targets-forward-check`
**Dependencies:** completed 39a, 39b and 39c

## Goal

Settle frozen Rec Targets predictions under their own model identity and show
their coverage, settled-call funnel and ranking slices beside the existing v4
record on `/nfl/model`. The CLI and weekly workflow report the same separate
records. Preserve the nine-market v4 sample and its pre-registered rule.

39b failed its probability display check. Rec Targets rows therefore have no
P(over), P(under) or served probability version. Settlement and coverage can
grow, but probability-based picks cannot. This feature makes that limitation
visible; it does not validate the reference projection or enable betting.

## Design reference

Extend the existing `/nfl/model` page, `NflRankingSlices` and
`web/src/pages/nfl-model.css`, using the current headings, gray reference
styling and responsive layout. This is a reporting addition, not a visual
replication or redesign. No `prototypes/` directory exists at spec time.

## In scope

- A read-only targets frozen-line loader and coverage query, separate from
  existing v4 queries, with `receiving_targets` settled against weekly
  `targets` rather than receptions or a missing-stat fallback.
- The two current report identities: v4 with `nfl-pover-v1`, and
  `nfl-targets-v1` with a null served probability version. Select each
  independently, before targets latest-row selection and coverage counting.
- Reuse 27i/27j's pure settlement/ranking pieces and finished-week guard;
  share report construction between API and CLI. Add only the small shared
  typing/loader adaptation needed to accept a null report probability version.
- Optional `model_version` on the existing ranking endpoint, defaulting to
  v4; separate cache and web query keys for each model identity.
- Two labelled report sections on `/nfl/model`, with independent loading,
  error and empty states. Targets show standard over/under progress, neutral
  reference wording, and why no picks accrue.
- A CLI model selector and both records in the existing weekly workflow
  Summary, after the stats load; no new schedule or provider request.
- Fixed-input v4/NBA regression proof, running API/browser evidence and
  an update to the local employer guide if it exists.

## Out of scope

- Fitting, enabling or substituting a targets probability; rerunning 39a,
  39b, any 2025 holdout command or any tennis/NBA validation.
- Changes to projection coefficients, version strings, ranking thresholds,
  payouts, ladder collapse, verdict samples, finished-week semantics or
  adoption decisions. No 27h ranking/pick activation or signal-color change.
- Historical replay, reconstruction or backfill of frozen targets rows;
  grading current projections as if they were frozen forecasts.
- Expanding 27a, the P(over) fit panel, sportsbook prop grading or CLV to
  targets; new accuracy/calibration metrics or a new adoption rule.
- Arbitrary historical model discovery, a generic model management system,
  another sport registration, extra market eligibility or new providers.
- Schema migrations, new tables, snapshot formats, freeze/ingest changes,
  production data writes, remote workflow dispatch, deployment or push.
- Unrelated findings repairs or edits to the two user-owned plans.

## Build loop

Build one step at a time, never the whole feature at once.

1. Explain the step, create/use the planned branch, then implement that step.
2. Show its diff and observable done-when evidence, with focused checks.
3. Obtain the owner's review before continuing; only approved steps are
   checked off. Offer an optional checkpoint after passing checks.
4. Run the documented Verify gate as the final automated gate; `/check`
   proves running behavior. `/complete` handles archive, work-level commit
   and merge only with the required approvals.

## Build steps

- [x] **Step 1 - Define targets settlement (pure server logic).** Add a
  small targets-specific settlement adapter using the existing pure
  settlement primitives. Take the frozen line and observed targets,
  distinguishing an absent player stat row from a present row with unknown
  targets. Do not widen `STAT_COLUMN_BY_MARKET`, which deliberately covers
  v4 only. *Done when:* tests prove over, under, integer-line push and real
  zero; no game stats means ungraded; no player row and positive offensive
  snaps means zero under the existing NFL convention; neither row nor snaps
  means void DNP. A present row with null, negative or nonfinite targets is
  excluded as `stat_unavailable`, never converted into an under. Missing or
  invalid stored lines also fail closed. No shared v4 settlement changes.

- [x] **Step 2 - Load targets frozen rows and coverage (repository).** Add
  batched read-only queries in `repositories/nfl_targets.py` or a focused
  sibling. Require NFL, REG weeks 1-18, completed games, linked RB/WR/TE,
  full-game standard targets lines and known kickoff. Restrict frozen rows
  to `nfl-targets-v1` with `over_probability_version IS NULL` before
  selecting each provider prop's latest eligible frozen prediction. Join
  observed targets, player-row presence, snaps and game-stats presence for
  Step 1. Add the matching coverage denominator and numerator.
  *Done when:* recorded-SQL and row-mapping tests cover sport/market/model
  isolation, null version matching, position/payout/segment eligibility,
  strict pre-kickoff timestamps and deterministic ties. Fixtures show a
  later unfrozen line does not discard an earlier frozen prediction, and
  another model/probability version cannot displace or cover a targets row.
  Existing v4 loaders and their selected rows/counts remain unchanged.

- [x] **Step 3 - Build independent ranking records (service).** Add a
  narrow report-only targets source/adapter, outside `PROP_SOURCES`, and
  route the two allowlisted report identities through the shared ranking
  machinery. If needed, extract a structural read-only ranking-source
  protocol from the larger ingest/freezing protocol; keep shared modules
  free of NFL imports. Allow a null expected/report probability version
  while retaining existing nonnull callers' null-row acceptance semantics.
  Add independent 15-minute single-flight cache entries by season, model
  and expected probability version. *Done when:* mixed-model fixtures
  produce separate records, targets settle without probability picks, empty
  targets records remain valid, and unfinished weeks cannot fix samples.
  Interleaved/concurrent loads and cached failures do not cross model or
  season boundaries. On fixed inputs/time, every v4 record field and NBA
  record field matches its pre-change value.

- [x] **Step 4 - Expose the model-specific record (API).** Extend
  `GET /nfl/model/ranking` with the optional allowlisted selector described
  below, preserving v4 as the default. Extend the NFL response typing for
  targets' null probability version without weakening NBA's nonnull public
  contract. Keep the router thin and errors consistent.
  *Done when:* API evidence shows the omitted selector and explicit v4
  selector return the same record, targets return their own model and a
  JSON null probability version, an empty sample returns 200, an unsupported
  selector returns 422, and a loader failure returns the existing generic
  503 without affecting the other cached report. Serialization/validation
  unit checks cover the changed data contract; no real DB integration suite.

- [x] **Step 5 - Report both models from the CLI/workflow.** Add
  `--model-version` accepting the two concrete model strings and `all` to
  `app.backtest.nfl_ranking_check`. Default omission preserves the existing
  v4-only command; `all` prints v4 then targets as labelled separate reports.
  Reuse the API's model resolver/loaders and pure rule. Change only the
  existing weekly ranking command to request `all`, keeping the stats-first
  order, Summary output and schedule. *Done when:* synthetic CLI/report
  checks show unchanged default v4 content, isolated counts for both models,
  truthful targets coverage wording and "P(over) not served" rather than
  `None` or a fitted/served version claim. Invalid selectors fail before DB
  loading; failure of either report fails the command without presenting a
  partial report as success. No workflow is dispatched during verification.

- [x] **Step 6 - Show both records on the model page (web).** Add the
  selector to typed transport and TanStack Query keys; retain the v4 call's
  existing default. Render v4 and Rec Targets as separate labelled sections
  with their own query states. Reuse the slice renderer with a small optional
  reference/eligibility presentation, preserving its NBA and v4 defaults.
  Targets show standard over/under; explain that goblin/demon are unsupported
  and P(over) failed validation. Keep the page summary explicitly scoped to
  v4 rather than combining denominators or suggesting one projection version
  describes both. *Done when:* pure helper tests cover labels, null version,
  zero picks, supported slices and summary scope; existing v4/NBA fixtures
  retain their values. Browser evidence shows both sections on desktop and
  phone, independent loading/error/empty states, readable gray targets
  progress and no claim that zero picks means a failed or adopted model.

- [x] **Step 7 - Prove parity and document the reporting boundary.** Run
  final Verify and `/check` against the API, CLI and model page. Compare
  both selectors using the same captured inputs/clock; confirm v4 identity,
  calls, exclusions, coverage, funnel, sample and verdicts are unchanged.
  Inspect query shape/runtime for the additional targets load to keep it
  bounded on the 512 MB host; no slate replay, broad frozen-table load or
  per-player query is allowed. Update the local employer guide if present.
  *Done when:* exact check results, API/browser evidence, v4/NBA parity and
  operational limits are recorded here. Empty real targets data is reported
  honestly; deterministic running-app fixtures prove settlement and unhappy
  paths, labelled as fixtures. No row is inserted to manufacture evidence.

## Files / areas

| Area | Expected files and purpose |
|---|---|
| Settlement and SQL | New focused targets settlement helper/tests; `api/app/repositories/nfl_targets.py` or a sibling for frozen grading and coverage; preserve `repositories/nfl.py` v4 readers |
| Report orchestration | `api/app/services/nfl/track_record.py`, focused targets report source; minimal adaptations in `services/prop_ranking.py`, `core/prop_ranking_check.py` and report-only protocol typing |
| API contract | `api/app/routers/nfl.py`, `api/app/schemas/nfl.py`; retain shared/NBA response behavior |
| CLI and schedule | `api/app/backtest/nfl_ranking_check.py`, its pure report formatting/tests and the existing ranking step in `.github/workflows/nfl-ingest.yml` |
| Web transport and view | `web/src/types/nfl.ts`, `api/nfl.ts`, `hooks/useNflModelTrackRecord.ts`, `pages/NflModelPage.tsx`, `components/nfl/model/NflRankingSlices.tsx`, `utils/nflTrackRecord.ts` and adjacent helper tests; CSS only as needed |
| Regression checks | `test_nfl_v4_markets.py`, `test_nfl_prop_source.py`, `test_prop_ranking_loader.py`, `test_prop_ranking_check.py`, `test_prop_ranking_rule.py`, `test_nfl_track_record_service.py`, existing NBA/shared pipeline checks and relevant web helpers |
| Documentation | This spec's evidence and the existing local `docs/SportApp-Employer-Interview-Guide.md`, ignored and never staged |

## Data / contracts

These are load-bearing for 27h and any later targets probability work.

| Contract | Required behavior |
|---|---|
| API selector | `/nfl/model/ranking?season=<year>&model_version=<version>`; omit `model_version` for `opponent-dvp-tg-blend-usage-snap-v4`; the other accepted value is `nfl-targets-v1`; no `all` API response and no arbitrary version discovery |
| v4 identity | The original nine markets, `opponent-dvp-tg-blend-usage-snap-v4` and `nfl-pover-v1`; retain existing loader selection, null-row acceptance, exclusions and coverage semantics; targets never enter these readers |
| Targets identity | `receiving_targets`, `nfl-targets-v1`, served probability version NULL; the hidden candidate method's string `nfl-targets-pover-v1` is not substituted for NULL |
| Eligibility | Same supported population as 39c: linked RB/WR/TE, full game, `standard`, REG weeks 1-18; all `sport_*` references explicitly NFL scoped |
| Latest frozen row | Select within the targets model/null probability identity before `DISTINCT ON`; group by provider and provider prop id; order by line fetch time DESC, line id DESC, prediction generated time DESC, prediction id DESC |
| Timing | Both line `fetched_at` and prediction `generated_at` strictly before the game's known `start_utc`; equal/after kickoff and unknown-start rows excluded |
| Settlement | Use that selected row's stored line and weekly `targets`, not a current line or reconstructed projection; Step 1 defines missing-data handling; carry explicit exclusions rather than invented outcomes |
| Coverage denominator | Each eligible provider prop's latest pre-kickoff line on completed games, grouped by week; independent of whether it has a frozen row or usable projection |
| Coverage numerator | A denominator prop with at least one eligible pre-kickoff frozen row of the same provider/id, player/game/market and exact targets model/null probability identity; do not require the latest line id to be frozen; never count another version |
| Finished weeks | Reuse `get_finished_weeks`: every REG game completed and each has loaded stats; preserve the existing full-week sample boundary |
| Response | Existing camelCase ranking fields; targets `overProbabilityVersion` is JSON null, rates/SE null when no picks; the four canonical API slices remain `insufficient`, n=0, weeks=0, neutral while probabilities are absent |
| Null probability | Settled over/under lines may count in `funnel.calls`; `withPOver`, picks and bets stay zero for today's targets rows. Null projection rows still freeze/count for coverage, never become picks |
| Presentation | Show standard targets slices only, with unsupported goblin/demon explained; API retains canonical four-slice shape. No combined sample, adopted count or version label across models; v4 summary retains its own scope |
| Cache | API key includes season/model/expected probability version; web query key includes season/model; defaults map to v4 consistently; failures stay isolated |
| Compatibility | No new schema or frozen-row writes. Existing default API/CLI values, v4 sample boundaries, NBA record values and default renderer behavior remain intact |
| Future probability | A new served probability version requires separately reviewed evidence and a separately selected forward sample; never pool it with today's NULL-version rows |

## Testing

- Test gate is on. Every logic-bearing step ships focused pytest/Vitest
  cases with fixed timestamps, pure inputs and recorded SQL/test doubles.
  No provider request, shared DB mutation or new test runner is needed.
- Mixed fixtures must include the same provider id across competing model
  versions, newer unfrozen snapshots, timestamp/id ties, wrong sport/market,
  wrong payout/segment/position, equal/post-kickoff rows, null probability
  versions, missing/zero targets and an unfinished week with partial stats.
- Test coverage separately from grading: no frozen row, only another
  version's frozen row, older eligible frozen row and latest eligible row.
  Zero-denominator weeks and no frozen predictions must be ordinary data.
- Exercise shared null handling without changing existing nonnull version
  rules. V4 parity includes exclusions and coverage, not only final verdicts;
  NBA/shared pipeline regressions guard import boundaries and nonnull output.
- Verify changed API behavior by running the app; use schema-validation
  unit checks for serialization. UI proof uses browser screenshots and API
  observations, with helper tests rather than component/browser test suites.
- Final gate from the root with API venv first on PATH:
  `npm --prefix web run verify && cd api && python -m pytest`.
  If this PowerShell host needs separate halves, run web Verify first, then
  `.venv\Scripts\python.exe -m pytest` from `api/`; stop on a failed half.
- Manual path: API on 8000, web on 3001; open `/#/nfl/model`, inspect both
  labelled ranking sections and targets' hidden-probability explanation.
  Compare default and explicit v4 API requests, then the targets selector.
  Run the read-only CLI with the default, targets and `all` selectors only
  against approved/configured data; synthetic fixtures suffice for parity.
- Do not run build/tests, grading CLIs or live data reads during this spec
  phase. Implementation records checks as they actually occur.

## Notes for the AI

- One bounded reporting feature with seven reviewable steps; no further
  build-plan split is needed. This invocation writes a draft only.
- Preserve the pre-existing overview edit. Create the feature branch only
  during `/implement`; do not commit or change app code during `/feature`.
- The existing v4 frozen query selects before service-level version
  exclusions. Do not rewrite its semantics as a cleanup; add the targets
  loader separately and demonstrate fixed-input parity.
- `STAT_COLUMN_BY_MARKET` and `_GRADED_STAT_COLUMNS` currently describe
  v4. Adding targets blindly widens replay/fit iterations. Use a dedicated
  targets mapping/adapter instead of weakening the nine-market boundary.
- The shared source protocol currently exposes one model per sport. A
  report-only adapter is sufficient; keep `PROP_SOURCES['nfl']` and the
  mixed-model freezer unchanged. Shared modules must not import NFL code.
- `NflRankingSlices` is also used by NBA. Optional presentation changes
  must preserve default rendering; NFL nullability must not turn NBA's
  version chip into a nullable public contract.
- No synthetic probability, projection-gap pick, retrospective backfill,
  calibration claim or new verdict is justified by this reporting feature.
- Keep request work bounded: query only eligible frozen targets rows and
  aggregate coverage, reuse the short-lived cache, never replay slates or
  import the targets backtest on a request. If profiling shows a heavy
  report, stop and revise the serving design before adding a production
  request path, following the existing stored-report pattern.
- Findings remain separate work. F-15 is fixed pending independent audit;
  this spec neither closes it nor adds unrelated repairs. No P0/P1 blocker
  is recorded at specification time.
- Update the employer guide only after verified implementation; describe
  settlement/coverage separately from validated picks and hosted rollout.

## Spec critique

- Separated targets selection and coverage from v4 before latest-row
  deduplication; prevented another model or probability identity from
  displacing or falsely covering a targets prediction.
- Defined JSON null as the targets report's actual probability identity,
  rather than presenting the rejected fit's method string as served.
- Split settlement, SQL, orchestration, API, CLI and web into individual
  review gates; kept operational proof as the final step.
- Added an explicit missing-targets branch so an existing row with unknown
  data cannot become an invented zero; preserved the established absent-row
  plus positive-snaps NFL convention and v4 behavior.
- Kept probability-free settlement distinct from picks: no progress to an
  adoption verdict is possible today, even with many frozen target rows.
- Locked the default v4 API/CLI behavior and summary scope, isolated query
  failures, and covered NBA's reuse of the shared renderer and types.
- Cut new accuracy/calibration metrics, refits, freeze changes, arbitrary
  model discovery and historical sample reconstruction from scope.

## Implementation evidence

### Step 1 (2026-10-19), approved

- Created `feature/nfl-targets-forward-check`, preserving the existing spec
  and overview edits. Added the pure `nfl_targets_grading.py` helper and
  36 synthetic cases in `test_nfl_targets_grading.py`.
- Settlement uses the supplied frozen line and the shared `settle` primitive.
  It rejects missing/nonfinite/negative lines, preserves valid zero targets,
  distinguishes unknown values on present rows from absent player rows,
  requires loaded game stats and applies the existing positive-snaps zero
  convention only when the player stat row is absent.
- Focused check from `api/`:
  `.venv\Scripts\python.exe -m pytest tests/test_nfl_targets_grading.py tests/test_nfl_line_grading.py tests/test_nfl_v4_markets.py -q`:
  **65 passed**.
- Final Verify, with the API venv first on PATH:
  `npm --prefix web run verify && cd api && python -m pytest`:
  **625 web tests, production build and 2,924 API tests passed**. The first
  sandbox attempt could not resolve the Vite config because esbuild was
  denied parent-directory access; the approved outside-sandbox rerun passed.
  Existing large-bundle and dependency deprecation warnings remain.
- Reviewed both new-file diffs; `git diff --check` passes. Existing v4
  settlement and market filters are untouched. No source change followed
  the passing Verify; this evidence/status update is documentation only.
- No live data read, holdout/backtest command, provider request, DB write,
  application wiring, commit or push occurred in Step 1.
- The owner approved Step 1 and continuation without a checkpoint commit.

### Step 2 (2026-10-19), approved

- Added `repositories/nfl_targets_ranking.py` as a focused sibling, keeping
  the existing v4, serving and replay readers unchanged. Its two read-only
  queries load frozen targets and weekly coverage; neither is wired into
  the application yet.
- Both queries share the NFL/REG/standard/full-game/RB-WR-TE eligibility
  restriction. Frozen selection filters `nfl-targets-v1` and a NULL
  probability version before deterministic latest-row selection; both
  line-fetch and prediction-generation timestamps must precede kickoff.
- The coverage numerator matches provider/id, player, game, market and
  targets/null-version identity. An older eligible frozen row covers a
  newer unfrozen line, while other versions, players or games cannot.
- Typed mapping uses Step 1's settlement helper with separate player-row
  and game-stats presence. Unknown targets on present rows stay unknown;
  absent player rows follow the approved positive-snaps zero convention.
- Added 47 synthetic cases in `test_nfl_targets_ranking_repository.py`.
  Recorded SQL checks cover bound identity and filters. In-memory SQLite
  executes the query logic after replacing only PostgreSQL `DISTINCT ON`
  with the equivalent window selection, preserving production predicates
  and ordering. This is unit evidence, not a live PostgreSQL execution or
  query-runtime measurement; those remain Step 7 proof.
- Initial focused execution found a whitespace assumption in a recorded-
  SQL test's CTE split. Corrected that test parser; no production query
  correction was required. Final focused command from `api/`:
  `.venv\Scripts\python.exe -m pytest tests/test_nfl_targets_ranking_repository.py tests/test_nfl_targets_grading.py tests/test_nfl_v4_markets.py -q`:
  **90 passed**.
- Full Verify, with the API venv first on PATH:
  `npm --prefix web run verify && cd api && python -m pytest`:
  **625 web tests, production build and 2,971 API tests passed**. Used the
  approved outside-sandbox execution needed by esbuild. Existing bundle
  size and dependency deprecation warnings remain.
- Reviewed both new-file diffs; `git diff --check` passes. No change to
  existing v4 repository, settlement map, market membership or source.
  No source change followed Verify; this status/evidence edit is docs only.
- No live-data read, provider request, holdout/backtest command, database
  write, commit or push occurred. All SQL fixture writes used isolated
  in-memory test databases.
- The owner approved Step 2 and continuation without a checkpoint commit.

### Step 3 (2026-10-19), approved

- Added a structural read-only `RankingSource` protocol in the shared
  ranking service. The existing full sport sources still satisfy it;
  their ingest/freezing protocol and registry are unchanged.
- Added `NflTargetsRankingSource`, which delegates to Step 2's frozen and
  coverage readers and the existing NFL finished-week guard. Its model is
  `nfl-targets-v1`, with a null expected probability version.
- NFL record loading/building now accepts either current model identity,
  defaulting to v4; unsupported identities fail before reads/cache work.
  The ranking cache key is `(season, model, expected_probability_version)`
  with the existing 15-minute single-flight and cached-failure behavior.
  API/CLI selectors and public NFL schema nullability remain Step 4/5 work.
- Shared record typing accepts a null probability version. Only the new
  null-version report mode suppresses probability fields when creating a
  call, so stray unversioned values cannot become probability picks.
  Named-version callers keep their existing null-row acceptance semantics.
- Added eight service cases and three pure ranking cases covering source
  routing, mixed models, exclusions, empty data, a 300-call probability-free
  sample, concurrent requests, isolated cached failures/expiry and cache
  identity. No finished-week or ranking-rule constants changed.
- Focused command from `api/`:
  `.venv\Scripts\python.exe -m pytest tests/test_nfl_targets_ranking_service.py tests/test_prop_ranking_check.py tests/test_prop_ranking_loader.py tests/test_nfl_track_record_service.py tests/test_sport_props_pipeline.py tests/test_nba_track_record_routes.py -q`:
  **38 passed**. This includes the fresh-interpreter shared-pipeline check
  proving the shared modules load no NFL modules.
- Before changing source, saved complete v4/NBA record dictionaries for
  210 synthetic calls and a fixed clock. Rebuilt them afterward and compared
  every field: identical, SHA256
  `80ee271e4d0f5b2797c9dc811e6a54eb103bf407579188d40b0a0dfef4bbf5c5`.
  The scratch baseline lives in the system temp directory, not the repo;
  it contains synthetic inputs only.
- Full Verify, API venv first on PATH:
  `npm --prefix web run verify && cd api && python -m pytest`:
  **625 web tests, production build and 2,982 API tests passed**. Used the
  approved outside-sandbox execution required by esbuild; the existing
  bundle-size/dependency deprecation warnings remain.
- Reviewed the changed and new-file diffs; `git diff --check` passes.
  No source edit followed Verify. No live data read, provider request,
  holdout command, database mutation, commit or push occurred.
- The owner approved Step 3 and continuation without a checkpoint commit.

### Step 4 (2026-10-19), approved

- The existing ranking route now accepts optional `model_version`, limited
  to the current v4 string and `nfl-targets-v1`; omission still selects v4.
  The thin router forwards the selector to the Step 3 service and retains
  the existing generic failure response.
- `NflModelRankingResponse` overrides only its probability-version field
  to allow a required JSON null. Shared and NBA public response contracts
  remain nonnull. Added eight schema/selector validation cases; updated
  two existing route-test doubles for the optional service argument.
- Focused command from `api/`:
  `.venv\Scripts\python.exe -m pytest tests/test_nfl_ranking_schema.py tests/test_nfl_track_record_routes.py tests/test_nba_track_record_routes.py tests/test_nfl_targets_ranking_service.py -q`:
  **27 passed**.
- Ran the actual `app.main` FastAPI app under Uvicorn on isolated localhost
  port 18039, with real router/service/cache/schema behavior and synthetic
  repository inputs. Disabled the DB dependency, supplied a password-free
  dummy database URL and disabled the unrelated model-loading lifespan.
  No connection to the shared database was opened. Harness and output live
  only in the system temp directory; the fixture server was stopped.
- The first HTTP batch reached the existing heavy-route rate limit after
  the initial checks. Increased only the disposable fixture's in-memory
  rate allowance, restarted it and reran the complete matrix successfully.
  No app rate-limit setting or product source was changed for this proof.

| Step 4 HTTP /check criterion | Observed fixture result |
|---|---|
| Default vs explicit v4 | Both 200, byte-equivalent parsed JSON including cached grade time |
| Targets identity and null probability | 200, `modelVersion=nfl-targets-v1`, explicit JSON null probability version, two settled calls and zero picks |
| Empty targets sample | 200, zero frozen rows, empty coverage and no last settled week |
| Unsupported, `all`, empty selectors | Each 422, validation error names query `model_version` |
| Missing season | 422 |
| Targets failure and isolation | Repeated generic 503 with no private exception detail; same-season v4 and another targets season stay 200 |
| OpenAPI | Exactly two selector values, v4 default, NFL string-or-null field, NBA string field |

- Full Verify, API venv first on PATH:
  `npm --prefix web run verify && cd api && python -m pytest`:
  **625 web tests, production build and 2,990 API tests passed**. Used the
  approved esbuild access; existing bundle/dependency warnings remain.
- Reviewed all Step 4 diffs; `git diff --check` passes. No source edit
  followed Verify. Real stored-data/SQL execution and runtime profiling
  remain Step 7; these API observations are explicitly fixture evidence.
- No shared DB read/write, provider request, holdout command, commit or
  push occurred in Step 4.
- The owner approved Step 4 and continuation without a checkpoint commit.

### Step 5 (2026-10-19), approved

- Added CLI `--model-version` choices for v4, `nfl-targets-v1` and `all`.
  Omission still selects v4; `all` prints v4 then targets as separate
  reports. Parsing/selector validation happens before lazy DB imports.
- Both reports reuse the API's model resolver and ranking-call loader.
  Text is assembled before printing, so either report's failure exits
  nonzero with no partial success report on stdout; session cleanup still
  runs. Targets coverage names its own eligible standard props, displays
  `P(over) not served`, and explains hidden probability/no pick accrual and
  unsupported goblin/demon lines. Shared/NBA report formatting is unchanged.
- Changed only the existing ranking step in `nfl-ingest.yml`: request
  `--model-version all` and set Bash `pipefail` so `tee` cannot mask a CLI
  failure. The stats-first order, schedule and Summary output stay intact.
  No workflow was dispatched or remote setting changed.
- Added 15 pure/parser/orchestration test cases in `test_nfl_ranking_cli.py`.
  Focused command from `api/`:
  `.venv\Scripts\python.exe -m pytest tests/test_nfl_ranking_cli.py tests/test_prop_ranking_check.py tests/test_nba_ranking_check.py tests/test_sport_props_pipeline.py -q`:
  **31 passed**.
- Saved the full default v4 report on fixed synthetic inputs before edits,
  rebuilt it afterward and compared bytes: identical. The baseline is in
  the system temp directory, not the repo.
- Subprocess `/check` executed the actual CLI module entry point with
  synthetic session/loader inputs. Harness/output are in the system temp
  directory. Default: exit 0 and v4 only; targets: exit 0 and targets only
  with no served probability/picks; `all`: exit 0, two ordered reports with
  independent counts; forced targets failure: nonzero exit and empty
  stdout. Actual `python -m app.backtest.nfl_ranking_check --help` exited 0;
  an invalid selector exited 2 before DB loading. A password-free dummy DB
  URL and synthetic sessions prevented shared DB access.
- Full Verify, API venv first on PATH:
  `npm --prefix web run verify && cd api && python -m pytest`:
  **625 web tests, production build and 3,005 API tests passed**. Used the
  approved esbuild access; existing bundle/dependency warnings remain.
- Reviewed Step 5 diffs; `git diff --check` passes. No source edit followed
  Verify. No shared data read/write, provider request, holdout command,
  commit, push or workflow dispatch occurred in Step 5.
- The owner approved Step 5 and continuation without a checkpoint commit.

### Step 6 (2026-10-19), approved

- NFL ranking transport accepts the typed model selector and preserves the
  omitted v4 query parameter. TanStack keys explicitly include season and
  model, with canonical default/explicit v4 identity and a distinct targets
  key. Generic shared record typing defaults to nonnull strings for NBA;
  NFL specializes it for a null probability version.
- `/nfl/model` renders separately labelled V4 and Rec Targets sections with
  independent `ModelSection` loading/error/retry behavior. The summary and
  page grade time are explicitly v4-scoped. Targets display standard over
  and under only, gray `Not accruing` status, no probability picks, the
  hidden-probability explanation and unsupported goblin/demon note.
- The shared slice renderer retains its defaults for v4/NBA. A small
  optional reference mode supplies targets labels, eligible-prop coverage
  and a useful empty message. One CSS rule preserves the incumbent palette
  and fonts while limiting the new explanation's line length.
- Added five helper cases for query identity/params, reference eligibility,
  null-version wording, neutral status, empty data and summary isolation.
  Focused web check: `npm.cmd run test -- src/utils/nflTrackRecord.test.ts
  src/utils/nbaModel.test.ts`: **16 passed**; `npx.cmd tsc -b` passed.
- Used Impeccable context and its craft/Operate guidance, preserving the
  incumbent model page. The required one detector run returned `[]` for
  the changed page, renderer and stylesheet. No design drift repair or
  redesign was performed.
- Captured the incumbent first. The connected browser profile was busy;
  used the already installed Playwright Python driver with an isolated
  headless Edge profile instead. The driver needed approved execution
  outside the sandbox. All API fetches were intercepted with synthetic
  response fixtures; no live provider or database request was made.
- Batched desktop (1440px) and phone (390px) visual checks, then one final
  confirmation after tightening targets coverage wording. Screenshots and
  temporary QA scripts live in the system temp directory, including
  `lineform39d-step6-targets-desktop.png`,
  `lineform39d-step6-mobile-top.png`,
  `lineform39d-step6-targets-mobile.png` and loading/error/empty captures.

| Step 6 browser /check criterion | Observed fixture result |
|---|---|
| Separate queries and counts | v4 omits the selector; targets sends `model_version=nfl-targets-v1`; separate records show four vs two slices |
| Reference presentation | Two gray standard slices, `Not accruing`, null probability explained, 12 settled calls and zero probability picks |
| Desktop and phone | Existing theme retained; phone header/version wraps, targets stack; no document-width overflow |
| Loading isolation | Either query can wait while the other report remains visible |
| Error isolation and recovery | Either report can fail independently; focusing targets Retry and pressing Enter recovers it |
| Empty and unfrozen coverage | Helpful empty message, neutral zero-pick slices, no null/undefined text; 0 of 20 eligible props frozen is reported as coverage |
| NBA compatibility | Four original slices, Accruing wording and `nba-pover-v1` remain visible |

- Runtime observations: no page errors, failed requests or unexpected
  intercepted API paths in the final functional pass. The final console
  audit did log the existing Ant Design v5/React 19 compatibility warning
  when exercising the unchanged shared retry UI, and one generic resource
  404. The unchanged index supplies no favicon; a separate request to
  `/favicon.ico` reproduced 404, consistent with that console message.
  Expected fixture 503 responses also log resource errors. The final QA
  script therefore failed its strict clean-console assertion after all
  functional assertions passed; this is not reported as a clean console.
- Full Verify, API venv first on PATH:
  `npm --prefix web run verify && cd api && python -m pytest`:
  **630 web tests, production build and 3,005 API tests passed**. Existing
  bundle-size/dependency warnings remain. No source change followed it.
- Reviewed the web diff; `git diff --check` passes. No shared data access,
  provider request, holdout command, commit, push or workflow dispatch.
  The owner approved Step 6 and continuation without a checkpoint commit.
  Step 7's real-data/runtime proof and employer-guide update follow.

### Step 7 (2026-10-19), approved

- Executed the real PostgreSQL repository readers against season 2026 in
  one REPEATABLE READ transaction with `SET TRANSACTION READ ONLY` and a
  30-second local statement timeout. Verified `transaction_read_only=on`
  before and after the API/CLI proof. The initial sandbox connection was
  blocked; the authorized outside-sandbox read succeeded. No credentials
  or connection URL were printed. Diagnostic scripts/output are confined
  to the system temp directory, outside the live application tree.
- Real targets data: zero frozen rows, settled calls and probability picks.
  Coverage is 0 of 12 eligible props in week 4, 0 of 147 in week 5 and
  0 of 125 in week 6 (284 total). Finished weeks are 1-5; week 6 coverage
  does not make that unfinished week eligible for a verdict sample.
  No live row was inserted to manufacture a populated targets report.
- Captured the v4 frozen rows, finished weeks and coverage in that same
  database snapshot. Loaded the pre-change core and shared service directly
  from HEAD into temporary in-memory modules, then compared their entire
  inputs and record dictionaries with the new code at the same fixed clock.
  Every field matched, including model/probability identity, calls,
  exclusions, coverage, funnel, sample and verdicts. Default and explicit
  v4 also matched. The captured v4 sample has 38,244 frozen rows and 17,367
  settled calls; this parity check makes no new validation/adoption claim.
  Step 3's complete fixed-input NBA parity proof also remains passing.

| Final integration /check | Observed result |
|---|---|
| Running FastAPI with real stored data | Default v4, explicit v4 and targets each 200; default/explicit v4 JSON identical; targets probability version null and zero probability picks; unknown model 422 |
| Running CLI with real stored data | Actual `run(2026, 'all')` orchestration and repository queries produced separate v4-then-targets reports, including `P(over) not served`; used the same read-only session |
| Running model page | Captured real API ranking responses rendered four v4 slices, two neutral targets slices, the empty explanation and all three zero-frozen coverage counts; other page sections used labelled synthetic fixtures |
| Populated settlement and unhappy paths | Step 4-6 running-app fixtures prove populated settlement, empty data, independent loading/errors, generic failures and keyboard retry; CLI subprocess fixtures prove selector/exit/stdout behavior |

- Browser evidence: `lineform39d-step7-stored-targets.png` and
  `lineform39d-step7-browser-evidence.json` in the system temp directory.
  Inspected the screenshot. No page errors or unexpected fetches; the
  console still logged one generic resource 404, consistent with Step 6's
  missing-favicon observation. This is not a clean-console claim. Step 6
  also recorded the existing Ant Design/React compatibility warning in
  the retry path. No unrelated UI source was changed.
- Operational proof at current volume: the complete additional targets
  loader took 0.413 seconds with a 45,707-byte traced Python allocation
  peak. PostgreSQL EXPLAIN ANALYZE measured 2.763 ms for frozen selection
  and 37.306 ms for coverage, with zero temp read/written blocks. The plan
  used eligible lines and indexed predictions by line/model/null-version;
  654 eligible line snapshots collapsed to 284 provider props. Three
  batched repository calls include the unchanged finished-week query;
  there are no per-player application queries, slate replays or broad
  frozen-table materialization. The 15-minute cache is retained.
- These measurements concern today's zero-frozen-row sample and local
  client, not a production RSS measurement or future-volume guarantee.
  The coverage query's correlated EXISTS scans eligible history, so profile
  again as that history grows. No new heavy request builder was introduced.
- Invariants review: **clean** for the branch plus uncommitted/new source.
  Checked the shared checklist directly as instructed for Codex: NFL sport
  predicates, explicit targets-only eligibility and unchanged v4 filters,
  provider/NBA boundaries, pure core and NFL-free shared modules, unchanged
  rules/versions, neutral targets styling, generic errors and request cost.
  No holdout season, training, fit artifact or adoption decision was changed.
- Updated the existing receiving-targets passage in the local employer
  interview guide with the implemented reporting boundary, empty real
  sample, parity/runtime evidence and unverified deployment. Confirmed the
  guide remains ignored; it was not staged. The user-owned plans and
  pre-existing overview refresh were preserved.
- Final exact Verify, with the API venv first on PATH:
  `npm --prefix web run verify && cd api && python -m pytest`:
  **630 web tests, production build and 3,005 API tests passed** (API
  18.12 seconds). Existing bundle-size and Starlette/Anyio warnings remain.
  No product source changed after this gate. `git diff --check` passes.
- Ledger unchanged: open F-20, F-07, F-08, F-13 and F-14; fixed F-15
  awaits independent audit; F-09 and F-12 remain unverified. No open/fixed
  P0/P1 blocker. This feature does not repair or close unrelated findings.
- All task-created servers/browser profiles were stopped. No shared DB
  write, provider request, holdout command, workflow dispatch, commit,
  push or deploy occurred. The owner approved Step 7 and continuation
  without a checkpoint commit. All seven implementation steps are checked.
  `/complete` owns archive, plan bookkeeping, work-level commit and the
  separately approved merge/push process.

## Completion

- All seven steps approved by the owner. Exact Verify passed in this session:
  `npm --prefix web run verify && cd api && python -m pytest`, with 630 web
  tests, production build and 3,005 API tests. No product source changed
  after that gate. API, CLI, browser and read-only PostgreSQL evidence is
  recorded above; the invariants review was clean.
- 39d and parent 39 are complete in the build plan. Rec Targets remains
  reference only, with a null served probability version and no probability
  picks. Completion does not claim deployment or a populated frozen sample.
- No resolved findings need archival. All unresolved ledger entries retain
  their IDs and statuses, including F-15 fixed pending independent audit.
- The pre-existing overview refresh is excluded from the work commit. The
  updated employer guide remains local, ignored and unstaged.
- Manual try: with the API and web dev servers running, open
  `http://localhost:3001/#/nfl/model`. The separate Rec Targets section
  explains the hidden probability, shows two neutral standard slices and
  reports its own eligible-prop coverage. From `api/`, run
  `.venv\Scripts\python.exe -m app.backtest.nfl_ranking_check --model-version all`
  for the separate v4 and targets reports. The CLI only reads stored data.
- The work commit is authorized by the owner's `$complete` invocation.
  The owner approved the local squash merge and feature-branch deletion.
  Push requires separate approval afterward.

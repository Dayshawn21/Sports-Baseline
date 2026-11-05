# Feature: NHL ranking check and Model page

**From build-plan:** feature 56d (last sub-item of 56)
**Branch:** `feature/nhl-ranking-check` (cut from `master` at `bd3f0c14`)
**Status:** complete (2026-11-05)

## Goal

Grade NHL's frozen pre-puck-drop predictions (56c4) under the pre-registered 27i ranking rule, unchanged, and show the running result: a CLI on the daily `nhl-ingest.yml` Summary page, `GET /nhl/model/ranking`, and `/nhl/model` with each slice's progress and verdict, gray until decided. It also puts an NHL record card on the home page. This is the record a later NHL adoption item reads before any NHL edge becomes a pick.

**It is thin on purpose.** 20g4 already moved the sport-agnostic record, report and response schema into the shared pipeline (`prop_ranking.py`, `prop_ranking_report.py`, `schemas/prop_ranking.py`), and 56c4 gave NHL a full `SportPropSource`. NHL only adds its own season lookup, CLI, route and page, the same pieces NBA has.

## Sizing

One feature, six steps (API three, web two, verify and bookkeeping one). No build-plan split.

## Design reference

No mockup. `/nhl/model` reuses the NBA and NFL model pages as is: `web/src/pages/NbaModelPage.tsx` (layout, head, summary strip), `web/src/components/nfl/model/NflRankingSlices.tsx` (slice cards, funnel and rule notes), under the same `nfl-model` and `nba-model` classes. The home card reuses `HomeRecords`. No new visual design.

## In scope

- `app/services/nhl/track_record.py`: `nhl_season(db, now)` (season of `nhl.get_current_week`, None with no `REG` game), `load_ranking_calls(db, season)` through `prop_source("nhl")`, `build_ranking_record`, and a 15-minute `TimedSingleFlight` cache, as NBA's.
- `python -m app.backtest.nhl_ranking_check [--season N]` and a read-only final step in `nhl-ingest.yml` writing its report to the run Summary.
- `GET /nhl/model/ranking?season=` (season optional).
- `/nhl/model`: summary strip plus the forward ranking check section, reached from a Model view in NHL's Slate / Props / Model switch.
- A home record card for NHL, replacing the "NHL has no model page" note.
- Bookkeeping carried from 56c4: record that the first GitHub run of the freeze step passed (run `42085206301`, 2026-11-05) in the 56c4 archive and its build-plan line.

## Out of scope

- Any change to 27i's rule, constants, settlement, or NHL's frozen rows. A verdict here must equal what the shared check gives.
- Ranking, coloring or sorting NHL lines by P(over) on the board, game or player pages. That is a later adoption item, after a slice reads `adopt`.
- A forward grade of the projection gap itself (MAE, hit rate by gap). Only P(over) picks are graded; the funnel's "with a P(over)" count shows which markets feed it.
- Any calibration report by odds type (F-12 territory), a new fit, any edit to `nhl_over_probability_fit.py`, edge wording, the F-14 board cache.
- Playoff (`PST`) games: no week, never frozen, never graded.
- Renaming NBA or NFL files or classes, beyond the one summary-helper move in Step 3.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - NHL track record service, CLI and workflow Summary** - `app/services/nhl/track_record.py` (as above) and `app/backtest/nhl_ranking_check.py` (`--season` defaults to `nhl_season`; exits 1 with "No NHL regular-season games are loaded, so there is no season to grade." when there is none; sets `WindowsSelectorEventLoopPolicy` on Windows). The report is `ranking_report("NHL", ...)` with `NHL_PROJECTION_REFERENCE_VERSION`, `fit.OVER_PROBABILITY_VERSION` and coverage label `full-game lines with a frozen row`. Add a final `Report NHL forward ranking check` step to `nhl-ingest.yml` after the relink, appending the report to `$GITHUB_STEP_SUMMARY`, with no write. *Done when:* a report test pins the first line `NHL forward ranking check, 2026 (model nhl-reference-v1, P(over) nhl-pover-v1)`, the coverage label and the `week_not_finished` wording; the CLI runs on the real database (read-only) and prints four slices accruing at 0 of 200 picks with the funnel and coverage by week; the workflow YAML parses and the new step follows the relink; no module in the shared pipeline imports NHL code (`test_sport_props_pipeline.py` passes).

- [x] **Step 2 - `GET /nhl/model/ranking`** - `NhlModelRankingResponse(PropRankingResponse)` in `app/schemas/nhl.py`; `get_ranking_record(db, season)` cached per season; route in `app/routers/nhl.py` with optional `season` resolved before the cache, 404 `No NHL regular-season games are loaded`, 503 `The ranking check is unavailable; try again shortly` when grading failed. *Done when:* route tests (monkeypatched service) show the camelCase shape equal to `/nba/model/ranking`'s, the default season, the 404 and the 503; a local call returns season 2026 with four slices and `modelVersion` `nhl-reference-v1`.

- [x] **Step 3 - Web data layer and shared summary helper** - `fetchNhlModelRanking()` in `web/src/api/nhl.ts`; `useNhlModelRanking()` in `web/src/hooks/useNhl.ts` (key `['nhl', 'model', 'ranking', { season: 'current' }]`, 15-minute `staleTime` as NBA's, no retry on 404); move `nbaModelSummary` to a neutral `web/src/utils/propModel.ts` as `propModelSummary` (NBA page and its test updated, behavior identical). *Done when:* `npm run build` and `npm run test` pass; the moved helper's test (no data, no finished week, one adopted slice) passes unchanged in substance; `/nba/model` is unchanged in the browser.

- [x] **Step 4 - `/nhl/model` page and registries** - `model: '/nhl/model'` in NHL's `SPORTS` entry and `model: NhlModelPage` in `SPORT_PAGES` (`tsc` enforces the pair); `web/src/pages/NhlModelPage.tsx` with the NBA page's head (title Track record, season and last-graded time), the four-chip summary strip, and the "Forward ranking check" heading (`56d · frozen pre-puck-drop predictions · 27i's rule`) over `NflRankingSlices` inside `ModelSection`; a 404 renders the "no regular-season games" message, not a retry card. *Done when:* NHL's switch reads Slate / Props / Model on `/nhl`, `/nhl/board` and `/nhl/model`; the page shows four gray "Accruing" slice cards at `0 of 200`, the funnel note and `None yet`; no text under 11px; the mobile drawer nav still highlights NHL; `sportNav.test.ts` updated and passing; build passes; desktop and phone screenshots checked.

- [x] **Step 5 - NHL home record card** - `RecordSport` gains `nhl`; `rankingRecord` accepts it; `DETAIL.nhl = 'Forward ranking check'`; `HomeRecords` titles it `NHL props` and drops the "NHL has no model page" sentence; `useHomeData` reads `useNhlModelRanking()`. *Done when:* `homeRecords.test.ts` covers NHL (all accruing, one adopted, loading, error); the home page shows an NHL card linking to `/nhl/model` reading `0 of 4 adopted · 4 accruing`; the existing sport cards are unchanged; build and tests pass.

- [x] **Step 6 - Verify, bookkeeping and guide** - run `npm --prefix web run verify && cd api && python -m pytest`; update the 56c4 archive's "Not verified" line and its build-plan line to say the GitHub run passed (run `42085206301`, 2026-11-05); update the local, untracked `docs/SportApp-Employer-Interview-Guide.md` if present (NHL has a Model page and ranking check that grade frozen predictions under a rule fixed for NFL, all slices accruing, nothing adopted), or say it is absent. *Done when:* Verify passes and the summary names the guide update.

## Files / areas

- New: `api/app/services/nhl/track_record.py`, `api/app/backtest/nhl_ranking_check.py`, `api/tests/test_nhl_ranking_check.py`, `api/tests/test_nhl_track_record_routes.py`, `web/src/pages/NhlModelPage.tsx`, `web/src/utils/propModel.ts` (+ test, moved from `nbaModel`)
- Changed: `api/app/routers/nhl.py`, `api/app/schemas/nhl.py`, `.github/workflows/nhl-ingest.yml`, `web/src/api/nhl.ts`, `web/src/hooks/useNhl.ts`, `web/src/pages/NbaModelPage.tsx`, `web/src/utils/sportNav.ts` (+ test), `web/src/routes/sportPages.tsx`, `web/src/utils/homeRecords.ts` (+ test), `web/src/components/home/HomeRecords.tsx`, `web/src/hooks/useHomeData.ts`, the 56c4 archive and `blueprint/build-plan.md`
- Read only: `api/app/services/prop_ranking.py`, `api/app/core/prop_ranking_*.py`, `api/app/services/nhl/prop_source.py`, the NBA equivalents as the template
- Untouched: migrations, the freeze, the fit, the pre-registered rule files

## Data / contracts

No schema change, no migration.

**Load-bearing: `GET /nhl/model/ranking?season=`** returns the same camelCase `PropRankingResponse` as `/nba/model/ranking`: `gradedAt`, `season`, `modelVersion` (`nhl-reference-v1`), `overProbabilityVersion` (`nhl-pover-v1`), `rule` (`minPicks` 200, `minWeeks` 4, `minPickMargin` 0.03, unchanged), `finishedWeeks`, `lastSettledWeek`, `frozenRows`, `excluded`, `coverage[]`, `funnel`, and four `slices[]` (standard over, standard under, goblin over, demon over). Field names say "week" because NHL's period is the regular-season week (56c4). A later NHL adoption item reads each slice's verdict here.

**Shared builder** `build_ranking_record(...)` stays free of `sport_registry` and sport code (17c's rule).

## How it runs, and what proves it (hosted API note)

The Summary step and the CLI read the database directly from GitHub Actions, so they do not depend on the hosted API, which was suspended on 2026-11-05 (`x-render-routing: suspend-by-user`). The route and page do depend on an API being up, so they are verified against a local API (started with the selector loop, per the local-API memory) and the Vite dev server only; no hosted check is claimed. The Summary step takes effect only once pushed (the file changes in that push, so it registers).

## Testing

Test gate on. Logic tests: the NHL report header and wording (Step 1), route tests with a monkeypatched service (Step 2), `propModelSummary` (Step 3), `sportNav.test.ts` (Step 4), `homeRecords.test.ts` (Step 5). The page and home card ride on browser screenshots (desktop and phone) plus build. API tests need `DATABASE_URL=postgresql://localhost/ci` and `C:/dev/SportAppV2/api/.venv/Scripts/python.exe`; web needs `npm ci` in a fresh worktree; never print the database URL.

**What cannot be shown yet.** No frozen row has settled: week 6 is still being played, a week counts as finished only after every game is completed with box scores (earliest 2026-11-09), and a verdict needs 200 picks over 4 finished weeks (about 2026-12-01 at the earliest). So every slice reads accruing at build time. The shared check's verdict logic is already tested on NFL and NBA; this feature proves the wiring with the real database (frozen rows present, nothing settled) and fixtures, not a real verdict.

## Notes for the AI

- **27i's rule and 27j's application are frozen.** No change to `prop_ranking_rule.py`, `prop_ranking_check.py`, NHL settlement or frozen rows. A verdict computed here must equal the shared check's.
- **Gray until decided.** Slice color comes from `verdict_signal`; an accruing slice is never green or red. P(over) exists only in four markets, so only those feed picks; do not name markets in copy (the funnel's "with a P(over)" count shows it).
- **Known limits, stated not fixed.** Ladder rungs of one player-game are correlated, so the rule's nominal standard errors overstate certainty (F-12). The NHL fit was calibrated on synthetic x.5 lines, not posted ones, so a goblin or demon slice may reject; that is what the forward check is for. Do not tune anything from a read.
- **Read-only:** the CLI and Summary step write nothing; they go after the relink so freshly linked lines count.
- **Windows:** the CLI sets `WindowsSelectorEventLoopPolicy`.
- **Holdout discipline.** No read of 2025-26 outcomes. The only outcome read is the forward 2026-27 frozen rows, as designed.
- Reuse the NBA page's components and `nfl-model` and `nba-model` classes as is, the precedent 20g4 set.
- No em dashes in new text; no UI text under 11px. Ask before committing; no AI attribution beyond the repo's commit attribution lines.

## Decisions for the owner

1. **Apply 27i unchanged to NHL (recommended).** It is what NBA did and needs no new pre-registration. The alternative is an NHL-specific rule (different thresholds or slices for a daily sport with many rungs per player), which would need its own pre-registration commit before any verdict, as 56b did, and would delay this feature.
2. **Home card: include it here (recommended)** since the build-plan line names it and the plumbing is small; the alternative is a separate follow-up.
3. **Season label.** NHL season is the start year (2026 is 2026-27), as everywhere else in the app; the page says "2026 season" like NBA's.

## Red-team record (this draft)

- **Cut:** a shared `PropModelPage` refactor across NFL, NBA and NHL (a larger change than this feature needs); any calibration or gap-grading view; any change to the shared check.
- **Added:** the explicit statement that no verdict can exist yet and what proves the wiring instead; the hosted-API independence of the Summary step versus the page; the one-helper move so NHL does not import a function named for NBA; the correlated-rungs limit (F-12) as a stated limit, not a fix.
- **Resequenced:** API before web, so the page has a real endpoint to read; the home card after the page, since it links to it.
- **Contracts:** response shape locked to NBA's, flagged load-bearing for the adoption item.
- **Honesty:** earliest settled week (2026-11-09) and earliest possible verdict (about 2026-12-01) are stated rather than implied.

## Results

- **Step 1:** `app/services/nhl/track_record.py`, `python -m app.backtest.nhl_ranking_check` and the final `Report NHL forward ranking check` step in `nhl-ingest.yml`. Report test pins the first line, the coverage label and the `week_not_finished` wording; `test_sport_props_pipeline.py` passes. CLI on the real database (read-only): season 2026, four slices accruing at 0 of 200 picks, coverage wk 4 0/5476, wk 5 0/12249, wk 6 0/5519, `frozen rows on completed games 0`.
- **Step 2:** `GET /nhl/model/ranking`, NBA's shape; four route tests (shape, default season, 404, 503). Local API returned season 2026, `nhl-reference-v1`, `nhl-pover-v1`, four `insufficient` slices, `finishedWeeks` 1 to 5; `/nba/model/ranking` unchanged.
- **Step 3:** `fetchNhlModelRanking`, `useNhlModelRanking`, and `nbaModelSummary` moved to `utils/propModel.ts` as `propModelSummary` (test moved with it).
- **Step 4:** `/nhl/model` page and the `model` view in NHL's `SPORTS` and `SPORT_PAGES`; `sportNav.test.ts` and one `home.test.ts` assertion updated (NHL's home card now links Model). Desktop and phone screenshots checked, drawer highlights NHL Model.
- **Step 5:** NHL home record card reading `0 of 4 adopted`, `Forward ranking check · 4 accruing`; the "NHL has no model page" sentence removed.
- **Step 6:** `npm --prefix web run verify` passed (81 files, 1234 tests, build clean); API pytest 5793 passed. The 56c4 archive and build-plan line record the passing GitHub run `42085206301` (2026-11-05). The local, untracked interview guide was updated (NHL has a Model page and ranking check on the NFL rule, all slices accruing, nothing adopted).
- **Not verified:** a real verdict (no frozen row has settled; earliest finished frozen week 2026-11-09, earliest verdict about 2026-12-01); the new Summary step on GitHub (takes effect once pushed); hosted API (suspended, not involved).
- **Observed:** `frozenRows` is 0 and `finishedWeeks` reads 1 to 5 because a week finishes on game completion alone; weeks 4 and 5 predate the freeze and week 6's 620 frozen lines are unsettled.

# Feature: NBA ranking check and model page

**From build-plan:** feature 20g4 (last sub-item of 20g)
**Status:** complete (2026-10-07)

## Goal

Grade NBA's frozen pre-tip predictions (20g3) under 27i's pre-registered
ranking rule, unchanged, and show the running result: a CLI on the daily
`nba-ingest.yml` Summary page, and `/nba/model` with each slice's progress and
verdict, gray until decided. This is the record a later NBA adoption item reads
before any NBA edge turns into a pick.

It is also the first time a second sport runs the 27j check, so the
sport-agnostic part of NFL's ranking record (33d) moves into the shared prop
pipeline first, proved unchanged for NFL.

## Design reference

No mockup. The page reuses the NFL model page's ranking section as is:
`web/src/pages/NflModelPage.tsx` (layout, heading, summary strip) and
`web/src/components/nfl/model/NflRankingSlices.tsx` (slice cards, funnel and
rule notes), under the same classes in `web/src/pages/nfl-model.css`. No new
visual design.

## In scope

- A shared ranking record and report, built from any `SportPropSource`.
- `python -m app.backtest.nba_ranking_check [--season N]`, plus a read-only
  `nba-ingest.yml` step that writes its report to the run Summary.
- `GET /nba/model/ranking?season=` (season optional), cached 15 minutes.
- `/nba/model`: summary strip plus the forward ranking check section, reached
  from a Model view in NBA's Slate / Model switch.

## Out of scope

- Any change to 27i's rule, its constants, settlement, or NBA's frozen rows.
- Ranking, coloring or sorting NBA lines by P(over) on the game page (a later
  adoption item, after a slice reads `adopt`).
- An NBA prop board / Props view (open question 43).
- Showing 20g1's fit table or a 27a-style line grading for NBA on the page.
- NFL page or NFL CLI output changes of any kind.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Shared ranking record and report (NFL unchanged)** - move
  `RankingRule`, `CoverageWeek`, `RankingSliceRow`, `RankingRecord`,
  `_display_standard_error`, `_slice_row` and `build_ranking_record` from
  `app/services/nfl/track_record.py` into `app/services/prop_ranking.py`;
  `build_ranking_record` takes the model and P(over) versions as arguments
  (the source's), so nothing in it names NFL. Move the CLI's `report` text into
  a pure `app/core/prop_ranking_report.py` taking the sport label, the coverage
  label and the versions. NFL's track record and CLI call the shared pieces with
  their existing wording. Move the four ranking schema classes to
  `app/schemas/prop_ranking.py`; `NflModelRankingResponse` stays as a subclass
  name. *Done when:* `python -m app.backtest.nfl_ranking_check` prints output
  byte-identical to master (saved before the change, `diff` empty);
  `/nfl/model/ranking?season=2026` JSON is identical to master's apart from
  `gradedAt`; `pytest` passes; `tests/test_sport_props_pipeline.py` (or an
  added case) proves the moved modules load no NFL code.
- [x] **Step 2 - NBA ranking check CLI and workflow Summary** - add
  `app/services/nba/track_record.py` with `nba_season(db, now)` (the season of
  `nba_repo.get_current_week`, None with no `REG` game) and
  `load_ranking_calls(db, season)` through `prop_source("nba")`; add
  `app/backtest/nba_ranking_check.py` (`--season` defaults to that season, and
  exits non-zero with a message when none exists). Add a final
  `Report NBA forward ranking check` step to `nba-ingest.yml`, after the
  relink, appending the report to `$GITHUB_STEP_SUMMARY`. *Done when:* the CLI
  runs on the real database and prints `NBA forward ranking check, 2026 (model
  nba-reference-v1, P(over) nba-pover-v1)`, the four slices, the funnel and
  coverage (today: every slice accruing and 0 frozen rows on completed
  games, since the 380 opening-night rows sit on games not yet played); a test pins the NBA header and the per-week wording;
  the workflow YAML parses and the step runs only read-only code.
- [x] **Step 3 - `GET /nba/model/ranking`** - `get_ranking_record(db, season)`
  in the NBA track record service, cached 15 minutes per season with its own
  `TimedSingleFlight`; route in `app/routers/nba.py` with optional `season`
  (default: `nba_season`), 404 `No NBA regular-season games are loaded` when
  there is none, 503 when grading failed (NFL's message). *Done when:* route
  tests show camelCase output matching the NFL ranking shape, the default
  season, the 404 and the 503; a live call returns season 2026 with four
  slices.
- [x] **Step 4 - Web data layer** - move `NflModelRanking` and
  `NflRankingSlice` to a shared `PropRankingRecord` / `PropRankingSlice` in
  `web/src/types/propRanking.ts` (the NFL names stay as aliases), type
  `NflRankingSlices` and the `nflTrackRecord` slice helpers against them; add
  `fetchNbaModelRanking(season?)` in `web/src/api/nba.ts` and
  `useNbaModelRanking()` in `web/src/hooks/useNba.ts` (key
  `['nba', 'model', 'ranking', { season: 'current' }]`, 5-minute `staleTime`,
  no retry on 404).
  *Done when:* `npm run build` and `npm run test` pass, and `/nfl/model` looks
  unchanged in the browser.
- [x] **Step 5 - `/nba/model` page and registries** - `model: '/nba/model'`
  in NBA's `SPORTS` entry and `model: NbaModelPage` in `SPORT_PAGES` (`tsc`
  enforces the pair); `web/src/pages/NbaModelPage.tsx` with the NFL page's
  head (eyebrow `NBA · Model · <season>`, Track Record title, last-graded
  time, `SportViewSwitch`), a summary strip from a pure `nbaModelSummary`
  helper (Prop slices adopted `n of 4`, Last settled week `W<n>` or `None
  yet`, Projection version, P(over) version), and the "Forward ranking check"
  heading over `NflRankingSlices` inside `ModelSection`. A 404 renders the
  "no regular-season games" message, not a retry card. *Done when:* the NBA
  switch reads Slate / Model on `/nba` and `/nba/model` (game pages carry no
  switch, as on NFL; the nav highlights NBA there); the
  page shows four gray "Accruing" slice cards with `0 of 200` picks, the
  funnel note and "None yet"; no text under 11px; the mobile drawer nav still
  highlights NBA; `sportNav.test.ts` and the helper's test pass; build passes.

## Files / areas

- `api/app/services/prop_ranking.py` (gains the record builder),
  `api/app/core/prop_ranking_report.py` (new), `api/app/schemas/prop_ranking.py` (new)
- `api/app/services/nfl/track_record.py`, `api/app/backtest/nfl_ranking_check.py`,
  `api/app/schemas/nfl.py` (now thin users of the shared pieces)
- `api/app/services/nba/track_record.py`, `api/app/backtest/nba_ranking_check.py`,
  `api/app/routers/nba.py`, `api/app/schemas/nba.py` (new or extended)
- `.github/workflows/nba-ingest.yml`
- `api/tests/`: shared report, NBA CLI header, NBA route tests; existing NFL
  ranking tests keep passing untouched
- `web/src/types/propRanking.ts`, `web/src/types/nfl.ts`, `web/src/api/nba.ts`,
  `web/src/hooks/useNba.ts`, `web/src/utils/sportNav.ts`(+ test),
  `web/src/routes/sportPages.tsx`, `web/src/pages/NbaModelPage.tsx`,
  `web/src/utils/nbaModel.ts` (+ test),
  `web/src/components/nfl/model/NflRankingSlices.tsx`, `web/src/utils/nflTrackRecord.ts`

## Data / contracts

No schema change, no migration.

**Load-bearing: `GET /nba/model/ranking?season=`** returns the same camelCase
shape as `/nfl/model/ranking` (shared `PropRankingResponse`):

| Field | Meaning |
|---|---|
| `gradedAt`, `season` | grading time; the season graded (start year, 2026 = 2026-27) |
| `modelVersion`, `overProbabilityVersion` | `nba-reference-v1`, `nba-pover-v1` (from `NbaPropSource`) |
| `rule` | `minPicks` 200, `minWeeks` 4, `minPickMargin` 0.03 (27i, unchanged) |
| `finishedWeeks`, `lastSettledWeek` | NBA's `get_finished_weeks`; null before the first |
| `frozenRows`, `excluded` | frozen rows on completed games; reason counts (`week_not_finished`, `void_dnp`, `wrong_version`, ...) |
| `coverage[]` | `{week, lines, frozen}` from `get_frozen_coverage` |
| `funnel` | `calls`, `withPOver`, `picks`, `bets` |
| `slices[]` | standard over, standard under, goblin over, demon over: `oddsType`, `side`, `verdict`, `n`, `weeks`, `hits`, `hitRate`, `standardError`, `breakEven`, `signal` |

A later NBA adoption item reads each slice's verdict here, as 27h reads NFL's.
The field names say "week" because NBA's period is the regular-season week
(20a); a sport with another period would need its own labels.

**Shared builder:** `build_ranking_record(inputs, season, graded_at,
model_version, over_probability_version)` in `app/services/prop_ranking.py`
must never import `sport_registry` or NFL code (17c's rule).

**Report:** first line `<SPORT> forward ranking check, <season> (model <v>,
P(over) <v>)`; the rest of the NFL text unchanged, with the coverage label per
sport (NFL: `27a full-game lines with a frozen row`; NBA: `modelled full-game
lines with a frozen row`).

## Testing

Test gate on.

- **Step 1:** the existing NFL ranking tests (`test_prop_ranking_check.py`,
  `test_nfl_track_record_service.py`, `test_nfl_track_record_routes.py`) pass
  unmodified apart from import paths; a pure test of
  `ranking_report`; the NFL CLI byte-diff and API JSON diff as
  evidence.
- **Step 2:** a report test for the NBA header, coverage label and
  `week_not_finished` exclusion; a live CLI run as evidence.
- **Step 3:** route tests (monkeypatched service): camelCase shape, default
  season, 404, 503.
- **Steps 4-5:** `nbaModelSummary` test (no data, no finished week, one
  adopted slice); `sportNav.test.ts` updated for NBA's Model view; build;
  browser screenshots of `/nba/model` (desktop and mobile) and `/nfl/model`
  unchanged.

## Notes for the AI

- **27i's rule and 27j's application are frozen.** Nothing in this feature
  changes `prop_ranking_rule.py`, `prop_ranking_check.py`, NBA settlement or
  frozen rows; a verdict computed here must equal what the shared check gives.
- **Gray until decided:** slice color comes from `verdict_signal`, unchanged;
  a still-accruing slice is never green or red. All four NBA slices are
  accruing today and the season opens 2026-10-20, so picks will accrue only
  from lines with a P(over), which under `nba-pover-v1` is assists alone. Do
  not add copy that names assists; the funnel's "with a P(over)" count shows it.
- **Read-only:** the CLI and workflow step write nothing. The workflow step
  goes after the relink so freshly linked lines count.
- **Windows:** the CLI sets `WindowsSelectorEventLoopPolicy`, as NFL's does.
  Start the API with the selector loop (memory: plain uvicorn fails here).
- **NBA period is the regular-season week;** play-in and playoff rows have no
  week and never reach the check (20g3).
- Prefer moving code over copying it. Step 1 is a move-only diff: if it grows
  past a read-in-one-sitting size, split the schema move into its own step.
- NBA reuses the NFL model page's components and `nfl-model-*` classes as is,
  as NBA's pages already reuse NFL classes (20e); renaming them is out of scope.
- The route resolves the default season before the cache lookup, so the cache
  is always keyed by a concrete season.
- No em dashes in new text; no UI text under 11px.

## Outcome (2026-10-07)

- **Shared, NFL unchanged:** the ranking record, report text and response schema
  moved to `app/services/prop_ranking.py`, `app/core/prop_ranking_report.py` and
  `app/schemas/prop_ranking.py`. `nfl_ranking_check` printed byte-identical
  output before and after (1,055 bytes), and the `/nfl/model/ranking` 2026
  response was identical apart from `gradedAt`.
- **First NBA read:** season 2026, every slice accruing at 0 of 200 picks, 0
  frozen rows on completed games. The 380 frozen opening-night rows (two
  snapshots) sit on games not yet played, so they are not counted as
  exclusions; the spec's first guess said otherwise and was corrected.
- **Picks will come from assists only** under `nba-pover-v1`, the one market
  with a P(over); the funnel's "with a P(over)" count shows it.
- **Departures from the spec:**
  - the NBA hook's `staleTime` is 15 minutes (NFL's model hooks, the API cache),
    not 5
  - game pages carry no view switch on either sport, so the switch done-when
    covers `/nba` and `/nba/model` only
  - one NFL test fixture renamed `finished_weeks` to `finished_periods` when
    NFL's `RankingInputs` merged into the shared `RankingCalls`
- **Effective on push:** the `nba-ingest.yml` Summary step runs only once this
  commit is on the pushed default branch.

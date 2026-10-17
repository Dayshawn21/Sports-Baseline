# Feature: Sport-aware web shell and prop registry

**From build-plan:** feature 17d
**Status:** completed (2026-10-05)

## Goal

Make "which sport" a registered value on both sides, so item 20 (NBA) adds a
sport by adding registry entries rather than hand-editing the nav, the routes
and the prop pipeline call sites:

- **Web:** one sport registry drives the top nav, the Slate / Props / Model
  switch, the nav highlight for detail pages, and the sport routes.
- **API:** one registry maps a sport code to its prop pipeline source (the
  hook 17c left for 17d).

Every URL, page, report and response that exists today stays the same.

**Scope change (2026-10-05):** `bets.sport` was dropped. The owner tracks bets
in Pikkit, so My Bets gets no sport. It was built (migration `0042`, bets API,
My Bets sport select and filter) and verified, then fully reverted, including
`alembic downgrade 0041` on the local database. Nothing from it remains on the
branch.

## In scope

- **Web sport registry:** `SPORTS` in `web/src/utils/sportNav.ts` replaces
  `SPORT_VIEW_PATHS`, the hand-written sport entries in `NAV_ITEMS`, and
  `SPORT_PREFIXES`.
- **Routes:** a typed page map drives the sport `<Route>`s in `App.tsx`.
- **API prop-source registry:** `prop_source(code)` returns the sport's
  `SportPropSource`, and the three NFL call sites use it.

## Out of scope

- **`bets.sport` and any My Bets change.** Dropped 2026-10-05; see Goal.
  Hiding or removing My Bets is not part of 17d.
- **Tennis `matches` convergence** (item 22, per the build plan). Tennis
  routers, tables and `/tennis/*` paths are untouched.
- **A `GET /sports` endpoint and any change to the `sports` table.** Nothing
  consumes them: the web registry has to be static, because it holds page
  components. `sports` stays `nfl` only; item 20 seeds `nba`.
- **Mounting API routers from the registry.** The routers sit under fixed
  `/tennis`, `/tennis/props` and `/nfl` prefixes already. Generating them
  would mean services importing routers, which inverts the layering for no
  user-visible change. `main.py` keeps its explicit `include_router` calls.
- **A generic `--sport` prop CLI.** `prizepicks_nfl` and `nfl_prop_predictions`
  keep their names and flags. Item 20 can add an NBA entry point, or a
  `--sport` flag, beside them.
- **Seeding `nba`, NBA routes and NBA pages** (item 20).
- **Any change to a projection, edge, rank, pick or color rule.**

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Web sport registry (pure)** - in
  `web/src/utils/sportNav.ts`:
  - **Registry:** `SPORTS`, `as const satisfies readonly SportDefinition[]`.
    Each entry holds `code`, `label`, `prefix` and `views: { slate, props,
    model? }`.
  - **Types:** `Sport` is derived from `SPORTS`, and `sportViews` reads it.
  - **Nav:** `NAV_ITEMS` is built from `SPORTS` followed by Live Odds, My Bets
    and Admin. `navKeyForPath` uses each sport's `prefix`.
  - **Removed:** `SPORT_VIEW_PATHS` and `SPORT_PREFIXES`.
  - **Tests:** existing `sportNav.test.ts` cases unchanged and passing, plus
    new cases:
    - `NAV_ITEMS` keys and labels are exactly today's five, in order
    - view paths are unique across sports
    - every non-root view path starts with its sport's `prefix`

  *Done when:* `npm run test` and `npm run build` pass, and the nav looks and
  highlights exactly as before.

- [x] **Step 2 - Routes from the registry** -
  - **Page map:** `web/src/routes/sportPages.tsx` exports `SPORT_PAGES:
    Record<Sport, SportPages>`, where `SportPages` is `{ slate, props, model?,
    details: { path, element }[] }`. Slate and props are required, so a sport
    without them fails `tsc`.
  - **`App.tsx`:** maps `SPORTS` x `SPORT_PAGES` into `<Route>`s and drops the
    hand-written sport routes. The `/nfl/prospects` and `/props` redirects,
    `/live-odds`, `/parlays`, `/bets` and `/admin` stay explicit.
  - **Model view:** a `model` view path and a `model` page must exist
    together. A type-level pairing is enough, or a dev-time assert if the
    types cannot express it.

  *Done when:*
  - `npm run build` passes
  - in the browser, every route renders as before, including the
    `/nfl?gameId=` redirect and the Slate / Props / Model switch on both
    sports, with no console errors: `/`, `/tennis/board`, `/tennis/model`, a
    `/tennis/match/:id`, a `/tennis/player/:id`, `/nfl`, `/nfl/board`,
    `/nfl/model`, a `/nfl/game/:id` and a `/nfl/player/:id`

- [x] **Step 3 - API prop-source registry** -
  - **Registry:** `app/services/sport_registry.py` with `PROP_SOURCES:
    Mapping[str, Callable[[], SportPropSource]]` (`{"nfl": NflPropSource}`)
    and `prop_source(code)`, which raises `KeyError` naming the known codes.
  - **Call sites:** `app/ingest/prizepicks_nfl.py` (twice),
    `app/ingest/nfl_prop_predictions.py` and
    `app/services/nfl/track_record.py` call `prop_source("nfl")` instead of
    `NflPropSource()`.
  - **Test:** `tests/test_sport_registry.py`:
    - `nfl` resolves to a source whose `config.code` is `nfl`
    - an unknown code raises
    - every registered source's `config.code` equals its key

  *Done when:*
  - `python -m app.ingest.nfl_prop_predictions --dry-run` prints the same
    counts as on master
  - `python -m app.backtest.nfl_ranking_check --season 2026` prints the same
    report as on master
  - `tests/test_sport_props_pipeline.py` still passes, so the shared modules
    still do not load NFL code
  - pytest passes
  - not `prizepicks_nfl --relink`: it writes even with `--dry-run`

- [x] **Step 4 - Full verification** - run `npm run build`, `npm run test`
  and `pytest`, and re-check the step 2 route walk and the step 3 parity in
  one pass on the final branch.

  *Done when:* all three pass, and the step 2 and 3 checks still hold.

## Files / areas

- **New:**
  - `api/app/services/sport_registry.py`
  - `api/tests/test_sport_registry.py`
  - `web/src/routes/sportPages.tsx`
- **Changed:**
  - `api/app/ingest/prizepicks_nfl.py`
  - `api/app/ingest/nfl_prop_predictions.py`
  - `api/app/services/nfl/track_record.py`
  - `web/src/utils/sportNav.ts`, `web/src/utils/sportNav.test.ts`
  - `web/src/App.tsx`
- **Unchanged, consuming the same API:** `SportViewSwitch.tsx`

## Data / contracts

**Load-bearing for item 20 and later sports:**

- **API registry:** `app/services/sport_registry.py` has `prop_source(code)
  -> SportPropSource`. Item 20 adds `"nba": NbaPropSource` there and nowhere
  else in the shared pipeline.
- **Web registry:**
  - `SPORTS` in `web/src/utils/sportNav.ts` holds `code`, `label`, `prefix`
    and `views`; `Sport` is derived from it
  - `SPORT_PAGES` in `web/src/routes/sportPages.tsx` is keyed by `Sport`
  - adding a sport means one `SPORTS` entry plus one `SPORT_PAGES` entry, and
    `tsc` fails if the second is missing
  - detail pages live under the sport's `prefix`, so the nav highlight works
    without extra code
- **Unchanged:** no schema change; `bets` has no sport, and `sports` holds
  `nfl` only. Every URL, every `/tennis/*` and `/nfl/*` response, and every
  report also stay the same.

## Testing

**Test gate is on.** Logic ships with tests:

- **Web:** `sportNav.test.ts`, covering the registry-derived `NAV_ITEMS` and
  path uniqueness and prefixes.
- **API:** `test_sport_registry.py`, covering lookup, an unknown code, and
  each key equal to its `config.code`.

**Not unit-tested** (per coding standards): `App.tsx` routing rides on
`npm run build` plus a browser walk through every route.

**Parity:** step 3 compares the NFL freeze dry run and the ranking check with
master. Open question 40's intermittent `get_slate_lines` stall can slow a dry
run. The output must still match, so retry once rather than treat a slow run
as a failure.

## Notes for the AI

- **Windows API launch:** set the selector event loop before starting uvicorn
  (see memory). Run the API from `api/` with the venv python.
- **Layering:**
  - `app/core/` gains nothing (the registry references services, so it
    cannot be core)
  - `test_sport_props_pipeline.py` must keep passing: shared prop modules
    must not import `sport_registry`, since it imports NFL code
- **No em dashes** in new code, comments or the spec.
- **Light comments.** Comment only the non-obvious.

## Outcome

- **Shipped:** the web `SPORTS` registry (nav, view switch, nav highlight),
  `SPORT_PAGES` and `sportRoutes()` driving the sport routes, and
  `prop_source(code)` in `app/services/sport_registry.py` serving the three
  NFL call sites.
- **Dropped:** `bets.sport` (2026-10-05). The owner tracks bets in Pikkit. The
  migration, bets API and My Bets work were built and verified, then reverted
  before the commit; the local database went back to `0041`, so this feature
  has no schema change. Open question 42 in the overview asks what to do with
  My Bets and the plans' bet-tracking wording.
- **Type guard proven:** removing `model` or `props` from the NFL page map
  fails `tsc` with TS2322 against `SportPages<"nfl">`.
- **Parity:** `python -m app.ingest.nfl_prop_predictions --dry-run` and
  `python -m app.backtest.nfl_ranking_check --season 2026` printed identical
  output before and after the registry swap (week 4: 612 frozen, 9711 kicked
  off; all four slices accruing).
- **Route walk:** 16 URLs in the browser, each with the right page, nav
  highlight and active view; the `/nfl?gameId=`, `/nfl/prospects` and
  `/props` redirects held. The only console errors were already on master: the
  missing `favicon.ico` and antd's React 19 warning.
- **Checks:** `npm run build`, `npm run test` (449), `pytest` (2169).
- **Seen, not caused:** `/nfl` shows its loading state until the slate
  arrives, and the slate request was slow during the walk (open question 40).

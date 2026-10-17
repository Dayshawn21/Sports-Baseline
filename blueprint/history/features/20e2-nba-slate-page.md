# Feature: NBA slate page

**From build-plan:** feature 20e2 (second of 20e's three parts)
**Status:** complete (2026-10-06)

## Goal

Put NBA in the web app: an NBA nav entry and `/nba`, a one-day, game-first
slate of cards from 20e1's `GET /nba/slate`, showing each game's market, line
movement, records, prop line count and, once final, the score against the
closing lines. Display only, no signal color.

## Design reference

No mockup: the target is the shipped NFL slate (33b), `/nfl`, built from
`web/src/pages/NflIntelligencePage.tsx`, `components/nfl/NflSlateGameCard.tsx`,
`pages/nfl-slate.css` and `components/nfl/nfl-slate-card.css`. The NBA page
reuses those stylesheets and their class names rather than copying them, so
the two slates look the same and share the gray-signal variables set on the
`.nfl-slate` root. An NBA card is the NFL card minus the model strip,
conditions, injuries and top props.

## In scope

- The web sport registries accept a sport without a Props view, as they
  already accept one without a Model view; NBA is that sport.
- `SPORTS` and `SPORT_PAGES` entries for NBA: nav label "NBA", slate `/nba`,
  prefix `/nba/`, no props, no model, no detail routes yet.
- `web/src/types/nba.ts`, `api/nba.ts`, `hooks/useNba.ts` for the slate.
- A pure card model in `web/src/utils/nbaSlate.ts`, tested.
- `NbaSlatePage` at `/nba` with previous and next date buttons and `?date=`.
- `NbaSlateGameCard`.

## Out of scope

- The game page and card links (20e3 makes each card a link to
  `/nba/game/:gameId`).
- A date picker; navigation is previous and next game date plus `?date=`
  links.
- Any projection, edge, model strip or signal color (20g).
- Injuries, rest, top props on cards.
- Renaming the shared `nfl-slate*` classes to a sport-neutral prefix.
- Any API change.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Props view optional in the registries** - in
  `utils/sportNav.ts`, `props` becomes optional like `model`; in
  `routes/sportPages.tsx`, a sport's `props` page is required exactly when
  its registry entry has a props view (the same conditional type `model`
  uses). Tennis and NFL are unchanged.

  *Done when:* `npm run build` passes; `sportNav.test.ts` still passes
  unchanged for tennis and NFL; a type-level check (a `// @ts-expect-error`
  test line, as `tsc` enforces) shows a sport with a props view and no props
  page fails to compile.

- [x] **Step 2 - NBA types, API, hook and card model** -
  `types/nba.ts` (the 20e1 slate contract), `fetchNbaSlate(date | null)` in
  `api/nba.ts`, `useNbaSlate(date | null)` in `hooks/useNba.ts` (query key
  `['nba', 'slate', date]`, 5-minute `staleTime`), and in `utils/nbaSlate.ts`:
  - `nbaSlateCard(game, now)`: state (`upcoming`; `started` once tipped off
    but not yet completed, tagged "Tipped off", because scores load with the
    next morning's 09:30 UTC ingest, so last night's games would read "Live"
    for hours after they end; `final` when completed; `off` when postponed or
    canceled), tip label in
    Central time, teams (code, name, record, or "No games yet" at 0-0; score
    and loser once final), win bar from `moneyline.homeWinProbability`,
    market cells (spread with favorite, total, moneyline favorite first; each
    cell `--` when its market is missing; spread and total detail "opened X",
    "no move", or none while only one row is stored), final cells (close
    spread and total graded against the score from `lineMovement`'s current
    line, plus the prop count; null when no closing line is stored), and a
    prop count label.
  - `parseSlateDate(value)`: a `YYYY-MM-DD` string that is a real date, else
    null, so a malformed `?date=` falls back to the API's choice instead of
    a 422.
  - `nbaSlateSummary(games)`: games, prop lines, finals, odds updated (latest
    market `fetchedAt`, Central).

  *Done when:* `nbaSlate.test.ts` passes for each state (including a game
  past tip-off still `scheduled` reading `started`), a missing market, a
  single stored row (no detail), a moved line, an away favorite, a final
  graded both ways and a push, a final with no closing lines, a postponed
  game, `parseSlateDate` (valid, malformed, impossible like 2026-02-30), and
  the summary; `npm run
  build` and `npm run test` pass. No UI yet.

- [x] **Step 3 - NBA in the nav and `/nba` page shell** - the `SPORTS` and
  `SPORT_PAGES` entries and `NbaSlatePage`: header (eyebrow with the date,
  title, `SportViewSwitch` showing Slate only, previous and next buttons
  driven by `previousDate` / `nextDate`, disabled at the ends, writing
  `?date=`), summary strip, legend, and a plain list of games (away at home,
  tip time) standing in for cards. Loading, error and empty ("No NBA games on
  this date") states use the shared components.

  *Done when:* in the running app, the nav shows NBA between NFL and Live
  Odds and highlights on `/nba`; `/nba` opens on 2026-10-20 with 3 games and
  the summary (3 games, 194 prop lines, 0 / 3 final); Next goes to
  `?date=2026-10-21`, Previous from 2026-10-20 to 2026-06-13; `?date=2026-10-10`
  shows the empty state; `?date=garbage` opens 2026-10-20 like no date; `/nfl` and `/` are unchanged; `sportNav.test.ts`
  gains NBA cases (nav highlight, views = slate only) and passes.

- [x] **Step 4 - Slate cards** - `NbaSlateGameCard` replaces the plain list:
  meta row (tip time, state tag), teams with records, win bar, the three
  market cells with movement detail, a prop count footer; final cards show
  the score and graded closing lines, or "No closing lines stored"; started
  cards keep the market and say scores load the next morning; postponed or
  canceled cards say so and show no market. Cards are not links yet.

  *Done when:* screenshots of `/nba` (desktop and 390px wide) show the 3
  opening-night cards with DraftKings markets (BOS at DET: DET -2.5, total
  221.5, DET -125 / BOS +105, win bar 47% / 53%) and "61 prop lines";
  `?date=2026-04-12` shows 15 final cards with scores, the loser dimmed,
  records through 81 games and "No closing lines stored" (no 2025-26 odds); no text below 11px; no
  green or red anywhere on the page; `npm run build` and `npm run test` pass.

## Files / areas

- New: `web/src/types/nba.ts`, `web/src/api/nba.ts`, `web/src/hooks/useNba.ts`,
  `web/src/utils/nbaSlate.ts`, `web/src/utils/nbaSlate.test.ts`,
  `web/src/pages/NbaSlatePage.tsx`, `web/src/components/nba/NbaSlateGameCard.tsx`
- Changed: `web/src/utils/sportNav.ts`, `web/src/utils/sportNav.test.ts`,
  `web/src/routes/sportPages.tsx`
- Reused, unchanged: `pages/nfl-slate.css`, `components/nfl/nfl-slate-card.css`,
  `components/shared/SportViewSwitch.tsx`, `StatChip`, `LoadingState`,
  `ErrorState`, `fmtAmerican` (`utils/odds.ts`), `spreadLabel`
  (`utils/nflGameModel.ts`), `hasKickedOff` (`utils/nflGame.ts`)

## Data / contracts

- Reads 20e1's `GET /nba/slate?date=` unchanged (`NbaSlateResponse`,
  `NbaSlateGame` in `types/nba.ts`, mirroring `app/schemas/nba.py`).
- **Load-bearing:**
  - The route `/nba` and its `?date=YYYY-MM-DD` link; no `date` means the
    API's choice (today, else the next game date).
  - `SportViewPaths.props` optional, `SPORT_PAGES` requiring a props page
    only when promised. 20g adds NBA's props and model views by adding paths
    and pages, nothing else.
  - The `/nba/` prefix, so 20e3's `/nba/game/:gameId` highlights NBA in the
    nav.
  - `NbaSlateCardModel` is not load-bearing beyond the slate (33b's rule).

## Testing

- Test gate is on: `utils/nbaSlate.test.ts` (card model and summary) and the
  `sportNav.test.ts` additions. Components and the page ride on build plus
  screenshots.
- `cd web && npm run build` (typechecks) and `npm run test` after each step.
- Screenshots via the Playwright MCP against the running web dev server
  (`npm run dev`, port 3001) and API (port 8000).

## Notes for the AI

- TanStack Query only; components call the hook, never axios.
- `~/` imports; no `any`; theme variables, not hex.
- Times are Central (`America/Chicago`), as on the NFL slate and per the
  owner's profile.
- Green is a signal color: nothing on this page is green or red (the
  `.nfl-slate` root sets the NFL signal variables to the text color; keep the
  page under it).
- No UI text under 11px.
- Do not edit the NFL slate's components or CSS; reuse classes only.

## Results

Proved in headless Chromium (Playwright for Python from `api/.venv`; the
Playwright MCP browser was held by another session) against the owner's
running web dev server (3001) and API (8000) on 2026-10-06.

- **Nav:** Tennis, NFL, NBA, Live Odds, My Bets, Admin; NBA highlighted on
  `/nba`; the view switch shows Slate only. `/nfl` and `/` unchanged.
- **`/nba`:** opens on Tue, Oct 20, 2026; summary 3 games, 194 prop lines,
  0 / 3 final, odds updated Tue 9:34 AM CT. Cards: BOS at DET 2:00 PM CT
  (`DET -2.5`, `221.5`, `DET -125` / `BOS +105`, win bar 47% / 53%, 61 prop
  lines), PHI at NY 6:00 PM (`NY -5.5`, `231.5`, `NY -185` / `PHI +154`,
  38% / 62%, 65), OKC at SA 8:30 PM (`SA -1.5`, `230.5`, `SA -125` /
  `OKC +105`, 68). Records read "No games yet".
- **Navigation:** Next to `?date=2026-10-21` (11 games); Previous from
  2026-10-20 to 2026-06-13 (NY at SA, 1 / 1 final); `?date=2026-10-10` shows
  "No NBA games on this date."; `?date=garbage` opens 2026-10-20.
- **Finals:** `?date=2026-04-12` shows 15 final cards with the loser dimmed
  and records through 81 games (ORL 108 at BOS 113, 45-36 and 55-26), each
  "No closing lines stored" (no 2025-26 odds).
- **390px:** single column, no horizontal overflow.
- **Rules:** a DOM audit found 0 text elements under 11px and 0 elements
  whose text or background computes to the theme's `#00c805` or `#ff5000`,
  on both dates.
- **Type rule:** removing one `@ts-expect-error` in `sportPages.test.ts`
  made `tsc` fail with TS2322 (`Property 'props' is missing`); restored.
- **Checks:** `npm run build` passes; `npm run test` 477 passed (15 in
  `nbaSlate.test.ts`, the `ViewPages` type test, NBA cases in
  `sportNav.test.ts`, whose nav-entry test now pins six entries).
- **Console:** only the pre-existing antd React 19 compatibility warning.

**Beyond the spec:**
- `spreadResult` and `totalResult` (about 10 lines) are copied from
  `nflSlate.ts`, where they are private, rather than editing NFL code.
- The card grid sits in NFL's `nfl-slate-window` section for its spacing.

**Not exercised live:** a "Tipped off" or postponed card (no current game is
in either state); both are covered by tests. The NFL card's hover highlight
applies to the NBA cards, which are not links until 20e3.

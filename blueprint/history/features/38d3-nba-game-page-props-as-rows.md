# Feature: NBA game-page props as rows

**From build-plan:** feature 38d3
**Status:** implementation complete

## Goal

Replace the NBA game page's modelled and line-only prop cards with dense rows.
Each row opens an on-demand detail drawer built entirely from the response
already loaded for that section. The change preserves NBA's current market and
player order, reference projections, gaps, probabilities, recent results, and
gray-only signal treatment.

## Design reference

- No NBA-props mockup remains. The direction contract
  `.impeccable/surfaces/web-src-pages-nflintelligencepage-tsx.md` and chosen
  sketch `.impeccable/mocks/decision/command.html` establish the dense,
  border-light table direction.
- Reuse `web/src/components/shared/prop-table.css`, `MiniBars`, and the drawer
  interaction established by 38d1 and 38d2.
- Match the current NBA cards for content and gray-only semantics. This is a
  presentation change, not a projection or ranking change.

## In scope

- The modelled Props section renders one row per player and market, matching
  today's one-card-per-player-and-market grouping. Alternate PrizePicks rungs
  stay grouped under that row rather than becoming duplicate rows.
- Modelled rows use these columns:

  | Column | Content | Existing source |
  |---|---|---|
  | Player | Team, player, position, and market | `NbaPropCard` |
  | Line | Main rung and payout type | `main` |
  | Model | Reference projection, or `--` | `projectionRow` |
  | Gap | Projection minus main line, or `--` | `projectionRow` |
  | P(over) | Served probability, or `--` | `projectionRow` |
  | Last 5 | Existing gray mini bars against the standard line | `recent`, `lineOnlyBars` |
  | Sample | Existing eligibility or probability note, plus recent over count | `flagText`, `overCount`, `count` |

- The Other lines section renders one row per player in the double-double
  market, with Player, Line, Also, Last 5, and Recent count columns. It never
  gains a projection, gap, probability, rank, or signal.
- Keep the existing deterministic display order: modelled markets in
  `NbaPropMarket` order, double-double under Other lines, and players
  alphabetically within a market. Never sort or rank by gap, P(over), recent
  results, payout type, or any other signal.
- Clicking a row, or pressing Enter or Space on its player button, opens an Ant
  Design drawer. The open row uses the shared selected treatment and exposes
  `aria-pressed`; Escape and the close control close it.
- The drawer is 460px on desktop and full width on phones. It shows player and
  market context, every available rung, the main line's reference projection,
  gap and P(over)/P(under) when present, eligibility or fit flags, sample
  context, and the existing recent-game dates, opponents, and values.
- Other-line drawers show all rungs and recent games but no invented model
  output. Double-double recent values continue to read yes or no.
- Drawer content is built from the already loaded `/props` or
  `/line-only-props` response. Opening a row triggers no request, prefetch, or
  recomputation.
- Preserve each section's independent loading, error, and empty behavior. A
  failed props request does not blank the game page or the other section.
- At 1100px and below, rows use the shared two-line layout. At 390px there is
  no horizontal page or drawer scroll and no text below 11px.
- Delete `web/src/components/nfl/nfl-prop-card.css` and every retired NBA card
  selector once no component reads them.

## Out of scope

- An NBA prop board or `/nba/board` route.
- Any change to `project_line`, projection eligibility, market membership,
  main-rung selection, P(over), gap math, flags, recent history, or API shapes.
- Ranking, sorting, recommendations, break-even comparisons, picks, or green
  and red signal colors. Those remain gated on a later NBA adoption item.
- Changes to the NBA slate digest. Its normalized-gap ordering is the narrow
  slate-only exception established by 38c2.
- New API calls, schemas, endpoints, stored fields, or backend work.
- NBA player pages, injuries, minutes news, virtualization, or pagination.
- The game-page heading and shared `PageHead` work deferred to 38f.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Modelled NBA props as rows (web)** - add an NBA prop table
  and NBA-specific table styles on top of the shared prop-row foundation.
  Replace the modelled Props cards with rows while continuing to read
  `nbaPropGroups` and its main-rung choice. *Done when:*
  - for a game with modelled props, the row market order, alphabetical player
    order, main line, alternate rungs, projection, gap, P(over), flag text,
    last-five bars, and recent count match the current cards or `master`
  - eligible, ineligible, whole-number, and no-fit lines keep their current
    explicit values or missing states
  - no row has a rank or recommendation, and every gap, probability, and bar
    stays gray
  - the section's loading, error, and empty states behave as before
  - `npm run build` and `npm run test` pass

- [x] **Step 2 - Detail drawers and Other lines rows (web)** - add a shared NBA
  prop evidence panel for modelled and line-only data, wire modelled rows to it,
  and replace the Other lines cards with plain NBA rows that open the same
  drawer shape without model fields. *Done when:*
  - click, Enter, and Space open the correct row; Escape and the close control
    close it; the open row exposes `aria-pressed`
  - a modelled drawer lists every rung with its own gap and P(over) when served,
    plus the main projection, sample context, flags, and all recent games
  - an Other lines drawer lists every rung and recent game, including yes/no
    double-double values, without projection, gap, probability, or signal text
  - browser network evidence shows opening either drawer makes no request
  - one endpoint failing leaves the game and the other prop section usable
  - `npm run build` and `npm run test` pass

- [x] **Step 3 - Responsive pass and card cleanup (web)** - finish the two-line
  phone layout, remove retired card rules from `nba-game.css`, and delete the
  last shared card stylesheet. *Done when:*
  - at 1440px both tables use the available width and their columns align; the
    460px drawer does not change row order or values
  - at 390px each row is two readable lines, the drawer is full width, there is
    no horizontal page or drawer scroll, and all text is at least 11px
  - modelled and Other lines recent bars remain gray and readable, including
    clean empty history
  - `rg` finds no `nfl-prop-card.css`, `nfl-prop-grid`, `nfl-prop-card`, or
    `nba-prop-card` reference in `web/src`
  - Verify passes

## Files / areas

- **Web, new:** `web/src/components/nba/NbaPropTable.tsx`,
  `web/src/components/nba/NbaPropEvidencePanel.tsx`,
  `web/src/components/nba/nba-prop-table.css`
- **Web, changed:** `web/src/components/nba/NbaProps.tsx`,
  `web/src/components/nba/NbaLineOnlyProps.tsx`,
  `web/src/utils/nbaProps.ts`, `web/src/utils/nbaProps.test.ts`,
  `web/src/pages/nba-game.css`
- **Web, reused:** `web/src/components/shared/prop-table.css`,
  `web/src/components/shared/MiniBars.tsx`, `web/src/utils/nflLineOnly.ts`
- **Web, deleted:** `web/src/components/nfl/nfl-prop-card.css`
- **No API or database change.** Client only.

## Data / contracts

- No schema, endpoint, response type, query key, or stored-data change.
- **Load-bearing:** `nbaPropGroups` remains the modelled row source and keeps
  `NbaPropMarket` order, alphabetical player order, all rungs, and
  `mainRung` selection. It may expose additional existing response fields for
  the drawer, but must not recompute projections or probabilities.
- **Load-bearing:** `nbaLineOnlyGroups` remains the Other lines row source with
  the same market, player, rung, and recent-history ordering.
- **Load-bearing:** `NbaPropsResponse` and `NbaLineOnlyPropsResponse` already
  contain all drawer data. The drawer never fetches details.
- **Load-bearing:** `.nfl-slate` remains the NBA game's gray-signal scope.
  `prop-table.css` supplies only structure and grayscale bars; NBA-specific
  CSS must not add positive or negative colors.
- Null remains missing, never zero. A missing projection, gap, or probability
  displays `--` or its existing explanatory flag.

## Testing

- Keep and extend `nbaProps.test.ts` for any newly exposed drawer fields and
  the existing grouping, rung, flag, and formatting behavior. If
  `nbaLineOnlyGroups` changes shape, update `nbaLineOnly.test.ts` in the same
  step.
- Do not add React component tests. Verify rows and drawers in the running app
  at 1440px and 390px.
- Compare row values and order against the pre-change cards or `master` for a
  game with assists P(over), a whole-number line, a market without a fitted
  probability, and a game with double-double Other lines.
- Confirm a game with no props still hides both sections, and simulate or
  observe one section's request failure without blanking the page.
- Confirm through the browser network panel that opening and closing drawers
  creates no request.
- Final gate: `npm --prefix web run verify && cd api && python -m pytest`, with
  `api/.venv/Scripts/python.exe -m pytest` for the API half in this shell.

## Completion evidence

- `npm --prefix web run verify && cd api && python -m pytest`, with `api/.venv`
  active: 45 web test files and 547 tests passed, the production build passed,
  and 2,608 API tests passed on 2026-10-17.
- Browser captures in `.playwright-mcp/` cover the NBA prop tables and drawers
  at 1440px and 390px, including modelled and line-only rows, keyboard opening
  and closing, selected state, full-width phone drawers, and grayscale values.
- Browser network evidence confirmed opening either drawer makes no request.
  A simulated failed modelled-props request left the game and Other lines usable.
- Manual try path: open `#/nba/game/21320`, select rows under Props and Other
  lines, inspect their drawers, and repeat at desktop and phone widths.

## Notes for the AI

- â€œUnsortedâ€ means no signal ordering. Preserve the current deterministic
  market order and alphabetical player order so the restyle does not move data.
- Keep â€œgapâ€, never â€œedgeâ€. Do not add Over or Under labels, break-even math,
  rank numbers, or pick language.
- Keep P(over) display-only and muted. Do not infer 0.5 when it is absent, and
  do not derive P(under) unless the loaded model already supplies it.
- Use a real button for the accessible row-open action. Do not make a bare
  `<tr>` the only keyboard target or nest buttons.
- Use `Drawer` with `destroyOnHidden`, 460px desktop width, and full phone width.
- Recent bars remain oldest to newest and use `lineOnlyBars` unchanged. Recent
  detail rows may show the API's newest-first order only when labeled clearly.
- Preserve the global Lineform palette and 11px text floor. No green or red may
  appear anywhere in either NBA prop section or drawer.
- This restyle does not materially change employer-facing product claims, so
  the local interview guide does not need an update.

# Feature: NFL game page

**From build-plan:** feature 33a (parent: 33. NFL redesign and detail pages)
**Status:** complete (2026-09-30)
**Branch:** `feature/nfl-game-page`

## Goal

Give each NFL game its own linkable page at `/nfl/game/:gameId`. It shows the
market beside the muted model, spread and total movement, injuries, depth
changes, form, rest and team stats, and every prop for the game as prop-board
cards. It ships before the slate redesign (33b) because it takes over the
slate's matchup bar, model strip and notes panel, so nothing is lost when 33b
strips the slate down to game cards.

**Display only.** It never changes a projection, edge, rank or pick.

## Design reference

- [prototypes/nfl-game.html](../../prototypes/nfl-game.html) is the target layout.
- [prototypes/theme.css](../../prototypes/theme.css) holds the tokens. They are
  identical to `web/src/index.css` `:root` (ported in 31a), so **no token port
  step is needed**. Build against the existing variables.

**Where the build departs from the mockup (no data behind it):**
- **Stadium name.** Not stored. The header shows venue type and conditions instead.
- **"1.5 pts shorter" gap text.** The page uses `nflGameModelSummary`'s existing
  gap wording.
- **The "BUF off / MIA off" toggle.** The team stats block shows both teams'
  offense and defense the way the 30 notes block already does, restyled.

## In scope

- **API.** `GET /nfl/games/{game_id}` returns the game's identity (season,
  week, teams, kickoff, status) plus pre-kickoff spread and total history from
  one book. A missing game is a 404.
- **Route and data.** Web route `/nfl/game/:gameId`. The page reads that
  endpoint, then the week's existing `/nfl/slate` and `/nfl/game-notes`
  (already cached by TanStack Query when coming from the slate) and picks this
  game out of both.
- **Hero.** Away @ home, records, kickoff, status, venue type and conditions.
- **Market and model block.** Spread, win probability and total. The market
  row is in the primary text color. The model row is muted, with the fixed
  `NFL_GAME_MODEL_CAVEAT`.
- **Line movement.** A small step chart, SVG, no chart library, one series per
  market. It shows the book, the open to current change, and an empty state.
- **Props.** This game's lines as `NflPropCard`s, grouped by market in
  prop-board order, with position chips and a Full / 1H / Q1 period toggle.
  - Rank and edge share come from the **week-wide prop board**, so a card on
    the game page reads exactly as it does on `/nfl/board`.
  - Clicking a card opens the existing `NflEvidencePanel` in a right-side Drawer.
  - "Show all" reveals the not-rateable lines, as on the board.
- **Sidebar.** Injury report, depth changes, form and rest, and team stats. It
  reuses the item-29/30 data and the existing formatters in
  `web/src/utils/nflGameNotes.ts`.
- **Gray edges on this page only.** The page scopes `--nfl-green` and
  `--nfl-red` to `var(--text-primary)`, so the card and panel edges render
  gray here. The slate and prop board keep their colors until 33b.
- **Entry points.**
  - The current slate's matchup bar gets an "Open game page" link.
  - `NflEvidencePanel`'s game market section gets a link to the game page.
- **Text size.** No new text below 11px.
- **States.**
  - Loading and error use the shared states.
  - An unknown id shows "Game not found" with a link back to the slate.
  - A game with no book odds says so; the model is still shown if it exists.
  - A game with no model shows "Model unavailable for this game".
  - A game with no prop lines says "No prop lines stored for this game yet".
  - Once a game has kicked off, the page labels its prop cards "Lines closed at
    kickoff" and still shows them.

## Out of scope

- **The slate itself.** Game cards, dropping the signal boards, and gray edges
  on the slate and prop board are all 33b. Here the slate only gains a link.
- **Player links on cards** (33c).
- **Model record page** (33d).
- **Any schema change, and any change to `build_slate`.** It is replayed by
  27a and 27i, so the game page never calls it for more than the week the
  slate already fetches.
- **Live scores or in-play odds.** Movement is pre-kickoff only.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Line-history core and repository** - add
  `line_history_steps(rows)` to `app/core/nfl_game_notes.py`. It is pure, and
  per market it keeps the first row plus each row whose line differs from the
  previous one. Add `get_game(db, game_id)` and
  `get_game_line_history(db, game_id)` to `app/repositories/nfl.py`. The
  history query reuses `get_week_line_movement`'s rules: lowercase book only,
  pre-kickoff, and one book per market (DraftKings, else the book with the
  most rows). *Done when:* `test_nfl_game_notes.py` covers
  `line_history_steps` for repeats, a single row, two markets and empty input,
  and `pytest` passes.
- [x] **Step 2 - `GET /nfl/games/{game_id}`** - add `NflGameDetailResponse` to
  `app/schemas/nfl.py`, `build_game_detail` to a new
  `app/services/nfl/game_detail.py`, and the route in `app/routers/nfl.py`. An
  unknown id raises `HTTPException(404)`. *Done when:*
  - `curl /nfl/games/<a week-3 id>` returns the game and its spread and total
    steps
  - `curl /nfl/games/999999` returns 404
  - `pytest` passes
- [x] **Step 3 - Web data layer and props util** - add the types to
  `types/nfl.ts`, `fetchNflGame` to `api/nfl.ts`, and a `useNflGame(gameId)`
  hook (key `['nfl', 'game', gameId]`, 5-minute `staleTime`). Add a pure
  `nflGameProps(games, gameId, position, period, now)` in
  `utils/nflGameProps.ts`:
  - it builds the week-wide categories with `buildNflPropBoard`, as of
    `min(now, kickoff - 1 ms)`, so a started game still shows the ranks the
    board showed just before its kickoff
  - it keeps only this game's rows, drops empty categories, and keeps
    prop-board market order

  *Done when:* `nflGameProps.test.ts` covers ranks matching the board for an
  upcoming game, a started game keeping its cards, the position and period
  filters, and an empty game, and `npm run test` passes.
- [x] **Step 4 - Page shell, route, hero and market block** - add
  `pages/NflGamePage.tsx` and `pages/nfl-game.css`, and register
  `/nfl/game/:gameId` in `App.tsx`. Build the hero and the market and model
  block (reusing `nflGameModelSummary`), with loading, error, not-found,
  no-odds and no-model states. Scope the gray edge variables on the page root.
  *Done when:* the page renders a real week-4 game at 1440 and 390 px against
  the mockup, `/nfl/game/999999` and `/nfl/game/abc` both show "Game not
  found" (a non-numeric id makes no request), and `npm run build` passes.
- [x] **Step 5 - Line movement chart** - add
  `components/nfl/NflLineMovementChart.tsx`, a step SVG built from the Step 2
  history, with the book label, open to current change, and an empty state.
  The x-to-time scaling goes in a pure helper in
  `utils/nflLineMovement.ts`. *Done when:* the helper's test covers scaling
  and a single point, the chart renders for a game with movement and shows the
  empty state for one without, and the build passes.
- [x] **Step 6 - Props section and evidence drawer** - add
  `components/nfl/NflGameProps.tsx`: period toggle, position chips, show-all,
  and card grids per market from `nflGameProps`. A card opens `NflEvidencePanel`
  in an antd `Drawer` with this game's alternates. The drawer is full width
  below 768 px, and the selected card is marked. *Done when:*
  - a card's rank and edge share match the same line on `/nfl/board`
  - the edge renders gray
  - the drawer opens and closes
  - a started game shows "Lines closed at kickoff"
- [x] **Step 7 - Sidebar** - add `components/nfl/NflGameSidebar.tsx`: injury
  report, depth changes, form and rest, and team stats as four cards. It
  reuses the notes types and `utils/nflGameNotes.ts` formatters. Each card has
  loading and empty states. *Done when:* the sidebar matches the mockup for a
  week-4 game, stacks under the main column below 1100 px, and nothing is set
  below 11px.
- [x] **Step 8 - Entry links** - the slate's `MatchupBar` gets an "Open game
  page" link. `NflEvidencePanel`'s game market section links to
  `/nfl/game/:gameId` when a game is known. It takes a `showGameLink` prop,
  false in the game page's drawer. *Done when:* clicking the link from both the slate and the
  prop board lands on the right game page.

## Files / areas

**API**
- `api/app/core/nfl_game_notes.py` - add `line_history_steps`
- `api/app/repositories/nfl.py` - add `get_game` and `get_game_line_history`
- `api/app/services/nfl/game_detail.py` - new
- `api/app/schemas/nfl.py`, `api/app/routers/nfl.py`
- `api/tests/test_nfl_game_notes.py`, plus a service test next to
  `test_nfl_game_notes_service.py`

**Web**
- `web/src/types/nfl.ts`, `web/src/api/nfl.ts`, `web/src/hooks/useNfl.ts`
- `web/src/utils/nflGameProps.ts` and `nflLineMovement.ts`, each with a test
- `web/src/pages/NflGamePage.tsx` and `nfl-game.css` - new
- `web/src/components/nfl/NflGameProps.tsx`, `NflGameSidebar.tsx`,
  `NflLineMovementChart.tsx` - new
- `web/src/App.tsx`
- `web/src/pages/NflIntelligencePage.tsx` - matchup bar link only
- `web/src/components/NflEvidencePanel.tsx` or `NflPropDetailSections.tsx` -
  game link only

## Data / contracts

**Load-bearing:** `GET /nfl/games/{game_id}` and `NflGameDetailResponse` are
the game page's anchor. 33b links to the route. Later game-level display
context extends this response or adds a sibling under `/nfl/games/{id}/`, never
another page. This follows 32a's rule for `MatchDetailResponse`.

```python
class NflLineStepSchema(_CamelModel):
    fetched_at: datetime
    line: float

class NflLineHistorySchema(_CamelModel):
    market: str            # 'spread' | 'total'
    book: str              # one book per market, same rule as game notes
    steps: list[NflLineStepSchema]   # pre-kickoff, consecutive repeats dropped

class NflGameDetailResponse(_CamelModel):
    game_id: int
    season: int
    week: int
    game_date: date
    start_utc: datetime | None
    away_team: str
    home_team: str
    status: str
    line_history: list[NflLineHistorySchema]   # empty when no odds are stored
```

- **Spread sign (confirmed).** A stored `spread` row's `line` is the home
  spread in book sign. The slate's `latest_odds` query already reads it
  straight into `odds.homeSpread`. The chart labels it with the home team code
  ("MIA +2.5").
- **Book choice.** History uses game notes' rule (DraftKings, else the book
  with the most rows). The slate's matchup bar uses DraftKings, else the
  latest row. The two agree whenever DraftKings has a row, and the chart
  always names its book.
- **Regular season only.** `get_game` filters `game_type = 'REG'`, as
  `get_games` does, so a playoff id is a 404 until playoffs are in scope.
- **No schema change.**

## Testing

Test gate on: `pytest` and `npm run test`.

**Logic tests:**
- `line_history_steps` - repeats, single row, two markets, empty
- the `build_game_detail` 404 path and response shaping, with the repository mocked
- `nflGameProps` - board parity, started game, filters, empty
- the `nflLineMovement` scaling helper

**Browser evidence:**
- screenshots of the page, the drawer and the empty states at 1440 and 390 px
- the same line's rank and edge share read on `/nfl/game/:id` and `/nfl/board`

**Final gate:** `npm run build` plus both test suites.

## Notes for the AI

- **Launching the API on Windows.** Plain `uvicorn` fails here; set the selector
  event loop first (see memory).
- **Layering.** Routers stay thin; SQL lives only in `app/repositories/nfl.py`;
  `line_history_steps` stays pure in `app/core/`.
- **No I/O through the slate.** Never call `build_slate` from the new service.
- **Reuse, don't fork.** Use `NflPropCard`, `NflEvidencePanel`,
  `buildNflPropBoard`, `groupNflPropRows`, `filterNflSlateLinesByPeriod`,
  `nflGameModelSummary`, `NFL_GAME_MODEL_CAVEAT` and the `nflGameNotes`
  formatters.
- **Colors and sizes.** Use only theme variables, with no hex in component CSS,
  and nothing below 11px (the user's standing preference).
- **Green rule.** Nothing on this page is green. Out tags use `--negative`, and
  Q and D tags use `--caution`.
- **No em dashes** in new comments or docs.
- **Prototypes.** `prototypes/` stays until the last item-33 sub-feature that
  uses it.

## Outcome

- **Shipped as specced.** `GET /nfl/games/{id}` and `/nfl/game/:gameId` with the
  hero, market and model block, line movement chart, week-ranked prop cards with
  the evidence drawer, and the notes sidebar. Links from the slate matchup bar
  ("Game page") and the evidence panel ("Open game page", hidden in the game
  page's own drawer).
- **Board parity confirmed.** James Cook, Josh Allen and Drake Maye rushing yards
  read #2 +70.6%, #16 +16.0%, #25 -10.4% on both `/nfl/game/52` and `/nfl/board`.
- **Beyond the spec:**
  - `navKeyForPath` now maps any `/nfl/` or `/tennis/` detail path to its
    sport's nav entry; before, unmatched paths fell back to Tennis, so the
    tennis match and player pages were right only by accident.
  - Team records in the hero stay blank until the slate loads, rather than
    reading "No games yet".
  - Half and quarter periods always show every line, because partial-game lines
    are never rateable; "Show all" applies to full game only.
  - Sidebar injury tags use theme tokens (`--negative` for Out, `--caution` for
    D and Q) instead of antd presets; the old notes panel is untouched until 33b.
- **Known limits.** A direct link to an older week waits on a cold
  `build_slate` (about 25 s for week 3); the hero and chart load without it.
  Week-4 injury reports were not yet ingested at completion.
- **Checks.** `pytest` 1,927 passed; `npm run test` 386 passed; `npm run build`
  passed; browser at 1440, 1000 and 390 px; no text under 11px on the page.

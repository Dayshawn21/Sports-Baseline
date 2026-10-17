# Feature: Line-only prop display

**From build-plan:** feature 35
**Status:** completed (2026-10-05)

## Goal

Show all 9 line-only NFL markets that item 34 stores on the game page, so the
owner can read a kicker's, punter's or QB's PrizePicks line next to how that
player actually did recently. The section answers "what is the line, and what
has he done lately" without the app claiming an opinion. There is no
projection, edge, rank, P(over) or signal color.

| Market | Label | Recent value (from `nfl_player_weekly_stats`) |
|---|---|---|
| `receiving_targets` | Rec Targets | `targets` |
| `passing_touchdowns` | Pass TDs | `passing_tds` |
| `interceptions` | INT | `interceptions` |
| `rushing_receiving_yards` | Rush+Rec Yds | `rushing_yards + receiving_yards` |
| `passing_rushing_yards` | Pass+Rush Yds | `passing_yards + rushing_yards` |
| `passing_rushing_receiving_touchdowns` | Pass+Rush+Rec TDs | `passing_tds + touchdowns` |
| `field_goals_made` | FG Made | `fg_made` |
| `kicking_points` | Kicking Points | `3 * fg_made + pat_made` |
| `punts` | Punts | `punts` |

## Design reference

- **Placement:** [35-game-page-props-k-filter.png](../../reference/35-game-page-props-k-filter.png),
  the game page's Props panel with the K filter showing "No lines for this
  period and position". The new section goes inside this panel, below the
  modelled markets, and uses the same Period and Position controls.
- **Look:** the existing panel's tokens and type (`nfl-game.css`,
  `nfl-prop-board.css`). Everything is gray (`--text-secondary` and
  `--text-primary`, never `--nfl-green` or `--nfl-red`), and no text is under
  11px.

## In scope

- **Settlement core:** `app/core/nfl_line_only.py` turns a weekly stat row into
  a market's value, using the rules item 34 fixed. It is pure and shared with
  any later grading item.
- **Endpoint:** `GET /nfl/games/{id}/line-only-props`, a sibling of
  `/nfl/games/{id}` (33a's rule). It returns:
  - each linked line-only line for the game, taking each provider prop's
    latest snapshot fetched before kickoff
  - each of those players' last 5 regular-season games before this game,
    across seasons
- **Web section:** an "Other lines" block in the game page's Props panel,
  under the modelled markets:
  - grouped by market
  - one card per player, in the modelled props' card grid, with all of that
    player's rungs (standard, goblin and demon lines) and their last 5 values
    as bars
  - a gray "over N of 5" count against the standard line, when the player has
    one
- **Filters:**
  - the same Position filter applies; punters show under All only, since there
    is no P chip
  - the section shows on Full game only
  - "Show all lines" does not affect it: every line-only line shows, since
    none is rateable
- **States:**
  - the section is hidden when the game has no line-only lines for the filter
  - while loading or on an error it shows inside the section, and the rest of
    the page is unaffected
- **Empty-message wording:** the modelled "No lines for this period and
  position" message becomes "No modelled lines for this period and position",
  so it no longer contradicts the new section.

## Out of scope

- **First-half and first-quarter line-only lines.** Weekly stats are
  full-game only, so their recent values would be wrong. They stay stored and
  unshown.
- **A P position chip, the player page, the prop board and slate cards.**
  Each is a later item if wanted.
- **Settling, grading or a hit-rate report** of stored line-only lines, and
  any projection. Those come with a later item under a pre-registered rule.
- **A finished game's actual result** beside its line. That is grading, so it
  is also later work.
- **Any change to `/nfl/slate`, `build_slate`, 34a's modelled-market filter,
  board parity, or the modelled cards.**

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Settlement core** - `app/core/nfl_line_only.py`:
  - **Function:** `line_only_value(market: NflLineOnlyMarket, row: Mapping[str,
    int | None]) -> float | None`, implementing the Goal table.
  - **Null rule:** any input column that is NULL makes the value `None`,
    never a partial sum.
  - **Columns:** `LINE_ONLY_COLUMNS` lists every weekly-stat column the
    function reads, so the repository selects exactly those.
  - **Tests:** `tests/test_nfl_line_only.py`:
    - each of the 9 markets on one row
    - `kicking_points` is `None` when either `fg_made` or `pat_made` is NULL
    - a combo is `None` when either part is NULL
    - every `NflLineOnlyMarket` value is covered, so a new market fails the
      test until it gets a rule

  *Done when:* pytest passes.

- [x] **Step 2 - Repository reads** - two functions in `app/repositories/nfl.py`:
  - **Lines:** `get_line_only_lines(db, game_id)`. For each provider prop on
    the game, the latest snapshot with `fetched_at < start_utc`, linked to a
    player, `segment = 'full_game'`, and a market in `NflLineOnlyMarket`. It
    returns player id, name and position, provider team (the `raw_json` key
    `get_unmatched_slate_lines` reads), market, odds type, line and fetch
    time.
  - **Recent games:** `get_recent_stat_rows(db, player_ids, season, week,
    limit=5)`. For each player, the last `limit` regular-season weekly rows
    strictly before (`season`, `week`), reading `LINE_ONLY_COLUMNS` plus
    season, week and opponent team code. Every query filters `sport = 'nfl'`.
  - **Tests:** SQL capture in `tests/test_nfl_repository.py`:
    - the market filter lists exactly the 9 line-only markets
    - the game, full-game and pre-kickoff conditions are present
    - the recent-games as-of bound and the per-player limit are present

  *Done when:* pytest passes, and a one-off read against the local database
  returns the MNF game's line-only lines and 5 recent rows for a kicker.

- [x] **Step 3 - Endpoint** -
  - **Schemas** (`app/schemas/nfl.py`):
    - `NflLineOnlyRecentSchema`: `season`, `week`, `opponent`, and `value`
      (nullable)
    - `NflLineOnlyLineSchema`: `player_id`, `player_name`, `position`,
      `team`, `market`, `odds_type`, `line`, `fetched_at`, and `recent` (a
      list, newest first)
    - `NflLineOnlyPropsResponse`: `game_id` and `lines`
  - **Service:** `app/services/nfl/line_only_props.py`
    `build_line_only_props(db, game_id)`. It returns `None` for an unknown
    game, and fills each line's `recent` through `line_only_value`.
  - **Route:** `GET /nfl/games/{game_id}/line-only-props` returns 404 for an
    unknown game.
  - **Tests:** the service with a mocked repository:
    - a kicker's kicking-points values come out as 3 × FG + PAT
    - a player with no prior games gets an empty `recent`
    - an unknown game gives `None`

  *Done when:*
  - `curl /nfl/games/<MNF id>/line-only-props` lists that game's kicking,
    punting and QB lines, each with up to 5 recent values
  - an unknown id returns 404
  - `/nfl/slate` and `/nfl/games/{id}` are byte-identical to before this step
  - pytest passes

- [x] **Step 4 - Web data layer** -
  - **Plumbing:** types in `web/src/types/nfl.ts`, `fetchNflLineOnlyProps` in
    `api/nfl.ts`, and a `useNflLineOnlyProps(gameId)` hook (query key `['nfl',
    'game', gameId, 'line-only']`, 5-minute `staleTime`).
  - **Labels:** the 9 market labels in `utils/nflLabels.ts`.
  - **Pure util:** `utils/nflLineOnly.ts`
    `lineOnlyGroups(lines, position)`:
    - groups by market in the Goal table's order, then one row per player
      (by name), each with that player's rungs sorted by line
    - computes `overCount` and `count` against the standard rung only (null
      when there is no standard rung)
    - drops `null` recent values from the count
    - applies the position filter (`all` keeps everyone, including punters)
  - **Tests:** `utils/nflLineOnly.test.ts`:
    - grouping and ordering
    - the over count against a standard line, including a push (equal, not
      over)
    - no standard rung gives null
    - null values skipped
    - the K filter keeps kickers and drops punters

  *Done when:* `npm run test` and `npm run build` pass.

- [x] **Step 5 - Game page section** -
  - **Component:** `components/nfl/NflLineOnlyProps.tsx`, rendered inside
    `NflGameProps` under the modelled markets, Full game only. It shows:
    - a heading "Other lines" with the note "not modelled · recent results
      only"
    - per market, a label and a `.nfl-prop-grid` of cards built on
      `.nfl-prop-card` (owner's request, 2026-10-05: cards, not a table). Each
      card shows:
      - a position badge and the name, linked to `/nfl/player/:id`
      - the main line (standard, else the lowest rung), with any other rungs
        listed as "Also 0.5 goblin · 2.5 demon"
      - the last 5 values as gray bars, with the standard line dashed
      - a footer with the values, oldest to newest like the bars, and "over
        3 of 5" when there is a standard line
    - no pick, edge, model or drawer: the cards do not open anything
  - **Styling:** gray only, and no text under 11px.
  - **States:** loading and error appear inside the section only, and an
    empty result hides it.
  - **Wording:** the modelled empty message becomes "No modelled lines for
    this period and position."

  *Done when:*
  - on the MNF game page, All shows the line-only section with recent values
  - K shows only kickers (FG Made and Kicking Points) with their last 5
    values
  - 1st half hides the section
  - a game with no line-only lines shows no section
  - the modelled cards, ranks and counts are unchanged
  - no console errors
  - checked with a screenshot, plus a 375px-wide screenshot with no
    horizontal scroll

- [x] **Step 6 - Full verification** - run `npm run build`, `npm run test`
  and `pytest`.

  *Done when:* all three pass.

## Files / areas

- **New:**
  - `api/app/core/nfl_line_only.py`, `api/tests/test_nfl_line_only.py`
  - `api/app/services/nfl/line_only_props.py`, with its service test
  - `web/src/utils/nflLineOnly.ts`, `web/src/utils/nflLineOnly.test.ts`
  - `web/src/components/nfl/NflLineOnlyProps.tsx`
- **API changed:**
  - `api/app/repositories/nfl.py`
  - `api/app/schemas/nfl.py`
  - `api/app/routers/nfl.py`
  - `api/tests/test_nfl_repository.py`
- **Web changed:**
  - `web/src/types/nfl.ts`, `web/src/api/nfl.ts`, `web/src/hooks/useNfl.ts`
  - `web/src/utils/nflLabels.ts`
  - `web/src/components/nfl/NflGameProps.tsx`
  - `web/src/pages/nfl-game.css`

## Data / contracts

**Load-bearing:**

- **`line_only_value(market, row)`** in `app/core/nfl_line_only.py` is the
  settlement rule for every line-only market. A later grading item imports
  it rather than restating the rules. Adding an `NflLineOnlyMarket` value
  requires a rule here, and the coverage test enforces that.
- **`GET /nfl/games/{id}/line-only-props`** returns `NflLineOnlyPropsResponse`
  (`gameId`, `lines[]` with `recent[]`). It is display only, and later
  line-only display context extends it.
- **Recent values are plain numbers.** "Over N of 5" is an anecdote and never
  colored, like 33c's past-line counts.
- **Unchanged:** `/nfl/slate`, `build_slate`, `MODELLED_MARKET_FILTER`,
  `/nfl/games/{id}` and every report.

## Testing

**Test gate is on.** These ship with tests:

- the settlement core: every market, the null rules and full coverage
- the repository SQL: the market list, the conditions and the as-of bound
- the service: value mapping, empty history and an unknown game
- the web grouping util: grouping, the over count, null handling and the
  position filter

**Not unit-tested:** the React component and the route wiring. They ride on
the step 3 `curl` checks and the step 5 browser screenshots.

## Notes for the AI

- **Game ids:** find the MNF game's id and a game with no line-only lines from
  the database when step 3 runs. Ids are not fixed here.
- **As-of rule:** recent games are strictly before this game's (`season`,
  `week`), the same cutoff `/projections` and `/slate` use, so a finished
  game never shows its own result in its own history.
- **Windows:** set the selector event loop before starting uvicorn (see
  memory). The NFL slate can stall (open question 40); the new endpoint must
  not call `build_slate`.
- **No AI attribution in commits, no em dashes, light comments.**

## Outcome

- **API:**
  - `GET /nfl/games/{id}/line-only-props`, served by
    `app/services/nfl/line_only_props.py`, with a 404 for an unknown game
  - settlement rules in `app/core/nfl_line_only.py` (`line_only_value`,
    `LINE_ONLY_COLUMNS`, and a coverage test over every `NflLineOnlyMarket`)
  - two reads in `app/repositories/nfl.py`: `LINE_ONLY_MARKET_FILTER`,
    `get_line_only_lines` and `get_recent_stat_rows`
- **First read (game 64, ATL at NO, 2026 week 4):** 72 line-only lines across
  all 9 markets. Daniel Carlson's Kicking Points history (3, 10, 6, 12, 4)
  matched his raw FG and PAT counts.
- **Parity:** `/nfl/slate?season=2026&week=4` (16.45 MB) and `/nfl/games/64`
  were byte-identical with and without this item's API code.
- **Web:** an "Other lines" section in the game page's Props panel, Full game
  only, using the same position filter. The owner asked for cards instead of
  the first table version (2026-10-05). Each card is built on `.nfl-prop-card`
  in `.nfl-prop-grid`, and shows:
  - a position badge and the linked name
  - the main line (standard, else the lowest rung) and the other rungs
  - gray bars for the last 5 games, with the standard line dashed
  - values oldest to newest, matching the bars, and "over N of 5"
  - no pick, edge, model or drawer
- **Browser checks:**
  - 28 cards under All and 4 under K; the section is hidden on 1st half and
    on game 49, which has no line-only lines
  - gray and near-white only, with text 11px or larger
  - no horizontal scroll at 375px
  - no new console errors
- **Checks:** `npm run build`, `npm run test` (460), `pytest` (2226).
- **Follow-ups:**
  - punters show under All only, since there is no P chip
  - a player with many rungs gets a long "Also" line

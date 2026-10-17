# Feature: NBA projection on the game page

**From build-plan:** feature 20g2 (second of 20g's four parts)
**Status:** complete (2026-10-07)

## Goal

Serve NBA's first projection. Each modelled PrizePicks line on an NBA game gets
20f's reference projection (`nba-reference-v1`), and assists lines also get
20g1's P(over). The game page shows them as gray prop cards above the remaining
line-only cards. Nothing is colored, ranked or picked: that waits for 20g4's
ranking check.

It also builds the projection function that 20g3 freezes, so the number on the
page and the number frozen before tip-off come from one function.

## Design reference

No mockup. The target is the shipped NBA game page (20e3) and its gray
`.nfl-prop-card` cards (`components/nba/NbaLineOnlyProps.tsx`). A modelled card
is a line-only card plus a projection row: the projection, its gray gap to the
line, and P(over) / P(under) when the market has a fit. The NFL card model is
not reused: it is tied to NFL's week-wide prop board.

## In scope

- **Market split, NFL's pattern (load-bearing):** `NbaPropMarket` holds the
  nine modelled markets (20f's `BACKTEST_MARKETS`), and `NbaLineOnlyMarket`
  keeps only `double_double`. Stored strings are unchanged, so no data moves.
- **A modelled-market filter**, `NBA_MODELLED_MARKET_FILTER` in
  `app/repositories/nba.py`, which 20g3 and 20g4 must apply to every reader
  that projects, freezes or grades NBA lines.
- **A pure projection module, `app/core/nba_projection.py`:** eligibility, the
  reference projection, the gap to the line and P(over), from a player's prior
  played games.
- **`GET /nba/games/{id}/props`** (`NbaPropsResponse`), a sibling of 20e1's
  line-only endpoint: each linked modelled line at its latest pre-tip
  snapshot, with its projection block and the player's last 5 results.
- **Web:** types, API and hook, a pure card model, and an `NbaProps` section on
  the game page above "Other lines".

## Out of scope

- Freezing predictions, `NbaPropSource`, workflows (20g3).
- Ranking, picks, break-even comparison, coloring, the model page (20g4).
- Double-double projection (binary; it stays line-only).
- P(over) for the eight hidden markets, or any new distribution method.
- Projections on the slate cards, a prop board, or an NBA player page.
- Injuries or minutes news: the projection is the 20-game mean only.
- Changing 20f's harness history depth (see Notes).

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Split the NBA markets** - before any change, run
  `python -m app.ingest.prizepicks_nba --dry-run` and keep its counts. Then in
  `app/nba/markets.py`: `NbaPropMarket` (the nine, in today's order) and
  `NbaLineOnlyMarket` (`double_double`), with
  `NbaMarket = NbaPropMarket | NbaLineOnlyMarket`; PrizePicks aliases map to
  whichever enum holds the market. `line_only_value` keeps its name and module
  (20c's one settlement rule) and takes any `NbaMarket`. `BACKTEST_MARKETS`
  becomes `tuple(NbaPropMarket)`. The repository's line-only filter now covers
  double-double only, and `NBA_MODELLED_MARKET_FILTER` names the nine.

  *Done when:* `test_nba_markets.py` covers every alias landing in exactly one
  enum and the two enums being disjoint, with no stored value renamed;
  `BACKTEST_MARKETS` is the same nine values in the same order (the 20f and
  20g1 tests pass unchanged); the dry run after the change prints the same
  mapped and unsupported counts as before (the board may move between runs,
  so both runs are taken minutes apart and any difference is explained);
  `/nba/games/21318/line-only-props` returns only its double-double lines and
  `/nba/games/21320/line-only-props` returns none; the full suite passes.

- [x] **Step 2 - The projection (pure)** - `app/core/nba_projection.py`:
  `project_line(prior, market, line) -> NbaLineProjection` from a player's
  prior played games (oldest first, the 20f definition):
  - not eligible (fewer than 10 prior games, or under 20 prior minutes): no
    projection, with flag `few_prior_games` or `low_minutes`;
  - eligible: `projection` (20f's reference arm), `games_in_sample` (up to
    20), `prior_minutes`, and `gap` = projection minus line, rounded to 2;
  - P(over), P(under) and `over_probability_version` only when the market is
    in the generated fit's `SHOWN_MARKETS`, the fit's projection version
    equals `NBA_PROJECTION_MODEL_VERSION`, the line is not an integer and the
    projection is positive; otherwise all three are None, with flag
    `no_over_probability` (market not fitted or fit stale) or `integer_line`.

  *Done when:* unit tests cover each branch: 9 vs 10 prior games, 19.9 vs 20.0
  minutes, a 20-game window over 25 games, the gap's sign and rounding,
  assists with P(over) equal to
  `over_probability(QUANTILES_BY_MARKET["assists"], ...)`, points without it,
  an integer assists line, a stale fit version (monkeypatched) hiding P(over),
  and `model_version` always `nba-reference-v1`.

- [x] **Step 3 - `GET /nba/games/{id}/props`** - repository reads: the game's
  linked full-game lines in modelled markets at their latest pre-tip snapshot
  (20e1's line-only query, parameterized by the market filter), and each
  player's last 20 played `REG`/`PIN`/`PST` games dated before the game,
  **from every stored season**, with minutes and the settled stats. A pure
  builder in `app/services/nba/props.py` shapes `NbaPropsResponse`; the router
  adds the route. A `PRE`, NFL or missing game id is a 404, as on the sibling
  endpoints.

  *Done when:* builder tests cover ordering (market, player, line), an
  ineligible player, and the recent list; a recorded-SQL test shows the
  `'nba'` literals, the modelled-market filter, the pre-tip cutoff and no
  season limit on history; against the running API, `/nba/games/21320/props`
  returns all 61 of its lines (none are double-double), Cunningham's and
  Tatum's projections equal the mean of their last 20 played games by a
  direct query, assists lines carry P(over) except integer lines, and the
  three 404 cases hold.

- [x] **Step 4 - Web types, API, hook and card model** - `types/nba.ts`
  mirrors `NbaPropsResponse`; `fetchNbaProps(id)` / `useNbaProps(id)` (key
  `['nba', 'game', id, 'props']`); `utils/nbaProps.ts`:
  - `nbaPropGroups(lines)`: grouped by market (`NbaPropMarket` order), one
    card per player with every rung, the main rung as on the line-only cards
    (standard, else the lowest);
  - the main rung's projection row: `Proj 7.4`, `gap +1.9` (signed),
    `P(over) 42% · under 58%` only when present;
  - each "Also" rung with its own P(over) when present (`9.5 demon · 31%`);
  - the flag text: `No projection: fewer than 10 earlier games`, `No
    projection: under 20 minutes a game`, `P(over) not fitted for this
    market`, `Whole-number line: no P(over)`.

  *Done when:* `nbaProps.test.ts` covers grouping, rungs, each flag text, a
  card with and without P(over), an "Also" rung with P(over), and the gap's
  sign and rounding; `npm run build` and `npm run test` pass.

- [x] **Step 5 - The Props section on the game page** - `NbaProps` renders a
  "Props · reference projection · gray until the ranking check adopts a
  slice" section above "Other lines": gray `.nfl-prop-card` cards (team badge,
  name, position and market, main rung and "Also" rungs, the projection row,
  recent bars with the standard line dashed, "over N of 5"), with its own
  loading, error and empty states, so a failure never blanks the page.

  *Done when:* screenshots of `/nba/game/21320` (desktop and 390px) show
  Cunningham's and Tatum's cards with projections and the assists cards with
  P(over); `/nba/game/21318` shows its double-double cards under "Other
  lines"; `/nba/game/17568` (a 2025-26 final with no lines) shows neither
  section; a DOM audit finds no text under 11px and nothing computing to the
  theme's green or red; an NFL game page is unchanged; `npm run build` and
  `npm run test` pass.

## Files / areas

- New: `api/app/core/nba_projection.py`, `api/app/services/nba/props.py`,
  `api/tests/test_nba_projection.py`, `api/tests/test_nba_props.py`,
  `web/src/utils/nbaProps.ts`, `web/src/utils/nbaProps.test.ts`,
  `web/src/components/nba/NbaProps.tsx`
- Changed: `api/app/nba/markets.py`, `api/app/core/nba_line_only.py` (type
  only), `api/app/core/nba_projection_backtest.py` (`BACKTEST_MARKETS`),
  `api/app/repositories/nba.py`, `api/app/schemas/nba.py`,
  `api/app/routers/nba.py`, `api/app/services/nba/line_only_props.py`,
  `api/tests/test_nba_markets.py`, `api/tests/test_nba_repository.py`,
  `web/src/types/nba.ts`, `web/src/api/nba.ts`, `web/src/hooks/useNba.ts`,
  `web/src/pages/NbaGamePage.tsx`
- Read only: `api/app/core/nba_over_probability_fit.py`,
  `api/app/core/nfl_over_probability.py`

## Data / contracts

No schema change.

**Load-bearing for 20g3 and 20g4:**
- **`NbaPropMarket`** (nine modelled markets) and **`NbaLineOnlyMarket`**
  (`double_double`), disjoint, stored strings never renamed. Moving a market
  into `NbaPropMarket` widens `NBA_MODELLED_MARKET_FILTER` automatically.
- **`project_line`** in `app/core/nba_projection.py` is the one projection
  function: the page serves it now, 20g3 freezes it.
- **History depth:** a player's prior games are every stored played
  `REG`/`PIN`/`PST` game dated before the game's Eastern date, any season (the
  depth 20g1's holdout was scored on).
- **`NbaPropsResponse`** (`GET /nba/games/{id}/props`, camelCase):

```
NbaPropsResponse
  gameId
  modelVersion: 'nba-reference-v1'
  lines: [{
    playerId, playerName, position, team, market, oddsType, line, fetchedAt,
    projection: float | null,          # null when not eligible
    gamesInSample: int, priorMinutes: float | null,
    gap: float | null,                 # projection - line, 2 places
    pOver: float | null, pUnder: float | null,
    overProbabilityVersion: 'nba-pover-v1' | null,
    flags: string[],                   # few_prior_games | low_minutes | no_over_probability | integer_line
    recent: [{ gameDate, opponent, value }]   # last 5 played, newest first
  }]
```

- Null never means zero: a missing projection or P(over) is "not served", and
  the card says why.
- **No signal:** the gap and P(over) are gray, never sorted by, never compared
  to a payout, until 20g4's ranking check adopts a slice. "Gap", not "edge",
  so nothing on the page reads as a pick.

## Testing

- Test gate on: Step 1 market tests, Step 2 unit tests, Step 3 builder and
  recorded-SQL tests, Step 4 `nbaProps.test.ts`. Step 5 rides on screenshots,
  the DOM audit and build.
- `cd api && .venv\Scripts\python.exe -m pytest`; `cd web && npm run build`
  and `npm run test`.

## Notes for the AI

- **Opening night is 2026-10-20.** 20g3 freezes `project_line`'s output, so
  keep it pure and its inputs explicit; do not read the clock inside it.
- **History depth differs from 20f's harness**, which loads one prior season.
  20g1's holdout used every stored season, and so does serving. Aligning the
  harness is a later `/fix`, noted here, not done.
- Step 1 must not change what PrizePicks ingest stores: same `market` strings,
  same aliases, same unsupported list. The PrizePicks dry run is free but
  rate-limited (honor `Retry-After`); two runs are enough.
- Read the generated fit only through its module constants; an empty
  `SHOWN_MARKETS` must simply mean no P(over).
- Every `sport_*` reference carries `'nba'`; never read `PRE`. The card's team
  badge is the line's provider team, as 20e1's line-only cards use.
- Web: TanStack Query only, `~/` imports, no `any`, theme variables, no text
  under 11px, nothing green or red (keep the `.nfl-slate` root).
- `X | None`, no `Any`, `app/core` pure, repositories own SQL, no em dashes,
  comment only the why.

## Results

`/check` on 2026-10-07 proved every done-when against the running app.

- **Step 1.** The PrizePicks NBA dry run printed 194 mapped lines with no
  unsupported stat types on master (09:17:35, from a temporary worktree) and on
  the branch (09:18:37). The alias map, stored strings, board segments and
  `BACKTEST_MARKETS` order are identical on both. `/nba/games/21318/line-only-props`
  returns its 2 double-double lines; `/nba/games/21320/line-only-props` returns none.
- **Step 3.** `/nba/games/21320/props` returns all 61 lines, none double-double.
  Cunningham and Tatum match a direct SQL mean of their last 20 played games
  (points 24.2 / 22.65, rebounds 5.0 / 10.45, assists 8.0 / 5.85). Every
  non-integer assists line carries P(over) and no other market does; game 21318's
  whole-number line (Wembanyama, 3.0 assists) has none, flagged `integer_line`.
  Preseason 22527, NFL 330 and missing 28029 are 404.
- **Step 5.** Headless Chromium (the API venv's Playwright): `/nba/game/21320`
  at 1440px and 390px shows 16 gray Props cards, assists with P(over)
  (Cunningham 9.5: 34% / 66%); `/nba/game/21318` shows Props and Other lines;
  `/nba/game/17568` shows neither. No text under 11px, no green or red in either
  props section, no horizontal scroll at 390px, and no console errors, failed
  requests or 4xx/5xx responses on any of the five loads, the NFL game page
  (`#/nfl/game/65`) included.
- **Suites:** `pytest` 2,459 passed; `npm run test` 504 passed; `npm run build`
  clean.

**Decisions made while building:**
- `REFERENCE_GAMES = 20` names 20f's window in `nba_projection_backtest.py`, and
  `project_line` reads it, so the served projection and the harness arm cannot
  drift (a test pins `project_line` to `ARMS["reference"]` in every market).
- A player with 10+ prior games but no settled value for the market is
  `few_prior_games`; an assists projection of 0 is `no_over_probability`.
- The page makes two box-score reads per request (20 prior games for the
  projection, the existing 5-game recent query for the bars).
- `mainRung` (`web/src/utils/nflLineOnly.ts`) is now generic over its rung type;
  NFL callers are unchanged. `NbaRecentBars` is exported from
  `NbaLineOnlyProps.tsx` so both NBA sections draw identical bars.
- Live checks never crossed a season boundary (both players' last 20 games are
  2025-26); the any-season read is covered by the recorded-SQL test.

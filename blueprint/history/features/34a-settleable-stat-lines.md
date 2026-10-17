# Feature: Settleable stat lines

**From build-plan:** feature 34a
**Status:** completed (2026-10-05)

## Goal

Start storing PrizePicks NFL lines for six markets the model does not project:

| PrizePicks stat | Stored market | Settles later from (`nfl_player_weekly_stats`) |
|---|---|---|
| Rec Targets | `receiving_targets` | `targets` |
| Pass TDs | `passing_touchdowns` | `passing_tds` |
| INT | `interceptions` | `interceptions` |
| Rush+Rec Yds | `rushing_receiving_yards` | `rushing_yards + receiving_yards` |
| Pass+Rush Yds | `passing_rushing_yards` | `passing_yards + rushing_yards` |
| Pass+Rush+Rec TDs | `passing_rushing_receiving_touchdowns` | `passing_tds + touchdowns` |

Line history exists only from the day the app stores it (the binding
constraint of items 25 and 27), so every week skipped is lost. Storing these
lines changes no projection, edge, rank, pick, report or page.

## In scope

- **Modelled-market filter:** every reader that would treat a stored line as
  a modelled market reads only the 9 `NflPropMarket` markets. The readers are:
  - `_LATEST_LINES_CTE`, which feeds the slate, the prop board, the game and
    player pages, frozen predictions (27i), 27a's replay and
    `get_unmatched_slate_lines`
  - `get_gradeable_prop_lines` (27a grading and the player page's past lines)
  - `get_frozen_coverage` (27j's coverage line)
- **Stored-only markets:** a stored-only market enum and its PrizePicks
  aliases in `app/nfl/markets.py`, so the existing ingest stores these lines
  through the unchanged shared pipeline (`prizepicks_props.run`) and relinks
  them to players and games.
- **Stat-name helper:** `market_for_prizepicks_stat` keeps returning only
  modelled markets, never raising on a stored-only one.

## Out of scope

- **Projecting, grading or showing these markets.** There is no slate row,
  board card, edge, P(over), frozen prediction, 27a grade or UI. A later item
  adopts a market through the usual pre-registered backtest.
- **A settlement report** for stored-only lines. Settling needs only the
  stored lines and the existing stat columns, so a later item can grade the
  whole history at once.
- **Kicking and punting** (34b).
- **"(Combo)" lines, defense, longest plays, quarter and half splits, and Rush
  TDs** (see the overview's item 34 notes).
- **`/nfl/prospects`.** It lists raw stored lines with `market: str` and is
  redirected in the web app, so the new markets appearing there is harmless.
- **Schema.** `sport_prop_lines.market` is free text with no check
  constraint, so no migration is needed.
- **Cron changes.** `nfl-prop-lines.yml` already runs the ingest; the new
  markets accrue once this is merged and pushed.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

The filter lands before any new market is stored, so no reader ever sees an
unmodelled market.

- [x] **Step 1 - Limit the projection readers to modelled markets** - in
  `app/repositories/nfl.py`:
  - **Filter:** one SQL fragment built from `NflPropMarket` values
    (`l.market IN ('passing_yards', ...)`). The values are code constants,
    not user input. It is applied in `_LATEST_LINES_CTE`,
    `get_gradeable_prop_lines` and `get_frozen_coverage`.
  - **Tests:** extend `tests/test_nfl_repository.py`:
    - the fragment lists exactly the 9 `NflPropMarket` values
    - each of the three readers' captured SQL carries it
  - **Parity, captured before the change and compared after:**
    - `python -m app.backtest.nfl_ranking_check --season 2026`
    - `python -m app.backtest.nfl_prizepicks_lines` (27a)
    - `python -m app.ingest.nfl_prop_predictions --dry-run`
    - `GET /nfl/slate?season=2026&week=4`, which the prop board, game page
      and player page lines also read
    - `GET /nfl/players/{id}` for one player with settled past lines
      (`get_gradeable_prop_lines` with a `player_id`)

  *Done when:*
  - every parity output is identical before and after (only modelled markets
    are stored today, so the filter must change nothing)
  - pytest passes

- [x] **Step 2 - Store the six markets** - in `app/nfl/markets.py`:
  - **Markets:** an `NflLineOnlyMarket` `StrEnum` with the six values in the
    Goal table.
  - **Aliases:** `NFL_PROPS.market_aliases` gains `rec targets`, `pass tds`,
    `int`, `rush+rec yds`, `pass+rush yds` and `pass+rush+rec tds`. These are
    the exact names from the 2026-10-05 skip log, lowercased. They match
    exactly, so `receiving yards (combo)` and the other combo names still
    skip.
  - **Helper:** `market_for_prizepicks_stat` in `app/ingest/prizepicks_nfl.py`
    returns `None` for a stored-only market instead of raising in
    `NflPropMarket(...)`.
  - **Tests:** extend `tests/test_prizepicks_nfl.py`, or the prop-sports
    tests:
    - each of the six names maps to its stored market
    - the `(Combo)` variants map to nothing
    - `market_for_prizepicks_stat` returns `None` for the six
    - every alias value is either an `NflPropMarket` or an
      `NflLineOnlyMarket`, and the two sets do not overlap

  *Done when:*
  - `python -m app.ingest.prizepicks_nfl --dry-run` no longer lists the six
    in "skipped unsupported stat types", while the combo variants still do
  - pytest passes

- [x] **Step 3 - First real ingest and parity with new rows present** -
  - **Ingest:** run `python -m app.ingest.prizepicks_nfl` once against the
    local database. This writes, and it is what the cron does four times a
    week. Ask before running it.
  - **Rows:** list stored rows by market for the six. Check that most link to
    a player and a game after the ingest's own relink.
  - **INT position check:** every stored `interceptions` line's
    `raw_json ->> 'player_position'` must be QB, because the `interceptions`
    column counts interceptions thrown. If any is a defender, stop and flag it
    before step 4.
  - **Parity:** re-run step 1's parity commands. Their output must match step
    1's, with the new rows now in the table.

  *Done when:*
  - rows exist for each market the board offered
  - every stored `interceptions` line is on a QB
  - every parity output still matches step 1

- [x] **Step 4 - Full verification** - run `npm run build`, `npm run test`
  and `pytest`.

  *Done when:* all three pass.

## Files / areas

- **Changed:**
  - `api/app/repositories/nfl.py`
  - `api/app/nfl/markets.py`
  - `api/app/ingest/prizepicks_nfl.py`
  - `api/tests/test_nfl_repository.py`
  - `api/tests/test_prizepicks_nfl.py`
- **Unchanged and relied on:**
  - `app/ingest/prizepicks_props.py`, which stores any market the config maps
  - `app/repositories/sport_props.py`, whose relink covers every market
  - `get_frozen_gradeable_lines`, which joins frozen predictions, and no
    stored-only line is ever frozen
  - `get_latest_prop_lines` (`/nfl/prospects`), deliberately unfiltered
  - `app/services/nfl/props_provider.py`, an unused stub that nothing imports

## Data / contracts

**Load-bearing for 34b and any later market adoption:**

- **Two NFL market sets:**
  - `NflPropMarket`: the 9 modelled markets. Only these reach the projection
    readers.
  - `NflLineOnlyMarket`: lines stored for history only.
  - A market moves from line-only to modelled only through an item that
    projects it under the pre-registered backtest rules. That move also
    widens the reader filter automatically, because the filter is built from
    `NflPropMarket`.
- **The six stored market strings** in the Goal table are written into
  `sport_prop_lines.market` and are never renamed. A later settlement report
  uses them.
- **The modelled-market filter is the guard.** Any new reader of
  `sport_prop_lines` that feeds projections must apply it.
- **Unchanged:** the schema, every response, every report, and every stored
  row of the 9 modelled markets.

## Testing

**Test gate is on.**

- **Filter and readers** (step 1): the fragment's exact market list, and its
  presence in each reader's captured SQL.
- **Aliases** (step 2): each name maps to its market, combos map to nothing,
  the two market sets are disjoint and every alias lands in one of them, and
  the helper never raises.

**Not unit-tested:** the real ingest and the parity runs. They are evidence
in step 3, against the local database.

**Parity can be slow.** The slate and 27a replays go through
`get_slate_lines`, which stalls intermittently (open question 40). Retry once
rather than treat a slow run as a failure; the output must still match.

## Notes for the AI

- **Windows API launch:** set the selector event loop before starting uvicorn
  (see memory). Run CLIs from `api/` with the venv python.
- **The local scheduled task `ingest_daily`** runs ingest from the working
  folder on whatever branch is checked out. With this branch checked out it
  stores the six markets too, which is fine once step 1's filter is in place.
  Never leave the tree with step 2 applied but step 1 missing.
- **Commit attribution:** no AI attribution in commits.
- **No em dashes**, and light comments. Comment why the filter exists (a
  stored line is not necessarily a modelled market), not what it does.

## Outcome

- **Shipped:**
  - `MODELLED_MARKET_FILTER` in `app/repositories/nfl.py`, applied to
    `_LATEST_LINES_CTE`, `get_gradeable_prop_lines` and `get_frozen_coverage`
  - `NflLineOnlyMarket` and six exact PrizePicks aliases in
    `app/nfl/markets.py`
  - `market_for_prizepicks_stat` returning only modelled markets
- **Parity before any new market existed:** these five outputs were
  byte-identical before and after the filter:
  - `nfl_ranking_check --season 2026`
  - `nfl_prizepicks_lines`
  - `nfl_prop_predictions --dry-run`
  - `GET /nfl/slate?season=2026&week=4` (16.3 MB)
  - `GET /nfl/players/2347`
- **First real ingest (2026-10-05, Monday, mostly the MNF board):** 958 lines
  stored, all linked to a player and a game:
  - `rushing_receiving_yards` 31, all RB
  - `passing_rushing_yards` 28
  - `passing_touchdowns` 17 full game + 2 Q1
  - `receiving_targets` 12, RB, TE and WR
  - `interceptions` 10 full game + 2 Q1
  - `passing_rushing_receiving_touchdowns` 2
- **INT check passed:** all 12 interception lines were on QBs (Prescott,
  Penix, Shough, Daniels), so they settle against interceptions thrown.
- **Parity with the new rows present:**
  - Unchanged: the ranking check, 27a grading and the player page.
  - Changed only by the same ingest's fresh modelled-market snapshots for the
    scheduled MNF game: 464 slate lines added, 421 older snapshots replaced,
    all in the 9 modelled markets. That is 43 new props, matching the freeze
    dry run's 612 to 655.
  - No line-only market appeared in the slate.
- **Checks:** `npm run build`, `npm run test` (449), `pytest` (2186).
- **Accrual starts on push.** The `nfl-prop-lines.yml` cron stores the new
  markets only once this code is on the pushed branch.

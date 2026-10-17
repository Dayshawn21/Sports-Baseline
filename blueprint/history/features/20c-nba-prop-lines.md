# Feature: NBA prop lines

**From build-plan:** feature 20c
**Status:** complete (2026-10-06)

## Goal

Store PrizePicks NBA player lines through the shared 17c pipeline, linked to
`sport_players` and `sport_games` rows that 20b loaded. Every market is
line-only: stored for line history, never projected, graded or shown. NBA line
history exists only from the day the app stores it (the binding constraint of
items 25 and 27). Opening night is 2026-10-20, and its board has been posted
since 2026-08-20, so storage should start before the season does.

## In scope

- **`NBA_PROPS` config** (`SportPropConfig`) and an `NbaLineOnlyMarket` enum in
  `app/nba/markets.py`, the counterpart of `app/nfl/markets.py`.
- **Full game only:** the `NBA` league. `NBA1H`, `NBA2H` and `NBA1Q` are
  recognized as segments but kept off the board, because no stored data settles
  a half or a quarter. `NBAP` (preseason, confirmed 2026-10-06), `NBASZN`,
  `NBA4Q`, `NBASL` and `NBA SERIES` are never stored.
- **Markets: only the 10 stat names seen on the board** (20a's rule; probe
  2026-10-06 matched 20a's list exactly). Other names are logged as unsupported
  by the existing ingest warning and added by a later `/fix` once seen
  in-season.
- **A settlement rule for every stored market**, pure, in
  `app/core/nba_line_only.py`. A coverage test fails if a market has no rule.
- **Linking:**
  - PrizePicks-to-ESPN team codes
  - accent folding (PrizePicks sends `Egor Dëmin`, ESPN stores `Egor Demin`)
  - position ignored (see Notes)
  - the existing `resolve_player` and `find_game_id` reused unchanged
- **`PropLineSource` protocol:** the part of `SportPropSource` that ingest and
  relink actually use (`config`, `load_resolver`). NBA implements only this
  until 20g.
- **CLI** `python -m app.ingest.prizepicks_nba [--dry-run] [--relink]`.
- **Workflows:**
  - a new `nba-prop-lines.yml`, twice daily, October to June
  - a relink step in `nba-ingest.yml` after the box scores load
- `AGENTS.md` ingest command list gains the NBA line.

## Out of scope

- Projections, frozen predictions, the ranking check and the `PROP_SOURCES`
  registry entry: all 20g. `prop_source("nba")` keeps raising `KeyError`
  (pinned by `tests/test_sport_registry.py`).
- Any display (20e), game odds (20d).
- Markets not yet posted (Fantasy Score, Steals, Turnovers and others): a later
  `/fix` maps them from the unsupported-stat log. Fantasy Score also needs
  PrizePicks' NBA formula confirmed (the 27f lesson).
- "(Combo)" two-player lines, half and quarter lines, preseason (`NBAP`) lines.
- Renaming `app/core/nfl_resolution.py` / `nfl_names.py` to sport-neutral
  modules. NBA imports them as they are; a rename would touch every NFL
  importer for no behavior change.
- Any migration: `sport_prop_lines` already takes `sport = 'nba'`.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Line-source protocol** - split `PropLineSource` (`config`,
  `load_resolver`) out of `SportPropSource` in `app/services/sport_props.py`,
  with `SportPropSource(PropLineSource, Protocol)` adding the rest unchanged.
  `prizepicks_props.run` and `relink` take a `PropLineSource`. Type-only:
  no runtime change. *Done when:*
  - `pytest` passes in full, including `test_sport_props_pipeline.py` and
    `test_prizepicks_props.py`, with no test edited
  - `git diff` touches only `sport_props.py` and `prizepicks_props.py`
- [x] **Step 2 - NBA config and markets** - `app/nba/__init__.py` and
  `app/nba/markets.py`: `NbaLineOnlyMarket` (10 values, table under Data /
  contracts) and `NBA_PROPS`. Plus `tests/test_nba_markets.py`. *Done when*
  tests pass for:
  - league selection over the probed catalog names: only `NBA` is selected,
    as `full_game`
  - `NBA1H` maps to `first_half` and stays off the board
  - `NBAP`, `NBASZN`, `NBA4Q`, `NBASL`, `NBA SERIES` and every `WNBA*` name
    map to no board segment
  - each of the 10 board names maps to its market, case-insensitively
  - `Points (Combo)` and `Steals` map to None
- [x] **Step 3 - Settlement rules** - `app/core/nba_line_only.py`:
  `line_only_value(market, row) -> float | None` over an
  `nba_player_game_stats` row (a mapping of column to value). Plus
  `tests/test_nba_line_only.py`. *Done when* tests pass for:
  - every `NbaLineOnlyMarket` has a rule (coverage test)
  - each single stat and each sum on a fixture row
  - double-double gives 1 for 10+ in two of points, rebounds, assists, steals
    and blocks; 1 for a triple-double; 0 for 10+ in one category
  - a DNP row (`did_not_play` true, stats NULL) gives None, never 0
  - a row missing a summed column gives None
- [x] **Step 4 - Name and team helpers** - `app/core/nba_names.py`:
  - `espn_team_code(code)`: `NYK`->`NY`, `SAS`->`SA`, `GSW`->`GS`,
    `NOP`->`NO`, `UTA`->`UTAH`, `WAS`->`WSH`; other codes upper-cased and
    passed through, blank gives None
  - `fold_name(name)`: NFKD accent folding to ASCII
  - plus `tests/test_nba_names.py`

  *Done when* tests pass for:
  - each mapped code, a pass-through code (`BOS`), and blank or None
  - every mapped value is one of the 30 stored ESPN codes, listed in the test
  - `Egor Dëmin` gives `Egor Demin`, `Nikola Jokić` gives `Nikola Jokic`, and
    an ASCII name is unchanged
- [x] **Step 5 - Resolver** - `app/core/nba_resolution.py`:
  `build_resolver(candidates, game_index, aliases) -> LineResolver`. It folds
  provider and candidate names, maps the team, calls `resolve_player` with position
  `None`, and calls `find_game_id` with the ESPN code. Also:
  - `nba_repo.get_player_candidates(db)`: id, name, team code from
    `sport_players.team_id`, position; `sport = 'nba'`
  - `app/services/nba/prop_source.py`: `NbaPropSource(config, load_resolver)`
  - `tests/test_nba_resolution.py`, in-memory candidates

  *Done when* tests pass for:
  - `Egor Dëmin` (BKN) links to the stored `Egor Demin`
  - `Stephen Curry` vs `Seth Curry` resolve by full name
  - a `NYK` line at `2026-10-20 19:00-04:00` gets the NY game dated 2026-10-20
  - a `22:30-04:00` tip (next UTC day) still gets that game
  - an unstored rookie gives `no_candidate` with a NULL player but still gets
    the game
  - a hyphenated position (`F-C`) never produces `contradicted`
- [x] **Step 6 - Ingest CLI and first live run** - `app/ingest/prizepicks_nba.py`
  (`run`, `relink`, argparse, the selector event loop on Windows, exit 75 on
  `PrizePicksRateLimited`, as `prizepicks_nfl.py`). *Done when:*
  - `--dry-run` prints a line count matching the probe's full-game board
    (about 194, all 10 markets, no `NBAP` rows)
  - a real run stores them with `sport = 'nba'`, `segment = 'full_game'`
  - the linkage log shows at least 95% of lines linked to a player; every
    unlinked one is listed by reason and checked by hand as genuinely
    unstored or ambiguous, never a wrong link
  - every line has a `game_id`, and spot checks of 5 lines match the player's
    team to a side of the game
  - `--relink` reports `rows changed: 0` straight after
  - NFL `sport_prop_lines` row count is the same before and after
- [x] **Step 7 - Workflows and docs** -
  - `.github/workflows/nba-prop-lines.yml`: daily 16:30 and 22:15 UTC,
    October to June, same shape and exit-75 handling as `nfl-prop-lines.yml`,
    no freeze step
  - a `--relink` step at the end of `nba-ingest.yml`
  - the `AGENTS.md` ingest line

  *Done when:*
  - both YAML files parse
  - neither cron time equals an `nfl-prop-lines.yml` time
  - the workflow commands match the AGENTS.md line exactly
  - full `pytest` passes

## Files / areas

- `api/app/services/sport_props.py`, `api/app/ingest/prizepicks_props.py` (protocol split)
- `api/app/nba/__init__.py`, `api/app/nba/markets.py` (new)
- `api/app/core/nba_line_only.py`, `api/app/core/nba_names.py`, `api/app/core/nba_resolution.py` (new)
- `api/app/repositories/nba.py` (`get_player_candidates`)
- `api/app/services/nba/__init__.py`, `api/app/services/nba/prop_source.py` (new)
- `api/app/ingest/prizepicks_nba.py` (new)
- `api/tests/test_nba_markets.py`, `test_nba_line_only.py`, `test_nba_names.py`, `test_nba_resolution.py` (new)
- `.github/workflows/nba-prop-lines.yml` (new), `.github/workflows/nba-ingest.yml`
- `AGENTS.md`

## Data / contracts

No schema change. Rows go into `sport_prop_lines` with `sport = 'nba'`,
`provider = 'prizepicks'`, `segment = 'full_game'`, and the same `raw_json`
shape NFL writes.

**`NbaLineOnlyMarket` (load-bearing: stored strings, never renamed):**

| PrizePicks name | Market | Settles on |
|---|---|---|
| `Points` | `points` | `points` |
| `Rebounds` | `rebounds` | `rebounds` |
| `Assists` | `assists` | `assists` |
| `3-PT Made` | `threes_made` | `three_pointers_made` |
| `Blocked Shots` | `blocks` | `blocks` |
| `Pts+Rebs+Asts` | `points_rebounds_assists` | sum |
| `Pts+Rebs` | `points_rebounds` | sum |
| `Pts+Asts` | `points_assists` | sum |
| `Rebs+Asts` | `rebounds_assists` | sum |
| `Double-Double` | `double_double` | 1 if 10+ in two of points, rebounds, assists, steals, blocks, else 0 |

**Load-bearing for 20e to 20g:**
- `line_only_value` in `app/core/nba_line_only.py` is the one settlement rule
  for stored NBA lines (35's rule for NFL). It returns None for a DNP or a
  missing stat, never 0.
- **NBA has no modelled market yet.** Any later reader that projects, grades
  or freezes NBA lines must filter to modelled markets, as NFL's
  `MODELLED_MARKET_FILTER` does. 20g adds an `NbaPropMarket` enum and moves
  markets into it.
- `PropLineSource` is what a sport needs to store lines; `SportPropSource` is
  what it needs to freeze and grade. A sport joins `PROP_SOURCES` only once
  it implements the full protocol (NBA in 20g).
- `espn_team_code` is the only PrizePicks-to-ESPN team mapping. The Odds API
  (20d) uses full team names and does not use it.

## Testing

- Test gate on: Steps 2 to 5 each ship their tests (pure config, settlement,
  name and team mapping, resolver). Step 1 rides on the existing suite
  unchanged.
- Step 6 is integration: evidence is the dry-run count, the stored row counts
  and linkage log, a SQL spot check of linked lines, and the unchanged NFL
  count.
- Step 7: YAML parse and full `pytest`. Workflows are not run in Actions here.
- Run from `api/`: `.venv\Scripts\python.exe -m pytest`.

## Notes for the AI

- **Position is ignored for NBA.** PrizePicks sends `G`, `F`, `F-C`, `F-G`,
  `G-F`, `C-F`; ESPN stores `G`, `F`, `C`. `resolve_player` narrows on exact
  position and returns `contradicted` when nothing matches, so passing
  position would reject Julius Randle (`F-C`). Full name, then team, break
  ties. 29 NBA name keys are shared by two or more stored players (the Curry
  brothers, four J. Greens); full name resolves all of them.
- **Team is a tiebreak, never a veto.** `sport_players.team_id` is the team of
  the player's latest box score (preseason included), so it can trail a trade.
  This is 20b's rule for past games turned around: it is right for current
  lines only.
- **Fold accents before keying, on both sides.** ESPN names in
  `sport_players` are ASCII today (none of 652 has a non-ASCII character), but
  folding candidates too costs nothing and survives a source change. NBA
  aliases in `sport_player_aliases` must be keyed from the folded name.
- **Empty board** (offseason, or a day with no posted lines): the `NBA` league
  still exists, so the run stores 0 lines and exits 0. A missing league
  catalog is a failed request and exits 75 (existing `fetch_board` behavior).
- **Game dates:** `sport_games.game_date` is the Eastern date and PrizePicks
  `start_time` carries an offset; `find_game_id` already checks the UTC date
  and the day before.
- **Every SQL statement carries `sport = 'nba'`** (literal, as in
  `app/repositories/nba.py`).
- **Rookies with no box score** (no preseason game) do not link until their
  first game loads; the `nba-ingest.yml` relink step catches them the next
  morning.
- **PrizePicks rate limits:** honor 429 through the existing helpers. The NBA
  cron times sit off every NFL prop-lines time.
- Probe scripts stay in the session scratchpad, never under `api/`.
- **Probe 2026-10-06** (catalog, `NBA`, `NBAP`; one 429 retried):
  - `NBA`: 194 lines, all on 2026-10-20, 10 stat names, 106 demon, 54 goblin,
    34 standard
  - `NBAP`: 38 standard lines for 2026-10-06 preseason games
  - team codes seen: `NYK`, `SAS`, `GSW`, `NOP`, `UTA`, plus 9 that match ESPN

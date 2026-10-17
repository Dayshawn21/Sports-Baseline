# Fix: Store NBA preseason games and box scores

**Type:** Fix
**Status:** complete (2026-10-06)

## The problem

The 2026-27 NBA preseason started 2026-10-04 (5 games on 10-05, 12 on 10-16),
but none of it reaches the database. 20b skips ESPN season type 1 by design,
and hoopR does not publish preseason at all: its 2026-27 schedule file holds
only regular-season games, and its daily release job starts 2026-10-18. Early
roles (which rookie or new signing starts, who gets minutes) are visible only
in these games.

## The fix

Load preseason games and box scores from ESPN's site API, the fallback source
20a chose (same ESPN ids, so rows key exactly like 20b's), into the same
tables under a new `game_type` **`PRE`**, with `week` NULL.

- **Source** (keyless, unofficial):
  - `site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=YYYYMMDD`:
    games per date; keep events whose `season.type == 1`; `season.year` is the
    end year (2027), stored as the start year (2026) through `stored_season`
  - `.../summary?event=<id>`: box score for each completed game, stats under
    named `keys` (`minutes`, `points`, `fieldGoalsMade-fieldGoalsAttempted` as
    `"3-6"`, `threePointFieldGoalsMade-threePointFieldGoalsAttempted`,
    `freeThrowsMade-freeThrowsAttempted`, `rebounds`, `assists`, `turnovers`,
    `steals`, `blocks`, `offensiveRebounds`, `defensiveRebounds`, `fouls`,
    `plusMinus`), plus `starter`, `didNotPlay`, `reason`
- **Reuse:** `NbaGame`, `NbaPlayerGame` and every `app/repositories/nba.py`
  upsert unchanged; only a new parser and command.
- **Must not break:**
  - preseason never gets a week, so it is never frozen or graded (20a's period
    is regular season only)
  - **load-bearing for 20f and 20g:** every NBA reader that builds a baseline,
    projects or grades filters `game_type IN ('REG', 'PIN', 'PST')`, never
    `PRE`; recorded in the overview's NBA section
  - the daily hoopR run upserts only its own games, so it never deletes or
    rewrites `PRE` rows
  - `sport_players.team_id` may be set from a preseason game; that is the
    player's current team, which is what the column holds
- **Not in scope:** showing it anywhere (the NBA pages are 20e); preseason
  PrizePicks (`NBAP`) or The Odds API `basketball_nba_preseason`; past
  preseasons.

## Build steps

- [x] **Step 1 - Preseason parsers** - `PRESEASON = "PRE"` in
  `app/core/nba_season.py`; new `app/ingest/espn_nba_preseason.py` with pure
  `parse_scoreboard(json) -> list[NbaGame]` (preseason events only) and
  `parse_summary(json, game) -> list[NbaPlayerGame]`; tests in
  `tests/test_espn_nba_preseason.py` from small JSON fixtures. *Done when:*
  tests pass for: a preseason event kept as `PRE`, week None, season 2026,
  Eastern `game_date` (a 23:00Z tip stays on its date, a 00:30Z tip moves to
  the previous day), status and scores (NULL until final); a regular-season
  event on the same scoreboard ignored; `"3-6"` splits to 3 made, 6 attempted;
  `"+5"` / `"-3"` plus-minus; a DNP athlete with an empty `stats` list stored
  with NULL stats; an athlete with no id skipped.
- [x] **Step 2 - Command and backfill** - `run(start, end, dry_run)` and a CLI
  `python -m app.ingest.espn_nba_preseason [--start YYYY-MM-DD] [--end
  YYYY-MM-DD] [--dry-run]` (default start: Oct 1 of the season in progress;
  default end: today + 14 days), one scoreboard request per date and one
  summary per completed preseason game, a short pause between requests,
  `tenacity` retry on transient errors, all upserts in one transaction.
  *Done when:*
  - `--dry-run` prints preseason game and box-score counts and writes nothing
  - a real run stores every 2026-27 preseason game to date as `PRE` with
    `week` NULL, and box-score rows for each completed one
  - a second run leaves every NBA count unchanged
  - SQL check: `PRE` games have NULL `week`; the 2026 `REG` count is still
    1,200 and 2025's stored rows are unchanged; no `PRE` box-score row points
    at a non-NBA game or player; NFL counts unchanged
- [x] **Step 3 - Schedule and docs** - `.github/workflows/nba-preseason.yml`
  (cron `45 9 1-20 10 *`, October 1 to 20 only, plus `workflow_dispatch`;
  same setup as `nba-ingest.yml`); the command in `AGENTS.md`; the `PRE` type
  and the `REG`/`PIN`/`PST` reader filter in the overview's NBA section.
  *Done when:* the workflow parses as YAML with that cron and command; its
  exact command succeeds locally; `AGENTS.md` and the overview name `PRE`.

## Verify

- `cd api && .venv\Scripts\python.exe -m pytest` (new parser tests plus the
  full suite)
- `python -m app.ingest.espn_nba_preseason --dry-run`, then the real run and
  the Step 2 SQL checks
- Spot check: last night's Grizzlies at Hawks (`401898388`) is stored as
  `PRE`, final, with box scores matching ESPN's page (Grizzlies' Cedric Coward
  9 points, 3-6 FG, +5)

## Build notes

- **Added during the build (approved 2026-10-06):** `dnp_reason` is kept only
  when `did_not_play` is true, in both `hoopr_nba` and this parser, because
  ESPN puts `COACH'S DECISION` on players who played. 2025-26 was reloaded:
  0 played rows now carry a reason; all 6,103 DNP rows keep theirs.
- **Overseas clubs skipped:** preseason scheduled Portland vs the London Lions
  (`LON`, 2026-10-12). Games with a side outside `NBA_TEAM_CODES` (the 30 ESPN
  franchise codes, `app/core/nba_season.py`) are not stored.
- **First run:** 66 preseason games (8 final, 58 scheduled through
  2026-10-16), 305 box-score rows, 61 players new to `sport_players`; a second
  run changed nothing.
- **Team-of-record caveat:** `sport_players.team_id` is whichever load ran
  last. Re-running `hoopr_nba --season 2025` after the preseason load resets
  offseason movers to their 2025-26 team; re-run the preseason load (or wait
  for the first 2026-27 box scores) to restore current teams. Past-game teams
  always come from `nba_player_game_stats.team_id`, unaffected.

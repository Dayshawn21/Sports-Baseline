# Feature: Kicking and punting lines

**From build-plan:** feature 34b
**Status:** completed (2026-10-05)

## Goal

Store PrizePicks NFL lines for three more line-only markets, plus the
per-game stats that will settle them:

| PrizePicks stat | Stored market | Settles later from (`nfl_player_weekly_stats`) | Source |
|---|---|---|---|
| FG Made | `field_goals_made` | `fg_made` | NFLverse weekly stats file (already downloaded) |
| Kicking Points | `kicking_points` | `3 * fg_made + pat_made` | same file |
| Punts | `punts` | `punts` | NFLverse play-by-play (already read for red-zone counts) |

These are line-only markets, as in 34a. Nothing projects, grades or shows
them, and 34a's `MODELLED_MARKET_FILTER` keeps them out of every projection
reader.

**What is already in place** (checked 2026-10-05):
- Kickers (55) and punters (46) exist in `sport_players`, and kickers already
  have 2026 weekly stat rows.
- The weekly stats file has `fg_made` and `pat_made` on every row; 115 of 126
  kicker rows in 2026 have attempts.
- PrizePicks player linking does not filter by position.
- Weekly stats and play-by-play are loaded for 2024, 2025 and 2026, and the
  Tuesday `nfl-ingest.yml` refreshes both for the current season.

## In scope

- **Migration `0042`:** nullable `smallint` columns `fg_made`, `pat_made` and
  `punts` on `nfl_player_weekly_stats`.
- **Weekly stats ingest:** `parse_player_stats` reads `fg_made` and
  `pat_made`, and `upsert_weekly_stat` writes them.
- **Play-by-play ingest:** `parse_red_zone_usage` also counts punts per
  punter per game (`punt_attempt = 1`, keyed by `punter_player_id`).
  `write_red_zone_usage` zeroes and applies them on the same contract as the
  red-zone counts, as 19n did for end-zone targets.
- **Backfill:** 2024, 2025 and 2026, for both ingests.
- **Line-only markets:** three `NflLineOnlyMarket` values and their exact
  PrizePicks aliases.

## Out of scope

- **Projecting, grading, settling or showing** these markets. A later item
  does that under a pre-registered backtest.
- **Punts Inside 20, and every "(Combo)" kicking or punting line**, including
  FG Made (Combo), Kicking Points (Combo), Punts (Combo), PAT Made (Combo)
  and the FG distance combos. Punts Inside 20 is not in the 34b plan line.
  The "(Combo)" lines look like two players added together.
- **FG and PAT attempts, distances and blocks.** Only the made counts that
  settle the lines are stored. Attempts can be added later with a re-run.
- **Any change to the 27f fantasy computation or the modelled markets.**

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

The columns and their data land before the PrizePicks names, so lines are never
stored without a way to settle them.

- [x] **Step 1 - Migration `0042`: kicking and punting columns** -
  `0042_nfl_kicking_punting_stats.py`:
  - **Upgrade:** add nullable `smallint` `fg_made`, `pat_made` and `punts`
    to `nfl_player_weekly_stats`. Additive, so master's code is unaffected.
  - **Downgrade:** drop the three columns.
  - **Test:** `tests/test_migration_0042.py` (statement capture), pinning the
    three columns as nullable `smallint` with no default.

  *Done when:*
  - `alembic upgrade head` reaches `0042`
  - `downgrade 0041` then `upgrade head` round-trips
  - `\d nfl_player_weekly_stats` shows the three columns as nullable
  - pytest passes

- [x] **Step 2 - Kicking from the weekly stats file** -
  - **Parser:** `NflversePlayerWeek` gains optional `fg_made` and `pat_made`.
    `parse_player_stats` reads them with `_as_optional_int`, so blank is NULL
    and `0` is a real zero.
  - **Writer:** `upsert_weekly_stat` inserts and updates them.
  - **Tests:** extend the parser tests: a kicker row's values, a blank cell
    as `None`, and a non-kicker row's values.
  - **Backfill:** `python -m app.ingest.nflverse --season 2024`, then 2025
    and 2026.

  *Done when:*
  - every 2024 to 2026 `K` row has non-NULL `fg_made` and `pat_made`
  - each season's summed `fg_made` and `pat_made` equal the downloaded file's
    `K` totals
  - the other weekly columns are unchanged for 2024 and 2025, checked by
    comparing each season's row count and summed `passing_yards`,
    `receiving_yards` and `prizepicks_fantasy_points` before and after.
    2026 is excluded: NFLverse updates the current season's file, so a
    re-run can change it legitimately.
  - pytest passes

- [x] **Step 3 - Punts from play-by-play** -
  - **Header check first:** confirm the 2026 play-by-play header has
    `punt_attempt` and `punter_player_id`; stop if either is missing.
  - **Parser:** `NflverseRedZoneGame` gains `punts: int = 0`.
    `parse_red_zone_usage` counts regular-season rows with
    `punt_attempt = 1` and a `punter_player_id`, keyed by punter and game.
    Every play type is counted, so blocked punts count too.
  - **Writer:** `write_red_zone_usage` resets `punts = 0` with the other
    counts and applies it. The `run` summary line is unchanged apart from
    the counts it reports.
  - **Tests:** extend the play-by-play parser tests:
    - a punt row is counted for its punter
    - a non-punt row is not
    - a preseason row is not
  - **Backfill:** `python -m app.ingest.nflverse_pbp --season 2024`, then
    2025 and 2026.

  *Done when:*
  - `P` rows carry punts, and every row in a loaded game is non-NULL (0 for
    non-punters)
  - the league-wide punts per team-game for 2025 fall between 3 and 6
  - the red-zone and end-zone totals for 2025 are unchanged before and after
  - the run's "player-games skipped" count is reported and explained
  - pytest passes

- [x] **Step 4 - Store the three markets** - in `app/nfl/markets.py`:
  - **Markets:** `NflLineOnlyMarket` gains `FIELD_GOALS_MADE =
    "field_goals_made"`, `KICKING_POINTS = "kicking_points"` and
    `PUNTS = "punts"`.
  - **Aliases:** `fg made`, `kicking points` and `punts`, the exact
    2026-10-05 names, lowercased.
  - **Tests:** extend 34a's alias tests:
    - the three names map to their markets and read as `None` through
      `market_for_prizepicks_stat`
    - `FG Made (Combo)`, `Kicking Points (Combo)`, `Punts (Combo)`,
      `Punts Inside 20` and `PAT Made (Combo)` stay unmapped
    - the two market sets stay disjoint

  *Done when:*
  - `python -m app.ingest.prizepicks_nfl --dry-run` no longer skips the three
  - the combo variants and Punts Inside 20 are still skipped
  - pytest passes

- [x] **Step 5 - First real ingest, linking and parity** -
  - **Parity first:** capture 34a's parity set before the ingest:
    - `nfl_ranking_check --season 2026`
    - `nfl_prizepicks_lines`
    - `nfl_prop_predictions --dry-run`
    - `GET /nfl/slate` for the week `/nfl/current-week` reports. Week 4 was
      current on 2026-10-05; use whatever week is live when step 5 runs.
    - `GET /nfl/players/2347`
  - **Ingest:** run `python -m app.ingest.prizepicks_nfl` once (it writes;
    ask first).
  - **Rows:** list the stored rows for the three markets, with link counts
    and positions.

  *Done when:*
  - FG Made and Kicking Points lines link to `K` players, and Punts lines to
    `P` players
  - any unlinked line is listed with its resolver reason
  - the ranking check, 27a and the player page are identical
  - the slate and freeze differ only by fresh modelled-market snapshots,
    attributed line by line as in 34a
  - no line-only market appears in the slate

- [x] **Step 6 - Full verification** - run `npm run build`, `npm run test`
  and `pytest`.

  *Done when:* all three pass.

## Files / areas

- **New:**
  - `api/app/db/migrations/versions/0042_nfl_kicking_punting_stats.py`
  - `api/tests/test_migration_0042.py`
- **Changed:**
  - `api/app/ingest/nflverse.py`
  - `api/app/ingest/nflverse_pbp.py`
  - `api/app/repositories/nfl.py` (`upsert_weekly_stat`,
    `write_red_zone_usage`)
  - `api/app/nfl/markets.py`
  - the matching parser, repository and PrizePicks tests

## Data / contracts

**Load-bearing for the later item that grades or projects these markets:**

- **`nfl_player_weekly_stats.fg_made` and `pat_made`** come from the weekly
  stats file. NULL means not loaded, never zero.
- **`nfl_player_weekly_stats.punts`** comes from play-by-play, written by
  `nflverse_pbp` under the red-zone contract: zero for every row in a loaded
  game, NULL until play-by-play is loaded.
- **Settlement rules, fixed now:**
  - `field_goals_made` settles on `fg_made`
  - `kicking_points` on `3 * fg_made + pat_made`
  - `punts` on `punts`

  The kicking-points formula is PrizePicks' standard (3 per field goal, 1 per
  extra point). Confirm it before any grading item relies on it.
- **The three stored market strings** are never renamed.
- **Unchanged:** every modelled market, every response and report, the 27f
  fantasy points, and the existing red-zone and end-zone values.

## Testing

**Test gate is on.** These ship with tests:

- the migration's statements
- the kicking parser fields
- the punt counting in the play-by-play parser, including the zero-reset
  contract in the writer's captured SQL
- the three aliases and the unmapped combos

**Not unit-tested:** the backfills, the real ingest and the parity runs. They
are evidence in steps 2, 3 and 5.

**Parity can be slow** (open question 40): retry once rather than treat a slow
run as a failure.

## Notes for the AI

- **Deployment order matters.** GitHub Actions runs the Tuesday ingest
  against the same database. Apply `0042` there before pushing code that
  writes the new columns. Migrating first is safe, because the old code
  never names them.
- **Large downloads:** each play-by-play season is about 19 MB gzipped and
  about 100 MB of CSV, so backfill one season at a time.
- **Windows:** set the selector event loop before starting uvicorn (see
  memory). Run CLIs from `api/` with the venv python.
- **The local `ingest_daily` task** runs from the working folder. Once step 4
  lands, it stores the new markets too, which is safe behind 34a's filter.
- **No AI attribution in commits, no em dashes, light comments.**

## Outcome

- **Schema:** `0042` adds nullable `smallint` `fg_made`, `pat_made` and
  `punts` to `nfl_player_weekly_stats`. It was applied to the local database
  on 2026-10-05 and round-trips cleanly.
- **Kicking backfill (weekly stats file), kicker rows:**

  | Season | Kicker rows | NULL | `fg_made` | `pat_made` |
  |---|---|---|---|---|
  | 2024 | 543 | 0 | 936 | 1,189 |
  | 2025 | 543 | 0 | 931 | 1,210 |
  | 2026 | 126 | 0 | 220 | 279 |

  Every value equals the downloaded file's kicker totals. The 2024
  all-position `fg_made` is 937, because one non-kicker made a field goal.
  For 2024 and 2025, the row counts and summed passing yards, receiving yards
  and PrizePicks fantasy points are unchanged.
- **The 2026 re-run loaded week 4 early.** NFLverse had already published
  Sunday's games, so 2026 rows grew from 3,336 to 4,375, a day before the
  Tuesday cron.
- **Punting backfill (play-by-play):**

  | Season | Punts | Per team-game | Player-games skipped |
  |---|---|---|---|
  | 2024 | 2,046 | 3.76 | 0 |
  | 2025 | 1,933 | 3.55 | 0 |
  | 2026 | 482 | 3.83 | 0 |

  The 2026 file confirmed that `punt_attempt = 1` only on `play_type = punt`,
  and that every punt row names a punter. The 2024 and 2025 red-zone and
  end-zone totals are unchanged.
- **First real ingest:** 1,661 lines, all linked. The new markets stored
  10 + 2 (first half) `field_goals_made`, 12 `kicking_points` and 2 `punts`
  lines. Every kicking line linked to a K and every punt line to a P.
- **Parity around the ingest:**
  - Unchanged: the ranking check, 27a grading and the player page.
  - The week 4 slate and freeze changed only by fresh modelled-market
    snapshots for the scheduled MNF game: 604 added, 558 replaced, a net
    of +46, matching the freeze's 655 to 701.
  - No line-only market appeared in the slate.
- **Checks:** `npm run build`, `npm run test` (449), `pytest` (2202).
- **Backfill time:** the kicking backfill took about 10 minutes per season, so
  a long run needs a background limit above 10 minutes.

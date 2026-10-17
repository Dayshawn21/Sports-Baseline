# Feature 24a: Team ELO ratings

**From build-plan:** feature 24a
**Status:** completed (2026-09-19)

## Final outcome

`nfl_team_elo` (migration `0030`) holds 7,870 `nfl-elo-v1` rows covering every
regular-season game from 2012 through the 2026 schedule (3,935 games). The
first run correlated end-of-2025 ELO with 2025 point differential at Spearman
0.924, and a rerun reproduced the table hash exactly. The 2012-2023 schedules
were backfilled schedule-only (2022 has 271 games: BUF-CIN was cancelled), and
the 2026 week 2 slate was unchanged by the backfill. No API or UI reads the
ratings yet; 24b decides how far to trust them.

## Goal

Give every NFL team a pre-game strength rating for every regular-season game,
computed only from results final before that game. This is the first team-level
signal in the app and the input 24b backtests against closing spreads and
moneylines. 24a stores ratings; it makes no betting claim.

## In scope

- A schedule-only NFLverse backfill so ELO has history before 2024. Only
  2024-2026 are loaded today, which would leave 2024 as pure burn-in and no fit
  season for 24b.
- Franchise-code normalization at ingest (`OAK` -> `LV`, `SD` -> `LAC`,
  `STL` -> `LA`) so a relocated team keeps one rating and `nfl_teams` stays at
  32 rows.
- Pure ELO math in `app/core/nfl_elo.py`: expected win probability with home
  field, margin-of-victory multiplier, zero-sum update, between-season
  regression, and a replay that turns an ordered list of games into per-game
  pre and post ratings.
- `nfl_team_elo` table (migration `0030`) and repository functions to read
  games and replace ratings.
- `python -m app.ingest.nfl_team_elo` to recompute the full history, plus a
  Tuesday step in `nfl-ingest.yml` after the NFLverse load.

## Out of scope

- Converting ELO into a spread, total, or bet signal, and tuning K, home field,
  or regression (24b, on fit seasons only).
- Totals. ELO measures relative strength, not scoring level; 24b needs a
  separate scoring input for the total arm.
- Play-by-play efficiency, weather, rest, QB adjustments (24c).
- Any API route or UI (24d).
- Playoff games. Ingest stores regular season only; between-season regression
  absorbs the gap.
- Player stats, rosters, or play-by-play for backfilled seasons.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Franchise codes and schedule-only backfill.** Normalize
  relocated franchise codes in `parse_schedules` and `parse_player_stats`. Add
  `--schedule-only` and `--through-season` to `app.ingest.nflverse` so one
  command loads games for a season range without fetching the player-stats
  asset (which only exists from 2022). Tests cover code normalization and the
  schedule-only path skipping the stats fetch.
  *Done when:* `--schedule-only --season 2012 --through-season 2023 --dry-run`
  prints per-season game counts (256 through 2020, 272 from 2021, except 271
  in 2022 because the cancelled BUF-CIN game was never replayed); after the
  real run, `nfl_games` holds 2012-2026 regular season, `nfl_teams` has exactly
  32 codes with no `OAK`, `SD`, or `STL`, 2024-2026 counts are unchanged, and
  `/nfl/slate?season=2026&week=2` returns the same line count and edges as
  before the backfill.

- [x] **Step 2 - Pure ELO core.** `app/core/nfl_elo.py` with frozen constants,
  `expected_home_win_probability`, `margin_multiplier`, `update`,
  `regress_to_mean`, and `replay(games) -> list[NflTeamEloRow]`. No I/O.
  Starting constants are reasoned, not fitted (see Notes). Tests cover
  symmetry, zero-sum updates, the margin multiplier's autocorrelation damping,
  season regression, a tie, and leakage (a game's pre rating is unchanged when
  that game's or any later game's score changes; scheduled games get a pre
  rating and no post rating).
  *Done when:* `pytest tests/test_nfl_elo.py` passes and the full suite stays
  green.

- [x] **Step 3 - Table and repository.** Migration `0030` creates
  `nfl_team_elo`. Repository adds `get_elo_games` (regular-season games in
  replay order with scores, NULL scores kept) and `replace_team_elo` (delete and
  insert for one `model_version` in one transaction).
  *Done when:* `alembic upgrade head` reaches `0030`, `alembic downgrade -1`
  then `upgrade head` round-trips cleanly, and a repository test covers the
  replay ordering.

- [x] **Step 4 - Command, schedule, and first run.**
  `app/ingest/nfl_team_elo.py` reads games, replays, replaces rows, and prints
  row count, seasons covered, and the current top 5 and bottom 5 teams. Add it
  to `nfl-ingest.yml` after the NFLverse step.
  *Done when:* the command writes one row per team per regular-season game for
  2012-2026 (two per game), a rerun produces identical ratings, the command
  prints the Spearman correlation between end-of-2025 ELO and 2025 point
  differential and it is at least 0.8, and the workflow file parses.

## Files / areas

- `api/app/ingest/nflverse.py` - franchise map, schedule-only mode, season range
- `api/app/core/nfl_elo.py` (new) - pure rating math and replay
- `api/app/db/migrations/versions/0030_nfl_team_elo.py` (new)
- `api/app/repositories/nfl.py` - `get_elo_games`, `replace_team_elo`
- `api/app/ingest/nfl_team_elo.py` (new) - standalone entry point
- `.github/workflows/nfl-ingest.yml` - one step after NFLverse
- `api/tests/test_nflverse.py`, `api/tests/test_nfl_elo.py` (new), `api/tests/test_nfl_repository.py`

## Data / contracts

**`nfl_team_elo` - load-bearing.** 24b reads it for the backtest and 24d for the
slate.

| Column | Type | Notes |
|---|---|---|
| `id` | BigInteger PK | autoincrement |
| `team_id` | BigInteger FK `nfl_teams.id` | cascade delete |
| `game_id` | BigInteger FK `nfl_games.id` | cascade delete |
| `season`, `week` | SmallInteger | copied from the game |
| `is_home` | Boolean | |
| `elo_pre` | Float, not null | rating entering the game, from finals before it only |
| `elo_post` | Float, nullable | NULL until the game is final |
| `model_version` | Text, not null | `nfl-elo-v1` |
| `computed_at` | TIMESTAMPTZ | default `now()` |

Unique on (`team_id`, `game_id`, `model_version`). Index on (`season`, `week`).

"Per team per week" in the build plan means per team per game: bye weeks carry
no row, and the pre rating for a team's next game already reflects the bye.

**`NflTeamEloRow`** (core dataclass): `team_code`, `game_key`, `season`, `week`,
`is_home`, `elo_pre`, `elo_post | None`. The core works on codes and NFLverse
game ids; the command maps them to database ids.

**Franchise map:** `{"OAK": "LV", "SD": "LAC", "STL": "LA"}`, applied to home,
away, player team, and opponent codes.

## Testing

- The test gate is on. Logic tests: franchise normalization and schedule-only
  parsing (`test_nflverse.py`), all ELO math and the leakage contract
  (`test_nfl_elo.py`), and replay ordering (`test_nfl_repository.py`).
- Integration: the backfill and first ELO run are local-database checks with
  printed output as evidence. Steps 1 and 4 each record their counts.
- Final gate: `.venv\Scripts\python.exe -m pytest` from `api/`. No web change,
  so no web build is required.

## Notes for the AI

- `app/core/nfl_elo.py` stays pure: no DB, no clock, no file reads.
- **Starting constants (reasoned, not fitted):** initial 1500; K 20; home field
  48 ELO points; margin multiplier `ln(|margin| + 1) * 2.2 / (winner_elo_diff *
  0.001 + 2.2)` (the FiveThirtyEight NFL form, which damps favorites'
  blowouts); regress one third toward 1500 between seasons. 24b owns any change,
  tuned on fit seasons only.
- Replay order is `game_date`, then `start_utc`, then `nflverse_game_id`, so
  reruns are deterministic. Games in the same week never see each other's
  results because each game's pre rating is read before any update.
- Every team starts 2012 at 1500, so 2012 and 2013 are burn-in. Ratings are
  stored for them, but 24b must not fit or score on them.
- A game counts as final only when both scores are non-NULL. Scheduled games
  still get `elo_pre` so the current week has ratings.
- The schedules asset is one whole-history file that answers 200 for any
  season. Fetch it once per command run, not once per season.
- Backfilled seasons add rows to `nfl_games` only. Every prop baseline reads
  `nfl_player_weekly_stats`, so they are unaffected; the Step 1 slate check
  proves it.
- Never rewrite `upsert_team` names or merge existing team rows. The franchise
  map is applied before any team is upserted, and no `OAK`/`SD`/`STL` rows
  exist today.
- Weather and live odds are not inputs here.

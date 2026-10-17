# Feature: NFL weekly rosters

**From build-plan:** feature 19k
**Status:** complete (2026-09-18)

## Goal

Store each player's team for each week from NFLverse weekly rosters, and use it
wherever the app needs a player's team **for a given week** instead of the
last-write-wins `nfl_players.team_id`. Today, 11 of 329 players with 2026 week 2
lines have a stored team that is neither side of their game, so they get no
opponent adjustment and a wrong home/away flag. The week 2 roster puts 10 of them
in the right game.

**Where the stale team actually bites.** Past games already carry the team for
that game (`nfl_player_weekly_stats.team_id` and `opponent_team_id`), so player
baselines, DVP allowances, and history do not use `nfl_players.team_id`. It
matters only for the **upcoming** game and for name resolution:

| Reader | Uses `nfl_players.team_id` for |
|---|---|
| `get_slate_lines` | `player_team_id` (home/away and game-market side), opponent code and id, the DVP join |
| `get_historical_player_baselines` (`/nfl/projections`) | which players belong to each upcoming game |
| `get_player_candidates` (prop linking) | the team tiebreak between same-name players |

It is also literally last-write-wins by import order: re-running
`python -m app.ingest.nflverse --season 2024` after 2025 moves every player back
to their 2024 team.

## In scope

- Migration `0025`: `nfl_player_weekly_rosters` (player, season, week, team,
  roster status).
- A pure parser for NFLverse `roster_weekly_{season}.csv` (regular season only).
- An idempotent ingest command, a 2024 to 2026 backfill, and a Tuesday cron step.
- One shared "team as of a week" rule in SQL, used by the slate, `/projections`,
  and prop-linking candidates, falling back to `nfl_players.team_id` only for a
  player with no roster row at all.
- A `team_not_in_game` quality flag on slate lines whose as-of team is neither
  side of the game, so the remaining case is visible instead of silently missing
  an opponent.

## Out of scope

- Changing past-game aggregates. They already use per-game `team_id`.
- Creating `nfl_players` from roster rows (rookies and practice-squad players
  with no stats yet). Unknown roster players are skipped and counted. Adding
  players changes the resolution candidate pool, so it is its own decision.
- Injury status and depth charts (19l). Roster status is stored because the team
  rule needs `CUT` and `RET`, but it is not surfaced or modeled.
- Rewriting or removing `nfl_players.team_id`. It stays as the fallback and for
  anything not listed above. Item 17 can retire it.
- Postseason rosters.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Roster table and parser.** Migration `0025` creates
  `nfl_player_weekly_rosters` (shape in Data / contracts) with a downgrade. New
  `app/ingest/nflverse_rosters.py` with
  `parse_weekly_rosters(lines, season) -> list[NflverseRosterWeek]`
  (gsis id, season, week, team code, status). It keeps `game_type == "REG"` rows
  for the requested season only, skips rows without a gsis id or team, and
  collapses a duplicate (gsis id, week) to the last row.
  *Done when:* `alembic upgrade head` reaches `0025`, and `downgrade -1` then
  `upgrade head` are clean. Parser tests on a fixture with the real published
  header prove the kept fields, REG and season filtering, missing-id and
  missing-team skips, and the duplicate rule.

- [x] **Step 2 - Ingest, backfill, and cron.** Add `fetch`, `run(season,
  dry_run)`, and a CLI (`python -m app.ingest.nflverse_rosters [--season N]
  [--dry-run]`). A repository write replaces the season's rows for every week in
  the file (delete those season-weeks, insert the parsed rows) in one
  transaction, after the whole file parses. Players are matched by
  `nfl_players.nflverse_id` and teams by `nfl_teams.team_code`. Unknown players or
  teams are skipped and counted, never created. An unpublished season exits
  non-zero via `SeasonNotPublished(season, "weekly rosters")`. Backfill 2024,
  2025, and 2026. Add the step to `nfl-ingest.yml` after the stats load, and to
  `nfl-prop-odds.yml` before the price fetch (Thursday and Sunday). The current
  week's roster is often published after Tuesday (the 2026 week 2 roster appeared
  on Friday), so the Tuesday run alone would usually serve last week's roster.
  In `nfl-prop-odds.yml` the roster step uses `continue-on-error: true`, so a
  roster outage never blocks the price fetch.
  *Done when:* a repository test proves the delete-then-insert statements are
  scoped to the file's season and weeks and that unknown players are skipped,
  not inserted. The backfill prints stored and skipped counts per season, and a
  rerun leaves identical row counts and a checksum. Both workflows run the
  command.

- [x] **Step 3 - "Team as of a week" in the slate and `/projections`.** Add one
  shared SQL fragment in `app/repositories/nfl.py` that returns, per player, the
  latest roster row with `(season, week) <= (:season, :week)`. If that row's
  status is `CUT` or `RET`, the player has no team. If the player has no roster
  row at all, fall back to `nfl_players.team_id`. Use it for `player_team_id`,
  the opponent code and id, and the DVP join in `get_slate_lines`, and for the
  player-to-game membership in `get_historical_player_baselines`.
  *Done when:* repository tests prove the fragment is present in both queries
  with the week bound. Statement-shape tests cannot prove the rule's meaning, so
  a live-database spot check also runs the fragment and confirms one real player
  for each branch: roster team preferred over a stale `nfl_players.team_id`; a
  later week's row ignored (a player whose team changed between weeks 1 and 2,
  queried as of week 1); `CUT` or `RET` giving no team; and no roster row falling
  back to `nfl_players.team_id`. A before/after run of the 2026 week 2 slate
  shows the 10 corrected players gaining an opponent, and every other line's
  projection unchanged unless its player's team changed. Record both counts.

- [x] **Step 4 - Flag the remaining mismatches.** In `routers/nfl.py`, add
  `team_not_in_game` to a slate line's quality flags when its as-of team is
  neither side of the game. Add its display text to `web/src/utils/nflLabels.ts`
  and a color to `FLAG_COLORS` in `NflIntelligencePage.tsx`.
  *Done when:* a router-level test proves the flag appears for a player whose
  team is neither side (including no team) and not otherwise. The web label is
  covered if `nflLabels` has tests. The live 2026 week 2 slate shows the flag on
  exactly the lines Step 3 left without an opponent (expected: 1). Web tests
  and the build pass.

- [x] **Step 5 - Prop-linking candidates use the roster team.**
  `get_player_candidates` reports each player's latest roster team (same
  `CUT`/`RET` and fallback rules, with no week bound), so the team tiebreak in
  `nfl_resolution` compares against the current team. The resolution logic
  itself is unchanged.
  *Done when:* a repository test covers the latest-row and fallback behavior.
  Before changing the code, capture the current relink counts with a read-only
  query of stored line links. Then run `python -m app.ingest.prizepicks_nfl
  --relink`, which rewrites stored links in the local database (the same thing
  the Tuesday cron does). Record resolved, ambiguous, and unmatched counts before
  and after, and explain any change.

- [x] **Step 6 - Verify.** Full API tests, web tests, and web build. Confirm
  migration `0025 (head)`.
  *Done when:* all pass, and a `/nfl` screenshot shows one corrected player's
  line with an opponent adjustment.

## Files / areas

| Path | Change |
|---|---|
| `api/app/db/migrations/versions/0025_nfl_player_weekly_rosters.py` | New table, with downgrade |
| `api/app/ingest/nflverse_rosters.py` | New: parser, fetch, CLI |
| `api/app/repositories/nfl.py` | Roster write; as-of team fragment in slate, projections, and candidates |
| `api/app/routers/nfl.py` | `team_not_in_game` flag |
| `.github/workflows/nfl-ingest.yml`, `.github/workflows/nfl-prop-odds.yml` | Roster refresh on Tuesday, and before the Thursday and Sunday price fetches |
| `web/src/utils/nflLabels.ts`, `web/src/pages/NflIntelligencePage.tsx` | `team_not_in_game` label and color |
| `api/tests/test_nflverse_rosters.py`, `test_nfl_repository.py`, router/projection tests | Parser, write, as-of, and flag coverage |

## Data / contracts

**Source.** `https://github.com/nflverse/nflverse-data/releases/download/weekly_rosters/roster_weekly_{season}.csv`.
Public, no key. About 15 MB for a full season. The current season's file is
updated during the week: the 2026 file had week 2 on 2026-09-18, before week 2's
stats. Columns used: `season`, `week`, `game_type`, `team`, `status`, `gsis_id`.
Team codes match `nfl_teams` (`LA`, `LV`, `WAS`, ...). Statuses seen: `ACT`,
`DEV`, `RES`, `INA`, `CUT`, `RET`, `EXE`.

**Schema (load-bearing, 19l and item 17 read it), migration `0025`:**

`nfl_player_weekly_rosters`
- `id` bigint PK
- `player_id` -> `nfl_players.id` (cascade), `season` smallint, `week` smallint,
  **unique (`player_id`, `season`, `week`)**
- `team_id` -> `nfl_teams.id`, not null
- `status` text, not null (the NFLverse roster status, stored verbatim)
- `updated_at` timestamptz default `now()`
- index on (`season`, `week`)

**Team-as-of rule (load-bearing, one definition reused by every reader):**
1. The latest roster row for the player with `(season, week) <= (S, W)`.
2. If that row's status is `CUT` or `RET`, the player has no team as of W.
3. With no roster row at all, use `nfl_players.team_id`.

Prop-linking candidates use the same rule with no week bound (the latest row).

**API:** no response shape changes. New quality flag value: `team_not_in_game`.

## Testing

Test gate is on:

- Step 1: parser rules.
- Step 2: scoped replace, skip-not-create, unpublished season.
- Step 3: the week bound, roster over fallback, `CUT`/`RET`.
- Step 4: the flag.
- Step 5: candidate team rule.

No live downloads in tests. The backfill, the slate before/after, and the relink
are explicit verification runs against the local database. API from `api/`
with `.venv\Scripts\python.exe -m pytest`, web with `npm run test` and
`npm run build`.

## Notes for the AI

- Do not touch past-game aggregates or `nfl_player_weekly_stats.team_id`. They
  are already per game.
- One team-as-of definition in SQL, reused. Do not re-derive it per query.
- Never create players or teams from roster rows. Count what is skipped.
- A future week's roster may not be published yet. The rule then uses the latest
  earlier week, which is the intended behavior, not an error.
- Keep `nfl_players.team_id` writes as they are. Changing import-order behavior is
  out of scope once readers stop depending on it.

## Implementation notes

- Step 1: migration `0025` upgrade, downgrade, and re-upgrade clean. The parser
  takes `Iterable[str]` lines (streams like 19j's) and keeps the later row for a
  duplicate player-week. 4 parser tests; API tests 841 passed. Real 2026 file
  (published 2026-09-18): 5,488 raw rows parse to 5,486 (the 2 without a gsis id,
  both `DEV`, skipped), weeks 1 and 2, 32 teams, no duplicate player-weeks,
  statuses verbatim.
- Step 2: `replace_weekly_rosters` deletes the file's season-weeks, then inserts
  through joins to `nfl_players` and `nfl_teams`, so unknown rows drop out.
  Backfill: 2024 44,466 parsed / 35,974 stored / 8,492 skipped; 2025 44,669 /
  37,555 / 7,114; 2026 5,486 / 3,986 / 1,500. No unknown teams in any season;
  every skip is a rostered player with no stats. A 2026 rerun replaced 3,986
  with 3,986 and left all three checksums identical. Both workflows parse. API
  tests 844 passed.
- Step 3: `_player_teams_cte(week_bound=True)` in `repositories/nfl.py`, used by
  `get_slate_lines` (team, opponent, DVP join) and
  `get_historical_player_baselines`. Live spot check (every matching player
  asserted, not only the example):
  - roster over stale stored team: 389 players as of 2026 wk2 (e.g. Josh
    Johnson, stored WAS, roster CIN);
  - later week ignored: 5 players moved between wk1 and wk2 (Tyler Goodson ATL
    as of wk1, DAL as of wk2);
  - `CUT`/`RET` gives no team: 233 players (Adam Thielen, `RET`);
  - fallback: every stored player has a roster row by 2026, so it was checked
    as of 2024 wk1, where 472 players have no row yet (Andre Szmyt, stored CLE).

  Slate before/after (2026 wk2, 7,983 lines): 12 lines for 10 players gained an
  opponent; nothing else changed; lines without an opponent 13 -> 1.
  `/projections` player-games 2,614 -> 2,381: 378 players moved from their stale
  team's game to their roster team's game, and 233 `CUT` (200) or `RET` (33)
  players dropped out. API tests 847 passed.
- Step 4: `_team_flags` in `routers/nfl.py` keys off the opponent being NULL,
  which the slate query sets exactly when the as-of team is neither side. Web
  label in `nflLabels.ts`, color `red` in `FLAG_COLORS`. The label map is data,
  and `nflLabels.test.ts` covers only the formatters, so no web test was added.
  Live 2026 wk2: the flag is on exactly 1 line, the same line that has no
  opponent. API tests 848, web tests 76, build passed.
- **Follow-up (not 19k scope, pre-existing):** the flagged line is a
  **mislink**. PrizePicks "Camden Brown" (DAL, WR, anytime TD) resolved to
  Chase Brown (CIN, RB). Camden Brown has no stats, so he is not in
  `nfl_players`, and the initial-plus-surname key matched one candidate, which
  `nfl_resolution` accepts as `UNIQUE_NAME` before any position or team check.
  A single-candidate match that contradicts position or team should probably not
  resolve. That changes resolution logic, which this spec keeps unchanged, so it
  needs a `/fix`.
- Step 5: `get_player_candidates` reads `_player_teams_cte(week_bound=False)`.
  The test helper `_RecordingSession.execute` now accepts no params, because
  the candidates query passes none. Relink before and after (22,582 stored
  lines): `unique_name` 18,582, `full_name` 3,950, `no_candidate` 49,
  `contradicted` 1, identical both times. A read-only replay resolved all lines
  identically, and the real relink changed 0 rows. No line currently reaches
  the team tiebreak (0 `position_tiebreak`, 0 `team_tiebreak`), so the change
  has no effect on today's data. It keeps candidate teams consistent with the
  slate for future ties and gives the single-candidate `/fix` a trustworthy
  current team to check against. API tests 849 passed.
- Step 6: API tests 849 passed; web tests 76 passed; `npm run build` passed;
  migration `0025 (head)`. All 12 corrected lines now carry
  `opponent_adjusted`. The running API (`/nfl/slate?season=2026&week=2`)
  returns Odell Beckham Jr. receiving yards vs LA with a +3.76% opponent
  adjustment, projection 7.09, line 5.5, edge +1.59, and exactly 1
  `team_not_in_game` line. The `/nfl` page (NYG @ LA) shows the row as
  "LA +3.8%, 32.8 allowed, 153 games, 5.5, +1.6"
  (`.playwright-mcp/19k-obj-row.png`). Before 19k his stored team was MIA
  (cut in 2024), so the line had no opponent. The only browser console error
  is the unrelated missing `favicon.ico`.

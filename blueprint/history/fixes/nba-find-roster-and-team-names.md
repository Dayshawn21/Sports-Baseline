# NBA find misses rostered players and team names

**Type:** Fix

## The problem

Ask Lineform eval `nba-player-game-lines` ("What are Nikola Jokic's prop lines
in his next game?") fails: the model never reaches `get_game_detail`.

NBA `find` (`_find_candidates` in `api/app/services/ask/tools.py`) builds its
candidates from only two sources:

- each slate game's `matchup` string, so teams match by code only (`DEN`)
- players with a **modelled prop line** on that date
  (`nba_repo.get_date_modelled_lines`)

So on a night Denver plays (`DEN @ NO`, game 21259), "Jokic", "Murray",
"Nuggets" and "Denver" all return nothing: Jokic has no posted line yet, and
the full team name is never a candidate. The model tried four dates and gave
up. This is finding 3 in `blueprint/history/features/47e-ask-evals.md`.

## The fix

Widen the NBA candidate set for the requested date; matching itself
(`app/core/ask_find.py`) does not change.

1. **Team names.** For each slate game, add a `team` candidate for
   `away_team_name` and `home_team_name` ("Denver Nuggets") beside the code.
   Both point at the game URL. `_score` already matches any word prefix, so
   "Denver" and "Nuggets" both hit.
2. **Rostered players.** New repository reader
   `nba_repo.get_team_players(db, team_codes)`: each NBA `sport_players` row
   whose `team_id` (team of their latest loaded game) is one of the slate's
   teams, returning `player_id`, `name`, `team_code`. In `_find_candidates`,
   add each as a `player` candidate with the game URL and `game_id` of the
   game their team plays. Players who also have lines dedupe through the
   existing `(kind, name, entity_id)` key.

Must not break:

- SQL stays in `app/repositories/nba.py` (repositories own SQL).
- `find` still searches one date; no multi-day search is added.
- `get_game_detail` with a `player_id` that has no lines keeps its existing
  note, which lets the model honestly say lines are not posted (the eval's
  `must_match` accepts "not posted").
- NFL and tennis `find` unchanged.

## Build steps

- [x] **Step 1 - team names and rostered players in NBA `find`.** Add
  `get_team_players` to `app/repositories/nba.py`; use it and the slate's
  team names in `_find_candidates`. Tests in `api/tests/test_ask_tools.py`
  (stubbed slate and repo, as the existing `find` tests do): "Jokic" finds a
  rostered player with no lines, with the game URL and `game_id`; "Nuggets"
  and "Denver" find the team; a player with lines appears once.
  **Done when:** those tests pass and the Verify command passes.

## Verify

- Free, no API call, against the local database:
  `python -m app.services.ask.preview find sport=nba query=Jokic` (and
  `query=Nuggets`, `query=Denver`) on a date Denver plays returns the player
  or team with `/nba/game/<id>`.
- Optional paid check (separate yes needed, about $0.001):
  `python -m app.evals.ask --confirm-spend --only nba-player-game-lines`
  should pass.

## Result (2026-10-28)

- Verify passed: web typecheck, tests and build; API suite 4,810 passed.
- Free `preview` against the local database, date 2026-10-28: `Jokic` finds
  Nikola Jokic at `/nba/game/21259`; `Nuggets` and `Denver` find Denver
  Nuggets at the same game; `Murray` lists three players with their games.
- `get_game_detail` for game 21259 with Jokic's `player_id` returns his lines.
  Jokic had lines locally by then, so the eval-time miss may partly have been
  timing; the team-name gap and players without lines are fixed either way.
- The paid `nba-player-game-lines` eval case was not rerun.

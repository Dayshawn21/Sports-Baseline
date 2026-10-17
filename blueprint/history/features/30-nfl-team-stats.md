# Feature: NFL team stats in game notes

**From build-plan:** feature 30
**Status:** complete (2026-09-28)

## Goal

Add a "Team stats" block to each game's notes panel on the NFL slate, showing
both teams' season-to-date offense and the same stats allowed on defense, each
with a league rank. When reading a prop like "Barkley rushing yards vs CHI",
you can see how PHI moves the ball and how CHI defends it without leaving the
slate. Display only: it never changes an edge, rank, or projection.

## In scope

- Per team, season to date before the slate week (this season, REG, completed
  games only):

  | Offense (per game) | Defense (allowed per game) |
  |---|---|
  | Points | Points allowed |
  | Pass yards | Pass yards allowed |
  | Rush yards | Rush yards allowed |
  | Plays | Plays allowed |
  | EPA per play | EPA per play allowed |
  | Success rate | Success rate allowed |

- A league rank (1 = best) beside each value, computed across every team with
  games this season. Offense: higher is better. Defense: lower allowed is
  better. Ties share the lower rank.
- Games counted shown per team, with a muted "small sample" tag under 3 games.
- Extends the existing `GET /nfl/game-notes` response (item 29's load-bearing
  rule). `/nfl/slate` is untouched.

## Out of scope

- Last-season stats or any blending with them.
- Last-N-games or home/away splits.
- Position-level defense (DVP); the model already has it in the "why" text.
- Turnovers, sacks, red-zone or third-down rates (not all stored per team).
- Any use in projections, edges, ranking, or sorting.
- `project-plan.md` edits (tracked in open question 27).

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Pure stats math** - `api/app/core/nfl_team_stats.py`: from
  per-team-game rows (averaged over loaded games), compute per-game rates, EPA per play and success
  rate (offense and allowed), and league ranks. *Done when:*
  `tests/test_nfl_team_stats.py` passes, covering rates, rank direction
  (offense high = 1, defense low allowed = 1), shared ranks on ties, a team
  with zero games (all values and ranks null, excluded from ranking), and a
  team with scores but no efficiency rows (plays, EPA and success rate null,
  others present).
- [x] **Step 2 - Team-game query** - `get_week_team_games(db, season, week)`
  in `api/app/repositories/nfl.py`: one query returning a `TeamGame` per team
  per completed game this season before the week, with points, pass and rush
  yards, plays, EPA and successes for and against (NULL when not loaded). *Done when:* a one-off read against the local database for the
  current slate week returns all 32 teams with every completed game counted,
  and PHI's points for match its results in the Form block.
- [x] **Step 3 - Schema and service wiring** - `NflTeamStatSchema` and
  `NflTeamStatsSchema` in `api/app/schemas/nfl.py`; `build_game_notes` calls
  the query once, ranks all teams once, and `game_notes()` attaches
  `away_stats` and `home_stats`. *Done when:* `test_nfl_game_notes_service.py`
  covers the attached stats (including a team absent from totals, which gets
  zero games and null values), full `pytest` passes, and `GET
  /nfl/game-notes?season=2026&week=4` returns `awayStats` and `homeStats` on
  every game.
- [x] **Step 4 - Web types and formatters** - types in `web/src/types/nfl.ts`;
  in `web/src/utils/nflGameNotes.ts`, formatters for each value (one decimal
  per game, signed two-decimal EPA, success rate as a whole percent, `-` for
  null) and an ordinal rank label (`1st`, `2nd`, `3rd`, `11th`, `22nd`).
  *Done when:* `nflGameNotes.test.ts` covers each formatter including null
  and 11th-13th, and `npm run test` passes.
- [x] **Step 5 - Team stats block** - `TeamStats` in
  `web/src/components/NflGameNotesPanel.tsx`, after "Form and rest", plus
  styles in `web/src/pages/nfl-slate.css`. Rows are stats; columns are away
  offense, away defense, home offense, home defense, each cell showing value
  and rank. On mobile the block stacks one team under the other. Numbers use
  the mono font; ranks are muted, never green or red. *Done when:* `npm run
  build` passes and a screenshot of `/nfl` week 4 with notes expanded shows
  the block for PHI @ CHI, with games counted, and a phone-width screenshot
  shows no horizontal scroll.

## Files / areas

- `api/app/core/nfl_team_stats.py` (new)
- `api/app/repositories/nfl.py`
- `api/app/schemas/nfl.py`
- `api/app/services/nfl/game_notes.py`
- `api/tests/test_nfl_team_stats.py` (new), `api/tests/test_nfl_game_notes_service.py`
- `web/src/types/nfl.ts`
- `web/src/utils/nflGameNotes.ts`, `web/src/utils/nflGameNotes.test.ts`
- `web/src/components/NflGameNotesPanel.tsx`
- `web/src/pages/nfl-slate.css`

## Data / contracts

No schema change. **Load-bearing:** later team-level display context extends
`NflTeamStatsSchema`, not a new block.

```python
class NflTeamStatSchema(_CamelModel):
    value: float | None
    rank: int | None

class NflTeamStatsSchema(_CamelModel):
    team: str
    games: int
    efficiency_games: int
    points: NflTeamStatSchema
    pass_yards: NflTeamStatSchema
    rush_yards: NflTeamStatSchema
    plays: NflTeamStatSchema
    epa_per_play: NflTeamStatSchema
    success_rate: NflTeamStatSchema          # 0 to 1
    points_allowed: NflTeamStatSchema
    pass_yards_allowed: NflTeamStatSchema
    rush_yards_allowed: NflTeamStatSchema
    plays_allowed: NflTeamStatSchema
    epa_per_play_allowed: NflTeamStatSchema
    success_rate_allowed: NflTeamStatSchema

# NflGameNotesSchema gains:
    away_stats: NflTeamStatsSchema
    home_stats: NflTeamStatsSchema
```

**Sources and rules:**

- **Games:** `nfl_games`, `season = S AND week < W`, `game_type = 'REG'`,
  `status = 'completed'`. Each game yields two team-games (home and away).
- **Points:** the team's score; allowed is the other side's score.
- **Pass and rush yards:** `SUM(passing_yards)`, `SUM(rushing_yards)` from
  `nfl_player_weekly_stats` grouped by `team_id, game_id`. **Allowed** comes
  from the opponent side of the game in `nfl_games`, not
  `opponent_team_id`, which is nullable. Gross passing yards (sacks not
  netted). A NULL sum counts as missing, not zero.
- **Plays, EPA, success rate:** `nfl_team_game_efficiency`; the team's row is
  offense, the opponent's row in the same game is defense. EPA per play =
  summed EPA / plays; success rate = successes / plays; plays per game
  divides by `efficiency_games` (games with a row), not `games`. With no
  efficiency rows, these three are null.
- **Ranks:** computed over all teams with a non-null value, so the rank is a
  league rank even though only two teams are shown.

## Testing

- **Test gate on.** Logic tests:
  - `app/core/nfl_team_stats.py` - rates, ranks, ties, nulls (Step 1)
  - the service's stat attachment (Step 3)
  - web formatters and ordinal ranks (Step 4)
- Not unit tested: the SQL query (checked against the local database in
  Step 2) and the React block (build plus screenshots in Step 5).
- Final gate: `pytest`, `npm run test`, `npm run build`.

## Notes for the AI

- Keep `app/core/nfl_team_stats.py` pure: plain dicts or dataclasses in, no DB.
- The repo query runs once per request for all teams; don't query per game.
- Weeks 1-3 hold few games, so ranks swing a lot. The games-counted line and
  "small sample" tag are the guard; don't add fallbacks to last season.
- Match the panel's existing compact one-line JSX style and `Block` / `Empty`
  helpers. A slate week with no completed games yet shows "No completed games
  this season" per team.
- Keep the caveat line; it already says the panel is context only.

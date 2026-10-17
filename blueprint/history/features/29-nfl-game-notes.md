# Feature: NFL game notes

**From build-plan:** feature 29
**Status:** complete (2026-09-27)

## Goal

Give each NFL game one pre-bet panel. It shows who is hurt, whose role changed,
how the spread and total have moved, and how each team has played and rested.
Today that context exists only as tags on players who have a prop line (19l),
so a missing starter without a line is invisible.

## Design reference

- Placement: under the matchup bar and the game-model strip on `/nfl`, above
  the filter bar. The layout is from the screenshot in the request of
  2026-09-27; no file is saved.
- Style: muted, like `GameModelStrip`. Colors come from theme variables in
  `web/src/index.css`, and injury tags reuse the existing OUT, D and Q tags.
  Green and red are never used as a signal.

## In scope

- **Injuries:** a week's injury report for QB, RB, WR and TE on both teams,
  including players with no prop line.
- **Depth changes:** promoted, demoted and new depth-chart entries this week,
  for starters and the first backup only (see Notes).
- **Line movement:** for spread and total, the earliest and latest pre-kickoff
  row from one book.
- **Form and rest:** per team, the last 3 completed regular-season results
  before the week, rest days for this game, and a short-week tag.
- **Delivery:** a new read-only endpoint, `GET /nfl/game-notes`, with its own
  hook. The panel collapses and remembers its open state per viewer.

## Out of scope

- Linking an injury to prop lines, or any change to an edge, rank, projection,
  flag or pick. This is display only, by the 19l rule.
- OL, defense and K injuries.
- Any change to `build_slate` or `/nfl/slate`. 27a grading and 27i frozen
  predictions call `build_slate`, so it stays untouched.
- New ingest, schema or migration work. Every input is already stored.
- The prop board page (`/nfl/board`).

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Pure notes logic** - add `app/core/nfl_game_notes.py`:
  - `depth_change(NflAvailability)` returns promoted, demoted, new or None. It
    reuses `availability_flags`, drops the injury flags, and keeps only rows
    whose current or previous rank is 2 or better.
  - `injury_sort_key` orders Out, then Doubtful, then Questionable, then
    practice-only, then by position QB, RB, WR, TE, then by name.
  - `line_move(open, current)` returns the rounded difference, or None when
    either value is missing.
  - `short_week(rest_days)` is true when rest is under 6.
  - `result(points_for, points_against)` returns W, L or T.
  
  Tests go in `api/tests/test_nfl_game_notes.py`. *Done when:* pytest passes
  the new tests, and the existing `test_nfl_availability.py` still passes.
- [x] **Step 2 - Injury and depth reads** - in `app/repositories/nfl.py`, add:
  - `get_week_skill_injuries(db, season, week)`: rows from
    `nfl_player_injuries` for the week, joined to `nfl_players`, and only
    positions QB, RB, WR and TE. The team comes from the injury row's
    `team_id`. A row with a NULL report status and a NULL practice status is
    dropped.
  - `get_week_depth_rows(db, season, week)`: the week's depth rows, each
    joined to that player's previous depth row. This reuses the `week_depth`
    and `previous_depth` SQL from `_AVAILABILITY_CTE`, factored into a shared
    string only if that stays readable.
  
  SQL tests go in `test_nfl_repository.py`. *Done when:* the tests assert the
  week bound, the position filter, and the earlier-week bound on the previous
  depth row.
- [x] **Step 3 - Line movement and form reads** - add:
  - `get_week_line_movement(db, season, week)`: per game and market (spread,
    total), the earliest and latest row with `fetched_at` before `start_utc`,
    both from one book. The book is `draftkings` when it has a row, else the
    lowercase book with the most rows. Capitalized keys are ignored, as in item
    28's rule.
  - `get_week_team_recent_results(db, season, week)`: the last 3 completed regular-season
    games per team before the week, with opponent code, home or away and
    scores. `get_week_game_rest(db, season, week)` returns each game's two teams with `home_rest` and `away_rest`.
  
  SQL tests go in `test_nfl_repository.py`. *Done when:* the tests assert
  pre-kickoff only, one book per game and market, lowercase keys only,
  completed games before the week only, and a limit of 3 per team.
- [x] **Step 4 - Schemas, service, route** - add the schemas described under
  Data / contracts. Add `build_game_notes(db, season, week)` in a new
  `app/services/nfl/game_notes.py`: it groups the four reads by game and applies
  step 1's logic. Add `GET /nfl/game-notes?season=&week=` to
  `app/routers/nfl.py`. It is read-only, so it needs no API key. Test the
  grouping helper with plain dicts. *Done when:*
  - pytest passes
  - `curl "http://127.0.0.1:8000/nfl/game-notes?season=2026&week=3"` returns
    one entry per week-3 game
  - empty lists and nulls appear where nothing is stored
- [x] **Step 5 - Web types, API, hook, utils** - add the types to
  `src/types/nfl.ts`, `fetchNflGameNotes` to `src/api/nfl.ts`, and
  `useNflGameNotes(season, week)` to `src/hooks/useNfl.ts`, with a 5-minute
  `staleTime` and the key `['nfl', 'game-notes', season, week]` (matching `useNflSlate`). Widen
  `Availability` in `src/utils/nflAvailability.ts` to a structural type, so a
  notes entry is accepted as well as a line. Add `src/utils/nflGameNotes.ts`:
  - `spreadMoveLabel`, for example "GB -4.5 → -5.5 · 1.0 toward GB", in book
    sign with the home team named
  - `totalMoveLabel`, for example "42.5 → 44.0 · up 1.5"
  - `formLabel`, for example "W 24-17 vs CHI" or "L 10-20 @ DAL"
  - `restLabel`, for example "10 days rest" or "Short week · 4 days"
  
  Add `nflGameNotes.test.ts`, extend `nflAvailability.test.ts`, and use fixed
  inputs. *Done when:* `npm run test` and `npm run build` pass.
- [x] **Step 6 - Panel** - add `src/components/NflGameNotesPanel.tsx` (beside `NflEvidencePanel`), a
  button-toggled collapsible section (matching the page's own buttons) with four blocks:
  - injuries, split into away and home
  - depth changes
  - line movement
  - form and rest
  
  Render it in `NflIntelligencePage.tsx` after `GameModelStrip`. Its own
  loading and error states are inline and compact, so the slate still renders
  if notes fail. Empty blocks say "None reported" or "No earlier line stored".
  The open state goes in `localStorage` inside try/catch. *Done when:*
  - on `/nfl`, 2026 week 3, ATL @ GB shows the four blocks
  - switching games updates the panel
  - collapse survives a reload
  - signal rankings and the model strip are unchanged
  - `npm run build` passes
  - there are no console errors

## Files / areas

**API, new:**
- `app/core/nfl_game_notes.py`
- `app/services/nfl/game_notes.py`
- `tests/test_nfl_game_notes.py`

**API, changed:**
- `app/repositories/nfl.py`
- `app/schemas/nfl.py`
- `app/routers/nfl.py`
- `tests/test_nfl_repository.py`

**Web, new:**
- `src/components/NflGameNotesPanel.tsx`
- `src/utils/nflGameNotes.ts`
- `src/utils/nflGameNotes.test.ts`

**Web, changed:**
- `src/types/nfl.ts`
- `src/api/nfl.ts`
- `src/hooks/useNfl.ts`
- `src/utils/nflAvailability.ts`
- `src/utils/nflAvailability.test.ts`
- `src/pages/NflIntelligencePage.tsx`
- `src/pages/nfl-slate.css`

## Data / contracts

`GET /nfl/game-notes?season=&week=` returns `NflGameNotesResponse`. Fields are
camelCase on the wire through `_CamelModel`. **Load-bearing:** later display-only
game context extends this response, not `/nfl/slate`.

```
NflGameNotesResponse { season, week, games: NflGameNotes[] }
NflGameNotes {
  game_id, away_team, home_team
  injuries: NflNoteInjury[]        # sorted by injury_sort_key
  depth_changes: NflNoteDepthChange[]
  line_movement: NflLineMove[]     # 0-2 entries: spread, total
  away_form, home_form: NflTeamForm
}
NflNoteInjury { player_name, team, position, injury_status|null, practice_status|null, injury|null }
NflNoteDepthChange { player_name, team, depth_position, depth_rank,
                     previous_depth_position|null, previous_depth_rank|null,
                     change: "promoted"|"demoted"|"new" }
NflLineMove { market: "spread"|"total", book,
              open_line, open_fetched_at, current_line, current_fetched_at,
              move|null }             # spread in book sign: home line, negative = home favored
NflTeamForm { team, rest_days|null, short_week,
              recent: [{ week, opponent, is_home, points_for, points_against, result }] }  # newest first, max 3
```

When a game has only one pre-kickoff row, `open` equals `current` and `move` is
null. A market with no rows is left out.

## Testing

The test gate is on, so these need tests:

- **Python:**
  - every function in `app/core/nfl_game_notes.py`
  - the four repository reads (SQL-text assertions with `_RecordingSession`)
  - the grouping in `build_game_notes`
- **Web:** `nflGameNotes.ts` formatters and the widened `nflAvailability.ts`.
- **Not unit-tested:** the panel component. It rides on the step 6 browser
  check and the build.
- **Final gate:** from `api/`, `.venv\Scripts\python.exe -m pytest`; from
  `web/`, `npm run test` and `npm run build`.

## Notes for the AI

- **Display only.** No import from this feature may reach `_slate_line`,
  ranking or projection code.
- **Keep `app/core/` pure.** SQL stays in repositories, and the router stays
  thin.
- **Practice-report filter (decided 2026-09-27).** A practice-only entry lists
  only when the player was limited or did not practice (`worth_listing`). Full
  participants are hidden, which cut 2026 week 3 from 88 rows to 49.
- **Depth noise cap (rank 2 or better).** Without it, a week-1 chart or a
  practice-squad shuffle floods the list with "new" WR5 entries. The cap keeps
  the moves that matter for props.
- **Line movement is not the CLV entry line.** Do not import `entry_line` or
  `window_open` from `app/core/nfl_game_line_clv.py`. Item 28's rule is
  pre-registered.
- **Spread sign.** `nfl_game_odds` spread rows store the home line in book sign
  (`first_side='home'`, `app/core/nfl_odds.py`). NFLverse `spread_line` uses the
  opposite sign; do not mix them.
- **Rest.** `nfl_games.home_rest` and `away_rest` come from the NFLverse
  schedule and may be NULL. Show nothing then, never 0.
- **Injury team.** Use the injury row's own `team_id`, which is the team that
  filed the report, not `nfl_players.team_id`.
- **Windows.** Launch the API with the selector event loop (see memory).

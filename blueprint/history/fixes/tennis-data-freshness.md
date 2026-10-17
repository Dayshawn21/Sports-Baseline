# Tennis data freshness

**Type:** Fix

## The problem

The tennis review (2026-09-25, item 3) found two gaps between the data that
exists and the data the picks use.

1. **The scheduled stats job refreshes the wrong players.**
   - `tennis-ingest.yml` runs `python -m app.ingest.player_stats --limit 300`
     (`.github/workflows/tennis-ingest.yml:226`).
   - Without `--today-only`, that selects the first 300 of the 2,956 players
     alphabetically (`api/app/ingest/player_stats.py:724`), whether or not they
     play.
   - The problem is mostly hidden today: 83 of the 92 players with an upcoming
     match have stats under 48 hours old. That comes from the local
     `api/ingest_daily.bat`, which runs
     `--today-only --match-days-back 0 --match-days-ahead 1 --skip-computed-today`.
   - Any day the local run is skipped, the slate's stats go stale and props are
     capped at LEAN by `stale_stats`.
2. **Best picks never loads stats for the two players in each match.**
   - `_pred_player_ids` always returns `[]` (`api/app/routers/tennis.py:337`), so
     `get_best_picks` only loads rolling stats for players who have props and
     their opponents (`routers/tennis.py:267-271`).
   - `build_best_picks` then gets no stats for a match without PrizePicks
     props, so it silently produces no serve-edge, total-games or game-spread
     picks.
   - The match's player ids are already loaded on line 262
     (`match_player_ids_map`); they are just never used for the stats lookup.

**Dropped from the review:** "PrizePicks fetch has no pagination" is not a real
problem. Stored runs hold 318 to 1,505 tennis lines from a single request with
`per_page=250`, so PrizePicks ignores the page size and returns the full slate.

## The fix

- Run the scheduled stats job with the same flags as the local `.bat`:
  `--today-only --match-days-back 0 --match-days-ahead 1 --skip-computed-today`.
  - It then refreshes only players with a match today or tomorrow (UTC).
  - It skips anyone the local run already refreshed today.
- In `get_best_picks`, load rolling stats for every match's two players from
  `match_player_ids_map`, and delete `_pred_player_ids`.

**Must not break:**
- The admin single-player stats refresh.
- The `--limit` flag for manual runs.
- The prop-player and opponent stats best picks already loads.

**Out of scope:**
- The same-run book tie in `get_all_market_odds_batch`, and the best-picks live
  overlay's old name matcher (follow-ups from the odds fix).
- A weekly full-roster refresh. Only players with an upcoming match feed a
  prediction or a pick, and v6 uses no TennisAbstract stats.

## Build steps

1. [x] **Refresh stats for the slate, not the alphabet.**
   - Change the workflow's stats command.
   - Done when the workflow runs the same flags as the local `.bat`. A
     read-only run of the job's player-selection query today returns every
     player with a scheduled or live match today or tomorrow. The only other
     players it selects are those whose match today has already finished.
2. [x] **Load match-player stats in best picks.**
   - Build the stats id list from `match_player_ids_map`.
   - Remove `_pred_player_ids`.
   - Done when, on today's slate run in-process (skipping the endpoint's
     odds-quota overlay), the rolling-stats map covers both players of every
     predicted match that has stats. Before-and-after counts must show
     serve-edge, total-games or spread picks appearing for matches with no
     PrizePicks props, and all tests pass.

## Verify

- `cd api && .venv\Scripts\python.exe -m pytest`
- Inspect `.github/workflows/tennis-ingest.yml`: the player-stats step matches
  the `.bat` flags.
- After merge and push, optionally trigger the workflow's `player-stats` job by
  hand (Actions, Run workflow, job `player-stats`). Its log should list only
  players on today's and tomorrow's slate.
- On the Tennis page, matches without PrizePicks props can now show
  serve-edge, total-games or game-spread picks when their players have stats.

## Completion evidence

- `cd api && .venv\Scripts\python.exe -m pytest` passed, 1191 tests. The web app
  was not touched.
- Stats job selection, read-only against the live database on 2026-09-25:
  - The old `--limit 300` covered 11 of the 92 players with a scheduled or live
    match today or tomorrow.
  - The new flags select 121 players and cover all 92.
  - The other 29 players all had a match today that had already finished.
- Best picks replayed in-process on the 2026-09-25/26 slate, skipping the
  live-odds overlay because it spends Odds-API.io quota:
  - Both players' stats loaded for 43 of 46 matches, up from 20.
  - Game Spread picks rose from 14 to 38, and Serve Edge picks from 1 to 2.
  - Matches without PrizePicks props gained 25 stat-based picks (24 Game
    Spread, 1 Serve Edge), up from none.
  - No pick type decreased.
- The workflow change itself can only be observed after push, by dispatching
  the `player-stats` job.

## Notes

- Game Spread picks rest on the set and game-count math that review item 5
  (set and total-games math) will revisit.

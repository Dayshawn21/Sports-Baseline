# Schedule the NFL weather refresh

**Type:** Fix

**Branch:** `fix/nfl-weather-schedule`

## The problem

The NFL matchup bar shows "Forecast unavailable" for outdoor games that should
have a forecast (NE @ JAX, 2026-09-27). The code works. The trouble is that the
weather ingest (`app.ingest.nfl_weather`, Open-Meteo, shipped in the
`nfl-weather-context` fix) was only ever meant to be run by hand, and nothing
schedules it. Before this fix, `nfl_game_weather_snapshots` held only 10 rows,
all from one hand run on 2026-09-18, and week 3 had just 1 snapshot.
`web/src/pages/NflIntelligencePage.tsx` falls back to "Forecast unavailable"
whenever an outdoor game has no snapshot.

A hand run on 2026-09-26 stored 12 snapshots, so NE @ JAX now reads 82.7°F with
4 mph wind. Without a schedule, the forecasts go stale again.

## The fix

Add a weather refresh step to `.github/workflows/nfl-prop-lines.yml`. That
workflow already runs before kickoff (Thu 20:00, Sat 23:00, Sun 15:00, Mon 20:00
UTC), costs nothing to run, and uses the same `DATABASE_URL` secret.

- Put the step after the PrizePicks snapshot and before "Freeze pre-kickoff predictions".
- Mark it `continue-on-error: true`. Weather is display-only, so an Open-Meteo
  failure must never block the frozen predictions that 27j grades.
- Run it with `--days-ahead 7`. The ingest's 3-hour freshness guard already
  stops it from fetching the same game twice.

**Must not break:**
- the PrizePicks snapshot and its exit-75 handling
- the 27i prediction freeze
- the rule that weather never feeds a projection, edge, or rank

No schema, model, API, or UI change.

**Expected gaps (not bugs):**
- Indoor and retractable-roof venues stay without a forecast.
- Games more than about 7 days out get no forecast until a later run, because
  of the Open-Meteo forecast horizon.

## Build steps

- [x] **Step 1 - Add the weather step to `nfl-prop-lines.yml`.** Add the step
  plus a one-line note in the header comment that the ingest was manual-only
  before.
  **Done when:** the workflow runs `python -m app.ingest.nfl_weather --days-ahead 7`
  with `continue-on-error: true` between the snapshot and freeze steps, and
  `pytest tests/test_nfl_weather.py` passes.

## Verify

- **Local:** week 3 outdoor games in `nfl_game_weather_snapshots` have
  `fetched_at` on 2026-09-27 UTC, and on `/nfl`, NE @ JAX shows `°F · wind N mph`.
  Confirmed: the database rows after the hand run, and the local
  `/nfl/slate?season=2026&week=3` response for JAX (82.7°F, wind 4.1 mph,
  fetched 2026-09-27 03:52 UTC).
- **Remote:** this check needs a push, which needs your approval. Once the
  workflow is pushed, trigger `NFL PrizePicks Prop Lines` with `workflow_dispatch`.
  The "Refresh game weather forecasts" log should show
  `NFL weather ingest: outdoor=.. stored=..`, and the freeze step should still run.

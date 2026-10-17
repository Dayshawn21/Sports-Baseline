# Run the NFL weather refresh once a day

**Type:** Fix

**Follows:** `nfl-weather-schedule.md` (same day, 2026-09-26)

## The problem

The first fix ran the Open-Meteo weather ingest inside `nfl-prop-lines.yml`,
four times a week (Thu, Sat, Sun, Mon). The owner asked for a daily refresh
instead.

## The fix

- New `.github/workflows/nfl-weather.yml` runs
  `python -m app.ingest.nfl_weather --days-ahead 7` daily at 14:00 UTC,
  September through February, plus `workflow_dispatch`.
  - 14:00 UTC (9:00 AM Central) comes before every kickoff window, including
    Sunday's 17:00 UTC games.
- The weather step and its header note were removed from `nfl-prop-lines.yml`,
  which is back to its pre-weather contents. The PrizePicks snapshot and the
  27i prediction freeze are unchanged.
- No `continue-on-error` is needed, because nothing in the new job depends on
  the forecast. A failure shows as a failed run.

Weather stays display-only. There is no schema, model, API, or UI change.

## Verification

- Both workflow files parse, and their step order is correct.
- `nfl-prop-lines.yml` has an empty diff against its state before
  `nfl-weather-schedule`.
- Once pushed, one manual `workflow_dispatch` run of "NFL Game Weather" confirms
  the job.

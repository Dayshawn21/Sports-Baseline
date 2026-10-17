# Fix: Schedule the weekly NFL stats refresh

**Type:** Fix
**Status:** complete (2026-09-15), squash-merged from `fix/scheduled-nfl-ingest`

## Outcome

- `--season` defaults to `current_nfl_season(today)`; `--dry-run` with no season on 2026-09-15 loaded season 2026 (272 games, 1,117 rows), and `--season 2025` still overrides.
- `.github/workflows/nfl-ingest.yml` runs stats then relink every Tuesday 15:00 UTC, January, February, and September to December, plus `workflow_dispatch`, with `contents: read`. PyYAML parse confirmed; `tennis-ingest.yml` unchanged.
- **Not yet proven live.** No run has happened on GitHub: it needs `master` pushed. The first manual run is the proof that the `DATABASE_URL` secret reaches Neon and of how long a load takes over the network.

## The problem

Nothing refreshes NFL data on a schedule. `.github/workflows/tennis-ingest.yml`
is the only workflow, and it has no NFL job. Feature 19d made baselines
season-aware, but `stale_baseline_season` only clears once a player has
`MIN_BASELINE_GAMES` (4) in the current season, and the small-sample edge gate
only lifts at the same point. Both depend on
`python -m app.ingest.nflverse --season <current>` and `--relink` being re-run
after each week's games. Today that is manual, so the slate stays on 2025
baselines, with few priced rookie edges, all season unless someone remembers.

The CLI also requires `--season`, so a scheduled job would need a hardcoded
year that silently goes stale next September.

## The fix

1. **Infer the season.** Make `--season` optional in `app/ingest/nflverse.py`,
   defaulting to the NFL season in progress. The season runs September to early
   February, so January and February belong to the previous year's season:
   `year if month >= 3 else year - 1`. Pure helper, unit tested, taking the date
   as an argument rather than reading the clock.
2. **New workflow `.github/workflows/nfl-ingest.yml`.** Separate from the tennis
   file, same shape (checkout, Python 3.11, pip cache, `DATABASE_URL` secret):
   - `nflverse` (inferred season) then `prizepicks_nfl --relink`, in one job, so
     the relink always runs against freshly loaded stats.
   - Weekly on Tuesday after Monday Night Football, plus `workflow_dispatch`.
   - Cron limited to September through February, so the off-season does not
     fail red on `SeasonNotPublished` before NFLverse publishes a new season.
   - `permissions: contents: read`.

**Must not break:** `tennis-ingest.yml`, the `SeasonNotPublished` non-zero exit
(a missing season should still fail the job visibly), or explicit `--season`
backfills.

## Build steps

- [x] **Step 0 - Confirm which database the cron writes to.** The tennis jobs
  use the `DATABASE_URL` repo secret, but the slate reviewed in 19d reads the
  database in `api/app/.env`. If the secret points elsewhere, that database
  needs migrations through the NFL tables plus a 2024-2026 backfill before a
  weekly refresh means anything, and that is a larger change than this fix.
  *Done when:* the user confirms where the secret points, and the spec is
  either kept as is or re-scoped before any code.
  - *Confirmed 2026-09-15:* the user says the secret matches `api/app/.env`, and
    that URL is a hosted Neon database (`*.us-east-1.aws.neon.tech`), so GitHub
    runners can reach it. The secret value itself could not be read (no `gh`
    CLI here); the first manual workflow run is the real proof. Spec kept as is.
- [x] **Step 1 - Default `--season` to the current NFL season.** *Done when:* a
  table-driven test covers March, August, September, December, January, and
  February; `--season` still overrides; `--dry-run` with no `--season` on
  2026-09-15 loads season 2026.
- [x] **Step 2 - Add `nfl-ingest.yml`.** *Done when:* the YAML parses; one job
  runs stats then relink; the schedule covers only September to February;
  `workflow_dispatch` is supported; permissions are `contents: read`; and
  `tennis-ingest.yml` is untouched.

## Verify

- `cd api && pytest` passes, including the season-inference test.
- Locally: `python -m app.ingest.nflverse --dry-run` with no `--season` prints a
  2026 row count.
- After merge and a push (each separately approved): run the workflow from the
  GitHub Actions tab with "Run workflow" and confirm both steps succeed.

## Out of scope

- **Scheduling PrizePicks NFL line ingest.** Also unscheduled, but it spends
  rate-limited provider requests and needs its own cadence decision.
- **Speeding up the row-by-row upsert.** A full season took over 10 minutes
  locally; GitHub's 6-hour job limit is ample.
- **Confirming NFLverse's weekly publish time.** Tuesday is an assumption. If
  data lands later, add a second weekly run rather than guessing a later hour.

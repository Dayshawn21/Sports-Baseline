# Tennis GitHub Actions

Tennis uses six workflow files, with the same UTC schedules and ingest commands
as the previous combined workflow. This split is implemented locally; GitHub
registration and runner behavior require a separately approved merge/push and
remote verification. It does not reduce API usage or change provider limits.

| Actions entry | File | Schedule (UTC) | Manual operation |
|---|---|---|---|
| Tennis Match Ingest | `tennis-ingest.yml` | Daily 06:30 | Run directly; matches and H2H |
| Tennis Game Odds | `tennis-odds.yml` | Every four hours at :10 | Run directly; next 14 hours |
| Tennis PrizePicks Prop Lines | `tennis-prop-lines.yml` | Daily 13:00 | Run directly |
| Tennis Predictions and Shadow Freeze | `tennis-predictions.yml` | Daily 13:30 | `predictions` or `tennis-elo-comparison` |
| Tennis Box Scores and Candidate ELO | `tennis-box-scores.yml` | Daily 11:00 | `tennismylife` or `tennis-elo` |
| Tennis Player Stats | `tennis-player-stats.yml` | Daily 10:00 | Run directly |

Game Odds requests DraftKings and FanDuel from Odds-API.io. Since Bet365 went
paid-only (2026-10-26), both free books send tennis moneylines only, so the
job stores no total-games or game-spread lines. A run stops before any odds
batch when the hour's remaining requests are at the safety floor, and exits
nonzero when the provider's plan refuses every odds batch (402/403).

For manual runs after publication, open Actions, choose the named workflow,
and select **Run workflow**. The two workflows containing a dependent ELO job
retain a job selector. All other entries run their single task directly.
Selecting an ingest operation can spend provider quota or write the shared
database; runner acceptance has not been tested by dispatching live ingest.

`predictions` persists predictions and then PrizePicks projection snapshots.
After both succeed, its dependent job freezes the ELO shadow comparison.
Choosing `tennis-elo-comparison` runs only that dependent operation, even though
the prediction job is skipped. Prediction or snapshot failure blocks the
automatic dependent operation; cancellation blocks it too.

`tennismylife` ingests box scores, then its dependent job refreshes isolated
candidate ELO ratings and validates the complete snapshot and original files.
Choosing `tennis-elo` runs only the candidate operation. Box-score failure
blocks the automatic candidate operation; cancellation blocks it too.

The ELO jobs retain their exact UTC-day cache keys, implementation and identity
pins, original source-file paths, concurrency groups, and validation checks.
There is no fallback to another day's files, automatic experiment activation,
automatic scoring, or change to the served ELO source.

Every workflow receives `DATABASE_URL`. Only Match Ingest receives
`LIVETENNIS_API_KEY`, and only Game Odds receives `ODDS_API_KEY`. Workflow token
permissions are `contents: read`. Installation, Python runtime, and job steps
are preserved.

The local `api/ingest_daily.bat` and Windows scheduled task are unchanged.
TennisAbstract's local ELO refresh stays local because runner IPs receive
Cloudflare blocks. The pre-existing remote player-stats job stays scheduled.

When publishing this split, update all six files together so the old combined
schedule is removed at the same time the new workflow schedules are introduced.
The existing repository registration caveat applies: newly added workflows
need a push touching their files before they appear in Actions. Check the
registered workflow list and subsequent run logs before calling this deployed.

# Current Feature

## Tennis props refresh twice a day

**Type:** Fix

### The problem

`.github/workflows/tennis-prop-lines.yml` pulls PrizePicks tennis lines once a
day, at 13:00 UTC. PrizePicks removes a line when the match starts, and tennis
matches start around the clock. Lines posted after about 13:00 UTC (the evening
slate, and overnight Asia and Australia matches) don't reach the props page
until the next morning, and lines that move during the day stay stale.

Two smaller gaps come with it:

- A new line has no projection until `app.ingest.prop_snapshots` runs. That
  runs only in the 13:30 UTC `predictions` job of `tennis-predictions.yml`, so
  a second line pull alone would leave its new lines without projections.
- `app.ingest.prizepicks` turns a rate-limited league catalog into an empty
  list, logs "No tennis leagues found", and exits 0. A throttled run looks
  like a quiet day. The NBA, NHL and NFL ingests raise
  `PrizePicksRateLimited` (`app/ingest/prizepicks_props.py`) and exit 75,
  and their workflows turn that into a visible `::error::`.

The other sports are not changed. Their pulls are already timed before each
start window (NBA 2 a day, NHL 3 a day, NFL 4 a week), and each run freezes
its predictions in the same job.

### The fix

- Add a second schedule, `45 19 * * *` (19:45 UTC). It doesn't overlap any
  other sport's PrizePicks pull (NBA 16:30 and 22:15, NHL 14:37, 18:22 and
  21:27, NFL 15:00, 20:00 and 23:00 on game days) or the `:40` and `:25` odds
  slots.
- After the ingest in the same job, run `python -m app.ingest.prop_snapshots`,
  on the 19:45 schedule only. A stored snapshot is frozen, so a 13:00 snapshot
  would lock lines in before the 13:30 predictions exist; the 13:00 pull keeps
  leaving its lines to the 13:30 job.
- In `app/ingest/prizepicks.py`, when the league catalog or a league's
  projections are still 429 after the last retry, raise `PrizePicksRateLimited`
  and exit 75 instead of returning empty. Wrap the workflow's ingest step in
  the same `status=$?` / `::error::` pattern as `nba-prop-lines.yml`.

It must not break:

- `--dry-run`, which still writes nothing.
- Pruning of pulled lines, which still runs only when every league fetch
  succeeded (`prune_pulled=failed_leagues == 0`).
- A day with no tennis leagues and no 429, which still exits 0.
- The 13:30 `predictions` job, which still runs `prop_snapshots` after
  `predictions`.

### Build steps

- [x] **Step 1 - rate limits fail loudly.** In `app/ingest/prizepicks.py`,
  a 429 that survives every retry on the league catalog, or on every tennis
  league's projections, raises `PrizePicksRateLimited`, and `__main__` exits 75
  on it. One throttled league among several keeps the others' lines (pruning
  off), the same rule `prizepicks_props.fetch_board` uses for the other sports. Any other
  error keeps its current handling. Add `api/tests/test_prizepicks_tennis_rate_limit.py`
  with a mocked `httpx` client.
  *Done when:* the tests show a 429 that outlasts the retries gives exit 75,
  a 429 that later succeeds returns the data, and an empty catalog with no
  429 still returns normally. `pytest` passes.
- [x] **Step 2 - second run plus snapshot.** In `tennis-prop-lines.yml`, add
  the 19:45 cron, wrap the ingest in the exit-75 `::error::` pattern, and add
  a `Snapshot PrizePicks projections` step after it. Update the tennis
  PrizePicks lines in `docs/commands.md` and `docs/tennis-actions.md` with the
  new schedule.
  *Done when:* the workflow YAML parses, both crons and the snapshot step are
  present, and the docs match.

### Verify

- Verify command: `npm --prefix web run verify && cd api && python -m pytest`.
- Locally from `api/` with the venv: `python -m app.ingest.prizepicks --dry-run`
  still lists today's tennis props and writes nothing.
- After the merge and push, start the workflow with Run workflow in Actions
  and confirm both steps pass. Then check that the 19:45 UTC run fires and the
  props page shows lines posted after 13:00 UTC with projections. The first
  scheduled run only shows up after the push.

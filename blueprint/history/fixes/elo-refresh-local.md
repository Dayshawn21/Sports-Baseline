# Move the TennisAbstract ELO refresh off GitHub Actions

**Type:** Fix
**Branch:** `fix/elo-refresh-local`

### The problem

- The Monday `elo` job in `.github/workflows/tennis-ingest.yml` fails at
  `scrape_elo` with `403 Forbidden` for
  `https://tennisabstract.com/reports/atp_elo_ratings.html`.
- TennisAbstract is behind Cloudflare (`Server: cloudflare`, `CF-RAY`).
  Sent from the owner's machine on 2026-10-18, the same request (same URL,
  same `Mozilla/5.0` User-Agent) returned 200 for both ATP and WTA. The block
  is on GitHub's datacenter IPs, not on the request, so a code change on the
  runner side is unlikely to get past it.
- The local fallback is broken too:
  - `api/ingest_daily.bat` starts with `cd /d C:\Users\dayshawn\Desktop\SportAppV2\api`, a path from an older machine that does not exist here.
  - No Windows scheduled task runs it. `api/logs/ingest_daily.log` shows only
    two runs, both started by hand on 2026-10-17. The overview's "local
    scheduled task `ingest_daily`" (found in 26e) is no longer true.
- Impact is low: `ensemble-v3` gives ELO a small coefficient (ATP -0.08,
  WTA -0.42) and the market does most of the work. The cost is a red weekly
  run and ratings going slowly stale.

### The fix

1. Make `ingest_daily.bat` run from its own folder (`cd /d "%~dp0"`), so it
   works wherever the repo lives.
2. Add an ELO step (`python -m app.ingest.elo --web`) to `ingest_daily.bat`,
   before `player_stats`. It runs **daily**, not weekly: it costs two page
   requests, the upsert is keyed on `(player_id, as_of_date)` so a re-run
   with the same TennisAbstract date is idempotent, and a daily run still
   gets a refresh in on any day the PC is on.
3. Remove the `elo` job, its `0 9 * * 1` cron and its `elo` dispatch option
   from `tennis-ingest.yml`. Leave a one-line comment at the schedule saying
   ELO runs locally because Cloudflare blocks the runners.
4. Register a Windows scheduled task, `Lineform ingest_daily`, that runs the
   `.bat` once a day. **This changes the machine, not the repo, so it needs a
   separate yes in chat before it runs.**

**Must not break:**
- The other tennis-ingest jobs and their `github.event.schedule ==` checks.
- `player-stats` in Actions stays as it is. It uses the same site, and
  whether it is also getting 403s is unknown (no `gh` CLI here). Its
  per-player failures are logged, not fatal. If its run logs show 403s, a
  follow-up fix moves it the same way.
- No change to `app/ingest/elo.py`, so no new tests are needed. This is
  script and workflow config only.
- **Found during step 1:** `pd.read_html` needs `lxml`, which was never
  declared in `api/requirements.txt` (the local venv lacked it, so ELO
  could not parse the page on a clean install). Added `lxml==5.3.0`.

### Build steps

- [x] **1. Script and workflow.** Edit `api/ingest_daily.bat` (relative `cd`,
  ELO step with START/END log lines like the others) and
  `.github/workflows/tennis-ingest.yml` (drop the `elo` job, cron and dispatch
  option).
  *Done when:* `grep -n elo .github/workflows/tennis-ingest.yml` finds only
  the explanatory comment; the YAML still parses; running `api\ingest_daily.bat` by hand logs
  `STEP END elo` with `Upserted N ATP` and `Upserted N WTA` lines and no
  traceback.
- [x] **2. Scheduled task (separate approval).** `schtasks /create` a daily
  task running `api\ingest_daily.bat`, at a time the PC is usually on
  (owner picks; default 12:00 local).
  *Done when:* `schtasks /query /tn "Lineform ingest_daily" /v` shows the
  task with its next run time, and a `/run` of it appends a new
  `Starting daily ingest` block to the log.

### Verify

- Run the Verify command (`npm --prefix web run verify && cd api && python -m pytest`);
  nothing it covers should change.
- `api/logs/ingest_daily.log` shows the ELO step succeeding.
- In Neon, `SELECT max(as_of_date) FROM player_elo` matches the "Last update"
  date on the TennisAbstract ELO page.
- After a push to `master`, the Actions tab no longer lists an ELO Refresh job.

### Notes for /complete

- The overview's Deployment section (the `ingest_daily` local task, and
  "refreshed weekly" for ELO) is generated; record the change in the archive
  and let the next `/overview` pick it up.
- The interview guide: skip unless it claims ELO refreshes in CI.

### Outcome (completed 2026-10-18)

- **Local ELO run:** `python -m app.ingest.elo --web` upserted 550 ATP rows
  (TennisAbstract `as_of` 2026-10-05) and 519 WTA rows (2026-10-12), no 403.
- **Scheduled task:** `Lineform ingest_daily` registered on the owner's PC,
  daily at 12:00 local, `StartWhenAvailable` (runs late after the PC was
  off), 2 hour limit, `cmd.exe /c api\ingest_daily.bat`. It is machine
  state, not in the repo; recreate it with `Register-ScheduledTask` if the
  repo moves to another PC.
- **End-to-end run of the task** (2026-10-18 21:40 to 22:09, exit 0):
  livetennis 240 matches; PrizePicks ok; odds 72 matches, 221 rows; ELO 550
  ATP and 519 WTA; player_stats 241 ok, 11 skipped, 0 failed.
- **Verify:** `npm --prefix web run verify && cd api && python -m pytest`
  passed (2770 API tests).
- **Not resolved here:** whether the Actions `player-stats` job also gets
  403s. It exits 0 either way, since a non-200 is a per-player warning; its
  `Done. N ok, M skipped, K failed.` line decides whether a follow-up fix
  moves it local too.
- **Overview drift for the next `/overview`:** ELO is no longer "refreshed
  weekly" in `tennis-ingest.yml`; it runs daily from `ingest_daily.bat`,
  which is now a real scheduled task (the old one from 26e no longer
  existed).

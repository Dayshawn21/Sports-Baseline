# Feature: Deploy to Render

**From build-plan:** feature 37d
**Status:** complete (2026-10-16)

## Goal

Put the app online as the hosted read-only demo. The API runs as a Render web
service against the existing Neon database, and the web runs as a Render static
site. Anonymous visitors can browse every sport page; only the owner, holding
`ADMIN_API_KEY`, can reach `/admin`. A recorded smoke test shows that the
production settings, proxy headers, CORS and rate limits behave the same live as
they do locally.

## Decisions (2026-10-15, owner)

- **Two Render services on one `render.yaml` Blueprint:**
  - `sportapp-api`: a Python web service on the **free** plan. It sleeps after
    15 idle minutes, so cold starts and cache resets are accepted.
  - `sportapp-web`: a static site.
- **Scheduled ingest stays on GitHub Actions.** All 11 cron workflows, unchanged.
  "Scheduled-job wiring" in 37d means confirming they keep writing to the same
  Neon database the deployed API reads. No Render cron jobs.
- **Separate origins.** The web calls the API origin directly, using a
  build-time `VITE_API_BASE_URL`. CORS allows only the web's origin. 37a
  already assumed this: the credential is a header, not a cookie, so there are
  no cross-site cookie rules to handle.
- **Model artifacts ship from git.** The v6 LightGBM `.txt` files,
  `_features.txt` and `_meta.json` files are already tracked, and no
  calibration `.joblib` exists. The overview's "model files are gitignored"
  blocker is out of date. This spec proves the models load from a clean
  checkout and adds no artifact step.
- **No migrations on deploy.** `alembic.ini` is gitignored and the database is
  shared with the crons, so migrations stay a manual local step. No Render
  `preDeployCommand`.

## In scope

- A build-time API base URL for the web, defaulting to `/api` so local dev and
  the Vite proxy are unchanged.
- `render.yaml` at the repo root defining both services, with these settings:
  - **Python:** 3.11, pinned through `PYTHON_VERSION`.
  - **API start command:** `uvicorn ... --proxy-headers
    --forwarded-allow-ips '*'`.
  - **Health check:** `/health`.
  - **Secrets:** `sync: false`, so the owner enters values in the dashboard and
    no value is ever committed.
- A local rehearsal from a clean `git worktree`, running the exact Render build
  and start commands with `API_ENV=production`.
- Creating the services on Render and the first deploy. Both are owner actions,
  each needing a separate explicit yes (see Notes).
- A live smoke test, with its results recorded in this spec.
- Doc updates:
  - `AGENTS.md` deploy notes
  - the employer interview guide
  - a proposed `project-plan.md` §8 edit, which the owner approves before it is
    written

## Out of scope

- **Public repo, README and live-link publicity.** That's 37e. Render deploys
  from the current private repo for now. 37e repoints both services to the
  public repo.
- **Moving any cron to Render**, and changing the local `ingest_daily` task.
- **A custom domain.** The `*.onrender.com` URLs are enough for the demo.
- **Paid plans, autoscaling, a CDN or edge caching.**
- **Rotating credentials** (open question 47). Nothing in 37d makes history
  public, so rotation has to happen before 37e, not before 37d. It's still
  recommended, and if done first, the new values go straight into Render.
- **Fixing the `X-Forwarded-For` spoofing limit** described under Notes. It is
  recorded as accepted, not fixed.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Build-time API base URL** - add a pure
  `resolveApiBaseUrl(value: string | undefined): string` in
  `web/src/utils/apiBase.ts`. It works like this:
  - a blank or missing value returns `/api`
  - otherwise it returns the trimmed value without a trailing slash
  - a value that isn't `http(s)://` throws, so a bad build fails loudly

  `web/src/api/client.ts` uses it with `import.meta.env.VITE_API_BASE_URL`.
  Declare the variable in `web/src/vite-env.d.ts`, creating the file if it's
  missing. `adminKeyHeaders` still receives the relative request path, so the
  `/admin` header rule is unchanged.
  *Done when:*
  - Vitest covers blank, missing, trailing slash, `https://` and an invalid
    value.
  - `npm --prefix web run verify` passes.
  - `npm run dev` with no variable still loads the slate through the proxy.

- [x] **Step 2 - `render.yaml`** - a Blueprint with two services.

  **`sportapp-api`:**
  - `runtime: python`, `plan: free`, `rootDir: api`
  - build: `pip install -r requirements.txt`
  - start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers
    --forwarded-allow-ips '*'`
  - `healthCheckPath: /health`
  - env vars:
    - `PYTHON_VERSION` set to the exact 3.11 patch version
    - `API_ENV=production`
    - `RATE_LIMIT_DEFAULT` and `RATE_LIMIT_HEAVY` at their current defaults
    - `DATABASE_URL`, `ADMIN_API_KEY`, `CORS_ORIGINS`, `ODDS_API_KEY`, all
      with `sync: false`. `THE_ODDS_API_KEY` and `LIVETENNIS_*` are left off
      on purpose: only the ingest jobs read them, and those jobs stay on
      GitHub Actions (amended in Step 2).

  **`sportapp-web`:**
  - `runtime: static`, `rootDir: web`
  - build: `npm ci && npm run build`
  - `staticPublishPath: build`
  - `VITE_API_BASE_URL` with `sync: false`
  - response headers matching the API's: `X-Content-Type-Options`,
    `X-Frame-Options`, `Referrer-Policy`

  Comments in the file explain only the non-obvious lines:
  - why `--forwarded-allow-ips '*'` (Render's proxy addresses aren't published)
  - why there is no migration command
  - why the crons are absent

  *Done when:*
  - The file parses as YAML.
  - Every env var `Settings` requires in production is listed.
  - No secret value appears in it.
  - The gitleaks scan passes on the branch.

- [x] **Step 3 - Clean-checkout rehearsal (no code)** - in a fresh
  `git worktree` of the branch, run the Step 2 build and start commands
  exactly. Use a scratch venv on Python 3.11 and `API_ENV=production`, with
  real database and key values passed through the shell environment (no
  `.env` in the worktree). Set `CORS_ORIGINS` to a placeholder `https` origin.
  Then build the web with `VITE_API_BASE_URL=http://127.0.0.1:8000`.
  *Done when:*
  - The API starts and `GET /health` returns `{"status":"ok","env":"production"}`.
  - The startup log shows the registry serving v6 for ATP and WTA.
  - One public route returns 200, for example `GET /nba/model/ranking`.
  - Starting with a localhost `CORS_ORIGINS` is refused.
  - The web build succeeds and the built bundle contains the base URL, not
    `/api`.
  - Results are recorded under Testing.

- [x] **Step 4 - Create the services and deploy (owner action, separate yes)** -
  push the branch, after a separate explicit yes. The owner then creates the
  Blueprint in the Render dashboard from `render.yaml` and enters the
  `sync: false` values. Two values depend on each other's URL:
  - `CORS_ORIGINS` is `["https://<web>.onrender.com"]`
  - `VITE_API_BASE_URL` is `https://<api>.onrender.com`

  Both are known once the services are named, before the first deploy
  finishes. If not, set them and redeploy.
  *Done when:*
  - Both services read "Live" in the dashboard.
  - The API's first deploy log shows startup passed the production check.
  - The two live URLs are recorded in this spec.

- [x] **Step 5 - Stop returning tracebacks to clients** - three routes in
  `app/routers/props.py` (around lines 850 to 894) put
  `traceback.format_exc()` into the 500 `detail`. Live, that exposed the
  database host, file paths and code. Change them to log with
  `logger.exception` and return a plain message, matching the other routers.
  Then search `app/` for any other `format_exc` or exception text reaching a
  response.
  *Done when:*
  - No route builds a response `detail` from a traceback or a raw exception
    string; the search is recorded.
  - Verify passes.
  - A local request with the database unreachable returns the plain message.

- [x] **Step 6 - Cache the NFL slate, one build at a time** - wrap
  `build_slate` behind the `/nfl/slate` route in a `TimedSingleFlight` keyed by
  `(season, week)` with a 15-minute window, like the model sections. Add a
  process-wide `asyncio.Semaphore(1)`, so two different weeks never build at
  once. One build peaks at about 380 to 470 MB, so two would pass 512 MB. A
  cached failure returns 503, like the model routes. The 27a replay and the
  27i freeze call `build_slate` directly, so they are unaffected, and so is
  `build_slate` itself.
  *Done when:*
  - A test proves concurrent requests for one key share one build.
  - A test proves builds for two keys run one after the other.
  - Locally, a second `/nfl/slate` request for the same week returns in under
    1 s.
  - Verify passes.

- [x] **Step 7 - Stored report snapshots (migration `0045`)** - a
  `report_snapshots` table:
  - `report` (text) and `season` (int), which together are the primary key
  - `payload` (JSONB)
  - `computed_at` (timestamptz)

  Plus `app/repositories/report_snapshots.py` with `get_snapshot` and
  `upsert_snapshot`. The table is additive, so cron jobs still on master's code
  are unaffected. Running `alembic upgrade head` on Neon is a shared-database
  write, so it needs a separate yes.
  *Done when:*
  - The migration upgrades and downgrades cleanly against Neon (owner yes).
  - The repository round-trips one row.
  - Verify passes.

- [x] **Step 8 - Precompute NFL prop-line grading** - a new CLI,
  `python -m app.ingest.nfl_model_snapshot [--season N] [--dry-run]`:
  - It builds the 27a `LineRecord` with the existing `load_line_grading` and
    `build_line_record`, so page and report still share one code path.
  - It stores the record as `NflModelPropLinesResponse` JSON under report
    `nfl_line_grading`. (`nfl_prop_lines` is banned in `app/` by
    `test_no_nfl_view_names`, since it was an old table name.)

  The route picks its source with a pure `report_source(has_snapshot,
  production)` in `app/core/report_snapshot_source.py`, through
  `app/services/nfl/prop_lines_snapshot.py`:
  - a stored snapshot is served when one exists
  - otherwise **production returns 503 and never replays**
  - dev computes live as before

  Add the CLI to `nfl-ingest.yml` right after the 27a report step. It takes
  effect once 37d merges, so run it once locally now (a shared-database write,
  owner yes).
  *Done when:*
  - The pure source rule is tested.
  - `--dry-run` prints the record's headline (calls, hit rate) without
    writing.
  - After a real run, a local `/nfl/model/prop-lines` read from the snapshot
    matches the live-computed response field for field, apart from
    `gradedAt`.
  - Verify passes.

- [x] **Step 9 - Move the API to Virginia and redeploy (owner action)** - add
  `region: virginia` to `sportapp-api` in `render.yaml`, beside Neon's
  us-east-1. Render cannot move a service between regions, so the steps are:
  1. Push the branch (separate yes).
  2. The owner deletes `sportapp-api` and syncs the Blueprint, which recreates
     the service in Virginia.
  3. The owner re-enters its four secrets.
  4. The owner sets `VITE_API_BASE_URL` on the web to the new API URL and
     redeploys the web.

  *Done when:*
  - The API is Live in Virginia.
  - The new URLs are recorded.
  - `/nfl/slate` for the current week returns 200 in under 30 s cold, and in
    under 1 s warm.

- [x] **Step 9b - 90 s timeout for the NFL slate request (added 2026-10-16,
  owner)** - in `fetchNflSlate` (`web/src/api/nfl.ts`), the same per-request
  override `fetchNflModelPropLines` already uses. The cold build on the free
  instance takes about 34 s, and a second week queues behind the first.
  *Done when:*
  - Verify passes.
  - After a push and redeploy, a cold NFL slate load in the browser shows a
    single 200, with no timed-out request.

- [x] **Step 9c - Cache the slate as JSON bytes (added 2026-10-16, owner)** -
  the first browser sweep on the Virginia API returned NFL 502s. Locally,
  through the real routes, the cached slate object held the process at
  399 MB, and every visitor re-serialized its 10.7 MB, so three at once peaked
  at 464 MB. `slate_cache` now stores `slate_json(slate)`
  (`model_dump_json(by_alias=True)`), and `/nfl/slate` returns it as an
  `application/json` `Response`, keeping `response_model` for the docs.
  *Done when:*
  - A test proves the bytes decode to the same JSON the response model
    sent.
  - Locally, warm and concurrent requests add no memory.
  - Verify passes.
  - After a push, the live NFL page loads without a 502.

- [x] **Step 9d - Build the slate off the event loop (added 2026-10-16,
  owner)** - Render's Events log showed the 11:02 restart was "HTTP health
  check failed (timed out after 5 seconds)", not out of memory. A cold week
  stalled the event loop for 3.6 s locally (about 10 s on Render's CPU), so
  `/health` could not answer.
  - **Change:** `build_slate` keeps its queries async, and runs everything
    after them (the scoring replay, the per-line loop, the response) as a
    nested `assemble()` through `asyncio.to_thread`.
  - **No logic change:** the 27a replay and the 27i freeze call the same
    function and get the same output.

  *Done when:*
  - Weeks 5 and 6 at a fixed `now` are byte-identical before and after.
  - The longest local stall is under 1 s.
  - Verify passes.
  - After a push, a cold NFL load causes no health-check failure in Events.

- [x] **Step 9e - Always-on API plan (added 2026-10-16, owner)** - after
  30 idle minutes, the first visit took about 2 minutes: requests failed
  during the free plan's wake, then were retried.
  - **Decision:** the owner chose the $7 compute plan over a keep-warm ping.
    A GitHub Actions ping every 10 minutes would use about 4,300 billed
    minutes a month against the private repo's 2,000, and GitHub cron runs
    late.
  - **Change:** `render.yaml` sets `sportapp-api` to `plan: 0.5c-512mb`
    (0.5 CPU, 512 MB, no sleep). Render's Blueprint reference lists that ID;
    "starter" is not listed.
  - **Takes effect on sync:** pushing this makes the Blueprint sync move the
    service to the paid plan.

  *Done when:*
  - The API shows the `0.5c-512mb` plan in the dashboard.
  - A visit after more than 15 idle minutes has no wake delay.
  - A cold NFL slate build is timed, expected well under 34 s.

  **Status (2026-10-16):** the owner confirmed the dashboard shows
  `0.5c-512mb`. Since 9g, production never builds a slate, so the
  cold-build timing no longer applies. Only the idle visit remains, and
  Step 10 checks it.

- [x] **Step 9f - Cap glibc malloc arenas (added 2026-10-16, owner)** - with
  9d live, health stayed responsive through a cold build (0.2 to 1.8 s), but
  the process died 10.6 s into a cold week 3 build that came after tennis,
  the tennis PrizePicks model page and a cached week 6.
  - **Events:** "Ran out of memory (used over 512MB)" at 2:38 PM.
  - **A fresh process** built the same week in 11.6 s.
  - **Change:** `render.yaml` sets `MALLOC_ARENA_MAX=2` on `sportapp-api`,
    because per-thread arenas inflate Linux RSS once 9d's worker thread
    exists. The owner chose this free try first.
  - **If it is not enough:** the 2 GB plan (`1c-2g`) or precomputing the
    slate.

  *Done when:* after the push, the same sequence survives (tennis, the
  tennis model page, a cached week, then a cold week), and the owner reads
  the peak in Metrics.

  **Result (`1eeb063`, live 2:44 PM): not enough.**
  - **Tennis:** today 3.4 s, best picks 1.3 s, PrizePicks lines 6.6 s.
  - **NFL week 6 (cold):** 200 in 14.9 s; health was 8 of 8 ok during the
    build.
  - **NFL week 5 (the next cold build):** 502 at 13.3 s; health was 5 of 8
    ok during the build.
  - **Afterwards:** week 3 and health both 502, until the restart.
  - **Conclusion:** one cold build fits; the second in the same process does
    not. Memory freed after a build is not returned to the OS, so each
    build starts higher.

  **Closed 2026-10-16 (owner): superseded by 9g.** `MALLOC_ARENA_MAX=2`
  stays, since it does no harm. 9d is ticked on the same evidence: health
  answered through every cold build on `1eeb063`, and Events has shown no
  health-check failure since.

- [x] **Step 9g - Precompute the NFL slate (added 2026-10-16, owner)** -
  the owner chose this over the 2 GB plan. Production stops building
  slates. A CLI stores each week's slate in `report_snapshots`, the same
  way Step 8 stores 27a, and the API serves the stored copy.
  - **Key:** `report_snapshots` is keyed by `(report, season)`, so the week
    goes in the report name: `nfl_slate_week_<N>` (`slate_report(week)`,
    one helper). There is no migration.
  - **CLI:** `python -m app.ingest.nfl_slate_snapshot [--season N]
    [--weeks current | all | 5,6] [--dry-run]`.
    - `current` (the default) stores the week `get_current_week` returns,
      and the week before it.
    - `all` stores weeks 1 to 18.
    - Each week is built by `build_slate(db, season, week, now)`, unchanged,
      and stored as the camelCase JSON the route sends today (`slate_json`).
    - It prints each week's game and line count and its payload size.
  - **Route:** `/nfl/slate` chooses its source with Step 8's
    `report_source`:
    - a stored snapshot is served as bytes, read as `payload::text` so the
      API never parses the 10.7 MB
    - production with no snapshot returns 503 and never builds
    - dev builds live, as now

    The existing `SerialBuildCache` holds the snapshot bytes for 5 minutes,
    so repeat visits skip the database.
  - **Freshness:** these workflows write the slate's inputs, so each one
    refreshes `--weeks current` as its last step:
    - `nfl-prop-lines.yml`, after the freeze (lines)
    - `nfl-prop-odds.yml` (anytime-TD prices, injuries, depth)
    - `nfl-ingest.yml` (stats, rosters, US game odds), which also stores the
      previous week with its final scores
    - `nfl-weather.yml`, daily (weather, and the 13:00 scores run)

    `nfl-odds-io.yml` is left out: the slate reads only `the_odds_api_us`
    rows, and the best line lives in game notes. Displayed data is at most
    one cron run old.
  - **Unchanged:** `build_slate`, the 27a replay and the 27i freeze.

  *Done when:*
  - Tests cover the report name and the route's source choice (stored,
    production 503, dev live), with the snapshot read stubbed.
  - A test proves the stored text decodes to the same JSON that
    `slate_json` produces.
  - `--dry-run` for 2026 week 6 prints its counts and stores nothing.
  - Verify passes.

- [x] **Step 9h - Backfill, schedule and redeploy (owner yes for each)**
  1. **Backfill (a shared-database write):** run `--weeks all` for 2024,
     2025 and 2026. 2024 and 2025 have no stored lines, so their payloads
     are small. Record the total table size from
     `pg_total_relation_size('report_snapshots')`.
  2. **Push:** the four workflows run on the default branch, so the
     refresh steps start once 37d merges. Until then, one manual refresh
     after each cron run keeps the demo current.
  3. **Live check:** after the redeploy, run the 9f sequence that killed
     the process (tennis, the tennis model page, a cached week, then two
     weeks never opened before).

  *Done when:*
  - Every slate request returns 200 in under 3 s.
  - Health stays 200.
  - Events shows no out-of-memory failure.
  - The results are recorded under Testing.

- [x] **Step 10 - Live smoke test (no code)** - run against the live URLs with
  `curl` and a browser, and record every result under Testing.
  *Done when* all of these hold:
  - **Health:** `GET /health` returns `env: production` and carries HSTS plus
    the three security headers.
  - **CORS:**
    - A preflight from the web origin is allowed.
    - A preflight from `https://example.com` gets no
      `Access-Control-Allow-Origin`.
  - **Admin:**
    - `GET /admin/session` returns 401 without a key and 200 with it.
    - Signing in on `/admin` in the browser works.
    - The key is never sent to a public route (checked in the network tab).
  - **Rate limit:** 11 quick requests to a heavy route
    (`/nba/model/ranking`) give a 429 with `Retry-After`. A request from
    another network right after succeeds, which proves buckets are per client
    rather than shared through the proxy.
  - **Pages:** every sport slate, the tennis and NFL props boards, all three
    model pages, a match, game and player page, and `/how-it-works` load with
    no console errors. `/nfl/model` finishes within its 90 s timeout.
  - **Cold start:** the first page load after more than 15 idle minutes
    eventually renders, with TanStack retries allowed. The time is recorded.
    If it shows `ErrorState` instead, stop and decide with the owner before
    continuing.
  - **Memory:** the API's memory in Render metrics stays under 512 MB through
    the run.
  - **Crons:** the next scheduled GitHub Actions run (any workflow) succeeds,
    and the data it writes shows on the live site.

- [x] **Step 11 - Docs** - update these:
  - **`AGENTS.md`:** a short Deploy section covering:
    - the two services and that `render.yaml` defines them
    - migrations are manual
    - crons are GitHub Actions
    - the cold-start caveat
  - **`docs/SportApp-Employer-Interview-Guide.md`:**
    - the deployment architecture
    - the production guardrails proven live
    - the free-tier trade-off
  - **`project-plan.md` §8:** a proposed edit (live URLs, Render free plan,
    crons stay on GitHub Actions, the model artifact blocker resolved), shown
    for the owner's approval before it is written. Then `/overview` runs at
    `/complete`.

  *Done when:*
  - The `AGENTS.md` and guide diffs are reviewed.
  - The §8 edit is approved or declined.

## Files / areas

- `web/src/utils/apiBase.ts`, `web/src/utils/apiBase.test.ts` (new)
- `web/src/api/client.ts`, `web/src/vite-env.d.ts`
- `render.yaml` (new, repo root)
- `AGENTS.md`, `docs/SportApp-Employer-Interview-Guide.md`
- `blueprint/project-plan.md` §8 (on approval only)

Added by Steps 5 to 9 (2026-10-16): `app/routers/props.py`,
`app/routers/nfl.py`, `app/services/nfl/track_record.py`, a new migration
`0045`, `app/repositories/report_snapshots.py`,
`app/ingest/nfl_model_snapshot.py`, a pure source rule in `app/core/`,
`.github/workflows/nfl-ingest.yml`, and `render.yaml` (region).

Added by Step 9g: `app/ingest/nfl_slate_snapshot.py`,
`app/services/nfl/slate_cache.py`, `app/repositories/report_snapshots.py` (a
text read), `app/routers/nfl.py`, and `nfl-prop-lines.yml`,
`nfl-prop-odds.yml` and `nfl-weather.yml` beside `nfl-ingest.yml`.

Originally no API code change was expected. Startup, CORS, the security headers and the
production check already exist (fix `api-hardening`). If Step 3 or 5 finds an
API gap, it becomes its own reviewed step, not a silent edit.

## Data / contracts

- **No schema change.** Neon stays at its current revision.
- **`VITE_API_BASE_URL` (load-bearing):** the API origin, read at web build
  time. When unset, the web uses `/api` through the Vite proxy. 37e's README
  documents it.
- **`render.yaml` service names `sportapp-api` and `sportapp-web`
  (load-bearing):** their `onrender.com` URLs feed `CORS_ORIGINS` and
  `VITE_API_BASE_URL`. 37e's README links the web URL. 37e repoints both
  services to the public repo and keeps the names.
- **`/admin/session`** is the smoke test's sign-in check (37a contract,
  unchanged).
- **`report_snapshots` (load-bearing, `0045`):** one stored payload per
  `(report, season)`. Any report too heavy to compute on the demo is
  precomputed into it by a CLI and served from it. Its first report is
  `nfl_line_grading`, an `NflModelPropLinesResponse` as JSON.
- **Production never replays 27a.** `/nfl/model/prop-lines` serves the stored
  snapshot, or 503 when none exists. Dev keeps the live replay.
- **Production never builds a slate (9g).** `/nfl/slate` serves the stored
  `nfl_slate_week_<N>` row for its season, or returns 503. The NFL crons keep
  the current week fresh. Any new slate input needs its writer to refresh
  the snapshot too.

## Testing

- **Unit (gate on):** `resolveApiBaseUrl` in Vitest (Step 1). `render.yaml` and
  the rehearsal are configuration, proven by Steps 3 and 5 rather than a unit
  test.
- **Verify:** `npm --prefix web run verify && cd api && python -m pytest` passes
  before each checkpoint and at `/complete`.
- **Evidence log** (filled in during Steps 3 to 5):
  - **Rehearsal (2026-10-15, Step 3):** a detached worktree of `45b741b`, plus
    this branch's five uncommitted product files, with no `.env`. Run on a
    fresh Python 3.11.9 venv. The API started through a Windows launcher that
    passes `proxy_headers=True` and `forwarded_allow_ips='*'`, because psycopg
    needs the selector loop here. Render runs the plain command on Linux.
    - **Build:** `pip install -r requirements.txt` clean. Web `npm ci` and
      `npm run build` with `VITE_API_BASE_URL=http://127.0.0.1:8000` built;
      the bundle has `baseURL: resolve("http://127.0.0.1:8000")`, and `"/api"`
      appears only as the fallback constant.
    - **Models:** the registry from the clean checkout serves `{'ATP': 'v6',
      'WTA': 'v6'}`, both loaded. No extra artifacts needed.
    - **Production check:** a localhost `CORS_ORIGINS` was refused at startup
      ("CORS_ORIGINS includes a local origin").
    - **Health:** `GET /health` returned 200 `{"status":"ok","env":"production"}`
      with HSTS, `nosniff`, `DENY` and `Referrer-Policy`.
    - **Public routes:** `/nba/model/ranking` 200 in 2.6 s;
      `/tennis/predictions/today` 200 in 2.4 s.
    - **CORS:** a preflight from the web origin got 200 with the origin
      echoed; from `https://example.com` it got 400 with no allow-origin.
    - **Admin:** `GET /admin/session` with no key returned 401.
    - **Proxy headers:** with `X-Forwarded-For: 203.0.113.7`, requests 1 to 10
      to the heavy route got 200, the 11th got 429 (`Retry-After: 56`), and a
      different forwarded client right after got 200. Buckets are per client.
  - **First deploy (2026-10-16, Step 4), Oregon:** API
    `https://sportapp-api-7fq7.onrender.com`, web
    `https://sportapp-web-7v3r.onrender.com`.
    - **Config errors, both caught at startup:** first `CORS_ORIGINS` was not
      JSON, then the production check refused a short `ADMIN_API_KEY`.
    - **Healthy once fixed:** `/health` 200 in production with HSTS and the
      security headers; CORS allows the web origin.
  - **Problems the first deploy found (scope added 2026-10-16, owner):**
    - `/tennis/props/prizepicks` returned a full traceback, including the
      database host (Step 5).
    - `/nfl/slate` took 39 s live, against the web's 30 s timeout. The second
      request was followed by 502s, meaning the process died.
    - Local peaks: slate 381 to 466 MB; 27a prop-lines 647 MB (39 s), against
      512 MB on Render. Every other model loader peaks under 280 MB: NFL
      ranking 258, tennis line settlement 276, the rest about 236.
    - Render put the API in Oregon, and Neon is in us-east-1.
    - The owner chose to precompute 27a (Steps 7 and 8), cache the slate
      (Step 6) and move to Virginia (Step 9), staying on the free plan.
  - **Step 5 (2026-10-16):** props.py's three `format_exc` details and two
    raw `httpx` error details (whose message can carry the Odds-API.io URL
    and its `apiKey`) were replaced with logged errors and plain messages.
    - **Search:** `format_exc`, `import traceback`, and `detail=` built from
      `e`, `exc`, `err` or `error` all have no match left in `app/`, outside
      `ingest/` and `backtest/`. The one remaining variable `detail`
      (`_provider_status_error`) forwards Odds-API.io's own error body, not
      our URL.
    - **Proof:** each route called with a session raising
      `connection to server at secret-db-host...` returned 500 with only the
      plain message.
  - **Step 6 (2026-10-16):** `SerialBuildCache` in
    `app/services/nfl/slate_cache.py` (one lock across keys, 15-minute
    results, 10 s failures, at most 4 weeks kept) behind `/nfl/slate`; a
    failed build gives 503.
    - **Tests:** 5 new tests: shared build, no two weeks at once, expiry,
      failure retry, eviction.
    - **Locally (Windows, production settings):** two simultaneous cold
      requests for 2026 week 6 both returned 200 in about 18 s (one shared
      build); the warm request took 0.25 s.
    - **Response size:** 10.7 MB of JSON. Render's Cloudflare edge already
      compresses responses (`content-encoding: br` was seen on the live API),
      so no API-side gzip is added.
  - **Step 7 (2026-10-16, owner yes):** `0045` applied to Neon one command
    at a time, using a scratch `alembic.ini` (logging sections plus
    `script_location`):
    - `upgrade head` gave `0045`.
    - `downgrade -1` gave `0044`, with `to_regclass('report_snapshots')`
      null.
    - `upgrade head` gave `0045` again.
    - **Round-trip:** a nested payload under `37d_check` was inserted and read
      back equal (payload and `computed_at`). A second upsert replaced it, and
      a missing season gave None. The row was then deleted; the table holds 0
      rows.
  - **Step 8 (2026-10-16, owner yes for the write):**
    - **Dry run, then a real run:** `2897 calls, hit rate 51.1%, weeks 1, 2,
      3, 4, 5` (model `opponent-dvp-tg-blend-usage-snap-v4`). Stored
      `nfl_line_grading` for 2026 at 15:24:46 UTC; the payload is about 4 KB.
    - **Field for field:** the production path
      (`get_prop_lines_response(..., production=True)`, served from the row)
      equals a fresh live replay in every camelCase field except `gradedAt`
      (`breakEven`, `byEdge`, `byMarket`, `byWeek`, `calls`, `coverage`,
      `modelVersion`, `overProbability`, `reliability`, `season`).
    - **Tests:** 8 new; the route tests stub the snapshot read. API 2,580
      pass.
    - **Workflow:** `nfl-ingest.yml` stores it every Tuesday after the 27a
      report, once 37d merges.
  - **Step 9 (2026-10-16):** the owner pushed `d49b929`, deleted the Oregon
    API, synced the Blueprint and redeployed the web.
    - **Live URLs:** API `https://sportapp-api-ftsf.onrender.com` (Virginia),
      web `https://sportapp-web-7v3r.onrender.com`; the web bundle is
      `index-B7K7Brfz.js`.
    - **Checks:** `/health` 200 in production with HSTS and the 3 headers.
      CORS allows the web and gives 400 to `example.com`. `/admin/session`
      with no key gives 401.
    - **Prop-lines:** `/nfl/model/prop-lines?season=2026` returned 200 in
      1.4 s from the stored row (`gradedAt` 15:24:46).
    - **`/nfl/slate` 2026 week 6:** cold 33.8 s, warm 2.1 s (10.7 MB
      uncompressed; the browser received 249 kB, brotli at the edge). Health
      was 200 after both, so the process survived.
    - **Done-when misses:**
      - Cold missed the 30 s target by 3.8 s. The free instance's
        fractional CPU builds in about 34 s, against 12 to 18 s locally.
      - Warm missed 1 s; it is transfer time, served from cache.
      - On a cold load the web's 30 s axios timeout fires, and TanStack's
        retry joins the in-flight build.
    - **Browser:** every request on the tennis and NFL pages returned 200.
  - **Step 9b (2026-10-16):** `3b9cf63` pushed and both services
    redeployed. The new web bundle `index-D9n8DUwZ.js` passes the 90 s
    `timeout` on `/nfl/slate`. The browser's first check was warm (4.2 s) and
    on the cached old bundle, so the cold check moves to Step 10's idle test.
  - **Smoke, server side (2026-10-16, API `sportapp-api-ftsf`, Virginia):**
    - **Public routes, 21 of 21 returned 200:**
      - tennis predictions and best picks
      - match, odds history and recent form
      - player, serve-return, matches and props
      - the prizepicks, dk, bet and top props boards
      - NFL current week, game notes, game and line-only props
      - NBA slate, game, props and line-only props
    - **More routes:** NFL player 200 (0.35 s).
    - **Model routes, 8 of 8 returned 200:**
      - tennis predictions 1.2 s
      - tennis PrizePicks lines 12.5 s
      - tennis prop tiers 3.9 s
      - NFL ranking 5.5 s
      - NFL CLV 0.8 s
      - NFL prop-lines 0.23 s (the stored row)
      - NFL over-probability fit 0.15 s
      - NBA ranking 0.2 s

      Health was 200 afterwards.
    - **Rate limit:** from one IP, `/nba/model/ranking` gave 10 × 200, then
      429 on the 11th, and the 12th carried `Retry-After: 57`. A different
      forwarded client right after got 200, as did the default-limit route
      from the same IP. Buckets are per client behind Render's proxy. The
      forwarded-header spoof works, as the accepted limit in Notes records.
    - **Admin (owner, browser):** the Admin nav entry is hidden for visitors,
      as 37a intends. `/#/admin` showed the sign-in card, and signing in with
      the production key worked.
    - **Owner sweep, first pass:** tennis took about 12 s; NFL returned 502.
      The API log showed a clean shutdown and restart (a sleep or redeploy,
      not a logged crash), and health answered 502 three times, then 200
      after 6.9 s.
    - **Step 9c (local, through the real routes):**

      | Request | Before 9c | After 9c |
      |---|---|---|
      | Steady memory after a build | 399 MB | 358 MB |
      | Warm visit | peak 420 MB, 1.0 s | peak 358 MB, 0.3 s |
      | 3 concurrent warm visits | peak 464 MB | peak 358 MB, 0.2 s |
      | Cold build | peak 426 MB | peak 419 MB |

      The served JSON (14 games, 6,692 lines) equals a fresh build
      serialized through the response model. Tennis predictions add about
      48 MB beforehand.
    - **Owner re-test after `864f560` (cold):**
      - The bundle is `index-D9n8DUwZ.js`.
      - `slate?season=2026&week=6` returned a single 200 after 34.54 s, with
        no timed-out or retried request, and transferred 249 kB.
      - `game-notes` 200 in 0.9 s; `current-week` 200.
      - API health 200 right after. No 502.
      - This closes Steps 9b and 9c.
      - The only non-200 was `favicon.ico` 404: the web ships no favicon.
        Cosmetic, left for 37e.
    - **Memory, live stress test (2026-10-16):** Render's memory graph needs
      a paid plan, so memory was proved by survival instead.
      - **Load, all at once:** a cold build of week 5, five concurrent
        week-6 requests, and the tennis slate.
      - **Week 5:** 200 in 39.0 s. Week 6: 5 × 200 in 0.9 to 1.5 s, served
        from the cache while week 5 built.
      - **Tennis:** 200 in 0.3 s.
      - **Health after:** 3 × 200. Week 5 again: 200 in 0.55 s.
      - **Conclusion:** no restart and no 502. The owner checks the Events
        tab for any out-of-memory entry.
    - **Events log (owner):** "Instance failed: HTTP health check failed
      (timed out after 5 seconds)" at 11:02 on `d49b929`, then "Service
      recovered" at 11:03. No out-of-memory event. No failure since
      `864f560` went live at 11:10.
    - **Step 9d (local):**
      - **Output:** weeks 5 and 6 at a fixed `now` were byte-identical
        before and after (26,040,079 bytes, sha256 `cce6efbc89a0f811...`).
      - **Cold-build loop stalls:** the longest went from 3.56 s to 0.98 s;
        stalls over 1 s went from 2 to 0; total stalled time from 6.7 s to
        1.1 s.
      - **The old per-request encode** (before 9c) stalled 3.5 s, which
        matches the 11:02 failure.
    - **No key on public requests (owner, production, signed in):**
      `GET https://sportapp-api-ftsf.onrender.com/tennis/predictions/today`
      returned 200.
      - **Request headers:** no `X-API-Key`.
      - **Response headers:** `access-control-allow-origin` set to the web
        origin, HSTS, `nosniff`, `DENY` and `Referrer-Policy`, with a
        brotli body.
    - **Step 9g (local, 2026-10-16):**
      - `nfl_slate_snapshot --season 2026 --weeks 6 --dry-run` printed
        `14 games, 6692 lines, 10.7 MB` and stored nothing.
      - **Tests:** 15 new tests cover the report name, the source choice
        (stored copy, production 503, dev live), stored text decoding to
        the route's body, and `--weeks` parsing. API 2,596 pass, and web
        verify passes.
      - **Workflows:** the refresh step was added last to all four, with
        `if: !cancelled()`, so it runs even after a failed step. The YAML
        parses.
    - **Step 9h backfill (2026-10-16, owner yes):** `--weeks all` for
      2024 (26 s), 2025 (27 s) and 2026 (57 s), 54 rows in total.
      - **2024 and 2025:** games only, 0 lines, so the payloads are tiny.
      - **2026:** week 1 0.9 MB; weeks 2 to 5 13.3 to 16.5 MB, larger than
        week 6's 10.7 MB; weeks 7 to 18 have games only.
      - **Size:** `report_snapshots` grew to 5,200 kB (Postgres compression),
        and the database from 860 to 865 MB.
      - **Read check:** week 4 read in production mode returned 17.9 MB of
        jsonb text in 1.47 s, equal as JSON to a fresh build.
    - **Step 9h live check (2026-10-16, `0934bb7`):** stored slates were
      served about 120 s after the push (jsonb spacing in the body).
      - **The 9f sequence:**
        - tennis today 200 in 7.4 s
        - tennis PrizePicks lines 200 in 5.8 s
        - week 6, twice, 200 in 0.5 s
        - weeks 5, 4, 3, 2 and 1, never opened before, all 200 in 0.28 to
          0.75 s (brotli 22 to 400 kB)
        - health 200 after each week
      - **Concurrency:** 9 slates at once (2026 weeks 1 to 7, plus 2024 and
        2025 week 9), each from its own forwarded client, run twice. All
        18 returned 200 in 0.12 to 1.12 s. Health and tennis were 200
        afterwards.
      - **Rate limit:** the same burst from one client got 429 on 3 of 5
        requests, the heavy limit, as intended.
      - **Events (owner):** `0934bb7` went live at 3:12 PM, and there has
        been no failure since. The last out-of-memory entry was 2:48 PM, on
        `1eeb063` (9f's failure).
    - **Browser sweep, first pass (owner, 2026-10-16, bundle
      `index-D9n8DUwZ.js`):** 19 of 19 Fetch/XHR requests returned 200.
      - **NFL slate:** week 6 263 kB in 162 ms, and week 5 379 kB in
        667 ms. Game notes 283 to 342 ms.
      - **Tennis:** slate, player stats and recent form 93 to 149 ms. Model
        predictions 1.03 s, PrizePicks lines 126 ms, prop tiers 928 ms.
      - **NBA slate:** 790 ms.
      - **NFL model:** ranking 4.86 s, CLV 228 ms, prop-lines 102 ms (the
        stored row), fit 83 ms.
      - **Full sweep (owner):** every page in Step 10's list loaded, with
        no console errors.
      - **The DevTools badge of 2 is an Issues-panel warning, not a console
        error:** "A form field element should have an id or name attribute",
        on 2 resources. These are most likely the NFL page's Ant Design
        Season and Week `Select` inputs, which carry only an `aria-label`.
        It affects only browser autofill, so it is cosmetic and left for 37e
        beside the missing favicon.
    - **Cron (2026-10-16, 20:21 UTC):** the newest tennis moneyline row,
      match 88537 fetched at 19:32:34 UTC, is served live by
      `/tennis/matches/88537/odds-history`. NBA lines were stored at
      19:36 UTC. The run history could not be read here (no `gh`), so
      whether the 19:32 write came from a GitHub run or the local
      `ingest_daily` task is not proven. The NFL slate refresh steps run
      once 37d merges.
    - **Idle visit: not applicable (owner, 2026-10-16).** The API is on the
      always-on `0.5c-512mb` plan, which never sleeps, so there is no wake
      delay to measure.
    - **Closed:** the page sweep is recorded above. The idle cold load does
      not apply on the always-on plan, and Events has shown no failure
      since `0934bb7`.

## Notes for the AI

- **Stop for a separate explicit yes** before pushing, creating a Render
  service, changing remote env vars, or triggering a deploy (`/release` rule
  and `AGENTS.md`). Approving a step's diff does not approve any of these.
- **Never write a secret** into `render.yaml`, the spec, the guide, a commit or
  a log you paste. In Step 3, pass values through the shell environment, not a
  file in the worktree.
- **Accepted limit: rate-limit keys are spoofable.** With
  `--forwarded-allow-ips '*'`, uvicorn takes the leftmost `X-Forwarded-For`
  entry, which a client can set. A determined visitor could rotate it to dodge
  rate limits. That's acceptable for a read-only demo with one instance and
  in-memory limits. Record it in the guide as a known limit, and do not widen
  37d to fix it.
- **Free-plan behaviour is expected, not a bug:**
  - the service sleeps after 15 idle minutes
  - the 15-minute `TimedSingleFlight` caches reset on wake
  - the first `/nfl/model` load after a wake is a cold 27a replay
- **`web/` has no runtime server.** Everything is static. HashRouter means no
  SPA rewrite rule is needed. Do not add the Vite proxy to production.
- **The overview is generated.** Don't hand-edit it. The stale model-artifact
  blocker and deployment notes get fixed through `project-plan.md` §8 and
  `/overview`.

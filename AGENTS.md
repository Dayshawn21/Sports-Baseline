# AGENTS.md

Instructions for AI coding agents working in this project. This is the cross-tool
entry point: Codex, OpenCode, Cursor, GitHub Copilot, Gemini CLI, Aider, Zed,
Windsurf, and others read `AGENTS.md`. Claude Code reads `CLAUDE.md`, which imports
this file, so there is a single source of truth.

## What this is

**Lineform** (formerly SportApp V2) is a tennis betting intelligence app. It ingests ATP and WTA
matches, book odds, player stats, and props on a schedule, blends ELO, LightGBM,
and de-vigged market probabilities into a calibrated ensemble, and surfaces the
plays where the model disagrees with the market by enough to be worth a bet. It
also tracks placed bets so the edge is measurable rather than assumed.

Two parts: a FastAPI backend in `api/` (Python 3.11, async SQLAlchemy over
Postgres, LightGBM/XGBoost models) and a React SPA in `web/` (React 19, Vite,
TypeScript, Ant Design, Tailwind v4, TanStack Query).

This project is built with the **AI Blueprint**, a workflow layer, not an
app skeleton. To start a new project, scaffold the app first in an empty folder
(create-next-app, Vite, etc.), then overlay these files on top. Never run a
framework scaffolder inside a directory that already holds the blueprint files
(`AGENTS.md`, `CLAUDE.md`, `.agents/`, `.claude/`, `blueprint/`); it fails
because the directory isn't empty.

The workflow is defined by the local skills and context files below.

## Read these for full context

- `blueprint/context/project-overview.md` - the project's source of truth
- `blueprint/context/coding-standards.md` - conventions to follow
- `blueprint/context/ai-interaction.md` - how to work with the user on this project
- `blueprint/context/current-feature.md` - the one feature, fix, or rollback being built right now

## Workflow

Build one feature, fix, or rollback at a time, behind review gates. Each step's instructions
are plain markdown skills any capable agent can read and follow. The workflow is
exposed through tool-specific adapters:

- Codex: `.agents/skills/<skill>/SKILL.md`
- Claude Code: `.claude/skills/<skill>/SKILL.md`
- GitHub Copilot: `AGENTS.md` plus `.agents/skills/<skill>/SKILL.md`
- OpenCode: `AGENTS.md` plus the compatible `.agents/skills/` or
  `.claude/skills/` tree already installed for the selected tools

Unused adapters can be removed. Codex, GitHub Copilot, and OpenCode can share
`.agents/`. OpenCode can also reuse `.claude/` when Claude Code is selected.
Codex-only, Copilot-only, or OpenCode-only projects can delete `CLAUDE.md` and
`.claude/`. Claude Code-only projects can delete `.agents/`, but should keep
`AGENTS.md` because `CLAUDE.md` imports it. Do not duplicate the same Blueprint
skills under `.opencode/skills/`; OpenCode already discovers the compatible
trees.

When changing shared workflow behavior, update the matching skill in both
adapter folders so Codex, Claude Code, GitHub Copilot, and OpenCode stay aligned.

Core skills:

- `onboard` - tune commands, standards, visibility, ignore rules, and tool adapters after overlaying the Blueprint onto a freshly scaffolded or early project
- `discovery` - optional deep, multi-turn planning conversation that drafts the two user-owned plans only after review and approval; direct plan writing remains fully supported
- `doctor` - read-only Blueprint health check for setup, adapters, plans, overview freshness, and workflow drift
- `adopt` - bootstrap the Blueprint into an existing brownfield app with shipped features
- `overview` - distill the two planning docs into `blueprint/context/project-overview.md`
- `brief` - read-only briefing on an upcoming build-plan feature (scope, dependencies, size) before you spec it
- `feature` - turn a build-plan item into a spec, or propose a reviewed plan addition for a genuinely new feature
- `debug` - reproduce and isolate a failure without editing code, then hand the evidence to `fix` or `implement`
- `fix` - document an ad-hoc bug or change into `blueprint/context/current-feature.md`
- `tests` - add or normalize unit testing and turn on the test gate
- `ci` - explicitly set up one project-specific Verify command and matching automatic GitHub checks
- `implement` - build the current spec one small, reviewed step at a time
- `check` - prove the current spec against the running app
- `try` - read-only manual review guide: where to go, what to click, what to expect
- `audit` - branch-aware or full-project review across all concerns or a focused quality, security, performance, or tests lens; records findings with durable IDs and statuses in `blueprint/context/findings.md`, where open or fixed P0/P1 findings block `complete`
- `rollback` - plan a safe reversal of a completed feature from its archive and exact git commit, with later-dependency review before code changes
- `complete` - run the final safety pass, log features, fixes, or rollbacks under `blueprint/history/`, then merge with approval
- `release` - optional Render or Vercel deployment readiness, local config, env review, and smoke-test planning
- `prototype` - optional, pre-build static mockups to lock the look
- `status` - read-only progress summary, workflow drift warning, and suggested next action

In Codex, invoke these as skills (`$onboard`, `$discovery`, `$overview`, `$feature`,
`$implement`, and so on) or ask naturally, such as "run the overview." In Claude
Code, use the slash commands (`/onboard`, `/discovery`, `/overview`, `/feature`,
and so on). In OpenCode or other tools without a dedicated invocation syntax,
ask the agent to run the matching skill or follow its `SKILL.md` manually. The
conventions in `blueprint/context/` apply however a step is invoked. `/discovery`
is never required: users may write detailed plans directly or develop them
through any conversation before running `/overview`.

Optional explicit-only skill: `autopilot` can run one bounded spec/build/check
and targeted-audit pass when directly invoked. It may create checkpoint commits
on the feature or fix branch after passing steps, repair confirmed P0/P1 findings
within scope, and rerun affected checks. It stops before `/complete`, merge, push,
deploy, or destructive actions.

Deployment is also explicit. `/release` can prepare local Render or Vercel config
and run readiness checks, but it must stop before deploy, remote service changes,
push, or publish unless the user gives a separate yes in the current chat.

## Automatic verification

Automatic GitHub checks are a separate explicit setup. `/onboard` and `/adopt`
only report existing checks and point to `/ci` or `$ci` when none exist. Running
`/ci` inspects the real project and defines one `Verify` command from checks that
already exist. Use this order when available: typecheck, tests, then build. Never
invent a test runner or another check just to fill the command.

For JavaScript and TypeScript projects, prefer a package script such as `verify`
and use the detected package manager. For other stacks, use the native task
runner or exact combined command. Record the exact command under Commands below.

The optional `.github/workflows/verify.yml` must run that same command for pull
requests and pushes to the default branch. Preserve existing workflows, use the
project's real runtime and install command, and grant only `contents: read` by
default. This setup does not add local git hooks, coverage, browser tests,
security scans, or version matrices. Those remain later project choices.

GitHub branch protection or a ruleset can require the check after the repository
is pushed, but that is a separate remote setting. Missing automatic GitHub
checks do not make the Blueprint unusable.

**This project (37c):** `verify.yml` has two jobs, `verify` (the Verify command,
with a password-free dummy `DATABASE_URL`, since no test connects) and
`secret-scan` (a pinned, checksum-verified gitleaks scanning the tracked tree
and the commits the push or pull request adds). The secret scan was a deliberate
build-plan choice for the public demo, not a default. Rename neither job without
updating any ruleset that requires it. A failing check does not stop a push;
GitHub push protection does, and is on since the repo went public (37e).

## Employer interview guide maintenance

Keep `docs/SportApp-Employer-Interview-Guide.md` current when completing an
important project change. The guide is a local, untracked file (ignored since
37e, so it never reaches the public repo); edit it on disk and never stage it.
If it is missing on this machine, skip this section. Update the relevant
passages in the same work as the change, without waiting for a separate
request. This applies to:

- Major features or sports becoming available, changing scope, or being removed.
- Architecture, technology, data provider, or deployment changes.
- Authentication, security, testing, or operational capabilities that materially
  change how the app can be described to an employer.
- Model validation findings, adopted or rejected signals, and changes to which
  outputs are recommendations versus reference information.
- Engineering decisions or measured results that provide a useful interview example.

Skip cosmetic changes, routine dependency updates, and small fixes unless they
change a claim in the guide. Check actual implementation and verification
evidence before making claims. Keep planned, implemented, validated, and deployed
work distinct; do not describe a partially completed spec as shipped. Preserve
the guide's plain-language interview style and update existing explanations
instead of appending a changelog. Mention guide updates in the work summary.

These are agent maintenance instructions, not a background file watcher. They
apply across tools through this shared file, which `CLAUDE.md` imports.

## Commands

Two apps, two command sets. Paths are relative to the repo root.

### Web (`web/`, npm)

- Dev server: `npm run dev` (http://localhost:3001, proxies `/api` to the API)
- Build: `npm run build` (runs `tsc -b` first, so this typechecks too)
- Preview production build: `npm run preview`
- Test: `npm run test` (Vitest, single run)
- Test watch: `npm run test:watch`

### API (`api/`, pip + venv)

- Dev server: `uvicorn app.main:app --reload` (http://127.0.0.1:8000)
- Install: `pip install -r requirements.txt`
- Test: `pytest`
- Migrate: `alembic upgrade head`
- New migration: `alembic revision -m "description"`

### Ingest (`api/`, each runnable standalone)

- Matches: `python -m app.ingest.livetennis --days-back 1 --days-ahead 1`
- Odds: `python -m app.ingest.odds_api --hours-ahead 4` (Odds-API.io DraftKings
  and FanDuel; both send tennis moneylines only on the free plan, so no book
  total-games or game-spread lines are stored after Bet365 went paid on
  2026-10-26, and prop projections fall back to the model total. Stops before
  any odds batch once the hourly quota is at `--min-requests-remaining`)
- Props: `python -m app.ingest.prizepicks`
- NFL schedule + player stats: `python -m app.ingest.nflverse --season 2024`
- NFL props: `python -m app.ingest.prizepicks_nfl` (add `--relink` to re-resolve
  stored lines to players and games without spending a provider request)
- NFL game odds: `python -m app.ingest.nfl_odds --days-ahead 14` (add `--dry-run`
  to report matched and stored market counts without database writes)
- ELO: `python -m app.ingest.elo --web`
- Player stats: `python -m app.ingest.player_stats --today-only`
- TennisMyLife box scores: `python -m app.ingest.tennismylife [--days-back 21]
  [--since YYYY-MM-DD] [--dry-run]` (tracked players only; TennisAbstract
  remains authoritative, and TennisMyLife fills display gaps without changing
  grading or model inputs)
- Candidate tennis ELO: `python -m app.ingest.tennis_elo` (dry run by
  default; `--write` stores an isolated, immutable current-UTC-day roster;
  `--manifest <path>` reuses reviewed cached inputs). Runs after the 11:00 UTC
  TennisMyLife job, with a separate `tennis-elo` dispatch choice. It never
  replaces TennisAbstract or the served ELO source.
- Tennis ELO shadow freeze: `python -m app.ingest.tennis_elo_comparison`
  (dry run by default; `--write` requires reviewed activation and the first
  full UTC day; `--cycle <aware-ISO-time>` retries an immutable cycle).
  `--scheduled` skips inactive/partial-first-day experiments cleanly; it runs
  after the 13:30 UTC predictions and existing prop snapshots, or by the
  `tennis-elo-comparison` dispatch choice. `--check-snapshot` only validates
  today's complete roster and original cached files. The jobs share an exact
  UTC-day/pinned-implementation Actions cache. Missing or invalid originals
  freeze no pairs; active cycles retain eligible attempts for coverage. Never
  substitute newly downloaded files for the originals of a stored daily roster.
- Tennis ELO report: `python -m app.backtest.tennis_elo --count` (default,
  no winners or losses loaded). `--score --group ATP|WTA|ATP_CHALLENGER`
  requires a separate once-only scoring approval after the sample matures.
  Preserve `api/data/tennismylife-elo/reports/` with the experiment evidence:
  its locked sample/report artifacts prevent repeating the test. No workflow
  scores or activates the experiment automatically.
- PrizePicks projection snapshots: `python -m app.ingest.prop_snapshots` (after
  predictions; safe to re-run, a stored prop row is skipped)
- NBA schedule + box scores: `python -m app.ingest.hoopr_nba [--season 2025]
  [--days-back 3] [--dry-run]` (no `--season`: the season in progress, whole
  schedule plus box scores from the last 3 days; `--season` backfills it all)
- NBA preseason: `python -m app.ingest.espn_nba_preseason [--start YYYY-MM-DD]
  [--end YYYY-MM-DD] [--dry-run]` (ESPN site API; default Oct 1 to today + 14;
  stored as `game_type = 'PRE'`, never used by baselines or grading)
- NBA props: `python -m app.ingest.prizepicks_nba [--dry-run]` (full-game
  lines, every market line-only until 20g; add `--relink` to re-resolve stored
  lines to players and games without a provider request)
- NBA injuries: `python -m app.ingest.nba_injuries [--dry-run]` (ESPN keyless
  display snapshots; dry run fetches and reads player IDs without writing).
  Migration `0048` must be applied manually before real writes/API reads.
  `nba-injuries.yml` refreshes every two hours at minute 43 UTC, October-June,
  independently of PrizePicks. Six-hour freshness and historical pre-tip
  selection remain visible. See `docs/nba-injuries.md` for operational limits.
- NBA game odds: `python -m app.ingest.nba_odds [--days-ahead 2]
  [--min-credits 100] [--dry-run]` (3 The Odds API credits a run, dry run
  included; skips the paid call below the credit floor or with no game in the
  window)
- NHL schedule + box scores: `python -m app.ingest.nhl_api [--season 2025]
  [--days-back 3] [--dry-run]` (no `--season`: the season in progress, whole
  REG/PST schedule plus box scores from 3 days ago through today;
  `--season` backfills it all, 2023-24 onward). Migration `0049` is applied
  to the shared database. `nhl-ingest.yml` runs at 09:45 UTC, September-June.
  NHL API reachability from GitHub Actions remains unverified until its
  first post-push run.
- NHL props: `python -m app.ingest.prizepicks_nhl [--dry-run]` (full-game
  PrizePicks lines, every market line-only; add `--relink` to repair stored
  player/game links without a provider request). Time On Ice lines stay in
  provider minutes; NHL box scores store seconds. `nhl-prop-lines.yml` is
  configured for 17:15 and 22:45 UTC daily, September-June, with manual
  dispatch; rate-limit exhaustion exits 75. `nhl-ingest.yml` relinks after
  the daily schedule/box-score load. A local snapshot stored 941 lines with
  all player/game links resolved; both subsequent relinks changed zero rows.
  No NHL predictions are written. GitHub registration and runner acceptance
  remain unverified until an approved push and actual run.
- NHL game odds: `python -m app.ingest.nhl_odds_io [--days-ahead 2]
  [--min-requests-remaining 20] [--dry-run]` (DraftKings and FanDuel full-game
  moneyline with OT/SO, +/-1.5 puck line and total, per-book de-vigged, stored
  under `sport='nhl'`, `provider='odds_api_io'`). Dry run uses hourly requests
  but makes no inserts or commits; no eligible games means no provider calls.
  The default floor is 20 requests in the hour shared with tennis/NFL;
  no The Odds API credits are spent. `nhl-odds.yml` runs every three hours at
  minute 40 UTC, September-June, with manual dispatch and serialized runs.
  Two local write runs appended 84 snapshots each; read-back checked all 168,
  and a following dry run left counts and row hashes unchanged. Prior
  snapshots are never updated. GitHub registration, runner acceptance
  and deployment remain unverified pending an approved push and actual run.
  See `docs/nhl-odds.md` for contracts, failure handling and freshness limits.
- NHL injuries and starting goalies:
  `python -m app.ingest.nhl_context [--dry-run] [--date YYYY-MM-DD]`
  (ESPN keyless reports; default goalies cover Eastern today/tomorrow;
  injuries are always current, even with `--date`). Dry run reads existing
  candidates with read-only transactions and needs no context tables. Omitting
  `--dry-run` writes immutable batches with independent per-feed commits.
  Migration `0050` is prepared but unapplied by this work; nonempty NHL
  slate/game reads require it and return an explicit 503 if tables are absent.
  `nhl-context.yml` proposes hourly minute 17 UTC, September-June, plus manual
  dispatch, with serialized runs and only DATABASE_URL. Real snapshot writes,
  PostgreSQL read acceptance, GitHub registration/runner acceptance and
  deployment remain pending. Display is gray context only; no model or picks
  change. See `docs/nhl-context.md` for activation order and verification limits.

### Ask Lineform (`api/`, 47)

- Tool preview: `python -m app.services.ask.preview <tool> key=value ...`
  (e.g. `get_top_props sport=nba limit=3`). Runs one tool against the local
  database and prints exactly what the model receives, or the one-line error
  it would get. Arguments are `key=value` because Windows PowerShell strips the
  quotes from a JSON argument. Makes no Anthropic API call.
- Chat: `python -m app.services.ask.chat <question>` (quotes optional). Runs
  the full tool loop (`run_ask` in `app/services/ask/loop.py`) against the
  local database and the real API, printing tool status live, then the
  answer, stop, each tool call and token usage including cache reads. Needs
  `ANTHROPIC_API_KEY`; every run is a paid request. Never part of Verify or CI.
- `ANTHROPIC_API_KEY` is read only through `Settings` (`anthropic_api_key`) and
  passed to the client explicitly; it is never needed by tests or CI. The model,
  max tokens, tool-iteration cap and effort are `ask_model`, `ask_max_tokens`,
  `ask_max_tool_iterations` and `ask_effort` (default `low`).
- **Off unless `ASK_ENABLED=true`** (`ask_enabled`, default false). With it off,
  `GET /ask/status` reads `{"enabled": false}`, the web shows no Ask button and
  `POST /ask` is a 404. **Production refuses to start with it on**
  (`validate_production_settings`) until 47d adds the per-IP question limit and
  spend cap; 47d deletes that check in the same diff. Never set it in
  `render.yaml` or the Render dashboard before then.
- Stream: `POST /ask` with `{"question": "..."}` (1-500 characters) returns
  server-sent events: `tool_start` (`name`, `sport`), `tool_end` (`name`,
  `ok`), `text` (`delta`), `: ping` comments through slow tools, then one
  `done` (`stop`, `text`; the final text replaces the deltas) or one `error`
  (fixed copy; the exception is logged, never sent). 503 when enabled without a
  key; `/ask` is on the heavy rate limit (10 a minute per client). Every
  question is a paid request:
  `curl -N -X POST http://127.0.0.1:8000/ask -H "Content-Type: application/json" -d "{\"question\":\"who plays in the NBA tonight?\"}"`
- To try the drawer locally, set `ASK_ENABLED=true` in `api/app/.env` (or in
  the API process's environment) and restart the API.

### Verify (both apps, from the repo root)

- Verify: `npm --prefix web run verify && cd api && python -m pytest`

Web typecheck, web tests and web build, then the API tests. This is the one
automated gate: `.github/workflows/verify.yml` runs it on every pull request
and push to `master`. Locally, `python` must be the API venv (activate
`api/.venv` first, or run the halves separately with
`.venv\Scripts\python.exe -m pytest` from `api/`).

No lint command is configured.

### Deploy (Render, 37d)

`render.yaml` defines both hosted services, deployed from the repo:

- `sportapp-api`: a Python web service on the always-on `0.5c-512mb` plan in
  Virginia, beside Neon's us-east-1. It runs `uvicorn ... --proxy-headers
  --forwarded-allow-ips '*'` with `API_ENV=production`. Its secrets
  (`DATABASE_URL`, `ADMIN_API_KEY`, `CORS_ORIGINS`) are entered in the
  dashboard, never committed.
- `sportapp-web`: a static site built with `VITE_API_BASE_URL` set to the API
  origin. The value is read at build time, so changing it needs a web
  redeploy.

Things that are easy to get wrong:

- **Memory.** The API runs on the always-on `0.5c-512mb` plan, with 512 MB.
  Production never builds a heavy report on request; it serves copies
  stored in `report_snapshots` and returns 503 when one is missing:
  - `/nfl/slate`: `python -m app.ingest.nfl_slate_snapshot` (the previous,
    current and next week, bounded to weeks 1-18; `--weeks all` backfills).
    The four NFL workflows that write slate inputs run it as their last step,
    so any new slate input's writer must refresh it too.
  - `/nfl/model/prop-lines`: `python -m app.ingest.nfl_model_snapshot`, run
    by `nfl-ingest.yml`.

  Keep any new heavy report off the request path the same way. In dev a
  stored copy also wins over a live build.
- **Ingest** stays on GitHub Actions; Render runs no cron jobs.
- **Migrations are manual and run one command at a time** against the shared
  Neon database. `alembic.ini` is untracked, so pass one with `-c`: it needs
  `[alembic] script_location = <repo>/api/app/db/migrations` plus logging
  sections, because `env.py` calls `fileConfig`.

### Repository (37e)

Tennis Actions are split by operation into six workflows. See
`docs/tennis-actions.md` for schedules, manual choices, and dependent ELO jobs.
This operational guide supersedes the older combined-workflow description in
the generated project overview until its next regeneration. The split is local
until separately approved merge/push; GitHub runner acceptance remains pending.

- **Public:** `Dayshawn21/Sports-Baseline` (remote `origin`). Render, CI and
  every cron run from its `master`.
- **History:** it starts from one snapshot commit (`2312f3a`). Everything
  before 37e lives in the archived private `Dayshawn21/SportAppV2` (remote
  `private`), so the commit hashes in pre-37e archives resolve only there.
  `/rollback` of a pre-37e feature reads its commit from that repo.
- **Workflows register only when a push changes their file.** A new
  workflow that runs only on a schedule or by hand does not appear in
  Actions until a commit touches it.
- **GitHub pauses schedules in a public repo after 60 days with no
  commit.** After a quiet spell, re-enable them in Actions or push a commit.

**Testing is on.** Both `npm run test` and `pytest` are real, so the test gate
applies: a step that adds logic ships a passing test in the same diff. See the
Testing section of `blueprint/context/coding-standards.md` for scope.

`pytest` is declared in `api/requirements.txt`. In this managed Codex shell, the
bare `pytest` command may not be on PATH; use the local venv equivalent
`.venv\Scripts\python.exe -m pytest` from `api/` when needed.

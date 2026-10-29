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

This project uses the **AI Blueprint** workflow layer (local skills plus the
context files below). Never run a framework scaffolder in this directory.

## Read these for full context

- `blueprint/context/project-overview.md` - the project's source of truth
- `blueprint/context/coding-standards.md` - conventions to follow
- `blueprint/context/ai-interaction.md` - how to work with the user on this project
- `blueprint/context/current-feature.md` - the one feature, fix, or rollback being built right now

## Workflow

Build one feature, fix, or rollback at a time, behind review gates. Skills live
in `.claude/skills/<skill>/SKILL.md` (Claude Code, `/name`) and
`.agents/skills/<skill>/SKILL.md` (Codex `$name`, Copilot, OpenCode); when
changing shared workflow behavior, update the skill in both folders. Each
skill's own description says when to use it.

Core loop: `brief` -> `feature` (or `fix`) -> `implement` -> `check` / `try` /
`audit` -> `complete`. Also: `status`, `debug`, `overview`, `rollback`,
`invariants-review`, and setup skills (`onboard`, `adopt`, `discovery`,
`doctor`, `tests`, `ci`, `release`, `prototype`).

`autopilot` runs only when explicitly invoked and stops before `/complete`,
merge, push, deploy, or destructive actions. `/release` stops before any
deploy, remote change, push, or publish without a separate yes in chat.

## Automatic verification

`.github/workflows/verify.yml` runs the Verify command (under Commands) on
pull requests and pushes to `master`, with `contents: read` only. `/ci` owns
changes to it; never invent a check just to fill the command.

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

One line each. **Read `docs/commands.md` before running, scheduling or changing
one:** it holds quotas, schedules, dry-run behavior and verification limits.

- Matches: `python -m app.ingest.livetennis --days-back 1 --days-ahead 1`
- Tennis odds: `python -m app.ingest.odds_api --hours-ahead 4` (moneyline only
  since 2026-10-26; stops at `--min-requests-remaining`)
- Tennis total games: `python -m app.ingest.tennis_totals [--hours-ahead 24] [--min-credits 150] [--dry-run]`
  (The Odds API, 1 credit per tour-level key with a stored match; dry run spends too)
- Tennis props: `python -m app.ingest.prizepicks`
- ELO: `python -m app.ingest.elo --web`
- Player stats: `python -m app.ingest.player_stats --today-only`
- TennisMyLife box scores: `python -m app.ingest.tennismylife [--days-back 21] [--since YYYY-MM-DD] [--dry-run]`
- Candidate tennis ELO: `python -m app.ingest.tennis_elo` (dry run by default)
- Tennis ELO shadow freeze: `python -m app.ingest.tennis_elo_comparison` (dry
  run by default; never substitute new downloads for a stored roster's originals)
- Tennis ELO report: `python -m app.backtest.tennis_elo --count` (`--score`
  needs a separate once-only approval)
- PrizePicks projection snapshots: `python -m app.ingest.prop_snapshots`
- Tennis forward prop check (48e): `python -m app.backtest.tennis_prop_check
  [--version props-v3] [--as-of YYYY-MM-DD]` (read-only; the first real run
  needs a separate yes in chat)
- NFL schedule + stats: `python -m app.ingest.nflverse --season 2024`
- NFL props: `python -m app.ingest.prizepicks_nfl [--relink]`
- NFL game odds: `python -m app.ingest.nfl_odds --days-ahead 14 [--dry-run]`
- NBA schedule + box scores: `python -m app.ingest.hoopr_nba [--season 2025] [--days-back 3] [--dry-run]`
- NBA preseason: `python -m app.ingest.espn_nba_preseason [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--dry-run]`
- NBA props: `python -m app.ingest.prizepicks_nba [--dry-run] [--relink]`
- NBA injuries: `python -m app.ingest.nba_injuries [--dry-run]` (needs migration `0048`)
- NBA game odds: `python -m app.ingest.nba_odds [--days-ahead 2] [--min-credits 100] [--dry-run]`
  (3 The Odds API credits a run, dry run included)
- NHL schedule + box scores: `python -m app.ingest.nhl_api [--season 2025] [--days-back 3] [--dry-run]`
- NHL props: `python -m app.ingest.prizepicks_nhl [--dry-run] [--relink]`
- NHL game odds: `python -m app.ingest.nhl_odds_io [--days-ahead 2] [--min-requests-remaining 20] [--dry-run]`
  (dry run still spends hourly Odds-API.io requests)
- NHL injuries and goalies: `python -m app.ingest.nhl_context [--dry-run] [--date YYYY-MM-DD]`
  (migration `0050` must be applied before real writes and nonempty NHL reads)

### Ask Lineform (`api/`, 47)

Full notes, the guardrails, the SSE contract and a `curl` example: `docs/commands.md`.

- Tool preview (no API call): `python -m app.services.ask.preview <tool> key=value ...`
- Chat: `python -m app.services.ask.chat <question>`. **Every run is a paid
  request**; needs `ANTHROPIC_API_KEY`, read only through `Settings`. Never
  part of Verify or CI.
- Evals (47e): `python -m app.evals.ask --dry-run` (no API call), then
  `--confirm-spend [--only ids] [--out]` for a paid run (30 cases, about
  $0.02). Never part of Verify or CI.
- **Off unless `ASK_ENABLED=true`.** In production `ASK_ENABLED` and
  `ANTHROPIC_API_KEY` are Render dashboard values (`sync: false`); never
  commit `ASK_ENABLED=true`. Production refuses to start with it on and no
  key. Locally, set it in `api/app/.env` and restart the API to try the drawer.
- Guardrails (47d, in memory, reset on restart): 20 questions per client a
  day and a $1 global daily spend cap, both refused before Claude is called.
  The Anthropic Console monthly spend limit is the hard stop.

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

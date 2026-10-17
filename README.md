# SportApp

[![Verify](https://github.com/Dayshawn21/Sports-Baseline/actions/workflows/verify.yml/badge.svg)](https://github.com/Dayshawn21/Sports-Baseline/actions/workflows/verify.yml)

A sports betting research app for tennis, NFL and NBA. It ingests matches,
odds, player stats and prop lines on a schedule, and builds model
projections. It then grades those projections against the betting market,
so an edge is measured rather than assumed.

**Live demo:** https://sportapp-web-7v3r.onrender.com
(read-only; anyone can browse every page)
**How it works:** https://sportapp-web-7v3r.onrender.com/#/how-it-works

![NFL game page: market beside a muted model, best line and injuries](docs/screenshots/nfl-game.png)

## What it shows

| Sport | Pages | What is a pick today |
|---|---|---|
| Tennis | Daily slate, prop board, match, player, model track record | Derived game-spread, serve-edge and PrizePicks picks. Moneyline picks are off (see below). |
| NFL | Game-first slate, prop board, game, player, model track record | None. Prop edges, the game-line model and the best-line view are reference only, shown in gray. |
| NBA | Slate, game page, model track record | None. A reference projection with P(over) for assists only, shown in gray. |

![Tennis slate](docs/screenshots/tennis-slate.png)

The tennis slate ranks its remaining picks by modelled EV. A large EV figure
there is the model's own estimate, not a validated edge. Those picks are
graded forward on the tennis track record page, and their confidence tiers
are still accruing.

## What I found

The interesting part of this project is what the testing showed, not the
models themselves.

- **Every signal had to pass a backtest first.** Each new signal had to beat
  the market or the production model on a held-out season, under an
  adoption rule written down before the data was read. Most failed, and the
  app says so.
- **Tennis.** On the 2023 to 2025 holdout (12,068 ATP and WTA matches), the
  Pinnacle closing line beat computed ELO and the original hand-set blend on
  log loss. A blend fitted on 2022 matched the close (+0.0002 +/- 0.0004), but
  betting its larger disagreements still lost money. So the served tennis
  model is now anchored to the market, and moneyline picks are switched off.
- **NFL game lines.** Team ELO, a scoring rating, weather, rest and
  play-by-play efficiency were each tested against closing lines on
  2022 to 2025. None beat the close, so the model is shown as context, never
  as a pick.
- **NFL props.** The first grading of the PrizePicks prop model (2026-09-26)
  hit 48.1% of 750 calls, against a 57.7% per-pick break-even. Prop edges
  have been gray since. Frozen pre-kickoff predictions are graded weekly
  under a rule fixed before any week was played.
- **Color is a claim.** Green means a result beat its baseline by more than
  two standard errors. Anything still accruing or unvalidated stays gray.

The live track records:
[tennis](https://sportapp-web-7v3r.onrender.com/#/tennis/model),
[NFL](https://sportapp-web-7v3r.onrender.com/#/nfl/model),
[NBA](https://sportapp-web-7v3r.onrender.com/#/nba/model).

![NFL model track record](docs/screenshots/nfl-model.png)

## Architecture

- **API** (`api/`): FastAPI on Python 3.11, async SQLAlchemy over Postgres.
  The code is layered: thin routers, services for orchestration, pure
  functions in `app/core/` with no I/O, and all SQL in `app/repositories/`.
- **Web** (`web/`): a React single-page app that only talks to the API.
- **Database:** PostgreSQL on Neon, with 45 Alembic migrations.
- **Ingest:** standalone `python -m app.ingest.<name>` jobs, scheduled in
  GitHub Actions. The hosted API runs no cron jobs.
- **Hosting:** Render, a Python web service and a static site, defined in
  [`render.yaml`](render.yaml). Reports too heavy to build inside the
  512 MB instance are precomputed by the scheduled jobs and served from
  the database. That covers the NFL slate (up to 18 MB of JSON a week) and
  the NFL prop-line grading.
- **CI:** [`verify.yml`](.github/workflows/verify.yml) runs the typecheck,
  both test suites and the build, plus a pinned gitleaks secret scan, on
  every push and pull request.

## Stack

- **Backend:** FastAPI, SQLAlchemy 2 (async, psycopg 3), Alembic,
  Pydantic 2, LightGBM, scikit-learn.
- **Frontend:** React 19, Vite, TypeScript (strict), Ant Design 5,
  Tailwind CSS v4, TanStack Query.
- **Tests:** pytest (about 2,600 tests) and Vitest (about 530).
- **Data:**
  - **Tennis:** livetennisapi, TennisAbstract, Odds-API.io, PrizePicks.
  - **NFL:** NFLverse, The Odds API, Odds-API.io, PrizePicks.
  - **NBA:** hoopR's ESPN releases, The Odds API, PrizePicks.

## Running locally

You need Python 3.11, Node 20.19 or newer, and PostgreSQL 15 or newer. The
pages fill only once the ingest jobs have run, and those need the provider
API keys listed in `api/.env.example`.

**API**

```bash
cd api
python -m venv .venv
.venv/bin/pip install -r requirements.txt   # Windows: .venv\Scripts\pip
cp .env.example app/.env                    # then set DATABASE_URL
```

Migrations need an `alembic.ini`, which is not tracked. Copy
`.claude/skills/neon-migrate/alembic.ini.template` to `api/alembic.ini`, set
`script_location = app/db/migrations`, then run `alembic upgrade head`
from `api/`.

```bash
uvicorn app.main:app --reload               # http://127.0.0.1:8000
```

On Windows, psycopg's async driver needs the selector event loop, so start
the API like this instead:

```bash
python -c "import asyncio, sys, uvicorn; sys.path.insert(0, '.'); asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy()); uvicorn.run('app.main:app', port=8000, loop='none')"
```

**Web**

```bash
cd web
npm ci
npm run dev                                 # http://localhost:3001, proxies /api to the API
```

**Checks** (the same command CI runs, from the repo root, with the API venv
active):

```bash
npm --prefix web run verify && cd api && python -m pytest
```

## Repo map

| Path | What is there |
|---|---|
| `api/app/routers`, `services`, `core`, `repositories` | The API layers described above |
| `api/app/ingest` | Scheduled data jobs |
| `api/app/backtest` | The holdout tests and forward grading reports |
| `web/src` | Pages, hooks, typed API client, pure display helpers |
| `.github/workflows` | CI and the ingest schedules |
| `blueprint/` | The AI-assisted build workflow. It holds the plan, and a spec for every shipped feature with its test evidence. |

## About this repo

This is a personal research project, not betting advice.

The code is shared for review; all rights reserved.

The repository starts from a clean snapshot. Earlier development history is
kept privately.

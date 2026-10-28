# Command reference

Full notes for the ingest and Ask Lineform commands. `AGENTS.md` keeps one line
per command; read this file before running, scheduling or changing one.

## Ingest (`api/`, each runnable standalone)

- Matches: `python -m app.ingest.livetennis --days-back 1 --days-ahead 1`
- Odds: `python -m app.ingest.odds_api --hours-ahead 4` (Odds-API.io DraftKings
  and FanDuel; both send tennis moneylines only on the free plan, checked on
  2026-10-27 and 2026-10-28, and DraftKings never stored a tennis total. No
  game-spread lines are stored after Bet365 went paid on 2026-10-26; totals
  come from `tennis_totals` below. Stops before any odds batch once the hourly
  quota is at `--min-requests-remaining`)
- Tennis total games: `python -m app.ingest.tennis_totals [--hours-ahead 24]
  [--min-credits 150] [--dry-run]` (48b; The Odds API. Free `/sports` and
  `/events` calls keep the active `tennis_*` keys with a stored upcoming
  match, then one `/odds` call per kept key for `totals` from Pinnacle,
  Marathonbet, Betsson, NordicBet, 1xBet and Coolbet, 1 credit each, usually
  1 to 4 a day. Stores one `match_odds` `total_games` row per match from the
  first of those books that prices it, over in `p1_odds`. ATP and WTA
  tour-level events only: Challenger and WTA 125 have no keys, so their props
  keep `no_market_total`. Stops below 150 credits, above NBA's 100, so tennis
  goes quiet first in a heavy month. `--dry-run` writes nothing but still
  spends the credits. `tennis-totals.yml` runs it daily at 12:45 UTC)
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

## Ask Lineform (`api/`, 47)

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
- Evals (47e): `python -m app.evals.ask --dry-run` validates
  `app/evals/ask_questions.json` and lists the cases (no API call);
  `python -m app.evals.ask --confirm-spend [--only id1,id2] [--out]` runs them
  through `run_ask` against the local database and the real API, one at a
  time, then prints PASS/FAIL/ERROR per case with failure reasons and
  ungrounded numbers, the pass count, tokens and estimated cost (47d's
  `estimate_cost_usd`). Every real run is paid and refuses without
  `--confirm-spend`; 30 cases cost about $0.02. `--out` writes results JSON
  (answers, no tool content) to `api/data/ask-evals/`, which is gitignored.
  Exit 0 only when every case passed, 1 otherwise, 2 on setup errors. Never
  part of Verify or CI. Case rules (`app/core/ask_eval.py`) describe the shape
  of a good answer, never today's values, because data is live; regex
  backslashes are doubled in the JSON. Ungrounded numbers are reported, never
  a failure (percentages of 0-1 rates land there).
- `ANTHROPIC_API_KEY` is read only through `Settings` (`anthropic_api_key`) and
  passed to the client explicitly; it is never needed by tests or CI. The model,
  max tokens, tool-iteration cap and effort are `ask_model`, `ask_max_tokens`,
  `ask_max_tool_iterations` and `ask_effort` (default `low`). Max tokens
  (256-4,096) and tool iterations (1-8) are bounded in `Settings`, so a bad
  environment value fails at startup.
- **Off unless `ASK_ENABLED=true`** (`ask_enabled`, default false). With it off,
  `GET /ask/status` reads `{"enabled": false}`, the web shows no Ask button and
  `POST /ask` is a 404. Production refuses to start with it on and no
  `ANTHROPIC_API_KEY` (`validate_production_settings`). In production both
  are dashboard values (`sync: false` in `render.yaml`); never commit
  `ASK_ENABLED=true`. Unsetting it in the dashboard turns Ask off without a
  deploy.
- **Guardrails (47d, in memory, one process; a restart resets both):**
  - Global daily spend cap, `ask_daily_spend_cap_usd` (default $1, UTC day):
    `POST /ask` is a 503 "Ask Lineform has reached today's limit..." once
    today's estimated spend reaches it.
  - Per-client daily questions, `ask_daily_questions_per_ip` (default 20, a
    rolling 24 hours): past it, a 429 with `Retry-After`. Checked after the
    cap and after body validation, so a refused or invalid question uses
    none. The client is `request.client.host`, spoofable through
    `X-Forwarded-For` (37d's accepted limit).
  - Both refuse before a client exists, so a refused question costs nothing.
    The check reads spend before a question runs, so questions in flight can
    overshoot the cap by at most one question's maximum cost each. **The
    Anthropic Console monthly spend limit is the hard stop.**
  - Cost is estimated from token usage and the `ask_price_*_per_mtok`
    settings (Haiku 5.5's up-to-100K rates; update them with `ask_model`).
    Every question that reached Claude logs one INFO line from
    `app.services.ask.answer_stream`: `ask question stop= requests= input=
    output= cache_read= cache_write= cost_usd= spent_today_usd= tools= ms=`
    (`stop` also `cancelled` on a disconnect). It never carries the question,
    the answer or the IP. A round cut off mid-stream by a disconnect is not
    counted.
- Stream: `POST /ask` with `{"question": "..."}` (1-500 characters) returns
  server-sent events: `tool_start` (`name`, `sport`), `tool_end` (`name`,
  `ok`), `text` (`delta`), `: ping` comments through slow tools, then one
  `done` (`stop`, `text`; the final text replaces the deltas) or one `error`
  (fixed copy; the exception is logged, never sent). 503 when enabled without a
  key; `/ask` is also on the heavy rate limit (10 a minute per client). Every
  question is a paid request:
  `curl -N -X POST http://127.0.0.1:8000/ask -H "Content-Type: application/json" -d "{\"question\":\"who plays in the NBA tonight?\"}"`
- To try the drawer locally, set `ASK_ENABLED=true` in `api/app/.env` (or in
  the API process's environment) and restart the API.

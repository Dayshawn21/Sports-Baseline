# 45f final local verification

Feature branch: `feature/45f-nhl-injuries-starting-goalies`.
Date: 2026-10-24. All implementation steps, including Step 7's documentation
and final checks, were approved without checkpoint commits. Ready for the
separate /complete workflow; no commit or merge was authorized by this approval.

## Review packet

| Area | Result and evidence |
| --- | --- |
| Source/parsing | Injury, goalie and team-directory samples were verified; pure parsers and conservative linking are tested. See `source-shapes.md`. |
| Persistence | Migration 0050 and offline SQL prepared; exact/conflicting retry, rollback and empty markers tested with doubles. See `storage-verification.md` and `0050-upgrade.sql`. |
| Ingest | Bounded retry/deadline, per-feed commits, dry-run and safe failure summaries tested. A real read-only dry run succeeded; see `ingest-verification.md`. |
| API | Two indexed batch selections and one shared clock/assembler; isolated SQL and localhost HTTP checks cover temporal boundaries and migration-required 503. See `api-verification.md`. |
| Slate | Typed context, goalie labels and team counts; desktop/phone states, search, date and keyboard navigation checked. See `slate-ui-verification.md`. |
| Game | Starting goalies and team injury lists in Matchup; both teams, long lists, identity/status/temporal states, default tab, parity, navigation and retry checked. See `game-ui-verification.md`. |
| Operations | `docs/nhl-context.md` documents activation, commands, schedules, source limits, storage, selection and acceptance boundaries. `AGENTS.md` and `docs/nhl-display.md` link the contract. |
| Product explanation | `web/src/pages/howItWorksContent.ts` names conditional ESPN reports and late-change/empty-report limits. Desktop/phone browser checks passed without API requests, page exceptions or horizontal overflow. |
| Interview guide | Existing NHL explanation updated locally to distinguish implemented/fixture-validated work from pending migration/write/runner/deployment acceptance. File remains ignored and unstaged. |

Step 7's incremental public diff is local `output/45f-step7.diff`. The ignored
guide has its own local `output/45f-step7-guide.diff`. The user's pre-existing
overview edit was preserved; plans and skill adapters were not changed.

## Busy-slate HTTP measurement

The actual FastAPI application ran on localhost with isolated SQLite context
tables and a controlled 12-game schedule, empty market rows and prop counts.
The 24 fixture teams had six injuries each, 144 total; every game had two
Expected goalie observations, 24 total. Requests were constrained to localhost;
no shared database, migration or external HTTP was used.

| Request | Bytes | Elapsed ms | Context queries |
| --- | ---: | ---: | ---: |
| Twelve-game slate, first sample | 51,163 | 58.40 | 2 |
| Same slate, second sample | 51,163 | 13.66 | 2 |
| Same slate, third sample | 51,163 | 11.15 | 2 |
| One game detail | 4,274 | 10.41 | 2 |

Each slate contained all 144 injury entries and 24 goalie sides, with expected
statuses. Detail contained twelve injuries and two goalie sides. Query count
was independent of game count. The server shut down after the probe. Reproducible
local artifacts: `output/45f-step7-http-probe.py` and
`output/45f-step7-http.json`.

This is payload/batch evidence, not a PostgreSQL query-plan, production latency,
concurrent-load or peak-memory benchmark. It makes no 512 MB memory guarantee.
Existing odds/prop HTTP parity evidence remains in Step 4; those market inputs
were deliberately controlled in this measurement.

## Invariants review

Verdict: clean for the feature's source diff plus uncommitted new files,
against `master`, using `.claude/agents/invariants-reviewer.md` through the
Codex invariants-review skill. This is a focused invariants review, not a full
quality/security audit. No ledger status was changed.

- Shared player/game/team candidate, link-validation and context-selection
  queries retain NHL sport filters; served games require REG/PST.
- Existing odds-provider and modelled-market predicates were not changed.
  No NBA baseline, projector, grader or shared prop module was changed.
- New core imports remain pure; SQL is confined to the repository/migration.
  Static import checks passed for the three new core modules.
- No holdout scoring, fitting, model/version/adoption rule or recommendation
  calculation changed. This is stored display context only.
- UI uses incumbent gray tokens and the observed 11px minimum; no new green/red
  signal or recommendation sorting was added.
- No embedded credentials or raw exception responses were found in the reviewed
  feature files. Missing context tables produce the sanitized 503. No separate
  secret-scanner run was added to the documented Verify gate.
- Context uses two batched reads without provider calls, roster relinks or
  heavy request-time reports. Production memory/load acceptance is unmeasured.

The new workflow's YAML and exact cron, contents-read permission, serialized
non-canceling group, ten-minute bound, command and sole DATABASE_URL environment
entry were checked locally. It was not published or dispatched.

The findings ledger contains F-09 (P3 unverified tennis research follow-up) and
F-12 (P2 unverified NFL research follow-up). There are no open/fixed P0/P1
findings blocking completion. These unrelated findings remain unchanged.

## Automated and browser checks

Final automated command, from root with the API venv on PATH:
`npm --prefix web run verify && cd api && python -m pytest`.
Typecheck, 903 web tests, production build and 4,462 API tests passed. The
ignored `output/45f-step7-verify.log` records the run. Existing Vite chunk-size and Starlette/AnyIO
deprecation warnings remain.

How It Works browser captures: `output/45f-step7-how-1440.png` and
`output/45f-step7-how-390.png`. Document scroll widths were 1425px at 1440px
and 375px at 390px. Both rendered the conditional pre-game report explanation
and retained No projections or pick recommendations. The manual UI detector
returned `[]`. Slate/game source did not change in Step 7; their approved
desktop/phone evidence remains the acceptance evidence for those surfaces.

## Remaining operational acceptance

Migration 0050 remains unapplied by this work. Real snapshot writes,
PostgreSQL read-back/query acceptance, GitHub workflow registration/first-run
acceptance and hosted API/UI deployment are pending. Nonempty NHL slate/game
reads require the new tables; apply the reviewed migration before deploying
the backend change. An empty context store after migration serves Unavailable.

The real Step 3 dry run proves source parsing/linking against existing
candidates at its recorded fetch times, not successful persistence. Portable
SQLite/double tests do not prove PostgreSQL DDL, locks or savepoint behavior.
Future model experiments need their own specification and scoring approval.

No commit, merge, push, dispatch or deployment was performed. After review,
`/complete` can archive/log the feature and create its work-level commit;
merging still needs explicit approval and pushing is a separate decision.

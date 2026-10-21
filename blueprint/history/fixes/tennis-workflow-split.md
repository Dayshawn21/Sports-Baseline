# Separate tennis GitHub Actions workflows

**Type:** Fix

**Completed:** 2026-10-21. Implementation approved by the user's `$complete` request.

## The problem

`.github/workflows/tennis-ingest.yml` bundles eight manual job choices and
multiple independent schedules into one Actions entry. NBA and NFL expose
separate workflows for operational tasks, making them easier to find and run.

## The fix

Split tennis into six clearly named Actions workflows, preserving existing
commands, UTC schedules, dependent job ordering, and experiment safeguards.

| File | Contents | Existing schedule (UTC) |
|---|---|---|
| `tennis-ingest.yml` | LiveTennis matches and H2H | Daily 06:30 |
| `tennis-odds.yml` | Odds-API.io odds refresh | Every four hours at :10 |
| `tennis-prop-lines.yml` | PrizePicks tennis lines | Daily 13:00 |
| `tennis-predictions.yml` | Predictions, then prop snapshots; dependent ELO shadow freeze | Daily 13:30 |
| `tennis-box-scores.yml` | TennisMyLife box scores; dependent candidate ELO refresh and cache validation | Daily 11:00 |
| `tennis-player-stats.yml` | Existing player-stats backfill | Daily 10:00 |

Each workflow supports manual dispatch. Single-purpose workflows need no job
selector. Predictions retains manual choices for its predictions chain or
shadow freeze alone; box scores retains choices for its ingest chain or
candidate ELO alone. Preserve the current rules controlling whether dependent
jobs run after success, explicit dispatch, failure, or cancellation.

Keep ELO cache paths and exact keys, UTC-day checks, implementation/identity
pins, concurrency groups, immutable source validation, and experiment
activation/scoring boundaries unchanged. Scope provider secrets to workflows
that use them. Preserve runtimes and install commands; use read-only contents
permissions. Do not introduce additional scheduled runs or duplicate the old
scheduled jobs.

This is organization only: no quota reduction claim, provider changes,
frequency changes, local batch/scheduled-task changes, model changes, live
ingest, remote dispatch, push, or deployment. TennisAbstract's local work stays
local. The earlier quota fix remains separate and is not implicitly approved
for merge or push by this request.

## Build steps

- [x] Split the workflow and synchronize operational documentation and the
  local employer guide when present. **Done when:** Actions definitions expose
  the six tasks above; every existing cron maps to exactly one workflow;
  all eight original manual operations remain available; dependency and ELO
  safeguards are preserved; references explain the new entry points.

## Verify

- Compare old and new schedules, CLI commands, manual operation routes, job
  dependencies, permissions, secrets, and ELO cache/concurrency settings.
- Validate workflow YAML and Actions expressions with available local tools;
  do not install a new test runner. Use focused checks for dispatch/dependency
  logic if needed, following the existing test conventions.
- Run the documented Verify gate (web verify and full API pytest via venv).
- Review relevant invariants. Record that GitHub registration and scheduled
  runner behavior remain unverified until a separately approved push and
  subsequent remote checks. Do not dispatch paid ingest as a validation step.

## Branch handling

Implementation belongs on `fix/tennis-workflow-split`, independently based on
`master`. Preserve commit `84a5cc5` on `fix/tennis-daily-quota`; do not merge it
or carry it into this fix without explicit approval. The active spec may be
carried to the new branch without discarding any work.

## Implementation review (2026-10-21)

- Implemented on `fix/tennis-workflow-split` from `master`, approved for completion.
  No live ingest or remote dispatch. Merge and push require separate approval.
  The quota fix remains on its separate branch at `84a5cc5`.
- Created the five additional workflow files and narrowed `tennis-ingest.yml`
  to matches. Commands, job steps, runtime, cache pins, concurrency, dependent
  conditions and schedule expressions match the original definitions.
- Added `docs/tennis-actions.md` and linked it from `AGENTS.md`. This guide
  supersedes the older combined-workflow deployment paragraph in the generated
  overview until its next regeneration; that generated file was not hand-edited.
  The local ignored employer interview guide was updated and remains unstaged.
- One-off PyYAML/BaseLoader comparison against `master` passed: six workflows,
  all six original cron expressions exactly once, all eight original jobs,
  unchanged job bodies except redundant single-purpose trigger guards,
  preserved paired-job manual choices/dependencies, scoped provider secrets,
  and read-only contents permissions. No runner dependency was installed.
- Evaluated the unchanged dependent-job expressions over 64 combinations of
  schedule/manual event, operation choice, upstream result, and cancellation;
  all matched the expected routing and failure/cancellation behavior.
- `actionlint` is unavailable locally. YAML parsing and the above structural
  and condition checks passed; GitHub's own acceptance and runtime behavior
  remain pending publication and remote verification.
- Exact Verify command passed with the API venv prepended to PATH, via
  `cmd.exe /d /c "npm --prefix web run verify && cd api && python -m pytest"`:
  web typecheck, 644 tests, production build; 3,455 API tests. Existing warnings:
  Vite large bundle and Starlette/AnyIO deprecation. Ten quota-fix tests are on
  its separate branch and intentionally absent here.
- `git diff --check` passed. Invariants review: clean; no app queries, models,
  UI, request paths, credentials, or holdout/scoring behavior changed. Existing
  F-09 (P3) and F-12 (P2) remain unverified; no P0/P1 blocker.
- Manual try after approved publication: use the six named Actions entries
  documented in `docs/tennis-actions.md`; only predictions and box scores have
  job selectors. Do not dispatch live ingest just to validate the split.

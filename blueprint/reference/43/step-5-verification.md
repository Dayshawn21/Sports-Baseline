# Feature 43 final verification

Implemented and verified locally 2026-10-22 on
`feature/nfl-matchup-usage-context`. Ready for final owner review and `/complete`.
No archive, commit, merge, push, deployment, provider call or shared write.

## Verification and limits

Latest unchanged-source Verify: `npm.cmd --prefix web run verify` passed
TypeScript, **758 web tests** and build; from api,
`.venv\Scripts\python.exe -m pytest` passed **3,674 tests**. Existing Vite
bundle-size/Starlette advisories remain. `git diff --check` passed.

Final `check-evidence-context-ui.cjs` run passed game/board parity, actual usage
and opponent cells, one shared context fetch, player/game/week/market reset,
keyboard focus restoration, desktop/390px and isolated loading/error/retry/
missing-roster cases. No application errors; existing favicon 404 only.
Rec Targets and week reset use controlled fixtures, not refreshed shared slate.
Tab/specialist browser reports also pass (real kicker, controlled punter).
Earlier Step 3 continuous-page captures represent the pre-tab layout; final
layout reference is `tabs-*` and final player reference is `specialist-*`.

`check-context-resources.py` uses one read-only PostgreSQL transaction and
statement timeouts. No credential/connection string is persisted. All 14 stored
2026 Week 7 games match their week-batch matchup values and covered dates
precede target kickoff. Four queries per game independent of roster size;
36-46 roster players. Per-game latency 0.452-0.635 seconds, payload
53,917-68,801 bytes; traced peak Python allocation 0.734-0.909 MiB including
serialization. Week batch: 14 matchups, two queries, 0.332 seconds, 40,610 bytes,
0.818 MiB peak. See `step-5-resources.json` for every sample.

This supports retaining the bounded display path at measured current volume.
Tracemalloc excludes total process RSS/native allocations; sequential local
samples do not prove hosted concurrency or future full-season volume. No new
heavy report/fallback was added.

## Invariants review

**Clean** for the current feature diff against master and uncommitted source.
Applied `.agents/skills/invariants-review/SKILL.md` and the repository reviewer
checklist. NFL table reads remain sport-filtered; same-season completed REG
pre-week history, pinned team membership and bounded SQL are explicit. Core
remains pure; SQL stays in repositories. No odds-reader, NBA, model/version,
probability, fit, ranking-rule, frozen/grading, admin/auth or workflow changes.
UI context remains neutral with 11px minimum; sample dates explicitly UTC,
kickoffs CT. No newly embedded secrets or exception details observed. Existing
main-feed-only player lines and past fantasy records remain documented limits.
No open/fixed P0/P1 in the findings ledger; existing unverified P2/P3 leads remain.
This targeted invariants pass is not a broad code or security audit.

Updated `docs/SportApp-Employer-Interview-Guide.md` on disk with implemented,
locally verified context, history safeguards and resource evidence. It remains
ignored and untracked; never stage it. Pre-existing plan/overview edits were
preserved. Line-only modelling/rating and P filter were deferred by the owner.
aDOT remains unavailable per the recorded source feasibility contract.

## Manual review / next action

Open http://localhost:3001/#/nfl/game/94. Player Props opens by default, with
roster usage beneath the markets; Matchup contains team stats and position
allowed. Open A.J. Brown's receiving-yards row and compare the same board row.
Other markets links navigate to specialist game-log columns; Andy Week 6 shows
2 FG, 2 PAT and 8 kicking points. Try
http://localhost:3001/#/nfl/player/40440?market=kicking_points#game-log.

Owner approval closes Steps 4/4a/4b/5. `/complete` then archives the spec,
checks build-plan43, resets current-feature and makes the feature commit;
merge requires explicit approval and push requires a separate approval.

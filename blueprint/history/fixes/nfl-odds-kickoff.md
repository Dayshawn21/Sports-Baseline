# Fix: Keep NFL game odds before kickoff

**Type:** Fix
**Fixes:** F-11
**Status:** Completed locally and audited; merge approval pending.
**Branch:** `fix/nfl-odds-kickoff`

## The problem

`api/app/ingest/nfl_odds.py` matches returned events to scheduled games without
checking whether kickoff has passed. A game can remain scheduled until the
next score refresh, allowing a delayed or manual run to store in-play prices.

In `api/app/repositories/nfl.py`, `get_slate_market_probabilities` and
`get_slate_matchup_context` select US-provider odds without a pre-kickoff
cutoff. In-play US prices could therefore feed prop projections and the
slate's displayed game markets.

The 2026-10-18 audit recorded 24 post-kickoff Pinnacle rows and zero US rows.
Those are dated audit observations, not a fresh database check. Existing
best-line, line-movement and CLV readers already exclude the affected prices.

## The fix

- In `nfl_odds.run`, skip a matched game when its stored `start_utc` is at or
  before the current UTC time, following `nfl_odds_io.select_events`. Check
  after the provider response, before accepting the event for persistence.
  Apply this to both US and Pinnacle modes and dry-run counts. Keep existing
  behavior when kickoff is unknown, matching the comparison ingest.
- Add `(g.start_utc IS NULL OR o.fetched_at < g.start_utc)` to both slate
  readers before selecting their latest eligible odds. In
  `get_slate_market_probabilities`, put it in the odds `LEFT JOIN` condition
  so games with no eligible price still return null probability/time. In
  `get_slate_matchup_context`, apply it inside `latest_odds` to moneyline,
  spread and total.
- Preserve NFL, regular-season and provider filters, book preference,
  timestamp/id ordering, market parsing, quota checks and append-only storage.
  Retain existing Pinnacle rows and frozen predictions.
- This enforces input timing only. No model/version, fit, threshold, ranking,
  schema, UI or workflow changes; no holdout rerun or forward validation.
  F-13's prop-line cutoff and the other findings remain separate work.

## Build steps

- [x] **1. Add the ingest guard and both reader cutoffs with regression tests.**
  Update `api/app/ingest/nfl_odds.py`, `api/app/repositories/nfl.py`,
  `api/tests/test_nfl_odds.py` and `api/tests/test_nfl_repository.py`.
  Use fixed UTC timestamps and mocked provider/database dependencies.

  **Done when:** before-kickoff events retain normal ingest behavior;
  exactly-at-kickoff and already-started events store no markets in either
  provider mode; dry runs use the same selection; unknown kickoff preserves
  existing behavior. Both reader queries exclude odds at/after known kickoff
  before latest-row selection, preserve games without eligible odds, and
  retain existing provider/book ordering. Tests and the final Verify gate
  pass. Record parity evidence below before marking the step complete.

## Verify

- From `api/`, run `.venv\Scripts\python.exe -m pytest tests/test_nfl_odds.py
  tests/test_nfl_repository.py tests/test_sport_game_odds_provider.py`.
  Extend the existing ingest mocks and recorded-SQL assertions to cover the
  boundary and join placement, including null kickoff and no eligible odds.
- Compare both reader outputs and locally built 2026 slate payloads before
  and after the change using the same captured inputs or a stable read-only
  database snapshot. Clean pre-kickoff inputs must yield identical market
  values, projections and P(over). Include a synthetic newer in-play price
  to demonstrate selection of the older pre-kickoff price, and a game with
  only in-play prices to demonstrate the existing missing-market behavior.
  Avoid comparing independently changing hosted snapshot responses.
- If using the shared database, use a read-only transaction and record the
  season/week and post-kickoff US count. If that count is no longer zero,
  explain changed outputs as removal of ineligible prices rather than claiming
  parity. Do not run ingest, spend provider quota, rewrite report snapshots,
  re-freeze predictions or read held-out outcomes for this check. Report any
  unavailable live parity evidence explicitly.
- Final gate from the repo root with the API venv active:
  `npm --prefix web run verify && cd api && python -m pytest`.
  The documented separate web/venv commands may be used in PowerShell.
- When the repairing step lands, mark F-11 `fixed` with test/parity evidence;
  `/audit` re-reviews it before closure. Leave the ledger open at spec time.

## Evidence

Verified 2026-10-18:

- Product diff: six added lines in `api/app/ingest/nfl_odds.py` check stored
  kickoff against current UTC after fetching; two added predicates in
  `api/app/repositories/nfl.py` exclude in-play prices before selection.
- `api/tests/test_nfl_odds.py`: 16 fixed-clock cases cover both provider modes,
  real/dry runs, past/exact/future/unknown kickoff, and a provider fetch that
  crosses kickoff. `api/tests/test_nfl_repository.py`: two SQL regressions
  pin cutoff placement, retained games, provider filters and ordering.
- Focused command from `api/`:
  `.venv\Scripts\python.exe -m pytest tests/test_nfl_odds.py tests/test_nfl_repository.py tests/test_sport_game_odds_provider.py -q`
  passed all **115 tests**.
- Read-only PostgreSQL parity used one `REPEATABLE READ READ ONLY`
  transaction. `transaction_read_only` was `on`; 2026 US odds fetched at or
  after kickoff still numbered **0**. Both original queries (only the new
  predicates removed) and changed queries returned identical **14 moneyline
  entries and 14 matchup entries** for 2026 week 6.
- Synthetic `VALUES` CTEs executed the actual repository SQL in that same
  transaction. Odds at kickoff and one minute after kickoff were excluded
  from all three markets; an older pregame price survived; in-play-only and
  no-odds games retained null odds; unknown kickoff retained eligible odds.
- Locally assembled synthetic 2026 week-6 slates used those reader results
  and identical mocked non-odds inputs. Full four-game payloads, including
  four non-null projections and P(over) values, were identical on clean
  inputs before/after and after injecting in-play odds with the new queries.
  The old queries produced a different payload on contaminated inputs.
  This is synthetic full-slate parity plus live reader parity, not a rebuild
  of the complete live slate or a regrade of frozen rows.
- The one-off parity script is in the session temp directory as
  `lineform-f11-parity.py`, outside the app tree. No provider request,
  database write, report refresh, freeze or holdout evaluation ran; the
  read-only transaction was rolled back.
- Final gate: `npm --prefix web run verify && cd api && python -m pytest`,
  with the API venv first on PATH, passed: web typecheck, **47 files / 611
  tests**, production build, and **2,672 API tests**. Sandbox restrictions
  initially blocked esbuild configuration loading; the same command passed
  with approved elevated execution. Non-failing warnings: web chunk size
  and the existing Starlette/AnyIO deprecation.
- `git diff --check` passed. No UI changes or browser check were needed.
  The employer interview guide's existing claims remain accurate for this
  small input guard, so no guide update was needed.

The user approved the verified step on 2026-10-18. The build step is checked
off and F-11 was subsequently closed by `/audit F-11`. No open/fixed P0 or P1 findings were present
in the ledger at this review. Other open findings are F-07, F-08, F-13, F-14,
F-15 and F-20; F-09 and F-12 remain unverified.

Review with `git diff -- api/app/ingest/nfl_odds.py api/app/repositories/nfl.py
api/tests/test_nfl_odds.py api/tests/test_nfl_repository.py`. Re-run the focused
command above to try the kickoff boundary cases without a provider call.
At implementation handoff, no commit, merge, push or deployment had been performed. Pre-existing planning
changes and `blueprint/reference/39a/` are outside this fix.

## Completion

- User approved the implementation and invoked `/complete` on 2026-10-18.
- Completed in `output/complete-f11` on `fix/nfl-odds-kickoff`, fast-forwarded
  to `master` at `8b891c0f2fb6d1ee7250f53ceb48294e29140522`. Only this fix's
  four product/test files and completion bookkeeping were copied in. The
  original checkout's active game-page work and planning edits were preserved.
- Final isolated Verify: `npm --prefix web run verify && cd api && python -m pytest`.
  Used the existing API venv and web dependencies with CI's password-free dummy
  `DATABASE_URL`; no test connects. Web typecheck, 47 files / 611 tests,
  production build, and 2,672 API tests passed. Warnings remain limited to
  bundle size and the existing Starlette/AnyIO deprecation.
- Invariants review: clean. NFL/provider filters, repository SQL boundaries,
  model/fit versions, holdout rules, append-only records, signal display and
  production report serving are preserved. No additional holdout read ran.
- F-11 is closed and archived below as `nfl-odds-kickoff/F-11`. Other findings
  remain in the live ledger. No open/fixed P0 or P1 finding blocked completion.
- No build-plan update applies to this fix. No workflow or prototype changed.
  The small input guard does not change an employer-guide claim, so that local
  guide required no update.
- To try it without spending quota, from `api/` run
  `.venv\Scripts\python.exe -m pytest tests/test_nfl_odds.py tests/test_nfl_repository.py tests/test_sport_game_odds_provider.py -q`.
  Expect 115 passing cases, including kickoff boundaries and reader filtering.
- Merge and push require separate explicit approvals. Deployment is unverified.

## Findings

### nfl-odds-kickoff/F-11 [P2] closed - The Odds API NFL ingest stores in-play prices, and the slate's moneyline readers have no pre-kickoff cutoff

**File:** api/app/ingest/nfl_odds.py:67; api/app/repositories/nfl.py:855; api/app/repositories/nfl.py:1937; api/app/repositories/nfl.py:1975
**Found:** 2026-10-18 by /audit (scope: NFL prediction system and consumers; lenses: data quality, leakage, tests)
**Why it matters:** `nfl_odds.run` matches every returned event to a
`scheduled` game dated yesterday to 14 days out, and never compares kickoff
with now. The Odds-API.io and anytime-TD ingests do (`nfl_odds_io.py:67`,
`nfl_prop_odds.py:54`). The Odds API returns live events, and a game stays
`scheduled` until the next morning's `nfl-scores.yml`. Read-only count of
2026 rows:

| Provider | Rows fetched at or after kickoff |
|---|---|
| `the_odds_api_eu` (Pinnacle) | 24 (8 per market): 7 games kicked off 2026-10-11 17:00, fetched 17:41 UTC; the London game 2026-10-18 13:30, fetched 15:51 UTC |
| `the_odds_api_us` | 0 |
| `odds_api_io`, anytime-TD prop odds | 0 |

Both in-play batches came from the Sunday 12:10 UTC `nfl-prop-odds.yml` run
starting 3.5 to 5.5 hours late. US rows are clean only because the US run is
Tuesday-only. Current readers are protected: `bestLine` and line movement
filter `fetched_at < start_utc`, and CLV reads US rows before kickoff. But
`get_slate_market_probabilities` (moneyline used to scale 6 of 9 prop
markets, live and in 27a replays) and `get_slate_matchup_context` (the slate
row's displayed market) take the latest US row with no cutoff. One manual or
rescheduled US run during games would put in-play prices into projections.
27a's `MoneylineTiming` only counts such rows after the fact.
**Suggested fix:** Skip events whose kickoff is at or before now in
`nfl_odds.run` (match `nfl_odds_io.select_events`), with a test, and add
`(g.start_utc IS NULL OR o.fetched_at < g.start_utc)` to the two slate
readers. With zero post-kickoff US rows stored, slate and frozen outputs stay
identical, which a before/after slate comparison can show. This is a data
guard, not a model change; no forward validation needed. Leave the existing
Pinnacle rows (append-only, already excluded by every reader).
**Resolution:** Fixed locally on `fix/nfl-odds-kickoff`, approved by the user
2026-10-18. Ingest skips known kickoffs at or before current UTC in both
provider modes; both slate readers filter odds before kickoff before selecting
their latest eligible rows, preserving games with no eligible odds. Added 16
ingest cases and two SQL regressions; 115 focused tests passed. Full Verify
passed (611 web tests, typecheck/build, 2,672 API tests). One read-only repeatable
transaction found zero 2026 post-kickoff US rows and identical week-6 outputs
from both readers (14 games). Synthetic SQL boundary cases and full four-game
slate parity passed, including projections and P(over). Stored odds and frozen
rows were retained. Evidence and limitations are in `current-feature.md`.
Closed by `/audit F-11` on 2026-10-18 after a fresh review of the repair and
nearby callers across quality, security, performance and tests. The original
defect is removed and no new defect was found in the reviewed repair. This
closure records local code review, not a commit or deployment.

**Re-review evidence:**

- Scope: the F-11 repair's complete product diff in
  `api/app/ingest/nfl_odds.py`, `api/app/repositories/nfl.py`,
  `api/tests/test_nfl_odds.py` and `api/tests/test_nfl_repository.py`, plus
  the parser/matcher, insertion and upcoming-game queries, comparison ingest,
  provider-filter tests, slate assembly, line-grading caller, timestamp/index
  migrations and scheduled ingest/snapshot wiring.
- At audit start, branch `fix/nfl-odds-kickoff`; base `master` (also the locally recorded
  `origin/HEAD`). Merge base and HEAD were both
  `e4d727a3c537e5b7df45edd4e95ac622c88aa487`. The committed range
  `master...HEAD` was empty; the four-file product repair was unstaged.
  There were no staged changes or untracked source files in scope.
- At the final status check, concurrent workspace activity had switched to
  `fix/nfl-game-page-tables` and advanced HEAD/master to
  `8b891c0f2fb6d1ee7250f53ceb48294e29140522`. The F-11 product diff remained
  unchanged. Newly modified web game-page files are outside this focused
  review. Reconcile the active branch with the F-11 spec before `/complete`;
  this audit did not switch branches or include unrelated work.
- Quality/correctness: the guard uses the stored timezone-aware kickoff,
  checks current UTC after the provider response, and follows the existing
  unknown-kickoff policy. Both SQL predicates precede latest-row selection;
  moneyline filtering stays inside the left join. Missing eligible prices
  retain null values and flow through the existing fallback path. All three
  displayed game markets are filtered without altering book preference or
  timestamp/id ordering.
- Security/invariants: NFL, regular-season and US-provider filters and bound
  query parameters remain intact. The repair adds no external input, endpoint,
  credential logging or authorization boundary. SQL stays in repositories;
  model versions, fits, holdout rules and append-only records are unchanged.
- Performance: the added kickoff map is bounded by the existing upcoming-game
  window. Reader predicates reuse existing joins and introduce no query,
  request, aggregation or per-player work. No runtime profiling or query-plan
  benchmark was performed; this is a code-level performance review.
- Fresh signal from `api/`:
  `.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider tests/test_nfl_odds.py tests/test_nfl_repository.py tests/test_sport_game_odds_provider.py`
  passed **115 tests** in 2.87 seconds. Reviewed all 16 new fixed-clock cases
  and both SQL placement regressions; no skipped, focused or placeholder
  tests were found in the three test files. Targeted `git diff --check` passed.
- Inspected the prior implementation's parity script and recorded results:
  live week-6 reader parity and synthetic full-slate parity, including
  non-null projections/P(over) and contaminated-price rejection. These are
  prior runtime observations, not database checks rerun by this audit.
  The earlier passing full Verify evidence was inspected, not rerun.
- Excluded: unrelated planning edits and `blueprint/reference/39a/`, the rest
  of the repository, dependencies, generated/build/cache output, browser QA,
  unrelated web game-page changes, live ingest, provider calls, database access, holdout evaluation and external
  vulnerability scanning. No network command was run. No additional signal
  was required or blocked for the selected repair review.
- Ledger result: F-11 changed from `fixed` to `closed`; no new findings or
  unverified risks were added. Other entries were not re-reviewed or changed.
  No repair is required from this pass; next workflow action is `/complete`.

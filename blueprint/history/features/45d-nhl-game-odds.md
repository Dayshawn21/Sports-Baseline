# Feature: 45d - NHL game odds

**From build-plan:** 45d, NHL game odds

**Status:** complete locally and squash-merged to `master` (2026-10-23); push pending

**Branch:** `feature/45d-nhl-game-odds` (implemented from `master`)

## Goal

Store pre-game NHL moneyline (overtime and shootout included), puck line and
total snapshots for DraftKings and Bet365 from Odds-API.io. Use the shared
`sport_game_odds` table and de-vig each book separately, giving 45e stored
market prices and line history without spending The Odds API credits.

45b and 45c are checked off in the build plan and archived. The overview's
older statement that 45b is next is superseded by that progress evidence.
This feature is one reviewable backend unit with four build steps.

## In scope

- Pure NHL team-name mapping, event matching and full-game market parsing.
- A standalone `app.ingest.nhl_odds_io` CLI with a bounded upcoming window,
  dry run, shared-hour quota floor and safe failure behavior.
- NHL repository reads and append-only writes using existing shared tables.
- A separate seasonal GitHub Actions workflow, operational documentation and
  local verification evidence.

## Out of scope

- NHL routes, slate, game page or frontend registries (45e); injuries and
  starting goalies (45f).
- Player-prop book odds, regulation/three-way markets, Draw No Bet, period
  markets, team totals, outrights and historical odds backfill.
- Projections, P(over), frozen model predictions, picks, signals, consensus
  fair prices or Pinnacle. Fair probabilities here describe each book only.
- Changes to tennis/NFL/NBA cadence, quota allocation or served odds.
- New schema, provider configuration or secrets. No push, workflow dispatch,
  deployment or remote settings change under this spec.

## Build loop

Build one step at a time. Explain the intended diff, implement the step with
its tests, show the diff and done-when evidence, then stop for review before
the next step. Checkpoint commits are optional and require approval.
`/complete` handles the final archive, plan checkbox and work-level commit.

## Build steps

- [x] **Step 1 - Pure matching and market contracts.** Add NHL full-name to
  tri-code mapping and an unambiguous two-team/start-time matcher. Parse only
  the three supported full-game markets from sanitized provider fixtures.
  Use existing odds math; any extraction of common Odds-API.io parsing must
  stay small and preserve NFL output with its existing tests. Do not import
  NFL ingest or repositories from NHL code.
  *Done when:* fixtures prove both home orientations, six-hour matching,
  accent folding, unknown/ambiguous teams, and rejection of unsupported or
  malformed markets. Parsed rows use the exact stored contracts below;
  each probability pair sums to one. NHL and affected NFL tests pass.

- [x] **Step 2 - NHL storage boundary.** Add repository methods for scheduled
  REG/PST games in the bounded UTC window and for appending snapshots with
  explicit `sport='nhl'` and `provider='odds_api_io'`. Guard writes against a
  game belonging to another sport. Keep all SQL in repositories.
  *Done when:* repository contract checks and a read-only local DB inspection
  show the expected NHL candidates; scheduled games with missing starts,
  started games, preseason and other sports cannot become write targets.
  The insert preserves book, sides, line sign, prices, probabilities and raw
  provenance. No migration is needed and no existing odds are modified.

- [x] **Step 3 - Bounded ingest and dry run.** Add
  `python -m app.ingest.nhl_odds_io [--days-ahead 2]
  [--min-requests-remaining 20] [--dry-run]`.
  Read eligible stored games first; skip all provider calls when none exist.
  Fetch ice-hockey events, select pending `usa-nhl` events, and request only
  matched event ids in batches of at most ten for the two allowed books.
  Recheck starts before writing so a slow run cannot store live prices.
  *Done when:* mocked runs prove dry run makes zero writes, real mode passes
  correctly oriented rows to the repository, unrelated returned ids/books
  are ignored, invalid records do not abort valid siblings, and all quota
  and failure cases below stop safely. A bounded live dry run records matched
  games, per-book/market candidate counts and remaining quota with no secret
  output. If the board is empty, record that honestly and use fixtures to
  prove parser behavior; do not fabricate live coverage.

- [x] **Step 4 - Schedule, smoke evidence and documentation.** Add
  `.github/workflows/nhl-odds.yml`, every three hours at minute 40 UTC during
  September-June (`40 */3 * 1-6,9-12 *`), plus manual dispatch. Use the CLI
  defaults, Python 3.11, `contents: read`, the existing install pattern and
  only `DATABASE_URL` and `ODDS_API_KEY`. Serialize runs of this workflow
  without canceling an in-progress writer. Document commands, budget,
  market meanings and freshness limits in `AGENTS.md` and an NHL odds guide.
  Update the ignored employer guide if present, describing only verified
  capabilities.
  *Done when:* one bounded local write run has read-back evidence for its
  accepted snapshots, and a subsequent run appends history without changing
  prior rows; dry run row counts remain unchanged. Missing book/market
  coverage is reported, with unavailable cases covered by fixtures. The
  workflow is inspected locally and the exact Verify gate passes. Remote
  registration, runner acceptance and deployment remain explicitly pending
  an approved push and actual execution.

## Files / areas

- New `api/app/core/nhl_odds.py` (mapping, matching, NHL market acceptance).
- New `api/app/ingest/nhl_odds_io.py`; extend `api/app/repositories/nhl.py`.
- Reuse `api/app/core/odds.py` and `odds_providers.py`; narrowly extract common
  game-market parsing into a neutral core module only if needed, preserving
  the NFL entry point and tests. No general ingest framework refactor.
- New `api/tests/test_nhl_odds.py`, `test_nhl_odds_io_ingest.py` and sanitized
  fixtures; repository contract coverage follows existing project patterns.
- New `.github/workflows/nhl-odds.yml` and `docs/nhl-odds.md`; update
  `AGENTS.md` commands/operations and the local employer guide if present.
- Read-only references: 45a/45b/45c archives, NFL Odds-API.io parser/ingest,
  NBA odds repository methods, and existing odds workflow schedules.

## Data / contracts

These contracts are load-bearing for 45e's market and line-movement readers.

| Field | Meaning |
|---|---|
| `sport`, `provider` | Exactly `nhl`, `odds_api_io`; every future reader must filter both |
| `game_id` | Existing NHL `sport_games.id`, not the provider event id |
| `book` | Canonical lowercase `draftkings` or `bet365`, explicit allowlist |
| `market='moneyline'` | Full-game two-way `ML`, OT/SO included; line NULL, sides home/away |
| `market='spread'` | Full-game `Spread`, puck line; line is the stored home team's signed handicap, sides home/away |
| `market='total'` | Full-game `Totals`; positive goal line, sides over/under |
| `first_odds`, `second_odds` | American integer prices converted from finite decimal prices greater than one |
| `first_market_prob`, `second_market_prob` | Proportional two-way de-vig of this book and this exact paired rung |
| `fetched_at` | Existing database snapshot timestamp; append history rather than updating prior rows |
| `raw_json` | Selected market/rung, provider update time when available, event id and enough period provenance to audit full-game acceptance; no key or request URL |

- Match full team names after case, whitespace and accent normalization to
  NHL tri-codes. Cover all current NHL teams and observed provider aliases;
  no fuzzy matching or mapping a former franchise name onto a current team
  without evidence. Require exactly one stored game with both teams and
  aware start times within six hours. Reject missing/naive/malformed starts,
  identical teams, ambiguous games and conflicting duplicate event matches.
- Both provider event and stored game must be pre-start; stored games must
  remain scheduled REG/PST games. Never create games or teams from odds.
- Exact market-name allowlist: `ML`, `Spread`, `Totals`. Reject draw-bearing
  or explicitly regulation/period markets even if they contain two prices.
  Do not infer full-game meaning from price levels. Preserve 45a's full-game
  source decision; if a new payload contradicts it, stop that market for review.
- For a puck-line ladder prefer the complete +/-1.5 rung; if absent, skip the
  spread instead of silently substituting an alternate handicap. For totals,
  retain the existing NFL parser's deterministic main-rung rule: lowest
  overround, then closest prices, with stable input order for ties. Never pair
  opposite sides from different rungs. Reject nonfinite/missing lines.
- Reversed provider home/away swaps moneyline/spread prices and probabilities
  and negates the spread; totals remain unchanged. Keep one accepted row per
  game/book/market per fetch. Reject conflicting duplicates rather than guessing.

### Quota and failures

- Use `Settings.odds_api_key`; never read or call The Odds API or its key.
- Existing free-plan contract from 45a: 100 requests/hour and two books shared
  with tennis and NFL. One event discovery plus `ceil(N/10)` odds calls costs
  three requests for a 16-game slate. Eight daily runs are about 24 requests
  a day at that size, with no monthly credits consumed.
- The discovery request is the bounded first call when games exist; its
  headers establish the balance. Before every later call require a valid
  remaining count such that spending one leaves at least the configured floor
  (default 20). Unknown, malformed or exhausted balance stops the run.
- Bound CLI inputs (positive days-ahead, nonnegative floor below the hourly
  limit). No blind retry: a timeout or failed response can have consumed quota.
  Stop further requests on HTTP/network failure or invalid top-level payload;
  never continue from a stale pre-error balance. Honor 429 by ending the run
  without sleeping/retrying. Preserve already accepted complete snapshots and
  report a clearly failed/partial outcome; do not log credential-bearing errors.
- Staggering and the floor reduce contention; independent tennis/NFL jobs can
  still overlap. Do not claim cross-workflow locking or guaranteed reservation.
- Missing books/markets append nothing and never delete history. Dry run still
  spends hourly requests, but invokes no insert or commit. Log separate request,
  match, skip, candidate, written and failure counts without sensitive URLs.

## Testing

- Step 1: fixtures cover current team names/accents, reversed sides, time-window
  boundaries, ambiguity, unsupported leagues/markets, one-sided/malformed odds,
  NaN/infinity, draw rows, missing +/-1.5 rung, total ladders and de-vig math.
- Step 2: test sport/provider isolation and inserted shape using existing
  repository test conventions; inspect eligible rows read-only in the real DB.
- Step 3: fixed-clock mocked HTTP/repository tests for no games, 10/11 event
  batching, wrong ids/books, start reached mid-run, empty responses, quota
  boundaries, missing headers, 429, timeout and failures after a good batch.
  These tests must run without external calls or database credentials.
- Step 4: record sanitized live dry-run and write/read-back evidence, including
  provider, books, markets, start bounds, probability sums and append behavior.
  Do not run a sport's holdout, projection harness or scoring report.
- Final Verify from the repo root with the API venv active:
  `npm --prefix web run verify && cd api && python -m pytest`.
  In this PowerShell environment run the documented halves if needed:
  `npm --prefix web run verify`, then `.venv\Scripts\python.exe -m pytest`
  from `api/`. No tests are required for this spec-only change.

## Notes for the AI

- Core stays pure; repositories own SQL; network and CLI orchestration stay
  in ingest. Reuse the shared tables and odds math, not a third sports stack.
- The planned live smoke writes append bounded NHL odds only, not schema or
  existing snapshots. No migrations, model reads or outcome analysis.
- Keep source fixtures small and sanitized. Live values and the market's
  availability can change; 45a's probe establishes a starting contract, not
  a guarantee of today's feed or future runner acceptance.
- Keep 44b's parked branch and all model validation samples untouched.
- Do not mark 45d complete, commit, merge or push during `/feature`.
- No em dashes in new content.

## Spec critique

- Closed the unsafe failure path in the NFL example: NHL stops after a failed
  request instead of reusing an old quota balance for the next batch.
- Made full-game acceptance, +/-1.5 puck-line selection, reversed sides and
  duplicate handling explicit so 45e cannot mix incompatible histories.
- Separated pure parsing, storage, orchestration and scheduled operation into
  four reviewable steps; left frontend, props and model work in later items.
- Distinguished local smoke evidence from GitHub/hosted acceptance, and kept
  the overview's stale progress prose from reopening completed dependencies.

## Implementation evidence

- Step 1 adds the pure NHL matcher/parser, a representative sanitized fixture
  (synthetic prices are labeled), and 81 parser/matcher test cases. No existing
  NFL module changed, and no external requests or database writes were made.
- Web Verify: `npm.cmd --prefix web run verify` passed typecheck, 817 tests
  across 57 files, and the production build. `npm.cmd` avoids this machine's
  PowerShell restriction on `npm.ps1`. Vite's existing large-chunk warning remains.
- API Verify: `.venv\Scripts\python.exe -m pytest` from `api/` passed all
  4,026 tests, including the 81 NHL cases and existing NFL odds tests. One
  existing Starlette/AnyIO deprecation warning remains.
- Step 1 approved by the user on 2026-10-23. Continuing without a checkpoint commit.
- Step 2 adds NHL-only bounded upcoming-game reads and guarded append-only
  inserts, with 17 repository contract tests. The insert fixes provider to
  `odds_api_io`, allows only the two configured books, retains provider event
  provenance and returns no id when the target game is ineligible. Both the
  eligibility check and `fetched_at` use the database statement time, avoiding
  the older transaction timestamp during a slow ingest.
- A read-only transaction against the configured database on 2026-10-23
  returned 15 candidates in the next two days. The first two were game 57029
  (MTL at CHI, 2026-10-24 00:00 UTC) and 57030 (TBL at COL, 01:00 UTC).
  No odds were written and no migration was run. Focused tests passed 102 cases.
- Step 2 approved by the user on 2026-10-23. Continuing without a checkpoint commit.
- Step 2 final Verify passed: `npm.cmd --prefix web run verify` (typecheck,
  817 web tests and production build) and `.venv\Scripts\python.exe -m pytest`
  from `api/` (4,043 passed). Existing Vite chunk-size and Starlette/AnyIO
  deprecation warnings remain; `git diff --check` passed.
- Step 3 adds `app.ingest.nhl_odds_io` and 49 ingest/CLI/storage-range test
  cases. It selects pending NHL events, rejects duplicate conflicts, batches
  at ten events, rechecks starts per parsed row, applies the shared-hour floor,
  and stops on HTTP/network/JSON failure without retry. Successful earlier
  batches can commit on a later provider failure; CLI exit status marks the
  run failed or incomplete. Error output contains no request URL or key.
- Step 3 also tightens the pure parser's numeric bounds to the existing SQL
  integer price and numeric line columns, preventing malformed but finite
  provider values from aborting otherwise valid writes.
- Two live dry runs on 2026-10-23 each used three requests and matched 15
  games. The final run parsed 84 candidates: 14 moneylines, 14 puck lines and
  14 totals per book. One requested event was absent from the odds response,
  reported as `missing_event=1`; no substitute prices were generated. The
  final shared-hour balance was 87. Neither run wrote odds; the final run
  additionally enforced a read-only database transaction and rolled it back.
- Step 3 final Verify passed: `npm.cmd --prefix web run verify` (typecheck,
  817 tests and production build) plus `.venv\Scripts\python.exe -m pytest`
  from `api/` (4,092 passed). The focused NHL suites passed 147 cases.
  Existing build/deprecation warnings remain; no new warning or failure.
- Step 3 approved by the user on 2026-10-23. Continuing to Step 4 without a
  checkpoint commit.
- Step 4 adds `nhl-odds.yml` with the specified seasonal cadence, manual
  dispatch, Python 3.11, two required secrets, `contents: read`, ten-minute
  timeout and non-canceling per-workflow concurrency. Local YAML parsing and
  schedule/permissions/secrets/command checks passed; no remote dispatch ran.
- Added `docs/nhl-odds.md` and the AGENTS.md command/operations entry. Updated
  the existing ignored employer interview guide with the measured storage and
  quota example, retaining the distinction between local verification and
  runner/deployment acceptance. The guide remains ignored and unstaged.
- Step 4 live smoke on 2026-10-23: NHL/provider count 0 -> 84 -> 168 across
  two real runs. Each stored all three markets from both books for 14 of 15
  matched games, with one missing provider event. All 168 read-back rows
  passed sport/provider/book, sides, market/line, event provenance, probability
  pair and pre-start timestamp checks. All 84 game/book/market keys repeated
  in the second run.
- The hash of the 84 first-run rows (including payloads and timestamps) stayed
  `c890ef66624049e433c3ffcb814f8909` after the second run. The hash of all 168
  rows was `ec947749458638c061de83bdfc769cbe`; a following dry run left both
  that hash and count unchanged. First run ended at row id 14634, second at
  14718. No existing rows were updated or deleted; no migration ran.
- Each of those three runs used three requests. Balances ended at 84, 81 and
  78 respectively; zero The Odds API credits were used. Sanitized local-only
  evidence is in ignored `output/45d-storage-smoke-result.json`; the temporary
  verification helper is outside the live app tree.
- The findings ledger has no open/fixed P0/P1 blocker. Existing F-09 (P3) and
  F-12 (P2) remain unverified and unchanged. No outcome/holdout report ran.
- Step 4 approved by the user on 2026-10-23. All four build steps are
  approved. Runner acceptance remains pending; no push, dispatch or deployment
  occurred during implementation.
- Step 4 final gate ran the exact root command
  `npm --prefix web run verify && cd api && python -m pytest` through cmd.exe
  with the API venv on PATH. It passed typecheck, 817 web tests, the production
  build and all 4,092 API tests. Only the existing Vite chunk-size and
  Starlette/AnyIO deprecation warnings remain. Final whitespace checks passed.

## Completion review

- Invariants review: clean. Reviewed the branch and all uncommitted files
  against master for sport/provider filters, pure-core and repository
  boundaries, holdout/version discipline, secrets and request-path memory.
  No model, serving, UI or shared prop-pipeline change.
- Final safety pass found no blocker. All changed files belong to 45d;
  the existing unverified F-09 and F-12 stay in the findings ledger.
  No Blueprint skill/adaptor behavior changed.
- The exact root Verify command and live storage proof are recorded above.
  Manual try: from api/, run the venv Python with
  `-m app.ingest.nhl_odds_io --dry-run`, or follow docs/nhl-odds.md.
- The employer interview guide was updated on disk and remains ignored.
- Parent 45 stays unchecked because 45e and 45f remain. The user approved
  completion after reviewing the feature commit. Squash-merged to local master
  on 2026-10-23; push still requires separate approval. Remote runner acceptance
  is pending.

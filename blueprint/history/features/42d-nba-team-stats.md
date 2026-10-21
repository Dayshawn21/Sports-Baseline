# Feature: NBA team stats

**From build-plan:** 42d (parent 42, NBA prop board)
**Status:** complete (approved 2026-10-21); verified locally; merge, push and hosted deployment pending
**Branch:** `feature/nba-team-stats`

## Goal

Show each team's season-to-date points, rebounds, assists, made threes and
blocks per game, for and allowed, with league ranks. Put both teams' table on
the NBA game page and the opponent's allowed figure for supported markets in
the shared board/game evidence drawer. This gives readers matchup context
without changing any projection, probability, gap, ordering or pick.

## Design reference

Extend the existing NBA surfaces and theme, with no redesign or token port.
There is no `prototypes/` directory. Existing layout references:

- [Game page](../../reference/42b/step2-game-1440.png)
- [Phone game page](../../reference/42b/step2-game-390.png)
- [Evidence drawer](../../reference/42b/step4-assists-drawer-1440.png)
- [Phone evidence drawer](../../reference/42b/step4-assists-drawer-390.png)

Use current source, including 42c's injury panels, as the integration baseline.
The captures establish continuity rather than a new pixel-exact design.
Place the team table after injuries and before props. Add a neutral opponent
context section to evidence, without adding board columns or colored signals.

## In scope

- Current target game's stored season only, from completed `REG` games whose
  Eastern `game_date` is strictly earlier than the target game's date.
- Five per-game measures, each for and allowed, with league ranks, loaded
  sample counts and explicit unavailable/partial/small-sample information.
- Historical team attribution from box-score `team_id` and the game's teams,
  never a player's current `sport_players.team_id`.
- One shared context assembler for game detail, both game prop responses and
  each board game; league-wide aggregation batched by season/date.
- Game-page table and shared evidence drawer, for board and game-page entry.
- Pure logic tests, repository/service regression tests following existing NBA
  patterns, browser evidence and the existing final Verify gate.

## Out of scope

- New sources, ingest jobs, schema changes, migrations or historical backfills.
- Prior-season fallback, rolling windows, home/away splits, possessions, pace,
  efficiency ratings, position defense or official team-box-score reconciliation.
- Combined-market team totals/ranks and double-double rates. Only the five
  named measures are supplied; combined markets show an explicit unavailable
  explanation rather than an invented rank or sum of ranks.
- Any model input, backtest scoring, holdout read, adoption, model/probability
  version change, prediction freeze change, ranking, sorting or pick change.
- NBA slate additions, new routes/pages, redesign, unrelated refactors,
  merge, push, deployment or shared database writes.

## Build loop

Build one step at a time, never the whole feature at once.

1. Explain the next step before editing code.
2. Implement only that step, including tests for its new logic.
3. Show its diff and observable verification; the user reviews it.
4. Proceed after approval. Checkpoints require permission and passing checks;
   `/complete` owns the final archive, commit and separately approved merge.

## Build steps

- [x] **Step 1 - Pure aggregation and ranking contract.** Add typed internal
  team-game inputs and pure season-context calculation in
  `app/core/nba_team_stats.py`, with tests in the same diff. Implement the
  eligibility, missing-data, pairing, denominator and rank rules below.
  *Done when:* deterministic tests prove correct for/allowed rates, strict
  date/season/type/status exclusions, DNP handling, zero versus missing,
  paired metric coverage, tie ranks, league-wide ranking and no prior-season
  fallback. A team with no eligible observations has null values/ranks.

- [x] **Step 2 - Bounded repository read and shared service.** Add a repository
  reader that groups stored player rows into two team sides per historical
  game in SQL, including missing-value counts and score checks. Add
  `services/nba/team_stats.py` to load all league teams and build context for
  requested games, once per distinct season/date, using Step 1's pure math.
  *Done when:* fixture/mocked repository tests prove literal NBA isolation,
  `REG`/completed/season/date filters, historical team attribution, exclusion of
  malformed sides and incomplete totals, and no query per player or prop line.
  A multi-game board uses one shared context read per season/date; an empty
  board uses none. No DB writes or external requests occur.

- [x] **Step 3 - Additive API context with parity.** Define the schemas below
  and attach `teamStats` at game/response level in game detail, both game prop
  responses and every board game. Pass context into existing response builders
  without changing line assembly. Extend existing mocked assembly/parity tests.
  *Done when:* the same game's context is equal across all four surfaces;
  existing line arrays, order, injury context, projections, gaps, probabilities,
  flags and versions are unchanged. Valid games without prior stats still
  return 200 with empty context; invalid/other-sport/PRE ids retain 404.

- [x] **Step 4 - Game-page team comparison.** Add matching TypeScript contracts
  and a compact `NbaGameTeamStats` component. Show all five measures for both
  teams, for/allowed values and ranks, season, cutoff, samples and caveats.
  *Done when:* desktop and 390px game-page captures show readable headers and
  all data without page overflow; no-history, partial coverage, small samples
  and true zeros are distinct. Existing loading/error handling remains usable.
  Any new pure format/selection helpers ship Vitest tests.

- [x] **Step 5 - Shared opponent evidence.** Thread the response-level context
  through board and game prop containers into `NbaPropEvidencePanel`. Use a
  tested pure helper to identify the opposite game team from the normalized
  line team, select the supported measure and format its allowed context.
  *Done when:* all five supported markets show the correct opponent, per-game
  allowed value, rank population and sample; combined/double-double markets
  explain unsupported context, and unknown/mismatched line teams never guess
  an opponent. Board and game drawers match. Keyboard close/focus restoration,
  injury evidence, rungs, row order and mobile behavior remain intact.

- [x] **Step 6 - Running-app evidence and final gate.** Exercise real loaded
  data when available and fixed browser fixtures for edge cases. Capture
  board/game drawers and game tables at 1440px and 390px under
  `blueprint/reference/42d/`, with a short check report. Record request/query
  observations and run the documented Verify command using the API venv.
  *Done when:* all acceptance cases below have evidence, final checks pass,
  and no source imports pull team context into projection/freezing/grading.
  Update the local ignored employer guide if present, distinguishing locally
  verified implementation from deployment; never stage that guide.

## Files / areas

| Area | Expected files |
|---|---|
| Pure math | New `api/app/core/nba_team_stats.py`, `api/tests/test_nba_team_stats.py` |
| SQL and orchestration | `api/app/repositories/nba.py`, new `api/app/services/nba/team_stats.py`, repository/service tests |
| API assembly | `api/app/schemas/nba.py`, `services/nba/game_detail.py`, `props.py`, `line_only_props.py`, `prop_board.py`, existing NBA assembly tests |
| Web contract and helpers | `web/src/types/nba.ts`, new `web/src/utils/nbaTeamStats.ts` and adjacent tests |
| Game table | New `web/src/components/nba/NbaGameTeamStats.tsx` and scoped CSS; `web/src/pages/NbaGamePage.tsx` |
| Shared evidence | `NbaPropEvidencePanel.tsx`, `NbaProps.tsx`, `NbaLineOnlyProps.tsx`, `NbaPropBoardMarket.tsx`, board helper/types as needed |
| Evidence and maintenance | `blueprint/reference/42d/`, current spec; local ignored employer guide if present |

No new API transport or hook is needed: existing endpoints carry additive fields.

## Data / contracts

### Eligibility and totals (load-bearing)

- Use the target game's stored start-year `season`, not today's season. Cutoff
  is the game's stored Eastern date, exclusive, even for completed target
  games or `PIN`/`PST` targets. Historical inputs are always `REG` only.
- Read every league team's eligible games, not just teams on the requested
  date. Restrict ranks to the 30 `NBA_TEAM_CODES`; require literal `nba`
  filters on shared-table reads/joins. Never use the broader served-game-type
  filter for team-stat history.
- For each historical game, sum non-DNP player rows by that row's team.
  `threes_made` reads `three_pointers_made`; other keys match stored columns.
  Ignore DNP rows even if they contain nulls. Zero is a valid observed value.
- A usable game requires both official game teams to have played-player
  rows, consistent opponent attribution, non-null player points, and summed
  points equal to each side's stored final score. Reject malformed games or
  sides, including unexpected third-team rows. Do not replace missing player
  totals with the game's score or infer absent rows as zero.
- For each of the other measures, every played row on both sides must have
  a non-null nonnegative value. A null on either side makes that measure
  unavailable for both teams for that game, while valid measures still count.
- Allowed equals the OTHER team's summed player statistic, not its own total
  or the target prop player's history. Include overtime as recorded, with no
  regulation-time adjustment. Rebounds are summed player rebounds, not an
  official team-rebound total including team-only rebounds; label this basis.
- Divide each measure's sums by its own count of usable paired games.
  `completedGames` counts all prior completed regular-season games for that
  team, including games whose box scores are missing. Show coverage when
  `games < completedGames`. This is observed stored-box coverage, not proof
  that every official player row exists; missing zero-point rows cannot be
  completely detected from scores alone.
- No eligible sample yields `perGame: null`, `rank: null`, `games: 0` and
  the actual `rankedTeams` population for that metric/direction (zero when
  the entire league has no usable observations).
  No carry-over from last season. With 1 or 2 usable games label small sample;
  do not suppress the value. No minimum sample for inclusion in ranks.

### Ranks

- For: highest per-game value ranks 1. Allowed: lowest per-game value ranks 1.
  These describe volume only, not a probability or a player matchup rating.
- Match NFL team-stat presentation: round per-game values to one decimal
  before ranking so identical displayed values share a rank. Competition
  ranks have gaps (1, 1, 3). Rank only non-null observations for the same
  season/cutoff/measure/direction and return the actual `rankedTeams` count.

### Additive response shape (camelCase on the wire)

Use the same `NbaTeamStatsContext` shape on `NbaGameDetailResponse`,
`NbaPropsResponse`, `NbaLineOnlyPropsResponse` and `NbaPropBoardGameSchema` as
`teamStats`. Do not duplicate it onto every prop line.

```text
NbaTeamStatsContext:
  season: integer                      # stored start year
  beforeDate: YYYY-MM-DD                # Eastern, exclusive
  basis: "stored_player_box_scores"
  away: NbaTeamSeasonStats
  home: NbaTeamSeasonStats

NbaTeamSeasonStats:
  team: string                         # game's ESPN team code
  completedGames: integer
  stats: record of exactly points, rebounds, assists, threes_made, blocks
    for: NbaTeamStatRate
    allowed: NbaTeamStatRate

NbaTeamStatRate:
  perGame: number | null                # one decimal
  rank: integer | null
  games: integer
  rankedTeams: integer
```

No prior data still returns both team objects with null rates/ranks and zero
samples. Actual repository failures follow existing endpoint error behavior;
do not silently disguise an error as no history. Missing context must never
remove a prop line. Preserve Pydantic camel aliases and strict web interfaces.

### Evidence selection

Map only `points`, `rebounds`, `assists`, `threes_made`, `blocks` to the same
context keys. The normalized line team must equal exactly one of the context
teams; use the other team's `allowed`. Do not infer from player name/current
roster. Show unavailable when mapping, team identity or the rate is missing.
Use text such as "Opponent allows 25.4 assists/game, rank 8 of 30 (1 = fewest)"
with counted games, season/cutoff and partial/small-sample notes. Explain that
these are team totals and display context, not a player projection.

## Testing

- Pure Python fixtures: two-sided totals and opposite allowed rates, unequal
  games played, DNP/null/zero cases, per-metric denominators, missing one side,
  score mismatches, invalid attribution, tied rounded ranks, missing teams,
  PRE/PIN/PST/non-completed/other-season/same-date/future exclusions, and
  current-season opening day with older-season data present.
- Existing-style mocked repository/service tests: SQL filters and grouped
  results, no writes/network calls, batched read counts, empty board, parity
  across game/detail/board responses, and unchanged pre-existing prop fields.
  Use fixtures only; do not introduce real-database tests or rerun holdouts.
- Vitest: all five mappings, combined/double-double unsupported cases,
  normalized matching and unknown team, away/home reversal, null versus zero,
  rank/population and coverage/small-sample formatting.
- Running API/browser: a historical date with loaded box scores, opening-day
  no history, partial-stat fixture, a missing/mismatched line team, supported
  and unsupported market drawers from both entry points, empty board and
  existing error/retry paths. Compare values and ordering before/after adding
  context; inspect console/network failures and keyboard interaction.
- Check query plans/response latency on a representative stored season with
  read-only bounded inspection. Fetch grouped team-game rows, not a raw season
  of player boxes. Do not create a heavy model/report on the 512 MB request
  path. If measured behavior needs persistent snapshots or a migration, stop
  to revise scope rather than silently adding operational work.
- Final automated gate from repo root, with the API venv active:
  `npm --prefix web run verify && cd api && python -m pytest`.

## Notes for the AI

- Server: repositories own SQL, core stays pure, services orchestrate; routers
  remain thin. Keep this display path independent of model imports and inputs.
- Client: reuse existing TanStack hooks, NBA drawer/theme conventions and CT
  time formatting. No new fetch per drawer, per player or per board row.
- Do not read or score validation outcomes to implement display statistics.
  Preserve modelled-market filters, odds-provider isolation and gray signals.
- The build plan and `42c-nba-injuries.md` archive mark injuries complete.
  The generated overview still calls 42c next; do not hand-edit that generated
  file or overwrite its pre-existing local changes during this feature.
- This spec is one reviewable feature with small steps, so no build-plan split
  or user-owned planning-document edit is needed. Only this spec is written
  by `$feature`; implementation starts after review.

## Draft critique applied

- Locked exclusive Eastern-date and same-season eligibility, league-wide rank
  population, rank direction and ties instead of leaving "league rank" vague.
- Added paired metric denominators, score reconciliation, unknown-team behavior
  and explicit coverage limits so partial boxes cannot silently become zeros.
- Kept player-rebound basis visible and unsupported combination markets honest;
  no new derived team markets, source or model signal was added.
- Kept context once per game/response and batched by season/date, with parity
  checks across all entry points and bounded reads for Render memory.
- Split game-table and shared-drawer UI into separate reviewable steps, and
  included first-game, partial-data and phone evidence before completion.

## Implementation evidence

### Step 1 (2026-10-21, approved)

- Added pure `nba_team_stats.py` and 31 deterministic test cases. The input
  contract groups boxes by team, opponent and DNP status; missing/invalid
  player values must produce null metric totals. Step 2 owns the SQL that
  enforces this per-player rule, including mapping `three_pointers_made`.
- Pure checks cover grouped DNP exclusion, paired for/allowed rates,
  per-metric samples, completed-game coverage, score checks, invalid team
  attribution, strict eligibility, rounded ties and all-league populations.
- Focused: `.venv\Scripts\python.exe -m pytest tests/test_nba_team_stats.py -q`
  from `api/`: 31 passed.
- Final gate: `npm --prefix web run verify && cd api && python -m pytest`
  with the API venv active: 673 web tests, production build and 3,592 API
  tests passed. The sandbox blocked Vite configuration loading; the same
  command passed with approved elevated execution. Vite reported its large
  bundle warning; pytest reported one Starlette/AnyIO deprecation warning.
- The user approved Step 1 with Continue. No API or UI wiring exists yet,
  and no checkpoint commit has been made.

### Step 2 (2026-10-21, approved)

- Added `get_team_box_games` in the NBA repository: one league-wide SQL read
  restricted to the requested season's completed REG games before the date.
  SQL groups by game/team/opponent/DNP and turns null, negative or mismatched
  box-season values into null totals. Missing-box games and unknown box-team
  identities remain visible to the pure coverage and validation rules.
- Added `services/nba/team_stats.py` with an internal typed context. The loader
  queries and calculates the league once per distinct season/date, returns both
  game teams by game id and performs no read when there are no targets.
- Added 13 repository/service cases in `test_nba_team_stats_context.py`.
  Focused command from `api/`:
  `.venv\Scripts\python.exe -m pytest tests/test_nba_team_stats_context.py tests/test_nba_team_stats.py tests/test_nba_repository.py -q`
  passed all 67 cases.
- Final gate: `npm --prefix web run verify && cd api && python -m pytest`
  with the API venv active and approved elevated execution: 673 web tests,
  production build and 3,605 API tests passed. The same Vite bundle warning
  and Starlette/AnyIO deprecation warning remain.
- SQL predicates and grouping are verified by mocked execution, consistent
  with the spec; real PostgreSQL query-plan/latency evidence remains Step 6.
  The user approved Step 2 with Continue. Nothing has been committed.

### Step 3 (2026-10-21, approved)

- Added camelCase team-context schemas with exactly five stat keys; the stat
  dictionary keeps `threes_made` and each pair serializes `for`/`allowed`.
  Added shared dataclass-to-schema conversion and wired the loader into game
  detail, both game prop builders and the date-wide board builder.
- Public builders always return both teams, even with no history or no lines.
  Pure response builders accept optional context for existing internal uses
  such as the slate digest, which reads only `.lines` and does not load team
  stats. Context is attached once per response/game, never per line.
- Added six assembly/contract cases to `test_nba_team_stats_context.py` and
  updated existing board/game/props/injury fixtures for the additive field.
  Parity tests compare all prior prop fields, not only projections, and check
  populated/empty history across all four surfaces and missing-game 404s.
- Focused command from `api/`:
  `.venv\Scripts\python.exe -m pytest tests/test_nba_team_stats_context.py tests/test_nba_prop_board.py tests/test_nba_props.py tests/test_nba_game_api.py tests/test_nba_injury_context.py tests/test_nba_slate_gaps_service.py -q`
  passed 74 cases.
- HTTP smoke: actual app through FastAPI TestClient, with fixed repository
  data and an overridden session dependency. All four endpoints returned 200
  with equal context for populated and empty history; all three game routes
  returned 404 for a missing id. See `blueprint/reference/42d/step3-api-check.md`.
- Final gate: `npm --prefix web run verify && cd api && python -m pytest`
  with the API venv active and approved elevated execution: 673 web tests,
  production build and 3,611 API tests passed. The existing Vite bundle and
  Starlette/AnyIO deprecation warnings remain. `git diff --check` passed.
- No web UI changes, shared database writes or commits. Real database query
  performance remains Step 6. The user approved Step 3 with Continue.

### Step 4 (2026-10-21, approved)

- Added strict web types for all four API surfaces and the five team-stat
  measures. Added the game-page comparison after injuries and before props,
  with two adjacent team tables on desktop and stacked tables on phones.
- Each measure shows for/allowed rates, rank population, counted versus
  completed games, partial coverage and small samples. The heading identifies
  season, exclusive Eastern-date cutoff and rank direction. The basis note
  explains player-box totals, overtime and team-only rebound exclusions.
  Null context has an unavailable state; no prior games have a distinct note.
- Added the pure `nbaTeamRateText` formatter and six Vitest cases covering
  zeros, nulls, actual rank populations, coverage and the small-sample boundary.
  Updated existing board/injury test fixtures for the required nullable field.
- Browser check used the running Vite app and isolated headless Edge with
  fixed HTTP responses: loaded, empty, partial and unavailable context at
  1440px and 390px. No page/table horizontal overflow or page runtime errors;
  the new content's minimum measured text size was 11px. Inspected desktop
  and phone captures; refreshed full-page captures to retain the phone heading.
  See `blueprint/reference/42d/step4-check.md` and its screenshots.
- Impeccable's mechanical detector returned no findings for the component,
  stylesheet and game page. The existing palette and typography were retained.
- Final gate: `npm --prefix web run verify && cd api && python -m pytest`
  with the API venv active and approved elevated execution: 679 web tests,
  production build and 3,611 API tests passed. Existing Vite bundle and
  Starlette/AnyIO deprecation warnings remain. `git diff --check` passed.
- The shared Playwright browser was occupied; the evidence harness reused an
  already cached Playwright package and a separate headless Edge instance.
  No dependency installed, shared browser closed, commit made or deploy run.
  Evidence-drawer display is Step 5; final real-data/error-retry checks remain
  Step 6. The user approved Step 4 with Continue.

### Step 5 (2026-10-21, approved)

- Added `nbaOpponentContext` to select the opposite side's allowed rate only
  when the normalized line team identifies exactly one context team and the
  market is one of the five supported measures. Missing context, ambiguous or
  unknown teams and unsupported markets get explicit explanations.
- Added shared `NbaOpponentEvidence` to both modelled and line-only evidence.
  Board and game containers pass their existing response-level `teamStats`;
  opening a drawer does not fetch data. The section shows the opponent's
  allowed value, rank population, sample, coverage, season/date and basis.
  Missing rates remain unavailable and zero remains an observed value.
- Added 21 selector cases alongside the six formatter tests, including all
  five measures, both team directions, null/foreign/unnormalized team codes,
  ambiguous identity, unsupported markets, missing context and null/zero rates.
- Browser checks found a game-page keyboard focus failure after Escape.
  Both game prop containers now use the board's existing opener tracking and
  post-animation restoration pattern; game rows have stable market/player
  keys for locating the correct button. This repair is within Step 5's
  keyboard/focus acceptance criterion and changes no projection or row order.
- The manual evidence harness initially reused cached fixture data when only
  the URL hash changed. It now reloads a distinct document per fixture case.
  After the focus repair, all 48 board/game cases passed at 1440px/390px:
  equal opponent text, unchanged row order, visible injury evidence, no new
  drawer requests, no context overflow/runtime errors, Enter open and Escape
  close with focus restored. See `blueprint/reference/42d/step5-check.md`.
- Final gate after the repair:
  `npm --prefix web run verify && cd api && python -m pytest`, with the API
  venv active and approved elevated execution: 700 web tests, production build
  and 3,611 API tests passed. Existing Vite bundle and Starlette/AnyIO warnings
  remain. The mechanical design detector and `git diff --check` passed.
- The user approved Step 5 with Continue. No commits, deployments or
  shared database writes. Final real-data, performance and error/retry checks
  remain Step 6.

### Step 6 (2026-10-21, approved)

- Real database checks used a read-only transaction and a 20-second statement
  timeout. The 2024 development-season sample before 2025-04-13 returned
  1,216 games and 4,541 grouped sides. EXPLAIN ANALYZE measured 2.156 ms
  planning and 38.285 ms execution. Grouped fetch plus pure math took
  0.384 seconds, with 4.27 MiB peak traced Python allocations. These are local
  observations, not process RSS or hosted performance guarantees.
- Historical game 25794 had 81/81 counted points games for HOU. Opening-night
  game 21318 had identical context across detail, modelled props, line-only
  props and its board game; both complete line arrays also matched. Its
  date-wide board had three games and 1,868,118 JSON bytes; the selected game's
  prop endpoints had 1,150 modelled and 13 line-only lines. Four sequential
  response assemblies together took 1.639 seconds.
- Final browser checks used captured real responses, retaining every rung for
  one assists and one line-only player. All 12 final checks passed at 1440px
  and 390px: historical values, opening-night no-history, matching board/game
  evidence, delayed loading, 503 error and manual Retry recovery. No page
  runtime errors. Prior fixture and keyboard checks remain in Steps 4 and 5.
- Invariants review: clean. NBA sport scope and REG-only display history are
  explicit; core remains pure. Projection/freezing/grading inputs, fits,
  versions, market/provider filters and gray signals are unchanged. No new
  holdout scoring, schema, scheduled task, provider or paid call occurred.
- The local ignored employer guide now explains the implementation and the
  measured SQL aggregation example, with local owner approval recorded and
  deployment unverified. It remains unstaged. The pre-existing overview edit
  was preserved. Existing ledger entries F-09/P3 and F-12/P2 are unverified and
  outside scope; no open/fixed P0/P1 finding blocks completion.
- Final gate: `npm --prefix web run verify && cd api && python -m pytest`
  with the API venv active and approved elevated execution passed: 700 web
  tests, production build and 3,611 API tests. Existing Vite bundle-size and
  Starlette/AnyIO deprecation warnings remain. `git diff --check` passed.
- Full evidence: `blueprint/reference/42d/step6-check.md`, raw query metrics,
  sampled stored responses and desktop/phone captures in the same directory.
  The user approved Step 6 with Continue. No commit, merge, push,
  migration, deployment or shared database write was performed.

## Completion safety pass

All six steps were approved in the current chat. The final Verify command and
running-app evidence are recorded above. No open/fixed P0/P1 findings exist;
F-09 and F-12 remain unverified in the ledger. The pre-existing overview edit
is excluded from this feature commit and remains unstaged. The ignored local
employer guide was updated and is never staged. No workflow adapters or
prototypes were changed. Merge and push require separate approval.

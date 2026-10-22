# Feature: NFL matchup and usage context

**From build-plan:** 43 (approved 2026-10-22)
**Status:** complete (owner approved via `$complete` on 2026-10-22); verified locally; merge, push and hosted deployment pending
**Branch:** `feature/nfl-matchup-usage-context`
**Type:** Feature

## Goal

Help readers compare opponents and player opportunity on the NFL game page and
inside existing prop drawers, using explicit historical numbers and samples.
This is descriptive context: no new recommendation, model input or player selection rule.

## Design reference

Extend the existing `NflTeamStatsMatchup`, game page and `NflEvidencePanel`.
Use current `web/src/index.css` tokens and the existing table/drawer patterns;
this is an incremental data feature, not replication of the whiteboard image.
No prototypes directory exists. Preserve gray context, numeric alignment, the
11px text minimum, CT labels, keyboard access and phone layouts.

## In scope

- Season-to-date opponent production allowed by position: RB carries/rushing
  yards and receptions/receiving yards; WR and TE receptions/receiving yards.
  Show per-team-game values, league rank, observed games and coverage.
- Compact game-page usage table for the two teams' current-week QB/RB/WR/TE
  roster, ordered by team then player name with stable ID ties. No selection
  by trend magnitude, projection gap or available prop. Player links remain.
- Season player target and carry shares, with explicit team denominators.
- Drawer comparison of last three played games versus season: targets/game,
  target share, carries/game, carry share and offensive snap share where
  applicable. Display metric-specific samples and actual date windows.
- Relevant opponent position context in the existing modelled-prop drawer,
  with identical values on the game page and board.
- Read-only aDOT feasibility review of the existing NFLverse source/schema.
  Record required field, units, coverage and join identity without shared writes.
  aDOT stays unavailable in this implementation unless a concrete schema/ingest
  amendment is reviewed before building it. Never derive it from air-yard share.

## Out of scope

Scheme, FTN integration, NBA, players-to-watch lists, trend labels/arrows,
favorable/unfavorable copy, signal colors, new ranking, projection adjustments,
P(over) changes, model versions, frozen predictions, grading and holdout reads.
No new drawer for line-only markets. No paid provider calls, migrations, shared
DB writes, snapshot refresh, deployment, merge or push in this spec.

## Build loop

Build one step at a time on `feature/nfl-matchup-usage-context`.
Explain the step, implement it, run its checks and show its diff and evidence.
Wait for approval before the next step. Commits require permission and passing
checks; `/complete` handles archive and merge separately.

## Build steps

- [x] **Step 1 - Pure calculations and contracts.** Define typed display
  inputs/results in a new pure core module and additive Pydantic schemas.
  Implement windows, per-game aggregates, ratio-of-sums shares, sample counts,
  coverage and ranks with synthetic tests. Record aDOT feasibility and finalize
  unavailable semantics before UI work.
  *Done when:* tests prove recent/season windows, missing versus zero, ties,
  partial coverage, trades and pre-week exclusion; aDOT evidence names the
  missing raw totals or a reviewed follow-up amendment. No model module changes.
- [x] **Step 2 - Bounded read path.** Add sport-filtered repository reads and
  an orchestration service. Extend `/nfl/game-notes` with matchup context and
  add `GET /nfl/games/{game_id}/context` for a single game's player usage and
  the same matchup context. Both use one shared calculation path. Aggregate
  league position totals in SQL; scope player histories to the game's roster.
  *Done when:* API fixtures prove same matchup values on both endpoints,
  historical cutoffs and NFL-only identity; unknown/non-NFL game returns 404;
  opening week returns structured unavailable values. Query count is bounded
  independently of player/prop count. Existing slate payload and calculations
  remain unchanged.
- [x] **Step 3 - Game-page context.** Add typed API/query helpers, matchup rows
  and the compact player usage table using one game-context query. Reuse notes
  where already available and avoid fetching on every row.
  *Done when:* both teams' values, ranks, samples, dates and links display at
  desktop and 390px; deterministic ordering, loading, unavailable, empty,
  error and manual retry states work; existing market/team stats are retained.
- [x] **Step 4 - Shared evidence drawer.** Use the same game-context query in
  the shared evidence panel, enabled when a valid game is selected. Render
  relevant opponent measures and recent/season usage for the selected player.
  *Done when:* game and board drawers show identical context; changing player,
  game, week or market cannot retain stale context; loading/error is isolated
  from existing evidence, keyboard close/focus restoration works, and unsupported
  position/market combinations omit irrelevant measures without inventing zeros.
- [x] **Step 4a - Game-page tabs (owner requested).** Keep the game header
  above Matchup and Player Props tabs; default to Player Props. Matchup contains
  team market/stats, line movement, position allowed and game notes/availability.
  Player Props contains prop markets and the roster usage table. Preserve relevant
  opponent context in shared prop drawers, query reuse and keyboard access.
  *Done when:* desktop/390px checks prove default/tab content separation,
  keyboard switching, shared header, drawer context and no horizontal overflow;
  the Verify gate passes. Game changes reset to Player Props.
- [x] **Step 4b - Specialist player-page repair (owner requested).** Add nullable
  fgMade, patMade, kickingPoints and punts to game-log rows. Reuse item 34's
  kicking-points rule. K/P logs show specialist columns; hide offensive columns,
  PP fantasy, snap tile and usage chart. Other markets links include market and
  open the matching game-log column. No line-only drawer or new model scope.
  *Done when:* tests prove missing/zero/calculation and position/URL contracts;
  real kicker and controlled punter browser checks show correct columns and
  selected market at desktop/390px; Verify passes. No shared writes required.
- [x] **Step 5 - Verification and documentation.** Run targeted regression
  checks, the exact Verify gate and running-app checks with real stored reads
  plus controlled missing/error/zero cases. Measure query time, response size
  and Python allocation on representative current data, recording limits.
  Update the local ignored employer guide only to the verified implementation
  status, without staging it.
  *Done when:* evidence under `blueprint/reference/43/` proves game/board parity,
  pre-week history, gray neutral presentation, phone/desktop/keyboard behavior,
  no model/probability/order changes and passing Verify. If request-time work
  is too heavy for the 512 MB service, stop for a bounded design amendment;
  do not add a heavy fallback or silently extend report snapshots.

## Files / areas

- New `api/app/core/nfl_matchup_context.py` (pure math/types) and
  `api/app/services/nfl/matchup_context.py` (orchestration).
- `api/app/repositories/nfl.py`, `api/app/services/nfl/game_notes.py`,
  `api/app/schemas/nfl.py`, `api/app/routers/nfl.py`.
- `web/src/types/nfl.ts`, `web/src/api/nfl.ts`, `web/src/hooks/useNfl.ts`,
  `web/src/pages/NflGamePage.tsx`, `web/src/components/NflEvidencePanel.tsx`,
  relevant `web/src/components/nfl/` sections and existing styles.
- API unit/contract tests, web pure formatter/mapping tests and browser evidence.
- `docs/SportApp-Employer-Interview-Guide.md` if present (ignored, never staged).

## Data / contracts

### As-of history and identity (load-bearing)

- Target is the stored NFL regular-season game; its season/week defines a
  uniform pre-week cutoff. History uses only completed `REG` games in the same
  season with `week < target.week` and a known start before target kickoff.
  Never include results from the target week, even if another game finished.
  No previous-season fallback; label `Season through Week N` explicitly.
- Resolve current-week membership from as-of weekly rosters, never the latest
  mutable player team. Historical team and opponent come from the stat row/game.
  Missing/ambiguous membership is unavailable; do not assign a player twice.
- Recent means the last up to three played games within that same season/window,
  chosen before metric filtering. Byes and DNPs do not become zero games;
  missing metrics do not pull older games into the recent window. Keep prior-team
  history, show team changes, and use each game's actual team denominator.

### Metrics

- Position allowed is a sum across opposing players in a position for each
  defense game, then a mean across observed games. Never average player rows as
  though each player represented a separate team-game. Count scheduled eligible
  completed games separately from observed games. An absent position aggregate
  is unavailable unless source completeness establishes a true zero. SQL sums
  must retain missingness rather than coalescing every absent value to zero.
- Rank 1 means fewest allowed, descending strength is not a recommendation.
  Rank only teams with observed values for that measure; report ranked-team
  count, use competition ties after display rounding to one decimal, and show
  `rank / ranked teams`, never assume all 32 teams have coverage.
- Target share = player targets / all teammates' recorded targets for the same
  observed player-games. Carry share = player carries / all teammates' recorded
  carries (including QB carries) for those games. Sum numerators/denominators
  across paired, covered games; do not average precomputed percentages.
  Label these denominators; they are not pass-attempt share or RB-only share.
- Snap share uses the arithmetic mean of stored game `offense_pct`, labeled
  `Avg game snap share`. Normalize the source's percent units to API fractions.
  The stored player snap count does not establish team snap counts; never infer
  a weighted rate from rounded percentages or imply team-count weighting.
- Each metric returns nullable value, observedGames, eligibleGames, windowStart,
  windowEnd, and a reason when unavailable. Define metric fields as targets,
  carries, targetShare, carryShare and avgGameSnapShare; allowed fields are
  rbCarries, rbRushYards, rbReceptions, rbRecYards, wrReceptions, wrRecYards,
  teReceptions and teRecYards. Allowed records also carry rank and rankedTeams. Shares use fractions in the API and
  percentages in the UI. Zero denominator is unavailable; observed zero is 0.
  Window dates reflect contributing games, not today's date.

### API and client

- CamelCase through existing schema conventions. Game notes gain an additive
  `matchupContext` field. The game context endpoint returns gameId, season,
  week, cutoffWeek, matchupContext and players, each with playerId, name,
  position, team, seasonUsage and recentUsage. Matchup context contains both
  team identities and named position/measure records with values/ranks/coverage.
- No fields are added to `NflSlateLine`, stored slate JSON, frozen records,
  model inputs or report versions. Existing consumers tolerate additive notes.
- Query key includes gameId; endpoint metadata defines season/week. Use existing
  TanStack Query/axios conventions and explicit staleTime. Share the cached
  context between game and board drawers; no fetch per line or provider calls.
- Relevant receiving context applies to RB/WR/TE receptions, receiving yards
  and Rec Targets; RB rushing context to RB carries/rushing yards. Rec Targets
  context is explicitly receptions/yards allowed, not targets allowed.
  Unsupported markets receive neutral usage only where meaningful, no fabricated
  fantasy/combo/TD matchup score. Existing line-only rows remain unchanged.

## Testing

Both test gates are on. Pure calculation and formatting logic ships tests in the
same step. Synthetic fixtures cover cutoff boundaries, future/current-week rows,
prior seasons, preseason/postseason, zero/missing denominators, a missing game,
unequal team totals, tied ranks, partial coverage, byes, DNPs and trades.
Repository/endpoint checks pin NFL scope and bounded batching. Compare existing
projection/slate fixtures before/after on fixed data/clock, including targets'
separate version and hidden probability. No historical holdout is scored.

Final gate from repository root:
`npm --prefix web run verify && cd api && python -m pytest`
Use the API venv for Python; run halves separately in PowerShell if needed.
Browser checks use real stored responses read-only and controlled fixtures;
record desktop/phone screenshots, console errors, drawer parity and retry.
A documentation-only spec does not require running application tests.

## Notes for the AI

- Step 1 calculation and unavailable semantics, including the read-only aDOT
  review, are recorded in `blueprint/reference/43/calculation-contract.md`.
  The stored snap percentage is already a 0-1 fraction; preserve those units.
  Step 1 checks passed: 27 new synthetic cases, 706 web tests plus typecheck
  and build, and all 3,641 API tests. Review diff:
  `blueprint/reference/43/step-1.diff`. Owner approved Step 1 and continuation
  to Step 2 on 2026-10-22; no checkpoint commit requested.
- Step 2 evidence and its incremental diff are in
  `blueprint/reference/43/step-2-verification.md` and `step-2.diff`.
  Added 28 SQL/endpoint fixtures; all 3,669 API tests and 706 web tests plus
  typecheck/build pass. A read-only stored 2026 Week 7 check proves shared
  matchup parity (39 game players, 14 week games). Owner approved Step 2 and
  continuation to Step 3 on 2026-10-22. No commit or shared writes.
- Step 3 evidence and incremental diff: `blueprint/reference/43/step-3-verification.md`
  and `step-3.diff`. Added game-page matchup rows and the complete roster usage
  disclosure, one cached context query, 18 formatter/ordering cases and desktop/
  390px browser checks. Verify passes: 724 web and 3,669 API tests. Independent
  UI review: ship within Step 3 scope, no material fixes. Owner approved Step 3
  and continuation to Step 4 on 2026-10-22. No checkpoint commit requested.

- Step 4 evidence and incremental diff: `blueprint/reference/43/step-4-verification.md`
  and `step-4.diff`. Shared game/board drawer context, guarded identities,
  current-row selection and keyboard focus restoration are implemented locally.
  Added 31 mapping/identity cases. Verify passes: 755 web and 3,669 API tests,
  typecheck and build. Desktop/390px browser checks pass, including cache reuse,
  player/game changes, isolated loading/error/retry and missing roster. Rec Targets
  and week/market reset use controlled fixtures; stored slate has no targets row.
  Independent UI review: ship, no material fixes; documentation handoff confirms
  ordinary extension with no system-document changes needed. Step 4 awaits owner
  approval; Step 5 and employer-guide maintenance remain pending. No commit.

- Owner requested and authorized the Step 4a tab split on 2026-10-22.
  Step 4a is implemented locally; evidence and incremental diff are
  `blueprint/reference/43/tabs-verification.md` and `tabs.diff`. Browser checks
  pass at 1440px/390px, including keyboard, drawer context, content separation,
  no overflow and game-change reset. Verify passes (755 web / 3,669 API tests).
  Independent UI review: no material fixes; documentation handoff: no system
  changes needed. Steps 4/4a await owner review; Step 5 has not started.

- Owner authorized Step 4b's specialist repair on 2026-10-22. Implemented
  locally: nullable specialist log fields, reused settlement calculation,
  K/P-specific presentation and market links. Five API cases and three web cases
  plus extended repository fixture pass. Verify: 758 web and 3,674 API tests,
  typecheck/build. Browser evidence: real kicker and controlled punter at 1440/
  390px, offense retained; no overflow or application errors. Review packet:
  `blueprint/reference/43/specialist-verification.md` and `specialist.diff`.
  Step 4b awaits owner review; Step 5 remains pending. No shared writes/commit.

- Step 5 was finished locally after the owner asked about completion on
  2026-10-22. Resource evidence across all 14 stored 2026 Week 7 games:
  four queries/game, 0.452-0.635 seconds, 53,917-68,801 response bytes,
  0.734-0.909 MiB peak traced Python allocation including serialization.
  Week matchup batch: two queries, 0.332 seconds, 0.818 MiB peak. All matchup
  pairs agree; transactions read-only and rolled back. Local measurement is
  not total RSS or a hosted concurrency guarantee. Final shared-drawer browser
  regression passed; tabs and specialist checks retain their latest passing
  evidence. No source change since the passing 758 web / 3,674 API Verify gate.
  Invariants review clean within changed scope; no open/fixed P0/P1 ledger entry.
  Updated ignored employer guide on disk with locally verified status only.
  Final review packet: `blueprint/reference/43/step-5-verification.md`.
  Steps remain unchecked until owner approval. No archive, commit, merge or push.
- Owner deferred modelling/rating line-only markets and a P position filter.
  No new line-only drawer or current-week player-card scope was added.

- Gray and unranked alone do not neutralize selective highlighting. No role
  increasing, elevated production, watch, favorable, arrows or delta-based sorting.
- 39a's recent-form blend and NBA 20f's last_10 were rejected in their tested
  settings; display comparisons cannot claim predictive value from those tests.
- Existing DvP calculations blend history for model purposes. Reuse appropriate
  loaders only when the current-season display cutoff/coverage contract holds;
  never change the model loader to make display results match.
- Repositories own SQL; core has no I/O. Group histories in SQL and retain all
  existing sport/provider/market filters and import boundaries.
- No deployment or adoption claim follows from local verification. Preserve the
  pre-existing overview changes and other user work. Planning approval is not
  approval to implement this draft or to perform remote/shared writes.

## Completion

Owner invoked `$complete` on 2026-10-22 after reviewing the feature, tab split,
specialist repair and final verification packet. This approves all remaining
implemented steps. Earlier per-step pending notes preserve the review history;
the status above and checked steps record the final approval.

The documented Verify command passed as PowerShell halves: 758 web tests,
typecheck/build and 3,674 API tests. Final browser regression and all 14 current
Week 7 resource samples passed; see `blueprint/reference/43/step-5-verification.md`.
No new holdout scoring, provider requests, migrations, shared writes or deployment.
The ignored employer guide was updated locally and is excluded from staging.
Existing F-09 (P3) and F-12 (P2) unverified leads remain in the findings ledger;
no resolved entries to archive and no open/fixed P0/P1 completion blocker.
The pre-existing plan/overview refresh is preserved with this work.

Known limits: aDOT unavailable pending verified raw totals; Rec Targets and
punter UI edge cases use controlled browser fixtures; measured Python allocation
is not full RSS/concurrent hosted capacity. Existing player current-week cards
exclude line-only markets; no line-only drawer was added. Owner deferred rating
those markets and adding a P position filter. No predictive improvement claimed.

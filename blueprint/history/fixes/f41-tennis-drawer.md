# Remove the tennis slate drawer's unreachable Match and serve section

**Type:** Fix
**Fixes:** F-41, F-43
**Branch:** `claude/fix-f41-tennis-drawer-049d68` (the worktree's branch, already off `master`)

### The problem

The tennis slate opens its inline drawer only when `matchAnalysisPath(row.match)`
is `null` (`web/src/components/tennis/TennisSlateTable.tsx:169`), that is for the
prop-only groups `buildUnifiedTennisMatches` builds from orphan props. Those groups
always have `prediction` and `bestMatch` set to `null`, so inside the drawer
`unifiedMatchToPrediction` always returns `null`. Every predicted match navigates
to `/tennis/match/:id` instead. As a result:

- `MatchAndServe` in `web/src/components/tennis/TennisMatchDetail.tsx` (match facts,
  serve and return, the F-27 player-stats queries) never renders.
- The `prediction` branches of the drawer's `Context` header (tags, quality flags,
  player links and prices, the "Open match analysis" link) never render either.

The analysis page already covers all of it: `MatchSidebar` (head-to-head, serve and
return), `MatchComponents` (ELO, ML, market) and `MatchSurfaceContext`.

The user chose option (a), remove, on 2026-11-06.

### The fix

Make the drawer what it actually is: a prop-only detail.

- `TennisMatchDetail.tsx`: delete `MatchAndServe`, `Measure`, `measureValue`,
  `surfaceElo`, `surname`, `PlayerLink`, and the `prediction` branches of `Context`.
  The header keeps the "Player props · start time" line; the grid keeps `Picks`.
  `pickItems` stays as is (best bets and angles are empty for these groups but the
  helpers are shared and cheap).
- `tennis-match-detail.css`: delete the rules only those parts used (`__tags`,
  `__tag`, `__players`, `__open`, `__fact`, `__measure`, the three-column grid and
  `is-props-only`, and their media-query entries).
- `web/src/hooks/useTennisPlayer.ts`: delete `playerStatsQuery` and `usePlayerStats`.
- `web/src/hooks/useTennisPlayer.test.ts`: delete (it only tests `playerStatsQuery`;
  deletion approved with option (a)).
- `web/src/api/tennis.ts`: delete `fetchPlayerStats`, and `PlayerStats` in
  `web/src/types/tennis.ts` if nothing else uses it.

Must not break: the prop-only drawer (picks list, adopted-prop color, gray tiers),
the slate's navigation to the analysis page, and the admin page's separate
`fetchPlayerStats` in `web/src/api/admin.ts`. Nothing in `api/` changes; the
`/tennis/players/stats` endpoint stays for other clients.

### Build steps

- [x] **Step 1 - remove the dead drawer code.** Apply the deletions above.
  Done when `npm --prefix web run verify` passes, a grep for `MatchAndServe`,
  `usePlayerStats` and `playerStatsQuery` in `web/src` finds nothing, and the
  tennis slate in the browser still navigates predicted rows to their analysis
  page and opens the drawer for a prop-only row (when the slate has one).

- [x] **Step 2 - repair F-43, the drawer's unreachable best-bet and angle branches.**
  Found by `/audit current` after step 1; the user chose to fold it in. The drawer
  lists only `match.props` (orphan groups are built with `bestPicks: []`), so
  `pickItem`, `BEST_BET`, `ConfidenceTag`, the positive `evClass` branch, the
  empty state and their CSS go; the section is headed "Props". EV stays gray and
  only the adopted side and margin keep the signal color (48f, 48g).
  Done when Verify passes and a grep for `bestBetPicks` and `ConfidenceTag` in
  `TennisMatchDetail.tsx` finds nothing.

### Verify

- `npm --prefix web run verify && cd api && python -m pytest`
- Browser: `/tennis` slate, click a predicted row (goes to analysis page); expand a
  prop-only row if one exists (picks render, no console errors).

## Findings

### f41-tennis-drawer/F-41 [P3] closed - The tennis slate drawer's Match and serve section is unreachable

**File:** web/src/components/tennis/TennisMatchDetail.tsx:213; web/src/components/tennis/TennisSlateTable.tsx:169
**Found:** 2026-11-06 by /audit (scope: current; lens: quality)
**Why it matters:** the slate opens the inline drawer only when `matchAnalysisPath(row.match)` is `null`, that is when `matchId` is `null`. `buildUnifiedTennisMatches` gives every match with a `prediction` or a `bestMatch` its `matchId` (`getMatch`), so `unifiedMatchToPrediction` always returns `null` inside the drawer and `MatchAndServe` (match facts, serve and return, and f27-player-stats-hook/F-27's stats queries) never renders. Confirmed in the browser on 2026-11-06: no slate row had a drawer toggle, and opening a predicted row navigated to its analysis page. The section and its CSS are dead weight that later changes keep maintaining.
**Suggested fix:** remove `MatchAndServe` and its helpers from the drawer (the analysis page covers them), or decide the drawer should show them and change the expand rule. A product choice, so not folded into f27-player-stats-hook/F-27.
**Resolution:** fixed 2026-11-06 by fix-f41-tennis-drawer (option a, the user chose remove): deleted `MatchAndServe` and its helpers, the drawer `Context` header's prediction branches, their CSS, `usePlayerStats`/`playerStatsQuery` and their test, `fetchPlayerStats` in `web/src/api/tennis.ts` and the `PlayerStats` type. The drawer is now the prop-only detail it always was in practice; predicted rows still open their analysis page, which covers head-to-head, serve and return and the ELO breakdown. Closed 2026-11-06 by /audit (scope: current; lens: all): `MatchAndServe`, `usePlayerStats`, `playerStatsQuery` and `fetchPlayerStats` are gone from `web/src`, Verify passes (web 1249, API 5930), and in the browser all six slate rows still link to `/tennis/match/:id` with no console errors (no prop-only row existed to open the drawer). The leftover best-bet and angle branches are F-43.

### f41-tennis-drawer/F-43 [P3] closed - The prop-only drawer still carries best-bet and angle branches it can never show

**File:** web/src/components/tennis/TennisMatchDetail.tsx:12
**Found:** 2026-11-06 by /audit (scope: current; lens: quality)
**Why it matters:** after F-41 the drawer only ever renders orphan prop groups, which `buildUnifiedTennisMatches` creates with `bestPicks: []` and never fills (bankroll picks go through `getMatch` by match id). So `bestBetPicks`/`anglePicks` there always return nothing, and `BEST_BET`, `ConfidenceTag`, the positive branch of `evClass`, `pickItem` and the "for this match" empty text are unreachable, the same dead weight F-41 removed.
**Suggested fix:** have the drawer list only `match.props.map(propItem)`, drop the best-bet and angle helpers and the confidence tag, and word the empty state for props.
**Resolution:** fixed 2026-11-06 in fix-f41-tennis-drawer (step 2, the user chose to fold it in): the drawer renders `match.props` only, with the best-bet and angle helpers, `ConfidenceTag`, the positive EV class, the empty state and their CSS removed. Closed 2026-11-06 by /audit (scope: current; lens: all): re-read `TennisMatchDetail.tsx` and its CSS, no unreachable branch left, EV gray and only the 48g adopted cell green, no remaining reference to the removed classes, Verify passes (web 1249). No prop-only row was on the slate, so the drawer itself was not opened in the browser.

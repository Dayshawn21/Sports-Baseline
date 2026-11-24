# Current Feature

## 70a. Role-change guard

**Parent:** 70. Injury-aware NFL projections (`blueprint/build-plan.md:330`)
**Branch:** `feature/role-change-guard`
**Completed:** 2026-11-18. Verify passed (1871 web tests, typecheck, build; 6579 API tests). Checked locally on the stored week-10 KC @ ATL game page: Emmett Johnson's rushing line sits under Not rateable as a gray "-58.6 reference gap" with trust Reference and the tooltip "Role changed: Walker out". Deviation: the note is prefixed to "why" at the card and detail call sites, so `nflSignal.ts` is unchanged.

## Goal

Stop the NFL board from calling a pick on a line whose projection cannot know the
player's role this week. 2026 week 10: Kenneth Walker III was ruled Out, and Emmett
Johnson's rushing projection stayed at his RB2 average (14.9) against a 73.5 line
that already priced Walker's absence, so the page showed **UNDER, -58.6**. That gap
is the model being blind, not an edge.

A line is **role-changed** when the player is Out, or his active depth differs from
his chart rank because a teammate ahead is Out (fix `nfl-active-depth`). A
role-changed line keeps its projection and gap, shown as a gray **reference**, the
way Rec Targets lines already are, and is never labelled or ranked as a pick.

## What exists (from a read of the code, 2026-11-16)

| Surface | Decided in | Reads injury or depth today? |
|---|---|---|
| OVER/UNDER label, P(over), trust on cards | `web/src/utils/nflPropCards.ts:82-99` | No |
| Same, on the player/prop detail panel | `web/src/utils/nflPropDetail.ts:92-160` | No |
| "Why" summary | `web/src/utils/nflSignal.ts:58` | No |
| Rateable vs show-all on the prop board | `web/src/utils/nflPropBoard.ts:99` `isRateable` | No |
| Top-N digest (slate strip, prop board, game strip, home gaps table) | `web/src/utils/nflSlate.ts:124` `rankTopProps`, over `rateable` lines | Demotes Out, never removes it |
| Player page prop section | `web/src/components/nfl/NflPlayerPropSection.tsx:22` | No |
| Availability flags | `api/app/core/nfl_availability.py` `availability_flags` | Injury and week-over-week depth only |

The "reference" state is market-level today (`isTargetsReference(market)`, 13 call
sites). 27h is **not built**, so no API path ranks or picks NFL lines by P(over);
the build-plan line's "never ranked or picked by 27h's adopted slices" and "the game
card's top three" (removed with the 33b table slate) have no code to touch yet.

## In scope

- An API flag `role_changed`, computed in the pure `availability_flags`.
- A line-level web predicate, `isReferenceLine(row)` (Targets market **or**
  role-changed), replacing `isTargetsReference(row.market)` at every **row-level**
  call site. Category-level sites (`NflPropTable.tsx:125`, `NflGameProps.tsx:60`,
  `NflPropBoardPage.tsx:92`, `nflPropBoard.ts:169`, `nflLineOnly.ts:76`) keep the
  market test.
- A note on the line saying why: `Role changed: Walker out` or `Player is out`.

## Out of scope

- **Projections, edges and P(over) values.** The API still computes and serves
  them unchanged; this is a display and selection guard. Changing the numbers is 70b.
- **The 27j forward ranking check.** Its rule is pre-registered; Out lines already
  settle `void_dnp`, and role-changed lines are graded as served. Not touched.
- **The API's per-game sort** (`slate_line_rank`), which ignores injury. The web
  re-orders every surface a user sees; changing the API order changes no screen.
- **27h**, still unbuilt; when it is, it must exclude `role_changed` lines (noted
  in Notes for the AI).
- **Cross-position role changes.** A starting QB Out (2026 week 10: Kyler Murray)
  also blinds his receivers' projections, but no depth rank moves for them, so this
  rule does not catch it. The game notes' QB-change panel (`nfl_qb_change`) already
  shows it. Guarding pass catchers on a QB change is a candidate for a later 70
  sub-item, decided after 70b shows how much a usage shift matters.
- **Doubtful or Questionable starters.** They may play, so neither the starter nor
  his backup is guarded.

## Build steps

- [x] **1. `role_changed` flag (API, pure).** In `api/app/core/nfl_availability.py`:
  `ROLE_CHANGED = "role_changed"`, added by `availability_flags` when
  `injury_status == "Out"`, or `active_depth_rank` and `depth_rank` are both set and
  differ. Week-over-week flags are unchanged. Tests in
  `api/tests/test_nfl_availability.py`.
  *Done when:* tests cover Out (with and without a chart row), a backup moved up
  (RB2 -> RB1), unchanged depth, and a Questionable starter (no flag).
- [x] **2. Line-level reference predicate (web, pure).** In
  `web/src/utils/nflAvailability.ts`: `isRoleChanged(row)` (the flag, or
  `injuryStatus === 'Out'`, or `depthShifted(row)`, so stored slates without the
  flag still guard) and `roleChangeNote(row)`; in `web/src/utils/nflTargets.ts`:
  `isReferenceLine(row)`. Tests beside each.
  *Done when:* tests cover the flag alone, Out without the flag, a shifted depth
  without the flag, a healthy line, and a Targets line.
- [x] **3. No pick on cards and the detail panel.** Switch the row-level sites in
  `nflPropCards.ts`, `nflPropDetail.ts`, `nflSignal.ts`, `nflSlate.ts:201-206` and
  `NflPlayerPropSection.tsx` to `isReferenceLine(row)`, and show
  `roleChangeNote(row)` where Targets shows its reference note.
  *Done when:* a card test gives Johnson's line `pickLabel '--'`, trust
  `Reference`, no P(over) text, and the note `Role changed: Walker out`; a healthy
  line is unchanged.
- [x] **4. Out of every top-N.** `isRateable` (`nflPropBoard.ts:99`) returns false
  for a role-changed line, so it moves to the board's show-all list and
  `rankTopProps` never sees it. Update `nflSlate.test.ts:157-180`, which pins an Out
  line reappearing at limit 10.
  *Done when:* a digest test at limit 10 excludes both an Out line and a moved-up
  backup, and the board test lists them under show-all.
- [x] **5. Verify and check in the app.** Run Verify; then, on a local API and web,
  Johnson's rushing line reads as a gray reference with the note and no UNDER, and
  is absent from the game strip and prop-board digest.
  *Done when:* Verify passes and a screenshot shows the reference line.

## Testing

- API: `availability_flags` cases (step 1). Pure, no DB.
- Web: predicates, card, detail and digest helpers (steps 2-4), with fixed rows; no
  component tests, per the standards.

## Notes for the AI

- `availability_flags`' docstring says flags never change a projection, an edge,
  or the ranking; keep that true. `role_changed` gates display and selection only.
- Frozen prop predictions copy `quality_flags` (`prop_predictions.py:24`), so
  frozen rows will start carrying `role_changed`. Metadata only: no check reads it.
- Old stored slates lack the flag and possibly `activeDepthRank`; the web
  predicate falls back to `injuryStatus === 'Out'` and `depthShifted`.
- When 27h is built, it must skip `role_changed` lines; add that to its spec.
- Keep gray signal colors: a reference line uses the existing Targets reference
  styling, never a new color.

## Findings

### 70a/F-49 [P2] closed - Tennis prop enrichment engine lives in a router, and an ingest imports it

**File:** api/app/routers/props.py:72-575; api/app/routers/props.py:552; api/app/ingest/prop_snapshots.py:25
**Found:** 2026-11-15 by /audit (scope: full; lens: quality)
**Why it matters:** about 500 lines of projection and enrichment logic (`_enrich` alone runs 233-481) sit in a router, against the thin-router rule. `prop_snapshots` imports `enrich_with` from `app.routers.props`, so an ingest depends on the HTTP layer, and 12 test files import router privates. The comment at :552 defers the move "to item 17", which is checked off, so the deferral is stale.
**Suggested fix:** move lines 72-575 verbatim into `services/tennis/prop_enrichment.py` (pure helpers such as `_deciding_set_probability` may go to `core/`), re-point the ingest and tests, and leave the four endpoints in the router. Ingest and page must keep sharing one function so the props-v3 snapshots stay identical to what the page serves.
**Resolution:** Fixed in PR #42 (`1de17587`, 2026-11-17): lines 72-575 moved verbatim into `services/tennis/prop_enrichment.py`; the router keeps its endpoints, and `prop_snapshots` and the tests import from the service, so ingest and page still share one function. Full API suite 6441 passed. Not yet re-reviewed. Re-reviewed 2026-11-18 by /audit (scope: fix commits; lens: quality): the router is endpoints only, the ingest imports the service, and the moved bodies are byte-identical apart from two renames, so props-v3 is unaffected. Closed.

### 70a/F-52 [P2] invalid - NFL finished-week and coverage rules differ from NBA and NHL

**File:** api/app/repositories/nfl.py:2612; api/app/repositories/nba.py:707; api/app/repositories/nhl.py:759
**Found:** 2026-11-15 by /audit (scope: full; lens: quality)
**Why it matters:** NFL `get_finished_weeks` requires `bool_and(g.status = 'completed')`, while NBA and NHL also accept postponed and canceled games, so a canceled NFL game would keep its week open and out of the ranking record. NFL's coverage `EXISTS` also matches `fl.market = latest.market` and NBA/NHL do not. Either difference may be deliberate.
**Suggested fix:** confirm which rule each sport should have. Fix or comment the one that is not deliberate before F-51 merges them.
**Resolution:** Invalid as a defect, both differences deliberate (user chose option A, 2026-11-18; `blueprint/history/fixes/nfl-finished-week-rule.md`). The only NFL `sport_games` writer, `upsert_game` (`nfl.py:425`), stores `completed` or `scheduled`, never `postponed` or `canceled`, so the stricter finished-week rule picks the same weeks NBA's would. The coverage `fl.market = latest.market` came with 39c (`4b79aa00`) so a Rec Targets freeze on the same provider prop never counts as v4 coverage; F-51 must keep it as an NFL predicate. Both now carry a why-comment; no SQL changed. Possible follow-up: teach the nflverse ingest postponed and canceled statuses, then relax the NFL rule to match.

### 70a/F-53 [P2] closed - NBA and NHL `upsert_games` conflict rules differ

**File:** api/app/repositories/nba.py:89-99; api/app/repositories/nhl.py:82-94
**Found:** 2026-11-15 by /audit (scope: full; lens: quality)
**Why it matters:** NBA keeps a known start time (`COALESCE(EXCLUDED.start_utc, sport_games.start_utc)`) and never updates `season`. NHL overwrites `start_utc`, so a feed row with no time can null a known one, and does update `season`. `_chunks`, `_ids_by_source`, `upsert_team` and `get_player_candidates` are otherwise word-for-word copies with only the sport literal changed.
**Suggested fix:** decide the right conflict rule and comment any deliberate difference. Then move the shared helpers into a `repositories/sport_common.py` that takes `sport` as a required argument.
**Resolution:** Fixed 2026-11-18 (user chose option A; `blueprint/history/fixes/nhl-upsert-games-conflict.md`): NHL `upsert_games` now uses NBA's rule, `start_utc = COALESCE(EXCLUDED.start_utc, sport_games.start_utc)` and no `season` update on conflict, keeping its `end_period` refresh. No behaviour change today: the NHL ingest always supplies a start time and derives season from the game id. `tests/test_nhl_games_repository.py` pins the clause. Re-reviewed 2026-11-18 by an independent reviewer: confirmed. Closed. Remaining work, not done here: move `_chunks`, `_ids_by_source`, `upsert_team` and `get_player_candidates` into `repositories/sport_common.py` with `sport` required.

### 70a/F-55 [P2] closed - The three Odds-API.io quota gates disagree when the balance is unknown

**File:** api/app/ingest/odds_api.py:88-106; api/app/ingest/nfl_odds_io.py:44-46; api/app/ingest/nhl_odds_io.py:101-110
**Found:** 2026-11-15 by /audit (scope: full; lens: quality)
**Why it matters:** the three scripts share one hourly request bucket. NFL and NHL refuse to request when `remaining is None` ("unknown balance stops the run: tennis shares the hour"), but tennis `_quota_too_low` returns False on None and keeps spending. NHL also discards header values outside 0-100. That makes three header parsers and three gates for one provider.
**Suggested fix:** decide the unknown-balance policy on purpose, then add one shared Odds-API.io helper (`remaining(headers)`, `can_request(remaining, floor)`) used by all three.
**Resolution:** Fixed 2026-11-18 (user chose option A; `blueprint/history/fixes/odds-api-io-unknown-balance.md`): unknown means stop for all three. New pure `app/core/odds_api_io_quota.py` (`remaining_requests(headers)`, `can_request(balance, floor)`) replaces the three parsers and gates; NHL's 0-100 range is kept on purpose as `HOURLY_ALLOWANCE = 100`, the shared plan's hourly allowance, so a value outside it reads as unknown everywhere. Visible change: tennis now stops and logs `request balance unknown` instead of spending; NFL also stops on a header above 100. Tests cover the helper and the tennis gate. Re-reviewed 2026-11-18 by an independent reviewer: confirmed. Closed.

### 70a/F-59 [P2] closed - Web game-status labels are reimplemented five times, and the copies have drifted

**File:** web/src/utils/gameState.ts:16-26; web/src/utils/nhlGame.ts:36-46; web/src/utils/nbaSlate.ts:68-74; web/src/utils/nbaPropBoard.ts:35-41; web/src/utils/nhlPropBoard.ts:55-60
**Found:** 2026-11-15 by /audit (scope: full; lens: quality)
**Why it matters:** `gameState` lowercases the status, accepts `cancelled` and shows "Result pending" for a long-started game with no final. The board copies skip both, so an old game with no stored final reads "Tipped off" or "Started". The NHL final label is "Final / OT" in one file and "Final/OT" in another.
**Suggested fix:** have the slate and board helpers call `gameState()` (with an optional per-sport started label) and drop the local terminal maps.
**Resolution:** Fixed in `6d5b298b` (2026-11-16; pushed to master 2026-11-18): `gameState()` takes a per-sport started label, and the NHL and NBA slate cards and the NBA and NHL props boards route through it. Approved visible changes: `Final/OT` on NHL cards, `Result pending` on the boards, case-insensitive and `cancelled` statuses. Spec in `blueprint/history/fixes/web-game-status.md`. Not yet re-reviewed. Re-reviewed 2026-11-18 by /audit (scope: fix commits; lens: quality): all four listed copies route through `gameState()`, and the visible changes match the approved list. A separate NFL slate copy is logged as F-76. Closed.

### 70a/F-60 [P2] closed - Signed-number and percent formatting is reimplemented about 20 times with different zero handling

**File:** web/src/utils/nflSignal.ts:13-18; web/src/utils/gapUnits.ts:7; web/src/utils/nbaProps.ts:83-85; web/src/utils/propRowVisuals.ts:90-92; web/src/utils/nhlGame.ts:61-62; web/src/utils/calculators.ts:148-162; web/src/utils/odds.ts:16
**Found:** 2026-11-15 by /audit (scope: full; lens: quality)
**Why it matters:** some copies round before choosing the sign and some do not, so `edgeLabel(-0.04)` shows "-0.0" while others show "0.0". `(x * 100).toFixed(1)}%` appears 53 times beside `fmtPct`, and 9 components define a local `pct`. The null placeholder is an em dash character in `odds.ts` and "--" in NFL/NHL utils.
**Suggested fix:** add `fmtSigned(value, decimals, suffix?)` to `format.ts` (round, then sign, normalize -0), use it and `fmtPct` everywhere, and pick one placeholder constant. Changing visible output (placeholder, -0.0) is a UI decision, so make it explicitly.
**Resolution:** Fixed in `dd5c3d9c` (2026-11-16; pushed to master 2026-11-18): `fmtSigned` in `utils/format.ts` (round, then sign, normalise -0) replaces the signed-number copies, and the local `pct` helpers use `fmtPct`, which now takes a placeholder. Each page keeps its current missing-value text by decision. Spec in `blueprint/history/fixes/web-formatting.md`. Not yet re-reviewed. Re-reviewed 2026-11-18 by /audit (scope: fix commits; lens: quality): `fmtSigned` rounds before signing and normalises -0, no hand-signed copy remains, and the nine `pct` helpers use `fmtPct`. Whole-percent copies and pass-through wrappers are logged as F-77. Closed.

### 70a/F-61 [P2] closed - Moneyline pick generation is duplicated between best picks and the bankroll builder

**File:** api/app/services/tennis/best_picks.py:101-176; api/app/services/tennis/bankroll_builder.py:138-193; api/app/services/tennis/bankroll_builder.py:34
**Found:** 2026-11-15 by /audit (scope: full; lens: quality)
**Why it matters:** both compute EV, Kelly, the devig, the bettable assessment and the reasoning text. The edge formulas already differ (`/ market_prob` vs `/ max(mkt_p or our_p, 0.01)`). `bankroll_builder` imports privates `_compute_stat_avg` and `_CONF_MULT` from `best_picks`, and both read a declared field through `getattr(pred, "quality_flags", [])`.
**Suggested fix:** extract one pure `moneyline_sides(pred)` that both shape from, choose one edge formula on purpose (or document why they differ), import `compute_stat_avg` from core and make `_CONF_MULT` public.
**Resolution:** Fixed in PR #44 (`d00d2489`, 2026-11-17): one pure `moneyline_sides(pred)` in `services/tennis/moneyline.py` feeds both callers; each keeps its own edge formula and output, pinned by golden tests written on the old code. `compute_stat_avg` comes from core, `CONF_MULT` is public, and both read `pred.quality_flags or []`. Full API suite 6488 passed. Not yet re-reviewed. Re-reviewed 2026-11-18 by /audit (scope: fix commits; lens: quality): one `moneyline_sides` feeds both callers, both edge formulas are kept on purpose, and the golden tests pin the old outputs. Closed.

### 70a/F-66 [P2] closed - Admin flagged-player logic sits in the router, and the admin page renders its panels twice

**File:** api/app/routers/admin.py:48-139; web/src/pages/AdminPage.tsx:310-410; web/src/pages/AdminPage.tsx:544-780
**Found:** 2026-11-15 by /audit (scope: full; lens: quality)
**Why it matters:** about 90 lines of the router run predictions, join ELO and stats and refine flags, using function-local imports and the private `app.ingest.player_stats._slug`. On the web, the Fix Stats, Fetch ELO and Set ELO panels are written once for mobile and once for desktop, including the same `SetEloRequest` payload build (:397-405 and :761-769).
**Suggested fix:** move the flag logic into `services/tennis/flagged_players.py` and make `_slug` public. Extract the three panels and a tested `buildSetEloPayload` in `~/utils/adminFlags` so both layouts share them.
**Resolution:** Fixed: the web part landed in `cefc83cb` (pushed 2026-11-18); the API part in PR #43 (`ad464fc0`, 2026-11-17) moved the flag logic into `services/tennis/flagged_players.py` and the slug into a public `core/ta_slug.py`, pinned by a golden test of the old response. Full API suite 6460 passed. Not yet re-reviewed. Re-reviewed 2026-11-18 by /audit (scope: fix commits; lens: quality): the defect is gone in both apps (one service call in the router, each repair panel rendered once, payload builders tested). Kept `fixed`: the repair left two comments naming the old `_slug` (`api/app/routers/admin.py:87`, `api/app/schemas/admin.py:26`); rename them to `ta_slug` and drop the em dashes in `core/ta_slug.py:8`, then close. Repaired on `fix/ta-slug-comments` (2026-11-18): the two comments now name `ta_slug` (`api/app/routers/admin.py:87`, `api/app/schemas/admin.py:26`) and match the code (`flagged_players.py:123`, `player_stats.py:199`), and the em dashes and arrows in `core/ta_slug.py` and `ingest/player_stats.py:650` are gone. Re-reviewed 2026-11-18 by /audit (scope: fix diff; lens: quality): no `_slug(` reference is left in `api/app`, and the diff is comments only. API suite 6553 passed. Closed.

### 70a/F-67 [P2] closed - The NHL board-to-player link drops the return path that NBA and NFL have

**File:** web/src/components/nhl/NhlPropBoardMarket.tsx:39; web/src/pages/NhlPlayerPage.tsx:33-37
**Found:** 2026-11-15 by /audit (scope: full; lens: quality)
**Why it matters:** NBA and NFL pass `FROM_BOARD` state and their player crumb goes back to the board. `arrivedFromBoard` appears only in the NBA and NFL pages, so an NHL user opening a player from the board loses the board's filters on the way back. This is a consistency gap from copying per sport.
**Suggested fix:** pass `state={FROM_BOARD}` on the NHL board link and add the same crumb branch to `NhlPlayerPage`.
**Resolution:** Fixed in `86d381cd` (2026-11-16; pushed to master 2026-11-18): the NHL board link passes `FROM_BOARD`, and `NhlPlayerPage` shows the NBA-style `<- NHL props` crumb back to the board (approved visible change). Spec in `blueprint/history/fixes/web-player-pages.md`. Not yet re-reviewed. Re-reviewed 2026-11-18 by /audit (scope: fix commits; lens: quality): the NHL board link passes `FROM_BOARD` and the crumb returns to the board; the game-page link is unchanged. The now-duplicated crumb is logged as F-79. Closed.

### 70a/F-68 [P2] closed - Per-sport hook files follow two different patterns

**File:** web/src/hooks/useNhl.ts; web/src/hooks/useNba.ts:37-77; web/src/hooks/useNfl.ts:8-72; web/src/hooks/useModelTrackRecord.ts:6; web/src/hooks/useNflModelTrackRecord.ts:7
**Found:** 2026-11-15 by /audit (scope: full; lens: quality)
**Why it matters:** NHL uses `queryOptions` with `skipToken` and normalizes the slate date. NBA and NFL use `enabled` with 10 `gameId as number` casts, and the NBA slate key uses the raw date, so one slate can get two cache entries. `useNbaModelRanking` and `useNhlModelRanking` are identical, and the track-record stale time is declared twice.
**Suggested fix:** move NBA and NFL to the NHL pattern, add a shared model-ranking hook helper and export the stale constants from one place.
**Resolution:** Fixed in `030ef1b8` (2026-11-16; pushed to master 2026-11-18): NBA and NFL hooks use the NHL `queryOptions` and `skipToken` pattern with no `gameId` casts, the NBA slate key normalises its date, the model-ranking hooks share one helper, and the stale times are exported once. Spec in `blueprint/history/fixes/web-hooks.md`. Not yet re-reviewed. Re-reviewed 2026-11-18 by /audit (scope: fix commits; lens: quality): `useNba.ts` and `useNfl.ts` have no casts or `enabled` options, the NBA slate key is normalised, ranking hooks share one query and stale times live in `queryTimes.ts`. The three track-record hooks still on the old pattern are logged as F-78. Closed.

### 70a/F-69 [P2] closed - Near-copy sport components and board utils

**File:** web/src/components/nhl/NhlGameProps.tsx:15-58; web/src/components/nhl/NhlPropBoardMarket.tsx:13-53; web/src/components/nhl/NhlPlayerProjectionHistory.tsx; web/src/components/tennis/player/PlayerProjectionHistory.tsx; web/src/utils/nbaPropBoard.ts:22-80; web/src/utils/nhlPropBoard.ts:20-53
**Found:** 2026-11-15 by /audit (scope: full; lens: quality)
**Why it matters:** the NHL game and board prop tables repeat columns, caption and an `alternates()` helper, but differ in how they show alternates and in the ring and "Updated" columns. The NHL and tennis projection-history sections are the same structure with local `shortDate` and footnote copies. The NBA and NHL board utils share start-time sort, comparator and path builders but differ on the default market (NBA falls back to points even when empty).
**Suggested fix:** move `alternates` and the caption into `~/utils/nhlProjection` and share one table with optional columns. Add one `ProjectionHistorySection` with a sport adapter. Put the board sort, comparator and path in a shared util and choose one default-market rule on purpose.
**Resolution:** Fixed in `9e248092` (2026-11-16; pushed to master 2026-11-18): `nhlAlternateLabels` and `nhlProbabilityCaption` serve both NHL tables, `ProjectionHistorySection` with `historyFootnote` serves NHL and tennis, and `utils/propBoardRows.ts` holds the shared board sort and path. Each sport keeps its default-market rule by decision. Spec in `blueprint/history/fixes/web-shared-props.md`. Not yet re-reviewed. Re-reviewed 2026-11-18 by /audit (scope: fix commits; lens: quality): no `alternates()` copy is left, both history sections are adapters over `ProjectionHistorySection`, and the board sort and path live in `propBoardRows.ts`. Closed.

### 70a/F-70 [P2] closed - `ParlaysPage` is an 802-line legacy page outside the shared page patterns

**File:** web/src/pages/ParlaysPage.tsx:37-640; web/src/pages/ParlaysPage.tsx:655-690
**Found:** 2026-11-15 by /audit (scope: full; lens: quality)
**Why it matters:** seven subcomponents are defined in the page, it builds its own `<h1>` with an eyebrow instead of `PageHead`, it uses `onMouseEnter`/`onMouseLeave` style mutation for hover, and it has banner-divider comments. `SinglePickRow` (:80) and `SinglePickCard` (:377) show the same data in two layouts.
**Suggested fix:** switch to `PageHead`, move the subcomponents into `components/tennis/parlays/`, and replace hover handlers with CSS classes.
**Resolution:** Fixed in `31d92b68` (2026-11-16; pushed to master 2026-11-18): the page uses `PageHead`, its subcomponents moved under `components/tennis/parlays/`, and hover handlers became CSS classes. Spec in `blueprint/history/fixes/web-parlays-page.md`. Not yet re-reviewed. Re-reviewed 2026-11-18 by /audit (scope: fix commits; lens: quality): reopened. `PageHead`, the moved subcomponents and the CSS hover landed, but banner comments remain at `web/src/pages/ParlaysPage.tsx:87,97,108` with narration comments at `:37,81,119`, an empty fragment at `:38-79` and an IIFE in the JSX at `:88-132`. The moved `SinglePickRow.tsx:25-50` and `SinglePickCard.tsx:17-60` carry what-comments. Delete the comments and fragment and compute the four lists before `return`. Repaired on `fix/parlays-page-cleanup` (2026-11-18): a tested `splitByTour` in `utils/bankrollTours.ts` replaces the JSX IIFE, and the empty fragment and every what-comment in the page and the five parlay components are gone. Re-reviewed 2026-11-18 by /audit (scope: fix diff; lens: quality): section filtering is unchanged, and `SinglePickRow` and `SinglePickCard` are the wide and narrow layouts `TourSection` chooses between, not a duplicate. Verify passed and the page renders as before. Closed.

### 70a/F-76 [P3] closed - The NFL slate keeps its own case-sensitive game-status rule

**File:** web/src/utils/nflSlate.ts:264-268; web/src/pages/NflIntelligencePage.tsx:33
**Found:** 2026-11-18 by /audit (scope: fix commits; lens: quality)
**Why it matters:** `rowState` checks `game.status === 'completed'` and has no postponed or canceled branch, so a postponed NFL game reads as live or pending while the other sports read it through `gameState()`. Smaller case-sensitive `=== 'completed'` counts remain in `homeSources.ts:152,197`, `nbaSlate.ts:186`, `nflSlate.ts:110` and `nhlSlate.ts:104`.
**Suggested fix:** Map `gameState()` phases in `rowState`, handling the `off` phase, and use the same lowercase check in the counts.
**Resolution:** Repaired on `claude/fix-nfl-slate-status-a58bad` (2026-11-18): `rowState` returns the `gameState()` phase with NFL's labels (`Live`, `Result pending`, `Final`), so a postponed or canceled game reads as `off` with its label, no market lines and no pre-game tags, and the page's `STATE_LABEL` map gives way to the row's `stateLabel`. The finals counts in the NFL, NBA and NHL slate summaries and the home page's schedule and moneyline filters use the new `isFinalStatus`. Visible change, listed in the spec for the user's approval at merge: postponed and canceled NFL games show as such, and a final stored in another case counts as one. Spec in `blueprint/history/fixes/nfl-slate-status.md`. Re-reviewed 2026-11-18 by an independent review of the diff: no case-sensitive status check remains, and upcoming, live, pending and final rows are unchanged. Web Verify passed (1859 tests) and the API tests passed (6553). Closed.

### 70a/F-77 [P3] closed - Whole-percent and pass-through percent formatters beside `fmtPct`

**File:** web/src/utils/nbaProps.ts:74; web/src/utils/nflSignal.ts:44; web/src/utils/nflVolume.ts:21; web/src/utils/boardRecord.ts:105; web/src/components/tennis/TennisSlateTable.tsx:72; web/src/utils/homeSources.ts:188
**Found:** 2026-11-18 by /audit (scope: fix commits; lens: quality)
**Why it matters:** About 13 sites hand-roll `${Math.round(x * 100)}%` (three as local `percent()` helpers) instead of `fmtPct(x, 0)`. `boardRecord.ts` `percent` and `TennisSlateTable.tsx` `pct` only forward to `fmtPct`. `homeSources.ts:188` hard-codes a `+` on the gap.
**Suggested fix:** Use `fmtPct(x, 0)` and `fmtSigned(diff * 100, 1, ' pp')` directly and delete the wrappers. Output is unchanged for probabilities.
**Resolution:** Repaired on `claude/fix-percent-formatters-93ec2a` (2026-11-18): every whole-percent copy and the three `percent()` helpers use `fmtPct(x, 0)`, the `boardRecord.ts` and `TennisSlateTable.tsx` wrappers are gone, and the moneyline gap uses `fmtSigned(diff * 100, 1, ' pp')`. Output is unchanged for every value these sites receive (all non-negative, each guards null), except a gap that rounds to zero now shows `0.0 pp` by the F-60 zero rule. Left alone on purpose: `nbaSlate.ts` `winBar`, `nhlProjection.ts` `nhlPercentLabel`, the `trackRecord.ts` range and three `points`/`pts` labels. Spec in `blueprint/history/fixes/percent-formatters.md`. Verify passed. Re-reviewed 2026-11-18 by an independent subagent (scope: fix diff; lens: quality): same text at every site, no copy or wrapper left, nothing new. Closed.

### 70a/F-78 [P3] closed - NFL model track-record hooks still use `enabled` with `season as number`

**File:** web/src/hooks/useNflModelTrackRecord.ts:8-31
**Found:** 2026-11-18 by /audit (scope: fix commits; lens: quality)
**Why it matters:** Three hooks keep the `enabled: season !== null` plus `season as number` pattern that F-68 removed from the other NBA and NFL hooks. `useNba.ts:9` and `useNhl.ts:69` also gate a disabled slate two different ways.
**Suggested fix:** Move the three hooks to `queryOptions` with `skipToken`, as in `useNfl.ts`, and pick one disabled-slate idiom.
**Resolution:** Repaired on `fix/nfl-track-record-hooks` (2026-11-18): the three hooks build `queryOptions` with `skipToken` for a null season, and `nhlSlateQuery(date, enabled)` gates a waiting slate through `skipToken` as `nbaSlateQuery` does, so `useNhlSlate` no longer spreads `enabled`. Tests cover the idle null season, the unchanged cache keys and the gated NHL slate. Re-reviewed 2026-11-18 by /audit (scope: fix diff; lens: quality): keys, stale times, retry and fetch arguments are unchanged, and no caller refetches a gated slate. Verify passed, and in the app the NFL model page fires each track-record request once and the NHL game page waits for its date before loading the slate. Closed.

### 70a/F-79 [P3] closed - The NBA and NHL board crumbs are near-identical copies

**File:** web/src/pages/NbaPlayerPage.tsx:33-42; web/src/pages/NhlPlayerPage.tsx:34-42
**Found:** 2026-11-18 by /audit (scope: fix commits; lens: quality)
**Why it matters:** F-67 copied the NBA crumb into the NHL page, so the per-sport copying the finding named now covers the crumb. Both call `useLocation()` inside an `if` condition, which reads like a conditional hook.
**Suggested fix:** A shared `BoardCrumb({ boardPath, label })` in `components/shared`, with `useLocation()` hoisted to a `const` as `NflPlayerPage.tsx:66` does.
**Resolution:** Fixed on `claude/fix-board-crumb-f57805` (2026-11-18): a shared `BoardCrumb({ boardPath, label, fallback })` in `components/shared` calls `useLocation()` once at the top, and the NBA, NHL and NFL player pages use it, each passing its own game or slate fallback. No visible change. Spec in `blueprint/history/fixes/web-board-crumb.md`. Re-reviewed 2026-11-18 by an independent reviewer (scope: fix diff; lens: quality): the board branch lives only in `BoardCrumb`, no page calls `useLocation()`, and hrefs, labels, back navigation and fallbacks match the previous code on all three pages. Verify passed. Closed.

# Tennis match research, picks tabs, and navigation

**Type:** Fix

## The problem

Clicking a tennis slate row opens an inline detail section, requiring another
click to reach full analysis. That section fetches ELO through a rolling-stats
endpoint that returns null when rolling stats are absent, even if ELO exists.
This coupling is confirmed in code; it has not yet been established as the
specific reason the owner saw missing ELO for Nakashima versus Jacquet.

A read-only shared-database query on 2026-10-22 confirmed match 91823,
Brandon Nakashima versus Kyrian Jacquet, is stored as Clay, indoor, for Lyon
tournament 14767. Both players have TennisAbstract ELO dated 2026-10-19:
Hard ELO 1868.0 and 1682.0 respectively. The existing ingest override maps
14767 and qualifying event 14763 to Hard, indoor. The prior correction only
covered matches through October 21. The writer responsible for this new
incorrect row and its deployed revision remain unverified.

## The fix

Open `/tennis/match/:id` directly from slate rows with a canonical match ID.
Use a real link for keyboard access and normal modified-click behavior.
Update digest selection consistently so it no longer depends on opening an
inline panel for these matches. Preserve useful details for prop-only rows
without a canonical match ID; never link those to a fabricated match.

Use the full analysis page's independent ELO lookup. Check the reported
match's detail response and rendered ratings before adding any backend fix.
Keep raw player ratings distinct from the slate's ELO win probabilities.
Do not change model weights, reliability rules, served ELO source, or picks.

Trace the current ingest revision and existing Lyon override. Prepare a
bounded correction of the affected Lyon rows, with before/after evidence.
Do not modify frozen predictions, prop snapshots, or shadow experiment evidence.
Merge, push, deployment, and remote workflow dispatch remain separate actions.

### Owner-approved scope extension: match tabs (2026-10-22)

Add Analysis and Picks & Props tabs to full match analysis, following the existing
NFL game-page tab styling and interaction pattern. Keep the match header and
Back link above both tabs. Analysis is the default for match links. These are
the owner's approved final labels; Overview/Props below describe their roles.

- Overview retains the prediction, ELO components, recent form, head-to-head,
  odds movement, books, and serve/return context.
- Props contains the match's available best picks alongside its prop lines,
  using existing eligibility and signal rules. Distinguish no picks,
  unavailable picks, and loading/errors. Do not generate current picks for a
  finished match or present a newly computed prediction as its historical pick.
  It gets a full-width table of all available lines canonically linked to
  that match, including PASS, line-only, and alternate lines. Reuse the existing
  tennis prop table, evidence drawer, display calculations, and source access
  rules. Default to PrizePicks, matching the current match-page source; retain
  supported owner-only source choices if reusing that board exposes them.
- Allow both-player or individual-player filtering and market filtering. Show
  lines, projections, available probabilities, and confidence using existing
  labels, missing-value handling, and gray/green rules. An empty match must
  not fall back to other matches' props. Historical matches may have no current
  provider lines; describe availability honestly without promising an archive.
- A prop entry with a canonical match ID opens that match's Props tab with
  the selected line/player/market identified. Match links still open Overview;
  unlinked props retain their existing useful fallback. Use URL query state
  for shareable tab and selection links, and browser Back/Forward behavior.
- Remove the long prop list from the Overview sidebar; use a concise link
  to the match's Props tab. Preserve the existing slate navigation fix.

This extends the current uncommitted fix on `fix/tennis-direct-analysis`;
preserve its code, surface repair, scheduled-copy patch, and evidence. No new
model, provider request, schema change, scoring, or deployment is included.

### Requested scope extension: four matchup context panels (2026-10-22)

On the tennis match's Analysis tab, add surface-specific stats with sample
sizes, recent workload, first/second serve-versus-return comparisons, and
input freshness. These are descriptive research context. Keep all match picks
and prop lines on Picks & Props. Preserve pending step 4's direct prop-entry
and URL-state work rather than replacing it with this extension.

Inspected implementation already stores `player_rolling_stats` surface rows,
`matches_count`, `computed_at`, `first_in_pct`, `first_won_pct`,
`second_won_pct`, opponent-allowed first/second-serve percentages, and
`PlayerElo.as_of_date`. Odds rows already have `fetched_at`. The current
match/recent-form responses do not expose all these inputs. Tennis match
duration is not present in the inspected storage. No new source or ingest is
required for this initial version; unavailable minutes stay unavailable.

- **Surface context:** compare both players on the actual match surface over
  the stored last-52-week window, with win rate, hold rate, return points won,
  break conversion rate, and sample size. Label break conversion accurately;
  it is not return games won. Indoor hard uses Hard stats; do not label these
  as an indoor-only sample. Keep small surface samples visible with a neutral
  thin-sample note below the existing 10-match floor. If an overall comparison
  is offered, label it explicitly; never silently substitute it for surface
  stats. Show W-L only if exact, deduplicated counts are available from an
  authoritative stored source; never reconstruct counts from rounded win rate.
- **Workload:** for each player, show the previous match date, calendar days
  since that match, matches and sets played in the seven days before the target
  match. Use canonical match IDs and actual match dates, not box-score rows
  dated by tournament start. Exclude the target and future matches. Without
  reliable end times, label calendar days rather than claiming hours of rest.
  Include same-day matches only if their order is provable from stored data;
  otherwise disclose the exclusion. Walkovers/cancellations add no workload;
  retirement or unparseable scores must not become invented complete-set
  totals. Show score coverage/partial totals when needed. Minutes played is
  explicitly unavailable until verified duration data exists.
- **Serve versus return:** show first serves in, first-serve points won, and
  second-serve points won, beside the opponent's first/second-serve return
  points won. Return percentages can be derived as one minus the corresponding
  opponent-serve-points-won allowed percentage, only when the stored value
  exists and lies within 0..1. Keep denominators, surface/window, sample sizes,
  and missing inputs clear. Do not multiply these rates into a new projection
  or imply that a descriptive comparison has passed model validation.
- **Freshness:** show per-player ELO rating date, per-player statistics refresh
  time, and latest available odds timestamps per book, with source/window
  labels. Label times in CT consistently. Distinguish rating date, stats fetch
  time, and the period the stats cover. Missing timestamps say unavailable.
  Reuse established freshness rules where they exist; do not invent one stale
  threshold for all feeds. Live model-generation time is shown only if known.

Extend the existing match-detail contract through typed schemas, repository
queries, service orchestration, hooks, and frontend types. Keep queries bounded
to the two players and required windows, and avoid heavy request-time reports
on the 512 MB API. Current rolling snapshots must be labeled as current when
viewing a finished match. Do not claim historical pre-match availability unless
an actual as-of snapshot supports it. Workload remains cut off at the match.
No frozen prediction, model input, coefficient, prop ranking, ELO source,
experiment evidence, database schema, provider ingestion, or deployment changes.

## Build steps

- [x] **1. Direct analysis navigation and ELO verification.** Create
  `fix/tennis-direct-analysis`, update slate and digest navigation, and remove
  obsolete expansion state only where no longer needed. Inspect the detail
  API and UI for match 91823. Repair an ELO display defect only if reproduced.
  **Done when:** clicking or keyboard-activating the match opens full analysis,
  modified link clicks work, browser Back returns to the slate, prop-only rows
  remain usable, and both existing player ratings are visible on full analysis.
- [x] **2. Lyon surface consistency.** Identify the ingest writer/revision
  mismatch or other evidenced cause; preserve the event-ID-specific override
  and its regression coverage. Prepare and apply the reviewed bounded data
  correction within the owner's authorized scope.
  **Done when:** match 91823 and affected rows in events 14767/14763 show
  Hard, indoor; non-target rows and frozen evidence are unchanged. Report any
  publication step still required to prevent recurrence on remote runs.
- [x] **3. Match Overview and Props tabs.** Reuse NFL's tab presentation and
  tennis's existing prop table/evidence components; split the match content,
  add player/market filters, and include available match picks on Props.
  Add focused tests for match scoping, filter logic, and finished-match rules
  where new pure logic is introduced.
  **Done when:** Overview is the default, both tabs keep the match header,
  Props shows all available linked lines without unrelated matches, filters
  work together, evidence opens, unavailable values remain explicit, and
  empty/error/finished cases are usable at desktop and mobile widths.
- [x] **4. Direct prop entry and tab navigation.** Wire canonical prop links
  to the match's Props tab and selected line, retaining safe unlinked fallbacks.
  **Done when:** a prop link opens the correct match and selection, direct
  URLs/reloads and Back/Forward preserve tab/filter state, ordinary match
  links open Overview, and keyboard tab controls and narrow-screen layout
  work. Invalid or stale selection parameters cannot show another match's line.
- [x] **5. Typed matchup context data.** Extend the match-detail response with
  surface/serve stats and samples, timestamp provenance, and bounded recent
  workload. Keep SQL in repositories and parsing/derivations in pure helpers.
  Add focused tests for missing data, actual surface versus explicit overall
  data, source duplication, workload cutoff, score coverage, and date handling.
  **Done when:** the API returns both players' available inputs with honest
  source/time/window labels; unknown minutes and missing metrics are null,
  target/future/walkover matches do not inflate workload, and finished matches
  never masquerade current snapshots as pre-match stats.
- [x] **6. Surface and serve/return panels.** Add side-by-side comparisons to
  Analysis using existing typography and neutral signals. Include samples,
  thin-sample notes, first/second-serve metrics, and explicit missing states.
  **Done when:** hard-court match 91823 uses Hard inputs, both players are
  easy to compare on desktop/mobile, return conversions use the correct
  opponent-allowed denominator, and no new pick or ranking signal is created.
- [x] **7. Workload and freshness panels.** Show the date-anchored seven-day
  workload, calendar-day rest, set-count coverage, unavailable minutes, and
  per-source timestamps in CT on Analysis.
  **Done when:** known, missing, thin, partial, and historical states are clear;
  dates remain correct near UTC/CT day boundaries; all four requested panels
  are visible and usable without moving picks off Picks & Props.

## Verify

### Step 7 evidence (implemented, awaiting final owner review)

- Owner approved step 6 and continuation to workload and freshness displays.
  Added `MatchWorkloadContext` and `MatchFreshness` to Analysis. All four
  requested research areas are implemented locally; match picks and prop lines
  remain on Picks & Props.
- Workload shows each player's date-anchored seven-day window, previous
  recorded match, calendar-day interval, recorded match count, completed-set
  total with score coverage, and unavailable minutes. Partial positive set
  counts are lower bounds; missing scores do not become zero sets. Notes
  disclose UTC match-date boundaries, excluded same-day matches, bounded
  previous-match lookup, and incomplete stored-history coverage.
- Freshness distinguishes source ELO rating dates, surface and overall stats
  refresh timestamps, known prediction generation timestamps, and per-book
  odds fetch timestamps. Date-only records retain source dates; aware
  timestamps render in CT. No fabricated live generation time or shared
  stale/fresh threshold was introduced. No model, pick, or ranking changes.
- Eighteen new date/coverage tests verify UTC/CT calendar boundaries, winter
  and summer offsets, spring daylight saving, explicit offsets, leap/invalid
  dates, missing/naive timestamps, complete versus partial sets, and unknown
  versus zero totals. Final Verify halves passed: 809 web tests, typecheck,
  production build, and 3,704 API tests. Existing bundle/deprecation warnings.
- Live browser check on 91823: workload matches 1/3, sets 3/At least 5,
  coverage 1 of 1 / 2 of 3; both players' previous match October 20; ELO
  rating date October 19; stats refreshes 12:05/12:08 PM CT; both book odds
  fetches 12:02 PM CT. Minutes and live-generation timestamp are unavailable.
- Missing-data browser fixture confirmed missing rating/stat/odds timestamps,
  unknown previous-match/rest, and unreadable set totals stay unavailable.
  Override removed and live cache restored by reload. Finished match 89084
  retained its pre-match workload window and stored-prediction label.
- Desktop workload and 390px mobile freshness screenshots inspected:
  `.playwright-mcp/tennis-workload-desktop.png` and
  `.playwright-mcp/tennis-freshness-mobile.png` in browser output. Tables and
  timestamp labels fit the viewport; no new page errors on the live check.
  Impeccable detector returned no findings. `git diff --check` passes.
- Updated the ignored, local-only employer interview guide with this verified
  research/navigation work and the scheduled-checkout surface incident. It
  explicitly distinguishes local verification from deployment and unobserved
  next-run acceptance. Never stage that guide.
- Existing F-09 (P3) and F-12 (P2) remain unverified; no open/fixed P0/P1.
  All implementation steps are built; step 7 remains unchecked until final
  owner review. Nothing committed, merged, pushed, or deployed in this step.

### Step 6 evidence (implemented, awaiting owner review)

- Owner approved step 5 and continuation to the surface/serve comparison UI.
  Added `MatchSurfaceContext` to Analysis after the model components. Two
  side-by-side tables show surface rates and first/second serve/return rates,
  with both player names, match samples, thin-sample notes, missing values,
  source/window labels, and current-snapshot caveats for finished matches.
- Match surface is the default; All surfaces is an explicit alternative.
  Indoor Hard uses Hard data with a note that indoor and outdoor matches are
  included. The existing sidebar's compact comparison is now explicitly
  labeled All-surface rates. No stat or recommendation was silently removed.
- `tennisResearch.ts` selects players by ID, checks the actual surface/window,
  and never fills absent surface stats from overall stats. Five tests cover
  reversed player order, thin samples, explicit overall selection, missing
  data, wrong surfaces/windows, and mislabeled overall inputs.
- Copy distinguishes break-point conversion from return games won, labels
  service/return point denominators, and explains that point-count samples
  are unavailable. No comparisons receive green/red advantage coloring or
  feed a model/projection/pick.
- Documented Verify halves passed: 791 web tests, typecheck, production
  build; 3,704 API tests. Existing bundle-size/deprecation warnings remain.
  `git diff --check` passes; Impeccable detector returned no findings.
- Browser evidence on match 91823: Hard samples 41 and 40; explicit overall
  samples 57 and 63; first-serve points won 78.6% and 75.4%; first-serve
  return points won 24.6% and 29.5%. Desktop and 390px mobile captures inspected:
  `.playwright-mcp/tennis-surface-context-desktop.png` and
  `.playwright-mcp/tennis-surface-context-mobile.png` in browser output.
  The mobile panel/table are 350px wide inside a 390px viewport, with no
  document overflow after resize settles. No new page errors in the live check.
- A browser-only response fixture showed one five-match thin sample and
  one missing surface sample, with no overall substitution. The route
  override was removed and the page reloaded to restore live samples. Actual
  finished match 89084 showed the explicit current-statistics warning.
- No backend source change, database write, commit, push, or deployment in
  this step. Existing findings and employer-guide claims remain unchanged.
  Step 7 (workload and freshness displays) remains unimplemented. Step 6's
  checkbox stays unchecked until owner review.

### Step 5 evidence (implemented, awaiting owner review)

- Owner approved step 4 and continuation to the data layer. Step 5 extends
  the existing match-detail API with an optional typed `research` object;
  the existing frontend detail hook now receives typed research data.
- New pure context helpers validate rate inputs, derive return-point rates,
  parse completed regulation/advantage sets conservatively, and summarize
  canonical workload with deduplication and score coverage. Unknown duration
  is null; match-tiebreak/unrecognized/retirement score tokens make totals
  partial rather than fabricating complete sets. Walkovers, defaults,
  cancellations, all-zero scores, target/future and same-day matches are excluded.
- New repository reads are scoped to the two players and a 365-day history
  window, with a seven-day workload summary. Workload explicitly uses UTC
  match dates, preserving their stored calendar-day meaning rather than
  silently converting date-only records to CT. All same-day records are
  excluded because start order does not prove completion before the target.
  Freshness timestamps remain aware UTC values for later CT formatting.
- Research service reuses the existing batch rolling-stat reader and already
  loaded ELO records. Actual surface snapshots and explicitly separate overall
  snapshots retain sample sizes, refresh times, thin-sample notes, and source
  labels. No silent surface fallback. W-L counts are not reconstructed from
  rounded win rates. Current snapshots are labeled as current even on a
  finished match; workload remains anchored before that match's date.
- Per-book freshness uses the latest stored row before scheduled start when
  known. No new source, migration, provider fetch, heavy report, model input,
  coefficient, pick, experiment evidence, or database write was added.
- Live API checks: match 91823 returned HTTP 200, Hard samples 41/40, ELO
  date October 19, current stats timestamps, and workload of 1/3 matches and
  3/5 completed sets (Jacquet: 2 of 3 scores complete). Minutes were null.
  Finished match 89084 returned HTTP 200 with its stored prediction and
  explicitly current research snapshots; no live re-prediction was introduced.
- Thirty new API tests cover score variants, unplayed/duplicate/cutoff rules,
  partial coverage, missing data, bounded reads, rate complements, separate
  surface/overall data, historical labels, and timestamp serialization.
  Final documented Verify halves: 3,704 API tests; 786 web tests, typecheck,
  and production build. Existing deprecation/bundle-size warnings remain.
- Source diff is limited to pure helpers, bounded repository reads, research
  service, existing match service/router/schema, frontend response types,
  and tests. Existing match-detail fixtures mock the new service boundary.
  `git diff --check` passes. No commit, push, deploy, or shared-data write.
- Steps 6 and 7 remain: the new research data is not yet rendered as panels.
  Step 5 remains unchecked until owner review. Existing findings and employer
  guide claims are unchanged by this unfinished display extension.

### Step 4 evidence (implemented, awaiting owner review)

- Owner's latest `/implement` invocation accepted step 3 and approved
  proceeding with the pending URL navigation and four-panel extension.
- `tennisMatchView.ts` parses validated tab/source/player/market/prop URL
  state, preserves unrelated query parameters, and creates canonical prop
  links. `useMatchView` shares this state between tabs and filters. Existing
  ordinary match links still open Analysis. Public readers cannot restore
  owner-source prop selections under a different source.
- Board player names and slate prop entries link directly to the match's
  Picks & Props tab. Board evidence retains its drawer and offers an explicit
  match link; unlinked rows keep their prior evidence fallback. Match-local
  rows keep their evidence controls without redundant self-links.
- The selected line is resolved only from the selected source's canonical
  match-linked rows after the current player and market filters. Unavailable
  selections show a clear message and Clear selection; no unrelated line
  is substituted. Filter changes clear the drawer selection.
- Seventeen new URL tests cover round trips, malformed/unsafe IDs, unknown
  players/tabs/markets, source authorization, history-state immutability,
  supported source aliases, and unlinked/synthetic-row fallbacks.
- Final documented Verify halves: `npm.cmd --prefix web run verify` passed
  typecheck, 786 tests, and production build; API venv pytest passed 3,674
  tests. Existing Vite bundle-size and Starlette deprecation warnings remain.
- Playwright: a real board link opened match 92174, player James Duckworth,
  market break_points_won, prop 322680, with evidence visible. Match 91823's
  selected Jacquet Aces prop 322546 survived reload; closing removed the prop
  parameter; Back reopened it and Forward closed it. Switching to Analysis
  and returning preserved the player and market filters.
- Cross-match test: requesting 91823's prop 322546 on finished match 89084
  showed the unavailable-selection notice and no evidence drawer. A final
  valid selection produced no new page errors or failed HTTP responses.
- Mobile evidence drawer inspected at 390x844, with full-viewport bounds;
  screenshot `.playwright-mcp/tennis-prop-url-mobile.png` in browser output.
  After resize/drawer animation settled, document width matched its viewport.
- Impeccable detector returned no findings. `git diff --check` passes.
  No commit, remote push, deployment, or database change for this step.
  Existing findings and employer-guide assessment remain unchanged.
- Steps 5-7, the four data panels, are still unimplemented. Step 4 remains
  unchecked until owner review, per the implement skill's per-step gate.

### Four-panel extension review gate

Steps 5-7 are a new review draft following the owner's request for all four
panels. No implementation for them has started. Keep existing step 3 review
and step 4 work in sequence. Run the documented Verify halves and observe
desktop/mobile, missing-data, historical, and time-boundary behavior for the
new context. Test parsing and derivation logic rather than React markup.

### Step 3 evidence (implemented, awaiting owner review)

- Added Analysis and Picks & Props using Ant Design tabs with the NFL tab
  styling, shared header, and Analysis default. A keyed section resets the
  selected tab on a different match. Moved the match-pick listing and prop
  list into Picks & Props; Analysis retains model/market probabilities and
  research context with a concise link to the second tab.
- Reused the tennis prop table and evidence drawer, with unique table IDs
  per market. Both-player/individual-player, source, and market filters work
  on canonical match-linked lines only. PrizePicks is the public default;
  existing owner view can choose DraftKings or Bet365.
- The global prop board omits goblin alternates. Added an opt-in match-board
  mode that includes them as reference rows; default global-board behavior
  and its tests remain unchanged. PASS and line-only rows stay visible.
- Match picks reuse the slate's existing composition/eligibility rules,
  distinguish best bets from angles, and load only for scheduled/live matches
  with a known start date. Finished matches do not fetch current match picks.
- `npm.cmd --prefix web run verify`: typecheck, 769 tests, production build
  passed. Existing bundle-size warning remains. API venv pytest: 3,674 passed
  with one existing deprecation warning. Nine new pure tests cover canonical
  match isolation, sources/players/markets, alternate lines, pick eligibility,
  finished matches, and missing start dates. `git diff --check` passes.
- Playwright observed match 91823 default to Analysis and render 28 linked
  current PrizePicks lines plus the Jacquet win-a-set angle on Picks & Props.
  Player filter restricted rows to Jacquet; Aces restricted to one market;
  the evidence drawer opened the selected Jacquet line. Keyboard ArrowRight
  and Enter activated Picks & Props. Ant Design adds live tab position text
  to its accessible name during keyboard use, so an exact-name assertion
  timed out after successful activation.
- Finished match 89084 showed no current match picks and an explicit no-lines
  message. A browser-only 503 fixture confirmed error/Retry UI; the route
  override was removed. No provider or database writes for this step.
- Desktop and 390px mobile screenshots inspected in browser output:
  `.playwright-mcp/tennis-match-tabs-desktop.png` and
  `.playwright-mcp/tennis-match-tabs-mobile.png`. The mobile layout fits the
  viewport after drawer animation settles. A transient width measurement
  during drawer closing was not treated as a persistent overflow defect.
- Impeccable detector returned no findings for the changed page, CSS, and
  two new UI components. Existing F-09/P3 and F-12/P2 remain unverified.
  No P0/P1 blocker; no employer-guide claim changed by this navigation work.
- Step 4 is not implemented: prop entry links and URL-backed tab/filter
  selection remain pending. Step 3's checkbox stays unchecked until review.

### Tab extension review gate

The owner requested the two-tab flow after the surface/navigation work.
Owner approved implementation of steps 3 and 4 with the Analysis and
Picks & Props labels. Step 2 accepted with the move to the tab extension.
Run the documented Verify
halves and browser acceptance checks for each new step. Reuse existing NFL
and tennis styling as the visual reference; no new visual theme is needed.

### Step 1 evidence (approved by owner)

- Branch: `fix/tennis-direct-analysis`. No commit, merge, push, or data write.
- `npm.cmd --prefix web run verify`: typecheck, 760 tests, and production
  build passed. Vite reports its existing large-bundle warning.
- From `api/`, `.venv\Scripts\python.exe -m pytest`: 3,674 passed,
  one Starlette/anyio deprecation warning. These are the two documented
  Verify halves, with the Windows npm launcher and API venv.
- Playwright observed the match link and a click elsewhere in its row
  navigate to `#/tennis/match/91823`; Enter activates the link; browser Back
  returns to `#/` with no inline detail row. Control-click created a separate
  match-analysis tab. The popup event listener timed out, but the new tab was
  subsequently observed by its exact URL.
- The first digest link navigated to its canonical match 91871.
- No unlinked props were visible in the live slate. A temporary browser-only
  response fixture verified an unlinked player's button expands its prop
  details without navigating. The route override was removed afterward;
  no fixture was written to the database or source.
- Match 91823's detail API returned both existing ELO ratings and full
  analysis rendered them, currently as Clay 1771 and 1604 pending step 2.
  Both player-stats API requests also returned ELO and rolling stats.
  The earlier missing display could not be reproduced; no backend change.
- Screenshot: `.playwright-mcp/tennis-direct-analysis.png` and slate capture
  `.playwright-mcp/tennis-direct-slate.png` in the browser tool's output.
- The first local API launch failed because Windows' default event loop is
  incompatible with psycopg async; restarted with SelectorEventLoopPolicy.
  A Vite dependency-optimization 504 occurred during reload; refreshed before
  the final navigation check. Initial launch errors are not product fixes.
- Owner approved step 1 and continuation to step 2 on 2026-10-22.

### Step 2 evidence (implemented, awaiting owner review)

- Confirmed cause: the Windows task `Lineform ingest_daily` launches
  `C:\dev\SportAppV2\api\ingest_daily.bat`, not this workspace. That checkout
  is at `8280634`, lacks the override module and its normalizer call, and
  logs its October 22 match ingest from 12:00:02 to 12:02:06 CT. Affected
  database rows share `updated_at = 2026-10-22 17:00:05.692654+00:00`.
- GitHub's October 22 Match Ingest run 39776259156 used `80b4235`, which
  already contains the override, and finished at 12:13 UTC. Current provider
  Lyon responses still say clay but normalize to Hard/indoor in this workspace.
  This disproves the earlier suggestion that GitHub lacked the fix.
- Corrected only `matches.surface`, `matches.indoor`, and `matches.updated_at`
  for events 14767/14763 when surface/indoor differed. Twelve rows changed;
  all 35 event rows now show Hard/indoor. No provider ingest was rerun.
- In the same repeatable-read transaction, fingerprints confirmed all
  41,161 non-target match rows and all rows in `predictions`,
  `prop_projection_snapshots`, `tennis_elo_comparisons`,
  `tennis_elo_freeze_cycles`, and `tennis_elo_snapshots` were unchanged.
  Evidence: `%TEMP%\lineform-lyon-2026-10-22-correction.json`.
- Playwright and HTTP 200 match detail confirmed match 91823 shows
  Hard, indoor, with Hard ELO 1868.0 and 1682.0. The live model recomputes
  using Hard inputs; frozen outputs remain untouched. Screenshot:
  `.playwright-mcp/lyon-hard-direct-analysis.png` in browser tool output.
- Prepared `%TEMP%\lineform-lyon-scheduled-copy.patch`, limited to the
  existing override module, its ingest call, and their two regression test
  files. `git apply --check` passes against `C:\dev\SportAppV2`.
  That copy's existing overview edit is preserved. Owner separately approved
  applying it to the active scheduled copy; all four patch files were applied.
  Its own venv passed all 100 normalizer/surface tests. No task configuration,
  unrelated file, commit, or remote changed. The next scheduled run was not
  dispatched, so end-to-end scheduled acceptance is still unobserved.
- Findings ledger has F-09 (P3) and F-12 (P2), both unverified; no open/fixed
  P0/P1 blocker. Employer guide unchanged: no architectural or model claim
  changed. Step 2 remains unchecked pending owner review.
- Final web Verify retry could not start: `tsc` is no longer installed in
  this workspace (`web/node_modules/typescript/bin/tsc` and `.bin/tsc.cmd`
  are absent). Earlier step 1's 760 tests/typecheck/build passed for the
  unchanged product diff. No dependencies were removed by this work; do not
  describe the latest combined verification retry as passing.
- Final API retry: 3,674 passed with one existing deprecation warning.
- Restored this workspace's dependencies with `npm.cmd ci --ignore-scripts
  --no-audit --no-fund` using the unchanged lockfile. The first attempt hit
  the verification Vite server's native-module lock; stopped only that server,
  restored dependencies, then restarted it at port 3001. No tracked package
  files changed. Final web retry: 760 tests and typecheck passed; production
  build passed with the existing bundle-size warning. The documented Verify
  halves are now green again. No new backend source change was needed here.

- Add focused tests for new pure navigation or surface logic, if introduced.
- Observe the running slate, digest, prop-only fallback, full analysis, and
  Back navigation. Confirm Hard ELO is shown after the surface correction.
- Run the exact Verify gate: `npm --prefix web run verify && cd api && python -m pytest`,
  using the API venv for the Python half.
- Show the diff and evidence after each step for review. No commits without
  permission. This small navigation/data fix does not currently change an
  employer-guide claim; reassess if investigation changes its scope.

## Completion record (2026-10-22)

All seven steps are implemented and reviewed through the owner's continue
approvals and final `$complete` invocation. Evidence sections above are a
chronological record; their pending-review notes describe earlier checkpoints.
The stale scheduled checkout was identified and patched with separate approval.
The employer interview guide was updated locally and remains ignored/untracked.

Final automated gate, using the documented Windows/venv equivalents:

- `npm.cmd --prefix web run verify`: typecheck, 809 web tests, production build.
- From `api/`, `.\.venv\Scripts\python.exe -m pytest`: 3,704 API tests.
- `git diff --check`: clean. Existing bundle-size and dependency warnings only.

Running-app evidence covers match 91823 at
`http://127.0.0.1:3001/#/tennis/match/91823`, both tabs, canonical prop links,
URL reload and Back/Forward, surface selection, historical/missing/thin data,
workload coverage, freshness and mobile layout. Screenshots are identified in
the step evidence above. Final invariants review found no blockers: research
reads are bounded, SQL stays in repositories, model/holdout/version behavior
is unchanged, and shared sport/provider filters and signal rules are preserved.
The ledger retains the existing unverified F-09 and F-12 leads unchanged.

How to try: click a canonical match on the tennis slate to open Analysis;
inspect surface/serve context, workload and freshness, then choose Picks & Props
for match picks and filtered lines. A canonical prop link selects its match,
player, market and line; reload and browser Back preserve URL state.

Known limits remain visible: duration minutes are unavailable, stored match
history and completed-set coverage can be partial, and current rolling stats
are not historical pre-match snapshots. The next scheduled ingest was not
observed. No merge, push or hosted deployment is included in this record.

# Feature: Lineform shape consistency

**From build-plan:** feature 38f
**Status:** completed and squash-merged locally into `master` on 2026-10-18; not pushed
**Branch:** `feature/38f-shape-consistency`
**Selected:** 2026-10-17. The owner selected 38f and kept 16f parked.

## Goal

Finish the shared Lineform page shape across sport detail pages, and give
NFL and NBA tables the same gray panel treatment as tennis. Complete
the header, tab-title and Central-time presentation promised by item 38.

## Design reference

- Approved structure: [command sketch](../../.impeccable/mocks/decision/command.html).
- [Direction contract](../../.impeccable/surfaces/web-src-pages-nflintelligencepage-tsx.md).
- Existing tennis slate tables are the reference for gray, bordered table
  surfaces. Existing `PageHead` is the reference for title sizing, metadata
  and controls. Theme tokens already live in `web/src/index.css`; do not
  port a new theme or copy the sketch's illustrative data.
- Owner correction, 2026-10-17: tennis has gray backgrounds behind content
  such as tables while NFL and NBA tables sit on black, which looks inconsistent.
  Owner clarified the direction after reviewing step 1: keep tennis gray and
  bring NFL and NBA to that treatment. This supersedes the first interpretation.
- Capture current desktop and phone views before changing each surface and
  save before/after evidence under `blueprint/reference/38f/`. The old
  2026-10-16 polish captures predate the redesign; only reproduced defects
  in this spec's surfaces count as remaining work.

## In scope

- Keep the filled, rounded table wrapper on the tennis slate.
  `.tennis-slate-table` currently sets `background: var(--bg-card)`, a
  surrounding border and a radius. Apply those tokens to NFL/NBA slate table
  containers. Keep table separators, readable grouping
  and visible hover, focus and expanded-row states.
- Check prop, model, match and player tables across sports for inconsistent
  enclosing surfaces. Use the existing tennis gray panel as the reference
  for comparable table containers, including a parent wrapper when appropriate.
  Do not flatten every card, chart, badge, control or drawer indiscriminately.
- Use the existing `PageHead` on NFL/NBA game pages, tennis match/player
  pages and the NFL player page. Each gets one primary `h1`.
- Keep the three model pages on their existing shared heads; verify their
  alignment and wrapping instead of rebuilding those heads.
- Specific browser tab titles for the five detail routes, from data already
  loaded by those pages, as promised in 38a.
- Display clock timestamps in `America/Chicago` with the label `CT`, including
  prop evidence and chart time axes. Retain date-only and relative-age semantics.
- Reproduce and repair spacing, clipping, background, heading and time-label
  defects on these surfaces at desktop and phone widths. List each confirmed
  defect and its evidence in this spec before its repair; split a large diff
  into another reviewable step within this feature.

## Out of scope

- Backend, database, ingest, new requests, models or prediction versions.
- Any probability, edge, pick, rank, filtering or sorting change. NBA game-page
  props stay unranked and unsorted; NFL and NBA reference gaps stay gray.
- New sport pages, an NBA player page, Admin or the hidden parlays layout.
- Changing NBA's Eastern slate-date contract, tennis date windows, NFL week
  selection, stored UTC timestamps or kickoff eligibility.
- A new palette, fonts, global removal of panel backgrounds, or a redesign of
  existing charts, evidence drawers and detailed analysis bodies.
- Unrelated polish, workflow changes, plan regeneration, publishing or deployment.

## Build loop

Build one step at a time, never the whole feature at once.

1. Explain the step and its expected diff before editing.
2. Implement only that step and verify its done-when.
3. Show the diff and evidence for owner review.
4. Continue after approval. A checkpoint commit is optional and needs permission
   plus passing required checks; `/complete` handles the final archive and merge.

## Build steps

- [x] **Step 1 - Shared gray slate surfaces.** Capture the tennis,
  NFL and NBA slates at 1440px and 390px, keep the tennis table's
  gray enclosing panel, and give NFL/NBA table containers matching tokens.
  Adjust wrapper spacing as needed. *Done when:* all three sports have the
  same gray table surface, border and radius at both widths; tour tabs,
  tournament separators, expansion, digest selection, command filtering,
  keyboard focus and scrolling still work. Expanded evidence remains legible.
- [x] **Step 2 - Remaining table surfaces.** Compare the tennis Props,
  Model, match and player tables with their NFL/NBA equivalents. Record the
  wrappers whose surface treatments differ, then change
  those specific containers. *Done when:* comparable tables use gray panels at
  1440px and 390px; separators, hover/selection and focus remain distinguishable;
  chart panels, badges, signal colors and evidence drawers retain their intended
  treatments. No global theme-token change is needed. Record any surface that
  already matches instead of changing it. Split this step by page if necessary.
- [x] **Step 3 - Central-time labels.** Update the remaining clock formatters,
  notably `nflLabels.formatTime`, `formatKickoffTime` and tennis prop
  `startLabel`, to label Central time `CT`. Label chart axes once per chart
  where repeating CT on each tick would be cluttered. Handle missing or
  invalid timestamps without throwing. *Done when:* NFL and tennis prop
  rows/evidence, game and match times, model freshness and chart clock axes
  use CT with correct winter and summer offsets; fixed-timestamp tests cover
  both seasons, a Central midnight boundary and invalid/missing values.
  Plain dates and relative fetch ages remain unchanged.
- [x] **Step 4 - NFL and NBA game heads.** Add `PageHead` with an
  `AWAY @ HOME` title, a concise period/start/status line, and retain existing
  back links. Adapt the existing hero into supporting records, score and
  conditions so the title and time are not repeated as competing headers.
  *Done when:* both game routes have one visible `h1` and the shared title
  alignment at both widths; records, final scores, venue/weather, game type,
  market, model caveats, charts and props remain available. NBA's back link
  still uses the API's `gameDate`; missing secondary NFL data cannot hide
  the primary game head. Missing/invalid routes use a generic shared head.
- [x] **Step 5 - Tennis match and player heads.** Use `PageHead` with
  `P1 vs P2` on matches and the player's name on player pages. Move the old
  header's context into metadata and supporting identity content. Replace
  the two match-side `h1` elements with non-primary identity elements.
  *Done when:* each route has one visible `h1`; player links, tour, event,
  surface/round, winner/final score, player rank/country/hand/age and next-match
  link remain accessible at both widths. No upcoming match and time TBA have
  readable fallbacks, and missing routes use a generic shared head.
- [x] **Step 6 - NFL player head and model alignment.** Put the player's name
  in `PageHead`, position/team/season/week in concise metadata, and its existing
  season summary in `stats`. Keep depth, injury and as-of roster tags as
  supporting content. Inspect all three existing model heads for consistency.
  *Done when:* the NFL player has one shared `h1`, its back link and summary
  values still work, tags wrap at 390px, and all model heads align with the
  shared gutter without clipping season, grading time or version controls.
- [x] **Step 7 - Specific detail tab titles.** Add route-scoped title metadata
  using loaded detail data, with one owner of `document.title` in the shell.
  Keep the existing pathname-derived title as fallback. *Done when:* each
  loaded detail route has the title listed below; loading, missing and failed
  pages show a generic route title; navigating between entities or to a slate
  never leaves the previous entity's title, even if its request finishes late.
  Pure title-resolution tests cover all detail kinds, fallback and stale-route
  registration. No title-specific data request is made.
- [x] **Step 8 - Finish verification.** Capture the changed surfaces at
  1440px and 390px, plus 1000px for header/control wrapping. Compare the three
  slates, prop boards, three model pages and five detail routes. Exercise one
  invalid detail link, loading/error retry, browser back/forward and an evidence
  drawer. *Done when:* there is no page-level horizontal overflow or UI text
  below 11px on changed surfaces; table-local scrolling remains usable; all
  earlier done-whens have evidence; confirmed scoped polish defects are resolved
  or explicitly presented for review; final Verify passes. No checkboxes in
  the build plan are changed until `/complete`.

## Files / areas

- `web/src/pages/nfl-slate.css` for shared NFL/NBA slate panels and
  `web/src/components/nfl/nfl-slate-table.css` for visible hover treatment.
- `web/src/components/tennis/tennis-slate.css` and the tennis table wrappers
  in `web/src/pages/tennis-{prop-board,model,match,player}.css` as confirmed.
- `web/src/components/shared/PageHead.tsx` and `web/src/index.css` only if a
  shared layout adjustment is needed; retain the existing props contract.
- `NflGamePage.tsx`, `NbaGamePage.tsx`, `TennisMatchPage.tsx`,
  `TennisPlayerPage.tsx`, `NflPlayerPage.tsx`, and their existing header/hero
  components and scoped styles.
- Existing model-page styles only for reproduced alignment defects.
- `web/src/utils/nflLabels.ts`, `tennisPropCards.ts`, relevant formatter tests,
  and `web/src/components/nfl/NflLineMovementChart.tsx` for chart labeling.
- `web/src/App.tsx`, `web/src/utils/sportNav.ts` and tests; a small shared
  title context/hook and pure resolver if needed to keep one title owner.
- `blueprint/reference/38f/` for browser evidence and this spec for results.

## Data / contracts

- **Client-only presentation.** Reuse existing hooks and response types. No API
  or schema changes and no extra fetches for headers or titles.
- **Shared head:** `title: string`, `meta?: ReactNode`,
  `period?: { label: string; previous?: string | null; next?: string | null }`,
  `actions?: ReactNode`, `stats?: ReactNode`. Do not invent previous/next entity
  navigation when no such contract exists. Keep current back-link destinations.
- **One title owner:** the shell resolves an optional loaded label registered
  for the exact current pathname, otherwise `documentTitle(pathname)`. A
  registration for a different pathname is ignored immediately. Clear entity
  labels when data is unavailable; do not let individual page effects race the
  shell's existing title effect.

  | Detail route | Loaded tab title |
  |---|---|
  | NFL game | `AWAY @ HOME - NFL game · Lineform` |
  | NBA game | `AWAY @ HOME - NBA game · Lineform` |
  | Tennis match | `P1 vs P2 - Tennis match · Lineform` |
  | NFL player | `Name - NFL player · Lineform` |
  | Tennis player | `Name - Tennis player · Lineform` |

- **Time:** clock instants stay in `America/Chicago`, including its daylight
  saving offsets, but the visible zone label is always `CT`. Date-only values
  stay dates; NBA `gameDate` remains an Eastern calendar-date key. This is a
  formatting change, not a schedule or query-window change.
- **Table surfaces:** existing tennis gray panels for comparable resting table
  containers over black pages; neutral raised states identify hover/selection and
  controls. Keep theme tokens and the existing validated signal rules.

## Testing

- Run focused Vitest tests for each formatter/title logic change in the same
  diff, then the documented web build. CSS and component composition use
  browser screenshots and interaction evidence, not component unit tests.
- Time fixtures include summer and winter UTC instants mapping to different
  Central offsets, an instant near midnight and malformed/missing input.
- Final gate from the repo root, with the API venv active:
  `npm --prefix web run verify && cd api && python -m pytest`.
  In PowerShell run the two halves sequentially if needed, using
  `api/.venv/Scripts/python.exe -m pytest` from `api/` for the second half.
- Compare a representative row before/after: values, rank, order, green/red EV
  on tennis and gray NFL/NBA reference values must agree. Review drawer
  readability separately from resting table backgrounds.
- Record actual routes, widths, screenshots and check results as work completes.
  Missing live data must be identified; fixtures may supplement it but cannot
  be described as a successful live-data check.

## Notes for the AI

- The build plan is the progress authority: 38d2, 38d3 and 38e are complete
  although the generated overview still calls them pending. Do not redo them
  or hand-edit the generated overview during implementation.
- Start with the owner's clarified background concern: keep tennis gray and
  make NFL/NBA consistent. Do not change `--bg-card` globally.
- Do not claim the old polish defects survive without reproducing them.
  Keep this pass limited to the surfaces and defect kinds above.
- Preserve the 38a decision: no repeated eyebrow or generic subtitle. The
  shared head uses one concise metadata line and a 34px title.
- Use theme variables, strict TypeScript, existing aliases and existing
  TanStack Query hooks. Do not introduce fetching effects.
- No backend or model work is justified by this presentation pass.
- This cosmetic feature does not change an employer-guide claim; update the
  local ignored guide only if implementation evidence reveals a material claim
  that actually needs correcting. Never stage that guide.

## Draft critique

- Added background consistency as the first implementation step. Owner review
  corrected its direction: tennis gray is the reference, not NFL/NBA black.
- Narrowed background changes to comparable table containers; global palette
  changes would also alter charts, controls and NFL/NBA detail cards.
- Model heads already use `PageHead`; their work is verification and specific
  alignment fixes, not another migration.
- Split game, tennis and NFL player header changes into separate reviewable
  steps, and included missing data and invalid-link states.
- Locked title ownership and stale-route behavior to prevent competing effects.
- Separated CT clock labels from date-only/Eastern slate semantics and added
  winter, summer and boundary tests.

## Implementation evidence

### Completion, 2026-10-18

- Owner invoked `/complete` after the implementation and acceptance review.
  All eight steps are complete. Feature 38f and parent 38 are checked off.
- Final verification: `npm.cmd --prefix web run verify` passed typecheck,
  612 web tests and production build; the API venv's `python -m pytest -q`
  passed 2,608 tests. Browser evidence and the manual try path are in
  `blueprint/reference/38f/acceptance.md`.
- Invariants review against `master` plus the uncommitted feature diff: clean.
  NFL/NBA signals remain gray and changed UI text meets the 11px floor.
  No backend, model, provider, filter, holdout or production-path changes.
- No blocking P0/P1 findings. Existing unverified P2 F-02 remains in the ledger.
  No prototypes were consumed; no employer-guide claim changed.
- Spec archived and active context reset. Local work commit: `fdb84c7`.
  Owner explicitly approved the squash merge into `master`; feature branch
  removed after the clean merge. Push and deployment are not authorized.

### Step 8 acceptance results, 2026-10-18

- All 13 routes passed at 1440px, 1000px and 390px (39 captures): three
  slates, two prop boards, three model pages and five detail pages. Each
  rendered one 34px h1 at shared gutters approximately 46px/32px/20px.
  No page horizontal overflow or rendered UI text below 11px was found.
  Slate and prop panels retain gray rgb(13,13,15) and 14px radius.
- The isolated matrix pass reported zero page errors and zero failed HTTP
  responses. Representative final desktop slate and phone prop/game
  captures were visually reviewed, alongside earlier per-step reviews.
- Tennis WTA filtering reduced 57 rows to 8; All restored 57. Stable-key
  keyboard expansion opens/closes its detail with solid focus at both widths.
  Digest selection opened the selected match, and start-time sorting rendered
  16 tournament groups at desktop and phone widths.
- All three slate command filters narrowed rows and cleared back to the
  original counts. Enter opened matching details and browser Back restored
  the slate. Phone search and loaded detail titles were observed explicitly.
  Early probes were corrected to await committed route titles and use stable
  match keys/visible Ant Select labels instead of stale or covered inputs.
- Local game-log scrolling works without page overflow: NFL player table
  moved approximately 403px horizontally; tennis player log moved 647px.
- Both prop boards and NFL/NBA game evidence drawers passed at desktop and
  phone widths: solid focus, Enter opens, Escape closes, no drawer overflow
  and no rendered text below 11px. Representative row text stayed unchanged
  through interaction. Tennis positive EV stayed green; NFL/NBA gap values
  stayed gray rgb(245,245,247). Existing pure tests cover negative EV tone.
- Rechecked invalid NFL game, delayed NBA loading, browser-only 503 and
  Retry, plus back/forward: generic heads/titles persist during unavailable
  states and the loaded PHI @ NY title returns after Retry. No page error.
  The intentional 503 fixture is separate from the clean live matrix pass.
- Earlier evidence also proves winter/summer/midnight CT offsets, preserved
  final scores/winner tags, roster/profile metadata, TBA/no-next fallbacks,
  missing NFL secondary data, and stale-response title protection.
- Final Verify passed sequentially: `npm.cmd --prefix web run verify`
  (typecheck, 612 tests, production build), then
  `.\\.venv\\Scripts\\python.exe -m pytest -q` from `api/` (2,608 passed).
  `git diff --check` passed. No API, workflow adapter, model or build-plan
  files changed. No new source repair was needed in this acceptance pass.
- Full review packet: `blueprint/reference/38f/acceptance.md`. There are 54
  final PNG captures, including the matrix and interaction states. Existing
  bundle-size and API deprecation warnings remain. Ledger F-02 is the
  pre-existing unverified P2 model finding; no open/fixed P0/P1 is recorded.
- At acceptance capture, Step 8 awaited final owner review. The subsequent
  `/complete` invocation accepted that review; see the completion record above.

### Step 8 acceptance plan, 2026-10-18

- Owner asked to continue after Step 7 review. Use the check skill for a
  final observation pass, with any source repair handled separately through
  implement. No commit or completion bookkeeping is authorized here.
- Capture all three slates, both prop boards, all three model pages and
  five detail pages at 1440px/1000px/390px. Check headings/title metadata,
  horizontal overflow, text sizes, table surfaces and local table scrolling.
- Exercise slate filtering/expansion and keyboard navigation, representative
  evidence drawers, invalid details, loading/error retry and browser history.
  Reuse the fixed-time tests and earlier per-step edge evidence.
- Run final Verify after the acceptance pass and record any remaining scoped
  issue explicitly. Do not change build-plan checkboxes until complete.

### Step 7 verification, 2026-10-18, awaiting approval

- DocumentTitleProvider is the sole document.title writer. Nav retains its
  menu-closing effect. Five detail pages register labels from their existing
  successful primary queries, or null when data is unavailable. No new fetch.
- Pure document-title resolver filters by exact pathname and retains the
  existing sportNav documentTitle fallback. Registration owner IDs prevent
  stale cleanup from clearing a newer page's metadata.
- Verified all five live loaded titles: BUF @ LV - NFL game, PHI @ NY - NBA
  game, Katarzyna Kawa vs Daria Snigur - Tennis match, Ashton Jeanty - NFL
  player and Katarzyna Kawa - Tennis player, each followed by `· Lineform`.
  Generic titles remain on missing/invalid details and the NBA slate.
- Browser-only delayed NBA game 21320 response: the pending game showed
  generic NBA game, then navigation to NFL player 40399 showed Ashton Jeanty.
  Releasing the NBA response afterward left the NFL player title unchanged.
  Back/Back/Forward restored BOS @ DET, PHI @ NY and BOS @ DET respectively.
- Browser-only 503 fixture produced generic NBA game, and removing it plus
  Retry restored BOS @ DET. Returning to the slate restored NBA slate.
  Both isolated browser passes reported zero page errors. Fixtures only
  controlled responses in the browser and did not write application data.
- Focused title/navigation tests: 40 passed. Full Verify halves passed
  sequentially: `npm.cmd --prefix web run verify` (typecheck, 612 tests,
  production build), then `.\\.venv\\Scripts\\python.exe -m pytest -q`
  from `api/` (2,608 passed). `git diff --check` passed.
- This step changes browser metadata only; page layout is unchanged from
  Step 6. Existing build bundle and API deprecation warnings remain.
- Step 7 checkbox remains unchecked pending review. No commit, merge or push.

### Step 7 inspection, 2026-10-18

- Owner asked to continue after Step 6 review. Proceeding with tab titles.
- Loaded NFL game 91, NBA game 21319, tennis match 88732, NFL player
  40399 and tennis player 2415 all still display generic kind-only tab
  titles although their headings contain the loaded entity labels.
- Nav currently owns document.title in its pathname effect. Replace only
  that write with a shell title provider; keep menu-closing behavior.
  Five detail pages register their existing query's successful loaded label
  for the exact pathname, or null during missing/error/loading states.
- A pure resolver retains documentTitle as fallback and ignores registrations
  for other paths. Owner IDs guard cleanup so an older registration cannot
  erase the current one. Use layout effects for registration/title writes
  before paint, with one DOM title owner and no new data requests.
- Add focused pure tests for all five title kinds, generic/empty fallback,
  stale-route registration and cleanup ownership; then prove navigation,
  errors, retry and a late response in the live browser.

### Step 6 verification, 2026-10-18, awaiting approval

- NFL player uses PageHead with name, position/team/season/week metadata
  and the existing Chips in stats. Availability/roster tags remain below the
  head, with existing injury tones and as-of team wording. Removed only the
  obsolete badge/head layout. Loading/error/missing states now compose a
  generic NFL player head with the existing state components.
- NFL player 40399 at 1440px, 1000px and 390px has one shared 34px h1,
  aligned to the same 46px/32px/20px gutters as all three model heads.
  No page overflow. Summary is unchanged: 5 games, 58.2 rushing yards per
  game, 17.6 carries per game, 72% snap share.
- Depth RB1, Full Participation in Practice and Week 6 team LV roster tags
  all remain readable; tags wrap at 390px without clipped content.
- Live back link resolves to BUF @ LV (game 91) after the slate loads.
  Keyboard focus is solid; Enter opens the game and browser Back restores
  the player at desktop and phone widths. A live line opens its evidence
  drawer and Escape closes it at both widths, with no drawer overflow.
- Malformed and absent numeric player IDs show one generic NFL player h1
  and the readable missing message. Isolated navigation and missing-state
  checks reported zero page errors.
- Model code unchanged: tennis, NFL and NBA heads already align and wrap
  correctly at all three widths. Observed season/last-graded text and
  complete version strings. Tennis's selected version text fits its control
  (311px content and scroll width), including at 390px.
- Captures: `step6-nfl-player-after-{1440,1000,390}.png`, drawer captures
  at desktop/phone, and `step6-{tennis,nfl,nba}-model-unchanged
  -{1440,1000,390}.png` under `blueprint/reference/38f/`. Visually reviewed
  NFL player desktop/phone and all three model phone captures. Used instant
  scrolling for final captures so smooth-scroll animation cannot crop heads.
- Verify passed sequentially: `npm.cmd --prefix web run verify`
  (typecheck, 590 tests, production build), then
  `.\\.venv\\Scripts\\python.exe -m pytest -q` from `api/` (2,608 passed).
  `git diff --check` passed. No new pure business logic, API requests or
  backend/model changes. Existing bundle and API deprecation warnings remain.
- Step 6 checkbox remains unchecked pending review. No commit, merge or push.

### Step 6 inspection, 2026-10-18

- Owner asked to continue after Step 5 review. Proceeding with the NFL
  player head and model alignment. Restarted local Vite without opening a
  native browser; the API on port 8000 was already running. A startup
  network-change error cleared after browser reload.
- NFL player 40399 uses a standalone heading, offset by its initials badge:
  title x=122px at 1440px, 108px at 1000px and 84px at 390px, with sizes
  46px/40px/32px. All three model heads already use shared 34px titles at
  gutters approximately 46px/32px/20px across those widths. No model-head
  clipping or page overflow was observed; keep the model code unchanged.
- Before captures: `step6-{nfl-player,tennis-model,nfl-model,nba-model}
  -before-{1440,1000,390}.png` under `blueprint/reference/38f/`.
- Expected diff: PageHead with player name, position/team/season/week
  metadata and existing Chips in stats; existing availability/roster tags
  as supporting content. Remove the duplicate initials badge and old scoped
  head layout. Give missing/loading/error states generic shared headings.
- Existing summary values for Ashton Jeanty: 5 games, 58.2 rushing yards
  per game, 17.6 carries per game and 72% snap share. Keep those contracts.
- Existing NFL player breadcrumb also focuses without an outline. Add a
  scoped focus-visible indicator while preserving its game/slate destination.

### Step 5 verification, 2026-10-18, awaiting approval

- MatchHeader uses PageHead for P1 vs P2, with tour, event, round, surface,
  format and start or final score in metadata. Both linked player identities
  remain below it as non-primary text, including rank/hand/ELO and winner.
  PlayerHeader uses PageHead for name and existing profile metadata, with
  NextMatch in actions. Removed only obsolete scoped header styles.
- Live match 88732 and player 2415 at 1440px and 390px each render one h1,
  with no page overflow. Player metadata retains WTA, #127, Right-handed,
  POL and age 33. Next-match navigation still opens match 88732.
- Completed match 83163 retains `Final · 6-3 4-6 5-7`, with Daria Snigur's
  Won badge and both player links at both widths.
- Keyboard focus is solid on breadcrumbs, both match-side player links
  and the next-match link. Enter opens the player or next match, and browser
  Back restores the original page at both widths; no page errors observed.
- Browser-only fixtures verified Time TBA and No upcoming match at both
  widths with one h1 and no page overflow. Fixtures do not write data.
  An initial fixture attempt reused cached query data; reran on a fresh
  page with reload before claiming the fallback checks passed.
- Malformed IDs and absent numeric IDs show generic Tennis match/player
  heads and readable missing messages. Loading/error states compose those
  same generic heads with the existing shared loading and retry components.
- Captures: `step5-{tennis-match,tennis-player}-{before,after,focus}
  -{1440,390}.png`, completed-match after captures, and time-TBA/no-next/
  missing captures under `blueprint/reference/38f/`. Visually reviewed the
  match phone and player desktop captures.
- Verify passed sequentially: `npm.cmd --prefix web run verify`
  (typecheck, 590 tests, production build), then
  `.\\.venv\\Scripts\\python.exe -m pytest -q` from `api/` (2,608 passed).
  Web Verify passed again after focus-only CSS refinements. API inputs are
  unchanged by those refinements. No new pure business logic was introduced.
- `git diff --check` passed. No obsolete migrated-header class references
  or direct h1 elements remain in the old tennis header components. Existing
  build bundle and API deprecation warnings remain.
- Step 5 checkbox remains unchecked pending review. No commit, merge or push.

### Step 5 inspection, 2026-10-18

- Owner asked to continue after Step 4 review. Proceeding with tennis heads.
- Match 88732 renders two h1 elements, Katarzyna Kawa and Daria Snigur.
  Player 2415 has one h1 using its own 40px header rather than PageHead.
  Before captures at 1440px and 390px:
  `step5-{tennis-match,tennis-player}-before-{1440,390}.png` under
  `blueprint/reference/38f/`.
- Expected diff: MatchHeader composes PageHead with P1 vs P2 and existing
  tour/event/surface/round/time-or-score metadata, followed by smaller linked
  player identities and winner badge. PlayerHeader composes PageHead with
  the player's name, existing tour/rank/hand/country/age metadata and
  NextMatch as an action. Country remains explicit text; remove its duplicate
  decorative badge from the player head. No profile field is discarded.
- Give loading/error/missing match/player states generic shared headings.
  Retain current API hooks, prediction panels, player links and next-match
  fallback. Remove only scoped header styles made unused by this migration.
- Keyboard inspection at both widths found computed outline `none` on the
  existing tennis breadcrumb, match-side player links and next-match link.
  Add scoped focus-visible outlines to those navigation paths.

### Step 4 verification, 2026-10-18, awaiting approval

- NFL/NBA game pages use PageHead with one AWAY @ HOME h1, period,
  Central start time and status. The supporting team strip retains records,
  NFL conditions and NBA final scores without repeating the start time.
  Loading/error/missing screens have generic shared heads and back links.
- Live checks at 1440px and 390px: NFL games 91 and 80, NBA game 21319,
  completed NBA game 17568 (ORL 108, BOS 113), and play-in game 17559
  (MIA 126, CHA 127). One visible h1 on each, no page overflow. Title
  gutters match between sports: approximately 46px desktop and 20px phone.
- Market/model caveats, charts, team names and records remain accessible.
  Current NFL and NBA game props still load (17 and 10 tables respectively).
  The archived NBA games have no stored prop lines or closing lines; their
  readable empty states were observed, not described as populated checks.
- Keyboard Enter on both back links returns to the correct slate at both
  widths; browser Back restores the game. NBA preserves the API gameDate
  query (`2026-10-20`, `2026-04-12`, `2026-04-14` in the checked games).
  Back links now show a solid focus-visible outline at both widths.
- Malformed IDs and absent numeric IDs show generic NFL/NBA heads and
  missing-game messages. Browser-only fixtures delayed the NBA primary
  response, then returned 503: loading and error retained one generic h1;
  removing the fixture and pressing Retry restored the real PHI @ NY head.
- Browser-only empty NFL slate/notes fixtures left the real BUF @ LV
  heading, metadata and both line charts visible. No fixture wrote data.
  Isolated state and back-navigation checks reported zero page errors.
- Before/after captures: `step4-{nfl-game,nba-game}-{before,after}
  -{1440,390}.png`, plus final/play-in, missing/loading/error,
  missing-secondary and back-focus captures under `blueprint/reference/38f/`.
  Visually reviewed NBA desktop, NFL phone and completed NBA phone screens.
- Verify passed sequentially: `npm.cmd --prefix web run verify`
  (typecheck, 590 tests, production build), then
  `.\\.venv\\Scripts\\python.exe -m pytest -q` from `api/` (2,608 passed).
  Reran web Verify after focus/ARIA refinements; passed again. Those changes
  do not affect API inputs. No new pure business logic was added.
- During sequential file edits, Vite briefly paired the old NBA hero with
  the new caller, causing a transient development refresh error. Full reload
  after the complete patch and isolated browser checks showed no page error.
  Existing bundle and API deprecation warnings remain.
- Step 4 checkbox remains unchecked pending review. No commit, merge or push.

### Step 4 inspection, 2026-10-18

- Owner approved Step 3. Continuing with NFL/NBA game heads.
- NFL game 91 and NBA game 21319 have no h1 at either 1440px or 390px.
  Both use large team codes and a centered start-time label as their hero.
  Missing-game screens also have no shared heading.
- Before captures: `step4-{nfl-game,nba-game}-before-{1440,390}.png`
  under `blueprint/reference/38f/`. NBA back link is
  `/nba?date=2026-10-20`, using the API's gameDate.
- Expected diff: PageHead on both loaded game pages, generic shared heads
  on loading/error/missing states, start/status/period metadata moved out of
  the hero, smaller supporting team records, preserved NBA final score and
  NFL conditions. Keep secondary NFL slate/notes requests independent from
  the primary heading. No data, model, market or route changes.
- Keyboard review found the existing game back links focus with computed
  outline `none` at both widths. Add a scoped focus-visible outline to
  the shared game breadcrumb class; retain destinations and normal styling.

### Step 3 verification, 2026-10-18, awaiting approval

- `nflLabels.formatTime` and tennis prop `startLabel` format with
  America/Chicago and append CT, with readable fallbacks for malformed
  timestamps. Compact NFL kickoff text reuses the existing `fmtTimeCT`.
- Each NFL/NBA line-movement figure labels its market `(CT)` once.
  Tick formatting and chart calculations are unchanged.
- Focused tests passed: 94 tests across `nflLabels`, `tennisPropCards`,
  `nflPropCards`, `nflPropDetail` and `format`. Fixed cases cover winter
  UTC-6, summer UTC-5, both sides of Central midnight, and malformed,
  empty or missing input. Date-only and relative-age helpers are unchanged.
- Full Verify halves passed sequentially: `npm.cmd --prefix web run verify`
  (typecheck, 590 tests, production build), then
  `.\\.venv\\Scripts\\python.exe -m pytest -q` from `api/` (2,608 passed).
- At 1440px and 390px, NFL game 91 and the NFL prop board show
  `3:25 PM CT` in rows and evidence. NFL/NBA game charts show `Spread (CT)`
  and `Total (CT)` with compact Central ticks. Tennis prop rows show
  `Oct 18, 3:30 AM CT` on desktop; their existing phone layout hides the
  start-time row and the drawer has no clock label, so neither was added.
- All four changed page areas have no page or drawer horizontal overflow;
  Enter/click opens evidence and Escape closes it. No seasonal-zone label
  remains in rendered text on those routes or in product source formatters.
- Also observed existing CT labels on tennis match 88732, tennis player
  2415, NFL player 40399, and all three model pages. Model freshness uses
  `Sat, Oct 17 11:58 PM CT`. Tennis match chart endpoints already include CT.
- Captures: `step3-{nfl-game,nfl-props,nba-game,tennis-props}-after
  -{1440,390}.png` and matching `-drawer-after-` captures under
  `blueprint/reference/38f/`. Reviewed NFL desktop and phone evidence captures.
- `git diff --check` passed. Existing large-bundle warning and API test
  deprecation warning remain. No backend, schedule or model changes.
- Step 3 checkbox remains unchecked pending review. No commit, merge or push.

### Step 3 inspection, 2026-10-18

- Owner invoked implement after Step 2 review; proceeding with CT labels.
- NFL game 91 prop evidence displays `3:25 PM CDT`; its line-movement
  axes display Central weekday/hour ticks without a zone label. Tennis prop
  rows use the same seasonal suffix through `startLabel`.
- The three remaining seasonal-zone formatters lack invalid-date guards.
  Existing `fmtTimeCT`, game kickoff labels and model freshness already use
  CT and handle malformed input; keep their presentation contracts.
- Before captures: `step3-{nfl-game,tennis-props}-before-{1440,390}.png`
  and matching `-drawer-before-` captures under `blueprint/reference/38f/`.
- Expected diff: remove seasonal suffixes from the detailed NFL and tennis
  formatters, append CT after formatting with America/Chicago, reuse
  `fmtTimeCT` for the compact NFL kickoff, add malformed-input fallbacks,
  label each line-movement figure CT, and extend fixed-timestamp tests.
  No schedule keys, date-only labels, fetch ages or chart math changes.

### Step 2 verification, 2026-10-18, awaiting approval

- Shared `prop-table-panel` styles use the existing gray background, border,
  14px radius and spacing tokens. Applied to both prop boards and to NFL/NBA
  game-page modelled and other-line market containers. NBA phone rows wrap
  numeric details and recent results across separate lines below 480px.
- Verified the four changed routes at 1440px and 390px: gray resting panels,
  lighter hover (`rgb(20, 20, 23)`), distinct selected rows
  (`rgb(26, 26, 30)`), solid keyboard focus, Enter opening each evidence
  drawer and Escape closing it. No page or drawer horizontal overflow.
- Live other-line coverage: nine NFL game-market panels and one NBA
  game-market panel. Table values and order are untouched by the diff;
  representative row text stays the same through drawer interaction.
- NBA phone numeric cells now fit: line 26, model 28.4 and P(over) `--`
  remain visible for Jalen Brunson. Existing long alternate-line lists and
  explanatory sample labels still use ellipsis; full details are in the drawer.
- Inspected all three model routes at both widths: gray 14px panels and no
  page overflow. Tennis match/player and NFL player surfaces already match
  the gray treatment, as recorded below; no edits were needed there.
- Captures: `step2-{tennis-props,nfl-props,nfl-game,nba-game}-{after,drawer}
  -{1440,390}.png` and `step2-{tennis,nfl,nba}-model-unchanged-{1440,390}.png`
  under `blueprint/reference/38f/`. Reviewed tennis desktop, NBA phone and
  NFL phone drawer captures visually. Initial drawer captures were replaced
  after allowing their entrance transition to finish.
- Verify halves passed sequentially: `npm.cmd --prefix web run verify`
  (typecheck, 563 tests, production build), then
  `.\\.venv\\Scripts\\python.exe -m pytest` from `api/` (2,608 passed).
  Reran web Verify after the NBA CSS correction; passed again. API code and
  inputs did not change in that correction. Web verification required broader
  filesystem access for esbuild, as in step 1.
- Mechanical design scan returned `[]`; `git diff --check` passed. Existing
  diagnostics remain: favicon 404, large build bundle warning, one API test
  deprecation warning. No new application console error observed.
- Step 2 checkbox remains unchecked pending review. No commit, merge or push.

### Step 2 inspection, 2026-10-17

- Owner asked to resume 38f after the verified gray-slate step. Continuing
  with table surfaces; no checkpoint commit requested.
- Reproduced at 1440px and 390px: tennis and NFL prop boards, NFL game 91
  and NBA game 21319 have transparent prop-table containers over black pages.
  All need the existing gray, bordered panel treatment. Shared prop hover
  currently uses the resting gray, so it must use the lighter hover token.
- Tennis match 88732 and player 2415 tables already inherit gray, bordered
  14px panels. NFL player 40399 tables inherit gray, bordered player cards;
  retain their established local radius. No surface change needed there.
- Tennis and NFL model tables already inherit gray, bordered 14px panels.
  NBA model has no table in the current accruing-data state; its existing
  shared NFL model cards use those same tokens.
- Before captures: `step2-{tennis-props,nfl-props,nfl-game,nba-game,
  tennis-match,tennis-player,nfl-player}-before-{1440,390}.png` under
  `blueprint/reference/38f/`. No page overflow on these routes at either width.
- Planned repair: one shared prop-panel class applied to board main
  containers and game-market containers; shared hover-token correction.
  No row, filter, rank, probability, model, drawer or theme-token changes.
- Phone screenshot inspection confirmed an existing NBA prop defect:
  `step2-nba-game-before-390.png` clips model and P(over) values in the
  five-column grid. Panel padding makes it tighter in the after capture.
  Repair the phone grid within this step: keep player/gap above three
  numeric columns, then recent bars and sample on a third line. Values,
  player order and drawer content remain unchanged.

### Initial step 1, 2026-10-17, superseded by owner correction

- Product diff: removed only the outer border, radius and background from
  `.tennis-slate-table` in `web/src/components/tennis/tennis-slate.css`.
  The step checkbox remains unchecked pending owner approval.
- Live local app: `http://localhost:3001/`, NFL `/#/nfl`, NBA
  `/#/nba?date=2026-10-20`. Reused existing web and API servers.
- Before: tennis computed background `rgb(13, 13, 15)`, 14px radius and
  outer border. NFL/NBA tables were transparent with no radius or outer border.
  After: tennis also transparent, no radius or outer border, over the black page.
- At 1440px and 390px: 23 match rows, WTA tab filters to 13; Bellucci search
  filters to one matching row; digest selection opens its match; row expansion
  and keyboard Enter toggle work, with a visible solid focus outline.
  Start-time sort shows nine tournament groups. No page horizontal overflow.
- Screenshots: `blueprint/reference/38f/step1-{tennis,nfl,nba}-before-{1440,390}.png`,
  `step1-tennis-after-{1440,390}.png`, `step1-tennis-expanded-{1440,390}.png`
  and `step1-tennis-grouped-{1440,390}.png` in that directory.
  Reviewed both after screenshots visually.
- Verify halves passed sequentially: `npm.cmd --prefix web run verify`
  (typecheck, 563 tests, production build), then
  `.\\.venv\\Scripts\\python.exe -m pytest` from `api/` (2,608 passed).
  Web verification needed sandbox escalation for esbuild directory access.
- Existing diagnostics: favicon request returns 404; build reports a large
  bundle warning; API tests report one Starlette/AnyIO deprecation warning.
  Observed application API requests succeeded. No application behavior error
  was observed during the step checks.

### Revised step 1, 2026-10-17, awaiting approval

- Restored the tennis wrapper exactly. Product diff now changes only
  `nfl-slate.css` and `nfl-slate-table.css`: NFL/NBA kickoff-window containers
  use the existing gray background, border and 14px radius, with token-based
  padding. Row hover uses `--bg-card-hover` so it remains visible on gray.
- Browser checks at 1440px and 390px confirm all three sport panels compute
  to `rgb(13, 13, 15)`, the same border and 14px radius, with no page overflow.
  NFL/NBA links retain solid keyboard-focus outlines; Enter opens the correct
  game and back navigation returns to the slate. Hover is visibly lighter
  (`rgb(20, 20, 23)`) at both widths.
- Screenshots: `blueprint/reference/38f/step1-{tennis,nfl,nba}-gray-{1440,390}.png`.
  Visually reviewed NFL phone and NBA desktop captures.
- Reran `npm.cmd --prefix web run verify`: typecheck, 563 tests and production
  build passed. The 2,608 API tests passed earlier in this same step; the
  correction changes only CSS and does not change their inputs.
- The initial black-table captures document the superseded interpretation;
  the `-gray-` captures are the current review target. No commit was made.

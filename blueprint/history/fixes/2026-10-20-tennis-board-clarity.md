# Tennis board clarity and responsive evidence

**Type:** Fix
**Fixes:** F-13, F-14, F-15, F-16
**Branch:** fix/tennis-board-clarity
**Status:** Implementation and local verification complete. User authorized
the work commit on 2026-10-20; merge approval remains pending.
Requested through
`impeccable clarify`, `impeccable adapt`, and `impeccable polish` on 2026-10-20.
No merge, push, or deployment performed.

## The problem

Market counts hide reference-line availability, and player-name buttons do not
explain that they open evidence. Empty states do not help reveal available rows.

## The fix

Clarify ranked versus reference counts and the include-reference control. Add a
market-local reveal action and explicitly label evidence access. Keep the existing
theme, probabilities, classifications, ranking, source/tour filters, and Goblin
exclusion. The requested adapt pass restores mobile timing, makes the selected
line summary visible across viewports, and lets evidence context and phone
filters wrap rather than hiding information.

## Build steps

- [x] Clarify board counts, reference disclosure, evidence actions, and empty
  states. Done when markets with only reference rows show their available count,
  users can reveal those rows from the market panel, and each row has a visible
  View evidence action that opens the existing drawer.
- [x] Adapt timing and evidence to phone, tablet, and desktop. Done when board
  start times remain visible below 600px, the drawer shows matchup, CT timing,
  side, line, and available EV at every width, long context wraps, and phone
  source/tour options remain discoverable with touch-sized controls.
- [x] Polish disclosure and access states. Done when the local reference action
  supports showing and hiding, market/filter keyboard focus is explicit, long
  labels wrap, and the evidence dialog has an accessible name. Verify the full
  path at desktop and phone widths when browser access returns.

## Verify

Run the documented Verify gate (web verify, then API venv pytest), the Impeccable
detector, and browser checks when browser access is available. Check a market with
only reference rows, a mixed market, source/tour changes, and evidence access at
desktop/mobile widths. Any unavailable browser proof must remain explicit.

## Evidence

- Web Verify passed: typecheck, 48 test files / 644 tests, production build.
- API Verify passed: api/.venv/Scripts/python.exe -m pytest, 3,455 tests.
- Impeccable detector returned no findings for the five changed UI files.
- git diff --check passed.
- Browser verification unavailable: the current computer-use inventory has no
  browsers. Desktop/mobile widths, 200% zoom, reveal click, and drawer click need
  a running-browser review. Build step stays unchecked pending that review.
- F-13 through F-16 are fixed pending re-review.
- Employer guide unchanged: this copy/disclosure change does not change a claim.

## Adapt verification, 2026-10-20

- API Verify passed again: 3,455 tests; one dependency deprecation warning.
- Web Verify passed again: typecheck, 644 tests, production build. Vite retains
  its bundle-size warning; no dependency or bundle architecture changed.
- Impeccable detector returned no findings for the five adapted UI files.
- git diff --check passed.
- No browser is exposed in the current inventory. No rendered viewport, 200%
  zoom, synthesized touch, physical phone/tablet, Safari, or landscape check was
  possible. Responsive build steps remain unchecked for visual/user review.

## Polish and browser verification, 2026-10-20

The user explicitly requested Playwright on localhost, and browser access worked
on retry. This supersedes the earlier browser-access limitations above.

- Added local show/hide disclosure state, explicit filter focus rings, a named
  evidence dialog, wrapping market labels, and consistent helper line height.
- The first visual pass revealed truncated provider/payout and break-even text.
  Scoped wrapping also preserves full player/match metadata. Removed the unused
  tennis-prop-empty selector.
- Web Verify passed: typecheck, 644 tests, production build. Detector found no
  issues across the four polished UI files. git diff --check passed.
- API Verify passed: 3,455 tests, one dependency deprecation warning.
- Playwright visited http://127.0.0.1:3002/false#/tennis/board with real local data.
  At 320, 390, 768, and 1440px, document width did not exceed viewport width and
  CT start labels stayed displayed.
- Reference-only market: keyboard Enter revealed all 57 first-set-game rows;
  hiding restored zero rows. Mixed Aces market: 46 rows including reference,
  then two ranked rows after hiding. Counts reflect this particular live slate.
- Source PrizePicks and tour ATP selected successfully; restored All/All tours.
- Mobile and desktop evidence dialogs opened with matching accessible names.
  Keyboard Enter opened mobile evidence; Escape closed it. Selected line, side,
  available EV, matchup, timing, and recent-match context were visible.
- Final desktop provider/payout and break-even labels had normal wrapping and
  scrollWidth equal to clientWidth. Filter keyboard focus had a visible outline.
- Saved and inspected desktop board/drawer and mobile row/drawer screenshots in
  .playwright-mcp/tennis-polish-*.png. The mobile final drawer capture was retaken
  with screenshot animations disabled after the first capture caught entry motion.
- Browser console showed only a favicon.ico 404, with no observed app exception.
- Viewport emulation, click, and keyboard checks were performed. Physical touch,
  Safari, real phone/tablet hardware, and 200% browser zoom remain untested.
- No model outputs, ranking, recommendation gates, or provider filters changed.
  F-13 through F-16 remain fixed pending a later audit; this pass does not close
  its own repairs. Build checkboxes remain pending user review.

## Completion review, 2026-10-20

- User requested continuation after the passing implementation review packet.
  All three build steps are recorded complete based on the browser evidence.
- Focused quality audit re-reviewed all seven changed UI files and shared
  styles/derivations. No new findings; F-13 through F-16 closed explicitly.
  Existing F-09 and F-12 remain unverified modelling leads outside this change.
- Invariants review: clean for this diff. No model, probability, EV, tier,
  signal-rule, provider-filter, SQL, backend, secret, or request-path changes.
- Final safety pass: correct fix branch; all changed paths relate to this fix;
  Verify passed; behavioral proof and screenshots recorded; no workflow files
  changed and no blocking P0/P1 findings remain. No additional test run was
  needed after documentation-only review changes.
- No prototypes consumed. Employer guide unchanged because this UI disclosure
  and wrapping fix does not alter any project capability claim.
- Archive prepared before commit/merge approval. Nothing pushed or deployed.

## How to try

1. Open http://127.0.0.1:3002/false#/tennis/board.
2. Choose a market with reference rows and use Show reference lines, then Hide
   reference lines. Check the counts and Include reference lines switch agree.
3. Use View evidence on a row. Check matchup, CT start time, selected side/line,
   recent matches, and projection inputs. Try a narrow window and Escape close.

## Findings

### 2026-10-20-tennis-board-clarity/F-13 [P2] closed - Reference lines are hidden without market-level disclosure

**File:** web/src/pages/TennisPropBoardPage.tsx:20; web/src/pages/TennisPropBoardPage.tsx:55; web/src/components/tennis/TennisPropBoardControls.tsx:20
**Found:** 2026-10-20 by /audit and Impeccable audit (scope: tennis prop board; lens: UI quality)
**Why it matters:** The initial view excludes category.other, but market badges count only rateable rows. A market containing reference lines can show 0 and an empty table with no local count or reveal action. The global Lines summary counts both buckets. Moneyline reference rows always enter the other bucket. This obscures available information without changing its underlying classification.
**Suggested fix:** Keep actionable rows first, show each market's actionable and reference counts, and add a local reveal action when reference rows are hidden. Preserve recommendation gates, ranking, and the intentional Goblin exclusion.
**Resolution:** 2026-10-20, impeccable clarify: tabs now show ranked and reference
counts, summary labels distinguish availability from ranking, and a market-local
Show reference lines action enables the existing include-reference state.
Implementation repaired; browser verification and later audit review remain pending.

### 2026-10-20-tennis-board-clarity/F-14 [P2] closed - Mobile removes start times with no evidence-panel fallback

**File:** web/src/components/tennis/tennis-prop-table.css:69; web/src/components/tennis/TennisPropTable.tsx:25; web/src/components/tennis/TennisPropEvidencePanel.tsx:98
**Found:** 2026-10-20 by /audit and Impeccable audit (scope: tennis prop board; lens: responsive UI quality)
**Why it matters:** At widths up to 600px, the last small element in the player cell, the CT start time, is display:none. The evidence panel does not render startTime either. Phone users cannot retrieve that timing from either board surface, although it is present in the row model.
**Suggested fix:** Retain a wrapping CT start label in mobile rows and repeat it in the evidence header.
**Resolution:** 2026-10-20, impeccable adapt: removed the mobile display:none
rule, added an explicit wrapping start-time class to the row, and repeated the
existing CT-formatted start label in the evidence header. Browser/device
verification and later audit review remain pending.

### 2026-10-20-tennis-board-clarity/F-15 [P2] closed - Desktop evidence drawer suppresses its selected-line summary

**File:** web/src/pages/tennis-prop-board.css:46; web/src/pages/tennis-prop-board.css:339; web/src/components/tennis/TennisPropEvidencePanel.tsx:77
**Found:** 2026-10-20 by /audit and Impeccable audit (scope: tennis prop board; lens: UI quality)
**Why it matters:** The drawer's explicit side, line value, and EV summary is hidden above 768px. Its header repeats only player, market, and source. Some reason text and charts repeat part of the line context, but there is no consistent selected-line summary while reading evidence, especially when comparing several lines for one player.
**Suggested fix:** Make the selected-line summary visible at every viewport, with matchup and CT start time alongside it.
**Resolution:** 2026-10-20, impeccable adapt: renamed MobileSummary to LineSummary,
made it visible at all widths with flex wrapping, and included matchup and CT
timing in the evidence header. Existing side, value, and EV derivation is reused.
Long evidence context and historical opponent names wrap instead of truncating.
Browser/device verification and later audit review remain pending.

### 2026-10-20-tennis-board-clarity/F-16 [P2] closed - Evidence access lacks an explicit action label

**File:** web/src/components/tennis/TennisPropTable.tsx:21; web/src/components/tennis/TennisPropTable.tsx:65; web/src/components/tennis/TennisPropEvidencePanel.tsx:105
**Found:** 2026-10-20 by /audit and Impeccable audit (scope: tennis prop board; lens: UI quality)
**Why it matters:** Clicking a row or player name opens the only board access to recent-match history, serve/return comparison, projection inputs, and opponent averages. The button text contains only the player's name, so its purpose does not communicate that evidence is available. The existing player button is keyboard reachable; this finding concerns discoverability rather than a keyboard-access failure.
**Suggested fix:** Add an explicit View evidence action and a concise visible context summary, preserving detailed inputs in the drawer.
**Resolution:** 2026-10-20, impeccable clarify: each row now has a visible View
evidence button with player/market/line context in its accessible name. The panel
explains which evidence can be opened; the existing player button also names its
purpose. Detailed inputs remain in the existing drawer. Browser verification and
later audit review remain pending; this repair does not close itself.

## Tennis prop board UI audit evidence, 2026-10-20

Source review on master with no active spec. Reviewed TennisPropBoardPage, its controls, table, evidence panel, shared and page CSS, board/card derivations, related tests, and recent-form query. Focused on information visibility, responsive behavior, and interaction clarity; no backend/model/security review. No product source changed.

Browser capture was blocked: Playwright reported an occupied browser profile, and the computer-use inventory exposed no available browser. No screenshots, contrast measurements, rendered overflow checks, keyboard flow, touch gestures, or runtime performance measurements were obtained. Do not interpret the findings as a visually verified full-page audit.

Impeccable's bundled detector returned [] for the eight reviewed component/page/CSS targets. This does not detect the visibility and discovery issues above. Intentional Goblin filtering is covered by an existing test and is not a defect to reverse. Shared table ellipsis, hidden filter scrollbars, and touch-target sizing need browser verification before assigning additional defects.

Focused validation: npm.cmd --prefix web run test -- src/utils/tennisPropBoard.test.ts src/utils/tennisPropCards.test.ts passed, 2 files and 67 tests. The initial sandbox run failed during config resolution; the authorized retry outside the sandbox passed. No full Verify run was needed for this read-only product-source review.

**Repair verification follow-up, 2026-10-20:** After clarify/adapt/polish, the
user requested Playwright and the browser connected successfully to the local
board. This supersedes the earlier browser-pending notes for F-13 through F-16.
Confirmed reference-only reveal (0 to 57 rows), mixed-market hiding (46 to two
rows), source/tour selection, evidence access with click and keyboard Enter,
Escape close, CT time visibility at 320/390/768/1440px, and named evidence dialogs
with selected-line summaries on desktop and mobile. No horizontal page overflow
at those widths. Inspected saved screenshots, then repaired remaining clipped
provider/payout and break-even labels with scoped wrapping. Full Verify passed:
644 web tests, typecheck/build, and 3,455 API tests. Console showed only a missing
favicon 404. Physical touch, Safari, hardware, and 200% zoom were not tested.
The implementation pass left these fixed pending re-review. See the active spec
or its archived copy for screenshot paths and detailed proof.

**Focused audit re-review, 2026-10-20:** Closed F-13, F-14, F-15, and F-16 after
reviewing all seven changed UI files plus their shared table styles, propCard
derivation, and recent-form hook against the saved Playwright proof. Each original
defect is removed and no new defect was found in the repair. Reviewed disclosure
state, summary counts, scoped wrapping, keyboard actions, named dialogs, CT time,
and unchanged classification/ranking. This is a quality review of the tennis
board changes, not a full security, performance, or model audit. Base master and
HEAD share b309ce678fed390070cb86080524613d8c7a39fb; all work is uncommitted.
Dependencies, generated build output, and other sports were excluded. No source
changes followed the passing Verify results, so the gate was not repeated.
Invariants review is clean for this diff: no SQL, backend, model, version, signal
rule, secret, or request-path changes; new text sizes meet the 11px floor.
Existing F-09 and F-12 remain unverified and outside this repair's scope.

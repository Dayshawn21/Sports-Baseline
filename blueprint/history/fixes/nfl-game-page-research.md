# Refine NFL game-page research

**Type:** Fix
**Completed:** 2026-10-21 (local implementation)
**Branch:** `fix/hide-nfl-partial-game-tabs`

## The problem

The NFL game page offered first-half and first-quarter tabs despite using a
full-game model. Mobile injury/depth notes followed the entire prop board,
position buttons had narrow targets, recent-game values relied on hover,
secondary markets were expanded, and validation copy used internal terminology.

## The fix

The page explicitly requests full-game props and uses a static Full game label.
Partial-game data and underlying segment support remain. Mobile/tablet gets an
expandable player-availability summary before Props; desktop retains its sidebar.
Position buttons have at least 44px hit areas. Recent-game bars open a readable
list by pointer or keyboard, with values/opponents in the accessible button name.
Other markets starts collapsed with a count. The alternate-line toggle names its
scope; help distinguishes projection direction, ranks, quality and recommendations.
Palette, fonts, signal colors, probabilities, ranks, sorting, models and ingest
are unchanged.

## Build steps

- [x] Hide partial-game tabs and verify full-game primary and alternate rows.
- [x] Apply and verify the five user-approved Impeccable refinements.

The user approved completion by invoking `/complete` on 2026-10-21. Merge and
push require their own approval; neither is claimed here.

## Verification

- `npm.cmd --prefix web run verify`: typecheck, 701 tests in 51 files, and
  production build passed after the final source changes.
- From `api/`, `.venv\Scripts\python.exe -m pytest`: 3,611 passed. No API change.
- The `nflGameProps.test.ts` regression proves full-game primary and alternate
  rows exclude first-half and first-quarter segments.
- Chromium at `http://localhost:3001/#/nfl/game/94`: availability precedes Props
  on mobile/tablet; desktop retains its injury/depth sidebar. All six position
  targets measured at least 44 by 44px.
- Recent values open with Enter or click; Escape closes them without opening
  the player drawer. Values/opponents are visible oldest to newest.
- Other markets starts closed and expands with Enter to show six tables.
  Position and alternate-line controls work; partial-game labels stay absent.
- Help explains comparisons, ranks and data-quality labels. No horizontal page
  overflow at 320, 390, 900 or 1440px.
- Impeccable source detector: zero findings on changed markup. All five
  critique priorities were addressed and the critique snapshot closed.
- `git diff --check` passed. Final invariants review was clean: no backend or
  holdout changes, new signal colors, UI text below 11px, or secrets added.
  F-09 and F-12 remain unverified modelling leads in the ledger. No open or
  fixed P0/P1 finding blocks completion.

## Limits and maintenance

Physical-device and screen-reader runtime checks were not performed. Existing
Ant Design React 19 compatibility, Vite bundle-size and Python dependency
deprecation warnings remain; observed keyboard/click behavior passed.
Deployment is unverified.

Pre-existing `project-overview.md` edits are excluded from the work commit.
No employer-guide claim or build-plan item changes for this UI refinement.

## How to try it

Open `http://localhost:3001/#/nfl/game/94`. On a narrow viewport, expand Player
availability above Props. Choose a position, activate the last-five bars and
expand Other markets. Only full-game props appear; gray gaps remain research
comparisons.

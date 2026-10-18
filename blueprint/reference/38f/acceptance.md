# 38f acceptance review

**Verdict:** PASS, implementation and acceptance checks verified locally.
**Branch:** `feature/38f-shape-consistency`
**Date:** 2026-10-18, Central time.
**State:** accepted through `/complete`; archived and squash-merged locally into `master` with owner approval. Not pushed or deployed.

## What changed

- Slate and prop containers share the existing gray panels, borders and radius.
- NBA phone prop rows wrap so model values remain readable.
- Remaining NFL/tennis clock labels use CT, with safe unavailable-time fallbacks.
- Five detail pages use shared headings; supporting identity and availability remain.
- Detail browser titles use loaded names with generic unavailable-state fallbacks.
- Changed navigation paths have visible keyboard focus.

Backend data, probabilities, ranks, market filters, model versions and signal rules
are unchanged. Existing model-page headings already matched and needed no edits.

## Acceptance results

| Criterion | Result | Evidence |
|---|---|---|
| Shared slate and prop surfaces | PASS | Gray rgb(13,13,15), 14px radius across checked panels. |
| Responsive headings | PASS | One 34px h1 on every checked route; matching gutters at all widths. |
| Readable layouts | PASS | 39 page/width checks; no page overflow or rendered UI text below 11px. |
| Tennis controls | PASS | WTA filter, All reset, keyboard expansion, digest selection and 16 tournament groups. |
| Slate command search | PASS | Three sports, desktop/phone filtering, clear, Enter navigation and browser Back. |
| Evidence drawers | PASS | Both boards and both game pages, desktop/phone; focus, Enter/Escape, no overflow or small text. |
| Table scrolling | PASS | NFL and tennis player logs scroll locally without widening the page. |
| Times and retained context | PASS | Fixed winter/summer/midnight tests plus earlier final-score, profile and TBA checks. |
| Specific browser titles | PASS | All five kinds, missing/loading/error, retry, history and delayed responses. |
| Error recovery | PASS | Invalid route and controlled 503 retain generic heads; Retry restores PHI @ NY. |
| Diagnostics | PASS | Isolated live matrix: zero page errors and zero failed HTTP responses. |

The error-recovery fixture intentionally returns 503 in an isolated browser page;
it does not modify stored data. Dates and counts in screenshots reflect live data
at capture time. Earlier steps preserve additional edge-state evidence.

## Final captures

| Page | Desktop | Tablet | Phone |
|---|---|---|---|
| Tennis slate | [1440](final-tennis-slate-1440.png) | [1000](final-tennis-slate-1000.png) | [390](final-tennis-slate-390.png) |
| NFL slate | [1440](final-nfl-slate-1440.png) | [1000](final-nfl-slate-1000.png) | [390](final-nfl-slate-390.png) |
| NBA slate, Oct 20 | [1440](final-nba-slate-1440.png) | [1000](final-nba-slate-1000.png) | [390](final-nba-slate-390.png) |
| Tennis props | [1440](final-tennis-props-1440.png) | [1000](final-tennis-props-1000.png) | [390](final-tennis-props-390.png) |
| NFL props | [1440](final-nfl-props-1440.png) | [1000](final-nfl-props-1000.png) | [390](final-nfl-props-390.png) |
| Tennis model | [1440](final-tennis-model-1440.png) | [1000](final-tennis-model-1000.png) | [390](final-tennis-model-390.png) |
| NFL model | [1440](final-nfl-model-1440.png) | [1000](final-nfl-model-1000.png) | [390](final-nfl-model-390.png) |
| NBA model | [1440](final-nba-model-1440.png) | [1000](final-nba-model-1000.png) | [390](final-nba-model-390.png) |
| NFL game 91 | [1440](final-nfl-game-1440.png) | [1000](final-nfl-game-1000.png) | [390](final-nfl-game-390.png) |
| NBA game 21319 | [1440](final-nba-game-1440.png) | [1000](final-nba-game-1000.png) | [390](final-nba-game-390.png) |
| Tennis match 88732 | [1440](final-tennis-match-1440.png) | [1000](final-tennis-match-1000.png) | [390](final-tennis-match-390.png) |
| Tennis player 2415 | [1440](final-tennis-player-1440.png) | [1000](final-tennis-player-1000.png) | [390](final-tennis-player-390.png) |
| NFL player 40399 | [1440](final-nfl-player-1440.png) | [1000](final-nfl-player-1000.png) | [390](final-nfl-player-390.png) |

Other final captures include [tennis expansion](final-tennis-expanded-390.png),
[grouping](final-tennis-grouped-390.png), [NFL evidence](final-nfl-game-drawer-390.png),
[invalid route](final-invalid-390.png), [loading](final-loading-390.png) and
[controlled error](final-error-390.png).

## Automated verification

Run sequentially in PowerShell, matching the documented Verify halves:

1. `npm.cmd --prefix web run verify`: typecheck, 612 web tests and production build passed.
2. From `api/`, `.\.venv\Scripts\python.exe -m pytest -q`: 2,608 passed.
3. `git diff --check`: passed.

The existing large-bundle warning and Starlette/AnyIO deprecation warning remain.
Ledger F-02 is a pre-existing unverified P2 model finding outside this UI change;
no open/fixed P0/P1 is recorded. No employer-guide claim changed in this cosmetic feature.

## Manual review and next action

Open `http://localhost:3001/`, compare the three sport slates, open a game or player,
and check its heading and browser tab. On a prop board, press Tab to a player and
Enter to open evidence; Escape closes it. At phone width, try slate search and
horizontal scrolling inside a player game log.

The completed spec is archived at
`blueprint/history/features/38f-shape-consistency.md`. Feature 38f and parent 38
are checked off, and the active context is reset. The owner approved the local
squash merge into `master`; pushing still requires separate approval.

# Feature 43, Step 4 review evidence

Implemented and verified locally on 2026-10-22 on
`feature/nfl-matchup-usage-context`. Steps 1-3 approved; Step 4 awaits review.
Step 5 remains pending. No commit, shared writes, snapshot refresh, provider
calls, model changes, push or deployment.

## Changed files

| File | Purpose |
|---|---|
| `web/src/components/NflEvidencePanel.tsx` | Inserts the new context into the existing shared panel, retaining existing projection/evidence sections. |
| `web/src/components/nfl/NflEvidenceContext.tsx` | Renders recent/season usage and relevant opponent measures using the same game-context hook and metric component as the game page. Loading/error recovery is scoped to this section. |
| `web/src/utils/nflEvidenceContext.ts` | Pure position/market mapping and identity guards: validate game/line, unique roster player, position, home/away identities and historical team mapping. |
| `web/src/utils/nflEvidenceContext.test.ts` | 31 cases for receiving/RB rushing maps, omitted unsupported combinations, meaningful usage, identity mismatch, ambiguity and disabled queries. |
| `web/src/components/nfl/NflGameProps.tsx` | Resolves selection from current visible rows rather than retaining an old row object; clears selection on game/position/visibility changes and restores row-button focus. |
| `web/src/pages/NflPropBoardPage.tsx` | Clears selected line on week, season, position, market and game-filter changes; restores row-button focus. |
| `web/src/hooks/useNflDrawerFocus.ts` | Remembers the originating row button and restores connected-button focus after drawer close. |
| `web/src/components/nfl/NflPropTable.tsx` | Adds stable line identity on the existing row button so focus restoration can identify the opener. |
| `web/src/components/nfl/nfl-matchup-context.css` | Adds neutral drawer table styling; uses the drawer body as the single scroll surface instead of a second constrained inner evidence scroller. |
| `blueprint/context/current-feature.md` | Records Step 3 approval, Step 4 implementation/evidence and its pending review gate. |

`step-4.diff` is incremental from the approved Step 3 working state. It excludes
the earlier backend/game-page work and existing planning edits.

## Behavior and mapping

- Query reuse: `['nfl', 'game', gameId, 'context']`, five-minute stale time.
  A drawer with no valid selected line/game does not start a query. A different
  player reselects by stable player ID in the cached roster. Game metadata comes
  from the endpoint; no placeholder response from another game is accepted.
- Both game and board drawers use the same new component, typed response and
  metric renderer. Shares remain fractions until display formatting.
- RB/WR/TE receiving yards, receptions and Rec Targets show their position's
  receptions and receiving yards allowed. Rec Targets explicitly identifies
  this as receiving context; it does not invent targets allowed.
- RB rushing yards/attempts show RB carries and rushing yards allowed. QB
  passing/rushing, fantasy, TD and combo markets receive no fabricated matchup
  measure. Supported players can retain meaningful neutral usage: QB carries,
  carry share and average game snap share; RB/WR/TE also targets and target
  share. Other positions receive no new context section.
- Recent means the last up to three played games in the same pre-week season
  window, selected by the backend before filtering metrics. Every metric shows
  its own sample, coverage and contributing dates. Shares identify the recorded
  team denominators; snap share is explicitly the arithmetic game average.
  Historical team changes remain visible. No trend labels, delta sorting or
  signal colors were introduced.
- Unknown/ambiguous roster membership cannot inherit another player's context.
  No new drawer was added for line-only markets. Existing projections,
  probabilities, frozen versions and prop ordering remain untouched.

## Running-app check, Step 4 only

Reused the existing Vite and API servers with isolated headless Edge and the
already installed Playwright package. Browser interactions used real stored
2026 Week 7 data, then controlled response fixtures in separate browser contexts.
The raw result is `step-4-browser.json`; the reproduction driver is
`check-evidence-context-ui.cjs` (PLAYWRIGHT_MODULE points to an existing install).

| Done-when | Result and evidence |
|---|---|
| Game/board context parity | Pass. A.J. Brown receiving-yards drawer text is identical across both pages. Ten recent/season metric cells and two opponent values/ranks match the raw stored context. |
| Shared cache, no per-row query | Pass. One game-94 request across game-page context, its drawer, board navigation and same-game player changes. Fresh board fixtures issue no context request until a drawer is selected. |
| Player changes | Pass. Opening a second roster player selects that player's history from the same response without another context request. Pure guards reject mismatched/duplicate player membership. |
| Game changes | Pass. In-app navigation from game 94 to 95 with a drawer open closes the old selection. Pure guards reject another game ID, changed line/player/market or changed team identity. |
| Week/market changes | Pass. Controlled week-8 empty slate and return to week 7/receiving yards do not reopen a retained selection or fetch context for an unselected row. The fixture modifies only browser responses. |
| Relevant measures | Pass. Real RB rushing context shows only RB carries/rush yards. Real QB passing context omits targets and opponent receiving measures. Unit cases cover the remaining unsupported combinations. |
| Rec Targets | Pass with controlled fixture. Stored Week 7 slate currently contains no Rec Targets market. An isolated injected reference row preserves null probabilities and shows receiving context only, with the existing reference projection label. No shared snapshot was refreshed. |
| Loading/error isolation | Pass. A delayed or 503 context response leaves the original projection visible. Loading contains no retained metric rows. Manual retry recovers on the second request. |
| Missing roster | Pass. Explicit player-specific unavailable explanation with no fabricated zero or metric rows; existing evidence remains. |
| Desktop/mobile/neutral | Pass. Required viewport captures at 1440x1000 and 390x844. Mobile context client/scroll width both 388px, text minimum 11px, numeric color rgb(245,245,247). |
| Keyboard close/focus | Pass. Open with keyboard, Escape to close and focus back on the originating player button, on both pages and phone. Removed triggers are not focused. |

Required captures: `step-4-desktop-usage.png`, `step-4-desktop-opponent.png`,
`step-4-mobile-usage.png`, `step-4-mobile-opponent.png`. Each is an actual
viewport, with the drawer body scrolled to the named content. Supplemental:
loading, error, missing-roster and Rec Targets fixture captures in this directory.

The test now waits for actual drawer-enter animations to finish before closing
or capturing: the cached board response could otherwise close the drawer during
its preparation frame. Explicit focus restoration is bound to the selected row
button. The diagnostic `step-4-before.png` was taken during an opening transition
and is not final acceptance evidence.

No application JavaScript errors were observed. The existing favicon.ico 404
is recorded separately; the controlled context 503 is expected fixture behavior.

## Automated gate

Documented Verify command run as PowerShell halves:

1. `npm.cmd --prefix web run verify`: typecheck, 755 tests and production build
   pass (31 new pure mapping/identity cases).
2. From `api/`, `.venv\Scripts\python.exe -m pytest`: 3,669 pass.
3. `git diff --check`: pass.

Existing warnings: Vite's bundle-size advisory and Starlette's anyio alias
deprecation. No configured check skipped. Impeccable detector ran once on the
new component and context CSS: `[]`.

## How to try

Open `http://localhost:3001/#/nfl/game/94`, choose A.J. Brown under Receiving
yards, and scroll the drawer to Historical usage. Compare the same player's
Receiving yards row on `http://localhost:3001/#/nfl/board`. Check Recent and
Season, then CHI allowed vs WR. Escape should return focus to the row button.
Try an RB rushing row or QB passing row to see the position/market mapping.

Independent UI review: ship, no material fixes (see `step-4-ui-review.md`).
Documentation handoff confirms an ordinary extension with no system-document
changes needed. Step 5 still
owns broader current-data allocation/resource measurements, final feature
verification and the ignored employer interview guide update.

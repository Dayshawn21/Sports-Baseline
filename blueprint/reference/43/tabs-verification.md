# Owner-requested game-page tab split (Step 4a)

Implemented locally 2026-10-22, awaiting owner review. Step 4 and Step 5 retain
prior review state. No commit, deployment or shared writes.

| File | Change |
|---|---|
| NflGamePage.tsx | Ant Design tabs default to Player Props; shared header remains above. Matchup owns market/model, best line, line movement, team stats, position allowed and game notes. Props owns prop markets and roster usage. Destroy hidden panels closes old selections; game identity resets the default. |
| NflGameContext.tsx | Optional section selects matchup or usage while reusing the existing query; matchup loading/error retry retained. |
| nfl-game.css | Incumbent tokens, 44px tab targets, keyboard focus and pane spacing. |
| current-feature.md | Records owner-approved scope amendment as Step 4a, still awaiting review. |

Browser script `check-game-tabs.cjs` uses installed Playwright/Edge and read-only
local responses. `tabs-browser.json` proves default selection, content separation,
shared header, drawer opponent context, ArrowLeft/Enter switching, no resurrected
drawer, reset on game navigation and no horizontal overflow at 1440px and 390px.
No application JavaScript errors. Screenshots: `tabs-{1440,390}-{props,matchup}.png`.
Prior Step 3/4 screenshots remain historical evidence of their original layout.

Verify: `npm.cmd --prefix web run verify` passed typecheck, 755 web tests, build.
From api: `.venv\Scripts\python.exe -m pytest` passed 3,669 tests, one existing
Starlette deprecation. Existing Vite bundle-size advisory remains. First sandboxed
web run could not resolve config due filesystem restrictions; escalated run passed.
Detector ran once on three UI targets: `[]`. No new pure calculation logic added;
this UI composition is covered by browser acceptance checks.

Try http://localhost:3001/#/nfl/game/94. Player Props opens first; select Matchup
for team data. Use ArrowLeft/Right and Enter on the tabs. Prop-row drawers retain
historical usage and opponent context. Review incremental `tabs.diff`.

Independent review: all four required captures checked, no material fixes.
Documentation handoff: ordinary extension, no design-system edits needed; this
note is the updated manual path for the tab layout. Earlier step evidence is
historical. Final feature verification and employer-guide update remain Step 5.

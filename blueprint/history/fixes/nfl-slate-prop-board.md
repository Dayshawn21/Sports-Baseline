# Redesign the NFL Slate as a focused prop board

**Type:** Fix

## Design reference

Selected ImageGen direction 3: a game navigator beside a focused, edge-ranked
prop board.

## The fix

Rebuilt the NFL Slate around a selected game without changing the typed slate
query or projection model. The page now has a compact header, game navigator,
focused matchup workspace, and expandable model evidence.

## Build steps

- [x] **Step 1 - Create the selected-game workspace.** Added local game
  selection, a responsive game navigator, and a selected-matchup board.
- [x] **Step 2 - Focus the prop board.** Reduced visible columns to decision
  fields and moved model evidence into expandable rows.
- [x] **Step 3 - Apply the dark slate visual system and verify.** Added scoped
  responsive styling and verified desktop and narrow layouts with live Week 2
  data.

## Verify

- `npm run test` from `web/` - 56 passed.
- `npm run build` from `web/` - passed.
- Local `/nfl` with live Week 2 data - switching from DET @ BUF to CAR @ ATL
  immediately replaced the prop board.
- Row evidence - the Keon Coleman row expanded to show baseline, opponent,
  usage, line shape, and quality notes.
- Narrow viewport - 390px screenshot captured with the game navigator and prop
  board still reachable without page-level horizontal overflow.

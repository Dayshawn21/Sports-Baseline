# Redesign the Tennis intelligence page

**Type:** Fix

## The problem

The current Tennis landing page presents every match as an equally weighted card.
It makes the daily decision workflow harder than it needs to be: users must scan
across a dense grid to find the strongest opportunity, understand its evidence,
and open the relevant match analysis.

## The fix

Implement the selected matchup-command-center direction: a tournament and
match navigator beside one selected-match workspace. The workspace leads with the
matchup, its best opportunities, and compact model-versus-market evidence.
Existing filters, real query data, prop-source selection, quality flags, and the
player-comparison modal continue to work. The redesign stays responsive and uses
the app's existing dark visual system, without changing APIs or projection logic.

## Build steps

- [x] **Step 1 - Replace the match-card grid with a selected-match command
  center.** Add an accessible tournament or match navigator, select a match by
  default, and render its ranked bets, angles, and props as one scannable
  workspace.

- [x] **Step 2 - Preserve filters, analysis, and responsive behavior.** Keep
  filters and source notices working with the new layout, retain player
  comparison, and support the navigator on narrow screens.

- [x] **Step 3 - Surface match analysis in the workspace.** Show head-to-head,
  model breakdown, and key serve and return measures below the decision board.

## Verify

- `cd web && npm run test` - 61 tests passed.
- `cd web && npm run build` - passed.
- Browser check at `/#/` - navigator selection updates the workspace, inline
  analysis appears, the modal remains available, and the narrow layout does not
  overflow.

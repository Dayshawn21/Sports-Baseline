# Fit opponent names under the form chart bars at phone width

**Type:** Fix
**Completed:** 2026-11-11
**Branch:** `fix/form-chart-names` (worktree `.claude/worktrees/prop-reasons-66e160`)

## The problem

The shared recent form chart (`GameLogBars` in
`web/src/components/nfl/NflPropDetailSections.tsx`) prints each bar's opponent
under it in a grid whose columns may shrink to zero (`minmax(0, 1fr)` in
`web/src/components/shared/player-panel.css`), but the name has no overflow
rule. At 375px a ten-bar tennis chart gives each column about 28px, so long last
names ("Hanfmann", "Carreno-Busta") spill into their neighbours and overlap.
Found while checking feature 63's panel; the tennis player page's Last 10 chart
shows the same overlap (8 of 9 names overflowed on Alejandro Tabilo's aces tab).
NFL's three-letter team codes fit and are unaffected.

## The fix

- Each opponent label clips to its column with an ellipsis instead of spilling.
- The full name is on the label's `title`, so a pointer can still read it.
- The date line under the name is unchanged.

Display only: no data, API, model, rank or color change.

## Steps

- [x] **Step 1 - Clip the labels** - CSS on `.nfl-prop-detail__opps > span`
  (no wrap, hidden overflow, ellipsis) and a `title` with the opponent on the
  span in `GameLogBars`. *Done when:* at 375px no opponent label spills past
  its column on the feature 63 panel or the tennis player page's Last 10 chart,
  an NFL player page chart looks unchanged at desktop width, the console has no
  errors, and Verify passes.

## Testing

CSS and markup only, so no new unit test (the test gate covers logic). Proof is
a measurement of each label against its column at 375px, plus screenshots, and
Verify.

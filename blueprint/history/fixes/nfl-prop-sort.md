# Current Feature


# Improve NFL prop-board sorting

**Type:** Fix

## The problem

The selected-game board ranks both positive and negative edges by absolute gap.
Large under and over signals therefore interleave, and stale-baseline rows can
still lead the current screen when every line needs review. It is difficult to
answer the primary question: which comparable over or under should be examined
first?

## The fix

Add a local prop-board sort control, defaulting to **Best actionable**:

1. current-season, standard, full-game comparable overs by edge descending
2. current-season, standard, full-game comparable unders by absolute edge descending
3. stale-baseline comparable overs, then unders, in the same order
4. alternate or non-comparable lines last

Offer **Overs**, **Unders**, **Largest disagreement**, and **Player A-Z** without
changing the API response, projection math, quality flags, or pagination.

## Build steps

- [x] **Step 1 - Add deterministic client-side prop sort modes.** Create a pure
  sort helper with focused tests and wire a compact sort selector into the
  selected-game workspace.
  *Done when:* the default puts actionable overs before unders and stale or
  non-comparable rows, while every alternate sort is stable and predictable.

- [x] **Step 2 - Verify sorting against live slate data.** Build and test the
  web app, then switch sort modes in `/nfl` on a game containing comparable,
  stale, and alternate lines.
  *Done when:* the visible first rows match the selected sort mode, and row
  expansion plus game selection continue to work.

## Verify

- `cd web && npm run test`
- `cd web && npm run build`
- Open `/nfl`, change sort modes, switch games, and expand a prop row.

# Fix: Recent form chart did not use the full card width

**Type:** Fix
**Follow-up to:** item 51 and `nfl-chart-labels`
**Status:** complete (2026-11-02)

## The problem

A 40px left gutter reserved for the betting-line number kept the bars in the middle
of the card, and on phones the ten bars and their labels sat close together.

## The fix

- The gutter is removed; the bars and the dashed line run edge to edge.
- The line number moves out of the plot into a small key (`Line 238.5`) beside the
  Last 5 / Last 10 / vs Opponent switch; on narrow screens it wraps below. The
  switch buttons no longer wrap their text.

## Verify

- `npm --prefix web run verify` passed (tests, build); the API is untouched.
- Phone (375px) and desktop, Lamar Jackson passing yards, Last 10, against the
  hosted API: bars span the card, no sideways scroll, switch on one line.
- Built directly at the user's request; this note is its record.

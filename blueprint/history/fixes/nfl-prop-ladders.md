# NFL prop ladder decluttering

**Type:** Fix

## The problem

The NFL slate showed every PrizePicks alternate line as a separate table row.
That repeated the same player and market many times, making the board difficult to
scan. The alternate lines are useful context, but they should not compete with
the main line in the table.

## The fix

Keep all imported lines, but render one current standard line per player, market,
and selected period in the table. Put the remaining current alternate lines in a
compact section of that row's expanded evidence panel. If no standard line exists,
show the newest available line as the main row.

This preserves period filters, position grouping, sorting, and the existing
projection evidence. It does not change imports, stored history, or model edges.

## Build steps

- [x] Group slate lines in a tested web utility, selecting one main line and
  retaining deduplicated alternate lines for the expanded panel.
  - Done when a player-market appears once in the table and alternates remain
    available to the UI.
- [x] Render the compact alternate-line section in expanded NFL prop evidence.
  - Done when expanding a row clearly shows its Goblin, Demon, or other alternate
    lines without adding duplicate table rows.

## Verify

- `npm run test` from `web/` - 69 tests passed.
- `npm run build` from `web/` - passed.
- Manual review in `/nfl` - a standard Receiving Yards row expanded with its
  Goblin and Demon lines shown as compact tags.

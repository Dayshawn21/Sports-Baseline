# Fix: NBA board Last 5 column room and duplicate count

**Type:** Fix
**Status:** complete (2026-11-11)
**Branch:** `fix/nba-board-last5-room`
**Follows:** feature 62 (prop board row polish), `blueprint/history/features/62-prop-board-row-polish.md`

## Outcome

- Step 1 (`4b1586e6`): the modelled NBA `Sample` cell renders only its flag text; the `over N of M` line is gone on the board and the NBA game page.
- Step 2 (`91ee08c1`): `nba-board-table` columns Line 150 -> 120, Last 5 90 -> 135, Sample 160 -> 140. Measured on `/nba/props`: at 1280 Line 132px, Last 5 148px (from 98), Sample 154px; at 1880 197 / 222 / 230; no stat strip wider than its cell, no chip wrapped; the 1024px wrapped layout matches production row for row.
- Verify: `npm --prefix web run verify` (108 files, 1752 tests, build) and `pytest` with CI's dummy `DATABASE_URL` (6188 passed).
- Left as is: `NbaPropCard.count` and `overCount` are still built in `nbaProps.ts` but no longer read by the NBA UI; the line-only table's Recent column still repeats the strip.

## The problem

On `/nba/props` (live since `abde64cc`), two things in the modelled rows:

1. **Last 5 is the narrowest content column while Line has slack.** The board
   table is `table-layout: fixed` at 100% width, so the `nba-board-table`
   `<col>` widths in `web/src/components/nba/nba-prop-table.css` scale in
   proportion. Measured on the live board, 2026-11-11:

   | Viewport | Line | Last 5 | Sample |
   |---|---|---|---|
   | 1880 | 245px | 147px | 261px |
   | 1280 | 164px | 98px | 175px |

   At 1280 the Last 5 cell has about 78px inside its padding while the 62 stat
   strip (`L5 Avg Diff`) is about 127px wide, so it crowds or spills into the
   padding. Line was sized (150) for the old wall of alternates; since 62 it
   holds only `13.5 [+18 alts]` over `standard`, about 110px.

2. **The Sample cell repeats L5.** Its second line, `over 2 of 5`, says what the
   strip's `L5 2/5` beside it says. They can also disagree: Sample counts
   against the standard line only (`overAgainstStandard`), the strip against the
   main rung, so a goblin-only row shows `--` in one and `1/5` in the other.

## The fix

- Rebalance the `nba-board-table` column widths: Line 150 -> 120, Last 5
  90 -> 135, Sample 160 -> 140 (sum 1057 -> 1052, so the other columns keep
  their share). At 1280 that gives Line about 130px and Last 5 about 147px.
- Drop the `over N of M` line from the modelled `Sample` cell in
  `NbaPropTable.tsx`, keeping its first line (`flagText` or `Reference only`).
  The strip is now the one recent-games count on the row.

Must not break:

- The 1100px wrapped layout (`.nba-prop-table tbody tr.is-row` grid in the same
  CSS file); it ignores `<col>` widths, so it should be unaffected, but check.
- The NBA game page, which renders the same `Sample` through `NbaPropTable`:
  its count line goes too, which is intended (the strip is there as well).
- No change to data, `overAgainstStandard`, colors (all gray) or any other sport.

## Out of scope

- The line-only table's **Recent** column (`over N of M`) duplicates the strip
  the same way. Left as is unless you want it in this fix; removing it means
  dropping a column, a slightly bigger change.
- The game page's own `nba-prop-table` widths.

## Build steps

- [x] **Step 1 - Drop the duplicate count** - `Sample` in `NbaPropTable.tsx`
  renders only its first line. *Done when:* on `/nba/props` (Points) no modelled
  row shows `over N of 5` in Sample, every row still shows its flag text or
  `Reference only`, the strip still shows `L5`, and `npm --prefix web run
  build` passes.
- [x] **Step 2 - Rebalance the column widths** - the three `nba-board-table col`
  rules in `nba-prop-table.css`. *Done when:* at 1280 the Last 5 column is at
  least 140px and no stat strip is wider than its cell's content box
  (`scrollWidth` check across all rows); no Line cell wraps the chip onto a
  second line (Line cell content stays at two lines, number plus chip over
  `standard`); at 1880 the columns read balanced in a screenshot; the 1024px
  wrapped layout is unchanged; build passes.

## Verify

- `npm --prefix web run verify && cd api && python -m pytest` (API venv,
  CI's dummy `DATABASE_URL`).
- Browser on `/nba/props` at 1280, 1880 and 1024: the measurements above, plus
  screenshots. No new logic, so no new test; the existing suite must stay green.

# NFL props in kickoff order, unranked

**Type:** Fix

## The problem

The NFL prop rows are ordered by the size of the model's gap and carry a `#N`
rank on the prop board, game page and player page. No NFL slice has an `adopt`
verdict, and item 27h (the only thing allowed to rank NFL lines) is still open.
Through week 6, two of the four slices are finally rejected: standard unders
(53.7% of 419 against 57.7% break-even) and demon overs (39.4% of 289 against
41.3%).

The order therefore implies a recommendation the record does not support:

- Sorting on absolute gap lets a rejected-slice under take `#1`.
- v4 predicts a mean while lines sit near the median, so its gaps lean over.
- Gap share ignores payout and how volatile the stat is.

NBA, NHL and non-adopted tennis props are already gray and unranked. NFL is the
one board that is not.

## The fix

Order every NFL prop row by these keys, in this order:

1. Availability: clear, then Doubtful, then Out. This is about who plays, not a
   model claim.
2. Kickoff, earliest first, with an unknown kickoff last.
3. Player name, then line ID.

Use this one comparator for every NFL market, including Anytime TD and Rec
Targets, and for both the rateable and "show all" rows. Remove the rank from
the row data and the UI.

**Must not change:**

- Which lines are rateable, the Gap column and its reference line, projections,
  P(over), quality flags, gray colors, filters, or model versions.
- The dimming of non-rateable rows, which today is derived from a null rank.
- The "Largest gaps" digest. It is a separately labeled gray reference, and the
  NBA board, shared `SlateNoPicks` and home page use the same pattern. It
  re-sorts for itself, so `compareBoardTiers` and `edgeShare` stay.
- The API. `slate_line_rank` still orders each game's lines in `/nfl/slate`, but
  the web rebuilds its own order, so changing it would only force a stored
  snapshot refresh for no visible difference.

**When 27h adopts a slice,** ranking returns for that slice only, by margin over
break-even, as tennis does with `adoptedPick.margin`.

## Build steps

- [x] **Step 1 - Remove the NFL prop rank.** Drop `rank` from
  `NflRankedBoardLine` (rows become plain `NflBoardLine`), `nflGameProps`,
  `filterNflBoardCategories`, `playerWeekLines` in `nflPlayer.ts`,
  `NflPropTableRow`, `nflPropCard` and `NflPlayerPropSection`. In
  `NflPropTable`, remove the `#` column and its `col.is-rank` width, and move
  `prop-table__lead` to the player cell, as `NbaPropTable` does, so the phone
  layout still leads with the player. Remove the now-unused
  `.prop-table__rank` rule. Dim explicitly: a row in the `other` section whose
  kind is not `reference`. Replace the rank sentence in the `NflGameProps`
  legend with: rows follow kickoff, then player name, and are not ranked. Update
  comments and tests that mention ranks.
  *Done when:* no NFL prop row, game page or player page shows a `#N`, the same
  rows are dimmed as before, the filtered views still match, and web tests pass.
  Opponent and league ranks in team stats are untouched.

- [x] **Step 2 - Sort by availability, kickoff, then player.** Add one exported
  comparator in `nflPropBoard.ts` and use it for every market in
  `buildNflPropBoard`. Remove `compareBoardLines` and `compareAnytimeTdLines`,
  and replace their tests with: Out and Doubtful sort last whatever their
  kickoff or gap, earlier kickoff sorts first, a null or unparseable kickoff
  sorts last, a larger gap or an under never moves a row, and name then line ID
  break ties. Update `docs/SportApp-Employer-Interview-Guide.md` on disk if a
  passage describes NFL props as ranked (never stage it).
  *Done when:* a market's rows follow the three keys on the board and game page,
  the digest shows the same items as before on the same data, and web tests
  pass.

## Verify

- `npm --prefix web run verify && cd api && python -m pytest` from the repo root
  with the API venv active.
- Run the app and open the NFL prop board, a game page and a player page:
  - No `#N` on any prop row, and the first column is the player.
  - Rows go by kickoff, then player, with Doubtful and Out players last.
  - "Show all" rows are still dimmed, and Rec Targets rows are not.
  - The "Largest gaps" digest is unchanged.
  - At phone width, each row still leads with the player.
- Run `/invariants-review` before `/complete`, since this changes NFL ordering.

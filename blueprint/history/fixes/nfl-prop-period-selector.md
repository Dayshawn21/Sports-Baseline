# NFL prop-period selector

**Type:** Fix

## The problem

The weekly NFL matchup board combines full-game, half, and quarter PrizePicks
lines in one player-props table. That makes it difficult to scan the market
period actually being evaluated. Season-long lines do not belong in a selected
weekly matchup because the matchup context is not relevant to them.

## The fix

Add a compact prop-period selector above the selected game's player-props table:

- Full game, First half, and First quarter filter the selected game's lines.
- The visible line count and ranking use the active period.
- Full game remains the default.
- Full-season props stay out of this weekly matchup board. They will be a
  separate season-props surface when that view is intentionally scoped.

Do not change projection or ranking formulas, game selection, or the existing
matchup-context card.

Make the existing opponent-versus-position adjustment visible in the table so a
player's position can be evaluated against that matchup's defense at a glance.

## Build steps

### 1. Add the selected-game period filter [x]

- Identify the persisted NFL segment values and map them to the three weekly
  selector options.
- Filter the selected game's rows before sorting and render the active count.
- Add a focused test for the segment-filter helper and preserve the empty-state
  behavior when a selected period has no props.

**Done when:** a user can switch a selected matchup between Full game, First
half, and First quarter, with the table and count showing only that period's
lines.

### 2. Surface opponent-versus-position context [x]

- Add a compact `Vs Pos` column using the existing pre-week opponent adjustment
  and sample count.
- Put the opponent team code in each returned slate line so the column states
  which defense the position is facing.
- Keep the detailed explanation in the expanded evidence row.

**Done when:** every player row clearly shows the scheduled defense's
position-specific allowance adjustment or an honest unavailable state, without
changing the projection formula.

### 3. Show the defense's raw position average [x]

- Return the opponent defense's pre-week average for the row's market and
  player position.
- Display that average beneath the opponent adjustment and sample in `Vs Pos`.
- Use the existing market formatter so yards, receptions, and touchdown
  probability remain accurately labeled.

**Done when:** a WR row shows both the opponent defense's versus-WR average and
the bounded adjustment that the model uses.

## Verify

- Run the web tests and production build.
- Open `/nfl`, select a matchup, switch each available period, and confirm the
  table and line count update without changing the selected game.
- Confirm a WR row identifies the opposing defense and its pre-week versus-WR
  adjustment with the supporting sample.
- Confirm that row also shows the defense's raw average allowed for the same
  market.

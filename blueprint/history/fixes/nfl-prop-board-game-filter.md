# NFL Prop Board game filter

**Type:** Fix

## The problem

The NFL Prop Board can filter a weekly slate by position, but it cannot narrow
the ranked categories to one matchup. Finding every prop for a specific game
requires scanning the full week.

## The fix

Add an `All games` selector to the existing Board filters. Populate it from the
upcoming games that have prop lines for the selected season and week, label each
option by matchup and kickoff time, and filter the category rankings and selected
evidence to that game. Reset the game selection when season or week changes. Do
not add an API route or change projection and ranking rules.

## Build steps

1. [x] Add the typed game filter, its pure filtering coverage, and the Prop Board
   selector using the existing Ant Design and NFL label patterns.
   - Done when `All games` shows the full upcoming weekly board, choosing one
     matchup shows only players from that game across categories, and changing
     season or week safely returns to `All games`.

## Verify

- Open `/#/nfl/board`, choose a season and week with multiple upcoming games,
  select one matchup from the game filter, and confirm every visible row and the
  evidence panel belong to that matchup.
- Switch back to `All games` and confirm the weekly board returns.
- Run `cd web && npm run test` and `cd web && npm run build`.

## Completion evidence

- `cd web && npm run test` passed, 167 tests.
- `cd web && npm run build` passed.
- `/#/nfl/board`, 2026 week 3: `All games` showed 14 upcoming matchups and
  excluded the finished ATL @ GB game. Selecting NE @ JAX left only NE @ JAX
  rows in every category and in the evidence panel. Switching week 3 to 4 and
  back returned the selector to `All games`.

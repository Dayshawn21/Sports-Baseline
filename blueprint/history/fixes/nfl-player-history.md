# NFL player recent form and opponent history

**Type:** Fix

## The problem

The NFL prop-row evidence shows a season baseline and defense-versus-position
context, but not the individual player results behind either recent form or
history against the scheduled opponent.

## The fix

In each expanded player-prop row, add two read-only evidence blocks for that
row's exact market:

- **Last 5 games** - average plus the five most recent completed regular-season
  single-game values before the slate game, each labeled with the opponent.
- **Vs opponent** - average, completed-game count, and individual values from
  the player's prior regular-season games against the scheduled defense.

All values must be pre-game, remain descriptive only, and never change the
existing projection, adjustment, edge, or ranking formula. If history is absent,
show an explicit unavailable state rather than a zero or an invented average.

## Build steps

### 1. Return batched player game-history evidence [x]

- Add one repository query that collects both recent and scheduled-opponent
  completed regular-season stat values without an N+1 query per prop row.
- Map each prop market to its historic stat value and attach recent-five and
  opponent-history records to the slate-line response.
- Add focused tests for pre-game cutoff, opponent matching, ordering, and empty
  history.

**Done when:** a slate-line response contains the correctly ordered individual
values and descriptive averages for recent form and the scheduled opponent.

### 2. Render row-level form and opponent history [x]

- Add concise Last 5 games and Vs opponent blocks to the expanded NFL prop-row
  evidence area.
- Use the market formatter for the averages and show each individual value.
- Preserve a compact responsive layout and clear no-history state.

**Done when:** expanding a receiving-yards row shows its last five receiving
yard values and its prior receiving-yard values against that defense, without
altering the board's ranking.

### 3. Filter or group the board by position [x]

- Add compact All, QB, RB, WR, TE, and K controls that filter the active period
  without changing its sort mode.
- Add an optional Group by position switch for research mode; the default remains
  one globally ranked table.
- Keep the position controls compatible with period selection and the existing
  empty state.

**Done when:** a user can isolate a position or scan the same active rows under
position group headings without losing the global-ranking default.

## Verify

- Focused API tests: 66 passed.
- Full API suite: 770 passed.
- Full web suite: 66 passed.
- Production web build passed.
- Manual browser verification was unavailable in this completion session.

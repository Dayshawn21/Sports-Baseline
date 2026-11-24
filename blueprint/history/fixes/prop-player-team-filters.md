# Player and team filters on props boards and game pages

**Type:** Fix

## The problem

The props boards and game-page Props tabs list every player for a period, with no
way to find one player or one team.

| Page | Filters today | Missing |
|---|---|---|
| NFL board | position, game | player, team |
| NBA board | date, market | player, team, game |
| NHL board | date, market | player, team, game |
| Tennis board | source, tour | player |
| NFL game page | position | player, team |
| NBA game page | none | player, team |
| NHL game page | none | player, team |
| Tennis match page | player, market | nothing |

The top-bar search does not cover this: it jumps to a game or player, and is not
active on the boards.

## The fix

Web only. No API, schema, migration or model change. Every filter narrows rows the
page has already loaded.

**Shared pieces**

- `web/src/utils/propFilters.ts`, pure and tested:
  - `playerNameMatches(name, query)`: case-insensitive; strips accents (including
    letters NFD does not split, such as d-stroke and o-slash) and punctuation, so
    `doncic` finds the accented name and `aj brown` finds `A.J. Brown`. Every word
    of the query must appear somewhere in the name, so `brown aj` also matches.
    An empty query matches everyone.
  - `teamMatches(team, filter)`: `'all'` matches everything, including a null team.
    A specific team never matches a null team.
  - URL parsing for `q` (trimmed, at most 64 characters) and `team` (an uppercase
    code, otherwise `'all'`).
  - `gameTeams(games)`: the sorted, unique away and home codes for a period.
  - `gameSideTeam(team, game)`: the row's team as one of its game's two codes.
    Player rows carry PrizePicks' code and games carry the schedule source's code,
    and they differ (live 2026 week 10: `JAC` on rows, `JAX` on the game). An exact
    match wins; otherwise the game team sharing the longer code prefix, and null on
    a tie or no shared prefix. Every row team goes through this before filtering.
  - `visibleMarket(selected, markets)`: while a filter is active and the selected
    market has no rows, the first market that has rows. This never writes the URL,
    so clearing the filter returns to the market the user chose.
- `web/src/components/shared/PlayerSearchInput.tsx`: one clearable, labelled text
  input for every page.

**Boards**

- A team dropdown on NFL, NBA and NHL, listing `gameTeams` for the period. A `team`
  value that is not in the list reads as `'all'`.
- NBA and NHL get the game dropdown NFL has, as `game` in the URL.
- Choosing a game clears a team that is not in that game.
- Tennis gets the search box only.

**Game pages (NFL, NBA, NHL)**

A player search and an All / away / home toggle in the Props tab. They apply to both
modelled and other-market tables. The Matchup tab gets no filters.

**URL state**

`q`, `team` and `game` live in the search params and are written with
`{ replace: true }`, so typing does not add history entries and Back from a player
page restores the view. The existing tennis `source`, `tour` and `showAll` state
stays as it is. The previous and next date links on the NBA and NHL boards keep
building from date and market only, so a date change clears the filters.

**Must not break**

- **NFL rank stays the real rank.** The board numbers rows by position in the list
  (`index + 1`). Player and team filters apply after rank is assigned, so a filtered
  player keeps their board rank. `referenceLine` still comes from the unfiltered
  category. The existing position and game filters keep their current behavior.
- **Market pill counts follow the filters.**
- **Top-gaps digests and the page-head stats stay unfiltered.**
- **NFL modelled rows have no team field.** Add `nflLineTeam(line)`: the game team
  that is not `opponentTeam`, or null when the opponent is null or matches neither
  team. A null-team row shows under All teams and in player search, not under a
  specific team.
- **NFL other-market rows** need `team` carried from `NflLineOnlyLine` onto
  `NflLineOnlyRow`.
- **Filtering is display only.** No gray signal, rank eligibility or projection
  logic changes.

## Build steps

- [x] **1. Shared helper and input.** `propFilters.ts` with tests,
  `nflLineTeam` with tests, `PlayerSearchInput`.
  Done when: tests cover accents, punctuation, word order, an empty query, a null
  team, a bad URL value, and the NFL team derivation in all branches.
- [x] **2. NBA and NHL boards.** Search, team and game dropdowns, filtered pill
  counts, `visibleMarket`.
  Done when: `?q=`, `&team=` and `&game=` narrow the rows and survive Back from a
  player page, and the digest is unchanged.
- [x] **3. NFL board.** Search and team dropdown across modelled and other-market
  tables, with rank assigned before filtering (tested).
  Done when: a searched player shows the same rank as on the unfiltered board.
- [x] **4. Tennis board.** Search box with `q` in the URL.
  Done when: search narrows every source and tour combination and survives Back.
- [x] **5. Game pages.** Search and team toggle in the NFL, NBA and NHL Props tabs,
  with an empty-result message in each filtered section.
  Done when: both tables narrow together, and NFL ranks still read from the weekly
  board.

## Verify

- Run the Verify command: `npm --prefix web run verify && cd api && python -m pytest`.
- In the browser, on each of the seven pages:
  - Search an accented name without its accent.
  - Pick a team, or the away/home toggle.
  - Open a player, press Back, and confirm the filters are still applied.
  - Search for a player who has no line in the selected market, and confirm the page
    moves to a market that has one, then returns when the search is cleared.
  - Confirm the mobile layout has no horizontal scroll.

## Implementation notes

- `q` keeps a trailing space in the URL (leading space only is trimmed), because the
  URL is the search box's only state and a trimmed value made it impossible to type
  a space between names. Matching ignores surrounding whitespace.
- `playerPageOrigin` in `tennisPlayerProps.ts` only trusted an exact `/tennis/board`
  return address, so it now also accepts an encoded `?q=`. Anything else is still
  rejected.
- Changing the NFL board's season or week clears `q` and `team`, matching the NBA and
  NHL date links.
- The team list is every team playing in the period, per the spec. PrizePicks often
  posts only one side of a game (2026-11-10: BOS @ PHI had PHI rows only), so a team
  with no lines shows the no-match message.

## Evidence

- Verify, run as its two halves with the API venv and CI's placeholder `DATABASE_URL`:
  1,522 web tests, typecheck and build pass; 6,073 API tests pass.
- Browser, local dev server proxied read-only to the live API on 2026-11-10: all seven
  pages for search, team, game, market fallback, Back, no-match and phone width.
- Accent-insensitive matching is covered by unit tests, not by a live accented name.

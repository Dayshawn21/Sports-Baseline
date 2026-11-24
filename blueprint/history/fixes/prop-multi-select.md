# Multi-select player and game filters

**Type:** Fix

## The problem

The filters added in `prop-player-team-filters` narrow to one search term and one
game. There is no way to view several chosen players, or several games, together.

## The fix

Web only. No API, schema, migration or model change. Team stays single-choice.

| Page | Player | Game |
|---|---|---|
| NFL, NBA, NHL boards | multi-select | multi-select |
| Tennis board | multi-select | none |
| NFL, NBA, NHL game pages | multi-select | none (one game) |
| Tennis match page | unchanged | none |

**Player picker**

`web/src/components/shared/PlayerSearchInput.tsx` is replaced by `PlayerPicker`, an
Ant Design `Select` in `mode="multiple"` with type-to-search. Each chosen player is a
removable chip, and `maxTagCount="responsive"` keeps the row to one line. Typing
filters the options with the existing accent- and punctuation-insensitive
`playerNameMatches`, so `doncic` still finds the accented name. This replaces free-text
partial matching: a player is chosen from the list before rows narrow.

**Selection is by player name**, not id. Tennis moneyline and Win a Set rows have a
null `playerId`, and a name works for every sport and row type on a page.

**Shared logic in `web/src/utils/propFilters.ts`, pure and tested**

- `parsePlayerFilter(params)`: repeated `player` params, each at most 64 characters,
  at most 20, duplicates dropped. Replaces `q`, which the new code ignores.
- `parseGameFilters(params)`: repeated `game` params, positive integers only.
  `activeGameFilters` drops ids not in the period.
- `playerSelected(name, players)`: an empty selection matches everyone; otherwise an
  exact match after the existing name normalization.
- `playerOptions(rows, players)`: sorted unique names on the page, always including
  anything already chosen so a chip never loses its label.
- `teamAfterGames(team, games, allGames)`: keeps the team only when it plays in one of
  the chosen games; no chosen games keeps it.

Rows must match a chosen player, the team, and a chosen game. Picker options respect
the team and game filters, so choosing Boston lists Boston players.

**URL state**

Repeated params, for example `?player=Joe+Burrow&player=Tee+Higgins&game=145&game=146`,
written with `{ replace: true }` so Back from a player page restores the view. Tennis
`playerPageOrigin` accepts encoded repeated `player` params and still rejects anything
else, and `tennisBoardPath` builds them.

**Must not break** (carried over from the previous fix)

- NFL rows keep their full-board rank under player and team filters. The game filter
  keeps today's behavior, ranking within the chosen games.
- Row team codes still resolve through `gameSideTeam`, and NFL modelled rows through
  `nflLineTeam`.
- Market pill counts follow the filters, and `visibleMarket` moves off an emptied
  market without changing the URL.
- Top-gaps digests and page-head stats stay unfiltered.
- Date, season and week changes clear the filters.
- Filtering is display only.

## Build steps

- [x] **1. Shared logic and picker.** The `propFilters.ts` changes with tests, and
  `PlayerPicker`.
  Done when: tests cover parsing limits, bad values, duplicates, exact-name selection
  with accents, an empty selection, options keeping chosen names, and `teamAfterGames`.
- [x] **2. NBA and NHL boards.** `PlayerPicker`, multi-select game dropdown, row
  filtering.
  Done when: two players and two games narrow the rows and survive Back from a player
  page.
- [x] **3. NFL board.** Same, across modelled and other-market tables.
  Done when: chosen players show the same ranks as the unfiltered board.
- [x] **4. Tennis board.** `PlayerPicker` and the `playerPageOrigin` return address.
  Done when: chosen players survive the crumb back from a player page, and moneyline
  rows with a null `playerId` can be chosen.
- [x] **5. Game pages.** `PlayerPicker` on the NFL, NBA and NHL Props tabs, with options
  from both the modelled and other-market rows.
  Done when: both tables narrow together, and NFL ranks still read from the weekly
  board.

## Verify

- Run the Verify command: `npm --prefix web run verify && cd api && python -m pytest`.
- In the browser, on each of the seven pages:
  - Type an accented name without its accent and choose it, then add a second player.
  - Choose two games on the NFL, NBA and NHL boards.
  - Remove a chip and confirm its rows return.
  - Open a player, press Back, and confirm the selections are still applied.
  - Choose a player with no line in the selected market, and confirm the page moves to a
    market that has one.
  - Confirm the phone layout has no horizontal scroll with several chips chosen.

## Implementation notes

- `PlayerSearchInput` and the `q` helpers stayed in place until step 5, so each page
  kept working as it moved over, and were then deleted.
- Picker options narrow with the team and game filters, and on the NFL pages exclude
  hidden alternate and thin-sample lines until "Show all lines" is on.
- Choosing games on the NFL board re-ranks within those games, as the single game
  filter already did. Player and team filters never change a rank.
- Old `q` links read as no player filter.

## Evidence

- Verify, run as its two halves with the API venv and CI's placeholder `DATABASE_URL`:
  1,541 web tests, typecheck and build pass; 6,073 API tests pass.
- Browser, local dev server proxied read-only to the live API on 2026-11-10: picker
  typing and Enter on the NBA, NHL, NFL and tennis boards and the NBA game page; URL
  selections on the NFL and NHL game pages; two games at once; chip removal; team
  clearing; market fallback; Back; moneyline rows with a null `playerId`; phone width.
- Accented names typed without accents were confirmed live on the NHL board.

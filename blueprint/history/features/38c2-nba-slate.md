# Feature: NBA slate on the shared shape

**From build-plan:** feature 38c2
**Status:** complete (2026-10-17)

## Goal

`/nba` takes the shape the NFL (38b) and tennis (38c1) slates already have: a
gray digest of the day's largest projection gaps above one dense table row per
game, each row opening the game page. Display only. The digest is the one place
an NBA gap is sorted, a narrow exception to 20g2 that the game page and props
do not share.

## Design reference

- The direction contract `.impeccable/surfaces/web-src-pages-nflintelligencepage-tsx.md`
  and the chosen sketch `.impeccable/mocks/decision/command.html` (item 38).
- The shipped shape to match: the NFL slate (`NflSlateDigest`, `NflSlateTable`,
  `nfl-slate-table.css`) and the shared `SlateDigest` strip.

## In scope

- **Digest:** a gray "Largest gaps today · reference, not picks" strip of up
  to 4 boxes (player, market, matchup, line, model, gap). Each box opens the
  game page. It is hidden when no line qualifies, and hidden quietly if its
  request fails, so the table still renders.
- **The digest rule (load-bearing, fixed here):**
  - Lines: linked, full-game, modelled, **standard** `odds_type`, with a
    non-null projection and a positive line.
  - Games: only those **not yet tipped** (`start_utc > now`, status
    `scheduled`) on the slate's date.
  - Rank: by `|gap| / line`, descending. Ties break on player name, then
    market, then game id.
  - One line per player (their top-ranked one), up to 4.
  - The numbers come from the same `props_response` / `project_line` path as
    `GET /nba/games/{id}/props`, so a digest box never disagrees with the game page.
- **API:** a sibling `GET /nba/slate/gaps?date=YYYY-MM-DD` (date required).
  The slate response stays as it is, so the slate request does no projection
  work.
- **Table:** one row per game, sorted by tip time, in a single table (one
  date, so no kickoff windows). The columns are:

  | Column | Content |
  |---|---|
  | Tip | Central clock, or Final, Postponed or Canceled |
  | Game | Codes and records, or the score once final |
  | Spread | Line plus "opened ..."; once final, the close and its result |
  | Total | The same, for the total |
  | Moneyline | Favorite first, the other price below; "--" once final |
  | Win | Market de-vigged home/away %, muted |
  | Props | Count of stored prop lines |
  | Notes | A "Tipped off" tag, and "Scores load the morning after" once tipped |

  - A row click and the Game link both open `/nba/game/:gameId`.
  - At 1100px and below, rows go to two lines, as the NFL table does.
- **Legend:** replace the stale "No model yet" line. Since 20g2 NBA has a gray
  reference projection, so the legend now says gaps are reference, not picks.
- **Cleanup:** delete `NbaSlateGameCard`. Trim `nfl-slate-card.css` to the
  rules still read (the row tags and `__live`), and drop `nfl-slate-grid` if
  nothing else uses it.

## Out of scope

- Changes to the game page or its props (38d makes props into rows). The NBA
  game page keeps reading `nbaSlateCard` (20e's load-bearing rule).
- Any edge, P(over) in the digest, color, pick, or sort outside the digest.
- An NBA prop board (`/nba/board`), and the command field (38e).
- `SPORT_STATUS` on How it works: no sport's picks change.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Digest ranking rule (API, pure)** - `rank_slate_gaps` in a new
  `app/core/nba_slate_gaps.py`. It takes candidate lines (game id, tip time,
  status, player, market, odds type, line, projection, gap) and `now`, and
  returns the top `limit` under the digest rule above. *Done when:*
  `tests/test_nba_slate_gaps.py` covers standard-only, a null projection
  dropped, started and non-scheduled games dropped, ranking by |gap| / line
  (not raw gap), one per player, the tie order and the limit, and `pytest` passes.
- [x] **Step 2 - `GET /nba/slate/gaps` (API)** - add `NbaSlateGapsResponse`
  (`date`, `modelVersion`, `items`) and `NbaSlateGapSchema` (`gameId`,
  `awayTeam`, `homeTeam`, `playerId`, `playerName`, `market`, `line`,
  `projection`, `gap`, `gapShare`) in `app/schemas/nba.py`. A service
  `app/services/nba/slate_gaps.py` gets the date's games (`get_games_on`),
  each upcoming game's `get_modelled_lines`, and one `get_prior_games` for
  every player (one date, so one cutoff). It projects through
  `props_response` and ranks with Step 1, and the router stays thin.
  *Done when:*
  - a service test pins that each item's projection and gap equal the
    `props_response` line for the same game and player
  - `curl /nba/slate/gaps?date=<next game date>` returns up to 4 items
  - a date with no games returns `items: []`
  - a malformed date is a 422
  - a cold call answers within about 2 s locally (timed and recorded)
- [x] **Step 3 - Digest on the page (web)** - `NbaSlateGap` types,
  `fetchNbaSlateGaps`, a `useNbaSlateGaps(date)` hook (enabled once the slate
  resolves its date, `staleTime` 5 minutes), `nbaSlateDigest(items)` display
  strings in `utils/nbaSlate.ts`, and an `NbaSlateDigest` component on
  `SlateDigest`. Update the legend. *Done when:*
  - `nbaSlate.test.ts` covers the strings: signed gap, line and model to one
    decimal, the "AWAY @ HOME" matchup, market labels from `nbaLineOnly`
  - on `/nba` the strip shows above the cards, every number in it is gray,
    and each box opens its game page
  - a date whose games have all tipped shows no strip
  - `npm run build` passes
- [x] **Step 4 - Game table (web)** - `nbaSlateRow(card)`, built from
  `NbaSlateCardModel` so the row and the game page hero share one state and
  final rule, plus `NbaSlateTable` (reusing the `nfl-slate-table` classes,
  with NBA column widths in `nba-slate-table.css`). Replace the card grid,
  then delete `NbaSlateGameCard` and the dead card CSS. *Done when:*
  - tests cover upcoming, started, final (close and result, no moneyline)
    and postponed rows
  - on `/nba` each game is one row, and a row click and the Game link both
    open the game page
  - the final and postponed states read as the cards did
  - at 390px the rows are two lines with no horizontal scroll
  - the NFL slate's tags still render
  - Verify passes

## Files / areas

- **API:**
  - new: `app/core/nba_slate_gaps.py`, `app/services/nba/slate_gaps.py`,
    `tests/test_nba_slate_gaps.py` and a service test
  - changed: `app/schemas/nba.py`, `app/routers/nba.py`
- **Web:**
  - new: `components/nba/NbaSlateDigest.tsx`, `components/nba/NbaSlateTable.tsx`,
    `components/nba/nba-slate-table.css`
  - changed: `types/nba.ts`, `api/nba.ts`, `hooks/useNba.ts`,
    `utils/nbaSlate.ts` (+ test), `pages/NbaSlatePage.tsx`,
    `components/nfl/nfl-slate-card.css`, possibly `pages/nfl-slate.css`
  - deleted: `components/nba/NbaSlateGameCard.tsx`

## Data / contracts

- **No schema change, no migration.**
- **Load-bearing:**
  - **`GET /nba/slate/gaps?date=`** and `NbaSlateGapsResponse` (camelCase)
    are the NBA digest's one source. 38e's command field may read its
    items. Later NBA slate-level display extends this response or the slate
    response, never a third.
  - **The digest rule above.** Changing it is a ranking change, as 38b fixed
    for the NFL digest order.
  - **`nbaSlateRow`** (`NbaSlateRowModel`, display strings keyed by
    `gameId`) is the row model 38e filters, as `nflSlateRow` is for NFL.
- **Unchanged:** `NbaSlateResponse`, `NbaPropsResponse`, `nbaSlateCard`.

## Testing

- **pytest:**
  - Step 1's pure rule
  - Step 2's parity with `props_response`, with fake repository rows and no
    database, as the CI rule requires
- **Vitest:** `nbaSlateDigest` and `nbaSlateRow` in `utils/nbaSlate.test.ts`,
  with a fixed `NOW`.
- **No component tests.** The page, digest and table ride on browser evidence
  at `/nba` (desktop and 390px) and the build.
- **Final gate:** `npm --prefix web run verify && cd api && python -m pytest`.

## Notes for the AI

- **Gray only.** The digest sits under `.nfl-slate`, where the green and red
  variables are the text color. Never add `is-positive`. The label says
  "reference, not picks".
- **Sport and game-type filters:** every query goes through the existing
  `nba_repo` functions, which already filter `sport = 'nba'` and the served
  game types. Add no new SQL unless a step needs it. If one does, it carries
  both filters, and `PRE` is never served.
- **Odds providers:** the slate's market stays on `the_odds_api_us` rows, as it
  does today. This feature reads no new odds.
- **Shared modules:** no new imports from `sport_registry` in shared prop
  modules. The new core module imports nothing from `app/services`.
- **Render memory:** the gaps request loads at most 20 prior games per player
  for one date's players (`REFERENCE_GAMES`), which is small. It is on the
  default rate limit, not the heavy one. If Step 2's timing is far over 2 s,
  stop and report instead of adding a snapshot.
- **Times are Central** on the web. The API's "today" is the Eastern date, and
  `date` here is always the slate's resolved date.
- Follow `coding-standards.md`: routers thin, SQL only in repositories, `core/`
  pure, no em dashes, comments only for the why.

## Outcome (2026-10-17)

- **Verify:** `npm --prefix web run verify && cd api && python -m pytest` passed
  (546 web tests and the web build; 2608 API tests, 11 of them new).
- **Endpoint** (branch API on port 8001, against the shared Neon database):
  - `?date=2026-10-20` (3 games): 4 items, 1.29 s cold, 0.41 s warm
  - `?date=2026-10-21`: 1 item, 0.86 s cold
  - a date with no games returned `items: []`, and a malformed or missing date
    returned 422
  - game 21319's top lines on `/nba/games/21319/props` matched the digest exactly
- **First digest, 2026-10-20:** Towns blocks 0.5 to 1.2 (+140%), Harris
  points 11.5 to 16.4 (+43%), Brown points 20.5 to 28.75 (+40%),
  Gilgeous-Alexander blocks 0.5 to 0.7 (+40%). Ranking by |gap| / line lets
  half-point lines lead. That is the rule as planned; changing it is a
  ranking change.
- **Browser** (dev server on port 3005 proxying to that API):
  - the strip sits above the legend and table and uses only text grays
  - a box and a row both open the game page
  - 2026-04-10 (15 finals) shows no strip, and finals read Final with scores
  - a 404 from the gaps request hid only the strip
  - 1440px: one 52px row per game, at fixed column widths
  - 390px: two lines per game with no horizontal scroll, once the Game cell
    truncates the pre-season records
  - the NFL table's tags still render
- **Found on the way:** Ant Design's global `a:hover` (0,1,1) outranked
  `.slate-digest__play` and turned a hovered link box dark blue, which had
  affected the NFL digest since 38b. `.slate-digest__play:hover` now restates
  the text color.
- **Proven by unit tests only:** postponed, canceled and tipped-off rows. No
  stored date holds one yet.
- **Follow-ups:**
  - `nfl-slate-card.css` now holds only the table tags and live marker, so its
    name is out of date.
  - `project-overview.md` still describes `/nba` as cards, so regenerate it
    with `/overview`.

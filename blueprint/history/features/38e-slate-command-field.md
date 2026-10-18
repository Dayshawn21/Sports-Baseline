# Feature: Slate command field

**From build-plan:** feature 38e
**Status:** implementation complete
**Completed:** 2026-10-17

## Goal

Add a keyboard-first command field to the shared top bar on the Tennis, NFL,
and NBA slate routes. It filters the slate rows already loaded in the browser
and offers direct match, game, team, and player jump targets without fetching
search data or changing any model order, rank, or signal.

## Design reference

- `.impeccable/surfaces/web-src-pages-nflintelligencepage-tsx.md` defines the
  search-first ledger direction, the `/` shortcut, the 620px desktop field,
  and the expanding phone control.
- `.impeccable/mocks/decision/command.html` is the chosen command-bar sketch.
- The shipped Lineform tokens in `web/src/index.css` remain authoritative.
  There is no `prototypes/` directory to port or discard.

## In scope

- Show the command field only on the three slate routes: `/`, `/nfl`, and
  `/nba`. Non-slate pages keep their current top bar and do not pretend to have
  a global index when no slate data is loaded.
- On desktop, place a field between the sport tabs and view navigation, up to
  620px wide. `/` focuses it unless focus is already in an input, textarea,
  select, or editable element, or a modifier key is held.
- On phones, show a search button in the header. Activating it replaces the
  normal header controls with a full-width field and close control. Escape
  clears first, then collapses the phone field when already empty.
- Use only data already returned to the active slate page:

  | Slate | Searchable rows and jump targets |
  |---|---|
  | Tennis | Visible match rows, both player names, tournament, and tour. Match results open `/tennis/match/:matchId`; players with IDs open `/tennis/player/:playerId`. |
  | NFL | Current week games, team codes, and players present in each game's loaded prop lines. Games and teams open `/nfl/game/:gameId`; players open `/nfl/player/:playerId`. |
  | NBA | Current date games, team codes and names, plus players present in the already loaded slate-gap digest. Games, teams, and players open `/nba/game/:gameId`, because no NBA player route exists. |

- Define one load-bearing client contract for registered command rows and
  targets. Each row has a stable row key, its game or match path, normalized
  search terms, and ordered targets with a kind, label, context, and path.
- Match case-insensitively after trimming and collapsing whitespace. Every
  whitespace-separated query token must occur in the target's searchable text.
  Do not add fuzzy scoring, remote suggestions, or signal-based ordering.
- Preserve the slate's current row order. A query only removes non-matching
  rows. Results follow row order, with the match or game first and de-duplicated
  team and player targets after it.
- While typing, filter only the table rows and their tournament or kickoff
  groups. Summary chips, plays digests, model values, ranks, and signal colors
  continue to describe the full period and remain unchanged.
- Tennis search runs after its existing date, tour, source, upcoming, Lean, and
  sort controls. A non-empty command searches across the local tour tabs without
  permanently changing the selected tab; clearing restores that tab.
- Enter from the field opens the first matching match or game in existing slate
  order, even when the text matched a team or player target. Clicking a listed
  target opens that target's own path.
- Use an accessible combobox and result list. Results identify their kind and
  context, keyboard focus is visible, and empty queries do not open a result
  list. A non-empty query with no match shows a clear no-results state in both
  the command field and the table area.
- Clear the command query and registered targets when the route changes. Also
  clear it when Tennis date/filter source, NFL season/week, or NBA date changes,
  so a new period cannot inherit a stale hidden-row filter.
- Loading leaves the slate command unavailable until rows register. Existing
  loading, request failure, and truly empty-slate states remain authoritative.
  Typing, clearing, opening, and closing the command make no API request.
- Keep the 11px text floor and the current neutral shell styling. Search state
  never introduces green, red, or another signal color.

## Out of scope

- A server-side, cross-period, cross-sport, or site-wide search endpoint.
- Search on prop boards, model pages, detail pages, How it works, or Admin.
- Loading a slate in the background from a non-slate route.
- Fuzzy ranking, recent searches, command history, aliases not present in the
  loaded response, or persistence in the URL or browser storage.
- A new NBA player page or team page. NBA player and all team targets open the
  containing game.
- Any change to data fetching, API schemas, projection math, probability, gap,
  rank, recommendation, sort, digest order, or signal color.
- The broader page-head, `h1`, and time-label consistency work in 38f.
- Re-activating parked or evidence-gated items 16f, 25c, or 27h.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Command model and local state foundation (web)** - add the
  typed command-row contract, pure normalization, matching, de-duplication, and
  first-match helpers, plus a provider and registration hook for page-owned
  loaded data. *Done when:*
  - unit tests prove case and whitespace normalization, all-token matching,
    stable row order, target de-duplication, player-to-parent-row matching,
    first-match selection, and clean empty/no-match behavior
  - the provider holds UI state only; TanStack Query remains the owner of all
    server data, and registering or changing a query performs no request
  - changing the route or registered period key clears stale query and targets
  - the app builds and existing navigation behavior is unchanged

- [x] **Step 2 - Desktop command field and Tennis slate (web)** - render the
  desktop combobox in the shared shell and register Tennis rows, match targets,
  and player targets from `SlateRow` data. Filter the Tennis table with the
  shared matcher. *Done when:*
  - `/` focuses the field from ordinary page focus but does not hijack editable
    controls or modified shortcuts; Escape clears it
  - typing a player, matchup, tournament, or tour filters the table without
    reordering it, and search spans all local tour tabs only while non-empty
  - the result list exposes match and valid player destinations; clicking one
    opens its path, while Enter opens the first matching match
  - clearing restores the prior tour tab and full row set; a no-match query has
    explicit field and table empty states
  - the Tennis summary and digest do not change, and browser network evidence
    shows typing and clearing make no request
  - focused utility tests, `npm run build`, and `npm run test` pass

- [x] **Step 3 - NFL and NBA slate registration and filtering (web)** - add
  command rows for the current NFL week and NBA date, reusing their already
  loaded games, NFL prop lines, and NBA gap digest. *Done when:*
  - NFL queries match game pairings, either team code, or a prop player; empty
    kickoff windows disappear, remaining games keep their original order, and
    Enter opens the first matching game
  - NFL player results open the existing player route; team results open the
    containing game; duplicate player lines produce one player target per game
  - NBA queries match team code, full team name, or a digest player; player and
    team results open the containing game, with duplicate digest players removed
  - an NBA digest failure removes only digest-player targets: game and team
    search remains usable, matching the page's existing independent failure rule
  - period changes clear the query; summaries and digests remain unfiltered;
    typing and clearing make no request
  - focused utility tests, `npm run build`, and `npm run test` pass

- [x] **Step 4 - Phone interaction and final accessibility pass (web)** - add
  the compact search button, full-width expanded phone field, result-list
  polish, focus restoration, and final cross-sport browser verification.
  *Done when:*
  - at 1440px the command field uses available header space up to 620px without
    displacing sport or view navigation, and results stay inside the viewport
  - at 390px the button expands to a full-width field, focus moves into it,
    Escape and the close control restore the normal header, and there is no
    horizontal page scroll or text below 11px
  - the combobox exposes an accessible name, expanded state, controlled result
    list, active result, and result count or no-match status; mouse and keyboard
    paths open the same destinations
  - direct loads, loading, request failures, truly empty slates, no-match
    queries, browser back/forward, and route changes leave no stale command
    state or blank page
  - Playwright evidence covers Tennis, NFL, and NBA at desktop and phone widths,
    and confirms command interactions add no network request
  - Verify passes

## Files / areas

- **Web, new:** `web/src/utils/slateCommand.ts`,
  `web/src/utils/slateCommand.test.ts`,
  `web/src/components/shared/SlateCommandProvider.tsx`,
  `web/src/components/shared/SlateCommandField.tsx`, and
  `web/src/components/shared/slate-command.css`.
- **Web, changed:** `web/src/App.tsx`,
  `web/src/pages/TennisIntelligencePage.tsx`,
  `web/src/pages/NflIntelligencePage.tsx`,
  `web/src/pages/NbaSlatePage.tsx`, and, only when needed for explicit filtered
  empty copy, the three slate-table components.
- **Web, reused:** current `SlateRow`, `NflSlateGame`, `NbaSlateGame`,
  `NbaSlateGap`, sport navigation, route paths, loaded query results, and shell
  tokens.
- **No API, database, ingest, model, or schema change.**

## Data / contracts

- No server contract changes. Command data is derived in memory from responses
  the active page already owns.
- **Load-bearing:** `SlateCommandRow` keeps one stable row key, a match/game
  destination, normalized searchable terms, and ordered `SlateCommandTarget`
  entries. A target has a stable key, `match`, `game`, `team`, or `player` kind,
  a label, context, its own destination, and the parent row destination.
- **Load-bearing:** target matching returns row keys in registration order and
  never sorts by target kind, gap, probability, props, rank, or recommendation.
- **Load-bearing:** Enter uses the first matched row's parent destination.
  Clicking a result uses that target's destination. Invalid or missing IDs never
  create broken player or match links.
- **Load-bearing:** the registered scope includes a period key. Changing it or
  leaving a slate resets the query and result state.
- React context owns ephemeral command UI state. TanStack Query continues to
  own all server state and request lifecycle.

## Testing

- Add Vitest coverage for normalization, multi-token matching, stable filtering,
  target de-duplication, first-row selection, each sport's target mapping,
  invalid IDs, NBA digest-player fallback, and empty results.
- Do not add React component tests. Verify focus, combobox semantics, navigation,
  filtering, responsive expansion, route cleanup, and request-free interaction
  in the running app.
- At 1440px and 390px, test a Tennis player and tournament, an NFL team and prop
  player, and an NBA full team name and digest player. Compare the surviving row
  order with the unfiltered slate.
- Capture browser network requests before and after typing, clearing, selecting,
  and escaping. Only navigation may trigger the destination page's normal data
  load; the command itself must trigger none.
- Final gate: `npm --prefix web run verify && cd api && python -m pytest`, with
  `api/.venv/Scripts/python.exe -m pytest` for the API half in this shell.

## Notes for the AI

- This is local slate filtering, not a new data source. Do not call an endpoint,
  prefetch a detail page, or read TanStack Query's cache from the shell.
- Keep one shared command contract and field. Do not build three independent
  search boxes or duplicate keyboard listeners across pages.
- Use real links or buttons for results. Do not make a bare list row the only
  accessible activation path.
- Do not mutate source arrays. Register and filter copies while preserving their
  existing order.
- A query filters rows only. It never changes summaries, digest contents,
  ranking, selection, projection values, or colors.
- Remove global key listeners on cleanup and ignore composition events so input
  methods are not interrupted.
- Keep all new text and styles within the existing Lineform palette and 11px
  floor. Neutral selection styling is not a betting signal.
- This shell interaction is an important product-navigation change. If the
  employer interview guide exists, update its navigation description only after
  browser verification proves the shipped behavior.

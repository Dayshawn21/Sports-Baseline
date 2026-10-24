# Feature: NHL slate and game page

**From build-plan:** feature 45e
**Type:** Feature
**Status:** completed and approved for squash merge to local master; push pending
**Spec date:** 2026-10-23

## Goal

Expose the NHL games, book prices and PrizePicks lines already stored by
45b-45d through a table-first slate at `/nhl` and a game page at
`/nhl/game/:gameId`. Add NHL to the shared navigation and sport-status
registries. All values are market information or gray line-only context;
there is no NHL model, projection, edge or recommendation.

45a-45d are complete and archived. This is one bounded display feature with
six reviewable steps, using the existing team-sport architecture rather than
introducing another ingest, prediction or report stack.

## Design reference

Extend the existing Lineform interface, with no new visual design or replica
target. No `prototypes/` directory exists at specification time.

- `web/src/pages/NbaSlatePage.tsx` and
  `web/src/components/nba/NbaSlateTable.tsx`: shared PageHead, date navigation,
  compact game rows, neutral market values and responsive table treatment.
- `web/src/pages/NbaGamePage.tsx`: game heading, back link, Matchup / Player
  Props tabs and separate query states. Use hockey language throughout.
- Existing shared theme in `web/src/index.css` and the shared NFL/NBA table,
  detail-page and prop-row styles. Do not copy the NBA digest, projection
  panels, injury panels or model tabs.
- During implementation, capture the running NBA slate/game as the existing
  visual baseline before adding NHL, then capture NHL desktop/mobile evidence.

## In scope

- Three public read-only NHL endpoints: date slate, game detail and game
  line-only props. Typed web transport and TanStack Query hooks for each.
- REG/PST games, Eastern slate dates, CT display times, stored scores and
  final REG/OT/SO context when present.
- Stored moneyline including OT/SO, +/-1.5 puck line and goal total, with
  book names, timestamps and clearly attributed de-vigged market probability.
- Pre-puck-drop puck-line and total movement from one book per market.
- All twelve configured full-game NHL prop markets, as plain gray rows
  grouped by market, retaining each provider offering and its odds type.
- Shared sport navigation, mobile menu, route titles, slate command search
  by team/game, and truthful How it works NHL status.
- Bounded read-only API/browser verification, automated checks and relevant
  employer interview guide maintenance during implementation.

## Out of scope

- Injuries, availability and Expected/Confirmed goalie snapshots (45f).
- Projections, gaps, P(over), EV, picks, signal colors, prediction freezes,
  model/ranking pages, prop boards or ranked digests. These require later
  explicitly planned NHL work and validation gates.
- Team standings/records, team stats, player pages, recent-result charts,
  hit rates, settlement/grading or prop evidence drawers. The requested
  line-only display does not require a new NHL stat-analysis pipeline.
- New feeds, paid calls, provider quota changes, ingest/workflow changes,
  database writes, schema changes or migrations.
- Broad NFL/NBA refactoring, new auth, deployment, remote dispatch, push or
  changes to parked model experiments.

## Build loop

Build one step at a time. Explain the intended diff, implement that step
with its logic tests, show the diff and observable done-when evidence, then
stop for review before the next step. Checkpoint commits are optional and
require approval. `/complete` handles the archive, checkbox and final commit.

## Build steps

- [x] **Step 1 - NHL read contracts and repository boundary.** Add NHL
  Pydantic schemas and bounded repository reads for served dates/games,
  current book markets, movement/history and latest eligible prop offerings.
  Apply the contracts below to every shared-table alias. Keep date-wide
  market and prop-count reads batched, rather than queries per slate row.
  *Done when:* fixed-fixture repository contract tests prove NHL/provider
  isolation, REG/PST eligibility, deterministic snapshot selection, pre-start
  cutoffs, same-book history and prop deduplication. Wrong-sport ids cannot
  return NHL data. Schemas serialize the documented camelCase shape. Existing
  APIs still start unchanged; no route or database writer is added yet.

- [x] **Step 2 - Assemble and expose the NHL API.** Add thin NHL routes,
  slate/game/line-only services and pure date/market/history shaping helpers.
  Reuse neutral shared helpers where available; a small extraction from an
  NBA/NFL-named helper is allowed only with unchanged caller behavior and
  regression coverage. The game page uses the slate's same game assembly.
  *Done when:* local HTTP reads return the three contracts below, including
  empty slate/props, missing market and missing-id behavior. Shared assembly
  produces identical slate/game market values for fixed inputs. Pure tests
  cover date fallback, side orientation, puck-line sign, timestamps, sorting
  and history reduction. API queries make no provider calls or writes.

- [x] **Step 3 - Typed web data and display derivations.** Add NHL types,
  API functions and query hooks, plus tested pure view helpers for dates,
  ids, game states, prices, market labels, grouped line-only offerings and
  slate command targets. Query keys include sport and all parameters;
  slate/detail/prop stale times are deliberately five minutes.
  *Done when:* helpers demonstrate CT times, null-safe states, signed puck
  lines, deterministic market/player/offer order, unchanged Time On Ice
  minutes and game-only search targets. Invalid ids disable detail queries;
  malformed browser dates fall back to API selection. Web typecheck and
  focused Vitest tests pass. No unfinished NHL route is advertised yet.

- [x] **Step 4 - NHL game page.** Build the shared detail heading, hero,
  date-preserving slate back link, Matchup tab with market and movement,
  and Player Props tab with grouped gray line-only rows. The Props tab header
  shows the game's total line count and its Standard / Goblin / Demon counts
  (`nhlOddsTypeCounts`, owner request 2026-10-23). Capture the existing
  NBA visual baseline first. Implement explicit loading, retry, not-found,
  missing-market, empty-props and props-error states. Reuse the movement
  chart only through a compatible neutral shape and hockey-specific labels.
  *Done when:* the page can be inspected locally in a temporary uncommitted
  preview route without advertising NHL in the sport registry. Desktop and
  phone evidence shows legible neutral rows, puck-drop language, price/book
  provenance, no invented projections, and no interference between game and
  props failures. Any preview wiring is removed before this step's final diff.

- [x] **Step 5 - Slate and complete navigation registration.** Build the
  NHL table-first slate and register the finished slate/game pages together
  in `SPORTS`, `SPORT_PAGES` and `SPORT_STATUS`. Use only a Slate view for
  NHL. Add PageHead date controls, game/prop-count summary, CT puck-drop time,
  game/status/score, puck line, total, moneyline, market probability and
  prop-count cells. Wire game/team command search and loaded detail titles.
  *Done when:* `/nhl` and direct `/nhl/game/:gameId` refresh work; desktop
  tabs/mobile drawer reach NHL and highlight it on detail pages. Date links
  survive navigation/back, search filters only the loaded slate and clears
  correctly across routes/dates, and zero games/search matches have separate
  empty states. No NHL Props/Model tab or unavailable player link is present.
  Registry/search logic tests pass and all other sport routes still resolve.

- [x] **Step 6 - Runtime proof, operational notes and final verification.**
  Run the real API/web locally against stored data with read-only DB access.
  Record populated/empty date and detail/prop evidence, book coverage and
  snapshots' age honestly; use fixed fixtures for unavailable edge states.
  Document the read endpoints and display limitations in `docs/nhl-display.md`.
  Update the ignored employer guide if present, keeping implemented, locally
  verified and deployed capabilities distinct.
  *Done when:* API observations and desktop/phone screenshots prove the
  criteria below; bounded response size/timing evidence shows these are
  lightweight stored reads, console/network checks have no new errors, the
  exact Verify gate and whitespace check pass. Missing live market coverage
  is reported rather than substituted. No remote acceptance is claimed.

## Files / areas

- New `api/app/schemas/nhl.py`, `api/app/routers/nhl.py` and
  `api/app/services/nhl/{slate,game_detail,line_only_props}.py`.
- Extend `api/app/repositories/nhl.py` and mount the router in
  `api/app/main.py`. Pure NHL display helpers under `api/app/core/` as needed.
- Reuse shared tables, odds math, NHL market/name definitions and neutral
  utilities. Do not import NBA/NFL repositories, services or ingest into NHL.
- New `web/src/types/nhl.ts`, `api/nhl.ts`, `hooks/useNhl.ts`,
  `utils/nhlSlate.ts`, `utils/nhlGame.ts`, `utils/nhlLineOnly.ts`,
  `pages/NhlSlatePage.tsx`, `pages/NhlGamePage.tsx` and NHL components/styles
  as needed. Small helpers may share a module to avoid unnecessary files.
- Extend `web/src/utils/sportNav.ts`, `routes/sportPages.tsx`,
  `pages/howItWorksContent.ts` and `utils/slateCommand.ts` with their tests;
  inspect exhaustive sport mappings revealed by TypeScript.
- New focused API tests and colocated web utility tests; `docs/nhl-display.md`.
- Local `docs/SportApp-Employer-Interview-Guide.md` if present; never stage it.

## Data / contracts

**Load-bearing: public responses.** Python uses snake_case internally and
Pydantic camelCase aliases on the wire. Web interfaces mirror the wire.
Dates are `YYYY-MM-DD`, instants are aware ISO timestamps. Game ids are
shared `sport_games.id`, never provider ids.

| Endpoint | Contract |
|---|---|
| `GET /nhl/slate?date=YYYY-MM-DD` | `{date, previousDate, nextDate, games: NhlSlateGame[]}` |
| `GET /nhl/games/{game_id}` | `NhlSlateGame` plus `lineHistory` |
| `GET /nhl/games/{game_id}/line-only-props` | `{gameId, lines: NhlLineOnlyLine[]}` |

- `NhlSlateGame`: `gameId`, `season`, nullable `week`, `gameType` (`REG` or
  `PST`), `gameDate`, nullable `startUtc`, stored `status`, away/home team
  codes/names, nullable scores, nullable `endPeriod`, `propLineCount`, nullable
  `moneyline`, `spread`, `total`, and `lineMovement` array.
- `moneyline`: `{book, homeOdds, awayOdds, homeWinProbability, fetchedAt}`.
  This probability is that book's stored de-vigged full-game probability,
  including OT/SO, not a model estimate or consensus.
- `spread`: `{book, homeLine, homeOdds, awayOdds, fetchedAt}`. Retain the
  storage name `spread`; label it Puck line on screen. Home handicap is signed;
  away handicap is its negation. `total`:
  `{book, line, overOdds, underOdds, fetchedAt}`, in goals.
- `lineMovement`: entries `{market, book, openLine, currentLine,
  openFetchedAt, currentFetchedAt}` for spread/total only. `lineHistory`:
  `{market, book, steps: [{fetchedAt, line}]}` for the identical chosen series,
  reduced to consecutive line changes. Empty arrays when unavailable; a
  single snapshot is a single point with zero change, not evidence of a move.
- `NhlLineOnlyLine`: `provider`, `providerPropId`, `playerId`, `playerName`,
  nullable `position`, nullable normalized provider `team`, `market`,
  `oddsType`, `line`, `fetchedAt`. Do not infer a historical team from the
  player's current roster. Unknown team remains null. No recent/model fields.

**Load-bearing: dates and eligibility.**

- `game_date` is already an America/New_York date from ingest. Omitted date
  chooses today in Eastern if served, otherwise the next served date, otherwise
  the latest served date, or today for an empty database. An explicit valid
  date remains selected even with no games. Previous/next are nearest served
  dates, nullable at boundaries. Sort games by start UTC nulls last, then id.
- Serve REG/PST only. Exclude preseason, other sports and absent ids; game
  and props return 404 for these. Malformed API dates/ids return FastAPI
  validation errors; a well-formed nonexistent id returns 404. Empty valid
  collections return 200. DB failures are errors, never fabricated empty data.
- Preserve completed scores and stored REG/OT/SO labels. Scheduled games
  passing start time are not advertised as live: the source is a scheduled
  refresh, with scores loaded after games. Missing starts display Time TBD.

**Load-bearing: market selection and isolation.**

- Every relevant shared-table alias is scoped to `sport='nhl'`. Odds reads
  also require `provider='odds_api_io'`, and book in `draftkings`, `bet365`.
  Reuse the full-game market semantics in the 45d archive and
  `docs/nhl-odds.md`. Never merge The Odds API, regulation or period prices.
- Select each market's book as DraftKings if eligible stored rows exist,
  otherwise Bet365. Use this same choice for latest market, movement and
  history. Order snapshots by `(fetched_at, id)` for deterministic ties.
  Show source and fetch time even if old; no silent freshness switch.
- For known starts, all displayed market and prop snapshots must satisfy
  `fetched_at < start_utc`, including historical games. For a missing start,
  show the latest stored snapshot with its timestamp, but no pre-start
  movement/history claim: those arrays are empty.
- Use only paired stored prices/probabilities. Preserve orientation and
  normalize signed home puck lines before display/history. No cross-book
  pairing or synthetic prices; null market renders unavailable independently.
- Read one date's games/markets/counts in bounded batches and one game's
  history on demand. No model imports, fitting, league-wide box-score reads,
  heavy request-time reports or cache/snapshot system introduced here.

**Load-bearing: line-only props.**

- Require `sport='nhl'`, `provider='prizepicks'`, `segment='full_game'`,
  a linked NHL game and player, and a market in `NhlLineOnlyMarket`.
  Latest eligible row per `(provider, provider_prop_id)` by timestamp/id.
  Skip null offering ids. Different provider ids remain distinct, including
  standard/demon/goblin offers for the same player/market/line.
- `propLineCount` counts the exact eligible latest offerings the props
  endpoint can display, not all historical snapshots or unresolved lines.
  Date-wide counts use the same selection predicate as detail reads.
- Sort markets in enum declaration order, then player name, player id,
  odds type, line and provider offering id. Labels cover all twelve markets:
  Shots on Goal, Points, Assists, Goals, Power Play Points, Blocked Shots,
  Plus/Minus, Goalie Saves, Hits, Time On Ice, Goals Allowed and Faceoffs Won.
- Time On Ice is provider minutes and is displayed as minutes. No seconds
  conversion or join to NHL box scores is needed in this feature. Preserve
  zero and negative values where valid, particularly Plus/Minus.
- Rows have no player-page links, recommendation ordering or semantic
  green/red tier styling. Odds-type labels identify offerings neutrally.

## Testing

- Each logic-bearing step includes passing tests in the same diff. Use fixed
  timestamps, sanitized fixtures and mocked DB results; no paid requests,
  real provider calls or model/holdout scoring in tests.
- API pure/contract tests: empty and boundary date selection, REG/PST and
  sport/provider isolation, exact-cutoff exclusion, timestamp ties, reversed
  sides, +/-1.5 signs, book fallback, same-book latest/history parity,
  unchanged-line reduction, null starts, duplicate offerings, all twelve
  labels/market filtering and slate-count/detail-offering parity.
- Web utility tests: invalid date/id handling, CT conversion including DST,
  null scores/start/market, OT/SO status, neutral probability labels, line
  formatting including zero/negative values, offering identity/order, Time
  On Ice units, NHL navigation/title/search and unchanged existing sports.
- Runtime API/browser evidence, not component or route-integration tests:
  populated and empty date; scheduled/completed game; historical odds frozen
  before start; missing market; repeated/single history points; empty props;
  invalid/missing/other-sport game; independent retry/error states. Compare
  observed game values/counts with slate and read-only stored selections.
- Capture desktop (about 1440px) and phone (about 390px) views. Check table
  readability/contained overflow, keyboard game links, tabs and date controls,
  mobile navigation, command search, direct refresh, back date, loaded title,
  no unavailable routes and no new console/network errors. State explicitly
  which cases used fixtures rather than live rows.
- Final Verify from the root with the API venv on PATH:
  `npm --prefix web run verify && cd api && python -m pytest`.
  In this managed PowerShell shell use cmd.exe for the exact combined command,
  or the documented halves (`npm.cmd --prefix web run verify` and
  `.venv\Scripts\python.exe -m pytest` from `api/`). Run `git diff --check`.
  Spec-only work does not require app tests.

## Notes for the AI

- Branch from `master` as `feature/45e-nhl-display` during implementation.
  Preserve the pre-existing modified `project-overview.md`; do not regenerate
  it or edit user-owned plans as part of this spec.
- Routers validate/delegate, services assemble, repositories own SQL and
  `core/` stays pure. Use the shared axios client and TanStack Query; no `any`.
- Reuse shared theme/components and neutral structural types. Do not copy
  NBA model/injury/team-stat dependencies into NHL to reuse a component.
  Small neutral extractions require existing caller regression evidence.
- Respect the 512 MB production memory limit. If bounded stored reads prove
  unexpectedly expensive, report evidence and revisit this spec before adding
  report infrastructure or heavy request-time computation.
- Keep 44b and tennis/NFL/NBA validation experiments untouched. NHL outcome
  display is not permission to run any model evaluation or score a holdout.
- Update the ignored employer guide only with implementation evidence, and
  never stage it. Deployment and GitHub runner acceptance remain separate.
- This skill writes the spec only. Do not implement, mark 45e complete,
  create a branch, commit, merge or push during `/feature`.
- No em dashes in new content.

## Spec critique

- Locked one book-selection rule across current markets and charts so a
  switch between providers/books cannot masquerade as line movement.
- Added exact pre-start cutoffs, missing-start behavior and stable ties;
  historical pages cannot silently select post-start snapshots.
- Defined offering identity and shared count predicates so alternate offers
  survive and the slate count agrees with the game page. Removed the NBA
  precedent of counting unresolved lines that the page cannot show.
- Kept NHL's units, REG/PST types and OT/SO labels explicit; excluded NBA
  W-L records and recent-result machinery rather than importing wrong rules.
- Split API storage, assembly, web derivations, detail UI, slate/registration
  and verification into small steps. Registry changes land only when both
  pages exist, avoiding a broken advertised route between reviews.
- Added the existing shell's command search, direct-refresh/title behavior,
  responsive evidence and independent empty/error states, without adding
  model, prop-board or 45f scope.

## Implementation evidence

- Spec approved by invoking `$implement` on 2026-10-23. Working branch:
  `feature/45e-nhl-display`. The pre-existing overview edits are preserved.
- Step 1 adds NHL response schemas and repository reads. Odds readers share
  one scoped CTE and book choice; prop rows/counts share one latest-offering
  predicate. Histories normalize away-first puck lines to the home sign.
- Added 29 executable SQL fixture tests using in-memory SQLite, covering
  mixed sports/providers, REG/PST eligibility, exact-cutoff exclusion,
  timestamp/id ties, book fallback, history consistency, null starts,
  offering deduplication and count parity. These exercise the query behavior,
  not just SQL text assertions; PostgreSQL/live stored-data acceptance follows
  with the API steps. No provider or shared-database calls ran in this step.
- Added 21 schema cases covering camelCase serialization, all twelve markets,
  offering identity, null fields, valid game/end-period enums, named books,
  probability bounds and timezone-aware timestamps.
- Full Verify exposed an older provider guard that assumed every single-feed
  reader was NFL/NBA. Scoped its historical assertion to those repositories
  and added an explicit NHL Odds-API.io reader guard. Existing NFL/NBA counts
  and provider expectations remain unchanged.
- Final exact root Verify ran through cmd.exe with the API venv on PATH:
  `npm --prefix web run verify && cd api && python -m pytest`.
  Passed typecheck, all 817 web tests, production build and all 4,143 API tests.
  Existing Vite chunk-size and Starlette/AnyIO deprecation warnings remain.
- Local TestClient startup/lifespan smoke returned 200/ok from `/health` and
  confirmed `/nhl/slate` is still 404. No NHL router, writer, schema migration
  or frontend change is included in Step 1. `git diff --check` passed.
- Product diff for review: ignored `output/45e-step1.diff`. No commit made;
  Step 1 stays unchecked until user approval, per the implement skill.
- Step 1 approved on 2026-10-23. Continuing to Step 2 without a checkpoint
  commit, as requested.
- Step 2 adds the three public NHL routes and slate, detail and line-only
  services. Both slate and detail use `assemble_games`; date-wide reads stay
  batched. Props retain provider offering identity, normalize provider teams
  against the game's sides, and sort in the specified market/player/offer
  order without projecting or joining performance data.
- Extracted existing daily date selection into `core/slate_dates.py` and
  line-history reduction into `core/line_history.py`. NBA/NFL modules re-export
  the old names so existing callers retain their interfaces. Existing NBA
  slate/game and NFL notes tests pass, as do 30 new fixed-input service cases.
- Step 2 `/check` used a real localhost Uvicorn server and PostgreSQL, with
  an ignored verification dependency enforcing `SET TRANSACTION READ ONLY`,
  a ten-second statement timeout, and rollback after every request. The local
  Windows helper sets the selector event-loop policy required by psycopg.
  No product startup configuration or database writer changed.
- On 2026-10-23, `GET /nhl/slate?date=2026-10-23` returned two games.
  Game 57029's detail returned three markets and two movement histories;
  its props endpoint returned 324 offerings. Detail matched all slate fields,
  and eligible prop count matched the returned offerings. All observed prices
  and offerings preceded the stored start. The default slate selected the
  same Eastern date. Evidence: ignored `output/45e-step2-http.json`.
- The initial cold slate response was 2,168 bytes in about 1.17 seconds;
  detail was 1,259 bytes in 438 ms and props 72,270 bytes in 348 ms. These are
  local observations, not deployed memory/latency acceptance.
- Historical date 2023-10-10 returned completed game 60898, stored scores and
  REG end-period context, with null markets, empty movement/history and zero
  prop offerings. Explicit empty date 1900-01-01 remained selected with 200
  and no games. Missing game/props returned 404; malformed date/id returned
  422. A bounded read-only lookup identified NFL game 1, and both NHL game
  endpoints returned 404 for it. Evidence: ignored
  `output/45e-step2-historical-http.json` and `output/45e-step2-db-check.json`.
- Final Step 2 Verify used the exact root command with the API venv on PATH:
  `npm --prefix web run verify && cd api && python -m pytest`.
  Passed typecheck, 817 web tests, production build and all 4,173 API tests.
  Only the existing Vite chunk-size and Starlette/AnyIO warnings remain.
  `git diff --check` passed. No provider request, database write, model
  evaluation, commit, deployment or remote workflow action ran.
- Step 2's incremental product diff is in ignored `output/45e-step2.diff`;
  it excludes already approved Step 1 changes. Step 2 remains unchecked
  pending review. The local verification server is stopped after checking.
- Step 2 approved on 2026-10-23. Continuing to Step 3 without a checkpoint
  commit, as requested.
- Step 3 adds the camelCase NHL web types, three shared-client API functions,
  and TanStack Query hooks/options. Query keys isolate sport, date, game and
  props; all three use five-minute freshness. Invalid game ids use skipToken
  so observers never start a request; malformed dates select the API default.
- Added pure game/slate helpers for CT short and dated timestamps, unknown
  puck-drop times, scheduled/started/final/off states, REG/OT/SO finals,
  signed home/away puck-line prices and per-market book/fetch provenance.
  Stored de-vigged win probability is explicitly labelled as market data
  including OT/SO. Score display preserves zero/null and waits for completed
  status. No grading, model fields, ranking or signal colors were added.
- Line-only helpers cover all twelve market labels, preserve provider minutes
  and signed Plus/Minus, and group one row per provider offering without
  merging repeated players or identical prices. Ordering matches the API's
  market/name/id/type/line/offering sequence without mutating input.
- Shared command search gains NHL game/team targets, all pointing to their
  loaded game's page. No NHL player destination is invented. Renamed its
  existing team-game input interface neutrally so NBA and NHL share that shape.
- Moved the existing web date parser/label to `utils/slateDates.ts`, preserving
  NBA's re-exports and existing tests. The parser additionally rejects year
  0000, which Python's API date type cannot accept; valid calendar behavior
  is unchanged. NHL helpers import no NBA/NFL display or model module.
- Added 55 web cases across game/slate derivations, offering grouping, query
  behavior and search. Fixed clocks prove summer/winter CT conversion and
  the five-minute cache boundary. QueryClient/QueryObserver tests use mocked
  transport without rendering components or making provider/HTTP calls.
- Step 3 exact root Verify passed with the API venv on PATH:
  `npm --prefix web run verify && cd api && python -m pytest`.
  Typecheck, all 872 web tests, production build and all 4,173 API tests pass.
  Only existing Vite chunk-size and Starlette/AnyIO warnings remain.
  `git diff --check` passed. No source under pages, routes or sport navigation
  changed; NHL remains unadvertised until the finished pages are registered.
- Step 3 product diff: ignored `output/45e-step3.diff`, excluding the earlier
  API steps. No external requests, database changes or commits ran in this
  step. Browser/visual acceptance belongs to Steps 4-6, not these data helpers.
  Step 3 remains unchecked pending user review.
- Step 3 approved on 2026-10-23. Continuing to Step 4 without a checkpoint
  commit. Preserve the owner's added odds-type count helper/test and Step 4
  header requirement, which were already on disk at the start of this step.
- Step 4 adds `NhlGamePage`, its team/score and market components, grouped
  line-only props and responsive page styles. It uses the shared page heading,
  query/loading/error components and detail-title registration. The Props tab
  shows total, Standard, Goblin and Demon counts from the displayed offerings;
  all twelve market tables retain each provider offering without player links,
  projections or signal coloring. Source books and dated CT fetch times remain
  attached to the market cells and prop offerings.
- The existing movement chart now accepts a neutral structural contract in
  `types/lineMovement.ts`, plus optional puck-line and empty-state labels.
  Its math is unchanged. Empty series get a visible empty state. Default
  NFL/NBA labels remain unchanged and were checked in the running NBA page.
- Captured the existing NBA slate/game at desktop and phone sizes before NHL
  UI work. References are ignored `output/45e-nba-*-reference.png` files.
  NHL was temporarily reachable through an uncommitted App.tsx preview route;
  no sport registry changed. That wiring was removed before final Verify and
  `App.tsx` has no diff. Step 5 will register the finished pages together.
- Step 4 `/check` drove the real local Vite/Uvicorn app with Playwright at
  1440x1000 and 390x844. The verification API used enforced read-only database
  transactions and rolled back each request. Existing user API port 8000 was
  preserved; the task's verification servers were stopped after checking.
- Stored game 57029 rendered 324 rows across twelve markets: 35 Standard,
  38 Goblin and 251 Demon. Its back link preserves 2026-10-23, the loaded
  title contains MTL @ CHI, prices name their books/fetch times, and a real
  Time On Ice row reads 20.75 min. Desktop and phone had no horizontal page
  overflow. No NHL player link was rendered. The title's NHL sport suffix
  awaits Step 5's registry entry, as expected for this unregistered preview.
- Stored historical game 60898 rendered NSH 3, TBL 5, with explicit empty
  market/props states. Missing id 2147483647 rendered not found; a malformed
  id rendered not found with zero NHL API requests.
- Browser-intercepted fixtures separately proved game/props loading,
  game-error retry, props-error retry while retaining the game header,
  unaffected Matchup content, missing start time, a SO final including a zero
  score, partial markets, empty history series, and keyboard tab activation.
  Expected fixture 500s and deliberate missing-id 404s are recorded separately
  from the final clean live check. That live pass had no page exceptions,
  console errors or failed network responses, and confirmed NBA's Spread
  chart labels were preserved.
- Review screenshots include ignored `output/45e-nhl-props-desktop.png`,
  `45e-nhl-matchup-desktop.png`, `45e-nhl-props-phone.png`,
  `45e-nhl-matchup-phone.png`, `45e-nhl-time-on-ice-phone.png` and
  `45e-nhl-movement-phone.png`. Loading/error/historical/fixture images use
  the same prefix. Consolidated observations are in ignored
  `output/45e-step4-browser-evidence.json`; live data and fixture evidence are
  explicitly distinguished there.
- Final Step 4 Verify ran after removing the preview route, using the exact
  root command with the API venv on PATH:
  `npm --prefix web run verify && cd api && python -m pytest`.
  Typecheck, 873 web tests, production build and all 4,173 API tests pass.
  The extra web case is the owner's pre-existing odds-type count test.
  UI behavior uses runtime evidence rather than new component tests, per
  coding standards. Existing Vite chunk-size and Starlette/AnyIO warnings
  remain; `git diff --check` passed. No provider call, database write,
  model evaluation, commit, push or deployment was performed.
- Step 4's incremental diff is ignored `output/45e-step4.diff`. It includes
  only this step's seven product files, excluding the earlier steps and the
  owner's pre-existing helper/test additions. Step 4 remains unchecked until
  approval; next is the slate and final navigation registration in Step 5.
- Step 4 approved by the user's continuation on 2026-10-23. Continuing to
  Step 5 without a checkpoint commit.
- Step 5 adds `NhlSlatePage`, its table and responsive CSS. Shared PageHead
  controls navigate served dates; summary counts come from the loaded slate.
  Each row shows CT puck drop/status, game/final scores, home/away puck-line
  and moneyline prices, total, per-book win probability and eligible prop count.
  Books and dated fetch times remain visible, with neutral colors and no digest,
  model output or recommendation ordering.
- Registered NHL in SPORTS, SPORT_PAGES and SPORT_STATUS with only a Slate
  view, plus `/nhl/game/:gameId`. How it works now renders a Track record link
  only for sports that register a model view. Existing sports retain those
  links; NHL's card correctly states no model or picks. App.tsx requires no
  special NHL route because registry generation owns the final routes.
- The running browser exposed a real alias gap: stored team names include
  Montreal's accent, while users commonly search without it. Added NHL-only
  composed, decomposed and accent-free team-name search aliases, including
  team targets. A new test covers all spellings. Existing search normalization
  for other sports is unchanged. The NHL search cue now says teams or games.
- Step 5 `/check` used Playwright against the real local app and enforced
  read-only database sessions. Stored 2026-10-23 data showed two games,
  495 eligible prop offerings and zero completed games, with latest stored
  odds at 6:59 PM CT. Desktop 1440x1000 and phone 390x844 had no horizontal
  page overflow. Sources and fetch times remain visible at both widths.
- Browser proof covers full-name/code search, accent-free Montreal search,
  no search matches, query clearing across routes and date changes, previous/
  next date navigation, date-preserving detail back links, direct refresh,
  mouse row clicks, real keyboard activation with a visible focus outline,
  mobile search/Enter navigation and the NHL drawer's single Slate entry.
  Loaded detail title is now `MTL @ CHI - NHL game`, followed by the Lineform
  suffix. NHL stays active in desktop navigation and the phone sport label.
- Explicit date 1900-01-01 retained its date with a distinct no-games state.
  Malformed browser date 2026-02-29 fell back to the API's October 23 slate.
  Intercepted fixtures separately proved loading, server-error and successful
  retry states. Expected fixture 500s are separate from the clean live pass.
- Final live browser checks returned no page exceptions, console errors or
  failed network responses. NBA, NFL and tennis slate routes all rendered
  their expected headings; How it works retained their Track record links.
  Screenshot and check inventory: ignored `output/45e-step5-browser-evidence.json`.
  Main screenshots are `output/45e-nhl-slate-desktop.png`,
  `output/45e-nhl-slate-phone.png` and
  `output/45e-nhl-registered-game-desktop.png`.
- Step 5 exact root Verify passed with the API venv on PATH:
  `npm --prefix web run verify && cd api && python -m pytest`.
  Typecheck, 878 web tests, production build and all 4,173 API tests pass.
  Five added cases cover NHL navigation/title behavior and accented search.
  Existing Vite chunk-size and Starlette/AnyIO warnings remain.
  `git diff --check` passed. No provider call, database write, model
  evaluation, commit, push or deployment was performed.
- Incremental product diff: ignored `output/45e-step5.diff`, excluding earlier
  steps. The local preview remains at
  `http://127.0.0.1:3001/#/nhl?date=2026-10-23` for user review, using this
  task's Vite process 23932 and read-only API process 37540 on port 8011.
  Preserve any existing user API on port 8000. Step 5 stays unchecked pending
  approval. Step 6 still owns final operational notes, employer guide updates
  and consolidated acceptance evidence before completion.
- Step 5 approved by the user on 2026-10-23. Continued to Step 6 without
  a checkpoint commit. Step 6 remains unchecked pending final review.
- Added `docs/nhl-display.md`: endpoint examples, route/date selection,
  provider/book isolation, pre-start cutoffs, offering identity/counts,
  supported markets/units, source freshness, runtime cost and manual review.
  Updated the ignored local employer guide to distinguish implemented and
  locally verified NHL displays from deployment and prediction validation.
- Final read-only API sample at 2026-10-24T03:12:15Z (October 23 Central):
  October 23 had 2 games/495 offerings; October 24 had 12 games/1,721 offerings.
  All three markets were displayed for each game, all selecting DraftKings.
  Selected odds were about 3 hours 13 minutes old. This does not prove Bet365
  availability; fallback is covered by repository tests. Game 57029 had 324
  offers and game 57040 had 221, matching slate counts and detail fields.
  Sample offering observations were strictly before their games' starts.
- Observed response sizes/timings: the two slates were 2,169 bytes/576 ms
  and 12,610 bytes/493 ms; sampled details were 1,259 bytes/424 ms and
  1,270 bytes/438 ms; sampled props were 72,270 bytes/379 ms and
  49,119 bytes/353 ms. These are bounded local observations, not production
  peak-memory/concurrency guarantees. Full request records are in ignored
  `output/45e-step6-http.json`. Empty date, historical empty markets/props,
  missing/wrong-sport 404 and malformed date/ID 422 checks passed again.
- Final live desktop 1440x1000 and phone 390x844 checks confirmed the slate
  and phone props with matching counts/titles, no horizontal overflow, no
  console errors, no failed responses and no page exceptions. New screenshots:
  `output/45e-final-slate-desktop.png`, `45e-final-slate-phone.png` and
  `45e-final-props-phone.png`. Earlier Step 4/5 runtime inventories retain
  independently identified fixture, navigation, movement and retry evidence.
- Final exact Verify passed with the API venv on PATH:
  `npm --prefix web run verify && cd api && python -m pytest`.
  Typecheck, 878 web tests, production build and all 4,173 API tests pass.
  Existing Vite chunk-size and Starlette/AnyIO deprecation warnings remain.
  `git diff --check` passes. Findings ledger has no open/fixed P0/P1;
  F-09 (P3) and F-12 (P2) remain unverified and outside NHL scope.
- No provider calls, shared database writes, model evaluation, commit, merge,
  push or deployment occurred in this display implementation. Preview remains
  at port 3001 using the read-only API on 8011 for review. Deployment and
  GitHub workflow acceptance remain unverified. Next: approve Step 6, then
  `/complete` for the work-level commit, archive and separately approved merge.
- Step 6 approved by the user's final approval. All six implementation steps
  are approved. Ready for `/complete`; no commit, merge or push performed.

## Completion review

- All six implementation steps were reviewed and approved. Runtime and exact
  Verify evidence is recorded above and in docs/nhl-display.md. No product
  source changed after the final passing Verify (878 web / 4,173 API tests).
- Invariants review: clean. Inspected NHL queries and shared helper changes
  for sport/provider filters, REG/PST eligibility, pure-core/import boundaries,
  neutral colors/minimum font sizes, source attribution and request memory.
  No projection/version, model rule, fit or holdout evaluation was changed.
- Findings F-09 (P3) and F-12 (P2) remain unverified in the active ledger.
  There are no open/fixed P0/P1 blockers or resolved entries to archive.
- Pre-existing project-overview.md changes are preserved outside this commit.
  No shared workflow or skill adapter files changed. The local employer guide
  was updated on disk and remains ignored. No prototypes were consumed.
- Parent 45 remains unchecked because 45f is pending. The feature is archived
  and 45e checked off; current-feature.md is reset. Merge requires explicit
  approval after review of the prepared feature commit; push is separate.
- Try http://127.0.0.1:3001/#/nhl?date=2026-10-23, open a game, inspect
  Matchup and Player Props, and repeat at phone width. See docs/nhl-display.md
  or /try latest for the fuller path. Hosted deployment and runner acceptance
  are unverified.
- The user explicitly approved squash merge and branch deletion after reviewing
  feature commit bb98985. The local master squash includes this completion
  record. Push requires separate approval; no remote deployment is claimed.

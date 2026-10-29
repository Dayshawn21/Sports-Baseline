# Feature: 48d. Sportsbook player props

**From build-plan:** feature 48d (parent 48, Tennis prop rebuild)
**Status:** not started (spec awaiting owner review)
**Branch:** `feature/48d-sportsbook-player-props`

## Goal

Find out, with a bounded and owner-approved probe, whether the key's two
Odds-API.io books (DraftKings, FanDuel) price tennis player props (games won,
aces, double faults). If they do, store each two-sided price, de-vig it, and
show each PrizePicks line beside the book's line and fair P(over), gray and
display only. If they do not, record that finding, as 48b did for totals, and
stop at a gate so the owner picks the next step before any code.

## What is already known (read-only, 2026-10-29)

- **Every tennis capture so far saw `ML` only.** 48b capture 1
  (2026-10-28 21:19 UTC): DraftKings and FanDuel each sent one market, `ML`,
  on four events (WTA 125 Queretaro x2, Challenger Sioux Falls x2, 35 to 170
  minutes out). The 2026-10-27 ATP Paris probe (fix `odds-io-fanduel`) also
  saw only `ML`, on five events. **No ATP or WTA main-tour singles event
  close to start, and none the day before, has been captured for props.**
  Player props are usually posted for main-tour matches only, so that is the
  gap this probe closes.
- **The NFL shape is the only Odds-API.io player-prop shape on record**:
  DraftKings and Bet365 send a market named `Player Props` in the default
  `/odds/multi` response (`docs/nfl-odds-market-inventory.md`). If tennis
  props exist, they likely arrive in the same response the scheduled
  `odds_api` run already fetches, at zero extra requests. Its entry shape for
  props was never recorded.
- **Constraints.** Odds-API.io: 100 requests an hour, two books per key,
  shared with NFL and NHL (`nhl_odds_io` keeps a 20-request floor). Changing
  the key's books is an owner-only dashboard change that moves NFL and NHL too.
  The Odds API: 500 credits a month, about 227 left after 48b's runs, and its
  tennis coverage was only checked for `totals`.
- **Readers that must not change.** `/tennis/props/prizepicks` ranks and
  colors only 48g-adopted slices; nothing is adopted, so the board is fully
  gray. `props-v3` and `props-v4` snapshots, the 48e check and the 48g writer
  read no book price, and this feature keeps it that way.
- **No storage exists for priced tennis props.** `props` has no price
  columns (the `/props/dk` route borrows `match_odds` prices for match
  markets only). NFL's `nfl_player_prop_odds` (migration `0023`) is the
  pattern: one append-only row per book, player, market and line, with the
  provider's player name, the prices and the de-vigged probability.

## In scope

- An owner-approved raw capture of the DraftKings and FanDuel tennis
  response for ATP and WTA main-tour singles, the day before and close to
  start, with the market names and one raw entry's keys for anything that
  looks like a player market.
- **Path A only** (a book sends tennis player props): a pure parser and
  de-vig with fixture tests from the real capture; a table (migration, owner
  applies it); storing the rows from the response the `odds_api` run already
  fetches; a display-only `bookPrice` on each PrizePicks tennis line; a gray
  book cell on the tennis prop table and match props panel.
- **Path B** (none sent): the finding recorded here and in docs, and an
  owner decision on the next step before any code.
- Docs for whichever path ships.

## Out of scope

- Any ranking, color, adoption, pick, snapshot or projection change. A book
  price never moves a line out of gray, never enters `props-v3` or
  `props-v4` snapshots, the 48e grader, the 48g writer or best picks.
- Converting a book's P(over) at one line to a different PrizePicks line
  (that is a model, and would need its own version and check). A
  mismatched line is shown as the book's line, not translated.
- Using the book price as a model input or anchor (48c's simulation stays
  as is).
- Paid plans, new providers, and changing the key's two books without an
  owner decision at the Step 2 gate.
- Book props for markets other than games won, aces and double faults,
  even if a book sends them (recorded at the gate, not stored).
- Reading any `props-v3` or `props-v4` outcome, or running the 48e grader
  or 48g writer on real data (those need their own yes).
- Game spreads and set handicaps (16f stays parked).

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [ ] **Step 1 - Raw player-prop capture (no app code, owner approves each
  capture)** - a scratchpad script (never committed) reuses
  `app.ingest.odds_api` helpers (`_fetch_events`, `_fetch_odds_batch`,
  `odds_event_tour`, `event_start`): one `/events` call, then one
  `/odds/multi` call for up to 10 singles events with `odds_event_tour` of
  ATP or WTA (main tour; Challenger and WTA 125 only to fill spare slots),
  books `DraftKings,FanDuel`. **Capture 1** takes events 12 to 30 hours out;
  **capture 2** (a second OK, a later hour the same or next day) takes events
  within 3 hours of start. For each event and book it records tour, minutes
  to start, every raw market name, and, for any market that is not `ML`, the
  market's keys and two raw entries (trimmed, no URLs). It logs the hourly
  quota after each call and refuses the odds call when remaining is at or
  below 20. Nothing is written to the database. *Cost:* 2 Odds-API.io
  requests per capture, 4 in all; no The Odds API credits. *Done when:*
  **Probe results** below says, per book and tour, whether any player market
  arrives, under what name and entry shape, how far before start, and whether
  it comes in the default `/odds/multi` response or needs another call. If
  any arrives, a trimmed copy of one event (player names kept, no key or URL)
  is saved as `api/tests/fixtures/odds_io_tennis_player_props.json` for
  Step 3.
- [ ] **Step 2 - Gate: pick the path (no code)** - read Step 1.
  - **Path A** - a book sends at least one of games won, aces or double
    faults, two-sided, in the default response: Steps 3 to 8 as written.
    If the props need a separate call, amend Step 5 to a separately budgeted
    ingest before any code.
  - **Path B** - neither book sends any tennis player market: stop and give
    the owner the options, each with its measured or quoted cost, then amend
    or close the spec before any code:
    1. **Record and close.** 48d is checked off as complete with the
       finding (no free tennis player props), like 48b's Path B record;
       the parent 48 loses the sportsbook comparison. No code.
    2. **The Odds API.** One `/events/{id}/markets` call (1 credit) on an
       active tennis key to list which markets its books carry for one
       event; only if a player market is listed, a spec amendment for a
       credit-floored ingest (from the roughly 227 credits left this month).
    3. **Swap a key book** to one that sends tennis props, if the owner
       knows of one. NFL and NHL lose that book; out of scope unless chosen.
  *Done when:* the path (and, for Path B, the owner's choice) is written
  under **Decision** below, with later steps amended or the spec closed.

*Steps 3 to 8 run only on Path A. The entry shape in Step 3 is fixed by the
Step 1 capture, not guessed; amend these steps at the gate if it differs.*

- [ ] **Step 3 - Parse and de-vig (pure)** - new
  `app/core/tennis_player_props.py`: from one Odds-API.io event's
  `bookmakers` value, a list of `BookPlayerProp` (book lowercase, provider
  player name, stat key, line, over and under American odds, de-vigged
  P(over) via `devig_two_way` on `american_to_prob`). Only `games_won`,
  `aces` and `double_faults` (the keys `normalize_stat_type` uses) are kept;
  one-sided or unparseable rungs are dropped and counted; a player on a
  split ladder keeps every two-sided rung. Player names are tied to the
  match side by the same token rules `match_event` uses, and a name that
  fits both sides is refused. *Done when:* `api/tests/test_tennis_player_props.py`
  passes on the Step 1 fixture: each kept rung's line, prices and fair
  P(over) asserted for one known player and stat; a one-sided rung dropped;
  a market outside the three stats ignored; an event with only `ML`
  giving nothing; an ambiguous name refused.
- [ ] **Step 4 - Table (migration, owner applies)** - migration
  `0051_tennis_player_prop_odds` (next number after `0050`), append-only,
  as in **Data / contracts**, with an index on `(match_id, stat_type,
  fetched_at)`. Repository functions in new
  `app/repositories/tennis_player_props.py`: `insert_rows` and
  `latest_for_matches` (newest row per match, player, stat, book and line in
  the last 24 hours). *Done when:* `alembic -c <config> upgrade 0050:0051 --sql`
  renders the expected DDL offline, the migration's `downgrade` drops only
  the new table, and the owner has applied it to the shared Neon database
  (one command, `-c` config as `AGENTS.md` says) or deferred it, recorded
  here. No code reads the table before Step 6.
- [ ] **Step 5 - Store from the existing odds run** - `app/ingest/odds_api.py`
  `run` passes each matched event's `bookmakers` to Step 3 and inserts the
  rows with `match_id` and the side's `player_id`, inside the same
  transaction as its `match_odds` rows, at **no extra request**. The run
  checks once that the table exists (`to_regclass`) before the loop, because
  a failed insert would abort the Postgres transaction and lose the
  moneyline rows; a missing table (migration not applied) logs one warning
  and skips the props. The run's final log line gains the
  player-prop row count. *Done when:* a test with a fake client and fake
  repository shows rows inserted with the contract shape, the moneyline rows
  unchanged, and a missing table leaving the moneyline write intact; then,
  with an owner OK (one scheduled-size run, about 2 to 6 requests), a real
  run stores at least one row, checked by a read-only query.
- [ ] **Step 6 - Book price on PrizePicks lines (display only)** - pure
  `pick_book_price(prizepicks_line, rows)` in
  `app/core/tennis_player_props.py`: among the line's match, player and stat
  rows, the same line first, else the closest line (ties to the lower
  line), books in the order DraftKings then FanDuel, rows older than 24 hours
  ignored; a line with no `match_id` or `player_id` gets none. `PropLine` gains optional `book_price` (`BookPrice` schema in
  `app/schemas/props.py`); `/tennis/props/prizepicks` fills it after
  `apply_adoption` from one `latest_for_matches` query, so ranking, color and
  adoption are computed first and never see it. Only the route fills it;
  `_enrich_props`, which the snapshot job shares, does not. A query failure (table
  missing) leaves every `book_price` null and the response 200. *Done when:*
  tests on `pick_book_price` cover same line, closest line, book order,
  stale rows and no rows; a test shows a line's `adopted_pick`, ordering and
  flags are identical with and without book rows; `prop_snapshots` code is unchanged; and `curl` on the local
  API shows `bookPrice` on a matched line and `null` elsewhere.
- [ ] **Step 7 - Gray book cell (web)** - `BookPrice` type in
  `web/src/types/`, a formatter in `web/src/utils/tennisBookPrice.ts`
  (`DK o6.5 -125 / u6.5 -105, fair 53%`, and `book line 7.5` when the line
  differs), and a gray cell on `TennisPropTable.tsx` and the match props
  panel, using the existing gray text token; empty when `bookPrice` is null.
  No sort, filter or color reads it. *Done when:* `tennisBookPrice.test.ts`
  passes on same-line, different-line and null inputs, `npm run build`
  passes, and a screenshot of the local props page shows the cell in gray
  beside an unranked line.
- [ ] **Step 8 - Docs and checks** - `docs/commands.md` odds line (what
  tennis player props are stored, from which books, at no extra request),
  the `odds_api.py` docstring and `BOOK_CONFIGS` comment, `AGENTS.md` only
  if a command changes, and the migration note. Propose (not apply) the
  `project-plan.md` §4 data-source line that overview note 66 asks for.
  The local interview guide is skipped if absent. *Done when:* the
  `invariants-reviewer` agent has run on the branch (gray-signal and
  provider-filter rules), and Verify passes:
  `npm --prefix web run verify && cd api && python -m pytest`.

## Probe results

*(Step 1 fills this in.)*

## Decision

*(Step 2 fills this in.)*

## Files / areas

- Probe script: scratchpad only; nothing diagnostic lands in `api/`.
- Path A new: `api/app/core/tennis_player_props.py`,
  `api/app/repositories/tennis_player_props.py`,
  `api/app/db/migrations/versions/0051_tennis_player_prop_odds.py`,
  `api/tests/test_tennis_player_props.py`,
  `api/tests/fixtures/odds_io_tennis_player_props.json`,
  `web/src/utils/tennisBookPrice.ts` (+ test).
- Path A changed: `api/app/ingest/odds_api.py`, `api/app/routers/props.py`,
  `api/app/schemas/props.py`, `web/src/types/` (props type),
  `web/src/components/tennis/TennisPropTable.tsx`, the match props panel
  under `web/src/components/tennis/match/`, `docs/commands.md`.
- Path B: this file, `docs/commands.md` (odds line), the `odds_api.py`
  docstring, `blueprint/build-plan.md` at `/complete`.

## Data / contracts

- **`tennis_player_prop_odds` (load-bearing; 48e or a later version may
  grade against it):** `id` bigint PK; `match_id` FK `matches` not null;
  `player_id` FK `players` null; `provider_player_name` text not null;
  `provider_event_id` text not null; `book` text not null (lowercase, as
  `match_odds.book`); `stat_type` text not null (`games_won`, `aces`,
  `double_faults`); `line` numeric(6,1) not null; `over_odds` and
  `under_odds` int not null (American); `fair_over_prob` float not null
  (de-vigged by `devig_two_way`); `fetched_at` timestamptz default now;
  `raw_json` jsonb (the one raw entry). Append-only; a run never updates an
  earlier row.
- **`PropLine.bookPrice` (API, camelCase):** null, or `{ book, line,
  overOdds, underOdds, fairOver, sameLine, fetchedAt }`. Never snapshotted,
  never read by ranking, adoption or best picks.
- No other shape changes. `match_odds`, `props`, `prop_projection_snapshots`
  and `report_snapshots` are untouched.

## Testing

- Test gate is on. Steps 3, 5 and 6 add logic and ship `pytest` tests from
  the real Step 1 fixture, never an invented shape; Step 7 ships a Vitest
  formatter test. Components ride on build plus a screenshot.
- Steps 1 and 2 add no code; evidence is the probe output recorded above.
- Final gate: `npm --prefix web run verify && cd api && python -m pytest`
  (API venv active).

## Notes for the AI

- **No provider request without an OK in chat, per capture or run.**
  Odds-API.io captures and dry runs spend hourly requests shared with NFL
  and NHL; read `x-ratelimit-remaining` from the events call before the
  odds call and stop at 20. Any The Odds API call at the gate needs its own
  OK.
- **Do not read any `props-v3` or `props-v4` outcome**, and do not run the
  48e grader or 48g writer; the probe reads provider data only.
- **Display only, gray only.** The book price is filled after adoption and
  must not change any line's color, order, `adopted_pick` or flags; the
  invariants reviewer checks this before `/complete`.
- Never log a request URL or raw `httpx` error text (it carries `apiKey`);
  log status codes, as `tennis_totals` does.
- Repositories own SQL; `core/` stays pure (parser, de-vig, picker).
- Migrations are manual and run one command at a time by the owner, never
  edited once applied; no write outside an approved run.
- Never push, merge or change the Odds-API.io dashboard books.
- No em dashes in docs, comments or commits.

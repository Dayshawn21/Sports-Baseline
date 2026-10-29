# Feature: 48d1. Player-prop probe

**From build-plan:** feature 48d1 (parent 48d Sportsbook player props, under 48 Tennis prop rebuild)
**Status:** spec approved by the owner (2026-10-29); not started
**Branch:** `feature/48d1-player-prop-probe`

## Goal

Find out, under a stop rule fixed before any request, whether Odds-API.io's
two free books (DraftKings and FanDuel) send any tennis player prop (games
won, aces, double faults) for tour-level matches. Either answer closes the
question: player props let 48d2 proceed; none park 48d2 and 48d3 with the
evidence recorded. (Owner decision 2026-10-29: confirm, then stop; The Odds
API is not probed.)

## What is already known (read-only, 2026-10-29)

- **Only moneylines so far.** 48b's capture 1 (2026-10-28 21:19 UTC: four
  WTA 125 and Challenger events within 3 hours of start) and the 2026-10-27
  probe (fix `odds-io-fanduel`: five ATP Paris events, doubles included,
  14:30 to 16:30 UTC) both saw exactly one market, `ML`, from each book.
  DraftKings priced 1,238 tennis matches over 120 days and never stored
  anything else.
- **The client asks for every market a book has.** `/odds/multi` takes
  event ids and bookmakers, not a market list, so a player prop would have
  appeared in those captures had a book sent one.
- **No capture has targeted tour-level singles near start.** 48b's capture
  1 had no ATP main-tour match in range, and the Paris probe mixed in
  doubles.
- **The inventory tool picks the wrong events.** `--inventory-only`
  (`app/ingest/odds_api.py`, 16c) sends the first 10 ids of the `/events`
  listing (803 events on 2026-10-28, mostly days out), which is why its
  2026-09-16 capture returned no markets at all. It checks no quota floor,
  merges markets across events (so per-event coverage is lost), and writes
  over `docs/odds-market-inventory.md` by default.
- **Quota.** Odds-API.io allows 100 requests an hour, shared with the
  scheduled tennis, NFL and NHL moneyline jobs. One capture costs two
  requests: one `/events`, one `/odds/multi` for up to 10 events
  (`BATCH_SIZE`).
- **Tour helpers exist.** `odds_event_tour` and `event_start`
  (`app/core/tennis_odds_events.py`) read the league name and start.
  `odds_event_tour` maps WTA 125 to `WTA` and the scheduled ingest relies on
  that, so this probe reads the circuit with its own helper.

## In scope

- **Event selection (pure):** tour-level singles events (circuit exactly
  `ATP` or `WTA`; no doubles, mixed, WTA 125, Challenger, ITF or other
  circuits) starting within a given number of hours, soonest first, at most
  10.
- **Inventory changes:** `--inventory-within-hours N` selects with that
  rule (without it the old first-10 behaviour stays); the existing
  `--min-requests-remaining` is honoured after `/events`, so the odds
  request is skipped at the floor; the report adds one line per captured
  event (league, minutes to start, each book's market names) below the
  existing merged table.
- **Two captures**, each with a separate owner yes in chat, written under
  `blueprint/reference/48d/` (never over `docs/odds-market-inventory.md`).
- **The verdict** under Results, applied by the stop rule.

## Out of scope

- Storing, de-vigging or showing any price (48d2, 48d3).
- The Odds API or any paid plan or book (owner decision 2026-10-29).
- Changing the scheduled tennis odds job, its books or its quota floor.
- Editing the build plan to park 48d2 and 48d3: `/complete` proposes that
  after the verdict.

## Stop rule (fixed here, before any capture)

Every capture uses `--inventory-within-hours 6`.

A capture **counts** when it selects at least 4 tour-level singles events
and the odds request runs. A capture that selects fewer, or stops at the
floor, is **void**: it is recorded, does not count, and the owner decides
whether to try another window.

A market is a **player prop** when its name refers to one player's games,
aces or double faults (for example "Player Games", "Total Aces", "Double
Faults"), from either book, on any captured event. Totals, spreads, set and
match markets are recorded but are not player props.

- **Not available:** two counting captures, on different UTC days, find no
  player prop. 48d records "not available on the free plan", and
  `/complete` proposes parking 48d2 and 48d3 with this evidence.
- **Available:** any counting capture finds a player prop. Record each such
  market's name, book, line shape and how many captured events carry it.
  48d2 proceeds (its coverage bar is set in its own spec); the second
  capture is still taken, to measure coverage.

No threshold, window or market definition is changed after a capture is read.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Tour-level event selection (pure)** - in
  `app/core/tennis_odds_events.py`: `tour_level_circuit(league_name)`
  returning `ATP`, `WTA` or None, and `near_start_events(events, now,
  within_hours, limit)` returning the tour-level singles events whose
  `event_start` is after `now` and no more than `within_hours` ahead,
  soonest first, at most `limit`, skipping events with no id or no
  parseable start. *Done when* tests in `tests/test_tennis_odds_events.py`
  show: "ATP - Paris, France" and "WTA - Riyadh" map to their tour;
  "ATP - Paris, Doubles", "WTA 125K - Adana", "Challenger - Bari" and
  "Tennis - ITF ..." map to None; an event already started, one beyond the
  window and one with a bad start are left out; the result is sorted and
  capped; an empty listing gives an empty list.
- [x] **Step 2 - Inventory selection, floor and per-event lines** - in
  `app/ingest/odds_api.py`: `capture_market_inventory` takes `within_hours`
  and `min_requests_remaining`; with `within_hours` it selects through step
  1, otherwise the old first-10 ids. After `/events`, a remaining count at
  or under the floor writes a report saying so and sends no odds request.
  The report keeps its merged table and adds one line per captured event:
  league, minutes to start, and each book's market names. The CLI gains
  `--inventory-within-hours`. *Done when* tests in
  `tests/test_odds_market_inventory.py` with a mocked client show: the
  selected ids are the ones sent to `/odds/multi`; at the floor no odds
  request is made and the report says why; no selected event gives the
  existing "No active tennis events returned." report with no odds
  request; the per-event lines list each book's markets; without the flag
  the first-10 behaviour and existing report lines are unchanged. Verify
  passes.
- [ ] **Step 3 - Capture 1 (owner yes, 2 requests)** - first count stored
  tour-level ATP and WTA singles starting within 6 hours (read-only) and
  report it when asking. With the owner's yes, from `api/` run
  `python -m app.ingest.odds_api --inventory-only --inventory-within-hours 6
  --min-requests-remaining 20 --inventory-output
  ../blueprint/reference/48d/capture-1.md`. *Done when* the file exists and
  Results records the capture's UTC time, events by tour, every market name
  by book, and whether it counts.
- [ ] **Step 4 - Capture 2 and verdict (owner yes, 2 requests)** - the same
  command on a different UTC day, written to `capture-2.md`. *Done when* it
  is recorded as in step 3, and Results records the stop rule's verdict
  (not available, available, or still short of two counting captures) with
  both files linked.

## Files / areas

- Changed: `api/app/core/tennis_odds_events.py` (two pure helpers),
  `api/app/ingest/odds_api.py` (inventory selection, floor, per-event lines,
  one flag)
- Tests: `api/tests/test_tennis_odds_events.py`,
  `api/tests/test_odds_market_inventory.py`
- New: `blueprint/reference/48d/capture-1.md`, `capture-2.md`
- Docs: `docs/commands.md` (the new flag, the floor, and that a capture
  costs two Odds-API.io requests)

## Data / contracts

- **No schema change and no database write.** The probe reads the provider
  and writes Markdown only.
- Capture files keep `render_market_inventory`'s existing table (book, raw
  market names) so they read like the 2026-09-16 inventory; the per-event
  lines are added below it.
- Captures never contain the API key or raw payloads; the renderer writes
  only names, leagues and times.

## Testing

- Steps 1 and 2: unit tests on the pure helpers and on the inventory path
  with a mocked `httpx` client and fixed timestamps (never `datetime.now()`
  in an assertion). No test calls the provider.
- Steps 3 and 4: recorded output, not tests. Each spends two requests from
  the shared hourly quota and needs its own yes in chat.
- Final gate: `npm --prefix web run verify && cd api && python -m pytest`.

## Notes for the AI

- **Spend only on a yes.** Steps 3 and 4 each need the owner's explicit yes
  in the current chat; a yes for one does not cover the other.
- **Pick the window.** Before asking, count stored tour-level singles
  starting within 6 hours, so a capture is unlikely to be void, and say the
  count when asking.
- **Read, then apply the rule.** Do not widen "player prop", lower the
  4-event bar, change the window or count a void capture after a result.
- `app/core/` stays pure: the helpers take `now` and the event list.
- Leave `odds_event_tour` unchanged.
- Match the surrounding comment density. No em dashes.
- **Interview guide:** update at `/complete` only if the verdict changes a
  claim (for example, that sportsbook tennis player props are unavailable
  on the free plan). It is untracked; never stage it.

## Results

- **Capture 1 window check (2026-10-29 16:29 UTC, read-only, no request
  spent):** 4 stored tour-level singles within 6 hours (ATP Vienna 16:30 and
  19:00, ATP Basel 17:00 and 18:30; no WTA), one starting at the check, so a
  capture would likely select 3 and be void. The owner chose to wait for the
  2026-10-30 quarterfinal window (about 10:30 UTC), re-counting before asking.
- **One probe (owner decision 2026-10-29):** a second session wrote a broader
  48d spec on `feature/48d-sportsbook-player-props` (`a401d8dc`, its own
  12 to 30 hour capture window). The owner kept 48d1 as the only probe; that
  spec is input for 48d2 and 48d3 only if 48d1 finds props, and it runs no
  capture.

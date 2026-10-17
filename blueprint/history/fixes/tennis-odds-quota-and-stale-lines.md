# Tennis odds follow-ups: quota and stale lines

**Type:** Fix

## The problem

This collects the follow-ups from the odds, parser, frontend and Bankroll fixes
(2026-09-25). Each was measured before this spec.

1. **Page loads use up the Odds-API.io hourly limit.**
   - `_overlay_live_moneyline` (`api/app/routers/tennis.py:128`) calls the live
     API from every best-picks request whose predictions lack stored odds, which
     is almost every request. The bankroll builder called it too.
   - One call is an event listing plus one odds request per 10 events, about 5
     requests for a 24-hour window.
   - The Tennis page requests best picks for two dates, so each page load costs
     about 10 of the plan's 100 requests an hour.
   - On 2026-09-25 the limit was hit (HTTP 429). The overlay swallows the error,
     so matches outside the 14-hour stored-odds window silently lost their
     moneyline pick (Vacherot v Harris).
2. **The overlay matches events loosely.** It uses the last-name substring
   matcher `_match_event` (`routers/tennis.py:110`), with no start-time check.
   The odds fix replaced that matcher in the ingest with `match_event`
   (`api/app/core/tennis_odds_events.py`).
3. **Stale spread and total lines are priced as if current.**
   - `get_today_match_odds_as_props` (`api/app/repositories/props.py`) returns
     every `match_odds` row from the last 24 hours, with no "latest" filter.
   - On 2026-09-25 it returned 135 rows for 58 match-markets, up to 6 copies of
     one. Match 81698's `game_spread` came back at −1.5 (three runs from
     yesterday), −2.5 (this morning) and −0.5 (current).
   - Best picks prices every copy, so spread picks can rest on lines the book no
     longer offers.
4. **Book ties outside moneyline.**
   - `get_all_market_odds_batch` (`api/app/repositories/matches.py`) takes
     `DISTINCT ON (match_id, market)` by `fetched_at` alone, so books tied in one
     run are picked arbitrarily. The moneyline queries were fixed this way
     already.
   - `_fetch_market_total_games` (`api/app/routers/props.py`) ranks DraftKings
     above Bet365 *before* recency, so an old DraftKings total would beat a
     fresh Bet365 one.

## The fix

- **Cache the overlay's live lookup.**
  - Keep the last live result in the process for 15 minutes, keyed by its
    request.
  - Concurrent callers share one in-flight fetch, so two date requests cost one
    lookup.
  - A failure (including 429) is logged once and cached for the same window, so
    it is not retried on every request.
  - The Live Odds page endpoint is user-triggered and stays uncached.
- **Match overlay events with `match_event`,** including the start-time check
  when both times are known.
- **Latest line only.**
  - `get_today_match_odds_as_props` returns the newest row per match, market
    and book.
  - `get_all_market_odds_batch` breaks same-run ties with the shared book
    priority.
  - `_fetch_market_total_games` orders by recency first, then book.

**Must not break:**
- Stored odds taking precedence over the overlay.
- Moneyline orientation.
- Game-spread picks for matches that have a current line.
- The PrizePicks total-games reader returning Bet365's line when it is the
  newest.

**Out of scope:**
- Caching or throttling the Live Odds page.
- Changing the scheduled ingest cadence.

## Build steps

1. [x] **Quota-safe live overlay.**
   - Add the TTL cache with an injectable clock and single-flight fetching.
   - Log failures instead of dropping them silently.
   - Switch the overlay to `match_event`.
   - Tests:
     - A second call within 15 minutes does not fetch again, and one after 15
       minutes does.
     - Two concurrent calls fetch once.
     - A failed fetch is cached, not retried per call.
     - The overlay fills odds with the right orientation for a reversed
       home/away event, and rejects an event 13 hours from the match.
   - Done when these pass.
2. [x] **Latest line per book, and recency before book priority.**
   - Update the three queries.
   - Tests: recorded-SQL tests in the style of
     `test_latest_odds_book_priority.py`, showing the latest-per-book
     `DISTINCT ON` and recency before priority.
   - Done when these pass, and a read-only replay of today shows one row per
     match, market and book (match 81698 spread at its current line only).

## Verify

- `cd api && .venv\Scripts\python.exe -m pytest`
- After the limit resets, load the Tennis page twice within a few minutes. The
  API log shows one live lookup, not four.
- Spread picks show each match's current line only.

## Completion evidence

- `cd api && .venv\Scripts\python.exe -m pytest` passed, 1321 tests. The web
  app was not touched.
- `tests/test_live_odds_overlay.py` (7 tests):
  - A cached result is reused until it expires.
  - Two concurrent callers share one fetch.
  - A failure is cached, not retried per call.
  - A reversed home/away event yields -200/+160.
  - An event 13 hours off is rejected.
  - Two page requests cost one API call.
  - Stored odds never reach the API.
- `tests/test_latest_market_lines.py` (4 tests) fails to collect without the
  query changes. It covers:
  - the Bet365 alias key, run as real SQL in sqlite
  - latest per match, market, and book
  - recency before book in the other two queries
- Read-only replay on 2026-09-25:
  - Market rows served to best picks fell from 135 (58 match-markets, up to 6
    copies) to 58 (1 each).
  - Match 81698's spread went from −1.5 ×3, −2.5 ×2, and −0.5 to −0.5 only.
  - The first replay still showed a stale `betonline.ag` −2.5. Grouping it
    with `bet365` removed it.

## Not yet observed live

The Odds-API.io hourly limit had been hit (resetting about 19:12 UTC), so two
checks remain:

- One live lookup per 15 minutes across Tennis page loads, seen in the API log.
- Vacherot v Harris regaining its moneyline pick.

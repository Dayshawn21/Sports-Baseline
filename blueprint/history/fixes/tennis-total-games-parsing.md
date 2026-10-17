# Tennis match total-games odds parsing

**Type:** Fix

## The problem

Found during the set-math fix (2026-09-25). Stored `match_odds` rows with
`market = 'total_games'` are not reliable match totals: matches went over the
stored line 61.8% of the time, while the stored prices implied 49.2%.

Two Odds-API.io samples taken 2026-09-25 (20 ATP and WTA events, DraftKings and
Bet365) show why.

1. **The match-total test matches the wrong markets.**
   - `_parse_draftkings` (`api/app/ingest/odds_api.py:302`) treats any market whose
     name contains "total" but not "set" as the match total.
   - Bet365 sends `Totals (Games)` next to `Totals (Aces)`,
     `Totals (Double Faults)`, `Team Total (Games) Home/Away`,
     `Team Total (Aces) Home/Away` and `Team Total (Double Faults) Home/Away`.
     Whichever of these comes last is kept.
2. **An alternative line wins over the main one.** Within the chosen market, the
   parser keeps the line nearest 21.5 games. The aces and double-fault markets
   are one-sided ladders (e.g. 4.5 to 49.5, over only), so "nearest 21.5" picks
   an arbitrary rung.
3. **The first-set total can be stored as the match total.** The `1st set`
   branch fills `total_line` whenever no match total was read first
   (`odds_api.py:309-313`).
4. **The one clean source is thrown away.**
   - Bet365's `Totals (Games)` carries a single main line with both prices
     (e.g. 24.5 at 1.83/1.83).
   - The Bet365 `BookConfig` stores only `moneyline` (`odds_api.py:416-421`).
   - DraftKings offered only moneyline on all 20 sampled events.

Stored DraftKings `total_games` lines range from 8.5 to 35.5: 1,029 rows at 8.5–9.5,
522 at 10.5, and 1,021 at 15.5–19.5.

**Impact:**
- The PrizePicks total-games projection uses the latest stored total
  (`_fetch_market_total_games`, `api/app/routers/props.py`, filtered to lines of
  17 or more), so it can sit on an alternative or non-match line.
- The set-math fix kept the total-games 3-set weight on `2p(1-p)` for exactly
  this reason.

## The fix

- **Match total only.** Accept a market as the match total only when its name,
  with punctuation removed, is one of `total games`, `totals games`, `totals` or
  `total`. Names naming aces, double faults, team, set or 1st set never qualify.
- **Main line only.** Within that market, keep the line whose over and under
  prices are closest to even. Skip entries missing either side, which are ladder
  rungs.
- **No first-set fallback.** Remove the branch that writes the first-set total
  into the match total.
- **Store Bet365 match totals.** Add `total_games` to the Bet365 `BookConfig`
  standard markets. Totals are not oriented, so over stays `p1_odds` and under
  stays `p2_odds` whichever side is home.

**Must not break:**
- Moneyline and set-winner parsing.
- Bet365 spreads.
- The market inventory tests (update expectations only where Bet365 now emits
  `total_games`).
- Readers' DraftKings-then-Bet365 preference for totals.

**Out of scope:**
- Rewriting stored rows. Rows before this fix stay as they are; any later
  calibration must use only `total_games` rows fetched after it.
- Refitting the total-games 3-set weight. That needs clean settled totals to
  accrue first.

## Build steps

1. [x] **Parse the real match total.**
   - Implement the name filter, the balanced-line choice and the removed
     fallback.
   - Tests use market shapes copied from the 2026-09-25 samples:
     - `Totals (Games)` beside aces, double-fault, team and 1st-set markets
       yields only the games total.
     - A multi-line list keeps the balanced line, not the one nearest 21.5.
     - Over-only ladders yield no total.
     - A payload with only `Totals 1st Set` yields no match total.
   - Done when these and the existing odds tests pass.
2. [x] **Store Bet365 match totals.**
   - Add `total_games` to Bet365's standard markets.
   - Update the inventory test.
   - Done when tests pass, and one live `python -m app.ingest.odds_api` run
     stores `bet365` `total_games` rows whose lines all sit in a plausible
     match-total range (about 17 to 30 for best-of-3) with two-sided prices.

## Verify

- `cd api && .venv\Scripts\python.exe -m pytest`
- After a live odds run, check that every new `total_games` row has a line of 17
  or more, and that no row has 8.5–10.5.
- On the Tennis Props board, a PrizePicks Total Games row's `marketTotalGames`
  matches Bet365's main line for that match.

## Completion evidence

- `cd api && .venv\Scripts\python.exe -m pytest` passed, 1310 tests. The web
  app was not touched.
- `tests/test_odds_total_games_parsing.py`: 5 of its tests fail against the old
  parser and all 7 pass against the new one. The seventh checks that totals are
  never flipped when the away player is p1.
- Replayed on the two saved 2026-09-25 samples (20 events), the new parser
  returned Bet365's `Totals (Games)` main line on all 13 events that had one.
  The old parser stored a team total (12.5, 13.5, 14.5) or an aces rung (19.5)
  on 6 of those 13, e.g. Medvedev at 12.5 instead of 21.5.
- Live `python -m app.ingest.odds_api --hours-ahead 14`: matched 13 of 13,
  inserted 49 rows, including 12 `bet365` `total_games` rows between 20.5 and
  23.5, all with both prices.
- `_fetch_market_total_games` returned the fresh Bet365 line for all 12 of
  those matches.
- Odds-API.io requests spent building this fix: 2 samples and 1 ingest run.

## Follow-ups

- `_fetch_market_total_games` (`api/app/routers/props.py`) orders by book
  priority before recency and has no date bound, so an old DraftKings total for
  a match would outrank a fresh Bet365 one. It did not bite on 2026-09-25;
  ordering by `fetched_at DESC` first would close it.
- Refit the total-games 3-set weight once settled matches with post-fix totals
  accrue. Use only `total_games` rows fetched on or after 2026-09-25 18:17 UTC.

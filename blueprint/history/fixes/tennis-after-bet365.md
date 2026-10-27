# Fix: Tennis after Bet365 (moneyline-only, props tab, quota floor)

**Type:** Fix
**Status:** complete (2026-10-27)
**Branch:** `fix/tennis-after-bet365`

## The problem

Follow-ups from fix `odds-io-fanduel` (archived 2026-10-27):

1. **Tennis totals and spreads have no source.** In the 7 days to
   2026-10-27, every stored tennis `total_games` (846 rows) and `game_spread`
   (773) came from Bet365; DraftKings stored moneylines only. A batched check
   of the next 10 ATP, Challenger and WTA 125 events on 2026-10-27 found both
   DraftKings and FanDuel send only `ML` on the free plan. **Owner decision
   (2026-10-27): accept moneyline-only tennis.** No code can restore the lines;
   what remains is to say so where the app and docs promise them.
2. **The tennis "Bet365" props source is dead.** `/tennis/props/bet` and the
   Bet365 option on the tennis prop board and match page show only Bet365
   total and spread rows from the last 24 hours, which stop today. **Owner
   decision: remove it.** Best picks (`tennis.py`) also hardcode
   `draftkings`, `bet365`, `betonline.ag` for its odds props.
3. **The tennis ingest checks its quota floor too late.** `run()` checks
   `_quota_too_low` only after an odds batch, so a run that starts with 0
   requests left still sends every batch (four 429s on 2026-10-27).

## The fix

- **Quota floor before any batch:** `_fetch_events` returns its rate-limit
  state; when the events call leaves the hour at or below the floor, the run
  logs the stop and sends no odds batch (exit 0, as the existing floor stop
  does).
- **Remove the Bet365 props source:**
  - API: delete `GET /tennis/props/bet`. Best picks reads odds props for the
    configured books (`settings.live_odds_bookmakers`, lowercased) instead of
    a hardcoded list, so a book that later sends tennis lines flows in.
  - Web: drop `'bet'` from the prop board, the tennis page and the match
    page source switches, `fetchBetProps` and `useBetProps`. An old
    `?source=bet` link falls back to PrizePicks, as any unknown source does.
    Lines from other books (stored Bet365, FanDuel) group under
    "Market odds" on the board instead of silently counting as Bet365.
- **Say tennis is moneyline-only:** docs and the How it works tennis entry
  (`SPORT_STATUS`) stop promising book total-games or spread picks if they
  do; the interview guide records the trade-off.

**Must not break:**
- Prop projection logic and `PROJECTION_VERSION` (`props-v2`). With no market
  total, `_expected_total_games` already falls back to the model total
  (`projection_source = "model_total"`), the path used today for matches
  Bet365 did not price. Snapshots record `projection_source` and
  `market_total_games`, so grading can split them. No version bump: the
  logic is unchanged, only the input stops arriving.
- Best-picks rules, colors and the moneyline-picks-off switch.
- The DraftKings props source (`/tennis/props/dk`) and PrizePicks.
- Stored `match_odds` rows; match pages still chart Bet365 history.

## Build steps

- [x] **Step 1 - Quota floor before batches** - `_fetch_events` returns
  `(events, RateLimitState)`; `run()` stops before `_fetch_matched_odds`
  when the events call leaves the hour at or below
  `min_requests_remaining`. *Done when:* a test with a fake client shows an
  events response at the floor sends no odds request, and one above it does;
  existing quota tests pass.
- [x] **Step 2 - Remove the Bet365 props source** - API route, best-picks
  book list from the setting, web source options, fetcher, hook and URL
  handling, board grouping. *Done when:* tests cover `readMatchView` and
  `propMatchPath` with `bet`/`bet365` (falls back, no `source=bet` link),
  board grouping of `fanduel` and `bet365` lines under Market odds, and the
  best-picks book list; `tsc` passes with no `'bet'` source left; the tennis
  page and prop board render with PrizePicks and DraftKings options only
  (local browser check).
- [x] **Step 3 - Docs and checks** - `SPORT_STATUS` tennis text if it names
  book totals or spreads; `AGENTS.md` and `docs/tennis-actions.md` odds lines;
  the local interview guide. *Done when:* Verify passes and no doc says tennis
  stores Bet365 or book total/spread lines going forward.

## Out of scope

- A paid plan or another book for tennis totals (owner chose moneyline-only).
- Any projection, probability, tier or pick logic change.
- Regenerating `project-overview.md`: run `/overview` after this merges.
- Deleting stored Bet365 rows or the Bet365 parser (stored rows still parse
  through aliases for history).

## Verify

- Verify command passes.
- Tennis prop board and a match page's Props tab show PrizePicks and
  DraftKings only; `?source=bet` opens PrizePicks.
- Next scheduled `tennis-odds.yml` run with a low hourly quota logs the
  floor stop without 429s.

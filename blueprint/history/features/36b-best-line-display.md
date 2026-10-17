# Feature: Best line and fair price display

**From build-plan:** feature 36b (second of 36's two parts)
**Status:** complete (2026-10-07)

## Goal

For each NFL game, show each side's best available price across the stored
books, naming the book and how old the price is, beside a de-vigged fair
price from Pinnacle, on the game page and the slate card. A pricing reference
for line shopping: it answers "is this number better than the market?", never
"should I bet this?".

**Why:** 36a stores Bet365, DraftKings and Pinnacle side by side. On
2026-10-07 TB at DAL already showed the use: Pinnacle had DAL -8, DraftKings
-8.5 and Bet365 -9.5, so a TB backer at Bet365 got 1.5 points over the sharp
line.

## Design reference

No mockup; the game-page card follows the existing Market and model block
(`.nfl-game-card`, `.nfl-game-mm` grid, `.nfl-game-big` numbers, 11px
`small` details) and the slate card reuses its `nfl-slate-card__market`
styling. Gray only: no green or red anywhere in this feature.

## In scope

- A pure best-line and fair-price rule (`app/core/nfl_best_line.py`).
- A repository read of each week game's newest pre-kickoff row per book and
  market across all three providers.
- A nullable `bestLine` block on each `/nfl/game-notes` game (item 29's rule:
  game-level display context extends this response).
- A "Best line" card on the game page under Market and model.
- One compact best-spread row on the upcoming slate card.

## Out of scope

- Any pick, rank, sort, edge color or alert. "vs fair" is information.
- Converting a fair price across different lines (key numbers 3 and 7):
  when the best line differs from the fair line, the card shows the point
  difference only. A cover-probability model is a later item.
- NBA (item 36 is NFL only), player props (the next item), alternate lines.
- Live and final games: the block is null once a game kicks off; the slate
  card's final view is unchanged.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - The rule** - pure `app/core/nfl_best_line.py` over a list
  of quotes (book, provider, market, line, both sides' American odds and
  de-vigged probabilities, `fetched_at`):
  - **Candidates:** every book except Pinnacle, one quote per book and
    market (the newest, so DraftKings' fresh `odds_api_io` row beats its
    stale `the_odds_api_us` row), fetched within `MAX_AGE_HOURS = 36` of
    the reference time. 36 hours covers Sunday's last Pinnacle refresh
    (12:10 UTC) through Monday night's kickoff.
  - **Best side:** moneyline by highest payout; spread by most points for
    that side (home: highest home line; away: lowest home line), then
    price; total over by lowest line, under by highest line, then price.
    Ties go to the newer quote, then the book name.
  - **Fair:** Pinnacle's de-vigged probabilities and line when its quote is
    within the age limit (`source: pinnacle`); otherwise the mean de-vigged
    probability of the candidates at the most common line (`source:
    consensus`, only with 2+ books at that line); otherwise none.
  - **vs fair:** when a best side's line equals the fair line (always for
    moneyline), `ev_pct = best decimal x fair probability - 1`; otherwise
    `ev_pct` is null and `points_vs_fair` is the line difference from that
    side's view (TB +9.5 against fair DAL -8 is +1.5; DAL -8.5 against DAL
    -8 is -0.5).
  *Done when:* tests cover each market and side, the age and
  Pinnacle-exclusion rules, both fair sources and the no-fair case, a tie,
  and the 2026-10-07 TB at DAL quotes: best TB +9.5 Bet365 (+1.5 vs fair)
  and DAL -8.5 DraftKings (-0.5), fair Pinnacle DAL -8, best TB moneyline
  +370 Bet365 with `ev_pct` within 0.005 of zero against Pinnacle's de-vigged
  21.3% TB win.
- [x] **Step 2 - The response** - `get_week_game_quotes(db, season, week)`
  in `app/repositories/nfl.py`: per week game, book, provider and market,
  the newest row fetched before kickoff, for providers
  `('the_odds_api_us', 'the_odds_api_eu', 'odds_api_io')` (36a's guard
  accepts `provider IN`). `build_game_notes` adds nullable `best_line`
  (`NflBestLineSchema`) per game with reference time `now`, null once a
  game has kicked off or when it has no candidate. *Done when:* service
  tests cover assembly and the kicked-off null; `GET
  /nfl/game-notes?season=2026&week=5` returns TB at DAL's block as in
  Step 1; every other field of that response is identical to master's;
  `pytest` passes.
- [x] **Step 3 - Game page card** - types, a pure
  `web/src/utils/nflBestLine.ts` (display strings: price, book label, age
  such as "2h ago", fair line, "+0.1% vs fair" or "+1.5 pts vs fair"), and
  `NflBestLineCard` under the Market and model block: one row per market
  with each side's best price, book and age, and the fair price with its
  source; an empty state when `bestLine` is null for an upcoming game.
  *Done when:* Vitest covers the strings (a missing fair, a consensus fair,
  a line difference, a moneyline EV); `npm run test` and `npm run build`
  pass; headless screenshots of `/nfl/game/65` at 1440px and 390px show the
  card in gray with no text under 11px and no horizontal scroll.
- [x] **Step 4 - Slate card row** - on upcoming slate cards with a best
  spread, one muted row under the market cells: each side's best spread and
  short book label (`Best DAL -8.5 DK · TB +9.5 B365`), built in
  `nflSlateCard` from the game notes it already reads. *Done when:* Vitest
  covers the row and its absence; a week 5 slate screenshot shows it on TB
  at DAL.

## Files / areas

- `api/app/core/nfl_best_line.py` (new), `api/app/repositories/nfl.py`,
  `api/app/services/nfl/game_notes.py`, `api/app/schemas/nfl.py`
- `api/tests/test_nfl_best_line.py` (new), `api/tests/test_nfl_game_notes_service.py`
- `web/src/types/nfl.ts`, `web/src/utils/nflBestLine.ts` and test (new),
  `web/src/components/nfl/NflBestLineCard.tsx` (new),
  `web/src/pages/NflGamePage.tsx`, `web/src/pages/nfl-game.css`,
  `web/src/utils/nflSlate.ts` and test,
  `web/src/components/nfl/NflSlateGameCard.tsx`

## Data / contracts

**`bestLine` on each `/nfl/game-notes` game** (camelCase; load-bearing for
the prop-comparison item, which reuses the fair-price shape):

```
bestLine: {
  maxAgeHours: 36,
  markets: [{
    market: 'moneyline' | 'spread' | 'total',
    fair: { source: 'pinnacle' | 'consensus', line: float | null,
            firstProbability: float, fetchedAt } | null,   # home or over side
    sides: [{
      side: 'home' | 'away' | 'over' | 'under',
      line: float | null,          # book sign: negative home spread = home favored
      odds: int,                   # American
      book: string, provider: string, fetchedAt,
      evPct: float | null,         # vs fair, only at the fair line
      pointsVsFair: float | null,  # from this side's view, only off the fair line
    }]
  }]
} | null
```

- **Pinnacle is never a candidate.** It is the reference, not a book the
  owner bets.
- **Age decides inclusion.** A quote older than 36 hours is dropped, not
  shown with a warning; `fetchedAt` is our fetch time (36a's contract).
- **Display only.** `evPct` and `pointsVsFair` are gray text, never sorted
  by, colored or fed to a pick.

## Testing

Test gate is on.

- **Logic with tests:** the rule (Step 1), the response assembly (Step 2),
  the display strings (Step 3) and the slate row (Step 4).
- **Proved by running:** the week 5 response, identity of the rest of
  `/nfl/game-notes`, and headless screenshots (the API venv's Playwright, as
  20g2 used).

## Notes for the AI

- 36a's provider contract: the new query names its providers; nothing reads
  `sport_game_odds` unfiltered.
- Book labels on the web: `bet365` -> Bet365 (B365 on the slate),
  `draftkings` -> DraftKings (DK), others title-cased from the key.
- Times read Central on the web; ages are relative ("2h ago").
- No UI text under 11px; no green or red (the `.nfl-slate` root keeps the
  signal variables gray).
- Odds-API.io's `updatedAt` stays in `raw_json` and is not used for age: an
  unchanged market is still current at our fetch time.

## Results

Built 2026-10-07 on `feature/nfl-best-line-display`.

- **Step 1.** `best_lines` on TB at DAL's stored quotes: spread fair Pinnacle
  DAL -8; best DAL -8.5 DraftKings (-0.5 pts vs fair) and TB +9.5 Bet365
  (+1.5); moneyline TB +370 Bet365 at -0.01% against Pinnacle's de-vigged
  21.3%; total 47.5 over -111 Bet365, under -105 DraftKings. A 6-day-old
  DraftKings DAL -9.5 row was dropped by the 36-hour limit.
- **Step 2.** `GET /nfl/game-notes?season=2026&week=5`: 200 in 3.3 s, a
  `bestLine` block on all 15 games, every other field identical to the
  2026-10-07 baseline. The provider guard now allows one multi-feed reader
  (`provider IN`, known providers only); the 10 older readers stay on
  `the_odds_api_us`.
- **Step 3.** `NflBestLineCard` on `/nfl/game/65`, audited headless at 1440px
  and 390px: no text under 11px, no horizontal scroll, text colors #F5F5F7
  and #85858F only, no console errors. **Changed while building:** spread
  and total fair labels show the line only ("DAL -8.0", "47.5"), the
  probability only on moneyline; an EV that rounds to zero reads "0.0%"
  with no sign.
- **Step 4.** `Best DAL -8.5 DK · TB +9.5 B365` on all 15 upcoming week 5
  slate cards, 11px gray, aligned with the market cells (16px side margin).
- **Suites:** `pytest` 2,497 passed; `npm run test` 513 passed;
  `npm run build` clean.

**Found while building:** the slate's market cells read The Odds API `us`
rows, which have been stale since 2026-10-01 (open question 44), so TB at
DAL's card showed DAL -9.5 / -520 "no move" above a best line of DAL -8.5.
The row is right; the cells are stale. They stay on that feed by design
(`get_slate_market_probabilities` also feeds the prop projections'
moneyline scaling), so fixing the scheduled runs resolves it.

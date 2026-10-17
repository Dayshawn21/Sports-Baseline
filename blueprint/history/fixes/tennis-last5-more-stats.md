# Tennis last-5 bars for score-derived markets and fantasy score

**Type:** Fix

**Branch:** `fix/tennis-last5-more-stats`

## The problem

The tennis prop evidence panel (`TennisPropEvidencePanel`, `RecentBars`) draws a
"last 5" bar chart against today's line only for box-score markets: aces, double
faults and break points. `recentStatBars` in `web/src/utils/tennisPropCards.ts`
returns null for every other market, so Fantasy score, Total games and the other
score-derived lines show no recent-results chart.

## The fix

Extend `recentStatBars` on the web side only. The match recent-form response
(`/tennis/matches/{id}/recent-form`) already carries each match's
player-oriented `score`, `result`, `aces` and `doubleFaults`, so no API or
schema change is needed.

| Market | Value per match |
|---|---|
| `total_games` | sum of both sides' games; a 7-6 set counts as 13 (as `app/core/prop_settlement.py` settles it) |
| `total_games_won` | the player's games |
| `total_sets` | number of sets |
| `total_tie_breaks` | sets scored 7-6 either way |
| `1st_set_total_games`, `1st_set_total_games_won` | first set only |
| `fantasy_score` | PrizePicks: 10 + games won - games lost + 3 per set won - 3 per set lost + 0.5 per ace - 0.5 per double fault |

- **Played-out matches only.** A score with an unfinished set ("3-6 3-5", how
  retirements are stored), no score, letters, or a final set not clinching the
  result gives null ("--" bar), mirroring `is_completed_score` in
  `app/core/tennis_grading.py`.
- **Fantasy needs the box score:** null when aces or double faults are missing.
- **Display only.** No signal color, no rate or count beyond the existing chart;
  the box-score markets and their tests are unchanged.
- **Not covered:** winners and unforced errors (nothing stored settles them)
  still show no chart.

## Build steps

- [x] **1. Score-derived and fantasy readers in `recentStatBars`** -
  `playerSets`, `fantasyScore` and the new `RECENT_STATS` entries in
  `web/src/utils/tennisPropCards.ts`, with tests in `tennisPropCards.test.ts`.
  **Done when:** the util tests cover each new market, a tie-break set, a
  retirement, a missing score and fantasy with a missing box-score count, and
  `npm run test` and `npm run build` pass. (Built and passing: 520 tests,
  build clean.)

## Verify

- `cd web && npm run test` and `npm run build` pass.
- Run the app, open the tennis prop board, select a Fantasy score line: the
  evidence panel shows "Fantasy score · last 5" bars with the dashed line at
  today's line.
- Select a Total games line: bars match the totals of the scores listed under
  "Last 5 completed matches" (7-6 sets as 13 games); a retired match shows "--".
- An aces line still shows the same bars as before.

## Check (2026-10-07)

- `npm run test` 520 passed; `npm run build` clean.
- Live board, Python Playwright: Fantasy score, Total games, Total sets, 1st set
  games and Aces panels all draw last-5 bars. Fantasy bars recomputed by hand
  from `/tennis/matches/{id}/recent-form` for Ilia Simakin (5) and Martin
  Landaluce (4 scored, negatives included) all match; totals match the listed
  scores, a 6-7 6-4 6-3 match reading 32. A match with no box score shows "--"
  for fantasy. Aces bars unchanged. No console errors beyond the existing antd
  React 19 warning.
- Retirements verified by unit test only; none appeared among the players opened.
- Observed: a negative fantasy value draws as the same floor stub as a value
  near zero; the label above the bar still shows the number.

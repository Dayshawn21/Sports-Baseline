# Feature 24e: Totals context

**From build-plan:** feature 24e
**Status:** completed (2026-09-19)

## Final outcome

Both context arms were rejected by the pre-registered rule on the 2022-2025
holdout: totals (adjusted MAE 10.1949 vs closing 10.1891; 0.5-point picks
50.6%) and spreads (adjusted MAE 9.4965 vs 9.4945; 89 picks). NFLverse game
temperature and wind are now stored on `nfl_games` (migration `0031`) for
2012-2026. 24d may show weather, roof, and rest as game context only. A
post-hoc 1.0-point total subgroup (93-68) is recorded below as a hypothesis
for 2026 forecast-weather games, not as evidence.

## Goal

Test whether game context the closing market might underprice (wind, cold,
indoor play, and short weeks for totals; rest difference for spreads) moves
NFL totals and spreads away from the closing line in a way that holds on the
2022-2025 holdout. The question is whether context adds anything *beyond the
market*, so the model adjusts the closing line itself rather than the rejected
24b ratings.

## In scope

- Parse and store NFLverse game `temp` and `wind` on `nfl_games` (migration
  `0031`), and re-run the schedule backfill for 2012-2026.
- Pure context features in `core/`: indoor, wind, cold, weather-unknown, and
  short-week for totals; clipped rest difference for spreads.
- A `context` arm in the 24b backtest: fit the market's residual on those
  features over 2014-2021 with no intercept, score 2022-2025 once, report, and
  apply the rule below.
- A recorded decision.

## Out of scope

- Live use of any adopted adjustment, and slate display (24d).
- Forecast weather. `nfl_game_weather_snapshots` holds true pre-game
  forecasts, but only for recent games, so it cannot back a 2014-2021 fit. It
  is the input for the 2026 confirmation (see Guardrails).
- Moneyline. Rest is tested through the spread only.
- EPA, success rate, and pace (24c).
- Retuning any 24b grid, weight, or verdict.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Store game temperature and wind.** Migration `0031` adds
  nullable `temp` and `wind` (smallint) to `nfl_games`. `parse_schedules` reads
  them with the existing optional-int parser (`NA` and blank stay NULL);
  `upsert_game` writes them. Re-run
  `python -m app.ingest.nflverse --schedule-only --season 2012 --through-season 2026`.
  *Done when:* parser tests cover a real outdoor row (2025_01_DAL_PHI: 75°F,
  11 mph) and a dome row (NULL, not 0); after the backfill, 2012-2025 has 2,459
  outdoor games with both values; the migration round-trips; and the 2026 week 2
  slate hash is unchanged.

- [x] **Step 2 - Pure context features.** `app/core/nfl_game_context.py`:
  `total_features(roof, temp, wind, home_rest, away_rest)` returns
  `indoor`, `wind`, `cold`, `weather_unknown`, `short_week`;
  `spread_features(home_rest, away_rest)` returns `rest_diff`. Rules below.
  *Done when:* tests cover dome, closed, open, outdoors with and without
  weather, a missing roof, a Thursday game, a bye against a short week, and
  missing rest.

- [x] **Step 3 - Context cases.** Extend `NflGameLineGame` and
  `get_game_line_games` with roof, temp, wind, and both rests; add the feature
  vectors to `NflGameLineCase`.
  *Done when:* the repository test pins the new columns, and a case test shows
  a dome game and an outdoor game with the expected feature values.

- [x] **Step 4 - Fit, score, report.** Add `--signal context` to
  `app/backtest/nfl_game_lines.py`. On 2014-2021 only, fit
  `actual - closing line` on each arm's features with
  `LinearRegression(fit_intercept=False)`. Score 2022-2025 once: closing-line
  MAE versus adjusted MAE, picks at adjustment thresholds 0.5, 1.0, and 2.0
  points, the fitted coefficients, and the verdict. `--dry-run-fit` prints the
  coefficients only.
  *Done when:* a test proves the coefficients do not change when every holdout
  outcome is flipped, and rule tests cover pass, too few picks, low hit rate,
  and no MAE gain.

- [x] **Step 5 - Run once and record the decision.** Run
  `python -m app.backtest.nfl_game_lines --signal context` a single time and
  record the output and per-arm verdicts under **Decision**.
  *Done when:* the output and verdicts are recorded, with no change to features,
  thresholds, or the rule after the holdout is seen.

## Pre-registered adoption rule

Fixed now, before any holdout number exists. Fit 2014-2021, holdout 2022-2025.

| Arm | Adjusted line | Adopted only if, on the holdout |
|---|---|---|
| Total | `total_line + β · total_features` | Adjusted MAE beats the closing-total MAE, **and** picks where the adjustment is at least 0.5 points hit at least 52.4% over at least 100 non-push picks |
| Spread | `spread_line + β · spread_features` | Same, using home margin and the closing spread |

The 1.0 and 2.0 thresholds are reported for context only. An adoption here is
**provisional**: 24d may not show it as an edge until it also holds on 2026
games scored with pre-game forecast weather.

## Feature rules

| Feature | Value |
|---|---|
| `indoor` | 1 when `roof` is `dome` or `closed`, else 0 |
| `wind` | mph when outdoor (`outdoors` or `open`) and known, else 0 |
| `cold` | `max(0, 40 - temp)` when outdoor and known, else 0 |
| `weather_unknown` | 1 when outdoor and temp or wind is NULL, or when `roof` itself is NULL or unrecognized (41 of the 2026 games), else 0 |
| `short_week` | 1 when either team's rest is 5 days or fewer, else 0 |
| `rest_diff` | `home_rest - away_rest`, clipped to [-7, 7]; 0 when either is NULL |

No intercept, so only context can move a line. A global over or under lean in
the fit seasons would otherwise pass for signal.

## Files / areas

- `api/app/db/migrations/versions/0031_nfl_game_weather_columns.py` (new)
- `api/app/ingest/nflverse.py`, `api/app/repositories/nfl.py`
- `api/app/core/nfl_game_context.py` (new), `api/app/core/nfl_game_lines.py`
- `api/app/backtest/nfl_game_lines.py`
- Tests: `test_nflverse.py`, `test_nfl_game_context.py` (new),
  `test_nfl_repository.py`, `test_nfl_game_line_backtest.py`

## Data / contracts

- **`nfl_games.temp`, `nfl_games.wind`** (smallint, nullable): NFLverse's
  recorded game conditions, in °F and mph. NULL for indoor games and when the
  source is blank. Load-bearing for any later weather work.
- **Context features** (load-bearing if adopted, since 24d must compute the
  same values live from forecast weather): the names and rules in the table
  above.

## Testing

- The test gate is on. Parser, feature rules, repository columns, case
  building, holdout independence, and the rule all get focused tests.
- Integration: the Step 1 backfill counts and slate hash, and the Step 5 run,
  are local-database checks with printed evidence.
- Final gate: `.venv\Scripts\python.exe -m pytest` from `api/`. No web change.

## Notes for the AI

- **NFLverse `temp` and `wind` are observed, not forecast.** They exist only
  for games already played (2026 has them for 11 of 272 games). The backtest
  therefore sees slightly better weather than a bettor would pre-game, which
  flatters the signal. That is why an adoption is provisional until confirmed
  on forecast weather.
- Coverage (2012-2025, regular season, verified after the Step 1 backfill):
  2,459 `outdoors` games with both values; 184 outdoor-type games without
  (123 `outdoors`, 61 `open`); 1,020 dome or closed games, one of which (a
  closed roof) carries a temperature. The feature rules treat it as indoor.
- The 2022-2025 holdout was already scored for 24b. It stays the holdout, with
  a fit on 2014-2021 only; the 2026 confirmation guards against a lucky pass.
- `spread_line` is the expected home margin, positive when the home team is
  favored (see the spread-sign fix).
- The regression lives in the backtest module (scikit-learn, as in
  `nfl_anytime_td.py`); `core/` stays pure.
- Do not look at holdout numbers before Step 5, and do not change a feature,
  threshold, or the rule after it.

## Decision

Recorded 2026-09-19 from the single holdout run
(`python -m app.backtest.nfl_game_lines --signal context`). No feature,
threshold, or rule changed after it.

```
Context fit 2014-2021 (points added to the closing line per unit):
  total: indoor +0.867, wind -0.078, cold -0.057, weather_unknown -0.019, short_week +0.898
  spread: rest_diff -0.113

TOTAL CONTEXT (MAE: closing line, adjusted line; picks by adjustment size)
set          games     close  adjusted  hit rate (W-L-P)
2022-2025     1087   10.1891   10.1949  @0.5 0.506 (370-361-6)  @1 0.578 (93-68-2)  @2 0.600 (9-6-0)
  wk 1-4       256   10.3750   10.4240  @0.5 0.466 (62-71-1)  @1 0.333 (3-6-0)  @2   -   (0-0-0)
  wk 5+        831   10.1318   10.1243  @0.5 0.515 (308-290-5)  @1 0.592 (90-62-2)  @2 0.600 (9-6-0)
Verdict: rejected

SPREAD CONTEXT (MAE: closing line, adjusted line; picks by adjustment size)
set          games     close  adjusted  hit rate (W-L-P)
2022-2025     1087    9.4945    9.4965  @0.5 0.517 (46-43-1)  @1   -   (0-0-0)  @2   -   (0-0-0)
  wk 1-4       256    9.7539    9.7442  @0.5   -   (0-0-0)  @1   -   (0-0-0)  @2   -   (0-0-0)
  wk 5+        831    9.4146    9.4202  @0.5 0.517 (46-43-1)  @1   -   (0-0-0)  @2   -   (0-0-0)
Verdict: rejected
```

**Both arms rejected.**

| Arm | Why |
|---|---|
| Total | Adjusted MAE worse than the closing total (10.1949 vs 10.1891), and 0.5-point picks hit 50.6%, under 52.4% |
| Spread | Adjusted MAE worse (9.4965 vs 9.4945), and only 89 decided picks, under 100 |

**What it means:** weather, roof, and rest as specified do not beat NFL
closing totals or spreads. 24d may show them as game context, never as an
adjustment or an edge.

**Post-hoc observation, not evidence.** Total picks where the adjustment
reached 1.0 point went 93-68 (57.8%), 90-62 in weeks 5+. The 1.0 threshold
was registered as context only, it was one of six threshold-by-bucket cells
seen at once, and the adjusted line still lost on MAE. It adopts nothing. If
pursued, "total adjustment of at least 1.0 point" must be pre-registered with
these frozen coefficients and scored only on 2026 games with pre-game forecast
weather.

# Fix: anytime-TD baseline

## Anytime-TD baseline: blend seasons and shrink toward the position rate

**Type:** Fix

## The problem

The NFL anytime-TD projection uses the same baseline path as yardage markets,
which does not suit a rare, noisy event. `/debug` on 2026-09-18 confirmed
the cause against CAR @ ATL week 2 (books are Yes-only, so they include margin):

| Player | Model | Books | Cause |
|---|---|---|---|
| Chuba Hubbard | 22% | 54% | `choose_baseline_season` fell back to 2025 only (4 TD in 15 games, 8.9 att/g); ignored 2024 (11 TD) and his 2026 week 1 (2 TD) |
| Darren Waller | 49% | 19% | 9 games with 6 TD on 2.7 rec/g got full weight: `model_projection` weight is `games / 4`, capped at 1 |
| Jonathon Brooks | 6% | 24% | 3-game 2024 sample with 0 TD at 75% weight |

The `1 - exp(-TD per game)` conversion is fine: it matches empirical TD-game
rates within about 5 points. The opponent (±10%) and moneyline (±8%)
adjustments are secondary.

Where: `app/repositories/nfl.py::get_slate_lines` collapses per-season averages to
one season; `app/routers/nfl.py::_slate_line` feeds that into
`baseline_projection` and `model_projection` from `app/core/nfl_projection.py`.

## The fix

For `anytime_touchdown` only, estimate a per-game TD rate from every loaded
season before the line's week, including current-season games, with recency
weights, shrunk toward the position's TD rate:

```
rate = (sum_s w_s * tds_s + PRIOR_GAMES * position_rate)
       / (sum_s w_s * games_s + PRIOR_GAMES)
probability = 1 - exp(-rate)
```

- `w_s` by seasons back from the line season: current `1.0`, one back `0.6`,
  two back `0.35`, older `0`. `PRIOR_GAMES = 10`. Named constants in
  `core/nfl_projection.py`, confirmed or tuned by the Step 3 backtest.
- `position_rate` is the position's TD per game from the most recent season in
  the player's history (already in `position_averages`).
- `model_projection` still applies the moneyline and opponent adjustments, but
  is given the total weighted games so its own `games / 4` blend does not
  regress a second time.

Rough effect with those constants: Hubbard about 36%, Waller about 29%, Brooks
about 22%. These are closer to books without copying them.

Must not change:

- Every other market's baseline, projection, edge, and flags.
- Labels, "Last 5 games" values, and `/nfl/projections` output for every
  market other than `anytime_touchdown` (Steps 5 to 7 change them for anytime
  TD only).

## Build steps

- [x] **Step 1 - pure TD-rate function.** Add `anytime_td_probability(seasons,
  line_season, position_rate) -> (probability, weighted_games)` to
  `core/nfl_projection.py`, where `seasons` is a list of (season, games, TD
  per game). Tests in `api/tests/test_nfl_projection.py`: no history returns
  the position rate; a 9-game hot streak is pulled well toward the position rate;
  a current-season game counts at full weight; a season 3+ back is ignored; a
  season after the line season is ignored.
  **Done when:** the new tests and full `pytest` pass.

- [x] **Step 2 - wire it into the slate.** `get_slate_lines` also returns each
  line's per-season TD history (`td_seasons`, from rows it already fetches).
  `_slate_line` uses `anytime_td_probability` for `anytime_touchdown` lines and
  passes its weighted games to `model_projection`. A router-level test proves a
  yardage line is unchanged and an anytime-TD line uses the blended rate.
  **Done when:** `pytest` passes, and `GET /nfl/slate?season=2026&week=2` shows
  new anytime-TD projections for CAR @ ATL with every other market's
  projections identical to before (compared from a saved response).

- [x] **Step 3 - backtest (read-only, scratch script, not committed).** For
  2025 weeks 4 to 18, predict each player-game's anytime-TD probability from
  data before that week with the old method and the new one, then compare Brier
  score and log loss against actual TD games. Tune `w_s` and `PRIOR_GAMES` only
  if the defaults lose.
  **Done when:** both scores are reported, and the new method scores at least as
  well as the old one. If it does not, stop and revisit the spec.

- [x] **Step 4 - extended backtest (read-only, scratch, not committed).** Rerun
  the Step 3 backtest with 2023 player stats fetched from the NFLverse release
  CSV and parsed in memory with `parse_player_stats` (not stored: loading 2023
  into the database would change opponent and league DVP aggregates for every
  market). Add the opponent DVP adjustment to both methods, computed from
  pre-week data the same way the slate does. Score 2025 (now with a real
  two-seasons-back season) and 2024 weeks 4 to 18.
  Moneyline cannot be replayed: `nfl_game_odds` holds only 2026 games.
  **Done when:** Brier and log loss for old vs new, with and without the
  opponent adjustment, are recorded below, and the new method still wins. If
  not, stop and revisit the constants.

- [x] **Step 5 - label blended anytime-TD baselines.** For `anytime_touchdown`
  lines, report `baseline_reason = "blended_seasons"`, `baseline_season` = the
  most recent season used, and `games_in_sample` = total raw games across the
  seasons used (weights ignored). The stale and partial-season flags follow the
  new `baseline_season`. Add the `blended_seasons` label to
  `BASELINE_REASON_LABELS` in `web/src/utils/nflLabels.ts`. Other markets keep
  their labels.
  Note: `games_in_sample` also gates `edge_is_comparable` (4 or more games), so
  a standard anytime-TD line can now receive an edge when the blended history
  has 4+ games.
  **Done when:** tests cover the anytime-TD labels and an unchanged yardage
  label; the slate shows `blended_seasons` on Hubbard's line with 31 games
  (15 + 15 + 1); `pytest`, `npm run build`, and `npm run test` pass.

- [x] **Step 6 - "Last 5 games" for anytime TD.** `_history_value` returns 1 or
  0 (scored or not) for `anytime_touchdown` instead of `1 - exp(-TDs)`, so the
  sample average is the share of games with a TD. The web evidence panel shows
  each value as "TD" or "No TD" and the average as a percentage. Pure formatter
  in `web/src/utils/` with a Vitest test; backend change covered by a pytest.
  **Done when:** Hubbard's "Last 5 games" row reads like "20% · 5 games" with
  "TD vs ..." / "No TD vs ..." entries, and all tests pass.

- [x] **Step 7 - `/nfl/projections` uses the blended TD rate.**
  `get_historical_player_baselines` also returns per-season TD history and the
  position's TD rate per player; the endpoint computes `anytime_touchdown` with
  `anytime_td_probability`. Other markets keep the flat average.
  **Done when:** a test covers the anytime-TD projection path, and
  `GET /nfl/projections?season=2026&week=2` shows Hubbard's anytime-TD
  projection matching the slate's pre-adjustment blended value.

## Backtest result (2026-09-18)

2025 weeks 4 to 18, QB/RB/WR/TE player-games with prior history (4,903 games,
18.2% scored). Baselines only: moneyline and opponent adjustments excluded from
both methods. Loaded seasons were 2024 to 2026, so the two-seasons-back weight
was never exercised.

| Method | Brier | Log loss |
|---|---|---|
| Old (one fallback season, full weight at 4 games) | 0.1440 | 0.6030 |
| New (weights 1.0/0.6/0.35, prior 10 games) | 0.1381 | 0.4406 |

Calibration: the old method predicted 2.0% for 2,033 games that scored 9.2% of
the time, and 54.0% for 463 games that scored 39.7%. The new method's buckets
track actual rates within about 3 points (0.10 to 0.20 bucket: 14.4% predicted,
11.4% actual). A prior of 5 games scored marginally better (Brier 0.1376);
defaults kept because the gain is small and 10 is more conservative.

## Extended backtest result (Step 4)

NFLverse weekly stats 2023 to 2025 parsed in memory (17,702 QB/RB/WR/TE rows),
nothing stored. Opponent adjustment replays the slate's DVP rule (±10% cap,
12-game sample weight) from pre-week data. Moneyline not replayable (stored odds
are 2026 only).

| Test season | Method | Brier | Log loss |
|---|---|---|---|
| 2025 (two-back = 2023 available) | old | 0.1439 | 0.6017 |
| | new | 0.1375 | 0.4386 |
| | old + opponent | 0.1436 | 0.6012 |
| | **new + opponent** | **0.1374** | **0.4383** |
| 2024 (no two-back season) | old | 0.1471 | 0.6201 |
| | new | 0.1426 | 0.4511 |
| | old + opponent | 0.1475 | 0.6213 |
| | **new + opponent** | **0.1431** | **0.4526** |

- The new method wins in both seasons, with and without the opponent adjustment.
- The two-seasons-back weight helps: on 2025, dropping it (0.35 to 0) worsens
  Brier from 0.1374 to 0.1379.
- The opponent adjustment is roughly neutral for anytime TD (slight help in
  2025, slight harm in 2024).
- A 5-game prior is again marginally better (Brier 0.1370); defaults kept.

## Verify

- `cd api && .venv\Scripts\python.exe -m pytest`
- `cd web && npm run build && npm run test` (no web change expected; confirms nothing broke)
- Open `/nfl`, CAR @ ATL, expand Chuba Hubbard's Anytime TD row: the baseline
  is no longer 22%, and the Sportsbooks row shows a smaller model gap.
- Backtest numbers recorded in the fix archive.

## Completion evidence (2026-09-18)

- `pytest`: 806 passed. `npm run build` passed. `npm run test`: 76 passed.
- `GET /nfl/slate?season=2026&week=2` compared before and after (7,983 lines):
  0 non-TD lines changed; all 717 anytime-TD lines now report
  `blended_seasons`; 690 projections changed.
- CAR @ ATL, 21 players with sportsbook prices: mean model-vs-book gap fell from
  9.0 to 6.1 points (Hubbard 22% to 35%, Waller 49% to 28%, Brooks 6% to 23%).
- Browser (after a full page reload): Hubbard's evidence panel shows
  "31 games · 2026", Sportsbooks gap -19.0 pts, and "Last 5 games 20.0% avg ·
  TD vs CHI · No TD vs TB ...".
- `GET /nfl/projections?season=2026&week=2`: anytime-TD values match the
  slate's pre-adjustment blended value for Hubbard, Waller, Brooks, and Bijan
  Robinson.

## Follow-ups

- Moneyline adjustment remains unbacktested until historical NFL game odds exist.
- A 5-game prior scored marginally better in both backtests; revisit with more
  seasons before changing `TD_PRIOR_GAMES`.

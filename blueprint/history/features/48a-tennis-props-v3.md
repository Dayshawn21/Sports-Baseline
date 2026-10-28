# Feature: props-v3 bias fixes

**From build-plan:** feature 48a (parent 48, tennis prop rebuild)
**Status:** complete 2026-10-28

## Goal

Remove the measured biases in the PrizePicks tennis prop projections and ship
them as `props-v3`, so the forward record restarts on corrected numbers
instead of grading known errors. The `props-v2` tiers lose at every level
(LOCK 51.9% against a 57.7% break-even while predicting 77.4%); a read-only
deep dive on 2026-10-28 traced most of it to three causes, fixed here.

This changes projections, probabilities and tiers. It does not add a model,
a book, a schema column or a page.

## In scope

- **Book total treated as the 50/50 point.** A book total-games line is no
  longer passed through as the expected total. A pure function solves for the
  mean whose set-count mixture (`total_games_probs`, best-of-3 and best-of-5)
  gives P(over line) equal to the de-vigged over probability from the stored
  over and under prices, or 0.5 when the row has no prices. Every consumer of
  `_downstream_total_games` (total games, games won, service points, aces,
  double faults, break points, fantasy score) then reads that mean.
- **Tour-specific league ace and double-fault rates.** `_LEAGUE_ACE_RATE` and
  `_LEAGUE_DF_RATE` become per player tour (`ATP`, `WTA`, from
  `players.tour`), so a typical opponent gives a matchup factor of 1.0 on
  either tour. The values are measured once (step 2) as the mean of
  `allowed_aces_per_sp` and `allowed_df_per_sp` across that tour's
  `player_rolling_stats` rows for the window the props page reads, frozen as
  dated constants with the measurement recorded below.
- **First-set level correction,** only where step 3's measurement shows it is
  needed (see the stop rule there).
- **`no_market_total` flag.** A prop whose projection depends on the match
  total (`total_games`, `total_games_won`, `aces`, `double_faults`,
  `break_points_won`, `fantasy_score`) and has no book total carries this
  flag, its confidence is capped at `PASS`, and best picks skip it. Its
  projection is still shown.
- **LOCK and STRONG withheld under `props-v3`.** Every tennis prop's
  confidence is capped at `LEAN` until a tier verdict adopts a higher tier
  (48e). The existing caps (`stale_stats`, `small_sample`, `ungraded_stat`)
  are unchanged.
- **Version bump.** `PROJECTION_VERSION = "props-v3"` and
  `TIER_RULE_VERSION = "props-v3"`, with the 32b tier rule re-registered
  unchanged (200 decided picks, 3-day maturity, 57.7% break-even, 2 SE) in
  the same commit, before any v3 snapshot exists. The constants test is
  updated to pin both to `props-v3`.

## Out of scope

- A new total-games source (48b). Until it ships, nearly every totals-based
  prop carries `no_market_total`, since Bet365 stopped on 2026-10-27. That
  thin board is accepted.
- The match simulation (48c), sportsbook player props (48d), and the
  per-stat, per-tour forward rule (48e).
- Moneyline, ensemble, derived or serve-edge picks, the priced Total Games
  and Game Spread picks, the retired bankroll builder, and the NFL/NBA prop
  pipelines.
- Fixing `_DOWNSTREAM_GAMES_CALIBRATION` (1.09 on the model total); it stays.
- Re-grading or deleting `props-v2` snapshots. Its reject, when it comes,
  stays final for v2.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Mean from a book total (pure)** - add
  `total_games_mean_from_line(line, p_over, best_of, p_deciding_set)` beside
  `total_games_probs` in `app/core/prop_probs.py`: bisection on the mean so
  the mixture's push-excluded P(over) equals `p_over`. *Done when* tests show:
  - with `p_over = 0.5` the returned mean reproduces 0.5 within 1e-6, and for
    a best-of-3 match with `p_deciding_set = 0.4` it sits above a 21.5 line
  - a higher `p_over` gives a higher mean; best-of-5 works the same way
  - `p_over` outside (0.02, 0.98) is clamped, and the search never leaves a
    bounded range (no infinite loop on any input)
- [x] **Step 2 - Measure tour league rates (read-only)** - a small backtest
  CLI `python -m app.backtest.tennis_league_rates` printing, per player tour,
  the row count and mean `allowed_aces_per_sp`, `allowed_df_per_sp`,
  `aces_per_game` and `df_per_game` for the rolling window the props page
  reads (all surfaces). *Done when* the CLI's report-format test passes and
  one local run is recorded under Results with its date. No production change.
- [x] **Step 3 - Measure the first-set level by tour (read-only)** - extend
  `app.backtest.tennis_first_set_level` to report mean bias for first-set
  total games and each player's games, by tour, and run it on 2026 matches.
  *Done when* the output is recorded under Results. **Stop rule (fixed here,
  before the run):** a tour gets a correction only if its player-games bias
  is at least 0.25 games in absolute value; otherwise its chain is unchanged.
- [x] **Step 4 - Tour rates and first-set correction in the projection** -
  `ace_matchup_factor` and `double_fault_matchup_factor` take the player tour
  and read the step 2 constants (unknown tour falls back to the pooled
  value). Step 3 qualified WTA only, with the bias on the underdog, so
  (owner decision 2026-10-28) `first_set_for_matchup` lowers only the weaker
  server's hold by one WTA constant, fitted on step 3's WTA cases so the mean
  underdog first-set games matches the actual; equal holds and other tours
  are unchanged. *Done when* tests show a tour-average opponent gives factor
  1.0 on each tour, a WTA projection with the old constant now falls, the
  WTA underdog's first-set mean drops while an ATP pair is unchanged, and
  the fit is recorded under Results.
- [x] **Step 5 - Wire tour and book prices through the router** - carry the
  player's tour onto the prop row, load the total-games over and under prices
  alongside the line in `_fetch_market_total_games` (confirm which of
  `p1_odds` / `p2_odds` is the over before using them), and use step 1's mean
  in `expected_total_games` and `_downstream_total_games` for prop rows only.
  The priced Total Games and Game Spread picks in best picks keep their
  current inputs: they compare against the book line itself, so a mean solved
  from that line would be circular. *Done when* tests show:
  - with a 21.5 line and no prices, every totals-based projection now reads
    from a mean above 21.5, not 21.5
  - an over-favored price raises the mean against the same line
  - `projection_inputs` records the line, the solved mean and the price source
- [x] **Step 6 - Flags, caps and version** - add `no_market_total` (cap
  `PASS`, skipped by best picks) and the `props-v3` `LEAN` cap; bump
  `PROJECTION_VERSION` and `TIER_RULE_VERSION`; update the pinned constants
  test. *Done when* tests show a totals-based prop with no book total is
  `PASS` with the flag, a first-set prop without a total is not flagged, no
  tennis prop is ever `LOCK` or `STRONG`, and best picks contains no flagged
  prop. Verify passes.
- [x] **Step 7 - Local check** - load the tennis prop board locally and run
  the snapshot job read-only if it supports a dry run (otherwise inspect one
  enriched response), recording the share of lines flagged
  `no_market_total`, the tier counts, and three example rows (a total, a WTA
  double fault, a first-set line) beside their v2 values. *Done when* the
  evidence is recorded under Results.

## Files / areas

- Changed: `api/app/core/prop_probs.py`, `api/app/core/prop_projection.py`,
  `api/app/core/track_record.py`, `api/app/services/tennis/prop_snapshots.py`,
  `api/app/routers/props.py`, `api/app/services/tennis/best_picks.py`
  (skip flagged props only), `api/app/repositories/props.py` (tour on the
  prop row),
  `api/app/backtest/tennis_first_set_level.py`
- New: `api/app/backtest/tennis_league_rates.py` and tests
  (`test_total_games_mean_from_line.py`, `test_tennis_league_rates.py`, plus
  additions to existing prop projection, first-set and track-record tests)

## Data / contracts

- **No schema change.** `prop_projection_snapshots` already stores
  `market_total_games`, `data_quality_flags` and `projection_inputs`.
- **Load-bearing:** `market_total_games` on a v3 snapshot remains the book
  line; the solved mean goes in `projection_inputs["market_total_mean"]`,
  so grading and the 48e rule can tell them apart.
- **Load-bearing:** `no_market_total` is a stable flag name 48b, 48c and 48e
  read. The list of totals-dependent stats lives in one constant.
- **Load-bearing:** `props-v3` starts a fresh sample; v2 rows are never
  pooled with it.

## Testing

- Steps 1, 4, 5 and 6: unit tests on pure functions and the router's pure
  `_enrich` path with synthetic stats, no database.
- Steps 2 and 3: report-format tests plus one recorded local run each.
- Step 7: local evidence, not tests.
- Final gate: `npm --prefix web run verify && cd api && python -m pytest`.

## Notes for the AI

- **No fitting on outcomes the v3 check will grade.** Step 2's constants are
  a population baseline from rolling stats; step 3's level comes from
  completed 2026 first sets read before any v3 snapshot exists. Neither reads
  a PrizePicks line outcome.
- `tennis_first_set.py` says its rules change only through a new check:
  step 3's stop rule is that check. Do not tune past it.
- `routers/props.py` duplicates some projection inputs (`_projection_inputs`);
  keep it reading the same constants as `prop_projection.py`.
- Match the existing comment density. No em dashes.
- **Interview guide:** update at `/complete` (a model change with measured
  evidence). It is untracked; never stage it.
- 44b lives on `feature/44b-nba-pover-confirmation`; never touch it here.

## Results

- **Deep dive (2026-10-28, read-only, before this spec):** book totals sit
  below actual by ATP +1.9, Challenger +2.5, WTA +1.1 games; WTA double
  faults projected 4.4-4.8 against 3.1-3.6 with opponents averaging 0.052
  allowed DF per serve point against the 0.045 constant; WTA first-set games
  won +0.6 to +1.4. Script kept outside the repo.
- **Step 2 league rates (2026-10-28 17:16 UTC,
  `python -m app.backtest.tennis_league_rates`, players with 5+ matches,
  `last_52w`, all surfaces):**

  | `players.tour` | Players | Allowed aces/SP | Allowed DF/SP | Own aces/SP | Own DF/SP |
  |---|---:|---:|---:|---:|---:|
  | ATP | 665 | 0.0582 | 0.0401 | 0.0600 | 0.0392 |
  | CHALLENGER | 189 | 0.0470 | 0.0426 | 0.0492 | 0.0428 |
  | WTA | 643 | 0.0263 | 0.0544 | 0.0273 | 0.0541 |

  Plain means shown (a typical opponent); match-weighted means differ by at
  most 0.0015. Both old constants were wrong for every tour: `_LEAGUE_ACE_RATE
  = 0.075` sits above even ATP (so ATP ace factors ran up to +25%) and is
  nearly 3x WTA's (so WTA ace factors sat pinned at the 0.75 floor), and
  `_LEAGUE_DF_RATE = 0.045` sits below WTA. **Spec note:** `players.tour`
  holds three values, not two, so step 4 keys the constants by all three,
  with the pooled value for an unknown tour.
- **Step 3 first-set level (2026-10-28 17:19 UTC,
  `python -m app.backtest.tennis_first_set_level`, completed 2026 ATP/WTA
  matches, 338 skipped for missing stats):**

  | Tour | Matches | Set-total bias | Favorite bias | Underdog bias | Player games |
  |---|---:|---:|---:|---:|---|
  | ATP | 3,417 | +0.32 | +0.15 | +0.17 | unchanged |
  | WTA | 3,906 | +0.36 | +0.05 | **+0.31** | **correct** |

  Favorite is the player with the higher hold. Under the stop rule fixed
  before the run (0.25 games), only WTA qualifies, and its bias sits almost
  entirely on the underdog: the chain gives WTA underdogs about 0.3 games
  too many, while favorites are close. A uniform hold shift on both servers
  would also move the WTA favorite, which is already near zero, so step 4's
  correction must lower the underdog's games, not both players'. Neither
  tour reaches the existing 0.5-game stop. Rolling stats include these
  matches (overwritten in place), so only the mean bias is read, as 16e did.
  No Challenger matches are in this check (the reader is ATP and WTA only).
- **Step 4 WTA underdog shift (2026-10-28 17:22 UTC,
  `python -m app.backtest.tennis_first_set_level --fit-underdog-shift WTA`):**
  `0.0522`, the hold drop on the weaker WTA server (strict underdogs only)
  that brings the mean underdog first-set games to the actual. Frozen as
  `_FIRST_SET_UNDERDOG_HOLD_SHIFT = {"WTA": 0.0522}`. Lowering the underdog's
  hold also lifts the favorite slightly; the favorite's +0.05 bias was the
  smaller error, so this was accepted (owner decision). Pooled fallbacks for
  an unknown tour: aces 0.0431, double faults 0.0466 (player-weighted across
  the three tours).
- **Step 6 effects to confirm at review:** the `/tennis/model` prop-tier
  section and the player page's past props read `PROJECTION_VERSION`, so both
  show `props-v3` (empty until v3 snapshots settle); the v2 record stays
  readable with `python -m app.backtest.tennis_prop_snapshots --version props-v2`.
  The LEAN ceiling is applied before the missing-input downgrade, so a prop
  missing an opponent or prediction lands at PASS. Eight existing tests were
  updated: their fixtures now carry a book total (they test caps and card
  parity, not totals), and three pins moved to the v3 ceiling or the
  best-of-5 book-total projection.
- **Step 7 local check (2026-10-28 17:45 UTC, read-only):** the snapshot
  job has no dry run, so a scratchpad script ran its own path
  (`get_today_props`, `enrich_props`, `skip_reason`) with no insert, once
  on this branch and once on `master` from a temporary worktree, against
  the same props. Today's 13:30 UTC `props-v2` snapshot job wrote no rows
  (last v2 rows 2026-10-27), so v2 values are `master`'s code on the same
  lines, not stored snapshots.
  - **Board:** 872 PrizePicks lines loaded, 355 eligible (skipped: 336
    invalid match link, 66 no match, 46 no player, 45 started, 24 live).
    **No eligible line has a book total** (0 of 355 on both versions), as
    expected after Bet365's exit; the solved-mean path is covered by tests
    only until 48b.
  - **`no_market_total`:** 289 of 355 (81.4%), exactly the six totals-based
    stats (Total Games 115, Aces 113, Total Games Won 36, Double Faults 15,
    Fantasy Score 6, Break Points Won 4). Total Sets, Total Tie Breaks and
    1st Set Total Games are not flagged.
  - **Tiers:** v2 LOCK 19, STRONG 11, LEAN 21, PASS 304; v3 LEAN 10, PASS
    345. All ten v3 LEANs are 1st Set Total Games.
  - **Mean projection shift, v3 minus v2:** WTA double faults -0.52 (n 15);
    aces ATP +0.67 (n 62), WTA +1.48 (n 51), because the old 0.075 league
    ace rate held every ace factor down (WTA at the 0.75 floor); WTA first
    set -0.15 (n 33); ATP first set and all total games 0.00 (no book total,
    so the model total is unchanged).

  | Line | v2 | v3 |
  |---|---|---|
  | Hurkacz (ATP) Total Games 23.5 | 22.31, UNDER 58.9%, PASS | 22.31, UNDER 58.9%, PASS, `no_market_total` |
  | Fernandez (WTA) Double Faults 3.5 | 5.94, OVER 74.1%, **LOCK** | 5.60, OVER 71.7%, PASS, `no_market_total` |
  | Teichmann (WTA) Double Faults 2.5 | 3.88, OVER 67.4%, **STRONG** | 3.35, OVER 61.7%, PASS, `no_market_total` |
  | Fernandez (WTA) 1st Set Total Games 9.5 | 9.93, OVER 54.1%, PASS | 9.81, OVER 51.5%, PASS |
  | Birrell (WTA) 1st Set Total Games 9.5 | 9.81, OVER 51.8%, PASS | 9.70, UNDER 50.4%, PASS |

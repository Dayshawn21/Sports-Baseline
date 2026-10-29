# Feature: 48c. Match simulation

**From build-plan:** feature 48c (parent 48, Tennis prop rebuild)
**Status:** complete (2026-10-29)
**Branch:** `feature/48c-match-simulation`

> **Where the code is.** This spec was first written and built in a local
> session ("Feature 48c", 2026-10-28) in the OneDrive copy. Steps 1-3 and
> their tests exist only there, uncommitted:
> `api/app/core/tennis_match_chain.py`, `api/app/backtest/tennis_match_sim.py`,
> `api/tests/test_tennis_match_chain.py`,
> `api/tests/test_tennis_match_sim_backtest.py`,
> `api/tests/test_tennis_hold_solver.py`. Before continuing, copy them into
> `C:\dev\SportAppV2` on this branch (the OneDrive copy is being renamed to a
> backup). This file is that spec, reconciled on 2026-10-29 with the
> no-tiers decision and 48f.

## Goal

Replace the per-stat closed-form projections with one simulation per match,
so every tennis prop on that match comes from the same draws and agrees with
the market on who wins and how long the match runs. Two serve parameters per
match (one hold probability per player) are solved so the match reproduces
the de-vigged moneyline and, when one is stored, the book total-games line
(48b). Total games, games won, sets, tie breaks, first-set stats, aces,
double faults, break points won and fantasy score are all read off those
draws.

The simulation runs **in shadow**: the snapshot job stores a `props-v4`
snapshot beside each `props-v3` one for the same line, and the props page and
best picks keep showing `props-v3`. Nothing about v4 is shown or picked until
48e's pre-registered check adopts a slice. This keeps v3's forward sample
whole and keeps the simulation off the 512 MB request path. (Owner decision
2026-10-28: shadow, not served on the page.)

Like every tennis prop since 48f, a v4 row carries a projection, a mean,
P(over) / P(under) / P(push) and flags. It never carries a confidence tier
(`confidence` is null).

## Coordination with 48f

48f (spec on `feature/48f-retire-tennis-tiers`) is built first. It nulls
`confidence`, keeps `PROJECTION_VERSION = "props-v3"` (its question 5) and
moves `TIER_RULE_VERSION` back to `props-v2`. 48c reads none of that tier
code.

| File | 48f | 48c | Handling |
|---|---|---|---|
| `app/services/tennis/prop_snapshots.py` | `confidence=None`, rewords the version comment | `to_snapshot` takes a version; adds `SIM_PROJECTION_VERSION` | 48c's step 9 starts after 48f merges, on top of its version |
| `api/tests/test_prop_snapshots.py` | asserts null confidence | asserts a v4 row beside v3 | same order |
| `app/routers/props.py` | removes tier code | read only (`enrich_with` inputs) | no conflict |
| `blueprint/context/current-feature.md` | its spec | this spec | on merging `master` after 48f's `/complete`, keep this spec |

- **If 48f's question 5 ends in a bump** (48f takes `props-v4`), the
  simulation takes `props-v5`. Never reuse a version 48f wrote rows under.
- Steps 1-8 are pure modules and read-only CLIs and can be built now. **Step
  9 starts only after 48f is on `master`.**

## Decided before step 4

**Total anchor (owner decision 2026-10-29): continue as specced.** Step 3
on the 12 real Pinnacle totals solved 8 exactly and clamped 4. ATP holds
came out at 0.92-0.99 against a typical 0.80 (see Results). With the set
effect, the chain plays fewer games at ordinary holds than Pinnacle prices,
so only near-perfect serving stretches the match to the line. That lowers
serve points per game, so aces and double faults may read low and tie
breaks high. Step 8's level check measures it, and `sim_clamped` is
recorded on every row. The alternative (anchoring the total through
something other than the hold level) was not taken.

**Serve points for step 4 (owner approved 2026-10-29):**
`player_match_stats` stores `service_games` but not serve points, though
both feeds carry them: TennisMyLife CSVs have `w_svpt` / `l_svpt` and the
TennisAbstract rows have `pts` (index 23); both parsers drop them. 2026 rows
with aces, DF and service games: TennisMyLife 18,376 ATP and 4,895 WTA,
TennisAbstract 28,428 ATP and 22,442 WTA. Step 4 reads serve points from the
TennisMyLife 2026 files directly, as below: no migration, no backfill, no
database write, and step 4 stays read-only. Rejected: a `serve_points`
column (a schema change against the shared database and a slow
TennisAbstract re-scrape, for one measurement), and estimating serve points
from service games (the estimate's own noise would be read as dispersion).

## What is already known (read-only, 2026-10-28)

- **Today's projections are separate approximations.** `compute_stat_avg`
  (`app/core/prop_projection.py`) builds each stat from its own formula:
  totals from `expected_total_games_from_matchup`, games won from a share,
  aces and DF from expected service points, sets from `2 + 2p(1-p)`, tie
  breaks from `(hold - 0.5) * 0.6`. They need not agree with each other or
  with the moneyline, and probabilities come from per-stat normal or Poisson
  spreads with hand-set sigmas.
- **The first-set chain is exact** (`app/core/tennis_first_set.py`): a
  game-by-game chain from two holds, serve order averaged, a single
  tiebreak game at 6-6. The match chain here extends it across sets.
- **Sets are not independent.** `app/core/tennis_sets.py` (fitted
  2026-09-25 on 3,276 best-of-3 matches, held out on 1,404) found a set
  winner more likely to win the next set; treating sets as independent
  doubled the deciding-set error. A constant-hold chain is exactly that
  independence, so step 2 checks it against the fit.
- **Inputs already loaded** by `enrich_with` (`app/routers/props.py`):
  rolling stats for both players, the latest ensemble prediction, the
  latest de-vigged moneyline (`_fetch_market_win_probs`), and the latest
  book total with prices (`_fetch_market_totals`). v3 prefers the ensemble
  over the moneyline; v4 anchors on the moneyline.
- **Rolling stats are per serve point.** `aces_per_game` and `df_per_game`
  are aces and DF per serve point (`app/ingest/player_stats.py`), despite
  the names.
- **Book totals:** ATP and WTA tour-level only, from The Odds API daily at
  12:45 UTC (48b). Challenger and WTA 125 have none and keep
  `no_market_total`.
- **Storage:** `prop_projection_snapshots` is unique on
  (`prop_id`, `projection_version`), so a v4 row can sit beside the v3 row
  for the same prop with no migration.
- **Snapshot job:** `python -m app.ingest.prop_snapshots`, run by
  `tennis-predictions.yml` on GitHub Actions; it has no dry run.

## In scope

- **Exact match chain (pure):** from two holds and best-of, the match win
  probability, set-count distribution, and total-games distribution, with
  serve order carried across sets.
- **Set-dependence check** against the `tennis_sets` fit, with a stop rule
  fixed before the run, and a match-level hold effect only if the rule
  requires it.
- **Hold solver (pure):** the two holds that reproduce the de-vigged
  moneyline and the book total's de-vigged over price (0.5 with no prices).
  With no book total, the hold level comes from the two players' rolling
  stats (`serve_hold`) and only the moneyline is matched. With no
  moneyline, the ensemble probability stands in and the row is flagged.
- **Game-level Monte Carlo (pure, numpy, seeded):** each service game's
  result and point summary (serve points won and lost) drawn from the exact
  game chain for that server; aces drawn from won serve points and DF from
  lost ones at the player's rates; break points won equal games broken.
  One seeded draw set per match, so both players' props share it.
- **Ace and DF dispersion** measured once from past box scores and frozen,
  so count probabilities are not narrower than reality.
- **Prop adapter (pure):** stat mean and exact over, under and push from the
  draws for every supported stat, plus `recommendation`, `hit_probability`,
  `break_even_pct` and `ev_pct` computed as v3 computes them after 48f, with
  `confidence` null and the flags below.
- **Historical level check** with a pre-registered stop rule: a stat whose
  simulated level misses by more than its threshold is flagged, never tuned.
- **Shadow snapshots:** the snapshot job writes `props-v4` rows beside v3,
  and gains a `--dry-run`.

## Out of scope

- Showing v4 on the props page, best picks, the player page or
  `/tennis/model`, or making it the page's version. That is 48e's and 48g's
  call.
- Any tier, cap, ranking or adoption rule (48f retired tiers; 48e and 48g
  decide adoption).
- Grading any v3 or v4 snapshot, or registering the per-stat, per-tour rule
  (48e). 48c stores; it never reads a v4 line outcome.
- Sportsbook player props (48d), set handicaps (16f, parked), game spreads.
- Changing PrizePicks fantasy scoring: the sim uses the formula already in
  `compute_stat_avg` (10, games +/-1, sets +/-3, aces +0.5, DF -0.5).
- Best-of-5 `total_sets` and `total_tie_breaks`: they keep
  `bo5_unsupported_stat` (the set-dependence fit is best-of-3 only).
- Point-level serve modelling beyond the game chain (first versus second
  serve, server fatigue, in-match momentum beyond step 2's effect).
- Retiring v3 code or the closed-form functions; v3 keeps running unchanged.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Exact match chain (pure)** - new
  `app/core/tennis_match_chain.py`: `match_distribution(hold_a, hold_b,
  best_of)` returning player A's match win probability, the set-count
  distribution and the total-games pmf. Sets reuse the first-set chain's
  scoring (single tiebreak game at 6-6, tiebreak won with
  `hold_a / (hold_a + hold_b)`), the first server of the match is averaged,
  and each later set's first server follows from the previous set's game
  count. *Done when* tests show:
  - equal holds give a 0.5 win probability and a symmetric set-count split
  - set 1 alone matches `first_set_distribution` exactly
  - pmfs sum to 1 within 1e-9 for best-of-3 and best-of-5, a higher hold
    for A raises A's win probability, and higher holds on both sides raise
    the total (raising one side only can shorten the match, since it cuts
    deciding sets; corrected at build)
- [x] **Step 2 - Set-dependence check (read-only, stop rule)** - a backtest
  CLI `python -m app.backtest.tennis_match_sim --sets` that, for win
  probabilities 0.50 to 0.95 and best-of-3, sets the holds to `L + d` and
  `L - d` with `d` bisected to match each probability, at levels `L` of
  0.75 and 0.82, and prints the chain's P(3 sets) beside
  `three_set_probability`. **Stop rule (fixed here, before the run):** if
  the largest gap is under 0.02 at every probability, the chain is used as
  is. Otherwise add one match-level effect: each draw shifts the hold
  difference by a normal amount shared across all sets, its sd fitted in
  the same CLI (`--fit-set-effect`) to minimize the largest gap, frozen as
  a dated constant, and the chain becomes a fixed 9-node Gauss-Hermite
  mixture over it. *Done when* the output and the decision are recorded
  under Results, with a format test for the CLI, and (only if the rule
  fired) a test that the mixed chain reproduces the fitted P(3 sets) within
  0.025 (amended from 0.02 by owner decision 2026-10-28: the best single sd
  leaves 0.023).
- [x] **Step 3 - Hold solver (pure)** - `solve_holds(win_prob, best_of,
  total_line=None, p_over=0.5, stats_level=None)` in the chain module.
  With a total line: the two holds whose chain gives `win_prob` and a
  push-excluded P(total over line) of `p_over`. Without one: the holds
  whose mean equals `stats_level` and whose chain gives `win_prob`. Bounded
  nested search (Illinois false position, bracketed so it cannot loop), the
  hold level within 0.55 to 0.95 and each hold within 0.25 to 0.99
  (amended at build from 0.40 to 0.97: below a 0.55 level the total stops
  rising with the level, and 0.97 capped real ATP lines), and a `clamped`
  result field when a target cannot be met. *Done when* tests show:
  - both targets reproduced within 1e-4 for a best-of-3 and a best-of-5 case
  - swapping the players mirrors the holds
  - a higher line at the same price raises both holds' mean
  - an impossible target returns `clamped=True` without looping
- [x] **Step 4 - Ace and DF dispersion (read-only, measured)** - add
  `--dispersion` to the backtest CLI: download the 2026 TennisMyLife ATP
  and WTA files (`2026.csv`, `2026_wta.csv`, the URLs the ingest uses;
  Challenger and qualifying excluded) and keep each completed side with
  aces, DF and serve points (`svpt` above 0; walkovers and retirements
  dropped). Each player's rate is their leave-one-out 2026 rate (aces or DF
  over serve points in their other matches in the file), with at least 5
  other matches; the rolling rate is not used, since it is overwritten in
  place and includes the match being scored. Compare per-match aces and DF
  with a binomial on that match's serve points at that rate, and fit one
  gamma shape per stat (pooled across tours, a match-level multiplier on
  the rate with mean 1) by method of moments so the simulated variance
  matches the observed. Nothing is written to the database. *Done when*
  the shapes, sample sizes per tour and the variance ratio before and after
  are recorded under Results, frozen as dated constants, with a format test
  and a test of the fit on synthetic counts with a known shape.
- [x] **Step 5 - Service-game point summaries (pure)** - in
  `app/core/tennis_match_sim.py`: `serve_point_prob(hold)`, the inverse of
  `markov_hold` by bisection, and `service_game_table(spw)`, the exact
  distribution of (held, serve points won, serve points lost) for one
  service game, deuce capped at a fixed depth with the remaining mass on
  the last state. *Done when* tests show the inverse round-trips
  `markov_hold` within 1e-6, the table sums to 1, its held mass equals
  `markov_hold(spw)` within 1e-6, and every held row has 4+ points won and
  every broken row 4+ points lost.
- [x] **Step 6 - Game-level Monte Carlo (pure)** - `simulate_match(hold_a,
  hold_b, best_of, ace_rate_a, ace_rate_b, df_rate_a, df_rate_b, draws,
  seed)` in the same module, vectorised over draws with numpy. Each service
  game draws a row from its server's table; tiebreak games are won with the
  chain's tiebreak probability and add no serve points; aces are binomial
  on won serve points with probability `ace_rate / spw` and DF binomial on
  lost ones with `df_rate / (1 - spw)` (both capped at 0.95), each rate
  scaled per draw by step 4's gamma multiplier; step 2's effect applies.
  Returns per-draw arrays for both players: games won, sets won, tie
  breaks, first-set games, aces, DF, breaks, and the match total. `draws`
  defaults to 4,000 (standard error at most 0.008 on a probability).
  *Done when* tests show:
  - the same seed gives identical arrays; a different seed does not
  - mean win rate and P(total over a line) agree with step 1's exact chain
    (mixed over step 2's effect) within 3 standard errors
  - aces never exceed won serve points and DF never exceed lost ones
  - 4,000 best-of-5 draws finish in under 1 second locally
- [x] **Step 7a - Stat values from the draws (pure)** - new
  `app/services/tennis/prop_sim.py` (split from step 7 at build, 2026-10-29,
  to keep each diff reviewable): `stat_values(draws, stat_type, player)`
  returning one value per draw for `total_games`, `total_games_won` /
  `games_won`, `total_sets`, `total_tie_breaks`, both first-set stats,
  `aces`, `double_faults`, `break_points_won` / `break_points_converted`
  and `fantasy_score` (None for any other stat), and
  `line_probabilities(values, line)`, the exact share of draws over, under
  and on the line. *Done when* tests show:
  - every supported stat returns a value per draw, and probabilities sum to 1
  - an integer line gets a push share, a half line none
  - both players' games won sum to the total on every draw, and fantasy
    score equals the formula worked by hand on one draw
  - an unsupported stat returns None without raising
- [x] **Step 7b - Prop rows (pure)** - in the same module,
  `sim_prop_lines(props, lines, inputs)` builds `PropLine`s from the inputs
  `enrich_with` already loads, one simulation per `match_id`, seeded from
  it. (Amended at build: it takes the v3 rows for the same props and
  replaces only their projection fields, so v4 inherits v3's flags, audit
  and display fields with no copied flag logic, and a v4 row can only exist
  beside a v3 one. The one copy is `_enrich`'s hard-block flag set, which
  is local to that function; 48f leaves that list as it is.) From 7a's values: `stat_avg` (the mean), `p_over`, `p_under`,
  `p_push`, then `recommendation`, `hit_probability`, `break_even_pct` and
  `ev_pct` exactly as the v3 path computes them after 48f (shared helpers
  imported, not copied; only `ev_pct` and the break-even are read from
  `assess_prop`), with `confidence` null. Ace and DF rates are the
  player's per-serve-point rate times 48a's matchup factor and surface
  factor; a missing opponent uses factor 1.0. Missing inputs follow v3: no
  player rate leaves that stat without a projection (`projection_status`
  not `ok`), and a match with neither a moneyline nor an ensemble
  probability is not simulated (`missing_prediction`). Best-of-5
  `total_sets` and `total_tie_breaks` keep `bo5_unsupported_stat`.
  *Done when* tests show:
  - two props on the same match read the same draws
  - a row with no moneyline carries `no_market_moneyline`; one with no book
    total carries `no_market_total`; every row has `confidence` null
  - a player with no ace rate gets no aces projection, and a match with no
    win probability gets no v4 projection, without raising
  - `projection_inputs` carries the load-bearing keys below
- [x] **Step 8 - Historical level check (read-only, stop rule)** - add
  `--level` to the backtest CLI: completed 2026 ATP and WTA matches with a
  pre-start de-vigged moneyline and a stored book total (the Bet365 era,
  before 2026-10-26), simulated from their pre-start odds and current
  rolling stats, mean bias by tour for each stat in step 7a. **Stop rule
  (fixed here, before the run):** a stat and tour whose absolute mean bias
  is at least 0.25 games (game stats), 0.5 (aces, DF), 0.25 (break points
  won), 0.05 (sets, tie breaks) or 1.5 points (fantasy score) goes in
  `SIM_LEVEL_UNVERIFIED`, and its v4 rows carry `sim_level_unverified`.
  Nothing is tuned. Rolling stats include these matches (overwritten in
  place), so only the mean bias is read, as in 48a. *Done when* the table
  and the resulting constant are recorded under Results, with a format test
  and a test that a listed stat carries the flag.
- [x] **Step 9 - Shadow snapshots and dry run** *(after 48f is on `master`)*
  - merge `master` first. `app.ingest.prop_snapshots` builds v3 lines as
  today, builds v4 lines with `sim_prop_lines` from the same loaded inputs,
  and stores both, each eligible line once per version. `to_snapshot` takes
  the version; `SIM_PROJECTION_VERSION` (see Data / contracts) sits beside
  `PROJECTION_VERSION` (unchanged, `props-v3`). A `--dry-run` prints the
  counts per version and inserts nothing. The page, best picks and
  `/tennis/model` are untouched. *Done when* tests show a v3 and a v4
  snapshot for the same eligible prop, `--dry-run` inserts nothing, and
  `PROJECTION_VERSION` is still `props-v3`. Verify passes. (Built
  2026-10-29: the job loads the inputs once with `prop_sim.load_sim_inputs`,
  which mirrors `_enrich_props`'s loads so `routers/props.py` stays
  unchanged, then builds v3 with `enrich_with` and v4 with `sim_prop_lines`.
  `sim_prop_lines` now holds one match's draws at a time. 48f kept
  `props-v3`, so the simulation takes `props-v4`.)
- [x] **Step 10 - Local check** - run `python -m app.ingest.prop_snapshots
  --dry-run` locally and record: lines per version, the share with a book
  total and with a moneyline, flag counts, the share with `sim_clamped`,
  total sim time and peak memory, and five example rows (a total, a games
  won, a WTA double fault, a first set, a fantasy score) with v3 and v4
  side by side. *Done when* the evidence is recorded under Results. No real
  insert without a separate yes.

## Files / areas

- New: `api/app/core/tennis_match_chain.py`,
  `api/app/core/tennis_match_sim.py`,
  `api/app/services/tennis/prop_sim.py`,
  `api/app/backtest/tennis_match_sim.py`, and tests
  (`test_tennis_match_chain.py`, `test_tennis_hold_solver.py`,
  `test_tennis_match_sim.py`, `test_prop_sim.py`,
  `test_tennis_match_sim_backtest.py`)
- Changed (step 9, after 48f): `api/app/ingest/prop_snapshots.py` (both
  versions, `--dry-run`), `api/app/services/tennis/prop_snapshots.py`
  (version argument and the sim constant),
  `api/tests/test_prop_snapshot_ingest.py`, `api/tests/test_prop_snapshots.py`
- Read, not changed: `app/routers/props.py` (`enrich_with` inputs and the
  EV and side helpers, imported rather than copied),
  `app/core/prop_projection.py` (`serve_hold`, `markov_hold`, tour rates,
  surface factors), `app/core/tennis_first_set.py`, `app/core/tennis_sets.py`
- Docs: `docs/commands.md` (the `--dry-run` flag and the two versions)

## Data / contracts

- **No schema change.** v4 rows use `prop_projection_snapshots` as is.
- **Load-bearing:** `SIM_PROJECTION_VERSION = "props-v4"` names the
  simulation's snapshots (`props-v5` if 48f bumps to `props-v4`). It is
  never pooled with v3, and its rows exist only for lines that also have a
  v3 row from the same run.
- **Load-bearing:** v4 `projection_inputs` keys, read by 48e:
  `sim_hold_player`, `sim_hold_opponent`, `sim_win_prob`,
  `sim_win_prob_source` (`market` or `ensemble`), `sim_total_anchor`
  (`book` or `stats`), `market_total_games` and `market_total_over_prob`
  when a book total exists, `sim_clamped`, `sim_draws`, `sim_seed`,
  `sim_set_effect_sd` (0.140).
- **Load-bearing flags:** `no_market_total` (unchanged meaning and stat
  list), `no_market_moneyline` (ensemble stood in), `sim_level_unverified`
  (step 8). Flags only: no tier, no cap. 48e reads them to slice or exclude.
- **`confidence` is null on every v4 row**, as on v3 rows after 48f.
- **Determinism:** the seed is derived from `match_id` and the stored
  inputs, so a re-run on the same inputs reproduces the row exactly.
- `PROJECTION_VERSION` stays `props-v3`, so every page and report keeps
  reading v3.

## Testing

- Steps 1, 3, 5, 6, 7a, 7b: unit tests on pure functions with synthetic inputs,
  no database. Monte Carlo assertions use fixed seeds and 3 standard error
  bounds, never exact floats from a random run.
- Steps 2, 4, 8: CLI format tests plus one recorded local run each, the
  stop rule written here before the run.
- Step 9: ingest tests with the repository mocked, as the existing snapshot
  ingest tests do.
- Step 10: local evidence, not tests.
- Final gate: `npm --prefix web run verify && cd api && python -m pytest`.

## Notes for the AI

- **No fitting on outcomes 48e will grade.** Steps 2, 4 and 8 read only
  completed matches from before this spec and no PrizePicks line outcome.
  Step 2 fits to an existing held-out model, step 4 to box-score variance,
  and step 8 flags rather than tunes. Do not tune past a stop rule. No
  tennis holdout season (2023-2025) is read.
- **48e comes before any grading.** Nothing here reads a v3 or v4 outcome.
- **No tier code.** Do not call or restore `assess_prop` tiers,
  `_cap_confidence`, `_MAX_PROP_CONFIDENCE` or `TIER_RULE_VERSION`; 48f
  removes or retires them.
- Holds, not serve stats, carry the market: player rolling stats enter only
  through the no-total level fallback and the ace and DF rates (with 48a's
  tour league rates and surface factors). The WTA first-set underdog shift
  is a v3 correction to the stats chain and is not applied under v4; step 8
  checks first-set level instead.
- Keep `app/core/` pure: numpy is fine, no DB or I/O.
- Keep the snapshot job's memory small: simulate one match at a time and
  drop its draws after its props are built.
- `routers/props.py` stays the v3 source; import its helpers, do not edit
  its projection path.
- Match the existing comment density. No em dashes.
- **Interview guide:** update at `/complete` (a modelling change with
  measured evidence). It is untracked; never stage it.
- 44b lives on `feature/44b-nba-pover-confirmation`; never touch it here.

## Results

- **Step 2 set dependence (2026-10-28 22:11 UTC,
  `python -m app.backtest.tennis_match_sim --sets`):** the constant-hold
  chain overstates P(3 sets) at every win probability, by +0.062 to +0.107
  (largest at p 0.80), identically at hold levels 0.75 and 0.82. The stop
  rule (0.02) fired, so the match-level effect is required.
- **Step 2 effect fit (2026-10-28 22:12 UTC, `--fit-set-effect`, 2m 12s):**
  sd **0.140** on the hold gap (split evenly between the two holds, one
  draw per match, 9-node Gauss-Hermite). Largest residual gap 0.023
  (level 0.75, p 0.80: +0.023; level 0.82, p 0.95: -0.022); at level 0.82
  every other probability is within 0.008, at level 0.75 within 0.022. One
  sd cannot fit both levels exactly, since a shift in hold units moves a
  low-hold match more. It missed the original 0.02 done-when by 0.003;
  owner decision 2026-10-28: accept, frozen as `SET_EFFECT_SD = 0.140` in
  `app/core/tennis_match_chain.py`, done-when amended to 0.025.
- **Step 3 solver on real lines (2026-10-28, read-only scratchpad run, the
  12 Pinnacle totals stored since 48b with each match's latest moneyline):**
  8 solved exactly, 4 clamped (3 ATP at the 0.99 hold ceiling: lines 25.0,
  22.0 and 23.0 at p 0.73 to 0.84; 1 WTA at the 0.55 level floor, 21.5 at
  p 0.41). 0.2 to 0.8 s per best-of-3 match, about 2 s best-of-5. **Finding
  for steps 7 and 8:** ATP holds solve to 0.92 to 0.99 against a typical
  0.80, WTA to 0.52 to 0.80. With the set effect, the game chain plays
  fewer games at ordinary holds than Pinnacle prices, so only near-perfect
  serving stretches the match, and higher holds mean fewer serve points
  per game (which lowers aces and double faults). Step 8's level check is
  the guard; `sim_clamped` is recorded on every row. See Decided before step 4.
- **Checks after step 3 (local):** Verify passed, web 984 tests and a clean
  build, API 4,861 tests.
- **Step 4 dispersion (2026-10-29, `--dispersion`, TennisMyLife `2026.csv`
  and `2026_wta.csv`):** 9,020 player-matches with at least 5 other matches
  (ATP 4,671, WTA 4,349). Observed variance over model variance:

  | Stat | Tour | Binomial | With gamma |
  |---|---|---|---|
  | Aces | ATP | 2.641 | 0.953 |
  | Aces | WTA | 2.076 | 1.180 |
  | Aces | all | 2.477 | 1.000 |
  | DF | ATP | 1.334 | 1.035 |
  | DF | WTA | 1.338 | 0.973 |
  | DF | all | 1.336 | 1.000 |

  Shapes **5.78** (aces) and **12.89** (DF), frozen as `ACE_RATE_SHAPE` and
  `DF_RATE_SHAPE` in `app/core/tennis_match_sim.py` and passed by
  `prop_sim`. A binomial alone made ace counts about 2.5 times too narrow.
  Pooled, the shape leaves WTA aces 18% narrower than observed and ATP
  aces 5% wider; per-tour shapes were not specced. The leave-one-out rate
  carries its own estimation error, so the shape covers that too, as the
  simulation's rolling rate does. Some of the spread is the opponent,
  which 48a's matchup factor also adjusts, so v4 counts may run slightly
  wide; step 8 reads level, not spread.
- **Step 8 level check (2026-10-29, `--level`, 1m 40s):** 523 completed
  best-of-3 matches (ATP 300, WTA 223) with a pre-start moneyline and a
  pre-start Bet365 total, 2026-09-26 to 2026-10-25, simulated through
  `build_match_sim`; 23 unfinished were skipped. No best-of-5 match had a
  stored total. The DraftKings totals (2026-03 to 2026-05) were left out,
  as the spec names the Bet365 era. Box-score stats cover the 973
  player-matches with a joined TennisAbstract box score. Bias is model
  minus played:

  | Stat | ATP bias | WTA bias | Stop |
  |---|---|---|---|
  | Total games | -0.07 | **+0.63** | 0.25 |
  | Games won | -0.03 | **+0.32** | 0.25 |
  | First-set total | +0.15 | +0.04 | 0.25 |
  | First-set games won | +0.07 | +0.02 | 0.25 |
  | Aces | +0.16 | **+0.77** | 0.5 |
  | Double faults | +0.35 | +0.20 | 0.5 |
  | Break points won | **-0.31** | **+0.84** | 0.25 |
  | Sets | **-0.06** | **+0.05** | 0.05 |
  | Tie breaks | **+0.10** | +0.01 | 0.05 |
  | Fantasy score | -0.35 | +0.09 | 1.5 |

  Eight stat and tour pairs fired (bold) and are frozen in
  `SIM_LEVEL_UNVERIFIED` in `app/services/tennis/prop_sim.py`; their v4
  rows carry `sim_level_unverified`. Nothing was tuned. WTA sets' bias rounds
  to the 0.05 stop and is at or above it unrounded, so it is unverified.
  Context, not used: the mean Bet365 line sat 2.03 games under the played
  mean for ATP and 1.15 for WTA (a line is nearer a median and totals skew
  long), so the WTA total miss is the simulation's spread around the line,
  not the book's level. WTA plays too many games and too many breaks,
  consistent with WTA holds solving low (step 3). ATP tie breaks run high
  and break points low, consistent with ATP holds solving near 0.99. The
  first-set chain, double faults and fantasy score held for both tours.
- **Checks after step 8 (local):** Verify passed, web 984 tests and a clean
  build, API 4,948 tests.
- **Step 10 local check (2026-10-29 evening UTC, `--dry-run`, 8.4 s):**
  663 PrizePicks props loaded, 71 eligible per version (`props-v3` 71,
  `props-v4` 71), nothing inserted. Skipped: 301 invalid match link, 151
  started, 106 live, 28 missing player, 6 missing match. A late-day run, so
  the eligible slate is thin: all 71 are WTA, on 8 matches.
  - **Anchors:** 57 of the 71 v4 rows have a projection; all 57 anchor on
    the market moneyline and on the stats level, since no eligible match had
    a book total (The Odds API covers tour level only). None clamped. The
    other 14 have neither a moneyline nor an ensemble probability and get
    no v4 projection (v3 still projects them from stats).
  - **Flags (v4):** `sim_level_unverified` 55, `no_market_total` 47,
    `ungraded_stat` 14, `missing_prediction` 14. v3 carries the same flags
    except `sim_level_unverified`. No tiers: `confidence` is null on all
    142 rows (48f). Recommendations: v3 64 OVER, 7 UNDER; v4 57 OVER, 14
    none (most of today's lines are over-only goblins and demons).
  - **Cost:** simulating all 39 linked matches (every loaded prop, as the
    job does) took 30.9 s, about 0.8 s a match. Peak Python allocation
    during the simulation 5.7 MB (`tracemalloc`); peak process working set
    for the whole run 124 MB. The job runs on GitHub Actions, not Render.
  - **Examples, v3 then v4** (mean, P(over), P(under)):

    | Row | Line | v3 | v4 |
    |---|---|---|---|
    | WTA total games (demon) | 17.5 | 17.54, 0.429, 0.571 | 19.19, 0.495, 0.505 |
    | WTA games won (demon) | 12.5 | 13.00, 0.567, 0.433 | 12.75, 0.332, 0.668 |
    | WTA double faults (demon)* | 2.5 | 2.36, 0.476, 0.524 | 2.30, 0.393, 0.608 |
    | WTA first-set total (goblin) | 6.5 | 9.44, 0.957, 0.043 | 8.65, 0.890, 0.110 |
    | WTA fantasy score (standard)* | 19.0 | 21.50, 0.583, 0.417 | 16.12, 0.528, 0.447 |

    \* Not eligible at capture (started or live), shown for comparison;
    no eligible double fault or fantasy row existed. The first three
    eligible rows share one lopsided match (win probability 0.93, holds
    0.73 and 0.40): v4's totals are skewed by deciding sets, so a mean
    above the line can sit beside P(over) under 0.5. The fantasy gap
    (21.5 against 16.1) is the largest v3 and v4 difference here; step 8
    found WTA fantasy level within 0.09.
  - **Finding:** a v4 row with no win probability gets `projection_status`
    `unsupported_stat`, not `missing_prediction` as step 7b says, because
    `_sim_line` maps every unprojected `ok` v3 row to `unsupported_stat`.
    The `missing_prediction` flag is still on the row. Fixed 2026-10-29:
    an unsimulated match now gives `missing_prediction`, and a stat with no
    rate keeps `unsupported_stat` (both tested).

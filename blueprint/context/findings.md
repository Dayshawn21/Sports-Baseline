# Findings

> **Generated file.** The findings ledger: review findings raised by `/audit`
> against the work in progress, each with a durable ID, severity (P0-P3), and
> status. `/implement` marks repaired findings `fixed`, a later `/audit` pass
> moves them to `closed`, and `/complete` refuses to merge while any P0 or P1
> finding is `open` or `fixed`, then archives resolved findings with the work
> and resets this file.

### F-20 [P3] open - Bankroll builder retains an unused dataclasses import

**File:** api/app/services/tennis/bankroll_builder.py:10
**Found:** 2026-10-18 by /audit (scope: imports in the two F-19 modules; lens: quality). Present before this fix.
**Why it matters:** `field` is imported from `dataclasses` but has no name load in the module, contrary to the no-unused-import convention. No runtime behavior is affected.
**Suggested fix:** Remove `field` from the import during a future cleanup.
**Resolution:** Open, nonblocking. F-19's three named imports are repaired and closed independently.

### F-07 [P3] open - Prediction grading has no loss comparison for the served no-ML path

**File:** api/app/services/tennis/track_record.py:147; api/app/services/tennis/track_record.py:165; api/app/backtest/tennis_predictions.py:31
**Found:** 2026-10-18 by /audit (scope: tennis prediction system; lenses: correctness, calibration coverage, tests)
**Why it matters:** Loss tables and calibration require every member of
`MARKET_COMPONENTS`, including ML, even though current Challenger predictions
intentionally have no ML and market-anchored v3 assigns ML zero weight. The
existing endpoint, read on 2026-10-18, returned 455 completed
`ensemble-v3+lgbm-none` predictions with 212 market prices, but all four score
groups had n=0 and no component rows. Challenger CLV still reports 135 eligible
nonzero gaps, confirming this is not simply an empty version. Separately,
market-free fallback rows cannot appear in the market-paired table by design;
the endpoint should not be described as validating that fallback.
**Suggested fix:** Add an explicitly labelled ensemble-versus-market paired
comparison requiring only those two probabilities. Keep the original all-four
comparison and its common-row contract intact, with separate counts for any
ELO/ML comparisons. Test a Challenger row with ML=None, plus missing/gated ELO
and market-free rows. This is reporting coverage, not a model change; tests
and existing forward grading suffice. Do not pool model versions or change the
26d adoption rule. Downgraded P2 to P3 on 2026-10-18 review: a reporting
coverage gap, not a correctness risk to served output.
**Resolution:**

### F-09 [P3] unverified - Derived and serve-edge confidence is not validated by the existing grading

**File:** api/app/services/tennis/best_picks.py:513; api/app/services/tennis/best_picks.py:595; api/app/services/tennis/best_picks.py:681; web/src/utils/tennisPropBoard.ts:142
**Found:** 2026-10-18 by /audit (scope: tennis prediction system and consumers; lenses: calibration, tests)
**Why it matters:** Serve Edge puts first-serve points-won rate into `model_prob`
and a raw-probability confidence tier; it is not a probability of a defined bet
winning. Derived BO5 estimates use match win probability cubed and other
heuristics; BO3 uses the existing fitted `set_outcomes` curve with an additional
dominance boost. Win-a-set board rows can retier these estimates at .70/.62.
They remain unpriced, and neither 26a moneyline grading nor 26f PrizePicks
snapshots grades these selections. This is a calibration/evidence limitation,
not proof that their forecasts are wrong. The 26d follow-up explicitly left
derived and serve-edge picks unchanged; no rejected signal should be revived
under the guise of repairing them.
**Suggested fix:** Do not retune from this audit. If pursued after the confirmed
bugs, choose one precisely defined derived event, freeze its current prediction
before start, and pre-register a forward comparison and adoption rule before
reading outcomes. Serve metrics should be identified as descriptive unless a
defined outcome is being forecast. Modelling changes require forward evidence;
unit tests alone cannot establish calibration or edge.
**Resolution:** Unverified modelling follow-up. No new verdict, fit or adoption.
Downgraded P2 to P3 on 2026-10-18 review: no defect to repair; a candidate
build-plan item rather than a bug.

### F-12 [P2] unverified - Served P(over) runs below observed over rates in 2026, most on goblin lines

**File:** api/app/services/nfl/slate.py:48; api/app/core/nfl_over_probability_fit.py; web/src/utils/nflSignal.ts:47
**Found:** 2026-10-18 by /audit (scope: NFL prediction system and consumers; lens: calibration)
**Why it matters:** The public `/nfl/model/prop-lines?season=2026` read
(27a snapshot, graded 2026-10-16 20:42 UTC) scores `nfl-pover-v1` against
settled lines:

| Odds type | Scored | Mean P(over) | Over rate | Gap |
|---|---|---|---|---|
| standard | 1,104 | 0.427 | 0.469 | +0.042 (about 2.8 SE) |
| goblin | 3,018 | 0.543 | 0.650 | +0.107 |
| demon | 5,097 | 0.240 | 0.238 | -0.003 |

Reliability bins: predicted 0.10 / 0.31 / 0.49 / 0.67 against observed
0.15 / 0.36 / 0.53 / 0.68. The pre-registered 27g display rule passed on the
2025 cross-fit; this forward read suggests overs are under-predicted at lines
below the projection. **Not confirmed as a served defect:** 27a replays
today's code rather than reading frozen rows, ladder rungs of one player-game
are correlated (so nominal SEs overstate certainty), and no endpoint reports
calibration of the frozen P(over) that 27j grades. Consequence if real: the
drawer's "Over N% · Under M%" text is biased toward under, and standard-under
picks (p_under >= 60.7%) become more numerous; 27j's rule will judge that
slice as registered.
**Suggested fix:** Change nothing in the fit, the display gate or the ranking
rule from this read. If pursued, add a reporting-only frozen-row calibration
to the model page (no new verdict). Any refit or method change is a new
`nfl-pover-v2` under a rule fixed before reading its outcomes, validated
forward, never on the 2025 holdout again.
**Resolution:**

### F-13 [P3] open - The slate's line query has no pre-kickoff cutoff, unlike NBA's

**File:** api/app/repositories/nfl.py:1159; api/app/services/nfl/track_record.py:66; api/app/ingest/prizepicks_props.py:85
**Found:** 2026-10-18 by /audit (scope: NFL prediction system and consumers; lenses: leakage, correctness)
**Why it matters:** `_LATEST_LINES_CTE` takes each provider prop's newest
snapshot regardless of kickoff, and the PrizePicks ingest stores whatever the
board returns with no start check. NBA's equivalent reads
`(g.start_utc IS NULL OR l.fetched_at < g.start_utc)` (`nba.py:409`, `:452`,
tested). Two latent effects: a started game's page would show a post-kickoff
line beside a pre-game projection, and 27a would silently drop the call,
because its edges are keyed by the latest snapshot id while
`get_gradeable_prop_lines` grades the last pre-kickoff id. Freezing is safe
(it only freezes unstarted games). Read-only count: 0 post-kickoff modelled
snapshots among about 96,000 in 2026, so there is no current effect.
**Suggested fix:** Join the game in the CTE and apply NBA's cutoff, with a
recorded-SQL test. Output is identical on today's data. No model change.
**Resolution:**

### F-14 [P3] open - Future-week slate snapshots from the 37d backfill are served at each week rollover, and the payload has no build time

**File:** api/app/ingest/nfl_slate_snapshot.py:29; api/app/repositories/nfl.py:943; api/app/services/nfl/slate_cache.py:102
**Found:** 2026-10-18 by /audit (scope: NFL report snapshots; lens: data quality)
**Why it matters:** `report_snapshots` holds 2026 weeks 7 to 18 built
2026-10-16 20:08 to 20:09 UTC (`--weeks all` backfill). `--weeks current`
writes only the current week and the one before. The current week rolls 12
hours after the last kickoff (Tuesday about 12:15 UTC), and the first refresh
after that is `nfl-weather.yml` at 14:00 UTC (subject to the same cron
delays). In between, production serves a copy several days old for the new
week. `NflSlateResponse` carries no computed time, so neither the page nor a
reader can tell. No wrong-week or cross-season serving was found: the key is
`(nfl_slate_week_<N>, season)` and the request names both.
**Suggested fix:** Have `current` also write the next week, or stop
backfilling future weeks; optionally expose the snapshot's `computed_at`.
Tests on `parse_weeks`. Display freshness only, no model change.
**Resolution:**

### F-15 [P3] fixed - Frozen-row grading loader does not apply MODELLED_MARKET_FILTER

**File:** api/app/repositories/nfl.py:2244
**Found:** 2026-10-18 by /audit (scope: NFL frozen predictions; lens: correctness)
**Why it matters:** The 34a rule says every reader that projects, grades or
freezes lines applies `MODELLED_MARKET_FILTER`. `get_frozen_gradeable_lines`
grades but relies on the freeze having written modelled lines only (true
today: rows come from `build_slate`, whose CTE filters). A line-only row
written by any other path would reach 27j, where `STAT_COLUMN_BY_MARKET`
has no column and it would settle as `void_dnp` rather than fail loudly.
**Suggested fix:** Add the filter to the `frozen` CTE and a recorded-SQL test,
matching `get_gradeable_prop_lines` and `get_frozen_coverage`. Output is
identical today.
**Resolution:** Fixed by 39c Step 1, approved 2026-10-19. The frozen CTE now
applies `V4_MARKET_FILTER`, the explicit nine-market subset of the modelled
universe, before latest-row selection. Recorded-SQL and mixed-market predicate
tests cover the guard in `test_nfl_v4_markets.py`. Full Verify passed (612 web
tests, production build, 2,836 API tests). Awaiting independent `/audit`
re-review; this repair does not close the finding.

## Tennis audit evidence, 2026-10-18

**Scope:** A focused audit of live tennis prediction producers, inputs,
downstream recommendation consumers, existing grading and relevant tests.
Reviewed on `master` at `3af62d8`; no active feature, so no feature merge-base
comparison applies. The pre-existing modification to `project-overview.md`
was left untouched. Only this ledger was edited by the audit. F-02 is outside
scope and unchanged. Added F-03 through F-09; closed no findings.

**Actual input/consumer trace:**

- `predictor.predict_matches` fetches latest player/ELO/rolling-stat/odds data,
  constructs features and computes ATP/WTA LightGBM through `ModelRegistry`.
  The live ELO component uses TennisAbstract surface ELO when both exist,
  otherwise overall ELO. Computed ELO is a separate v6 feature, not a replacement
  for the live ELO component (26d D7).
- `HistoryIndex` and `EloIndex` exclude results on or after the match date.
  Their as-of form, H2H and computed ELO overwrite the corresponding snapshot
  feature definitions. v6's feature allowlist excludes rolling serve/return
  snapshots and market price. Missing inputs use the artifact's NaN convention.
  Latest TennisAbstract snapshots/rolling stats are valid live inputs, not a
  license to reconstruct past forecasts. No such reconstruction was performed.
- A market price selects `ensemble-v3`'s frozen 2022 logit coefficients:
  ATP (1.139189, -0.078181), WTA (1.460511, -0.422608), Challenger
  (1.110494, 0.083259), in market/ELO order. Missing/fallback/unreliable ELO
  yields market-only; reliability uses fewer than 10 prior matches or a gap
  of at least .15. ML has zero weight. Stale/high-overround flags do not alter
  this probability. These coefficients are not percentage shares.
- Without market odds, the frozen hand-set path remains: ATP ELO/ML base
  .35/.40, WTA .40/.45, other tours .40/.40, normalized over usable sources;
  unavailable or unreliable components are omitted. It is intentional fallback
  behavior, not a new adoption of the historically rejected ELO-plus-market
  blend. It has no separate market-paired validation in the endpoint.
- Backend best picks suppress moneylines, but still build BO3/BO5 derived,
  serve-edge, player prop, and priced match-total/game-spread picks. Derived
  edges compare with hardcoded baselines; only priced picks have EV. F-03 is
  the separate frontend moneyline bypass.
- Props use surface stats at >=10 matches, otherwise all-surface stats;
  opponent stats; latest stored match prediction with market fallback; and the
  newest market total >=17, otherwise the existing hold-based estimate.
  Aces/DF input columns named `*_per_game` actually hold rates per serve point,
  matching their service-point multiplier. Fixed surface/matchup/distribution
  factors remain unchanged. First-set props stay ungraded/LEAN-capped and
  excluded from best picks. BO5 set-count props are blocked on the board.
- `props-v2` snapshots call the board's enrichment after daily predictions,
  persist once per prop/version, and are graded from stored recommendations.
  Latest snapshots per player/match/stat/type/line are used. Score-derived
  settlement and the opponent/score box-score join reject unfinished or
  ambiguous outcomes. Fantasy and other unsupported settlement stats remain
  outside scored evidence. Daily snapshots do not claim to capture later page
  views or the independently calculated best-pick cards.

**Existing grading read only:** Public GETs under
`https://sportapp-api-ftsf.onrender.com/tennis/model/`, graded at approximately
2026-10-18 15:31 UTC (10:31 AM CDT). Read `predictions`, `prizepicks-lines`,
`prop-tiers`, and `predictions?model_version=ensemble-v3%2Blgbm-none`.
No paid odds request, ingest, training, database mutation, historical export,
holdout command or 2023-2025 holdout data read occurred.

- Current v3+v6: 314 completed score-eligible predictions, 200 with market;
  194 have all components for ATP+WTA comparison. Ensemble log loss .623424
  versus market .623642, paired difference -0.000218 +/- .003160 (one SE).
  Brier .217820 versus .217406. This does not demonstrate an edge. ELO and ML
  paired loss gaps are +.033323 +/- .012741 and +.062831 +/- .015243.
  Calibration bins have only 1 to 33 observations, too thin to justify a refit.
  On 29 gaps >=3 points, 14 prices moved, 3 toward and 11 away; mean move
  toward the model is -.626 percentage points. These are descriptive forward
  results, not a rerun of the adoption gates.
- `props-v2` standard tiers: LOCK 96/183 (52.46%), STRONG 39/89 (43.82%),
  LEAN 135/254 (53.15%), versus assumed break-even 57.74%. The fixed rule's
  mature sample is 180 LOCK, 86 STRONG, and 213 LEAN. LOCK/STRONG remain
  **accruing**; LEAN is **reject**, at 53.05% in its fixed sample. Neutral
  coloring does not mean a pass. Preserve the 200-pick, whole-mature-days,
  three-day-lag, >2-SE rule and the final `props-v2` reject. Do not restart its
  clock or change thresholds after this read.
- Raw standard line over rates include total games 49.02%, games won 49.56%,
  and aces 36.11%. These are unconditional line-settlement rates, not the
  model's selected-pick calibration; they do not justify adopting an under
  signal. The tier endpoint reports 481 standard recommendations awaiting
  settlement and excludes 5,272 graded nonstandard lines. Missing box scores
  and unsupported fantasy settlement limit coverage; absence is not a win.
- Read the 26a-26f archives for historical decisions only. The 26c rejected
  ELO/hand-set candidates, 26d adopted frozen market anchoring, no ML weight,
  no live ELO-source switch, moneyline-off follow-up, first-set restrictions,
  and the existing total-games set-mixture rule are preserved. No archive or
  pre-registered rule was changed. The historical holdout read count stays two.

**Verification:**

- API: `.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider` on
  `test_ensemble`, `test_tennis_market_blend`, `test_asof_features`,
  `test_elo_history`, `test_train_features`, `test_feature_snapshot`,
  `test_predict_matches`, `test_best_picks`, `test_props_audit_projection`,
  `test_props_router_best_of`, `test_prop_side`, `test_prop_snapshots`,
  `test_prop_snapshot_repository`, `test_prop_snapshot_report`,
  `test_tennis_prediction_report`, `test_tennis_grading`,
  `test_track_record_core`, `test_track_record_service`, and
  `test_track_record_routes`: **268 passed**, one dependency deprecation
  warning. The market-blend report tests use synthetic cases only. No skipped,
  xfailed or placeholder tests appeared in this executed set.
- Web: `npm.cmd run test -- src/utils/tennisPropBoard.test.ts
  src/utils/tennisPropCards.test.ts src/utils/tennisSlate.test.ts
  src/utils/tennisMatch.test.ts`: **111 passed**. Initial PowerShell/npm and
  esbuild sandbox failures were resolved with npm.cmd and approved execution
  outside the sandbox. No dependencies were installed.
- Ran in-memory synthetic reproductions for F-04, F-05 and F-06 using existing
  fixture constructors; wrote no source or new test files. An initial API test
  invocation named a nonexistent test file and ran no tests; the corrected
  explicit selection above is the reported passing run.
- Excluded dependency/build/cache directories, raw historical datasets and all
  holdout execution. This is not a full-repository security/performance audit,
  a browser QA pass, a new training evaluation or a full Verify/build run.
  Live-data prevalence of the snapshot timing defect was not queried.

**Smallest next improvement:** F-03 first: enforce the already-approved
moneyline-off decision on the prop board, with a positive-EV regression proving
no BET/actionable/green moneyline recommendation survives. This needs **tests
and a UI check**, not forward model validation. Then F-06, because it can
contaminate the pre-registered tier sample and is hard to correct after the
fact. Then F-04 and F-05 as one consumer-parity fix. Keep F-07 reporting coverage and F-08 future
training isolation separate. Any probability, coefficient, distribution, tier
threshold or new derived-signal change must be versioned and **validated
forward**, under a rule fixed before reading its outcomes.

## NFL audit evidence, 2026-10-18

**Scope:** A focused audit of everything that produces or displays NFL prop
and game-line numbers, from inputs to the web pages. Lenses: correctness,
data quality, future-data leakage, calibration, tests. Reviewed on `master`
at `3af62d8`; no active feature, so no merge-base comparison applies. The
pre-existing edits to `findings.md` and `project-overview.md` were left as
found. Only this ledger was edited. Added F-10 through F-15; changed no
earlier entry.

**Input/consumer trace (what was checked, and held):**

- **One projection path.** `build_slate` reads lines (`_LATEST_LINES_CTE`,
  modelled markets only), pre-week baselines, team-game DVP, US moneyline,
  rosters, injuries, depth, snaps and TD history. It then applies team-game
  DVP (27c) and the season blend (27d) per row, and `_slate_line` skips the
  moneyline for `MONEYLINE_UNSCALED_MARKETS` (27e) and applies usage only to
  receiving markets. Game environment and wind are never set in production
  (27e and 27k were rejected). P(over) comes from `slate_over_probability`,
  gated on full game, a shown market, 4+ label games and
  `FIT_PROJECTION_MODEL_VERSION == NFL_PROJECTION_MODEL_VERSION`.
- **As-of cutoff held** on every stat input: player, position, opponent and
  league baselines, team-game DVP and opponent history (completed games
  only), recent form, snap and TD history, and team records all use
  `season < S OR (season = S AND week < W)`. The roster is the latest row at
  or before week W, and injuries and depth are week W's pre-game rows. These
  feed team assignment and flags, and only the team changes a projection.
  Unverified edge case: a game postponed past the next week's kickoff would
  enter a 27a replay of that next week.
- **Consumer parity held.** `/nfl/slate` is the only source of projections,
  edges and P(over). The board, slate digest (`slateDigest`), game-page props
  (`nflGameProps`, board as of kickoff), player page (`playerWeekLines`) and
  all three evidence drawers rank through `buildNflPropBoard` on that one
  payload; none recomputes. Frozen rows copy the same `NflSlateLineSchema`
  fields. There is no NFL `/games/{id}/props` endpoint (that is NBA's).
  Noted limitation, not a finding: `nfl-prop-odds.yml` refreshes rosters,
  injuries and depth and re-snapshots without freezing, and today it ran
  (15:51 UTC) after the 15:00 freeze. Already-frozen line ids can then show
  newer flags on the page; projections change only if a player's team does.
- **Display rules held.** Every NFL page and all three drawers sit under the
  `.nfl-slate` root, which sets `--nfl-green` and `--nfl-red` to the text
  color. The digest reads "reference, not picks", the game model reads "not
  a pick", and best line reads "Reference, not a pick". Anytime TD has no
  edge (`edge_is_comparable`, mirrored by `isRateable`) and ranks by
  probability. P(over) is never sorted on or compared to a payout. The only
  payout comparison is the player page's uncolored past-line meter (allowed
  by 33c). Model-page colors follow `verdict_signal` and `rate_signal`.
- **Filters held.** A static scan of every `sport_*` alias in NFL SQL string
  literals (repositories, NFL services, ingest, backtests), checked against a
  probe, found no read without its `sport = 'nfl'` filter. Every
  `sport_game_odds` reader names a provider; pre-36a readers use
  `the_odds_api_us` only. `MODELLED_MARKET_FILTER` is on the slate CTE, 27a
  lines and frozen coverage, but not the frozen loader (F-15).
- **Freezing and grading held** apart from F-10. `freeze_rows` skips games at
  or past kickoff, and the frozen and 27a loaders require
  `fetched_at < start_utc` and `generated_at < start_utc` against the current
  start time, so a delayed or corrected kickoff errs conservative (unlike
  tennis F-06). Each frozen row carries the constant model version, and a
  P(over) version only when one was served; `to_frozen_call` excludes other
  versions.
- **Snapshots:** keyed by week name and season, so no wrong-week serving.
  Every slate-input writer (`nfl-ingest`, `nfl-prop-lines`, `nfl-prop-odds`,
  `nfl-weather`) ends with a `!cancelled()` snapshot step. `nfl-scores` does
  not, but `nfl-weather` an hour later picks up its statuses. Rollover
  staleness is F-14.

**Read-only database counts** (2026 season, `SET TRANSACTION READ ONLY`, no
outcomes read):

- 0 of about 96,000 modelled PrizePicks snapshots fetched at or after kickoff.
- Game odds after kickoff: 0 US, 0 Odds-API.io, 24 Pinnacle (F-11); 0 of
  24,062 anytime-TD prices.
- 65,765 frozen rows, all `opponent-dvp-tg-blend-usage-snap-v4` (15,194 with
  `nfl-pover-v1`), weeks 3 to 6, none generated at or after kickoff.
- No completed game without stat or snap rows.
- `report_snapshots` holds 2024, 2025 and 2026 weeks 1-18 (built
  2026-10-16); 2026 weeks 5 and 6 were refreshed 2026-10-18 15:51 UTC.

**Existing grading read** (public GETs under
`https://sportapp-api-ftsf.onrender.com/nfl/model/`, about 15:55 UTC):

- **27j ranking** (graded live, 15:54 UTC): finished weeks 1-5; 30,309 frozen
  rows, 17,367 calls, 6,707 with P(over), 766 picks, 632 bets. Excluded:
  11,689 non-full-game, 744 week not finished, 462 void DNP, 47 pushes. All
  slices `insufficient` over 3 weeks: standard over 52/94 (55.3%), standard
  under 166/316 (52.5% +/- 2.8), goblin over 9/9, demon over 88/213 (41.3%
  against a 41.3% break-even). Weeks 3-5 are 94% to 100% frozen.
- **27a line grading** (snapshot of 2026-10-16 20:42 UTC): 2,956 calls at
  51.3% +/- 0.9 against 57.7%; edge < 5% 47.4%, 5-15% 48.1%, >= 15% 53.6%.
  The P(over) forward read is in F-12.
- **28 CLV:** spread 38 picks, +0.21 +/- 0.14; total 35 picks, -0.11 +/-
  0.20; both accruing toward 150.
- **27g fit:** served (`projectionVersion` matches); receiving and rushing
  yards shown, six markets hidden.

These are descriptive reads. No rule, threshold or verdict was changed, and
no verdict sample was re-read to decide anything.

**Verification:**

- API: `.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider` over 77
  files (`test_nfl*`, `test_prop_ranking*`, `test_prop_predictions`,
  `test_sport_props*`, `test_track_record*`, `test_no_nfl_view_names`,
  `test_sport_game_odds_provider`, `test_prizepicks_nfl`,
  `test_api_sports_nfl`): **1,090 passed**, one dependency deprecation
  warning, none skipped. All synthetic; no test connects to a database.
- Web: `npm.cmd run test -- src/utils/nfl`: **22 files, 248 passed**. No
  `.skip` or `.only` in the NFL test files.
- Synthetic in-memory reproduction for F-10 using the existing grading
  functions; no new test file. The scripts and read-only queries live in the
  session scratchpad only.
- **Guards with no regression test:** started-event skipping in `nfl_odds`
  (F-11); a pre-kickoff cutoff on the slate's line and moneyline queries
  (F-11, F-13); the stats-loaded half of the finished-week rule (F-10, whose
  current test pins the incomplete SQL); the frozen loader's market filter
  (F-15); and the web constants that mirror the API (`MIN_BASELINE_GAMES = 4`,
  `stale_baseline_season`, `isRateable` against `edge_is_comparable`), which
  match today but are not cross-checked.

**Excluded:** the 2025 prop holdout and the 2022-2025 game-line holdout (no
backtest CLI, fit or `--write` ran, and the stored 2025 slate snapshots were
not read); paid provider calls; ingest; database writes; browser QA; a full
Verify run; the security and performance lenses; NBA and tennis code, except
NBA as the comparison for F-10 and F-13.

**Smallest next improvement:** F-10, before 2026-10-20 13:00 UTC. Add the
per-game stats-loaded condition to NFL `get_finished_weeks` (NBA's query is
the template) and replace the pinned-SQL test. It enforces the rule as
pre-registered, so it needs tests only, and it must land before week 6 fixes
the standard-under and demon-over samples. Then F-11's ingest guard and
reader cutoffs as one data-guard fix, with a before/after slate comparison.
F-12 stays a reporting question: no refit, gate or rule change without a new
version and forward validation.

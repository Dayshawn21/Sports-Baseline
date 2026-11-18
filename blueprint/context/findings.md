# Findings

> **Generated file.** The findings ledger: review findings raised by `/audit`
> against the work in progress, each with a durable ID, severity (P0-P3), and
> status. `/implement` marks repaired findings `fixed`, a later `/audit` pass
> moves them to `closed`, and `/complete` refuses to merge while any P0 or P1
> finding is `open` or `fixed`, then archives resolved findings with the work
> and resets this file.

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
**Resolution:** `load_projection_inputs` now raises `ValueError` when the games span more than one date and reads the history with the real date (no type ignore); its docstring records why history is read before the context. Two tests cover the guard and the degraded context read. Closed 2026-11-04 by /audit (scope: current; lens: all): re-read the repaired `load_projection_inputs`; the guard fires before any read, the date is a real `dt.date`, and the repair introduced no new defect.

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

## Full audit evidence, 2026-11-06

**Scope:** full, all four lenses, on `claude/audit-d40214` at `eaa95078` (equal to `master`; no active feature, clean tree). **Coverage was partial**, not a complete full-project audit: four parallel reviewers covered API security, API performance and quality, the web app, and ingest plus the API tests, reading hot paths in full and the rest by grep and AST scan. Not read in depth: NBA and NHL board builders and track records (beyond prizepicks-rerun-snapshots/F-14's repair), the `nflverse*`, `hoopr_nba`, `nhl_api`, `tennismylife`, `tennis_elo*` bodies, `app/ml`, `backtest`, `evals`, most NBA, NFL and NHL web components, Ask core helpers past their entry points, git history for secrets, and dependency CVEs. Excluded: `blueprint/`, `analysis/`, `.claude/`, `.agents/`, `.impeccable/`, `api/models/`, `node_modules`, build output.
**Signals:** web verify (typecheck, 81 test files / 1,235 tests, build) passed. API `pytest` passed, 5,799 tests, run with a dummy `DATABASE_URL` because this worktree has no `api/app/.env` (the first run failed at collection on the missing setting, an environment gap, not a code defect). No lint command exists. No skipped, focused or xfail tests found on either side.
**Clean:** no SQL injection (every `text(f"...")` interpolates module constants; values are bound), admin key compared with `hmac.compare_digest`, production settings refuse weak keys and wildcard CORS, workflows use `contents: read` and no `pull_request_target`, no tracked secret, Ask output renders only allowlisted internal links, no `any` or `@ts-ignore` in the web, `app/core` has no I/O, dry runs guard their writes.
**Ledger:** added prizepicks-rerun-snapshots/F-19 to F-33; closed prizepicks-rerun-snapshots/F-14, prizepicks-rerun-snapshots/F-17 and prizepicks-rerun-snapshots/F-18.

### F-42 [P3] open - Windows checkouts made before the eol=lf rule keep CRLF registry CSVs until they are checked out again

**File:** .gitattributes:9; api/tests/test_tennis_elo_identities.py:177
**Found:** 2026-11-06 by /audit (scope: current; lenses: all)
**Why it matters:**
- Git only applies a new `eol` attribute when it writes the file. In an existing Windows checkout (the main `C:\dev\SportAppV2` and the sibling worktrees), a merge rewrites `tennis_elo_identities.csv` but leaves an unchanged `tennis_elo_local_overrides.csv` as CRLF.
- There, the new LF test and the committed-pin test fail, and any pins derived on that checkout would be wrong again. CI on Linux is unaffected.
**Suggested fix:** after merging, delete both registry CSVs in each existing checkout and run `git checkout --` on them. The data README already says to re-check them out before deriving pins.
**Resolution:** Still open after a byte check on 2026-11-06.
- CRLF registry CSVs were found only in `.claude/worktrees/sports-drawer-pages-747c69` (re-checked out to LF; its 59 registry tests pass), `.claude/worktrees/55-home-page` and the leftover `fix-f26-ask-spend-cap-ae1ff5` worktree. The main checkout and the other worktrees were already LF.
- The last two are on commits without the `eol=lf` rule (`2ce4cf00`, `c0728da0`). Their `tennis_elo_identities.csv` differs from `master`, so a merge rewrites it as LF, but their `tennis_elo_local_overrides.csv` is byte-identical to `master` in git and still CRLF on disk (11 CR bytes each), so a merge leaves it CRLF: the exact case this finding describes.
- To close: after either checkout next merges `master`, delete its `tennis_elo_local_overrides.csv` and run `git checkout -- api/app/ingest/data/tennis_elo_local_overrides.csv`, or remove the leftover worktree. Not done here, since both checkouts belong to other work.

### F-43 [P2] fixed - Prop board caches key the default date and the same explicit date separately, so returning to today rebuilds the board

**File:** api/app/services/nba/prop_board_cache.py:41; api/app/services/nhl/prop_board_cache.py:38
**Found:** 2026-11-13 by /audit (scope: NBA and NHL prop pages; lens: performance)
**Why it matters:**
- `_BOARDS.get((requested, today), ...)` keys on the raw request, so `/nba/props` and `/nba/props?date=2026-11-13` are two builds of one body. Measured on production: default warm at 0.18 s while explicit today took 1.14 s (NBA) and 0.52 s (NHL) on first hit.
- The previous/next date links always carry an explicit date, so stepping away and back to today pays a cold build. The web query keys (`['nba', 'prop-board', null]` vs the date) also miss each other, so the client refetches too.
**Suggested fix:** resolve the requested date to the board date first (one `get_game_dates` read, or a short memo of it) and key the cache on the resolved date. Optionally seed the dated web query key from the default response.
**Resolution:** Fixed on `fix/prop-board-cache` (2026-11-13): both board caches key on the resolved date, and the default date is memoized per `today` for 5 minutes. Unit-tested; not yet re-reviewed or measured on production.

### F-44 [P2] fixed - Every prop board date is rebuilt on request each 5 minutes, and the first visitor pays 1-2 s

**File:** api/app/services/nba/prop_board_cache.py:19; api/app/services/nhl/prop_board_cache.py:18; api/app/services/serial_build_cache.py:46
**Found:** 2026-11-13 by /audit (scope: NBA and NHL prop pages; lens: performance)
**Why it matters:**
- `SerialBuildCache` drops an entry at its 5-minute TTL and rebuilds inside the request. Uncached dates on production: NBA 0.99 s and 1.95 s TTFB, NHL 1.03 s, against 0.15-0.3 s warm. The NBA build runs eight sequential reads (`prop_board.py:23-36`).
- Builds share one lock, so a cold NBA board also queues any other date's request behind it. This is the most likely source of the "a little slow" loads, since it hits whoever arrives first after each expiry.
**Suggested fix:** serve the stale body while one background rebuild runs (stale-while-revalidate) in `SerialBuildCache`, so only a process's very first request waits. A longer TTL is a cheaper partial fix, since lines ingest on a schedule rather than continuously.
**Resolution:** Fixed on `fix/prop-board-cache` (2026-11-13): `SerialBuildCache` gained an opt-in `max_stale_seconds`. Both board caches serve an expired body for up to 30 minutes while one background rebuild runs on its own session. A process's first build, and any after 30 idle minutes, still runs inline. Unit-tested; not yet re-reviewed or measured on production.

### F-45 [P2] open - The board request waits for the lazy page chunk before it starts

**File:** web/src/routes/sportPages.tsx:19; web/src/routes/sportPages.tsx:23; web/src/pages/NbaPropBoardPage.tsx:25
**Found:** 2026-11-13 by /audit (scope: NBA and NHL prop pages; lens: performance)
**Why it matters:**
- The query starts only when the lazily imported page mounts. On a direct load (desktop, headless Chromium) the NBA chunk set (54 files) finished at 230-400 ms but `/nba/props` started at 455-580 ms; NHL started at 420-580 ms. The API answers in about 100 ms, so the chunk wait is the larger share.
- Phones pay this on slower parse and network.
**Suggested fix:** start the board query beside the chunk import, for example a `prefetchQuery(nbaPropBoardQuery(date))` fired from the route or the nav link (NHL already exposes `nhlPropBoardQuery`; NBA needs the same `queryOptions` factory).
**Resolution:**

### F-46 [P2] open - The NBA board ships 3 MB of JSON and costs a 200-260 ms main-thread task to show one market

**File:** api/app/services/nba/prop_board.py:40; web/src/pages/NbaPropBoardPage.tsx:26
**Found:** 2026-11-13 by /audit (scope: NBA and NHL prop pages; lens: performance)
**Why it matters:**
- The 2026-11-13 body is 3.0 MB raw (124 KB gzipped) for 4,432 lines, though one market (about 95 rows) renders. Each line repeats its player's `injury` object (about 360 B, roughly 1.6 MB of the body) across every market.
- After the response lands, a 207-259 ms long task runs on a fast desktop: grouping and filtering every market, React render, about 75 ms of forced layout (first read is rc-select's `scrollWidth` in `BoardFilterBar`) and 30-45 ms of GC. A mid-range phone runs several times slower. The NHL board (190 KB raw) costs 60-80 ms and is fine.
**Suggested fix:** send injuries once per player (or per game, as `injuryReport` already is) and join them on the client, as `nhlJoinProjections` does for NHL projections. That roughly halves the body, parse and GC. Per-market fetching is the larger option if the task stays heavy on phones.
**Resolution:**

### F-47 [P3] open - The NBA slate digest waits for the board, then re-renders the page

**File:** web/src/pages/NbaPropBoardPage.tsx:37
**Found:** 2026-11-13 by /audit (scope: NBA and NHL prop pages; lens: performance)
**Why it matters:** `useNbaSlateGaps(board.data?.date ?? null)` only starts once the board has rendered (measured start at 907-943 ms, done about 65 ms later), and its arrival triggers a second 57-84 ms task that re-renders the whole page including the table. NHL's goalie slate query waits the same way but is needed for its filter.
**Suggested fix:** when the URL carries a date, start the gaps query with it at mount; memoize the market table so the digest update does not re-render it.
**Resolution:**

### F-48 [P3] unverified - The API re-gzips the 3 MB NBA board on every request

**File:** api/app/main.py:102; api/app/services/nba/prop_board_cache.py:27
**Found:** 2026-11-13 by /audit (scope: NBA and NHL prop pages; lens: performance)
**Why it matters:** the cache holds uncompressed bytes and `GZipMiddleware` compresses each response, on the 0.5-CPU Render plan. Warm TTFB was 0.15-0.37 s against about 0.13 s for the tiny ranking route, so some of that gap may be compression. Not profiled on the server.
**Suggested fix:** time a warm request with and without `Accept-Encoding: gzip` first. If compression is the gap, cache the gzipped body beside the raw one. F-46 shrinks this either way.
**Resolution:**

### F-49 [P2] closed - Tennis prop enrichment engine lives in a router, and an ingest imports it

**File:** api/app/routers/props.py:72-575; api/app/routers/props.py:552; api/app/ingest/prop_snapshots.py:25
**Found:** 2026-11-15 by /audit (scope: full; lens: quality)
**Why it matters:** about 500 lines of projection and enrichment logic (`_enrich` alone runs 233-481) sit in a router, against the thin-router rule. `prop_snapshots` imports `enrich_with` from `app.routers.props`, so an ingest depends on the HTTP layer, and 12 test files import router privates. The comment at :552 defers the move "to item 17", which is checked off, so the deferral is stale.
**Suggested fix:** move lines 72-575 verbatim into `services/tennis/prop_enrichment.py` (pure helpers such as `_deciding_set_probability` may go to `core/`), re-point the ingest and tests, and leave the four endpoints in the router. Ingest and page must keep sharing one function so the props-v3 snapshots stay identical to what the page serves.
**Resolution:** Fixed in PR #42 (`1de17587`, 2026-11-17): lines 72-575 moved verbatim into `services/tennis/prop_enrichment.py`; the router keeps its endpoints, and `prop_snapshots` and the tests import from the service, so ingest and page still share one function. Full API suite 6441 passed. Not yet re-reviewed. Re-reviewed 2026-11-18 by /audit (scope: fix commits; lens: quality): the router is endpoints only, the ingest imports the service, and the moved bodies are byte-identical apart from two renames, so props-v3 is unaffected. Closed.

### F-50 [P2] open - `repositories/nfl.py` is 2,832 lines with ten separable areas

**File:** api/app/repositories/nfl.py
**Found:** 2026-11-15 by /audit (scope: full; lens: quality)
**Why it matters:** the largest file in the project mixes writes, model inputs, baselines, slate lines, ranking and replay readers. `_slate_line_rows` (1893) is 144 lines. It also has two helpers doing the same job (`_optional_float` 1454, `_float_or_none` 1884) and about 51 bare `dict` returns.
**Suggested fix:** first move the shared fragments (`_player_teams_cte`, `MODELLED_MARKET_FILTER`, `NOT_OTHER_MODEL`, `_LATEST_LINES_CTE`, about 1266-1360) into a small shared module, then split by seam: context 42-240, writes 242-815, model inputs 816-1030, baselines 1146-1500, slate lines 1888-2242, line-only 2242-2360, ranking 2361-2650, replay 2653-2762, leaving games/week/profile in `nfl.py`. Keep public names re-exported so callers do not change in the same step.
**Resolution:**

### F-51 [P2] open - Frozen-ranking SQL is copied across five repositories

**File:** api/app/repositories/nba.py:649-737; api/app/repositories/nhl.py:629-794; api/app/repositories/nfl.py:2554-2650; api/app/repositories/nfl_targets_ranking.py:12-68; api/app/repositories/nfl_volume_ranking.py:34-91
**Found:** 2026-11-15 by /audit (scope: full; lens: quality)
**Why it matters:** `get_frozen_gradeable_lines`, `get_finished_weeks` and `get_frozen_coverage` are the same shape in each sport, and the targets and volume CTEs are textually the same apart from market, odds types, prediction identity and two columns. The copies have already drifted (F-52), and the market filter is written two different ways (preformatted string in NBA, expanding bindparam in NHL).
**Suggested fix:** after F-52 is decided, factor one SQL builder for the eligible/frozen/coverage CTEs that takes sport, market predicate, settle-table join and prediction-identity predicate as required arguments (no defaults for the sport or model filters).
**Resolution:**

### F-52 [P2] invalid - NFL finished-week and coverage rules differ from NBA and NHL

**File:** api/app/repositories/nfl.py:2612; api/app/repositories/nba.py:707; api/app/repositories/nhl.py:759
**Found:** 2026-11-15 by /audit (scope: full; lens: quality)
**Why it matters:** NFL `get_finished_weeks` requires `bool_and(g.status = 'completed')`, while NBA and NHL also accept postponed and canceled games, so a canceled NFL game would keep its week open and out of the ranking record. NFL's coverage `EXISTS` also matches `fl.market = latest.market` and NBA/NHL do not. Either difference may be deliberate.
**Suggested fix:** confirm which rule each sport should have. Fix or comment the one that is not deliberate before F-51 merges them.
**Resolution:** Invalid as a defect, both differences deliberate (user chose option A, 2026-11-18; `blueprint/history/fixes/nfl-finished-week-rule.md`). The only NFL `sport_games` writer, `upsert_game` (`nfl.py:425`), stores `completed` or `scheduled`, never `postponed` or `canceled`, so the stricter finished-week rule picks the same weeks NBA's would. The coverage `fl.market = latest.market` came with 39c (`4b79aa00`) so a Rec Targets freeze on the same provider prop never counts as v4 coverage; F-51 must keep it as an NFL predicate. Both now carry a why-comment; no SQL changed. Possible follow-up: teach the nflverse ingest postponed and canceled statuses, then relax the NFL rule to match.

### F-53 [P2] unverified - NBA and NHL `upsert_games` conflict rules differ

**File:** api/app/repositories/nba.py:89-99; api/app/repositories/nhl.py:82-94
**Found:** 2026-11-15 by /audit (scope: full; lens: quality)
**Why it matters:** NBA keeps a known start time (`COALESCE(EXCLUDED.start_utc, sport_games.start_utc)`) and never updates `season`. NHL overwrites `start_utc`, so a feed row with no time can null a known one, and does update `season`. `_chunks`, `_ids_by_source`, `upsert_team` and `get_player_candidates` are otherwise word-for-word copies with only the sport literal changed.
**Suggested fix:** decide the right conflict rule and comment any deliberate difference. Then move the shared helpers into a `repositories/sport_common.py` that takes `sport` as a required argument.
**Resolution:**

### F-54 [P2] open - The served NBA/NHL game-type filter is retyped as a literal in about 13 queries

**File:** api/app/repositories/nhl.py:200; api/app/repositories/nhl.py:491; api/app/repositories/nhl_context.py:43; api/app/repositories/nba.py:203; api/app/repositories/nba.py:264; api/app/repositories/nba_injuries.py:87; api/app/core/nhl_projection_backtest.py:33
**Found:** 2026-11-15 by /audit (scope: full; lens: quality)
**Why it matters:** NHL has `SERVED_GAME_TYPES = ("REG","PST")` in core, but only nhl.py:491 uses it. `IN ('REG', 'PST')` is retyped at nhl.py 200, 224, 240, 255, 298, 374, 475 and nhl_context.py 43, 157, 228. NBA's `_SERVED_GAME_TYPES` is private and restated at nba.py:203 and nba_injuries.py:87. This is a load-bearing invariant, and one missed edit would split the served set.
**Suggested fix:** expose one public SQL fragment per sport built from the core tuple, and use it at every site.
**Resolution:**

### F-55 [P2] open - The three Odds-API.io quota gates disagree when the balance is unknown

**File:** api/app/ingest/odds_api.py:88-106; api/app/ingest/nfl_odds_io.py:44-46; api/app/ingest/nhl_odds_io.py:101-110
**Found:** 2026-11-15 by /audit (scope: full; lens: quality)
**Why it matters:** the three scripts share one hourly request bucket. NFL and NHL refuse to request when `remaining is None` ("unknown balance stops the run: tennis shares the hour"), but tennis `_quota_too_low` returns False on None and keeps spending. NHL also discards header values outside 0-100. That makes three header parsers and three gates for one provider.
**Suggested fix:** decide the unknown-balance policy on purpose, then add one shared Odds-API.io helper (`remaining(headers)`, `can_request(remaining, floor)`) used by all three.
**Resolution:**

### F-56 [P2] open - The Odds API client lives inside the NFL script, and NBA and tennis import its privates

**File:** api/app/ingest/nba_odds.py:21; api/app/ingest/tennis_totals.py:22-24
**Found:** 2026-11-15 by /audit (scope: full; lens: quality)
**Why it matters:** `nba_odds` imports `BASE_URL, _bookmaker_sets, _free_remaining, _odds_params, _provider_key, _remaining_requests, credit_gate` from `nfl_odds`, and `tennis_totals` gets `credit_gate` through `nba_odds` plus `_insert_odds` and `_load_upcoming` from `odds_api`. Tennis depends on NBA, which depends on NFL, and underscore names act as the public API.
**Suggested fix:** move the shared helpers into `app/ingest/the_odds_api.py` (the pure credit gate may go to `core/`) and import from there.
**Resolution:**

### F-57 [P2] open - Ingest scripts run SQL inline instead of through repositories

**File:** api/app/ingest/odds_api.py:677-699; api/app/ingest/livetennis.py:690-715; api/app/ingest/livetennis.py:1012; api/app/ingest/player_stats.py:518-535; api/app/ingest/player_stats.py:742-764
**Found:** 2026-11-15 by /audit (scope: full; lens: quality)
**Why it matters:** these break "repositories own SQL". `player_stats.run` builds its player-selection query by string concatenation. `_insert_odds` is a pass-through over `repositories.matches.upsert_odds`. Backtests set read-only transactions inline (`nhl_over_probability_fit.py:247`, `nhl_projections.py:262`) while `tennis_elo` uses the repository helper.
**Suggested fix:** move the four queries into `repositories/matches.py` and `repositories/players.py`, drop `_insert_odds`, and use one shared read-only-transaction helper in every backtest.
**Resolution:**

### F-58 [P2] open - Four ingest scripts hand-roll 429 retry loops with different rules

**File:** api/app/ingest/livetennis.py:156-200; api/app/ingest/prizepicks.py:47-120; api/app/ingest/nhl_context.py:36-84; api/app/ingest/player_stats.py:164-185
**Found:** 2026-11-15 by /audit (scope: full; lens: quality)
**Why it matters:** the standard says to use tenacity for transient retry, and 6 ingest files do. These four each have their own attempt count, Retry-After parsing and backoff. Some carry provider rules (the livetennis daily quota, fatal 4xx), so they cannot be swapped blindly.
**Suggested fix:** add one tenacity-based retry helper beside `log_config.py` that honors Retry-After, and keep provider-specific stop conditions as `retry_if_*` predicates.
**Resolution:**

### F-59 [P2] closed - Web game-status labels are reimplemented five times, and the copies have drifted

**File:** web/src/utils/gameState.ts:16-26; web/src/utils/nhlGame.ts:36-46; web/src/utils/nbaSlate.ts:68-74; web/src/utils/nbaPropBoard.ts:35-41; web/src/utils/nhlPropBoard.ts:55-60
**Found:** 2026-11-15 by /audit (scope: full; lens: quality)
**Why it matters:** `gameState` lowercases the status, accepts `cancelled` and shows "Result pending" for a long-started game with no final. The board copies skip both, so an old game with no stored final reads "Tipped off" or "Started". The NHL final label is "Final / OT" in one file and "Final/OT" in another.
**Suggested fix:** have the slate and board helpers call `gameState()` (with an optional per-sport started label) and drop the local terminal maps.
**Resolution:** Fixed in `6d5b298b` (2026-11-16; pushed to master 2026-11-18): `gameState()` takes a per-sport started label, and the NHL and NBA slate cards and the NBA and NHL props boards route through it. Approved visible changes: `Final/OT` on NHL cards, `Result pending` on the boards, case-insensitive and `cancelled` statuses. Spec in `blueprint/history/fixes/web-game-status.md`. Not yet re-reviewed. Re-reviewed 2026-11-18 by /audit (scope: fix commits; lens: quality): all four listed copies route through `gameState()`, and the visible changes match the approved list. A separate NFL slate copy is logged as F-76. Closed.

### F-60 [P2] closed - Signed-number and percent formatting is reimplemented about 20 times with different zero handling

**File:** web/src/utils/nflSignal.ts:13-18; web/src/utils/gapUnits.ts:7; web/src/utils/nbaProps.ts:83-85; web/src/utils/propRowVisuals.ts:90-92; web/src/utils/nhlGame.ts:61-62; web/src/utils/calculators.ts:148-162; web/src/utils/odds.ts:16
**Found:** 2026-11-15 by /audit (scope: full; lens: quality)
**Why it matters:** some copies round before choosing the sign and some do not, so `edgeLabel(-0.04)` shows "-0.0" while others show "0.0". `(x * 100).toFixed(1)}%` appears 53 times beside `fmtPct`, and 9 components define a local `pct`. The null placeholder is an em dash character in `odds.ts` and "--" in NFL/NHL utils.
**Suggested fix:** add `fmtSigned(value, decimals, suffix?)` to `format.ts` (round, then sign, normalize -0), use it and `fmtPct` everywhere, and pick one placeholder constant. Changing visible output (placeholder, -0.0) is a UI decision, so make it explicitly.
**Resolution:** Fixed in `dd5c3d9c` (2026-11-16; pushed to master 2026-11-18): `fmtSigned` in `utils/format.ts` (round, then sign, normalise -0) replaces the signed-number copies, and the local `pct` helpers use `fmtPct`, which now takes a placeholder. Each page keeps its current missing-value text by decision. Spec in `blueprint/history/fixes/web-formatting.md`. Not yet re-reviewed. Re-reviewed 2026-11-18 by /audit (scope: fix commits; lens: quality): `fmtSigned` rounds before signing and normalises -0, no hand-signed copy remains, and the nine `pct` helpers use `fmtPct`. Whole-percent copies and pass-through wrappers are logged as F-77. Closed.

### F-61 [P2] closed - Moneyline pick generation is duplicated between best picks and the bankroll builder

**File:** api/app/services/tennis/best_picks.py:101-176; api/app/services/tennis/bankroll_builder.py:138-193; api/app/services/tennis/bankroll_builder.py:34
**Found:** 2026-11-15 by /audit (scope: full; lens: quality)
**Why it matters:** both compute EV, Kelly, the devig, the bettable assessment and the reasoning text. The edge formulas already differ (`/ market_prob` vs `/ max(mkt_p or our_p, 0.01)`). `bankroll_builder` imports privates `_compute_stat_avg` and `_CONF_MULT` from `best_picks`, and both read a declared field through `getattr(pred, "quality_flags", [])`.
**Suggested fix:** extract one pure `moneyline_sides(pred)` that both shape from, choose one edge formula on purpose (or document why they differ), import `compute_stat_avg` from core and make `_CONF_MULT` public.
**Resolution:** Fixed in PR #44 (`d00d2489`, 2026-11-17): one pure `moneyline_sides(pred)` in `services/tennis/moneyline.py` feeds both callers; each keeps its own edge formula and output, pinned by golden tests written on the old code. `compute_stat_avg` comes from core, `CONF_MULT` is public, and both read `pred.quality_flags or []`. Full API suite 6488 passed. Not yet re-reviewed. Re-reviewed 2026-11-18 by /audit (scope: fix commits; lens: quality): one `moneyline_sides` feeds both callers, both edge formulas are kept on purpose, and the golden tests pin the old outputs. Closed.

### F-62 [P2] open - Cross-sport shared code lives under `nfl_` names in core and web utils

**File:** api/app/core/nfl_over_probability_calibration.py; api/app/core/nfl_resolution.py; web/src/utils/nflPlayer.ts; web/src/utils/nbaGame.ts:5
**Found:** 2026-11-15 by /audit (scope: full; lens: quality)
**Why it matters:** NBA and NHL import calibration and player resolution from `nfl_*` core modules. On the web, `FROM_BOARD`, `arrivedFromBoard`, `playerSearch` and `propSectionIds` live in `nflPlayer.ts` and are used by 9 NBA, NHL and tennis files, and 10 NBA/NHL files import `nfl-*.css`. `nbaPlayerTabs`/`nhlPlayerTabs` are identical and return `string[]`, which forces `as` casts in `NhlPlayerPropTabs.tsx:12,15`.
**Suggested fix:** move the generic modules to neutral names (`core/calibration.py`, `core/player_resolution.py`, `~/utils/playerPage.ts`), keeping re-export shims at the old Python paths because generated and pre-registered files hard-code them. Make the tab helper generic to remove the casts.
**Resolution:** Partly fixed, still open. The web part landed in `86d381cd` (2026-11-16; pushed to master 2026-11-18): `FROM_BOARD`, `arrivedFromBoard`, `playerSearch` and `propSectionIds` moved to `utils/playerPage.ts` with generic `playerTabs` and `selectedMarket`, so no non-NFL file imports `utils/nflPlayer` and the NHL casts are gone. Remaining: the API `core/nfl_*` calibration and resolution modules and the `nfl-*.css` imports.

### F-63 [P2] open - Over-probability verdict, normal-Brier and cross-fit code is copied per sport

**File:** api/app/core/nfl_over_probability_calibration.py:99; api/app/core/nba_over_probability.py:82; api/app/core/nhl_over_probability.py:81; api/app/core/nfl_targets_over_probability.py:144; api/app/core/nba_over_probability_v2_crossfit.py:131-139; api/app/core/nhl_over_probability_crossfit.py:163-207
**Found:** 2026-11-15 by /audit (scope: full; lens: quality)
**Why it matters:** there are four near-identical display-verdict functions, and the normal-Brier sum is repeated in 7 places. NHL `evaluate` guards empty input. NBA `evaluate` divides by `len(lines)` unguarded (its current caller probably never passes an empty list).
**Suggested fix:** add one `display_verdict(...)` and one `normal_brier(lines)` to the shared calibration module. Each sport passes its own pre-registered constants so no result changes. Add the empty guard to NBA.
**Resolution:**

### F-64 [P2] open - Odds-feed game matchers and number parsers are copied with different hardening

**File:** api/app/core/nba_odds.py:43; api/app/core/nhl_odds.py:62-89; api/app/core/nfl_odds.py:35-55; api/app/core/nfl_odds_io.py:21
**Found:** 2026-11-15 by /audit (scope: full; lens: quality)
**Why it matters:** all three matchers use the same unique-candidate loop, but only NHL rejects home == away, non-int game ids and naive datetimes. NBA and NFL call `int(str(game["game_id"]))` unchecked. NHL's `_number` rejects `bool` and the NFL copies accept `True` as 1.0.
**Suggested fix:** add a shared `finite_number` (NHL semantics) and `unique_game_match(home, away, games, within)`. Per-sport code then supplies only team mapping and the time window.
**Resolution:**

### F-65 [P2] open - The pre-0007 split-column fallback is repeated across `players.py`

**File:** api/app/repositories/players.py:123; api/app/repositories/players.py:328-710
**Found:** 2026-11-15 by /audit (scope: full; lens: quality)
**Why it matters:** every rolling-stats reader and the upsert catch `ProgrammingError` and rerun a legacy query for databases without migration 0007 (migrations are at 0054). The 26-column list is written out 10 times. The upsert fallback calls `db.rollback()`, which would discard earlier writes in the caller's transaction if it were ever reached.
**Suggested fix:** drop the fallback branches and `tests/test_players_repository_split_columns.py`, and share one `_ROLLING_COLUMNS` constant.
**Resolution:**

### F-66 [P2] closed - Admin flagged-player logic sits in the router, and the admin page renders its panels twice

**File:** api/app/routers/admin.py:48-139; web/src/pages/AdminPage.tsx:310-410; web/src/pages/AdminPage.tsx:544-780
**Found:** 2026-11-15 by /audit (scope: full; lens: quality)
**Why it matters:** about 90 lines of the router run predictions, join ELO and stats and refine flags, using function-local imports and the private `app.ingest.player_stats._slug`. On the web, the Fix Stats, Fetch ELO and Set ELO panels are written once for mobile and once for desktop, including the same `SetEloRequest` payload build (:397-405 and :761-769).
**Suggested fix:** move the flag logic into `services/tennis/flagged_players.py` and make `_slug` public. Extract the three panels and a tested `buildSetEloPayload` in `~/utils/adminFlags` so both layouts share them.
**Resolution:** Fixed: the web part landed in `cefc83cb` (pushed 2026-11-18); the API part in PR #43 (`ad464fc0`, 2026-11-17) moved the flag logic into `services/tennis/flagged_players.py` and the slug into a public `core/ta_slug.py`, pinned by a golden test of the old response. Full API suite 6460 passed. Not yet re-reviewed. Re-reviewed 2026-11-18 by /audit (scope: fix commits; lens: quality): the defect is gone in both apps (one service call in the router, each repair panel rendered once, payload builders tested). Kept `fixed`: the repair left two comments naming the old `_slug` (`api/app/routers/admin.py:87`, `api/app/schemas/admin.py:26`); rename them to `ta_slug` and drop the em dashes in `core/ta_slug.py:8`, then close. Repaired on `fix/ta-slug-comments` (2026-11-18): the two comments now name `ta_slug` (`api/app/routers/admin.py:87`, `api/app/schemas/admin.py:26`) and match the code (`flagged_players.py:123`, `player_stats.py:199`), and the em dashes and arrows in `core/ta_slug.py` and `ingest/player_stats.py:650` are gone. Re-reviewed 2026-11-18 by /audit (scope: fix diff; lens: quality): no `_slug(` reference is left in `api/app`, and the diff is comments only. API suite 6553 passed. Closed.

### F-67 [P2] closed - The NHL board-to-player link drops the return path that NBA and NFL have

**File:** web/src/components/nhl/NhlPropBoardMarket.tsx:39; web/src/pages/NhlPlayerPage.tsx:33-37
**Found:** 2026-11-15 by /audit (scope: full; lens: quality)
**Why it matters:** NBA and NFL pass `FROM_BOARD` state and their player crumb goes back to the board. `arrivedFromBoard` appears only in the NBA and NFL pages, so an NHL user opening a player from the board loses the board's filters on the way back. This is a consistency gap from copying per sport.
**Suggested fix:** pass `state={FROM_BOARD}` on the NHL board link and add the same crumb branch to `NhlPlayerPage`.
**Resolution:** Fixed in `86d381cd` (2026-11-16; pushed to master 2026-11-18): the NHL board link passes `FROM_BOARD`, and `NhlPlayerPage` shows the NBA-style `<- NHL props` crumb back to the board (approved visible change). Spec in `blueprint/history/fixes/web-player-pages.md`. Not yet re-reviewed. Re-reviewed 2026-11-18 by /audit (scope: fix commits; lens: quality): the NHL board link passes `FROM_BOARD` and the crumb returns to the board; the game-page link is unchanged. The now-duplicated crumb is logged as F-79. Closed.

### F-68 [P2] closed - Per-sport hook files follow two different patterns

**File:** web/src/hooks/useNhl.ts; web/src/hooks/useNba.ts:37-77; web/src/hooks/useNfl.ts:8-72; web/src/hooks/useModelTrackRecord.ts:6; web/src/hooks/useNflModelTrackRecord.ts:7
**Found:** 2026-11-15 by /audit (scope: full; lens: quality)
**Why it matters:** NHL uses `queryOptions` with `skipToken` and normalizes the slate date. NBA and NFL use `enabled` with 10 `gameId as number` casts, and the NBA slate key uses the raw date, so one slate can get two cache entries. `useNbaModelRanking` and `useNhlModelRanking` are identical, and the track-record stale time is declared twice.
**Suggested fix:** move NBA and NFL to the NHL pattern, add a shared model-ranking hook helper and export the stale constants from one place.
**Resolution:** Fixed in `030ef1b8` (2026-11-16; pushed to master 2026-11-18): NBA and NFL hooks use the NHL `queryOptions` and `skipToken` pattern with no `gameId` casts, the NBA slate key normalises its date, the model-ranking hooks share one helper, and the stale times are exported once. Spec in `blueprint/history/fixes/web-hooks.md`. Not yet re-reviewed. Re-reviewed 2026-11-18 by /audit (scope: fix commits; lens: quality): `useNba.ts` and `useNfl.ts` have no casts or `enabled` options, the NBA slate key is normalised, ranking hooks share one query and stale times live in `queryTimes.ts`. The three track-record hooks still on the old pattern are logged as F-78. Closed.

### F-69 [P2] closed - Near-copy sport components and board utils

**File:** web/src/components/nhl/NhlGameProps.tsx:15-58; web/src/components/nhl/NhlPropBoardMarket.tsx:13-53; web/src/components/nhl/NhlPlayerProjectionHistory.tsx; web/src/components/tennis/player/PlayerProjectionHistory.tsx; web/src/utils/nbaPropBoard.ts:22-80; web/src/utils/nhlPropBoard.ts:20-53
**Found:** 2026-11-15 by /audit (scope: full; lens: quality)
**Why it matters:** the NHL game and board prop tables repeat columns, caption and an `alternates()` helper, but differ in how they show alternates and in the ring and "Updated" columns. The NHL and tennis projection-history sections are the same structure with local `shortDate` and footnote copies. The NBA and NHL board utils share start-time sort, comparator and path builders but differ on the default market (NBA falls back to points even when empty).
**Suggested fix:** move `alternates` and the caption into `~/utils/nhlProjection` and share one table with optional columns. Add one `ProjectionHistorySection` with a sport adapter. Put the board sort, comparator and path in a shared util and choose one default-market rule on purpose.
**Resolution:** Fixed in `9e248092` (2026-11-16; pushed to master 2026-11-18): `nhlAlternateLabels` and `nhlProbabilityCaption` serve both NHL tables, `ProjectionHistorySection` with `historyFootnote` serves NHL and tennis, and `utils/propBoardRows.ts` holds the shared board sort and path. Each sport keeps its default-market rule by decision. Spec in `blueprint/history/fixes/web-shared-props.md`. Not yet re-reviewed. Re-reviewed 2026-11-18 by /audit (scope: fix commits; lens: quality): no `alternates()` copy is left, both history sections are adapters over `ProjectionHistorySection`, and the board sort and path live in `propBoardRows.ts`. Closed.

### F-70 [P2] closed - `ParlaysPage` is an 802-line legacy page outside the shared page patterns

**File:** web/src/pages/ParlaysPage.tsx:37-640; web/src/pages/ParlaysPage.tsx:655-690
**Found:** 2026-11-15 by /audit (scope: full; lens: quality)
**Why it matters:** seven subcomponents are defined in the page, it builds its own `<h1>` with an eyebrow instead of `PageHead`, it uses `onMouseEnter`/`onMouseLeave` style mutation for hover, and it has banner-divider comments. `SinglePickRow` (:80) and `SinglePickCard` (:377) show the same data in two layouts.
**Suggested fix:** switch to `PageHead`, move the subcomponents into `components/tennis/parlays/`, and replace hover handlers with CSS classes.
**Resolution:** Fixed in `31d92b68` (2026-11-16; pushed to master 2026-11-18): the page uses `PageHead`, its subcomponents moved under `components/tennis/parlays/`, and hover handlers became CSS classes. Spec in `blueprint/history/fixes/web-parlays-page.md`. Not yet re-reviewed. Re-reviewed 2026-11-18 by /audit (scope: fix commits; lens: quality): reopened. `PageHead`, the moved subcomponents and the CSS hover landed, but banner comments remain at `web/src/pages/ParlaysPage.tsx:87,97,108` with narration comments at `:37,81,119`, an empty fragment at `:38-79` and an IIFE in the JSX at `:88-132`. The moved `SinglePickRow.tsx:25-50` and `SinglePickCard.tsx:17-60` carry what-comments. Delete the comments and fragment and compute the four lists before `return`. Repaired on `fix/parlays-page-cleanup` (2026-11-18): a tested `splitByTour` in `utils/bankrollTours.ts` replaces the JSX IIFE, and the empty fragment and every what-comment in the page and the five parlay components are gone. Re-reviewed 2026-11-18 by /audit (scope: fix diff; lens: quality): section filtering is unchanged, and `SinglePickRow` and `SinglePickCard` are the wide and narrow layouts `TourSection` chooses between, not a duplicate. Verify passed and the page renders as before. Closed.

### F-71 [P3] open - Dead code across both apps

**File:** api/app/ingest/api_sports_nfl.py:37-53; api/app/config.py:24; api/app/repositories/players.py:436-493; api/app/scripts/seed_elo.py; api/app/ingest/elo.py:289; api/app/routers/tennis.py:494-502; web/src/utils/nflLabels.ts:27-81
**Found:** 2026-11-15 by /audit (scope: full; lens: quality)
**Why it matters:** `api_sports_nfl.py` has no importer, workflow or doc entry, and its `completed_game_players(self, ...)` sits after a `return` inside a module function, so it can never run. `get_rolling_stats_batch` has no callers. `seed_elo.py` reads the old pre-V2 repo and is the only caller of `ingest_from_csv`. `/tennis/parlays/suggested` has no web caller. On the web, `segmentRank` and `SEGMENT_COLORS` are unused, and about 12 exports are used only by their own tests (`kickoffLabel`, `formatTime`, `summarizePricedEdges`, `summarizeBaselineMix`, `describeBaselineMix`, `spreadMoveLabel`, `totalMoveLabel`, `playerInitials`, `groupNflSlateLinesByPosition`, `filterNflSlateLinesByPeriod`, `DEFAULT_BOARD_VIEW`, `matchProps`).
**Suggested fix:** delete each with its tests and the `api_sports_nfl_key` setting. Confirm no external consumer of the parlays endpoint first. Leave `backtest/nfl_anytime_td.py` (the record of the 19j/19m/19n evaluations) and `core/nba_over_probability_v2_fit.py` (the frozen 44a fit) in place.
**Resolution:** Partly fixed, still open. PR #46 (`08bf91e8`, 2026-11-18) removed `/tennis/parlays/suggested` after the user confirmed no external consumer; a test pins the 404. The web part landed in `3f152da5` (2026-11-16; pushed to master 2026-11-18): the unused exports listed above are deleted with their tests. Remaining: `api_sports_nfl.py` and `api_sports_nfl_key`, `get_rolling_stats_batch`, `seed_elo.py` and `ingest_from_csv`.

### F-72 [P3] open - Small helpers duplicated across files

**File:** api/app/schemas/*.py (`_CamelModel` x7); api/app/core/prop_ev.py:75; api/app/core/odds.py:85-92; api/app/services/tennis/best_picks.py:60-82; api/app/core/nba_names.py:23; api/app/core/nhl_names.py:14; web/src/pages/ParlaysPage.tsx:15; web/src/pages/AdminPage.tsx:23; web/src/utils/tennisMatch.ts:96-110; web/src/utils/tennisPlayer.ts:110-122
**Found:** 2026-11-15 by /audit (scope: full; lens: quality)
**Why it matters:** `_CamelModel` is defined in 7 schema modules. `american_to_decimal` exists in `prop_ev` and `odds`, `decimal_to_american` in 3 places with different invalid-input behavior, `_normal_cdf` and `_f` 3 times each, `fold_name` twice. `TOUR_COLORS` exists twice and only the Parlays copy has Challenger. The tennis date formatters exist twice and only one slices ISO timestamps. `CENTRAL = 'America/Chicago'` is declared 5 times. `tennisPropBoard.ts:226-232` restates the odds math in `oddsMath.ts`.
**Suggested fix:** one shared definition each (`schemas/base.py`, `core/odds.py`, `format.ts`, `oddsMath.ts`, a `tourColor` util), imported at every site.
**Resolution:** Partly fixed, still open. PR #45 (`79b68881`, 2026-11-17) made `core/prop_probs.normal_cdf` and `core/prop_projection.opt_float` public and removed the `_normal_cdf` and `_f` copies in `best_picks` and `prop_enrichment`. The web part landed in `dd5c3d9c` (2026-11-16; pushed to master 2026-11-18): one `CENTRAL` constant and day key, one tennis date formatter, `tennisPropBoard.ts` on `oddsMath.ts`, and one tour-colour helper for Parlays and Admin. Remaining (API only): `_CamelModel`, the odds converters, `fold_name` and `ingest/elo._f`.

### F-73 [P3] open - Oversized functions in services, core and ingest

**File:** api/app/core/prop_projection.py:255-366; api/app/services/tennis/best_picks.py:179-354; api/app/services/tennis/best_picks.py:404-604; api/app/services/tennis/bankroll_builder.py:204-465; api/app/ingest/livetennis.py:922; api/app/ingest/player_stats.py:716; api/app/ingest/odds_api.py:710
**Found:** 2026-11-15 by /audit (scope: full; lens: quality)
**Why it matters:** these run 107-200 lines against the roughly 50-line guideline. `compute_stat_avg` repeats the ace and double-fault formulas inside its fantasy branch. `odds_api.run` loads, pairs, fetches, parses and writes in one body.
**Suggested fix:** split into named stages or per-market functions. In `compute_stat_avg`, keep the inline unclamped sets formula: switching to the clamped `expected_sets_from_win_prob` would change props-v3/v4 output and needs a versioned change, not a refactor.
**Resolution:** Partly fixed, still open. PR #45 (`79b68881`, 2026-11-17) split `generate_market_odds_picks`, `generate_derived_picks`, `_generate_set_picks` and `_generate_total_picks` into named helpers (37-44 lines each), pinned by 53 golden cases written on the unsplit code. Remaining: `compute_stat_avg` (keep its unclamped sets formula), and `livetennis`, `player_stats` and `odds_api.run` in ingest.

### F-74 [P3] open - Flat `core/` (148 modules) and `utils/` (115 modules) directories

**File:** api/app/core/; web/src/utils/
**Found:** 2026-11-15 by /audit (scope: full; lens: quality)
**Why it matters:** filename prefixes already form groups (core: nfl 51, tennis 21, nba 20, nhl 17, prop 9, ask 7; utils: nfl 35, tennis 12, nba 9, nhl 9, slate 8, ask 6). Navigation and ownership are harder than they need to be.
**Suggested fix:** do this last, after F-62, as a mechanical move per sport (`core/nfl/`, `utils/nfl/`, and a `shared/`). Keep Python re-export shims for paths hard-coded in generated or pre-registered files. Approve it separately because it touches most imports.
**Resolution:**

### F-75 [P3] open - Layering leaks and stale docs

**File:** api/app/repositories/nfl.py (ingest dataclass imports); api/app/repositories/matches.py:484-733; api/app/db/pool.py; api/app/security.py:3-6; api/app/ingest/prizepicks_nfl.py:3; api/app/ingest/prizepicks_props.py:17-22; docs/commands.md
**Found:** 2026-11-15 by /audit (scope: full; lens: quality)
**Why it matters:** repositories import ingest dataclasses, which forces lazy imports in `hoopr_nba`, `nflverse` and `nhl_api` to avoid cycles. `matches.py` runs the win/loss streak loop in Python twice. `get_db` is typed `-> AsyncSession` but is a generator. The shared PrizePicks pipeline imports private functions from the tennis module, and the three team CLIs are copies. `security.py` says the app runs on localhost. The `prizepicks_nfl` docstring names API-Sports as the source. `nfl_weather`, `nfl_team_elo`, `nba_prop_predictions`, `nfl_odds_io` and `nfl_prop_odds` are scheduled but missing from `docs/commands.md`.
**Suggested fix:** move transfer types into core, the streak loop into core, and the PrizePicks HTTP/parse layer into a neutral `prizepicks_client.py`. Fix the `get_db` type and the stale docstrings, and add the missing commands.
**Resolution:**

### F-76 [P3] closed - The NFL slate keeps its own case-sensitive game-status rule

**File:** web/src/utils/nflSlate.ts:264-268; web/src/pages/NflIntelligencePage.tsx:33
**Found:** 2026-11-18 by /audit (scope: fix commits; lens: quality)
**Why it matters:** `rowState` checks `game.status === 'completed'` and has no postponed or canceled branch, so a postponed NFL game reads as live or pending while the other sports read it through `gameState()`. Smaller case-sensitive `=== 'completed'` counts remain in `homeSources.ts:152,197`, `nbaSlate.ts:186`, `nflSlate.ts:110` and `nhlSlate.ts:104`.
**Suggested fix:** Map `gameState()` phases in `rowState`, handling the `off` phase, and use the same lowercase check in the counts.
**Resolution:** Repaired on `claude/fix-nfl-slate-status-a58bad` (2026-11-18): `rowState` returns the `gameState()` phase with NFL's labels (`Live`, `Result pending`, `Final`), so a postponed or canceled game reads as `off` with its label, no market lines and no pre-game tags, and the page's `STATE_LABEL` map gives way to the row's `stateLabel`. The finals counts in the NFL, NBA and NHL slate summaries and the home page's schedule and moneyline filters use the new `isFinalStatus`. Visible change, listed in the spec for the user's approval at merge: postponed and canceled NFL games show as such, and a final stored in another case counts as one. Spec in `blueprint/history/fixes/nfl-slate-status.md`. Re-reviewed 2026-11-18 by an independent review of the diff: no case-sensitive status check remains, and upcoming, live, pending and final rows are unchanged. Web Verify passed (1859 tests) and the API tests passed (6553). Closed.

### F-77 [P3] closed - Whole-percent and pass-through percent formatters beside `fmtPct`

**File:** web/src/utils/nbaProps.ts:74; web/src/utils/nflSignal.ts:44; web/src/utils/nflVolume.ts:21; web/src/utils/boardRecord.ts:105; web/src/components/tennis/TennisSlateTable.tsx:72; web/src/utils/homeSources.ts:188
**Found:** 2026-11-18 by /audit (scope: fix commits; lens: quality)
**Why it matters:** About 13 sites hand-roll `${Math.round(x * 100)}%` (three as local `percent()` helpers) instead of `fmtPct(x, 0)`. `boardRecord.ts` `percent` and `TennisSlateTable.tsx` `pct` only forward to `fmtPct`. `homeSources.ts:188` hard-codes a `+` on the gap.
**Suggested fix:** Use `fmtPct(x, 0)` and `fmtSigned(diff * 100, 1, ' pp')` directly and delete the wrappers. Output is unchanged for probabilities.
**Resolution:** Repaired on `claude/fix-percent-formatters-93ec2a` (2026-11-18): every whole-percent copy and the three `percent()` helpers use `fmtPct(x, 0)`, the `boardRecord.ts` and `TennisSlateTable.tsx` wrappers are gone, and the moneyline gap uses `fmtSigned(diff * 100, 1, ' pp')`. Output is unchanged for every value these sites receive (all non-negative, each guards null), except a gap that rounds to zero now shows `0.0 pp` by the F-60 zero rule. Left alone on purpose: `nbaSlate.ts` `winBar`, `nhlProjection.ts` `nhlPercentLabel`, the `trackRecord.ts` range and three `points`/`pts` labels. Spec in `blueprint/history/fixes/percent-formatters.md`. Verify passed. Re-reviewed 2026-11-18 by an independent subagent (scope: fix diff; lens: quality): same text at every site, no copy or wrapper left, nothing new. Closed.

### F-78 [P3] closed - NFL model track-record hooks still use `enabled` with `season as number`

**File:** web/src/hooks/useNflModelTrackRecord.ts:8-31
**Found:** 2026-11-18 by /audit (scope: fix commits; lens: quality)
**Why it matters:** Three hooks keep the `enabled: season !== null` plus `season as number` pattern that F-68 removed from the other NBA and NFL hooks. `useNba.ts:9` and `useNhl.ts:69` also gate a disabled slate two different ways.
**Suggested fix:** Move the three hooks to `queryOptions` with `skipToken`, as in `useNfl.ts`, and pick one disabled-slate idiom.
**Resolution:** Repaired on `fix/nfl-track-record-hooks` (2026-11-18): the three hooks build `queryOptions` with `skipToken` for a null season, and `nhlSlateQuery(date, enabled)` gates a waiting slate through `skipToken` as `nbaSlateQuery` does, so `useNhlSlate` no longer spreads `enabled`. Tests cover the idle null season, the unchanged cache keys and the gated NHL slate. Re-reviewed 2026-11-18 by /audit (scope: fix diff; lens: quality): keys, stale times, retry and fetch arguments are unchanged, and no caller refetches a gated slate. Verify passed, and in the app the NFL model page fires each track-record request once and the NHL game page waits for its date before loading the slate. Closed.

### F-79 [P3] closed - The NBA and NHL board crumbs are near-identical copies

**File:** web/src/pages/NbaPlayerPage.tsx:33-42; web/src/pages/NhlPlayerPage.tsx:34-42
**Found:** 2026-11-18 by /audit (scope: fix commits; lens: quality)
**Why it matters:** F-67 copied the NBA crumb into the NHL page, so the per-sport copying the finding named now covers the crumb. Both call `useLocation()` inside an `if` condition, which reads like a conditional hook.
**Suggested fix:** A shared `BoardCrumb({ boardPath, label })` in `components/shared`, with `useLocation()` hoisted to a `const` as `NflPlayerPage.tsx:66` does.
**Resolution:** Fixed on `claude/fix-board-crumb-f57805` (2026-11-18): a shared `BoardCrumb({ boardPath, label, fallback })` in `components/shared` calls `useLocation()` once at the top, and the NBA, NHL and NFL player pages use it, each passing its own game or slate fallback. No visible change. Spec in `blueprint/history/fixes/web-board-crumb.md`. Re-reviewed 2026-11-18 by an independent reviewer (scope: fix diff; lens: quality): the board branch lives only in `BoardCrumb`, no page calls `useLocation()`, and hrefs, labels, back navigation and fallbacks match the previous code on all three pages. Verify passed. Closed.

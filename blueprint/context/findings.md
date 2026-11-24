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

### F-54 [P2] open - The served NBA/NHL game-type filter is retyped as a literal in about 13 queries

**File:** api/app/repositories/nhl.py:200; api/app/repositories/nhl.py:491; api/app/repositories/nhl_context.py:43; api/app/repositories/nba.py:203; api/app/repositories/nba.py:264; api/app/repositories/nba_injuries.py:87; api/app/core/nhl_projection_backtest.py:33
**Found:** 2026-11-15 by /audit (scope: full; lens: quality)
**Why it matters:** NHL has `SERVED_GAME_TYPES = ("REG","PST")` in core, but only nhl.py:491 uses it. `IN ('REG', 'PST')` is retyped at nhl.py 200, 224, 240, 255, 298, 374, 475 and nhl_context.py 43, 157, 228. NBA's `_SERVED_GAME_TYPES` is private and restated at nba.py:203 and nba_injuries.py:87. This is a load-bearing invariant, and one missed edit would split the served set.
**Suggested fix:** expose one public SQL fragment per sport built from the core tuple, and use it at every site.
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

### F-76 [P3] open - The documented NBA board contract still says each line carries `recent` and `injury`

**File:** api/app/routers/nba.py:45; blueprint/context/project-overview.md:328-340
**Found:** 2026-11-24 by /audit (scope: current; lens: quality)
**Why it matters:** `/nba/props` returns `board_json`'s bytes, which omit each line's `recent` and `injury` and add `playerRecent` (F-46), but the route still declares `response_model=NbaPropBoardResponse`, so OpenAPI (`/docs`) lists both fields as required on every line. The project overview's "NBA prop board response" block describes the old shape too. Nothing generates code from either today, so nothing breaks, but the next reader (or an Ask tool) is told the wrong contract.
**Suggested fix:** point the route's `response_model` at a wire schema (lines without the two fields), or note the omission in the route docstring; refresh the overview block at the next `/overview` run.
**Resolution:**

### F-77 [P3] fixed - The NBA board's main-thread task after load is still about 200 ms on desktop

**File:** web/src/utils/nbaPropBoardWire.ts:36; web/src/pages/NbaPropBoardPage.tsx:26
**Found:** 2026-11-24 by /audit (scope: current; lens: performance)
**Why it matters:** F-46 measured a 207-259 ms long task after the board lands (parse, grouping every market, render, forced layout, GC). The body is now 44% smaller, which should shrink parse and GC, but `nbaExpandPropBoard` adds a pass that rebuilds 4,208 line objects, and the grouping, render and `BoardFilterBar` layout are unchanged. Without a trace there is no evidence the task got shorter.
**Suggested fix:** record a Performance trace of a direct production load of `#/nba/props` before and after this branch (same date, desktop and 4x CPU throttle) and compare the long task. If it is still over about 150 ms on desktop, the next lever is F-46's per-market fetching or the `scrollWidth` read.
**Resolution:** Profiled 2026-11-24 on production (`409e63b8`, both services live), direct loads of `#/nba/props?date=2026-11-23` (1,561,980 B raw, 4,208 lines, one request, `playerRecent` on all 10 games) in headless Chromium via CDP tracing plus a 100 us sampling profile, 1440x900, cold cache. Desktop unthrottled, 6 runs: the long task after the response ran 174, 205, 208, 209, 251 and 319 ms, the same as F-46's 207-259 ms before the fix (F-46's figures, not a like-for-like rebuild of `f7653cb3`). 4x CPU throttle, 6 runs: 956-1,756 ms, followed by more 230-510 ms tasks. In the three fully profiled desktop runs the task splits as: forced style and layout from rc-select's `scrollWidth` layout effect (the `BoardFilterBar` Select) 61-71 ms, React render and commit 35-48 ms, antd and app component code 32-42 ms, GC 19-23 ms, antd cssinjs style lookup (`Array.from(children).filter(STYLE)`) 8-9 ms; at 4x the forced layout is 362-633 ms. JSON parse and `nbaExpandPropBoard` are not in it: they run in their own task, 15 ms desktop (expansion 1.8 ms of it) and 66 ms at 4x (expansion 10 ms). The smaller body and the expansion pass therefore moved neither way; the task is the render of every market plus the forced layout. Still over the 150 ms bar, so left open. Next lever: the forced layout first (stop the Select measuring during the board's first commit, or render the board's rows after the filter bar has laid out), then F-46's per-market fetching or rendering only the selected market to cut the render share. Fixed on `fix/nba-board-long-task` (step 2, 2026-11-24), pending `/audit`: the board renders 25 rows with the page and adds 25 more after each paint (`useRowBatches`, `rowBatches.ts`), with memoized rows so a batch never re-renders the earlier ones. On a local production build for 2026-11-23 the largest task after the response fell from 190-227 ms to 104-124 ms on desktop (7 of 8 runs; one first run at 155 ms) and from 1,119-1,189 ms to 376-618 ms at 4x; all 119 rows land within about 250 ms on desktop. The `scrollWidth` read was where the layout landed, not its cause. Production re-trace pending a deploy.

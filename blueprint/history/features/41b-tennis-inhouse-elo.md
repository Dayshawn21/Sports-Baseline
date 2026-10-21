# Feature: In-house tennis ELO

**From build-plan:** 41b (parent 41, TennisMyLife match data)
**Status:** Engineering completed and owner approved 2026-10-21 UTC; shadow activated; forward verdict accruing with zero observations; first real freeze and runner acceptance pending
**Branch:** `feature/tennis-inhouse-elo`

## Goal

Compute overall and surface ELO from TennisMyLife results with 26c's fixed
calculation, persist ratings separately from the incumbent, and build a
read-only comparison that determines whether 41c may propose a source switch.
The live ensemble, props, player pages and local TennisAbstract refresh keep
their current behavior throughout 41b.

This is one backend feature with reviewed build steps (Step 4 split into
4a-4c after the input audit exposed identity conflicts). It may complete
with a forward verdict of **accruing**. Waiting for matches is not permission
to substitute a historical sample or enable serving.

## Decisions to review

| Decision | Reason |
|---|---|
| Use a separate `tennis_elo_snapshots` table, with source `tennismylife-elo-v1`. | `player_elo` is unique on player/date, its readers do not filter sources, and admin writes also use it. An additive table prevents both overwrites and accidental source selection without changing those established contracts. |
| Replay the full provider opponent network from 2021 onward, not just tracked players or stored box scores. | 41a skips unknown players and rows without stats. Either restriction would remove legitimate opponents and distort ratings. Only the final persistence/linking step is restricted to tracked players. |
| Keep the 26c constants and the frozen 26d coefficients. | This tests an ELO source, not a new rating formula, coefficient fit or model. |
| Treat old seasons as replay inputs and engineering checks only. | 2023-2025 was already evaluated by 26c/26d, and 2026 was used by 40a. Neither is a fresh adoption sample. |
| Freeze a new pair of forecasts before each eligible future match. | Rebuilding an old prediction from today's CSV or today's TennisAbstract rating cannot prove that the inputs existed before play. |
| Test non-inferiority for an operational replacement, with a fixed log-loss margin of 0.005. | The motivation includes removing dependence on a local scrape. A pass means bounded forecast degradation under the rule below, not superiority or a betting edge. |

## Evidence and source boundary

- Inspected `app/ml/elo_history.py`, 26c/26d and 40a's archives, the existing
  TennisMyLife parser/ingest, all `player_elo` SQL readers, the predictor and
  `tennis-ingest.yml`. No dataset evaluation, provider CSV download, database
  query or model scoring was run to write this spec.
- [TennisMyLife's source documentation](https://stats.tennismylife.org/tennis-match-database)
  describes CSV access, provider IDs, a tournament-week date field, and lower
  confidence in its WTA files. Checked 2026-10-20. The existing local fixture
  has differing dates within a tournament. Therefore do not assume every
  family's `tourney_date` is an actual played date.
- Step 1 verifies the file manifest, IDs, date semantics and duplicate keys
  from metadata and pre-2023 examples. A date ambiguity prevents retrospective
  accuracy claims; it does not make an input downloaded before a future
  forecast into a historical as-of input.
- Do not change 41a's parser, display precedence, grading source, or file paths
  as a side effect. Its Challenger ongoing filename differs from the current
  download-page link; verify the manifest for this feature rather than assuming
  either spelling is authoritative. A confirmed 41a defect belongs in a fix.

## In scope

- A results parser independent of whether box-score statistics exist.
- Deterministic ELO replay, source provenance and a dry-run-first ratings CLI.
- Additive storage for candidate ratings and immutable pre-match comparisons.
- Explicit, unambiguous linking of provider identities to tracked players.
- A read-only report CLI, defaulting to coverage/counts, with an explicit
  once-only scoring mode governed by the rule below.
- Actions configuration to refresh candidate ratings before the daily
  prediction cycle and freeze comparisons alongside that cycle.

## Out of scope

- 41c: selecting these ratings for production, changing the model version,
  replacing TennisAbstract, or retiring `Lineform ingest_daily`.
- Changes to `player_elo`, its indexes/readers/writers, admin overrides,
  `EloIndex` behavior for existing callers, ML training, frozen blend
  coefficients, reliability thresholds, pick rules or moneyline-off behavior.
- ELO tuning, decay, extra seasons before 2021, alternative candidates,
  historical refitting, or another read of an old holdout for a verdict.
- WTA 125/ITF coverage, doubles, rolling stats, prop projections, box-score
  grading, API endpoints, web UI or request-time report construction.
- Push, hosted deployment, remote dispatch or local task changes.

## Build loop

1. Explain the next step and its checks before editing code.
2. Implement only that step, with its logic tests.
3. Show its diff and evidence, then wait for the user's review before the next.
4. Checkpoints require approval and passing checks. `/complete` owns the final
   archive, work commit and separately approved merge/push.

## Build steps

- [x] **Step 1 - Results contract and input audit.** Add a pure
  `app/core/tennis_elo.py` results parser and small synthetic fixtures. Define
  provider identity, event/match keys, deterministic ordering and exclusions
  below. Inspect the source manifest and 2021/2022 examples, recording family
  coverage, ID stability, date meanings, duplicate/conflict counts and how
  completed results are represented. Do not score any year. If stable identity,
  event keys or date handling cannot be established, stop with the concrete
  contract question before replaying real data.

  *Done when:* parser tests accept completed matches with no stats, reject
  doubles and walkovers, distinguish malformed from excluded rows, isolate
  men's/women's identities, deduplicate yearly/ongoing copies, and stop on
  contradictory duplicate results. Source facts and verified URLs are recorded
  in Evidence below; 41a's parser and tests are unchanged.

- [x] **Step 2 - Deterministic pure replay.** Implement the new adapter/replay
  around `EloIndex`, preserving its base 1500, 400-point logistic scale and
  `K(n) = 250 / (n + 5)^0.4`. Overall counts include all admitted surfaces;
  surface counts are independent for hard/clay/grass. Unknown surfaces update
  overall only. Sort the admitted rows deterministically before constructing
  the index; do not change the existing index's global behavior.

  *Done when:* a hand-worked sequence agrees with `EloIndex` to 1e-9; surface
  fallback, first appearance, missing surface and match counts are tested;
  shuffled input produces identical output; queries before a date exclude
  that date's rows. Audit output clearly identifies tournament-week dates
  instead of presenting their historical ratings as leak-free match features.

- [x] **Step 3 - Candidate rating storage.** Add the next Alembic revision
  after the current head (currently `0045`), creating only
  `tennis_elo_snapshots`; add `app/repositories/tennis_elo.py` for batched
  writes and explicit-source reads. Define the immutable daily snapshot and
  manifest fields below. Write the migration first; apply it manually only
  after the user reviews this step and authorizes the shared-database change.

  *Done when:* offline migration SQL is inspected, repository calls pass
  concrete typed payloads, and approved database verification shows legacy
  and candidate ratings for the same player/date coexist. Existing
  `player_elo` facts and fixed-input public player/prediction output are
  identical before and after. Repeating a candidate snapshot adds no rows;
  a changed payload under the same key fails rather than overwriting it.

- [x] **Step 4a - Download and preview ratings.** Add
  `app/ingest/tennis_elo.py` with `--dry-run` as its default and explicit
  `--write`. Cache immutable downloaded files and a hash manifest under the
  gitignored `api/data/tennismylife-elo/` directory. Load verified 2021-current
  annual families plus current ongoing files, replay all provider players,
  then map tracked players in one batch. Implement and unit-test the writer
  path, but keep real writes behind 4b/4c. No automatic historical database
  backfill is required.

  *Done when:* the dry-run prints per-family download/parse/exclusion counts,
  identity conflicts, unique matches, tracked/unmapped/ambiguous players,
  ratings and manifest hash without writing the DB, and `--manifest` reproduces
  that exact plan. A download failure, missing required file, unverified source
  contract or identity conflict blocks a partial write. No players, aliases or
  legacy ELO rows are created/changed. Real source conflicts are recorded for
  4b, rather than guessed through in this step.

- [x] **Step 4b - Review and freeze identity normalization.** Added with owner
  approval on 2026-10-20 after the dry run found 54 conflicts. Audit provider
  identities across the entire admitted network, including untracked opponents.
  Prepare a versioned crosswalk from raw `(namespace, provider_id)` to a stable
  canonical provider key, with official profile/metadata evidence. Review the
  registry and unresolved cases with the owner before applying it to replay.
  Resolve local name forks only with explicit read-only mapping overrides
  supported by player metadata; never merge or modify app players/aliases.

  *Done when:* verified crosswalk entries and evidence are frozen in a small
  tracked registry; normalization happens before deduplication, replay and
  local mapping; the cached-source dry run has no unresolved identity conflict.
  Tests cover shared identities across years, opposite namespace isolation,
  unrelated namesakes, duplicate/self-match/conflicting-result detection and
  deterministic replay. Unverifiable cases remain blocking. No automatic
  same-name merge, ELO-constant change, fitting or accuracy-based selection.

- [x] **Step 4c - Approve and prove the current-day write.** Re-run the normalized
  dry run and show its complete counts, normalization version and manifest hash.
  Obtain explicit approval for that exact current-UTC-day manifest, then persist
  the full daily roster once and repeat it. Compare legacy facts and fixed-input
  output before/after, as in Step 3.

  *Done when:* the approved first write stores only uniquely mapped players,
  the repeat inserts zero and reuses the immutable day, no local identity or
  legacy ELO fact changes, and the before/after proof is recorded. No write is
  authorized merely by approval of 4a or the identity-review amendment.

- [x] **Step 5a - Immutable comparison and coverage storage.** Split from
  Step 5 to keep the schema/repository review separate from predictor changes.
  Add the next additive migration for `tennis_elo_comparisons` and its
  companion `tennis_elo_freeze_cycles` coverage ledger. Add validated typed
  payloads and atomic, serialized repository writes. No schema application
  or real comparison freeze before review and separate approval.

  *Done when:* offline upgrade/downgrade SQL is inspected; tests cover finite
  probabilities, source/provenance/orientation/timing checks, full coverage
  attempts including missing-candidate skips, immutable cycle retries,
  first-pair-wins uniqueness and atomic rollback. The comparison tables are
  isolated from `predictions`, `players`, aliases and legacy ELO. Real schema
  application and storage proof follow only after approval.

- [x] **Step 5b - Freeze paired forecasts (engineering complete; real-freeze acceptance pending).** Using Step 5a storage, add a small shadow
  service/CLI in `app/services/tennis/elo_comparison.py` and
  `app/ingest/tennis_elo_comparison.py`. Freeze incumbent and candidate from
  the same market, match metadata, coefficients and production gates. Reuse
  the existing predictor's input construction; a minimal helper extraction
  is allowed only with parity evidence. Shadow writes never enter
  `predictions`, and a shadow failure never changes a served forecast.

  *Done when:* synthetic tests prove both forecasts use one market snapshot,
  candidate ratings replace only ELO, orientation is consistent, the baseline
  equals the current predictor, retries cannot replace a frozen pair, and
  post-start/stale/missing/ambiguous inputs cannot enter. A dry-run reports
  eligible/excluded counts without outcomes. Approved real freezes are shown
  to precede kickoff and leave live prediction output unchanged.

- [x] **Step 6 - Read-only rule and report.** Add
  `app/backtest/tennis_elo.py` with default `--count` and explicit `--score`.
  Encode the rule below as pure tested functions. Count mode does not fetch
  winners, compute losses, print running accuracy or call a grading loader.
  Before scoring, lock the mature sample IDs and rule/input hashes in an
  immutable local report artifact. Preserve that artifact with the completion
  evidence; later invocations return the locked report instead of a new test.

  *Done when:* tests cover every exclusion, exact sample/margin boundaries,
  source/group separation, revised kickoff, unresolved results and all three
  verdicts. Below the floor the real report prints accruing with no scored
  numbers. If a group is ready, its once-only run requires a separate go-ahead
  after code review; record its locked IDs, hashes and output. Real scoring
  is not required to complete the engineering work while accruing.

- [x] **Step 7 - Scheduled accrual and final proof.** Add candidate refresh to
  the 11:00 UTC TennisMyLife job and shadow freezing after production
  predictions at 13:30 UTC, retaining all existing jobs and their behavior.
  Add an explicit dispatch choice if needed. Require a complete successful
  current-UTC-day candidate snapshot before freezing; otherwise report the
  skipped cycle. Add concurrency protection for candidate writes and freeze
  retries. Document the new CLIs in `AGENTS.md`.

  *Done when:* workflow conditions/ordering and dry-run outputs are inspected,
  the exact Verify command passes, and Evidence contains source-isolation,
  immutable-freeze and count-only proof. After an approved push, dispatch the
  refresh/freeze and confirm stored timestamps and idempotency; if push is
  deferred, record runner acceptance as pending, not passed. Update the local
  ignored employer guide at completion with implemented/accruing boundaries.

## Files / areas

- New: `api/app/core/tennis_elo.py`, `api/app/repositories/tennis_elo.py`,
  `api/app/core/tennis_elo_report.py`, `api/app/repositories/tennis_elo_report.py`,
  `api/app/repositories/tennis_elo_comparison.py`,
  `api/app/services/tennis/elo_comparison.py`, the two ingest CLIs and
  `api/app/backtest/tennis_elo.py`.
- Two new migrations, using the next available revision IDs at implementation.
- Focused parser/replay, ingest, repository-payload and comparison/report tests
  in `api/tests/`; small fixtures in `api/tests/fixtures/`.
- `.gitignore`, `.github/workflows/tennis-ingest.yml`, `AGENTS.md`, this spec,
  and the existing predictor only if a small parity-preserving extraction
  is needed for the common input builder.
- `app/ml/elo_history.py`, `app/core/tennis_market_blend*.py`, 41a's code and
  legacy ELO SQL remain unchanged. No frontend work.

## Data / contracts

### Results and replay

- `TennisEloMatch`: namespace (`ATP` or `WTA`), family, provider event ID,
  provider match ID/number, provider date, round, surface, winner/loser provider
  IDs and names, completed status and stable source key. Preserve provider IDs
  as strings. Replay identity is `(namespace, provider_player_id)`; never
  equate provider IDs with local `players.id`.
- Families are ATP, men's Challenger, ATP qualifying and WTA main tour,
  from 2021 onward. No stats are required. Admit only completed singles with
  a score accepted by the existing completed-score helper and valid distinct
  participant IDs. Retirements, walkovers, abandoned/malformed results and
  exhibitions are excluded and counted. Record the exact admitted level
  values from Step 1 before processing later years.
- Deduplicate on verified provider event/match identity, not player name/date.
  Annual copies take precedence only when the facts agree; a result/identity
  conflict is fatal. Sort by date, event key and verified round/match order.
  These are reproducibility rules, not evidence of intraday chronology.
- Resolve normalized names/aliases through the existing batched index; require
  a one-to-one mapping consistent with namespace. Collisions or conflicting
  names/IDs are excluded and reported, never guessed or inserted as players.
- Only completed results present in a file downloaded before the snapshot
  freeze may contribute. Exclude rows dated on/after the UTC snapshot date,
  and any match identifiable as the forecast target. Do not later rebuild a
  frozen forecast from revised source files. Ambiguous tournament-week dating
  prohibits historical as-of claims even with the date cutoff.
- Replay API: `TennisEloReplay(matches)` deduplicates and orders the admitted
  results, keeping a sorted tuple of namespaced provider-player keys.
  `rating(player, before)` returns an immutable `TennisEloRating` with
  overall/hard/clay/grass values and their separate match counts, or None
  before first appearance. `probability(p1, p2, surface, before)` uses both
  surface ratings when available, otherwise both overall ratings; it stays
  None if either player lacks prior history. These are provider-date lookups,
  not a claim of historical pre-match availability.

### Candidate snapshots (load-bearing for 41c)

- `tennis_elo_snapshots`: unique `(player_id, source, as_of_date)`; FK to
  `players`; overall/hard/clay/grass ratings, overall and surface counts,
  provider namespace/ID, actual `computed_at` UTC, latest source download
  time, replay cutoff, method version and manifest SHA-256.
- Source and method are `tennismylife-elo-v1`. Null surface ratings mean no
  prior result there; an unseen player has no stored rating, not a fabricated
  observed 1500. Snapshot date is the UTC run date, not a historical provider
  date. First successful snapshot per day is immutable.
- Retain source URLs, file hashes and download times in the cached manifest.
  A partial/revised/conflicting run cannot replace a committed snapshot.
  41c must request this source explicitly; no legacy reader discovers it.
- Step 3 repository contract: `insert_daily_snapshots(db, snapshots)` accepts
  the complete daily player roster with one shared provenance, inside the
  caller's transaction. A nested transaction plus source/date advisory lock
  makes the batch atomic and serializes competing writers. Exact retries in
  any roster order return zero; changed facts, provenance, missing or added
  players are rejected. The repository does not commit. Future ingest must
  submit the full batch, not call this function on separate chunks of a day.
- `TennisEloSnapshot` pairs a local player ID and provider identity with a
  `TennisEloRating` and the provenance fields above. Dates are checked in UTC,
  timestamps must be aware and ordered, ratings finite, surface nulls consistent
  with counts, and provider/player mappings one-to-one within the daily batch.
  `get_daily_snapshots(db, *, source, as_of_date)` requires the explicit v1
  source. There is no fallback to or write to `player_elo`.

### Identity-normalization amendment (approved 2026-10-20)

- The original assumption that a provider ID was stable across all six
  seasons did not hold for the real inputs. The owner approved adding a
  separately reviewed identity-normalization step, without changing the ELO
  formula or merging app players. This modifies only this feature's build
  steps; the user-owned build plan's 41b scope is unchanged.
- Freeze the raw-to-canonical provider-key registry and its evidence before
  replay. Include the normalization version and registry SHA-256 in the input
  manifest so snapshots and future comparisons can reproduce it. Registry
  changes invalidate an uncommitted reviewed manifest; after experiment
  activation they require a separate version/experiment review.
- Validate all suspected identity aliases in the opponent network, not only
  the currently tracked players. Equal normalized names alone are insufficient
  evidence. Preserve raw IDs and source provenance; canonical keys never cross
  ATP/WTA namespaces. Local mapping overrides do not mutate `players`,
  `player_aliases`, legacy ELO or existing match links.
- Proposed registry area: `api/app/ingest/data/tennis_elo_identities.csv` with
  an evidence README; pure registry validation/application in
  `app/core/tennis_elo.py`. The owner reviews the actual entries before use.

### Paired freezes (load-bearing for the verdict)

- Unique `(match_id, experiment_version)`; experiment `tennis-elo-source-v1`.
  Store match/player IDs and orientation, group, frozen scheduled kickoff,
  `frozen_at`, incumbent model version, market probability and its odds-row
  ID/time/provider, both raw ELO probabilities and resulting ensemble
  probabilities, prior counts, gate/fallback reasons, coefficient hash,
  candidate manifest/date and the incumbent ratings/dates actually used.
- Store a validated typed payload (JSONB is acceptable for provenance) with
  probabilities finite and in range. Copy values rather than relying on a
  mutable latest-rating or latest-odds lookup during grading.
- Pin reviewed runtime versions and activation in
  `app/ingest/data/tennis_elo_experiment.json`. `activated_at: null` means
  inactive. The first eligible date is the next full UTC day after both
  activation and spec approval. Copy the config hash and activation/start
  fields into pairs and the config hash into every coverage attempt.
  Changed pins stop accrual, including after coverage-only skipped cycles.
- Require `downloaded_at <= computed_at <= frozen_at < kickoff`, market
  `fetched_at <= frozen_at`, scheduled/unstarted status and current-day
  complete candidate inputs. Use the existing production book selection,
  staleness and reliability gates. Exclude already-resulted target matches.
- First successful pair wins; duplicate dispatches do nothing. Missing inputs
  are counted, never imputed as a paired observation. A later kickoff change
  is checked against both frozen and current start times during grading.

## Pre-registered forward rule

**Approved for implementation 2026-10-20 via `$implement`.** Freeze these
choices before activation or any scored 2026 case. Do not adjust them after
observing outcomes. Owner approved shadow activation after Step 7 review;
the recorded activation and first eligible date are in the evidence below.

| Field | Fixed choice |
|---|---|
| Start | First full UTC date after both spec approval and shadow activation. Record the exact activation timestamp and start date before the first freeze. No earlier match can enter. Continue into later calendar years if needed. |
| Population | Future ATP main tour, WTA main tour, and men's Challenger singles; independently gated groups `ATP`, `WTA`, `ATP_CHALLENGER`. Exclude qualifiers, exhibitions, WTA 125 and ITF from scoring. Qualifying results can still feed ratings. |
| Candidate | Current frozen blend with only its ELO input replaced by `tennismylife-elo-v1`; same market and production reliability gates. |
| Incumbent | Current production blend using the legacy ELO path, including existing admin behavior, computed at the same freeze. |
| Version continuity | Pin incumbent model version, coefficient hash and gate constants at activation. A change stops accrual for review; never pool versions or silently restart the experiment. |
| Eligible pair | Both sources have real overall ratings and at least 10 admitted prior results per player; candidate and incumbent forecasts are frozen before play with the same valid market. Retain gate-to-market cases; do not select on which source passes the gap gate. |
| Result | Completed score and a valid participant winner; unresolved matches block their UTC cohort day, void/cancelled/retired matches are excluded with counts. No guessed losses/wins. |
| Maturity and sample | Per group, order by frozen kickoff UTC day. Use all eligible cases through the first fully resolved day reaching 300 paired matches, at least 14 distinct UTC kickoff days, and a three-full-UTC-day settlement lag. Do not skip an unresolved earlier day to reach the floor. Lock once; no rolling or repeated verdict. |
| Coverage | Report candidate availability among all otherwise incumbent-eligible matches in the same frozen cohorts, including missing-source skips. Require at least 90% coverage. Preserve attempt/skip counts durably with each cycle, so absent pairs remain in the denominator. |
| G1 | Paired log loss, candidate minus incumbent: `mean + 2.5 * SE <= 0.005`. |
| G2 | Paired log loss, candidate minus common de-vigged market: `mean + 2.5 * SE <= 0.005`. |
| Statistics | Existing per-match paired-loss calculation; 2.5 SE for three group decisions. Require finite SE and the sample floors. The 0.005 margin is an absolute per-match natural-log-loss tolerance. |
| Verdict | Below maturity/sample floors: `accruing`, with counts only. At the locked sample: `pass` only if coverage, G1 and G2 all pass; otherwise `keep incumbent`, final for this experiment. No extension to seek a pass. |
| Interpretation | Pass supports reviewing 41c for that group on market-priced matches. It does not establish better accuracy, profit, or a moneyline edge. WTA 125 and no-market fallbacks remain outside this authorization. |
| Context | On the locked sample only: Brier, raw-ELO losses, calibration, surface counts and missing/gated proportions. No extra candidates, decisive subgroup tests, ROI threshold changes or interim loss tables. |

The coverage ledger is part of Step 5's storage contract: an immutable cycle
record keyed by experiment and UTC freeze cycle, with attempted match IDs,
eligibility/skip reasons and timestamps. It can be a small companion table in
the comparison migration. Never infer successful coverage from pairs alone.

### Report implementation of the frozen rule

- Count mode reads frozen payloads, coverage attempts and current match
  metadata only. It selects no winner or score columns and never invokes a
  result loader or loss function. A count/day floor being met means only
  that a separate score review may be possible, not that resolution is known.
- A kickoff cohort D closes at D+1 midnight. Three complete settlement days
  then finish at D+4 midnight. Require this lag for both the frozen and any
  revised current kickoff. A rescheduled match stays in its original frozen
  cohort; an unresolved or not-yet-mature member blocks that entire day and
  every later day needed for the sample. Include the whole first resolved
  day reaching both floors, even when that makes the sample larger than 300.
- Coverage counts unique incumbent-eligible match IDs, not repeated cycles.
  When a pair exists, use its frozen kickoff cohort; otherwise use the first
  eligible attempt's cohort. Any recorded pre-start availability in that
  cohort counts as available, including recovery after an earlier missing
  source. Coverage is operational availability: later void/retirement
  exclusions from forecast scoring do not remove those eligible attempts.
- Explicit void/cancelled/retired observations are excluded with counts.
  Missing results, an invalid/missing participant winner, or a score that
  does not prove completion remain unresolved. Later participant changes or
  kickoff revisions at/before the freeze invalidate the captured pair.
- Only explicit `--score --group <group>` reads results. Before the first
  loss calculation, lock the selected IDs, coverage IDs, rule/config/input
  hashes, copied forecasts, result observations and supporting provenance in
  a local append-only sample artifact. A group file lock excludes concurrent
  scorers. Later calls return the saved report; crash recovery after sample
  lock uses the same copied inputs, never a newly selected sample.
- Pin drift or malformed frozen payloads block scoring for review. Neither
  a weak verdict nor low coverage authorizes adding cases to seek a pass.

## Testing

- Logic-bearing steps ship pytest tests with synthetic data. Test the parser,
  deduplication, identities, stable ordering, exact rating arithmetic, counts,
  surface fallback, source isolation, immutable payloads, timing, sample lock,
  coverage denominator and every verdict boundary in the same step as its logic.
- Mock downloads/DB sessions in unit tests. Do not use real provider results,
  historical holdout scoring or shared DB writes in the automated suite.
- Migration/repository integration is verified separately with offline SQL
  and approved live before/after evidence. Compare fixed-input production
  predictions and legacy player responses; adding a candidate must not alter
  their ratings, ranks, histories or forecast probabilities.
- Default commands and workflow dry runs must show counts only. Real scoring
  remains an explicit operation on a reviewed locked sample.
- Final gate, API venv active: `npm --prefix web run verify && cd api && python -m pytest`.
  On this Windows shell, use `npm.cmd` if required and the API venv Python.
- Manual try from `api/`: `python -m app.ingest.tennis_elo --dry-run`,
  `python -m app.ingest.tennis_elo_comparison --dry-run`, then
  `python -m app.backtest.tennis_elo --count`. Expected: provenance and
  coverage counts, no production change and no accuracy verdict while accruing.

## Notes for the AI

- This spec is server/CLI only. Core is pure; repositories own every SQL
  query. Keep downloads, mapping and orchestration outside core. Use concrete
  typed dataclasses, not unstructured `Any` or a second large framework.
- Do not run a historical evaluation to decide these rules. Do not fit new
  coefficients, reuse old outcomes as fresh evidence or change moneyline picks.
- Preserve old ELO provenance including `admin` and `admin_fetch`. The new
  table is intentional isolation, not a migration of the existing sources.
- Shared Neon schema changes and initial writes need the reviewed concrete
  operation and explicit user approval. Apply migrations one at a time, using
  an explicit Alembic config as documented in `AGENTS.md`.
- Keep heavy replay/report work in CLI/Actions, off Render's 512 MB request
  path. Do not add endpoint-triggered provider calls.
- No source switch follows from engineering completion or an accruing result.
  41c remains conditional and must preserve unsupported groups/fallbacks.
- At `/complete`, update the local ignored employer guide if present, without
  staging it; distinguish implemented, activated, accruing and validated work.

## Evidence / results

- Step 1 implemented and approved 2026-10-20 via `Continue`. Step 2 started
  without a checkpoint commit. No DB mutation, model evaluation, activation
  or new holdout read performed.
- Source manifest: `https://stats.tennismylife.org/api/data-files`, 171 entries
  when fetched. It lists `ongoing_tourneys.csv`,
  `challenger_ongoing_tourneys.csv` and `wta_ongoing_tourneys.csv`. The website
  link spelling differs, but 41a's existing Challenger path matches the
  manifest. No 41a repair is needed from this evidence.
- Read only the eight 2021/2022 CSVs below for schema, identity, date and score
  parsing. Raw inputs, full SHA-256s, manifest and audit report are local and
  ignored under `output/41b-input-audit/`. No later-year CSV was downloaded.

| Source path under `https://stats.tennismylife.org/data/` | Rows | Admitted | Retirement | Walkover | Other unfinished | Malformed |
|---|---:|---:|---:|---:|---:|---:|
| `2021.csv` | 2,735 | 2,627 | 62 | 20 | 26 | 0 |
| `2021_challenger.csv` | 4,340 | 4,155 | 167 | 18 | 0 | 0 |
| `atp_quali/2021_atp_quali.csv` | 1,290 | 1,250 | 33 | 3 | 4 | 0 |
| `2021_wta.csv` | 2,597 | 2,461 | 85 | 27 | 23 | 1 |
| `2022.csv` | 2,918 | 2,805 | 71 | 17 | 25 | 0 |
| `2022_challenger.csv` | 5,384 | 5,149 | 210 | 25 | 0 | 0 |
| `atp_quali/2022_atp_quali.csv` | 1,318 | 1,277 | 38 | 3 | 0 | 0 |
| `2022_wta.csv` | 2,594 | 2,474 | 89 | 27 | 4 | 0 |

- Total 23,176 raw results; 22,198 admitted, unique results. Zero duplicate
  or conflicting `(namespace, event, round, match number)` keys within or
  across the audited files. The code additionally includes family in the
  identity to separate qualifying/main-draw namespaces. Synthetic tests
  exercise annual/ongoing duplication; no current ongoing results were read.
- Required IDs, match numbers, dates and best-of were present in every raw
  row. ATP IDs are alphanumeric, WTA IDs are numeric strings. A name never
  mapped to multiple provider IDs within its namespace in this audit.
  Two ATP IDs had spelling variants across files: `S0H2` (Aleksandr/Alexander
  Shevchenko) and `EA31` (Melios/Menelaos Efstathiou). Replay identity remains
  the provider ID; Step 4 must resolve names without inventing aliases.
- Every ATP/Challenger/qualifying event had a single provider date across
  rounds. WTA had one multi-date event in 2021 and three in 2022, including
  widely separated dates under `2022-2075`. These fields are not uniformly
  actual match dates. The approved prohibition on historical as-of accuracy
  claims remains; forward availability uses real download/freeze timestamps.
- Admitted levels are frozen from these observations: ATP
  `A/250/500/M/G/D/O/F`, Challenger `C`, ATP qualifying `250/500/M/G`, WTA
  `250/500/1000/G/D/O/F`. WTA's additional `W` occurs only for
  `2021-2033` (Charleston 2); [the official WTA listing](https://www.wtatennis.com/tournaments/2033/charleston-250/2021)
  confirms WTA 250. Only that specific W-level event is allowed, not an
  inference that all future W labels mean the same thing. Unknown levels or
  rounds fail visibly. Davis/Billie Jean King Cup level `D` is not a doubles
  flag; doubles participant delimiters are separately excluded.
- One malformed raw score at `2021_wta.csv` line 1856 contains `RET+H64`.
  It raises `ValueError`, distinct from intentional exclusions. Bracketed
  match-tiebreak scores are recognized but excluded by the existing
  completed-score contract. No source strings or old parser were repaired.
- Focused test command: `.venv/Scripts/python.exe -m pytest
  tests/test_tennis_elo.py tests/test_tennismylife.py -q` from `api/`:
  **107 passed** (52 new parser/identity tests, 55 existing 41a tests).
- Full Verify passed: `npm --prefix web run verify && cd api && python -m
  pytest`, with the API venv on PATH: **632 web tests, production build and
  3,161 API tests passed**. One existing dependency deprecation warning.
  The initial sandbox run could not load Vite's config because esbuild
  directory access was denied; rerunning the same gate with approved access
  passed. Log: `output/41b-step1-verify.log` (ignored).
- Step 2 built, verified and approved 2026-10-20 via `Continue`, without a
  checkpoint commit. The new pure adapter reuses `EloIndex` and
  `expected_score` without editing the existing index or its consumers.
  All Step 2 replay/probability checks used synthetic results only. No source
  download, real-data replay, database operation or model evaluation ran.
- Step 2 focused tests: `.venv/Scripts/python.exe -m pytest
  tests/test_tennis_elo_replay.py tests/test_tennis_elo.py
  tests/test_elo_history.py -q` from `api/`: **86 passed**, including
  **17 new replay cases**. Evidence covers independent hand calculations,
  parity with the existing index to 1e-9, separate surface counts/K factors,
  unknown/unseen players, surface fallback, same-date exclusion, future
  result isolation, duplicate/conflict handling, shuffled same-day updates
  and men's/women's identity isolation.
- A synthetic four-match/three-player demo printed the audit note:
  `Provider dates may be tournament-week dates, not played dates; historical
  lookups do not prove pre-match availability.` Its first hard-court win
  produces 1565.6631951100942 versus 1434.3368048899058; the tests also check
  later unequal-K and surface-only updates.
- Step 2 full Verify: `npm --prefix web run verify && cd api && python -m
  pytest`, API venv on PATH, with the same approved esbuild access:
  **632 web tests, production build and 3,178 API tests passed**. One existing
  dependency deprecation warning. Log: `output/41b-step2-verify.log` (ignored).
- Step 3 local implementation verified 2026-10-20. New migration
  `0046_tennis_elo_snapshots.py` follows head `0045` and creates only the
  candidate table, with player FK, source/player/date primary key, unique
  source/date/provider identity and value/provenance constraints. The
  provider-identity index also supports source/date reads. Existing ELO
  repositories, predictor, player-detail service and `EloIndex` are unchanged
  against `master`.
- Offline SQL was generated with `.venv/Scripts/python.exe -m alembic -c
  ../output/41b-alembic.ini upgrade 0045:0046 --sql` from `api/`, and inspected
  at `output/41b-0046-upgrade.sql`. It creates the new table and advances the
  Alembic version, without altering or dropping legacy tables. The initial
  repo-root invocation failed to import `app`; the documented `api/` working
  directory resolved it. The approved application is recorded below.
- A read-only Neon transaction confirmed `alembic_version = 0045` and no
  candidate table. `player_elo` had 14,853 rows with digest
  `4084f05137d16a2a5be957af40675288`. This is a baseline, not after-migration
  proof. Local evidence: `output/41b-step3-db-before.json` (ignored).
- Step 3 focused tests: `.venv/Scripts/python.exe -m pytest
  tests/test_tennis_elo_repository.py tests/test_tennis_elo_replay.py -q`:
  **54 passed**, including **37 new repository/validation cases**. They cover
  finite ratings and counts, UTC provenance, batch identity/provenance,
  atomic error handling, immutable retries/rosters, explicit source reads and
  payload round-tripping. These are unit tests with recording sessions, not
  live PostgreSQL proof of constraints or locking.
- Step 3 full Verify passed: `npm --prefix web run verify && cd api &&
  python -m pytest`, API venv on PATH: **632 web tests, production build and
  3,215 API tests passed**. One existing dependency deprecation warning.
  Log: `output/41b-step3-verify.log` (ignored).
- Owner approved Step 3's migration and rollback-only probe on 2026-10-20
  via `continue`, replying to the concrete Neon approval request. A fresh
  read-only preflight confirmed revision `0045` and no candidate table.
- Applied exactly one migration command from `api/`:
  `.venv/Scripts/python.exe -m alembic -c ../output/41b-alembic.ini upgrade 0046`.
  It passed, advancing the shared Neon database to `0046` and creating
  `tennis_elo_snapshots`. No source/serving switch or deployment occurred.
- Ran `api/.venv/Scripts/python.exe output/41b-step3-db-probe.py` from the
  repo root after the migration. The live PostgreSQL probe passed: one
  synthetic candidate inserted inside the outer transaction; same-player/date
  coexistence with legacy ELO confirmed; identical retry inserted zero;
  changed manifest rejected; public player-detail service, legacy batch
  reader and fixed-input blend output exactly unchanged. The probe's entire
  transaction was rolled back, leaving **zero candidate rows**.
- Legacy ELO retained **14,853 rows** and digest
  `4084f05137d16a2a5be957af40675288` before, during and after the probe,
  matching the original pre-migration baseline. Results are in
  `output/41b-step3-db-after.json` (ignored). Probe provenance was synthetic,
  never an observed model input. Concurrent-writer and negative-constraint
  stress tests were not performed; do not imply those from the successful probe.
- No application source changed after Step 3's passing Verify; this turn
  applied the reviewed migration, ran its integration proof and updated this
  record. Step 3 is approved and checked; no checkpoint commit was requested.
- Reviewed migration/write approvals: `0046` and rollback-only synthetic probe
  approved and completed. The first real candidate-data write still requires
  the separate reviewed dry-run and owner approval in Step 4.
- Activation timestamp, forward start and version hashes: pending Step 5.
- Runtime storage evidence: Step 3 passed above; real ratings ingest is pending
  Steps 4b/4c. Candidate table remains empty.
- Step 4a implemented and locally verified 2026-10-20. Added
  `app/ingest/tennis_elo.py`, 22 ingest cases, immutable cached input/manifests
  and an explicit dry-run default. Repository writes are one full-day batch.
  `--manifest` pins source bytes, identity-map digest, rating digest and the
  original computation time; changed mappings or ratings fail reproduction.
  Repeated stored days reuse the existing snapshot without a download.
- Parsing distinguishes malformed individual records (counted/excluded) from
  unverified source contracts (fatal). The provider's generic ATP level `A`
  also occurs in 24 Doha/Los Cabos qualifying rows in 2024, consistent with
  its documented Tour label. Two 2025 WTA events use `A`; the parser allows
  only their verified IDs: [Prague 250](https://www.itftennis.com/en/tournament/prague-250/cze/2025/w-w250-cze-2025-001/draws-and-results/)
  (`2025-1082`) and [United Cup](https://www.wtatennis.com/tournaments/2084/united-cup/2025)
  (`2025-2084`). Other unverified labels still stop. No coefficient or adoption
  rule was changed in response to these metadata checks.
- The first two dry runs stopped before writes on source-contract differences.
  The second exposed two `R128` rows in 2026's qualifying file. Metadata and
  normalized result facts exactly match the main-file rows, so they are counted
  once only when full agreement with an already-loaded main row is established.
  A standalone or contradictory main-draw row in a qualifying file remains
  fatal. Qualifying round eligibility was not broadened.
- Complete real dry run: 27 files, **75,003 raw rows**, **71,346 unique
  admitted matches**, **2,755 provider identities**. ATP: 16,079 unique,
  Challenger: 32,807, ATP qualifying: 7,576, WTA: 14,884. Two duplicate copies,
  636 malformed and 3,019 otherwise excluded records reconcile the totals.
  Notable coverage limitation: 489 ATP rows in `2025.csv` lack match numbers
  and are excluded, without inventing replacement keys.
- Identity gate: **1,498 provisional tracked candidates**, **1,151 unmapped
  provider identities**, **106 ambiguous identities across 54 conflicts**.
  Three raw IDs resolve to multiple local players (Diego Dedura variants,
  Gabriela Knutson variants and Xinyu Wang variants); the remaining conflicts
  involve multiple raw IDs resolving to one local player. Examples include
  ATP `I0A0`/`I0B0` for Andre Ilagan and WTA `200035`/`201533`/`311779` for
  Shuai Zhang. These observations identify cases to verify, not authority to
  merge identities. Details: `output/41b-step4-identity-samples.json` (ignored).
- The dry run correctly returned **BLOCKED, 0 inserted**. Manifest
  `8ce25f5bdd4328dcea85238bfc729a5d3fa0c469e8f12e0a8f1bfd40aacc37a7`
  is local at `api/data/tennismylife-elo/manifests/<hash>.json` (ignored).
  The real CLI `python -m app.ingest.tennis_elo --dry-run --manifest
  data/tennismylife-elo/manifests/<hash>.json` reproduced that exact manifest
  and blocking counts without downloading again. Expected exit code: 1 for
  the fail-closed identity gate. Logs: `output/41b-step4-dry-run.log` and
  `output/41b-step4-manifest-replay.log`.
- Replay used historical results only to reconstruct state, as the spec permits.
  No loss, calibration, ROI, fit, forward verdict or holdout-accuracy run was
  performed. Current snapshots remain unserved and no real candidate was stored.
- Step 4a tests: **22 new ingest cases**; full Verify
  `npm --prefix web run verify && cd api && python -m pytest`, API venv on PATH:
  **632 web tests, production build and 3,237 API tests passed**. One existing
  dependency deprecation warning. Log: `output/41b-step4-verify.log` (ignored).
- Owner approved the identity-normalization amendment via the short choice
  `Add an identity-normalization review step`. Step 4a's diff was approved via
  `Continue`; 4b is now in progress, without a checkpoint commit.
- Final read-only Neon check after both previews: **zero candidate rows**;
  legacy ELO still **14,853 rows**, digest
  `4084f05137d16a2a5be957af40675288`, matching Step 3. Evidence:
  `output/41b-step4-db-after.json` (ignored). No write approval was requested
  for a blocked manifest, and no checkpoint commit was made.
- Step 4b audit run 2026-10-20 over the cached 4a manifest, every provider
  identity including untracked opponents. Read-only: no code path reads the
  registry yet, no DB write, no replay output or accuracy computed.
- Cause of 51 of 54 conflicts: in 2026 TennisMyLife files some WTA players
  under WTA-official IDs (`3xxxxx`) instead of legacy `2xxxxx` IDs. Queen's
  Club and 's-Hertogenbosch 2026 are entirely official IDs; about fifteen other
  2026 events mix in a few. 73 official IDs appear in all.
- Exact-name groups: 52 (49 WTA renumbering, 3 WTA one-off/wrong IDs incl.
  `200035`, 2 ATP). Space/order-insensitive and surname passes found 7 hidden
  forks (Begu, Sherif, Burillo, Bulgaru, Rakotomanga Rajaonah, Ku, Ma) plus
  Hernandez-Aguila. 18 official IDs have no partner and stay standalone.
- Evidence: implied birth date from the provider's own `*_age` and
  `tourney_date` agrees within 1 day for every merged WTA group and
  Hernandez-Aguila; countries agree apart from recorded nationality switches.
  No pair ever shares an event or plays each other. Ten official WTA profiles
  matched. ATP profile pages render any slug, so they are not evidence. WTA
  `200035` officially belongs to another player; its Stuttgart 2026 R32 row is
  corroborated as Zhang Shuai by the local livetennis match.
- Draft registry (status: awaiting owner review):
  `api/app/ingest/data/tennis_elo_identities.csv` (60 rows: 59 verified,
  1 proposed, SHA-256 `11ca1191...7f04`), `tennis_elo_local_overrides.csv`
  (3 rows, `1ce959f2...4a5b`) and `README.md` with the evidence standard.
  Canonical ID = most admitted matches, then earliest provider date.
- Open for owner: ATP `I0A0` to `I0B0` (Ilagan) is proposed only. Porras
  `C0KH`/`P0IL` kept distinct (ARG vs ESP). Local Knutson 53141's stored birth
  date (1989) disagrees with the provider's (1997); recorded, not changed.
- Forward risk: the provider appears to be migrating WTA IDs, so later daily
  dry runs may hit new renumbering conflicts. They fail closed and need a
  registry review, versioned after activation.
- Artifacts (ignored): `output/41b-step4b-name-groups.json`,
  `output/41b-step4b-id-attributes.json`, `output/41b-step4b-audit-scripts/`.
- Owner replied `approved` to the draft registry. Applied as approval of the
  59 verified aliases and 3 verified local overrides only; the proposed Ilagan
  row was not marked approved without an explicit decision.
- Implemented normalization: pure `parse_identity_registry` and
  `normalize_identities` in `app/core/tennis_elo.py` (rejects chains,
  duplicates, cross-namespace keys, missing evidence; applies only verified
  rows; a merge creating a self-match is fatal). Ingest loads and hashes the
  registry, normalizes before deduplication (including the qualifying-file
  main-draw check), applies local overrides inside `map_players` with the
  one-to-one check intact, prints registry version/hash, and pins
  `identity_version`/`identity_sha256` in the manifest so a changed registry
  cannot reuse a reviewed manifest. The 4a manifest predates these fields
  and cannot be replayed with `--manifest`.
- Cached-source check (no download, no manifest, read-only index): 71,346
  unique matches before and after normalization (none lost or duplicated),
  provider identities 2,755 to 2,696; conflicts 54 to 7. Remaining: Ilagan
  and six new local forks exposed by the spelling-fork merges (Begu, Burillo,
  Bulgaru, Ma, Ku, Rakotomanga Rajaonah). Their overrides are drafted as
  `proposed`, chosen by the same livetennis-linked rule. An in-memory
  simulation applying all seven gives **0 conflicts, 1,546 linked**; it is not
  a registry state. Logs: `output/41b-step4b-cached-dry-run.log`,
  `output/41b-step4b-if-approved-simulation.log` (ignored).
- Tests: new `tests/test_tennis_elo_identities.py` (22 cases: shared
  identity across years, namespace isolation, unrelated namesakes, self-match,
  dedup of renumbered copies with conflicts still fatal, shuffled determinism,
  registry validation, overrides, manifest pinning, tracked registry parse).
  Full Verify passed: **632 web tests, build and 3,259 API tests**.
  Log: `output/41b-step4b-verify.log` (ignored).
- Forward verdicts: not started. GitHub runner acceptance: pending push and
  an authorized dispatch.

### Step 4b final review and Step 4c preview (2026-10-20)

- Owner delegated the seven remaining decisions with "Do what you think is
  best" after the pending rows and write boundary were explained. Accepted
  the six local overrides under the existing livetennis-linked rule. Local
  birth-date discrepancies remain documented, without changing app players.
- Strengthened Ilagan evidence before accepting `I0A0` to `I0B0`: the
  [official Washington qualifying draw](https://www.protennislive.com/posting/2026/418/qs.pdf)
  matches both cached results (Bertola 7-5 7-6(2) win, Giron 6-3 7-6(2)
  loss). ATP's indexed Washington result associates the Bertola match with
  `i0b0`; the live ATP page returned 403. This is a documented exception to
  the age-data rule, supported by actual results rather than profile slugs.
- Registry frozen before activation: `tennis-elo-identities-v1`, 60 verified
  aliases, 9 verified local overrides, no proposed rows. Registry SHA-256:
  `fc117e713fe5b5e64ade7dd5a383d0d3b70eae2287f8f2cdfb1cb442120610d0`.
- Reused all 27 hash-checked files from audited source manifest
  `8ce25f5bdd4328dcea85238bfc729a5d3fa0c469e8f12e0a8f1bfd40aacc37a7`,
  preserving their original download times. No provider download, result
  scoring, or database write. Preview uses the real CLI orchestration with
  only its downloader replaced by the audited cache loader, then replays the
  new manifest through the normal `--manifest` path.
- Final result: 71,346 unique matches, 2,695 provider identities, 1,546
  tracked candidates, 1,149 unmapped provider players, 0 ambiguous mappings,
  0 conflicts. All admitted matches retained. Family counts (files / rows /
  unique / duplicates / malformed / excluded):

  | Family | Files | Rows | Unique | Duplicates | Malformed | Excluded |
  |---|---:|---:|---:|---:|---:|---:|
  | ATP | 7 | 17,268 | 16,079 | 0 | 490 | 699 |
  | Challenger | 7 | 34,248 | 32,807 | 0 | 0 | 1,441 |
  | ATP qualifying | 6 | 7,803 | 7,576 | 2 | 0 | 225 |
  | WTA | 7 | 15,684 | 14,884 | 0 | 146 | 654 |

- Exact current-UTC-day preview: 2026-10-20, computed at
  `2026-10-20T21:26:53.646028+00:00`; manifest SHA-256
  `ea8a52b9cdc5137ece5d5b56dfdcfa9beaadaea7702097059d5ac7b1319e843a`.
  Both initial dry run and exact-manifest replay report `DRY RUN, 0 inserted`.
  The manifest lives under `api/data/tennismylife-elo/manifests/`.
- Read-only database proof: zero candidate rows, 14,853 legacy rows, legacy
  digest `4084f05137d16a2a5be957af40675288`, unchanged from Step 3/4a.
- Evidence (ignored): `output/41b-step4b-final-cached-dry-run.log`,
  `output/41b-step4c-manifest-replay.log`,
  `output/41b-step4b-final-db-after.json`, and the cache-only preview helper
  `output/41b-step4b-final-preview.py`.
- Final Verify ran with the API venv active: web typecheck, 632 web tests,
  production build, and 3,259 API tests passed. Existing large-bundle and
  AnyIO deprecation warnings remain. Log:
  `output/41b-step4b-final-verify.log`. The first sandboxed attempt could not
  load Vite's config; the rerun outside the sandbox ran all checks. PowerShell
  classified Vite's stderr warning as a native-command error in the wrapper;
  the log confirms the build completed and all subsequent API tests passed.
- Step 4c remains unchecked: write approval must name this exact manifest
  while it is still the current UTC day. After approval, capture legacy and
  local identity facts plus fixed-input public output before/after the first
  write; repeat the same manifest to prove zero inserted. No write, commit,
  push, deployment, or Step 5 work is authorized by this review.

### Step 4c UTC rollover and replacement preview

- Owner replied "continue" to the October 20 manifest write request. At
  execution time it was already `2026-10-21T01:26:30Z` (October 20 evening in
  Chicago). The approved manifest was no longer current-day, so no write
  was attempted and no clock/cutoff was overridden. Its approval is recorded
  but cannot be transferred to a new manifest without review.
- Ran the normal `python -m app.ingest.tennis_elo --dry-run`, downloading all
  27 required files with fresh provenance. New October 21 UTC manifest:
  `a960691dd9d651da4f80872e1386341934fba3e0dce56f6329f30ff9c35ac6a4`,
  computed at `2026-10-21T01:26:57.053108+00:00` (October 20, 8:26 p.m. CT).
  Normalization version/hash unchanged from the final Step 4b review.
- Replacement preview and normal `--dry-run --manifest` replay both pass:
  71,381 admitted unique matches, 2,696 provider identities, 1,547 tracked
  candidates, 1,149 unmapped, 0 ambiguous, 0 conflicts, 0 inserted. The new
  inputs/cutoff add 35 matches and one linked player versus October 20 UTC.

  | Family | Files | Rows | Unique | Duplicates | Malformed | Excluded |
  |---|---:|---:|---:|---:|---:|---:|
  | ATP | 7 | 17,275 | 16,095 | 0 | 490 | 690 |
  | Challenger | 7 | 34,268 | 32,826 | 0 | 0 | 1,442 |
  | ATP qualifying | 6 | 7,803 | 7,576 | 2 | 0 | 225 |
  | WTA | 7 | 15,684 | 14,884 | 0 | 146 | 654 |

- Read-only baseline at `2026-10-21T01:28:01Z`: 0 candidate rows; legacy
  ELO still 14,853 rows, digest `4084f05137d16a2a5be957af40675288`.
  Also saved complete-table fingerprints for 3,054 players and 124 aliases,
  and fixed-date ATP/WTA player-detail, latest-ELO and fixed-input ensemble
  values for the eventual before/after comparison.
- Evidence (ignored): `output/41b-step4c-20261021-dry-run.log`,
  `output/41b-step4c-20261021-replay.log`,
  `output/41b-step4c-20261021-before.json`, and read-only helper
  `output/41b-step4c-facts.py`. PowerShell again classified parser warnings
  on stderr as native-command errors; both complete reports end with
  `DRY RUN, 0 inserted`, no blocked identities or manifest mismatch.
- No product code changed; the passing Step 4b Verify evidence remains
  applicable. Step 4c write approval is pending for the replacement hash.

### Step 4c approved write and proof

- Owner explicitly replied "approved" to replacement manifest
  `a960691dd9d651da4f80872e1386341934fba3e0dce56f6329f30ff9c35ac6a4`.
  Execution began at `2026-10-21T01:29:03Z`, still its approved UTC day
  (October 20 evening in Chicago).
- Ran the normal CLI with `--write --manifest` for that exact hash. First
  write stored **1,547 candidate ratings**. Repeated the identical command:
  **0 inserted**, reused the immutable October 21 UTC snapshot. Both commands
  exited successfully. No source downloads or registry changes in this step.
- Read back all 1,547 rows using the explicit candidate source. Every stored
  payload, including roster, ratings, counts, provider/local IDs and
  provenance, equals a fresh reconstruction from the approved cached files.
  Both mapping and ratings hashes reproduce the reviewed manifest.
- Before/after full-table row counts and fingerprints match for `players`
  (3,054), `player_aliases` (124) and legacy `player_elo` (14,853). Legacy
  digest remains `4084f05137d16a2a5be957af40675288`.
- Fixed-date ATP/WTA player-detail output, latest legacy ELO batch and
  fixed-input ensemble results match exactly before/after; combined SHA-256
  `88eea86233f2b27081a8d21a66a99fa95a955158ccf047aeb0f6feae0c26e428`.
  This is sampled public-output parity plus complete legacy/identity-table
  parity, not a claim that every public endpoint was exercised.
- Evidence (ignored): `output/41b-step4c-20261021-write.log`,
  `output/41b-step4c-20261021-repeat.log`,
  `output/41b-step4c-20261021-before.json`,
  `output/41b-step4c-20261021-after.json`,
  `output/41b-step4c-20261021-proof.json`, and read-only verification helper
  `output/41b-step4c-verify-stored.py`.
- No product code changed. Step 4b's passing Verify remains applicable;
  Step 4c adds real database write/readback and idempotency evidence. No
  commit, merge, push, deployment, serving-source switch or shadow activation.
  Step 5 remains unchecked and is the next implementation review gate.

### Step 5a storage review (2026-10-20 CT / October 21 UTC)

- Owner continued after Step 4c. Split the original Step 5 into 5a storage
  and 5b forecast/CLI implementation to keep the migration review separate
  from predictor input changes. The parent scope, frozen rule and activation
  boundary are unchanged. Neither substep is checked off yet.
- Added revision `0047`, following `0046`. Creates only
  `tennis_elo_freeze_cycles` (experiment/cycle key, observation timestamp,
  immutable plan hash, JSONB coverage attempts) and `tennis_elo_comparisons`
  (unique experiment/match, cycle FK, oriented player IDs, group, kickoff,
  freeze time and copied JSONB forecast/input payload). Checks enforce group,
  time, identity and payload shapes. No cascading deletion of observations.
  Downgrade drops only these new tables, comparisons before cycles.
- Added `app/repositories/tennis_elo_comparison.py`. Frozen dataclasses
  validate market-row provenance and de-vigged probability, finite forecast
  probabilities/weights, incumbent ratings/dates/prior counts, current-day
  candidate ratings/provenance, common manifest, player orientation,
  namespace, minimum prior counts, timestamp ordering and fresh odds.
  Both forecasts reference one copied market; ELO reliability flags and
  quality flags remain stored independently for later gated-case reporting.
- Coverage stores every attempted match with its kickoff, group, incumbent
  eligibility, candidate availability and reason. Missing candidates remain
  in the eligible denominator. Every `paired` attempt requires one payload;
  incomplete or contradictory rosters fail before any DB call.
- `freeze_cycle` uses an experiment advisory lock and nested transaction.
  Exact cycle retries are no-ops even if input order changes; a changed
  plan under the same cycle fails. Later-cycle duplicates keep the first
  pair and are recorded as `already_frozen`. A server-clock check rejects
  late/future observations, including coverage-only eligible attempts.
  Before each insert, a shared row lock rechecks the match's player ordering,
  kickoff, scheduled status and absent winner/score. The insert also checks
  the server clock; any failure rolls back the entire new cycle and pairs.
  The caller owns commit; no production prediction or player/ELO writer is
  called. `get_frozen_match_ids` is explicitly experiment-scoped.
- New tests: `tests/test_tennis_elo_comparison_repository.py`, **49 cases**.
  Covers immutable cycles, first-pair-wins, full skip ledger, atomic failure,
  source/orientation/provenance, stale/future/post-start rejection, finite
  probabilities/weights, roster consistency and equivalent timezone display.
  These are synthetic unit tests, not shared-Postgres integration proof.
- Offline Alembic upgrade `0046:0047 --sql` and downgrade
  `0047:0046 --sql` both exit successfully. Inspected generated SQL:
  upgrade creates two tables plus the normal Alembic revision update;
  downgrade removes just those tables and restores the revision marker.
  Initial offline invocation from repo root failed to import `app`; rerunning
  from `api/`, the documented API command directory, passed.
- Full Verify, API venv active: **632 web tests**, web typecheck/build and
  **3,308 API tests** passed; command exit 0. Existing bundle-size and AnyIO
  deprecation warnings remain. Evidence (ignored):
  `output/41b-step5a-upgrade.sql`, `output/41b-step5a-downgrade.sql`,
  `output/41b-step5a-verify.log`, `output/41b-step5a-api-tests.log`.
- Pending approval: apply `0047` to the shared database, one Alembic command,
  then verify repository behavior with synthetic rows inside a transaction
  that is always rolled back. This does not authorize storing real forecast
  pairs or activating the experiment. Step 5b still owns input construction,
  exact baseline parity, the dry-run-first CLI, experiment/version pinning
  and a separately approved real pre-match freeze. No predictor changes,
  real pair writes, activation, commit, push, scheduling or deployment here.

### Step 5a approved application and Step 5b implementation

- Owner replied "approve and continue" to applying `0047` plus the
  rollback-only storage proof. Applied exactly `alembic ... upgrade 0047`
  as one command. Revision is now `0047`. No earlier migration was edited.
- Approved live proof passed: first synthetic pair inserted once, same-cycle
  retry inserted zero, changed-cycle payload rejected, later-cycle duplicate
  kept the original pair. Fingerprints of `players`, `player_aliases`,
  `player_elo`, `predictions` and `tennis_elo_snapshots` remained identical.
  Always rolled back the enclosing transaction; both shadow tables are empty.
  Repeated the rollback-only proof after the final payload changes, including
  actual signed fitted coefficients. No actual forecast observation or
  experiment activation was persisted. Evidence:
  `output/41b-step5a-live-migration.log`,
  `output/41b-step5a-live-proof.json`, `output/41b-step5a-live-probe.py`.
- Extracted the existing batch prefetch into `PredictionBatch` and
  `load_prediction_batch` in the predictor. The slate and match page still
  call the same `_build_prediction`; inference remains in a worker thread.
  Added an optional clock only for controlled shadow staleness checks.
  Batched odds now include the selected row's ID, without changing ordering
  by recency then existing book priority.
- New shadow service reuses that baseline and its single copied market/ML
  result. Candidate replaces only the raw ELO input, using both surface
  ratings when available or both overall ratings otherwise. Each source
  gets the existing reliability gate using its own prior counts; gap-gated
  forecasts stay paired as market-only results. Candidate quality flags
  retain common feature/ML flags and recompute only ELO-dependent flags.
- Eligibility rejects started/live/resulted matches, missing/naive kickoff,
  qualifying/exhibition/ITF labels, ambiguous player namespaces and WTA 125,
  absent/future/stale odds, invalid incumbent ratings or fewer than ten
  prior matches. A completed source result matching the target's canonical
  participants, round, tournament and provider-date window also excludes it
  when the local status lags. Missing/invalid candidate inputs remain in
  the otherwise-incumbent-eligible coverage denominator.
- New dry-run-first `app.ingest.tennis_elo_comparison` verifies the complete
  persisted daily roster against the cached manifest's mapping and ratings
  hashes, registry pin, timestamps and every cached file hash. Missing,
  partial or changed daily input permits no pairs. It records local preview
  artifacts and prints counts/reasons only. `--write` requires explicitly
  reviewed activation and its first full UTC day; it never activates itself.
  An existing cycle reuses its immutable ledger before loading live inputs.
- Added tracked `tennis_elo_experiment.json`, currently **inactive**. Pins:
  identity registry `fc117e71...10610d0`; coefficients `8cd48afb...45185`;
  gates `36dfa049...8cb97`; incumbent versions `ensemble-v3+lgbm-v6` for
  ATP/WTA, `ensemble-v3+lgbm-none` for Challenger. Inactive config SHA-256:
  `8d112cfafedfd9598656dd85f5e7b52a7da6682d4407f81e6da3477fa0dd3985`.
  Real pairs copy activation, eligible date and config hash; coverage attempts
  also pin the config before any successful pair. Cross-cycle pin changes
  fail under the experiment lock. Empty cycles contain no eligible sample.
- Corrected Step 5a's overly strict nonnegative-weight validation: 26d's
  frozen ATP/WTA ELO coefficients are negative by design. Preserve finite
  signed coefficients unchanged; forecasts remain bounded probabilities.
  Allow group-specific incumbent model versions in one shared freeze cycle.
  These changes are covered by unit tests and the repeated live rollback
  probe; the applied schema needed no change.
- Synthetic tests: **100 cases** across comparison service, repository and
  CLI, plus the selected-odds-row provenance test. Covers serving-path
  parity, p1/p2 reversal, surface fallback, independent gap gates, namespace
  exclusions, exact staleness boundary, missing-source coverage, complete
  roster/hash validation, immutable retries, pinned-version continuity,
  inactive-write rejection, UTC start/rollover and atomic failure.
- Read-only real-input parity against the saved pre-extraction predictor:
  **all output fields equal for 40 upcoming matches** using the same batch.
  Production table fingerprints unchanged and both shadow tables empty.
  Evidence: `output/41b-step5b-serving-parity.json`,
  `output/41b-step5b-serving-parity.py` and `output/41b-step5b-baseline/`.
- Final real dry run: **40 attempts, 22 incumbent eligible, 22 candidate
  available, 22 ready preview pairs, 0 storable pairs, 0 inserted**. Excluded:
  2 missing incumbent, 6 missing market, 6 qualifying, 4 stale market. The
  experiment is inactive, so ready previews are not forward observations.
  Plan SHA-256:
  `a34df594ca6f16918e4d9be1e079b05226e86d0a0ea11e34e98ab0700f4cdfbc`.
  Evidence: `output/41b-step5b-final-dry-run.log` and the immutable plan under
  `api/data/tennismylife-elo/comparisons/`.
- Full Verify passed with exit 0: **632 web tests**, web typecheck/build,
  **3,360 API tests**. Evidence: `output/41b-step5b-verify.log`.
- Step 5b stays unchecked pending review and separately approved activation
  plus real pre-match freeze/readback proof on an eligible UTC day. If
  activation occurs on October 21 UTC, the first eligible day is October 22
  UTC (October 21 at 7 p.m. CT). A fresh complete candidate snapshot is
  required for that day. No clock override or early observation is permitted.
  No scoring, serving-source change, schedule change, commit, push or deploy.
  Step 6's report implementation is independent work available after this
  code review while waiting for the first eligible real freeze.
- Updated the ignored local employer guide with the implemented candidate
  storage, identity review and parity example, explicitly distinguishing
  inactive engineering previews from real forward evidence. Guide remains
  local and unstaged; no adoption or deployment claim was added.

### Step 6 count-only and locked report review

- Owner continued after Step 5b's code review. Implemented Step 6 while
  leaving activation and Step 5b's first real pre-match proof pending.
- New pure `app/core/tennis_elo_report.py` encodes source/group/version
  isolation, original and revised kickoff checks, UTC maturity, earliest
  resolved-prefix sample selection, unique-match coverage and the two
  2.5-SE non-inferiority gates with the fixed 0.005 inclusive margin and
  90% coverage floor. Count mode produces counts, never interim accuracy or
  loss numbers. Gate-to-market pairs stay in the sample.
- New `app/repositories/tennis_elo_report.py` separates outcome-free frozen
  payload/metadata/coverage reads from `get_report_results`, whose query is
  explicitly bounded to mature frozen IDs for the selected group. Stored
  payloads round-trip through Step 5's validated dataclasses; inconsistent
  columns or malformed provenance are reported and block actual scoring.
- New `app/backtest/tennis_elo.py`: default/`--count` prints all three groups;
  optional `--group` narrows counts. Only explicit `--score --group` may
  fetch result observations, and only after the potential count/day floors.
  Inactive, immature, under-floor or unresolved cohorts produce accruing
  counts without invoking loss functions. No real score command was run.
- Per-group sample/report artifacts live under the already ignored
  `api/data/tennismylife-elo/reports/tennis-elo-source-v1/`. Samples are
  written exclusively before computing any loss. Each artifact carries a
  verified content digest plus experiment/rule/input hashes. A process file
  lock prevents concurrent scoring; exact saved reports are reused without
  a DB query or new test. A crash after sample lock resumes only from that
  snapshot. Corruption, missing sample or changed pins/rule require review.
- Only the locked sample computes component log loss/Brier, the paired G1/G2
  differences, fixed calibration bins, raw-ELO context and surface/gated
  counts. These context metrics introduce no extra adoption test or candidate.
- Added **77 synthetic cases** across `tests/test_tennis_elo_report.py`,
  `tests/test_tennis_elo_report_repository.py` and
  `tests/test_tennis_elo_report_cli.py`. Covers every exclusion, exact sample,
  day, maturity, margin and coverage boundaries; full-day inclusion above
  300; unresolved early versus later cohorts; both kickoff clocks; groups,
  sources and model pins; repeated attempts and recovered availability;
  voids/retirements; p1 orientation; outcome-free counts; immutable samples,
  crash recovery, tampering and concurrent-score lock release.
- Full Verify passed, exit 0: **632 web tests**, web typecheck/build and
  **3,437 API tests**. Existing large-bundle/AnyIO warnings remain.
  Evidence: `output/41b-step6-verify.log`.
- Real `python -m app.backtest.tennis_elo --count` passed: ATP, WTA and
  ATP_CHALLENGER all **accruing**, each with **0 frozen pairs, 0 mature
  pairs/days, 0/0 eligible coverage attempts**. Activation is still pending;
  no scored numbers or actual adoption verdict exists. Evidence:
  `output/41b-step6-real-count.log`.
- Independent real count-path instrumentation observed **3 SQL statements**,
  with no winner/score column read and no database mutation. Replaced outcome
  loading, result resolution and loss functions with fail-if-called guards;
  none were invoked. Report artifacts were unchanged. Evidence:
  `output/41b-step6-real-count-proof.json`,
  `output/41b-step6-count-proof.py` (both ignored).
- Updated the ignored local employer guide to describe the implemented
  report and synthetic lock/maturity tests, while retaining inactive/accruing
  status, zero real scored cases and pending scheduling. The guide remains
  local and unstaged.
- Owner approved Step 6 and continued with Step 7 ("continue and approve").
  Step 5b's real activation/freeze proof remains pending; this approval does
  not manufacture a forward sample or authorize a once-only score.
  No activation, real score, serving change, commit, merge, push or deploy.

## Draft critique and changes

- Replaced an unsafe second source in `player_elo` with additive storage, so
  source-blind readers and admin overrides keep their existing behavior.
- Removed tracked-player-only and stats-required replay shortcuts; they would
  distort the opponent network.
- Separated deterministic date ordering from proof of actual played dates.
  Existing source docs do not justify retrospective as-of accuracy claims.
- Replaced reused 2026 outcomes with new pre-match frozen pairs and pinned
  versions. Defined count-only accrual and once-only mature sample selection.
- Defined coverage attempts as well as successful pairs, fixed non-inferiority
  margins, and restricted a possible pass to supported market-priced groups.
- Split storage, data writes, freezing and reporting into separate reviewable
  steps; completion can remain accruing without starting 41c.


### Step 7 scheduling and final proof review

- Owner approved Step 6 and continued with Step 7. No checkpoint commit,
  merge, push, workflow dispatch, real activation or real scoring was performed.
- Added two dependent jobs to `.github/workflows/tennis-ingest.yml`:
  candidate refresh follows the existing 11:00 UTC TennisMyLife job;
  shadow freeze follows the complete existing 13:30 UTC prediction job,
  including prop snapshots. Separate dispatch choices run each new job alone.
  Structural comparison against HEAD confirms all six existing jobs, schedules
  and global environment are unchanged (`output/41b-step7-workflow-proof.json`).
- Each new job has its own non-cancelling concurrency group, 30-minute timeout
  and contents-read permission. Existing repository advisory locks, atomic
  batches, first-pair-wins and immutable cycle retries remain authoritative
  across local and runner invocations.
- Separate runners restore an exact UTC-day/implementation/identity-keyed
  Actions cache of original files/manifests only, without previous-day restore
  fallbacks. Refresh shares it only after the new read-only `--check-snapshot`
  validates the full database roster and original source hashes, plus a final
  UTC-day check. Missing original cache cannot be rebuilt by substituting
  fresh upstream files for a stored immutable daily roster; that day's refresh
  fails validation and the shadow path freezes no pairs. Next-day refresh
  can recover. No report locks or comparison plans enter the runner cache.
- New `--scheduled` mode skips inactive experiments or their partial first
  UTC day cleanly without a database connection. After reviewed activation it
  uses the same guarded write path as `--write`. Invalid/missing current-day
  candidate inputs print a freeze-skip reason and retain eligible attempts
  for coverage, without creating any pairs. Explicit manual `--write` still
  rejects inactive/too-early writes. No job activates or scores an experiment.
- Seven new focused tests cover scheduled inactive/partial-day skips, active
  cache-miss coverage, fresh-runner cache transfer, missing files, partial
  rosters and UTC rollover. All 21 comparison-ingest tests pass.
- Documented all new commands in `AGENTS.md`, and cache loss/recovery plus
  preservation of once-only report artifacts in the registry README. Report
  locks coordinate one machine; moving machines requires preserving those
  artifacts, and independent scoring on fresh runners is prohibited.
- Invariants review of tracked and new feature files found report transaction
  SQL in the CLI. Returned to implementation and moved it into the report
  repository; the 19 CLI/repository tests still pass. Final review has no
  remaining invariant findings: pure core, repository-owned SQL, candidate
  source isolated, serving coefficients/model versions untouched, no holdout
  scoring/refit, no frontend signal changes and no heavy request-path report.
- Final exact Verify gate passed, exit 0:
  `npm --prefix web run verify && cd api && python -m pytest`, with the API
  venv activated. 48 web files / 632 tests, TypeScript and production build;
  3,444 API tests, one existing Starlette deprecation warning. Full output:
  `output/41b-step7-verify.log`. `git diff --check` passes.
- Real read-only `--check-snapshot` verified all 1,547 current-UTC-day
  (2026-10-21) players and original cached files. Real shadow dry run saw
  55 attempts, 33 incumbent-eligible, 31 candidate-available/ready previews,
  zero storable pairs and zero inserts while inactive. Snapshot and preview
  output: `output/41b-step7-snapshot-check.log` and
  `output/41b-step7-preview.log`. Preview counts are readiness, not observations.
- Repeated current-input serving parity against the saved pre-extraction
  predictor at 2026-10-21 02:22 UTC: all output fields match for 55 matches.
  Existing production table fingerprints still match the earlier baseline;
  both shadow tables remain empty. Evidence:
  `output/41b-step7-serving-parity.log` (underlying probe updates
  `output/41b-step5b-serving-parity.json`). Immutable-freeze proof remains the
  previously approved rolled-back synthetic storage probe at
  `output/41b-step5a-live-proof.json`; this is not a real forward freeze.
- Repeated the guarded real count-only probe after the repository change:
  three read-only SQL statements, no winner/score columns read, no outcome
  loader or loss function called, no database mutations and no report artifact
  changes. All three groups say accruing with zero frozen/mature cases.
  Evidence: `output/41b-step7-count-proof.log` and the refreshed
  `output/41b-step6-real-count-proof.json`. No real `--score` was run.
- Updated the ignored local employer interview guide with scheduling,
  cache-loss behavior and explicit inactive/runner-pending boundaries.
- Ledger still has F-09 (P3, unverified) and F-12 (P2, unverified), outside
  this feature. No open/fixed P0 or P1 blocks the engineering handoff.
- Step 7 is ready for owner review and remains unchecked until approved.
  Runner acceptance is PENDING an approved push and dispatch, as permitted
  by this step's done-when. Step 5b remains unchecked: a separately reviewed
  activation timestamp, next-full-UTC-day real pre-match freeze and immutable
  retry proof are still required. The inactive config is unchanged. Do not
  claim an accruing real sample, deployment, adoption or validated accuracy.


### Step 7 approval and shadow activation

- Owner replied "continue and approve" after the Step 7 review packet. Marked
  Step 7 approved. Runner acceptance remains pending an approved push/dispatch;
  this approval does not push, merge, deploy or dispatch anything remotely.
- Continued the remaining Step 5b local activation work under this approval.
  Verified the pinned registry, model versions, gates and coefficients against
  runtime before recording actual activation time `2026-10-21T02:25:51.864941+00:00`.
  No pin, formula, gate, identity or adoption rule changed.
- First eligible full UTC day: **2026-10-22**, starting at
  00:00 UTC (2026-10-21 19:00 America/Chicago). The real clock is still October
  21 UTC. Do not backdate activation or advance the clock to manufacture cases.
- Activated config SHA-256: `bdab3a645c923bef5742a1ff179504a342462afe7f023d6319ccc8814633e2a5`.
  Prior inactive SHA-256: `8d112cfafedfd9598656dd85f5e7b52a7da6682d4407f81e6da3477fa0dd3985`.
  Activation evidence: `output/41b-activation.json`.
- The actual `--scheduled` command skipped this partial first day cleanly.
  Explicit `--write` returned the expected activation/full-day guard failure
  before opening a database session (`output/41b-activation-early-write-guard.log`).
  No shadow or production database rows were written by activation verification.
- Real dry run accepted the new pinned config and found 55 attempts but zero
  eligible/storable pairs: 33 otherwise-eligible matches were explicitly
  excluded as `before_experiment_start`. No earlier preview becomes a forward
  observation. Evidence: `output/41b-activation-preview.log`.
- Real count-only report shows first eligible UTC date October 22 and zero
  frozen/mature cases in all three groups, with no outcomes or losses inspected
  (`output/41b-activation-count.log`).
- Exact Verify passed again, exit 0: 632 web tests, TypeScript/build, 3,444 API
  tests and the existing Starlette deprecation warning. Full output:
  `output/41b-activation-verify.log`.
- Updated registry documentation and the ignored employer guide to distinguish
  recorded activation from actual accrual. No scoring or serving switch.
- Step 5b remains unchecked solely because the first eligible full UTC day has
  not begun. The existing approval covers continuing the local daily candidate
  refresh and real pre-match freeze after that boundary, with the same frozen
  pins and safeguards; do not ask for the same authorization again. Prepare
  fresh current-day inputs, verify source completeness, execute the real freeze
  and exact-cycle retry, then record timestamps and production isolation.
  `output/41b-first-freeze-handoff.md` records the continuation procedure.


## Completion boundary and remaining operational acceptance

The owner requested "ok compelet" after discussing committing/merging the
reviewed code to prepare GitHub automation, with the first eligible UTC day
and pending real freeze explicitly disclosed. This completes the engineering
work before that time boundary. The original Step 5b real-freeze acceptance
criterion moves to the post-completion checklist below; it is not passed or
waived as evidence. The Step 5b check above describes the implemented/tested
code only. No data, timing, statistical rule or serving boundary changes.

Final safety pass: feature branch matches master at its base, all changed/new
files belong to 41b, all implementation reviews are approved, the exact Verify
command passed again (632 web tests, TypeScript/build, 3,444 API tests, exit 0;
`output/41b-complete-verify.log`), previous invariants/behavioral proofs remain
applicable, and F-09/P3 plus F-12/P2 remain unverified leads in the ledger.
No blocking open/fixed P0 or P1, no adapter changes requiring synchronization,
and no consumed prototypes. The ignored employer guide remains local.

- [ ] At or after 2026-10-22T00:00:00Z, refresh and validate that UTC day's
  complete candidate roster and original inputs. If unavailable, skip paired
  freezing and retain coverage attempts. Never reuse October 21 as October 22.
- [ ] Perform the already-approved first local real pre-match freeze, inspect
  stored provenance/config/timing, repeat the exact cycle with zero inserts,
  and compare production fingerprints and fixed-input serving output.
  There are zero real frozen pairs at completion; the synthetic rolled-back
  probe is engineering evidence only. Procedure:
  `python -m app.ingest.tennis_elo --dry-run`, then `--write`, comparison
  `--check-snapshot`, `--dry-run`, then approved `--write --cycle <aware-time>`
  and exact retry, followed by `python -m app.backtest.tennis_elo --count`.
- [ ] After separately approved push, dispatch the refresh/shadow workflows
  and verify original-input cache transfer, timestamps, skips and idempotency
  on GitHub runners. Workflow ordering has local structural proof only.

The conditional serving item 41c is not eligible for adoption yet. All three
report groups remain accruing with zero mature observations; no real outcomes
were evaluated and no once-only score was authorized. Local activation is
2026-10-21T02:25:51.864941+00:00, first eligible UTC day 2026-10-22, config hash
`bdab3a645c923bef5742a1ff179504a342462afe7f023d6319ccc8814633e2a5`.
Preserve the original cache and once-only report artifacts across machines.

# Feature: Frozen NHL predictions

**From build-plan:** feature 56c4 (fourth and last of 56c; 56d grades what this freezes)
**Branch:** `feature/nhl-frozen-predictions` (cut from `master` at `93b0cf6e`)
**Status:** complete (2026-11-05)

## Goal

Keep a record of what the gray NHL reference projection and P(over) said about each PrizePicks line before puck drop, so 56d's forward ranking check has a sample it can grade. `NhlPropSource` becomes a full `SportPropSource` (freezing and grading inputs), joins `PROP_SOURCES`, and `nhl-prop-lines.yml` freezes predictions after every line snapshot.

**Why now:** the sample only exists from the day freezing starts. Lines for 2026-10-23 onward are stored (43k rows over 13 days) but were never frozen; each week without the workflow is a week 56d cannot count.

## Sizing

One feature, seven build steps, the same shape as 20g3 (NBA) which shipped as one. No build-plan split. The grading queries are not deferrable to 56d: a source cannot join `PROP_SOURCES` without `frozen_lines`, `finished_periods` and `frozen_coverage`.

## In scope

- **Freeze what the pages serve.** The core value `NhlLineProjection` from `project_line` (full precision `projection`, `p_over`, `p_under`, `over_probability_version`, `flags`), not the 4-decimal wire value. Freezing and the three NHL endpoints share one projection path (Step 2) so they cannot drift.
- **Which lines.** Each linked, full-game PrizePicks line of an NHL `REG` game in the current regular-season week, at its latest snapshot before puck drop, across all 12 line-only markets and every odds type (standard, demon, goblin) and rung.
- **Gated lines freeze with a null projection.** A goalie not confirmed or expected, a player listed out, a thin sample, a non-center faceoff line: the row is stored with `projection` NULL and the flag, never skipped. This keeps the coverage denominator honest and records exactly what was knowable.
- **Hidden markets freeze no probability.** Goalie Saves, Hits and the other seven markets outside `SHOWN_MARKETS` freeze a projection (when not gated) with `p_over`, `p_under` and `over_probability_version` all NULL. A whole-number line in a shown market freezes `p_over` NULL with version `nhl-pover-v1` and flag `integer_line`, as the core returns it.
- **Context as of the freeze moment.** Goalie and injury context is read with `as_of = now` through the same `load_contexts` the board uses. It is stored context only; no new fetching.
- **`NhlPropSource`**: `model_version` (`nhl-reference-v1`), `over_probability_version` (`nhl-pover-v1`), `current_period`, `freezable_games`, `frozen_lines`, `finished_periods`, `frozen_coverage`; joins `PROP_SOURCES` as `"nhl"`.
- **Grading inputs** (used by 56d, built here because the protocol needs them): settlement against `nhl_skater_game_stats` and `nhl_goalie_game_stats`.
- **Entry point and workflow.** `python -m app.ingest.nhl_prop_predictions [--dry-run]` (thin, like NBA's), and a "Freeze pre-puck-drop predictions" step added to the existing `nhl-prop-lines.yml` after the snapshot step.

## Out of scope

- 56d: the forward ranking check, `/nhl/model`, the home record card, any slice verdict, any calibration read by odds type (F-12 territory).
- Any new fit, any change to `nhl_over_probability_fit.py`, the projection arms or the gate rules, the pre-registered constants.
- Edge, ranking or pick wording, color, or any web change. Frozen rows are not shown anywhere yet.
- Reading any 2025-26 or 2026-27 **outcome**. Settlement SQL is written and tested on fixtures; nothing is run that scores frozen rows against box scores here (the one real-database read of box scores is limited to counting rows, see Step 7).
- Postseason (`PST`) lines: `PST` games have `week` NULL and the shared pipeline's period is an integer, so they are never frozen or graded. A later item decides.
- Schema changes (none needed, see Data / contracts), the F-14 board cache, F-17/F-18 repairs.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Frozen row builder and settlement (pure)** - `app/core/nhl_prop_predictions.py`:
  - `NhlFreezeLine` (line id, game id, game date, start_utc, player id, team, provider position, market, odds type, line, fetched_at).
  - `prediction_row(line, projection, now) -> PropPredictionRow`: copies the `NhlLineProjection` field for field; `edge` None; `quality_flags` = the projection's flags; `feature_snapshot` = `games_in_sample`, `prior_toi_minutes`, `gap`, `line`, `odds_type`, `market`, `segment` (`full_game`), `line_fetched_at`.
  - `settle_frozen(market, line, skater_row, goalie_row, game_has_box_scores) -> str`: no box-score rows for the game at all -> `stats_not_loaded`; a skater market with no skater row -> `void_dnp`; a goalie market with no goalie row or `started` false -> `void_dnp` (the projection already treats a goalie's non-starts as not played); a row whose market value is None -> `missing_stat`; else `prop_settlement.settle(value, line)` using `nhl_stat_value` (the one settlement rule; Time On Ice in minutes).
  *Done when:* `tests/test_nhl_prop_predictions.py` (own fixtures, importing no other test module, F-17) passes, covering a shown-market line with P(over) (`nhl-pover-v1`, full-precision `p_over` and `p_under` equal to the core's, not rounded), a hidden-market line (all three probability fields NULL, version NULL), a whole-number shown-market line (`p_over` NULL, version set, `integer_line`), a gated goalie line (projection NULL, flag kept, `games_in_sample` kept), one line per odds type keeping its `odds_type` in the snapshot, and each settlement branch including TOI minutes, a goalie who did not start, a push, and a loaded game with the player absent.

- [x] **Step 2 - One projection path for serving and freezing** - in `app/services/nhl/projections.py`, split the body of `line_projection` into a function that returns the core `NhlLineProjection` (history position wins over the provider's, availability from the stored context) and have `line_projection` call it and only round and shape. The freeze builder calls the same function. *Done when:* a test builds one line both ways and shows `line_projection(...)` equals the schema made from the frozen core value (value, gap, `p_over` rounded to 4 decimals, flags), and the existing 56c1/56c3 service tests pass unchanged, so wire output is provably identical.

- [x] **Step 3 - Freeze queries** - in `app/repositories/nhl.py`:
  - `get_current_week(db, now)`: `(season, week)` of the next `REG` game with `start_utc > now`, else the latest loaded `REG` week, else None.
  - `get_week_freeze_lines(db, season, week)`: the board's line rule (`_latest_props`: provider `prizepicks`, `segment = 'full_game'`, `provider_prop_id` not null, market in `NhlLineOnlyMarket`, `fetched_at < start_utc`, latest per prop) restricted to `game_type = 'REG'` and the week, every `sport_*` reference on `'nhl'`, returning the Step 1 line type plus the player's provider position and `raw_json ->> 'player_team'`.
  - `get_week_games(db, season, week)`: the week's `REG` game rows in the shape `slate_games` takes, so contexts load with `load_contexts`.
  *Done when:* recorded-SQL tests (the `_RecordingSession` pattern in `tests/test_nba_repository.py`) show the `'nhl'` filters, `game_type = 'REG'`, the week filter, `segment = 'full_game'`, the market list, and the pre-start condition; a mapping test turns a fake row into the expected `NhlFreezeLine`.

- [x] **Step 4 - Week freeze service** - `app/services/nhl/prop_predictions.py`: `week_freezable_games(db, season, week, now)` reads the week's lines and games, loads prior history once per distinct game date (`get_prior_history`, as the board does, one date per call so a player's two games in a week each read only earlier games), loads contexts once with `as_of = now` (a context storage failure degrades to no context, so goalie lines freeze null with `no_goalie_report`, never a crash), projects each line through Step 2, and groups rows by game into `FreezableGame`. *Done when:* service tests with fake repository data show a started game skipped by `freeze_rows` and an upcoming one frozen; a player with two games in the week gets history from before each game's own date; a context read that fails freezes goalie lines null and skater lines without a gate; a frozen row equals what the board service returns for the same fake line (shown number, gap, flags).

- [x] **Step 5 - Grading queries** - in `app/repositories/nhl.py`:
  - `get_frozen_gradeable_lines(db, season) -> list[FrozenLine]`: each provider prop's latest frozen pre-puck-drop row (`l.fetched_at < g.start_utc AND p.generated_at < g.start_utc`) on a completed `REG` game, joined to the player's skater or goalie row and a per-game "has box scores" flag (either table), settled by Step 1. Same `DISTINCT ON` order as NBA's.
  - `get_finished_weeks(db, season)`: weeks whose every `REG` game is `completed`, `postponed` or `canceled` **and** whose every completed `REG` game has box-score rows, so a week never counts before its stats load (the half of the rule F-10 found untested on NFL).
  - `get_frozen_coverage(db, season)`: per week, (gradeable full-game lines on completed `REG` games, how many have any frozen pre-start row).
  *Done when:* recorded-SQL tests pin the `'nhl'` filters, `game_type = 'REG'`, the market filter (the loader is the F-15 gap on NFL), both pre-start conditions (F-11/F-13), `status = 'completed'`, and the stats-loaded half of the finished-week rule; a mapping test turns a fake skater row, a fake goalie row and a not-loaded game into the expected `FrozenLine` outcomes.

- [x] **Step 6 - `NhlPropSource` joins the registry** - `app/services/nhl/prop_source.py` gains `model_version` (`NHL_PROJECTION_REFERENCE_VERSION`), `over_probability_version` (`fit.OVER_PROBABILITY_VERSION`) and the five methods delegating to Steps 3 to 5; `PROP_SOURCES` gets `"nhl": NhlPropSource`. *Done when:* `prop_source("nhl")` returns it with `("nhl-reference-v1", "nhl-pover-v1")`; `test_sport_registry.py` is updated (known list now `['nba', 'nfl', 'nhl']`); a test pins that the source's `over_probability_version` equals `served_over_probability_version()` so a fit/projection mismatch fails loudly; `test_sport_props_pipeline.py` still passes (shared modules never import `sport_registry` or sport code); full API `pytest` passes.

- [x] **Step 7 - Freeze CLI, workflow and first run** - `app/ingest/nhl_prop_predictions.py` (thin: `main("nhl")`, `--dry-run`, summary label `NHL`, period label "week" from `NHL_PROPS.period_label`); add the "Freeze pre-puck-drop predictions" step to `nhl-prop-lines.yml` after the snapshot step and extend its header comment; add the command to `AGENTS.md` and `docs/commands.md` (one line each, per the Ingest convention). *Done when:*
  - `python -m app.ingest.nhl_prop_predictions --dry-run` reports `2026 week N` for the stored lines with `frozen`, per-skip counts and `with_p_over_*` counts for the four shown markets only (a read-only transaction; no write).
  - After a separate yes in chat for the write: a real run inserts rows, an immediate re-run inserts 0, `sport_prop_predictions` rows for `sport = 'nhl'` carry the expected version columns and no `p_over` for a hidden market (a read-only count query).
  - `load_ranking_calls(db, prop_source("nhl"), 2026)` runs against the database without error; because no 2026-27 frozen line has a settled outcome this run reads, it is checked only for "runs and reports `stats_not_loaded` or an empty sample", and the row counts read from box scores are counts only, never a comparison of a frozen value with a result.
  - The workflow YAML parses and the new step follows the snapshot step with no `continue-on-error`.

- [x] **Step 8 - Verify and guide** - run the Verify command (`npm --prefix web run verify && cd api && python -m pytest`); update the local, untracked `docs/SportApp-Employer-Interview-Guide.md` if present (NHL predictions now frozen before puck drop, gray, ungraded, and exactly what a frozen row records), or say it is absent in the summary. *Done when:* Verify passes and the summary names the guide update.

## Files / areas

- New: `api/app/core/nhl_prop_predictions.py`, `api/app/services/nhl/prop_predictions.py`, `api/app/ingest/nhl_prop_predictions.py`, `api/tests/test_nhl_prop_predictions.py`, `api/tests/test_nhl_prop_freeze_service.py`
- Changed: `api/app/repositories/nhl.py`, `api/app/services/nhl/projections.py`, `api/app/services/nhl/prop_source.py`, `api/app/services/sport_registry.py`, `.github/workflows/nhl-prop-lines.yml`, `api/tests/test_sport_registry.py`, the NHL repository test module, `AGENTS.md`, `docs/commands.md`
- Read only: `api/app/core/nhl_projection.py`, `api/app/core/nhl_over_probability_fit.py` (generated, never edited), `api/app/core/nhl_projection_backtest.py` (pre-registered, never edited), `api/app/services/prop_predictions.py`, `api/app/ingest/prop_predictions.py`, `api/app/repositories/sport_props.py`, and NBA's `prop_source.py`, `prop_predictions.py` and repository queries as the template
- Untouched: web, routers, schemas, migrations, `nfl-*` and `nba-*` workflows

## Data / contracts

**No migration.** Checked: `sport_prop_predictions` has no `sport` CHECK constraint (migrations 0037, 0039, 0040 renamed the NFL table to the shared one; the only sport-scoped constraint, `ck_sport_games_nfl_week`, is on `sport_games` and applies to NFL alone). The unique index is `(prop_line_id, model_version, over_probability_version) NULLS NOT DISTINCT`, already carrying NBA and NFL rows (148k and 104k). So nothing is applied manually against the shared Neon database; the first write is the freeze CLI's own `INSERT ... ON CONFLICT DO NOTHING`.

**Load-bearing for 56d:**
- **NHL frozen row:** `sport = 'nhl'`; `model_version` `nhl-reference-v1`; `over_probability_version` `nhl-pover-v1` when the market is shown (even if this line reads no probability: whole-number line), else NULL; `projection`, `p_over`, `p_under` nullable and full precision; `edge` always NULL; `quality_flags` = `NhlProjectionFlag` values; `feature_snapshot` = `{games_in_sample, prior_toi_minutes, gap, line, odds_type, market, segment: 'full_game', line_fetched_at}`.
- **Period:** the regular-season `sport_games.week` (Monday to Sunday by game date, week 1 holds opening night); current period is the week of the next `REG` game not yet started.
- **Settlement outcomes:** `over`, `under`, `push`, `void_dnp`, `missing_stat`, `stats_not_loaded`; only `over` and `under` become calls.
- **Finished week:** every `REG` game completed/postponed/canceled and every completed one has box scores.
- **One row per snapshot per version.** Every snapshot run inserts fresh `sport_prop_lines` rows (no dedupe), so each run freezes new line ids against the context at that moment. If the same line id is re-frozen after its context changed such that the version column flips (NULL to set or back), a second row is stored; the graded row is the latest with `generated_at` before puck drop, so a later row never reflects the game.

## How the freeze runs, and what proves it (hosted API note)

The freeze runs in GitHub Actions straight against the database (`DATABASE_URL` secret), exactly like the other NHL and NBA workflows. **It never calls the hosted API**, so the suspended `sportapp-api.onrender.com` (`x-render-routing: suspend-by-user`, 2026-11-05) cannot block it and no step here assumes the API is up. Proof is therefore database-side only: the local dry run, the real run with an idempotent re-run, read-only count queries, and (after push) one `workflow_dispatch` run whose log line shows `inserted=` and `already_stored=`. No hosted-UI verification is claimed.

## Testing

Test gate on. Logic tests: Step 1 builder and settlement, Step 2 parity, Steps 3 and 5 recorded SQL and row mapping, Step 4 service, Step 6 registry. Step 7 rides on the dry run, a real run, the idempotent re-run and read-only counts. API tests need `DATABASE_URL=postgresql://localhost/ci` and `C:/dev/SportAppV2/api/.venv/Scripts/python.exe`; never print the database URL.

**What these tests cannot show (F-12).** F-12 found NFL P(over) running below observed over rates, most on goblin lines, and that a replay of today's code is not the same as frozen rows. So the tests assert **structure and fidelity** (a frozen row equals the core value; every odds type is kept and labelled; hidden and gated cases carry no probability; guards on the SQL) and make **no calibration claim**. Because every odds type and rung is frozen with `odds_type` in the snapshot, 56d can read calibration by odds type from real frozen rows, which is the evidence F-12 lacked.

## Notes for the AI

- **Freeze what the page serves.** One projection path (Step 2), the board's line rule, the board's history depth (`get_prior_history`), the board's context loader. A test should make the board and the freeze agree on one line.
- **Holdout discipline.** No read, fit or score of 2025-26 or 2026-27 outcomes; run no backtest or `--confirm` CLI; do not touch the fit or the pre-registered rule files. Settlement SQL is exercised by fixtures only.
- Every `sport_*` reference carries `'nhl'`; only `REG` games; never read `PRE`/`PST`. Apply the market filter in every reader that freezes or grades.
- Shared modules (`app/core/prop_*`, `app/services/prop_*`, `app/ingest/prizepicks_props.py`) must not import `sport_registry`. `app/ingest/nhl_prop_predictions.py` is an entry point and may.
- Memory: nothing here is on the request path; the freeze loads one week of lines and history in batches inside an Actions runner, not the Render 512 MB API.
- Freezing writes real rows to the shared database: dry run first, then a separate yes in chat for the real run. Effective in Actions only once this commit is on the pushed default branch; workflows register only when a push changes their file (this one changes), and a quiet public repo pauses schedules after 60 days.
- No em dashes. Ask before committing; no AI attribution beyond the repo's commit attribution lines.

## Decisions for the owner

1. **All 12 markets, or the four shown ones?** **Decided 2026-11-05: all 12.** Recommended: all 12, as NBA freezes all modelled markets and 56b states 56d treats the projection as its own sample (projection-only rows in hidden markets count there). Cost: from stored lines, about 3,300 rows a day against about 830 for the four shown markets, so roughly 560k rows (about 350 MB with index at NBA's measured 0.6 KB a row) versus 140k (about 85 MB) over a 170-day season. The database is 1.6 GB now. Check your Neon plan limit; if it is tight, freezing the four shown markets only is the cheaper option and 56d would then grade P(over) and not hidden-market gaps.
2. **Goalie who dressed but did not start.** Recommended `void_dnp` (matches how 56b replays a goalie: starts only). Needs confirming against how PrizePicks actually voids a backup, which no stored data shows.
3. **Freeze step skipped when the snapshot step exits non-zero** (as NBA: PrizePicks 429 exit 75 skips it). A rate-limited run stores no new lines, so little is lost, but a context-only change on the same line ids also waits for the next good run.
4. **Last freeze of the day is the 21:27 UTC run**, so late West Coast games keep the context of about 17:00 Eastern. Accepted; adding a later snapshot slot is a separate change.

## Red-team record (this draft)

- **Cut:** a separate migration step (none exists to apply); a web or `/nhl/model` surface; any calibration report.
- **Added:** Step 2, so serving and freezing share one function and cannot drift (the draft had the freezer re-implementing availability); the context-failure degrade in Step 4; the stats-loaded half of the finished-week rule and the market-filter and pre-start guards in Step 5 as named regression tests (F-10, F-11, F-13, F-15 gaps on NFL); `team` and provider `position` on the freeze line, which the board reads and NBA never needed.
- **Resequenced:** the CLI and workflow come last, so the workflow never references a missing entry point; the registry step comes before the CLI so `--sport nhl` choices include it.
- **Contracts:** frozen row, period, settlement outcomes and finished-week rule locked above for 56d.
- **Honesty:** the 21:27 UTC cutoff, the storage cost, the goalie-void assumption and the hosted-API independence are stated rather than hidden; first-workflow acceptance stays unverified until after push.

## Results

- **Steps 1 to 6:** pure builder and settlement (17 tests), shared `core_projection`, freeze and grading queries, week service, `NhlPropSource` in `PROP_SOURCES` as `nhl`; API suite 5788 passed.
- **Step 7, first run (2026-11-05, local, shared database):** dry run reported `2026 week 6`, 620 lines frozen (5,519 already started, skipped). The real run inserted 620 (`already_stored=0`), the immediate re-run inserted 0 (`already_stored=620`). Read-only counts: the four shown markets 159 rows (158 with a projection, 158 with `p_over`, `p_under` and `nhl-pover-v1`); the other eight markets 461 rows (427 with a projection) and no probability or version; `edge` null on all; no row for a started game. Flags seen: `low_toi` 24, `injury_listed` 12, `other_starter_expected` 8, `few_prior_games` 2, `injured_out` 1. `load_ranking_calls(db, prop_source("nhl"), 2026)` ran against the database: 0 frozen rows before this run, finished weeks 1 to 5. Workflow YAML parses; the new step follows the snapshot step with no `continue-on-error`.
- **Step 8:** `npm --prefix web run verify` passed (build clean); API pytest 5788 passed. The local, untracked interview guide was updated (freezing built, one manual run of 620 lines, scheduled step not yet run on GitHub, nothing graded).
- **Not verified:** the first GitHub Actions run of the freeze step (effective only once pushed; use `workflow_dispatch` after push); hosted API (suspended, not involved); storage growth beyond this first run.

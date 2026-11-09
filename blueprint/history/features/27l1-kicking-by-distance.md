# Feature: Kicking by distance

**From build-plan:** feature 27l1 (parent 27l, Kicker fantasy projection)
**Status:** completed (2026-11-08)
**Branch:** `feature/kicking-by-distance` (worktree `.claude/worktrees/27l1-kicking-by-distance`)

## Goal

Two things, so 27l2 and 27l3 have what they need and the board stops lying
in the meantime:

1. **Stop the fake gaps.** Kicker (and punter) fantasy lines project 0.0,
   because both NFLverse PPR and `prizepicks_fantasy_points` score offense
   only (`api/app/core/nfl_fantasy.py`). With 4+ games they pass
   `edge_is_comparable`, so 0 against an 8.5 line ranks as a -85% to -100%
   gap at the top of the home page's "Largest gaps across sports". From this
   feature on, a K or P fantasy line keeps its line, recent form and history,
   but has no projection, edge or P(over).
2. **Store what the PrizePicks formula needs.** PrizePicks scores field goals
   by distance (0-39 yds +3, 40-49 +4, 50+ +5). We store only `fg_made` and
   `pat_made` (34b). Add NFLverse's made and missed counts per distance band
   and `pat_missed`, so 27l2 can test every candidate formula, including miss
   penalties.

**What is already in place** (checked 2026-11-08):
- 486 standard 2026 `fantasy_points` lines on 36 kickers, averaging 6.23.
- Kicker weekly stat rows exist for 2018-2026 with no NULL `fg_made`; the
  2025 average under 3 per FG and 1 per PAT is 7.37.
- NFLverse `stats_player_week_<season>.csv` carries `fg_made_0_19`,
  `fg_made_20_29`, `fg_made_30_39`, `fg_made_40_49`, `fg_made_50_59`,
  `fg_made_60_`, the six matching `fg_missed_*` columns, and `pat_missed`.
- Every NFL projection reader (slate, 27a grading, 27b replay, 27i frozen
  predictions) goes through `_slate_line` in `api/app/services/nfl/slate.py`.

## In scope

- **Hide rule:** a pure check in `app/core/nfl_projection.py` that a
  `fantasy_points` line is projected only for positions the scoring covers.
  K and P are not, until 27l3. `_slate_line` applies it.
- **Migration `0053`:** 13 nullable `smallint` columns on
  `nfl_player_weekly_stats`: six `fg_made_<band>`, six `fg_missed_<band>`,
  `pat_missed`.
- **Weekly stats ingest:** `parse_player_stats` and `upsert_weekly_stat` read
  and write them.
- **Backfill:** 2024, 2025 and 2026 (the `PROJECTION_FIRST_HISTORY_SEASON`
  floor), run by the user one season at a time.

## Out of scope

- **Any kicker projection or scoring formula.** 27l2 pins the formula and
  27l3 projects. No kicking term is added to `nfl_fantasy.py` here.
- **Seasons before 2024.** No reader goes below the history floor. A later
  item can backfill more with a re-run.
- **A projection version bump.** K and P fantasy output goes from a wrong
  0.0 to none; every other line is unchanged, so the P(over) fit
  (`FIT_PROJECTION_MODEL_VERSION`) stays valid. See Notes.
- **Re-grading 27j.** Not needed: 27j picks only rows with P(over), and the
  496 frozen K fantasy rows (projection 0) have none, so they never entered a
  slice.
- **FG attempts, blocks, distance lists and game-winning FGs.**

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

The hide rule lands first: it needs no migration, so the board is honest even
if the data steps wait on a manual migration.

- [x] **Step 1 - Hide rule** -
  - **Core:** in `app/core/nfl_projection.py`, a constant
    `FANTASY_UNSCORED_POSITIONS = frozenset({"K", "P"})` and
    `projects_line(market, position) -> bool` (False only for
    `fantasy_points` with K or P). A denylist, not an allowlist: the
    first build hid 3 CB fantasy lines (a two-way player who does score
    offense), so every other position, `None` included, is unchanged.
  - **Slate:** in `_slate_line`, when `projects_line` is False, `projection`,
    `edge`, `p_over`, `p_under` and `over_probability_version` are `None`
    and the flag `position_not_scored` is added. Recent form and history
    still render.
  - **Web:** a `position_not_scored` label in `web/src/utils/nflLabels.ts`
    ("Fantasy scoring for this position is not modelled yet").
  - **Tests:** `test_nfl_projection.py` covers `projects_line` for K, P,
    `None`, each skill position, and a non-fantasy market for a K. A
    `_slate_line` test with a K fantasy row asserts no projection, edge or
    P(over) and the flag.
  - *Done when:* tests pass; a local `/nfl/slate` for the current week has no
    K or P fantasy line with a projection or edge; the home page's Largest
    gaps (All and NFL) shows no kicker; a kicker's game-page fantasy line
    shows its line and recent form with no model value.
- [x] **Step 2 - Migration `0053`: kicking by distance** -
  `0053_nfl_kicking_by_distance.py`:
  - **Upgrade:** add the 13 nullable `smallint` columns, no default.
    Additive, so master's code is unaffected.
  - **Downgrade:** drop them.
  - **Test:** `tests/test_migration_0053.py` (statement capture, as
    `test_migration_0042.py`), pinning names, type and nullability.
  - *Done when:* the test passes and `alembic upgrade head --sql` shows only
    the 13 `ADD COLUMN` statements. The real upgrade against Neon is the
    user's, one command, after review.
- [x] **Step 3 - Parse and store** -
  - **Ingest:** `NflWeeklyStat` gains the 13 fields; `parse_player_stats`
    reads them with `_as_optional_int` (blank stays `None`, never 0);
    `upsert_weekly_stat` inserts and updates them.
  - **Tests:** extend the kicker test in `test_nflverse.py`: a kicker row's
    band values, a blank cell as `None`, a non-kicker row's zeros, and the
    upsert parameters carrying all 13.
  - *Done when:* tests pass and a `--dry-run` for 2026 parses kicker rows
    with band values.
- [x] **Step 3b - Correction note on the line record** - added 2026-11-08
  after the read-only replay showed step 1 lowers the published 27a record
  (see Notes). The user chose to correct it with a stated reason. A static
  `nfl-model-note` under "PrizePicks line grading" on `NflModelPage.tsx`
  gives the date, the cause and the before/after rates.
  - *Done when:* the note renders under the line grading section; web build
    and tests pass.
- [x] **Step 4 - Backfill and check** - the user runs
  `python -m app.ingest.nflverse --season 2024`, then 2025, then 2026 (about
  10 minutes each). A read-only check script in the scratchpad (not `api/`)
  then reports, per season, for K rows:
  - NULL count for each new column (expected 0);
  - rows where the six made bands do not sum to `fg_made` (expected 0);
  - rows where 3 x (0-39 made) + 4 x (40-49) + 5 x (50+) + `pat_made` is
    below 3 x `fg_made` + `pat_made` (expected 0, since bands only add).
  - *Done when:* all three counts are 0 for 2024-2026 (or every exception is
    explained), and the results are recorded in this spec.
  - **Result (2026-11-08):** migration `0053` applied to Neon, then all three
    seasons loaded (2026: 9037 rows in 1425s; 2025: 18522 in 1761s; 2024:
    18112 in 1781s). The first attempts failed and rolled back: Neon's
    `idle_in_transaction_session_timeout` is 5 min, each season is one
    transaction, and the PC entered Modern Standby mid-run (17:02, 17:25).
    The successful run held the machine awake per process
    (`SetThreadExecutionState`). Kicker rows:

    | Season | Rows | NULL band | Bands ≠ `fg_made` | Distance < flat | Avg distance pts | Avg flat pts | Avg FG missed | Avg PAT missed |
    |---|---|---|---|---|---|---|---|---|
    | 2024 | 543 | 0 | 0 | 0 | 8.50 | 7.36 | 0.29 | 0.07 |
    | 2025 | 543 | 0 | 0 | 0 | 8.53 | 7.37 | 0.25 | 0.07 |
    | 2026 | 262 | 0 | 0 | 0 | 8.69 | 7.44 | 0.30 | 0.10 |

    For 27l2: the 2026 standard K fantasy lines average 6.23, below both
    scorings and below distance scoring minus one point per miss (about 8.3),
    so PrizePicks' kicker formula, or how it sets these lines, differs from
    every candidate assumed so far.

## Files / areas

- `api/app/core/nfl_projection.py` - `FANTASY_UNSCORED_POSITIONS`, `projects_line`
- `api/app/services/nfl/slate.py` - apply the rule in `_slate_line`
- `web/src/utils/nflLabels.ts` - flag label
- `api/app/db/migrations/versions/0053_nfl_kicking_by_distance.py` (new)
- `api/app/ingest/nflverse.py` - `NflWeeklyStat`, `parse_player_stats`
- `api/app/repositories/nfl.py` - `upsert_weekly_stat`
- `api/app/core/nfl_kicking.py` (new) - the 13 column names
- `web/src/pages/NflModelPage.tsx` - correction note on the line record
- `api/tests/test_nfl_projection.py`, `test_nflverse.py`, `test_nfl_repository.py`,
  `test_migration_0053.py` (new), and the slate test that covers `_slate_line`

## Data / contracts

- **Load-bearing for 27l2 and 27l3:** columns on `nfl_player_weekly_stats`,
  all nullable `smallint` (NULL = not loaded, never "zero"):
  `fg_made_0_19`, `fg_made_20_29`, `fg_made_30_39`, `fg_made_40_49`,
  `fg_made_50_59`, `fg_made_60_`, `fg_missed_0_19`, `fg_missed_20_29`,
  `fg_missed_30_39`, `fg_missed_40_49`, `fg_missed_50_59`, `fg_missed_60_`,
  `pat_missed`. Names match NFLverse verbatim.
- **Load-bearing:** `projects_line(market, position)` is the one switch 27l3
  flips (by adding K to the scored set under a new version).
- **Response shape:** no new fields. `position_not_scored` is a new
  `quality_flags` value on `NflSlateLineSchema`.
- **Stored slate copies:** `/nfl/slate` serves `report_snapshots`, so
  production shows the change only after `nfl_slate_snapshot` reruns (the
  Tuesday NFL workflows, or a manual run).

## Testing

- Test gate is on (pytest and vitest).
- Logic tests: `projects_line`, the `_slate_line` K case, the migration
  statements, the parser and upsert parameters.
- Behavior: local slate and home page for step 1; the backfill check for
  step 4.
- Final gate: `npm --prefix web run verify && cd api && python -m pytest`.

## Notes for the AI

- `core/` stays pure: `projects_line` takes values, not rows or sessions.
- **No version bump, on purpose.** `NFL_PROJECTION_MODEL_VERSION` stays
  `opponent-dvp-tg-blend-usage-snap-v4`. Every non-K/P line is byte-identical,
  and bumping would hide P(over) until the 27g fit is regenerated. The 27b
  replay and 27a grading will drop K/P fantasy rows (projection None); say so
  when reporting any fantasy MAE change.
- **The published 27a line record changes.** Measured 2026-11-08 (read-only
  replay of `load_line_grading(db, 2026)`, weeks 1-8): 164 K fantasy
  player-game calls, every settled one an "under" that "hit" (160 of 160),
  because a kicker also settles at 0 points. Removing them moves overall
  calls from 51.1% (2558 of 5006) to 49.5% (2398 of 4846), and fantasy
  points from 56.2% (784 of 1394) to 50.6% (624 of 1234). The stored
  2026-11-03 record shows 51.0% and 56.1%. The old figures were inflated,
  not earned. Settlement of K fantasy lines stays 0 until 27l2 pins the
  formula, but with no projection those lines are no longer calls.
- Frozen predictions (27i) already handle a `None` projection (thin samples
  produce one); confirm that during step 1 rather than assume.
- Migrations run manually, one command at a time, with `-c` pointing at a
  local `alembic.ini` (see AGENTS.md). Never run the upgrade or backfill
  without the user's yes.
- The PrizePicks PAT value and miss penalties are unconfirmed. Do not encode
  any formula here; that is 27l2.
- Source for the distance bands: PrizePicks playbook,
  https://www.prizepicks.com/playbook-article/how-to-play-prizepicks-nfl-fantasy-scoring-system
- Update `docs/SportApp-Employer-Interview-Guide.md` (untracked, main
  checkout) only at 27l3 or if this changes a claim; 27l1 likely does not.

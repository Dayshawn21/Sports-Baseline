# Feature: Kicker projection

**From build-plan:** feature 27l3 (parent 27l, Kicker fantasy projection)
**Status:** spec approved 2026-11-08, not started
**Branch:** `feature/kicker-projection` (worktree `.claude/worktrees/kicker-projection-1d3348`)

## Goal

Two things, in this order:

1. **Settle kicker fantasy lines on real points.** `prizepicks_fantasy_points`
   scores offense only, so every K fantasy line settles at 0 and 27a's
   over/under table counts each one as an under. From this feature on, the
   stored value adds `kicking_points(PRIZEPICKS_KICKING_FORMULA, row)`.
2. **Project kickers, and serve the projection only if it earns it.** A
   recency-blended kicker baseline, scored on 2025 through the 27b harness
   against a pre-registered reference under 27b's adoption rule, committed
   before anything is scored. Adopt: K fantasy lines get a projection and
   edge under their own model version. Reject: K stays hidden, as now.

**What spec research found** (2026-11-08, counts only, nothing scored):

- **Kicker stat rows:** 543 in 2024, 543 in 2025, 262 in 2026 (REG), none
  with a NULL `prizepicks_fantasy_points`. 519 of the 543 2025 kicker-games
  have 4 or more earlier games from 2024 on, so the 300-case floor is met.
- **Kicking stats on non-kickers:** 3 rows, all punters (2 in 2024, 1 in
  2026). Every other non-K row has zero kicking stats, so adding the formula
  to every row changes nothing outside K and P.
- **NULL band columns:** none in 2024-2026; every stored 2018-2023 row (27l1
  backfilled 2024 on only). No reader goes below the 2024 history floor.
- **Lines:** 189 standard full-game and 185 first-half K fantasy
  player-games in 2026. 488 frozen v4 K fantasy rows, all from before 27l1.
- **The replay excludes kickers today.** `get_replay_rows` loads only the
  positions in `REPLAY_MARKETS_BY_POSITION` (QB, RB, WR, TE), which 27e's
  environment fit and 49's volume backtest also import.
- **Production fantasy projects from NFLverse PPR** (`averages.fantasy_points`,
  27f rejected PrizePicks points for skill players), which is 0 for a
  kicker. Flipping `projects_line` alone would bring back the 0.0 projection.
  The kicker path must swap in PrizePicks points, as the 27f arm
  (`apply_prizepicks_fantasy`) does.

## Decisions this spec makes (confirm at review)

| Question | Decision | Why |
|---|---|---|
| Settle at ingest or at grading time | **Ingest**: `prizepicks_fantasy_points` includes kicking points, re-backfilled for 2024-2026 | One stored definition. Grading-time would need the kicking terms added in five readers (27a loader, replay actual, four baseline aggregates, player page), and a future reader that forgets settles K at 0 again. Cost: about 90 minutes of DB writes, once, with the machine held awake |
| What 2025 is scored against | **The K position's pre-week mean** (a no-information constant per week) | Production serves no K number, so 27b's "against production" has nothing to pair with. A projection that cannot beat "every kicker scores the average" would only add noise gaps to the board |
| Version | **A separate `nfl-kicker-v1`** for K fantasy lines; `opponent-dvp-tg-blend-usage-snap-v4` unchanged | Bumping v4 would reset 27j's accruing v4 slices (standard over 128 of 200) and hide receiving and rushing yards P(over) until a 2025 refit. Rec Targets and volume set the precedent for a second version. The build plan says "a version bump"; this reads it as a new version for K lines |
| P(over) for K | **None** | The 27g fit describes v4's residuals and hides fantasy anyway. With no P(over), 27i's rule makes no K pick |
| Punters | **Stay hidden** | No P scoring exists; the 3 punter rows with a PAT or FG just settle correctly |
| PAT-miss penalty | **Carried as a bounded error** (see Notes), counted, not modelled | 27l2 left it unresolved; about 0.11 points a game |

## In scope

- **Settlement:** a pure total in `app/core/nfl_kicking.py`, the ingest
  wiring, and the 2024-2026 re-backfill (the user runs it).
- **The 27a record correction:** a measured before/after for the over/under
  table and a dated note on the model page, as 27l1 did.
- **The kicker projection** and its reference, pure, in a new
  `app/core/nfl_kicker_projection.py`.
- **The pre-registered decision rule**, committed as a checkpoint before any
  kicker projection is scored on real data.
- **A replay loader option and a read-only report**,
  `python -m app.backtest.nfl_kicker_projection`.
- **One real run** (separate yes in chat), and on `adopt` the serving change.

## Out of scope

- **Any v4 change.** Every non-K line stays byte-identical, P(over) and 27j's
  v4 sample included.
- **Re-fitting 27g or a K P(over).** A K distribution fit would be its own
  item and its own holdout read.
- **First-half K lines.** No per-half kicking stats; they stay
  `unsettleable_segment` and get no edge (`edge_is_comparable`).
- **Recent form for skill-player fantasy lines.** `_history_value` shows
  NFLverse PPR for them while they settle on PrizePicks points. A real but
  separate mismatch; follow-up.
- **Backfilling kicking points before 2024.** Stored 2018-2023 rows keep
  offense-only points; nothing reads them for kickers.
- **Game environment, wind or team-total inputs for kickers.** One
  registered candidate; a richer one is a new pre-registration.
- **27j or 27h for K.** No P(over), so nothing to rank.

## Pre-registered decision rule

Fixed in step 4 and committed before step 6 scores anything. Changing any of
it after a kicker projection has been scored on 2025 is a new rule under a
new version name, not an edit. This is the next read of the 2025 holdout
after 39b's (the overview counts eight) and the first for kickers.

**Sample.** 2025 regular-season weeks 1-18. A case is a `K` player-game
with a weekly stat row and a non-NULL `prizepicks_fantasy_points`, replayed
as a `fantasy_points` line through the slate's own `_slate_line`, that
`edge_is_comparable` rates (4 or more baseline games). Excluded rows are
counted, never dropped silently.

**Candidate (`nfl-kicker-v1`).** For a K fantasy row:
1. **The stat:** PrizePicks fantasy points (offense plus kicking) in place
   of PPR, for the player, position, opponent and league averages
   (`apply_prizepicks_fantasy`, unchanged).
2. **Recency blend:** 27d's `blended_row`, unchanged: the line season and
   the most recent earlier season with games, weighted by games with last
   season at `PREVIOUS_SEASON_WEIGHT = 0.6`. With one season, its average.
3. **Shrink toward the position:** `n_eff` = current games + 0.6 x previous
   games (or the one season's games), then
   `baseline = (n_eff x player + 10 x position) / (n_eff + 10)`.
   `KICKER_PRIOR_GAMES = 10`, the value anytime TD already uses
   (`TD_PRIOR_GAMES`), fixed here, not fitted.
4. **Then `model_projection`, unchanged:** the moneyline bump fantasy lines
   already take and the K opponent (DVP) adjustment. With `n_eff` of 4 or
   more its own regression does nothing; below 4 the line has no edge.

**Reference.** The same row's blended K position average from step 2 (the
value step 3 shrinks toward), with no moneyline or opponent adjustment.
Computed only on the rows the candidate rates, so the two arms pair one to
one; a row with no position average is excluded and counted.

**Verdict.** 27b's `adoption_verdict`, imported unchanged: 300 or more
paired cases, MAE at least 1.0% below the reference, and the mean paired
`|candidate error| - |reference error|` below zero by more than 2 SE.
`adopt`, `reject` or `insufficient`.

**Expected before the run.** Kicker points are noisy (per-game SD near 4)
and kickers differ little in true mean, so a raw season average carries
about as much noise as signal. The shrink and the moneyline bump are what
could clear 1%. A reject is a plausible outcome and an acceptable one.

**After the verdict.**
- `adopt`: step 7 serves it.
- `reject` or `insufficient`: K stays hidden, and step 7 is skipped. Final
  for `nfl-kicker-v1` on 2025; another candidate needs a new
  pre-registration and spends the holdout again.

**Reported, never deciding:** each arm's MAE, bias and share below; the
excluded counts; and the candidate's MAE with actuals settled under the
other consistent formula (`distance_pat1_fgmiss0_patmiss1`), to size the
PAT-miss error.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

**Exception: the step 4 checkpoint is required**, before step 6's run.

## Build steps

- [x] **Step 1 - Kicking in PrizePicks points** -
  - **Core:** in `app/core/nfl_kicking.py`,
    `prizepicks_points_with_kicking(offense: float | None, row) -> float | None`:
    offense plus `kicking_points(PRIZEPICKS_KICKING_FORMULA, row)`, rounded
    to 2; None when either is None (never a partial sum, as both inputs
    already do). The formula is never re-derived inline.
  - **Ingest:** `parse_player_stats` sets `prizepicks_fantasy_points` from
    it, reading `pat_made` and the band columns it already parses.
  - **Tests** (`test_nfl_kicking.py`, `test_nflverse.py`): a kicker row
    (FG bands, PATs, misses ignored); a skill-player row unchanged; a punter
    with one PAT gaining 1; a NULL band giving None; a None offense giving
    None.
  - *Done when:* tests pass and `python -m app.ingest.nflverse --season 2026
    --dry-run` shows kicker rows with kicking points and the same NULL
    `prizepicks_fantasy_points` count as the stored season (0).
- [x] **Step 2 - Re-backfill and check** - before the backfill, a read-only
  scratchpad script (not `api/`) saves, for 2024-2026, every stored
  `(player_id, game_id, position, prizepicks_fantasy_points)`, and a
  read-only replay of `load_line_grading(db, 2026)` saves the 27a over/under
  table and model hit rate (step 3's "before"). The user then runs
  `python -m app.ingest.nflverse --season 2026`, then 2025, then 2024,
  holding the machine awake per process (about 25-30 minutes each; Neon's
  5-minute idle-in-transaction limit killed 27l1's first attempts). Then the
  script reports:
  - K rows where the stored value differs from offense plus
    `kicking_points(PRIZEPICKS_KICKING_FORMULA, row)` (expected 0);
  - non-K, non-P player-games present before whose value changed (expected
    0; any change explained, for example an NFLverse stat correction; rows
    new since the snapshot, such as a fresh 2026 week, are counted apart);
  - P rows that changed (expected the 3 known).
  No projection is computed in this step.
  - *Done when:* all three hold for 2024-2026 or every exception is
    explained, and the counts are recorded under Results.
- [x] **Step 3 - The 27a record, measured and noted** - the same read-only
  replay of `load_line_grading(db, 2026)` after the backfill, against step
  2's saved "before":
  - the `fantasy_points / standard` over/under row and the overall table;
  - the model hit rate (expected unchanged: K lines have had no edge since
    27l1);
  - **the PAT-miss bound:** settled standard full-game K lines whose outcome
    differs under `distance_pat1_fgmiss0_patmiss1`.
  Then a dated note under "PrizePicks line grading" on `NflModelPage.tsx`
  (beside 27l1's) gives the cause and the before/after over rate. The stored
  `/nfl/model/prop-lines` copy refreshes on the next `nfl-ingest.yml` run,
  or by `python -m app.ingest.nfl_model_snapshot` with a yes in chat.
  - *Done when:* the figures are under Results; the note renders; web build
    and tests pass.
- [x] **Step 4 - Kicker projection and decision rule (pre-registration)** -
  new `app/core/nfl_kicker_projection.py`:
  - `NFL_KICKER_MODEL_VERSION = "nfl-kicker-v1"`, `KICKER_PRIOR_GAMES = 10`,
    `KICKER_PROJECTION_SERVED = False`.
  - `kicker_row(row, season) -> dict`: for a K `fantasy_points` row, the
    candidate's steps 1-3 and `"kicker_projected": True`; any other row
    unchanged.
  - `kicker_reference(row, season) -> float | None`: the reference.
  - The verdict is `adoption_verdict` itself; the module names the sample
    constants (`KICKER_REPLAY_MARKETS = {"K": ("fantasy_points",)}`, season
    2025).
  - **Slate wiring, inert in production:** `_slate_line` projects a row when
    `projects_line` allows it **or** `row["kicker_projected"]`; such a line
    carries `projection_model_version = NFL_KICKER_MODEL_VERSION`, no P(over)
    and no `position_not_scored`. `build_slate` applies `kicker_row` only
    when `KICKER_PROJECTION_SERVED` is True, so production is unchanged.
  - **Tests** (`test_nfl_kicker_projection.py`, the slate test): the shrink on
    known numbers (0, 4 and 30 effective games); one season and two seasons;
    a non-K row and a K non-fantasy row unchanged; the reference equals the
    position blend; a flagged K row through `_slate_line` gets a projection
    from PrizePicks points (never PPR's 0.0), the kicker version and no
    P(over); an unflagged K row is still hidden; a QB fantasy row is
    byte-identical.
  - The largest step (a new module plus the slate path, about 150 lines with
    tests). It stays one step because the pre-registration commit has to
    hold everything that sets the candidate's number, and `_slate_line`
    does.
  - *Done when:* tests pass; the user commits the checkpoint. **No kicker
    projection is scored on real data before this commit.** Its hash goes
    under Results.
- [ ] **Step 5 - Replay loader and report** -
  - **Repository:** `get_replay_rows(db, season, week, markets_by_position=REPLAY_MARKETS_BY_POSITION)`;
    the default keeps every current caller identical.
  - **Report:** new `app/backtest/nfl_kicker_projection.py` (read-only,
    `--season` defaults to 2025). Candidate cases through `kicker_row` and
    `_slate_line`, reference cases from `kicker_reference` on the same rows,
    both as 27b `ReplayCase`s. Prints coverage (K player-games, excluded and
    why), each arm's `market_metrics`, the paired table and verdict through
    `paired` and `adoption_verdict`, the PAT-miss sensitivity line, and a
    `PREREGISTRATION_COMMIT` constant.
  - **Tests:** recorded SQL shows the K position filter when passed; the
    report on synthetic cases prints one coverage count, one metrics row and
    the verdict line.
  - *Done when:* tests pass. No live run in this step.
- [ ] **Step 6 - The run** - after a separate yes in chat, run
  `python -m app.backtest.nfl_kicker_projection` once and paste its output
  under Results.
  - *Done when:* Results holds the output and verdict; on `reject` or
    `insufficient`, `KICKER_PROJECTION_SERVED` stays False and step 7 is
    marked skipped.
- [ ] **Step 7 - Serve (only on `adopt`)** -
  - `KICKER_PROJECTION_SERVED = True`.
  - **Recent form:** K fantasy history values read
    `prizepicks_fantasy_points` (added to `get_slate_player_history`), so a
    kicker's form is not a row of PPR zeros beside its projection.
  - **27a:** the model hit rate counts only edges on lines served under
    `NFL_PROJECTION_MODEL_VERSION`, so kicker calls never enter v4's record.
  - **Tests:** `build_slate`'s row path applies `kicker_row` to K fantasy
    rows only; K history reads PrizePicks points; the 27a edge filter.
  - *Done when:* tests pass; a local `/nfl/slate` for the current week shows
    K standard full-game fantasy lines with a projection, gray edge and
    `nfl-kicker-v1`, no P(over); punters still `position_not_scored`; the
    home page's Largest gaps may now list a kicker, gray, against a
    projection near the line rather than 0; a
    replay of the 27a model hit rate and the 27j v4 report are identical to
    before; a frozen-prediction dry run writes K rows under `nfl-kicker-v1`.
    Production shows it after `nfl_slate_snapshot` reruns (Tuesday, or a
    manual run with a yes).

## Files / areas

- `api/app/core/nfl_kicking.py` - `prizepicks_points_with_kicking`
- `api/app/ingest/nflverse.py` - settlement at ingest
- `api/app/core/nfl_kicker_projection.py` (new) - candidate, reference, version, constants
- `api/app/services/nfl/slate.py` - the `kicker_projected` path in `_slate_line` and `build_slate`
- `api/app/repositories/nfl.py` - `get_replay_rows` markets option; history column (step 7)
- `api/app/backtest/nfl_kicker_projection.py` (new) - the report
- `api/app/services/nfl/track_record.py` - v4-only edges for 27a (step 7)
- `web/src/pages/NflModelPage.tsx` - correction note
- Tests: `test_nfl_kicking.py`, `test_nflverse.py`, `test_nfl_kicker_projection.py`
  (new), `test_nfl_kicker_projection_report.py` (new), `test_nfl_repository.py`,
  the slate and track-record tests
- `blueprint/context/project-overview.md` - the 27l entry and the holdout count (at `/complete`)

## Data / contracts

- **No schema change.** `prizepicks_fantasy_points` changes meaning for K
  and P rows from 2024 on: offense plus kicking under
  `PRIZEPICKS_KICKING_FORMULA`. **Load-bearing:** every fantasy settlement
  (27a, 27b replay actuals, 27g, the player page) reads it.
- **Load-bearing:** `NFL_KICKER_MODEL_VERSION = "nfl-kicker-v1"` on
  `NflSlateLineSchema.projection_model_version` and on frozen
  `sport_prop_predictions` rows, with a NULL `over_probability_version`.
  27j's v4 sample excludes them by version, as it does targets and volume.
- **Response shape:** no new fields. On adopt, K fantasy lines lose
  `position_not_scored` and gain the usual model flags.
- **Stored copies:** `/nfl/slate` and `/nfl/model/prop-lines` serve
  `report_snapshots`; production changes only after their snapshot jobs run.

## Testing

- Test gate is on (pytest and vitest).
- Logic tests: steps 1, 4 and 5 (the total, the projection and reference,
  the slate path, the loader SQL, the report), step 7's wiring.
- Behavior: the step 1 dry run, the step 2 checks, the step 3 replay, the
  step 6 run, the step 7 local slate.
- Final gate: `npm --prefix web run verify && cd api && python -m pytest`.

## Results

**Step 2 re-backfill (2026-11-08).** Before snapshot: 45,671 stored
2024-2026 values, and the 27a report (`nfl_prizepicks_lines --season 2026`).
Loaded with the PC held awake, one season after another:

| Season | Window | Loaded |
|---|---|---|
| 2026 | 20:59-21:14 (15 min) | 272 games, 9,310 rows |
| 2025 | 21:14-21:46 (32 min) | 272 games, 18,522 rows |
| 2024 | 21:46-22:15 (29 min) | 272 games, 18,112 rows |

Check against the snapshot (45,944 rows now):
- K rows not equal to offense plus `kicking_points(PRIZEPICKS_KICKING_FORMULA, row)`: **0**
- Non-K, non-P player-games whose value changed: **0**
- P rows changed: **2** (Wishnowsky 2024 week 5, a 50-59 yard FG, 0 -> 3;
  Evans 2026 week 6, one PAT, 0 -> 1). The third punter row found in spec
  research (Gillan 2024 week 2) has only a missed PAT, which the pinned
  formula does not score, so it stays 0.
- Rows new since the snapshot: 273, all 2026 (week 9).
- NULL `prizepicks_fantasy_points`: 0 in every season.

**Step 3, the 27a record (2026-11-08).** The 2026 re-load also brought in
week 9 stats, so the whole-report diff mixes two changes. The kicker effect,
on the same settled lines now graded:

| `fantasy_points / standard` | Over | Under | Push | Over rate |
|---|---|---|---|---|
| K lines settled offense-only (as before) | 0 | 184 | 0 | 0% |
| K lines settled with kicking (now) | 90 | 91 | 3 | 49.7% |
| Whole row, offense-only K | 692 | 941 | 8 | 42.4% |
| Whole row, now | 782 | 848 | 11 | 48.0% |

- **Model hit rate:** unchanged by the fix. 0 K fantasy lines carry an
  edge, so none is a call. The report's all-calls figure moved from 49.4%
  (5,250) to 49.7% (5,440) only because week 9 was added.
- **PAT-miss bound:** 19 of the 184 settled K lines had a missed PAT, and 3
  would settle differently under `distance_pat1_fgmiss0_patmiss1`.
- A dated note under "PrizePicks line grading" on the model page records
  the correction. Production's stored `/nfl/model/prop-lines` copy refreshes
  on the next `nfl-ingest.yml` run (or `nfl_model_snapshot` with a yes).

(Steps 4 and 6 fill in the rest.)

## Notes for the AI

- `core/` stays pure. `nfl_kicker_projection.py` imports from
  `nfl_fantasy`, `nfl_season_blend` and `nfl_kicking`; `nfl_projection.py`
  must not import it (`nfl_season_blend` already imports `nfl_projection`).
- **Order matters for honesty.** Steps 1-3 read 2025 actuals only as formula
  checks (stored value equals the formula), never as projection errors. No
  kicker projection or reference is compared with any 2025 or 2026 outcome,
  not even in a scratch script, before step 4's commit.
- **Do not add K to `REPLAY_MARKETS_BY_POSITION`.** 27e's environment fit
  and 49's volume backtest import it.
- **The PAT-miss bound.** If PrizePicks does take 1 point per missed PAT,
  stored K points are 1 too high on a game with a missed PAT (7% to 10% of
  kicker-games, from 27l1's averages), about 0.11 points a game on average.
  A line flips only when the actual lands within 1 point above it. Step 3
  counts the flips on 2026 lines and step 6 reports the MAE effect; neither
  decides anything. Say so wherever K settlement figures are quoted.
- **Merge with a fast-forward or no-ff merge**, never a plain squash: this
  feature cites a pre-registration hash.
- The backfill and every snapshot regeneration are DB writes: never run
  them without the user's yes. Hold the machine awake per process (user
  memory on long Neon backfills).
- Use the API venv at `C:\dev\SportAppV2\api\.venv`, `PYTHONPATH=.` from
  `api/` for scratch scripts, and `asyncio.WindowsSelectorEventLoopPolicy()`.
  The main checkout runs other sessions: never switch, stash or merge there.
- The worktree is on `claude/kicker-projection-1d3348`; `/implement`
  creates `feature/kicker-projection` from it.
- Interview guide (untracked, main checkout): update at step 6 with the
  verdict, and at step 3 if the settlement correction changes a quoted
  figure.
- **Split option, if the user prefers:** 27l3a "Kicker settlement" (steps
  1-3, stands alone and fixes 27a whatever the projection does) and 27l3b
  "Kicker projection" (steps 4-7). Kept as one because step 6 needs step 2's
  actuals and 27l2 assigned settlement to 27l3.

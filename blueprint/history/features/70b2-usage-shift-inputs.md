# Feature: Point-in-time replay inputs and the pure usage-shift adjustment

**From build-plan:** feature 70b2 (parent 70b, Usage-shift backtest arm; feature 70, Injury-aware NFL projections)
**Status:** complete (2026-11-22). Verify passed (1871 web tests, typecheck, build; 6621 API tests). No scored run; no 2025 result read.
**Branch:** `feature/70b2-usage-shift-inputs` (worktree `.claude/worktrees/70b2-usage-shift`)

## Goal

Give the NFL projection replay what a usage-shift arm needs, and the pure math
that arm will run, without scoring anything. When a starter is ruled Out on the
Friday report, the teammate who takes his place gets a share of the starter's
recent carries or targets, and that teammate's rushing or receiving projection
scales with the extra volume. 70b3 adds the arm, pre-registers the pass rule and
the parameter values, and runs it on 2024.

## What exists (read 2026-11-22)

- **Replay rows already carry this week's availability.** `get_replay_rows`
  (`app/repositories/nfl.py:2822`) builds rows through `_slate_line_rows`, which
  includes `_AVAILABILITY_CTE` bound to `:season` and `:week`: `injury_status`,
  `depth_rank`, `active_depth_rank`, `out_ahead` (names) and the previous chart
  row. For 2024 and 2025 the injury source is the nflverse report alone (ESPN rows
  exist only for 2026), so it is the point-in-time Friday report.
- **What is missing:** the Out teammate himself. A row knows who is Out ahead of
  the player by name only, not that teammate's id, recent volume, or whether his
  absence is new.
- **How arms work:** each arm in `app/backtest/nfl_projections.py` transforms the
  row, then `_slate_line` projects it. A projection's baseline is
  `baseline_projection(market, row["averages"])`, the player's own per-game
  average for the market (`NflHistoricalAverages`).
- **Volume data:** `nfl_player_weekly_stats` has `rushing_attempts` and `targets`
  per player-game.
- **70b1's carry-over:** 19% of 2024's Out players have no chart row that week
  (3% in 2025), so no teammate "moves up" in the stored ranks for them.

## Design (decisions to confirm at review)

1. **Positions and markets.** RB, WR and TE only. Carries scale `RUSHING_YARDS`
   and `RUSHING_ATTEMPTS`; targets scale `RECEIVING_YARDS` and `RECEPTIONS`. QB
   (a backup QB has no usable per-game baseline), passing, fantasy and anytime TD
   are untouched, so their rows come back unchanged.
2. **Who gives volume:** a same-team, same-position player who is `Out` this week,
   is on this week's chart, and played in his team's most recent game before this
   week (a **fresh absence**). A player already missing last week is not shifted
   again, because his backup's recent averages already include those games.
3. **Who receives it:** the non-Out teammate(s) at the same position whose active
   rank equals the Out player's chart rank (the next man up). Ties, such as three
   WRs at rank 1, split the volume equally.
4. **How much:** `transfer` times the Out player's season-to-date volume per game
   played, before this week. The receiver's multiplier is
   `(own + gained) / own`, using his own season-to-date volume per game played,
   capped at `max_multiplier`. A receiver whose own volume is below
   `min_own_volume` per game is left unshifted and counted, since a ratio on a
   near-zero base is not a projection.
5. **Parameters, not constants.** `transfer`, `min_own_volume` and
   `max_multiplier` are function arguments with no defaults. 70b3 chooses and
   pre-registers them before any scored run.
6. **2024 Out players with no chart row** are not shifted, and are counted as
   missed by position, so 70b3 can say how much of the effect they hide.

## In scope

- A pure `app/core/nfl_usage_shift.py`: the input type, the shift computation and
  the row adjustment, with tests.
- A repository loader for one season-week's usage-shift inputs per team and
  position, with a test that pins its SQL bounds.
- `ReplayRow` carrying those inputs, loaded by `get_replay_rows`, with every
  existing arm's output unchanged.
- A counts-only CLI that reports, for 2024 only, how many replay rows a given
  parameter set would shift and how many Out players it misses.

## Out of scope

- The `usage_shift` arm, the pass rule, any scored run or verdict (70b3).
- Reading any 2025 result. The counts CLI refuses any season but 2024.
- Serving, freezing, a model version, or any change to what the slate shows (70c).
- QB changes and cross-position effects (a QB Out changing his receivers).
- Changing `_AVAILABILITY_CTE`, `out_ahead` or 70a's `role_changed` guard.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Shift computation (pure).** `app/core/nfl_usage_shift.py`:
  `UsageShiftPlayer` (player id, chart rank or None, out, fresh, carries and
  targets per game, games) and `usage_shifts(players, transfer, min_own_volume,
  max_multiplier) -> dict[player_id, UsageShift]` for one team-position, where
  `UsageShift` holds the carry and target multipliers, the Out players it came
  from, and a reason when a receiver is left unshifted.
  *Done when:* tests in `api/tests/test_nfl_usage_shift.py` cover an RB1 Out and
  fresh (RB2 gains `transfer` of his carries), an Out player not fresh (no shift),
  an Out player with no chart rank (no shift, reported as missed), a WR tie
  (equal split), a receiver below `min_own_volume` (unshifted, with a reason), the
  `max_multiplier` cap, a backup who is also Out (gives nothing, receives nothing),
  and a team-position with nobody Out (empty result).
- [x] **Step 2 - Row adjustment (pure).** `apply_usage_shift(row, shift)` scales
  `row["averages"]` for the row's market (`rushing_yards` and `rushing_attempts`
  by the carry multiplier; `receiving_yards` and `receptions` by the target
  multiplier) and records the multiplier on the row under `usage_shift`; every
  other market, position or a missing shift returns the row unchanged.
  *Done when:* tests cover each of the four markets, a passing and a fantasy row
  (unchanged), a QB row (unchanged), `shift=None` (same object back), and that the
  games count and other average fields are untouched.
- [x] **Step 3 - Repository loader.** `get_usage_shift_players(db, season, week)
  -> dict[(team_id, position), list[UsageShiftPlayer]]`: this week's RB/WR/TE
  chart rows joined to the merged injury report, each player's season-to-date
  carries and targets per game played over REG weeks before `:week` of the same
  season, and `fresh` from his team's latest REG game before `:week`. Out players
  with no chart row this week are returned with `depth_rank = None`.
  *Done when:* a test in `api/tests/test_nfl_usage_shift_repository.py` (fake
  session, as `test_nfl_volume_anchor_repository.py` does) pins that the volume
  window is `season = :season AND week < :week` with `game_type = 'REG'`, and maps
  a row to `UsageShiftPlayer`; a live read of one 2024 week finds at least one Out
  RB1 with a fresh absence and a charted RB2 (named in Results).
- [x] **Step 4 - Carry the inputs on replay rows.** `ReplayRow` gains
  `usage_shift_players: tuple[UsageShiftPlayer, ...] | None = None` (the row's own team-position), and `get_replay_rows` loads
  the week's inputs once and attaches its team-position's list to each row. No
  arm reads it yet.
  *Done when:* a test shows `replay_cases` gives identical cases for every
  existing arm with and without the new field, and the existing projection
  backtest tests pass unchanged.
- [x] **Step 5 - Counts-only CLI (2024 only).** `python -m
  app.backtest.nfl_usage_shift_counts --transfer 1.0 --min-own-volume 1.0
  --max-multiplier 3.0` loads 2024 replay rows week by week and prints, per
  market: rows shifted, the multiplier's median and range, receivers left
  unshifted by reason, and Out players missed (not fresh, or no chart row). It
  prints no projection error and no actual value, and exits with a message naming
  the holdout rule for any `--season` other than 2024. Counting in a pure helper
  with a test.
  *Done when:* the test covers the counts and the season guard, and the 2024
  output is recorded in Results.
- [x] **Step 6 - Verify and docs.** Passed 2026-11-22: web typecheck, 1871 tests and build; API 6621 passed (29 new). The CLI in `docs/commands.md` and `AGENTS.md`;
  run `npm --prefix web run verify && cd api && python -m pytest`.
  *Done when:* Verify passes.

## Files / areas

- `api/app/core/nfl_usage_shift.py` (new, pure)
- `api/tests/test_nfl_usage_shift.py` (new)
- `api/app/repositories/nfl.py` (the loader; `get_replay_rows` attaches inputs)
- `api/tests/test_nfl_usage_shift_repository.py` (new)
- `api/app/core/nfl_projection_backtest.py` (`ReplayRow` field)
- `api/tests/test_nfl_projection_backtest.py` (unchanged-output test)
- `api/app/backtest/nfl_usage_shift_counts.py` (new CLI)
- `docs/commands.md`, `AGENTS.md`

## Data / contracts

- **Load-bearing for 70b3:** `UsageShiftPlayer`, `UsageShift`, `usage_shifts(...)`
  and `apply_usage_shift(row, shift)` signatures, and `ReplayRow.usage_shift_players`
  (a tuple of the row's own team-position players, or None).
  70b3's arm is `apply_usage_shift(_production(row, season), shift)` with the
  shift from `usage_shifts(replay.usage_shift_players, ...)` for the row's player.
- `row["usage_shift"]`: `{"multiplier": float, "from": [player ids]}` on a shifted
  row, absent otherwise.
- No schema change and no stored data.

## Testing

- Pure: steps 1, 2 and 5's counting, with fixed fixtures.
- Repository: step 3's SQL bounds through a fake session, plus one live 2024 read
  as evidence.
- Regression: step 4 proves existing arms are unchanged without running any
  scored backtest.

## Notes for the AI

- **Holdout discipline:** nothing here reads a 2025 result or prints a projection
  error. Do not run `python -m app.backtest.nfl_projections` in this feature: it
  defaults to 2025 and prints errors. Step 4's proof is a unit test.
- **History floor:** the volume window is the current season only, before the
  week, so it never reaches below `PROJECTION_FIRST_HISTORY_SEASON`; say so in a
  comment on the SQL.
- **Served code stays unchanged.** Nothing in `app/services/` or the slate path
  imports `nfl_usage_shift`; no `NFL_PROJECTION_MODEL_VERSION` change.
- Scale `row["averages"]` after `_production`'s season blend, never before, so
  the arm in 70b3 stacks on what is served. Copy the dict; never mutate the
  caller's row.
- `out_ahead` stays a display field; match Out teammates by id from the loader.
- Use the merged `injury_reports` CTE so the rule is the slate's; for 2024 and
  2025 that is the nflverse report.
- No em dashes in new comments, docs or commit messages.

## Results

### Step 1 - shift computation

`app/core/nfl_usage_shift.py`: `usage_shifts` returns receivers only;
`missed_out_players` reports Out players who give nothing (`no_chart_row`,
`not_fresh`), so the "reported as missed" case is a second function rather than
a field on the result. Active rank counts every charted Out player ahead,
fresh or not, the same as `_AVAILABILITY_CTE`. Tests: 8 passed in
`tests/test_nfl_usage_shift.py`.

### Step 2 - row adjustment

`apply_usage_shift(row, shift)` scales only the market's own field in a copied
`averages` dict and adds `usage_shift`; the caller's row is never mutated, and an
unshifted row comes back as the same object. Tests: 17 passed in the file (9 new:
four markets, three untouched markets, a QB row, and `shift=None`).

### Step 3 - repository loader

`get_usage_shift_players` with `_USAGE_SHIFT_SQL`: this week's RB/WR/TE chart,
plus Out players with no chart row (`depth_rank = None`), Out from the merged
`injury_reports`, season-to-date carries and targets per game over REG weeks
before `:week`, and `fresh` from a stat row in the team's latest REG game before
`:week`. Tests: 2 in `tests/test_nfl_usage_shift_repository.py` (SQL bounds and
the mapping).

Live read of 2024 weeks 2-18, 2026-11-22, with illustration parameters only
(`transfer=1.0, min_own_volume=1.0, max_multiplier=3.0`; no result read, no
projection made). The first three RB1 cases:

| Week | Out RB1 | Receiver | Carry x | Target x |
|---|---|---|---|---|
| 2 MIA | Raheem Mostert (6.0 car/g) | Jeff Wilson (RB2, 5.0 car/g) | 1.40 | 1.00 |
| 4 WAS | Austin Ekeler (4.3 car/g) | Jeremy McNichols (RB2, 0.5 car/g) | 1.00 (below min) | 1.00 |
| 5 LV | Zamir White (12.2 car/g) | Alexander Mattison (RB2, 4.2 car/g) | 3.00 (capped) | 1.70 |

Across weeks 2-18: 105 givers; 151 Out players give nothing (99 not fresh, 52 no
chart row). The 2024 weekly chart can miss a real starter: MIA week 2 charts
Mostert and Wilson but not De'Von Achane, so Wilson is the receiver. That is a
property of the published 2024 chart, kept as is; 70b3 should read its 2024
results knowing it.

"Played" is a weekly stat row, so a player who took the field and recorded
nothing reads as not fresh; this undercounts givers slightly and never adds a
false one.

### Step 4 - inputs on replay rows

`ReplayRow.usage_shift_players` holds the row's own team-position list (a tuple),
not the whole week's mapping the spec named, so 70b3's arm needs no lookup:
`usage_shifts(replay.usage_shift_players, ...)` then `apply_usage_shift`.
`get_replay_rows` loads the week once and skips the query when the replay has no
RB, WR or TE markets (the kicker replay), and reads the team with
`row.get("player_team_id")`.

Tests: `test_usage_shift_players_on_a_replay_row_change_no_existing_arm` runs all
seven arms on two fixture rows (each arm yields 2 cases) with and without the
field and gets identical cases; the replay repository test now stubs the loader
and checks each row gets its own team-position's players or None. All 1,957 NFL
tests pass. No scored backtest was run.

### Step 5 - counts-only CLI

`python -m app.backtest.nfl_usage_shift_counts --transfer 1.0 --min-own-volume 1.0
--max-multiplier 3.0`, 2026-11-22 (illustration parameters, not a choice; about
15 minutes for 18 replay weeks):

```
Market              RB/WR/TE rows  Shifted  Median x         Range  Below min
rushing_yards                1550       24      2.80     1.11-3.00         11
rushing_attempts             1550       24      2.80     1.11-3.00         11
receiving_yards              5212      139      1.53     1.06-3.00         45
receptions                   5212      139      1.53     1.06-3.00         45

Out players who gave volume: 98
Out players missed: no_chart_row 55, not_fresh 106
```

`--season 2025` exits with "only 2024, the development season, may be read
here; 2025 is the usage-shift holdout and needs 70b3 and a separate yes".
Tests: 3 passed in `tests/test_nfl_usage_shift_counts.py`.

**Carry into 70b3:**
- **Sample size.** One season gives 24 shifted rows per rushing market and 139
  per receiving market. The existing projection adoption rule needs at least
  `MIN_PAIRED_CASES = 300` paired cases per market, so no market can pass it on
  2024 or on 2025 alone. 70b3 must pre-register a rule that fits this size
  (pooled markets, pooled seasons, or a rule judged on the shifted rows only)
  and say so before any scored run.
- **The cap binds on rushing.** The median rushing multiplier is 2.80 against a
  cap of 3.0: backups with few carries get large ratios. The cap and
  `min_own_volume` are real choices for 70b3, not details.
- Givers here (98) count only Out players whose receiver has a prop row in the
  replay; step 3's 105 counted every receiver.

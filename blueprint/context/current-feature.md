# Feature: NBA injury-aware minutes, development backtest

**From build-plan:** feature 65a (parent 65, NBA injury-aware minutes)
**Status:** spec approved 2026-11-11; not started

## Goal

`nba-reference-v1` projects a player from the mean of his last 20 played
games. Minutes only gate eligibility, and the stored ESPN injury report is
display only. When a rotation teammate is out (or comes back), a player's
minutes move, and the reference cannot see it.

65 tests one candidate: **`nba-minutes-v1`**, the reference projection plus a
per-minute rate times an expected-minutes change driven by teammate
availability. 65a builds the pure functions, fits one coefficient on 2023-24,
fixes two rules in a pre-registration commit (a development gate and the
forward rule 65c will apply), then scores the candidate once on 2024-25
against the reference. Nothing is served. The 2025-26 holdout is never read.

Sub-items (in `build-plan.md`):

- **65a** (this spec) - loader, pure functions, fit, rules, development run.
- **65b** - shadow freeze of `nba-minutes-v1` beside `nba-reference-v1`, only
  for markets that pass 65a's gate; no page shows it.
- **65c** - read-only forward verdict under the rule fixed here.

## Design reference

None. A CLI report, no UI.

## In scope

- A bounded roster loader with each box-score row's own team.
- `app/core/nba_minutes.py` (pure): rotation, point-in-time availability, the
  teammate-minutes delta, the player's minutes change and the adjusted
  projection.
- A least-squares fit of the one coefficient `k` on 2023-24.
- `app/core/nba_minutes_rule.py`: the development gate and the forward rule as
  tested constants, committed as a pre-registration before any 2024-25 score
  of the new arm.
- `python -m app.backtest.nba_minutes --season 2024` and one recorded run.

## Out of scope

- Serving, freezing or showing anything (65b), the forward verdict (65c).
- A usage (per-minute rate) adjustment. Field-goal, free-throw and turnover
  columns are stored, so a usage arm is possible, but one candidate at a time
  keeps the paired test clean; a later item can stack it on an adopted
  `nba-minutes-v1` as 20f's rule allows.
- P(over) for the new version. 20g1's fit is tied to `nba-reference-v1`
  (`FIT_PROJECTION_MODEL_VERSION`), so the new version serves no P(over) and
  enters no 20g4 ranking slice.
- Any change to `nba-reference-v1`, `project_line`, `NbaHistoryRow`,
  `get_prior_games`, 20f's constants, 20g1, 44 or their samples.
- Double-double and any market outside 20f's `BACKTEST_MARKETS`.
- Using the ESPN injury snapshots in the backtest: they start on 2026-10-21,
  so no development season has them. They enter in 65b.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Counts probe (no outcomes).** A one-off read, run from a
  scratch script outside `api/`, of 2023-24 and 2024-25 only:
  - box-score rows by `did_not_play` and `dnp_reason`, and team-games where a
    player with 15+ last-10 minutes has no row at all;
  - players whose rows change `team_id` within a season (trades);
  - distinct `status` values and counts in `nba_player_injuries` (any date).

  No minutes or stat is compared with a projection. *Done when:* the counts are
  pasted under Results and `OUT_STATUSES` below is confirmed or corrected from
  the status list (before Step 6's commit).

- [x] **Step 2 - Roster loader.** `get_roster_history(db, seasons) ->
  list[NbaRosterRow]` in `app/repositories/nba.py`: one row per box-score row
  in `REG`, `PIN` or `PST` games (`'nba'` on every `sport_*` reference), with
  `player_id`, `game_id`, `team_id` (the row's own, never
  `sport_players.team_id`), `game_date`, `did_not_play`, `minutes`, ordered by
  `game_date`, `game_id`. It raises `ValueError` for any season below
  `NBA_MINUTES_FIRST_HISTORY_SEASON` (2023).

  *Done when:* a recorded-SQL test (`_RecordingSession`) shows the `'nba'`
  literal, the game-type filter, the seasons parameter and the box-score
  `team_id`; a second test shows the floor refusal; a live call for 2023 and
  2024 prints row counts equal to Step 1's.

- [x] **Step 3 - Availability (pure).** In `app/core/nba_minutes.py`, for one
  player P in game G of team T (T is P's own row in G: who is on the floor is
  an outcome, which team he plays for is not):
  - **as-of history** is every roster row dated strictly before G's Eastern
    date (box scores load the next morning, as in 20f);
  - **rotation** is every other player j whose latest as-of row is for T and
    whose mean minutes over his last 10 as-of played games, `m_j`, is at least
    `ROTATION_MINUTES` (15.0; NULL minutes skipped);
  - **f_j** is the share of P's reference window (his last 20 as-of played
    games, 20f's `REFERENCE_GAMES`) in which j also played;
  - **a_j** is availability by a named source:
    - `previous_game` (the backtest source, leakage-free): 1 if j played in
      T's latest game before G's date, else 0;
    - `oracle` (diagnostic only, leaks): 1 if j played in G;
  - **team delta** `D = sum_j m_j * (a_j - f_j)`: negative when minutes
    P's window had are now vacated, positive when a teammate returns.
  - If any of P's reference-window games was for a team other than T, the
    result is `team_changed` and D is not used.

  *Done when:* unit tests cover a same-date game excluded; a teammate below
  15.0 excluded; a teammate traded away (latest row for another team)
  excluded; f_j over a window where j missed some games; each source on one
  history (`previous_game` sees a first missed game one game late, `oracle`
  sees it at once); `team_changed`; D = 0 when availability matches the
  window.

- [x] **Step 4 - Minutes change and projection (pure).** Same module:
  - `minutes_change(m_P, D, M, k) = clamp(-k * D * m_P / M, ±MAX_MINUTE_SHIFT)`,
    where `m_P` is 20f's `prior_minutes`, `M = m_P + sum_j a_j * m_j`, and the
    adjusted minutes `m_P + change` are capped at `MAX_MINUTES`;
  - `project_minutes_line(prior, availability, market, k) ->
    NbaMinutesProjection`: P's eligibility is 20f's (10 games, 20.0 minutes);
    the per-minute rate is the sum of the market's settled value
    (`line_only_value`) over the sum of minutes on reference-window rows where
    both are stored; the projection is `reference + rate * change`.
  - Flags: `team_changed`, `no_rate` (no row with both stored) return the
    reference projection unchanged with change 0; an ineligible player keeps
    the reference's own flag and a null projection.

  *Done when:* tests show the projection equals `project_line`'s exactly when
  change is 0; a known vacated case (worked by hand) matches; both clamps
  bind; a combo's rate equals the sum of its components' rates when every
  component is stored on the same rows; `no_rate` and `team_changed` fall back; eligibility matches
  `project_line` at 10 games and 20.0 minutes and just under each.

- [x] **Step 5 - The fit (pure).** `fit_rotation_coefficient(cases) -> float`:
  least squares through the origin of `y = actual minutes - m_P` on
  `x = -D * m_P / M`, over eligible played player-games with `previous_game`
  availability and `|x| > 0`. It raises below `MIN_FIT_CASES` (2,000), and the
  harness stops with `reject` if `k` falls outside `[0.0, 2.0]`. 2023-24 only;
  2023-24's own early games are ineligible until players have 10 prior games,
  since no 2022-23 is stored.

  *Done when:* a synthetic test recovers a known `k`; the refusal below 2,000
  and the out-of-range stop are tested; the fit takes no season argument (the
  harness passes 2023-24 cases only).

- [ ] **Step 6 - Rules and pre-registration checkpoint.**
  `app/core/nba_minutes_rule.py` holds the two rules below as constants and
  functions, importing 20f's `nba_adoption_verdict` and its constants rather
  than copying them, plus the version string, `OUT_STATUSES`,
  `AFFECTED_MINUTES` and the clamps. Show the owner the Steps 3-6 diff and the
  rules. **With the owner's yes in chat**, make a checkpoint commit before the
  harness exists or any 2024-25 score of the new arm is computed, and record
  its hash under "Pre-registration commit". Merge it `--ff-only` at
  `/complete`, never squashed, so the hash stays on `master`.

  *Done when:* constants tests pin every value below; each rule clause fails
  on its own in a test; the forward rule's clustered SE is tested on a small
  hand-computed sample; the commit hash is recorded.

- [ ] **Step 7 - The harness and the development run.**
  `app/backtest/nba_minutes.py`, `--season` (only 2024 accepted; 2025 or later
  is an argparse error naming the holdout). It loads roster and projection
  history for 2023 and 2024 only, fits `k` on 2023-24, then replays 2024-25
  and prints:
  - `k`, its case count, and the share of eligible player-games affected
    (`|change| >= AFFECTED_MINUTES`), by market;
  - per market, on affected cases: n, reference MAE, candidate MAE, change,
    paired diff, SE, bias of each, and the development-gate verdict;
  - the unaffected count, with a check that their paired diff is exactly 0;
  - the same table with `oracle` availability, headed "diagnostic, leaks the
    game's own box score, no verdict".

  *Done when:* a report test on synthetic cases checks one row and a verdict;
  the live run completes and its output and timing are pasted under Results
  with the list of markets that pass to 65b (or "none: 65 closes at 65a").

## Files / areas

- New: `api/app/core/nba_minutes.py`, `api/app/core/nba_minutes_rule.py`,
  `api/app/backtest/nba_minutes.py`, `api/tests/test_nba_minutes.py`,
  `api/tests/test_nba_minutes_rule.py`, `api/tests/test_nba_minutes_harness.py`
- Changed: `api/app/repositories/nba.py` (`get_roster_history`),
  `api/tests/test_nba_repository.py`
- Read only: `api/app/core/nba_projection_backtest.py`,
  `api/app/core/nba_projection.py`, `api/app/core/nba_line_only.py`,
  `api/app/core/nba_injuries.py`
- Data: none written. No migration.

## Data / contracts

**Data sources.**

| Use | Source | Seasons |
|---|---|---|
| Player history, rates, eligibility | `nba_player_game_stats` + `sport_games` (hoopR, 20b) | inputs 2023-24 on |
| Team and availability per game | the same rows' `team_id`, `did_not_play`, `minutes` | 2023-24, 2024-25 here |
| Forward "out" (65b) | `nba_injury_snapshots` / `nba_player_injuries` (ESPN, 42c), last batch with `fetched_at` before the freeze and before tip | 2026-27 on |
| Settled actuals | `line_only_value` on the game's box score, as 20c settles | |

**Load-bearing constants (65b and 65c read them):**

```python
NBA_MINUTES_MODEL_VERSION = "nba-minutes-v1"
NBA_MINUTES_FIRST_HISTORY_SEASON = 2023   # 2023-24, the first stored season
FIT_SEASON = 2023                        # 2023-24: k is fitted here only
DEVELOPMENT_SEASON = 2024                # 2024-25: scored once by the gate
ROTATION_MINUTES = 15.0
MAX_MINUTE_SHIFT = 10.0
MAX_MINUTES = 42.0
AFFECTED_MINUTES = 1.0                   # |change| that makes a case "affected"
OUT_STATUSES = frozenset({"Out", "Suspension"})  # Step 1 status list; Day-To-Day is not out
```

`NbaMinutesProjection` carries `model_version`, `projection`, `reference`,
`minutes_change`, `prior_minutes`, `rate`, `out_player_ids`, `flags`; 65b
freezes `minutes_change`, `out_player_ids` and the snapshot time in
`feature_snapshot`.

**Forward availability (fixed now, built in 65b):** `a_j = 0` when j is in
the snapshot with a status in `OUT_STATUSES`; otherwise the `previous_game`
value. So the forward version is the backtest's source plus the report's
information, never less. A scratch after the freeze is not seen, and that is
part of what 65c measures.

**Metric.** Mean absolute error of the projection against the settled actual,
per market, paired on (player, game, market) against `nba-reference-v1`, on
affected cases only (unaffected cases are identical by construction).

**Development gate (65a, applied once to 2024-25).** A market passes to 65b
only if 20f's `nba_adoption_verdict` returns `adopt` for the candidate against
`reference` on that market's affected, eligible 2024-25 cases with
`previous_game` availability: at least 300 paired cases, MAE at least 1.0%
lower, and the paired mean |error| difference below zero by more than 2 SE.
The `oracle` table never decides anything. A failed market is not refitted or
rescored under this version.

**Forward adoption rule (65c, pre-registered here).** For each market 65b
freezes:

1. **Pairs.** Frozen `nba-minutes-v1` and `nba-reference-v1` rows on the same
   `prop_line_id`, deduplicated to one per (player, game, market) by the
   latest row generated before tip; settled by `line_only_value`; affected
   means the frozen `|minutes_change| >= 1.0`; DNP, voided and unsettled lines
   excluded.
2. **Fixed sample.** From the first 65b freeze, through the end of the Eastern
   date on which the market's 300th affected pair settles, extended to at
   least 28 days if that comes sooner. Before then the verdict is
   `insufficient`.
3. **Adopt** only if, on that sample, the candidate's MAE is at least 1.0%
   lower than the reference's and the paired mean |error| difference is below
   zero by more than 2 standard errors, the SE clustered by game (pairs from
   one game are not independent once a teammate's absence moves them all).
   Otherwise `reject`.

A verdict is final for `nba-minutes-v1`; any changed constant or coefficient
is a new version with a new sample. `adopt` means only that a later item may
serve the version on the page (and fit its own P(over)); it stays gray until
a 20g4 slice for that version reads `adopt`.

**Holdout:** 65 makes no read of 2025-26 for scoring or fitting; the harness
refuses it. 2025-26 box scores are only prior-game inputs for 2026-27 forward
rows in 65b, as for every served NBA projection.

## Testing

- Test gate on: Step 2 recorded-SQL tests, Steps 3-6 unit tests, Step 7 a
  report test. Step 1 is counts only.
- `cd api && .venv\Scripts\python.exe -m pytest` after each step; Verify
  before any checkpoint.
- No web change.

## Notes for the AI

- **Never read 2025-26 or later as a scored season.** If anything seems to
  need it, stop and ask; a holdout read needs a separate yes in chat.
- Do not run Step 7 before Step 6's commit exists. Fitting on 2023-24 in Step
  5 tests is synthetic only; the real fit runs inside Step 7.
- A team's game list comes from the roster rows, not `sport_players`, which is
  last-write-wins (20f).
- Load both seasons once and walk them in Python (about 70,000 rows); no
  per-game queries. If the run exceeds a few minutes, report before
  optimizing.
- Leakage checks to keep in the tests: nothing dated on G's date is an input;
  `oracle` is used only in the diagnostic table; `k` never sees 2024-25.
- `X | None`, no `Any`, dataclasses inside, `app/core` pure, repositories own
  SQL, no em dashes, comment only the why.
- Pre-registration commit: merge `--ff-only` (memory: preregistration-merge).
- Interview guide: update at `/complete` only with the measured result.

## Pre-registration commit

Not yet made (Step 6).

## Results

**Step 1 counts (2026-11-11, scratch script outside `api/`, about 5 s).** No
minutes or stat was compared with a projection.

| | 2023-24 | 2024-25 |
|---|---|---|
| Box-score rows (non-`PRE`) | 35,004 (1,319 games) | 35,198 (1,321 games) |
| Played / DNP rows | 28,366 / 6,638 | 28,348 / 6,850 |
| DNP rows "COACH'S DECISION" | 5,774 | 5,468 |
| Played rows with NULL minutes | 0 | 83 |
| Players with 2+ teams in the season | 82 | 86 |
| Rotation player-games (15+ last-10 minutes, latest row for the team) with **no row** in the team's game | 4,267 (1,969 of 2,638 team-games) | 8,547 (2,283 of 2,642 team-games) |

Row counts match 20f's. What they settle:

- **An injured player usually has no row at all,** not a DNP row: DNP rows
  are almost all coach's decisions, and injury reasons appear only in the
  dozens. So "j played in a game" means a played row exists; a missing row and
  a DNP row both read as not played, as Step 3 already defines it.
- **A traded or long-injured player keeps his latest row for his old team,**
  so he stays in that team's rotation with `a_j = 0`. That is the intended
  reading: his minutes are vacated, and `f_j` falls to 0 as he leaves P's
  20-game window, so his effect fades without a special case. 2023-24's lower
  missing count reflects its rotation building from an empty history (no
  2022-23 stored).
- **ESPN statuses** across 83 stored batches (2026-10-21 to 2026-11-11):
  `Out` 5,610, `Day-To-Day` 1,621, `Suspension` 3. `OUT_STATUSES` is
  corrected to `{"Out", "Suspension"}` (a suspended player cannot play);
  `Day-To-Day` stays available.

# Feature: NFL snap counts

**From build-plan:** feature 19m
**Status:** complete (2026-09-19); snap share adopted for RB/TE anytime TD

## Goal

Store each offensive player's per-game snap count and snap share from NFLverse,
keep it fresh on the Tuesday ingest, and test pre-week snap share as an **RB and
TE** anytime-TD signal in the 19j backtest. Snap share goes into the anytime-TD
probability **only if** the pre-registered adoption rule below passes on the
2025 holdout. Snap share should describe an RB's or TE's role more steadily than
targets or touchdowns do, but this feature tests that idea. It does not assume it.

## In scope

- Migration `0027`: a new `nfl_player_snap_counts` table, one row per player per
  game.
- Pure parsers for NFLverse `snap_counts_{season}.csv` (keyed by PFR id) and for
  the PFR-to-gsis id map from NFLverse `players.csv`.
- An idempotent ingest command, a 2024 to 2026 backfill, and a Tuesday
  `nfl-ingest.yml` step.
- Pure snap-share math in two forms: season-weighted, and the last 4 games.
  It returns an expected TD rate and a blended probability.
- Extend the 19j backtest harness with snap share. Fit on 2024 and score once on
  the 2025 holdout, for RB and TE.
- **Only if adopted:** wire the blend into `/nfl/slate` and `/nfl/projections`
  for RB and TE anytime-TD lines, bump the model version, and show snap share in
  the anytime-TD evidence panel.

## Out of scope

- Snap share for QB and WR. Both backtest arms leave them unchanged. The plan
  names RB and TE, and deciding that before seeing 2025 keeps the holdout honest.
- Snap share for yardage, reception, or any market other than anytime TD. The
  only backtest harness today is anytime TD. A yardage harness would be a
  separate feature.
- Defensive and special-teams snaps. Only `offense_snaps` and `offense_pct` are
  stored.
- Showing snap share on the slate when it is **not** adopted. If you want it as
  display-only context anyway, that is a separate follow-up, like 19l.
- Adding a `pfr_id` column to `nfl_players`. The PFR-to-gsis map is rebuilt from
  `players.csv` on every run.
- Fixing the TD-history gap this feature exposes. Player-games with snaps but no
  weekly-stat row never enter the production TD baseline. See Notes.
- Postseason games, and 2023 or earlier seasons (the same reason as 19j).

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Table.** Migration `0027` creates `nfl_player_snap_counts`
  (shape in Data / contracts), with a downgrade.
  *Done when:* `alembic upgrade head` reaches `0027`, and `downgrade -1` then
  `upgrade head` both run cleanly.

- [x] **Step 2 - Parsers.** Add a new `app/ingest/nflverse_snap_counts.py` with
  two pure functions:
  - `parse_pfr_gsis_map(lines) -> dict[str, str]` maps from `players.csv`. It
    drops rows missing either id, and drops any PFR id that maps to more than one
    gsis id.
  - `parse_snap_counts(lines, season) -> NflverseSnapSeason(game_ids, games)`
    keeps rows where `game_type == "REG"`, the season matches, and `position` is
    QB, RB, WR, TE, or FB. It skips rows without a PFR id, game id, or team. It
    turns a blank snap value into `None` and keeps `0` as `0`. It keeps the later
    row for a duplicate player-game.

  `game_ids` holds every REG game in the file, so Step 3 knows which games to
  replace.
  *Done when:* tests run on fixtures that use the real published headers. They
  cover kept fields, `offense_pct` as a fraction (`0.79`, not `79`), the REG,
  season, and position filters, skips, duplicates, blank versus zero, and the
  ambiguous-id drop. The real 2025 file parses to about 6,980 skill rows over
  272 games.

- [x] **Step 3 - Ingest, backfill, and cron.** Add a fetch for both files,
  `run(season, dry_run)`, and a CLI:
  `python -m app.ingest.nflverse_snap_counts [--season N] [--dry-run]`. The
  season defaults to `current_nfl_season`.

  A repository function `replace_snap_counts` works in one transaction. It
  deletes the stored rows for the file's games, then inserts through the id map,
  `nfl_players`, `nfl_games`, and `nfl_teams` joins. It never creates a player,
  game, or team. It returns counts of rows stored, rows skipped because the PFR
  id is unmapped, rows skipped because the player is not stored, and rows
  skipped because the game is not stored.

  The whole season parses before any write. A file that is not published yet
  raises `SeasonNotPublished(season, "snap counts")`. Backfill 2024, 2025, and
  2026. Add the step to `nfl-ingest.yml` after the red-zone step.
  *Done when:* a repository test proves the scoped replace (other games stay
  untouched), skip-not-create, and that a rerun leaves identical rows. The
  backfill prints stored and skipped counts per season, and a 2025 rerun leaves
  an identical checksum. The workflow parses. A spot check matches the file:
  Alvin Kamara, `2025_01_ARI_NO`, 59 snaps, 0.79.

- [x] **Step 4 - Pure snap-share math.** Add a new `app/core/nfl_snap_share.py`:
  - `NflSnapSeason(season, games, share)`.
  - `season_snap_share(seasons, line_season, position_share)` recency-weights
    with `TD_SEASON_WEIGHTS` and shrinks toward the position with
    `SNAP_PRIOR_GAMES = 2` (amended 2026-09-19, user decision B, before any
    backtest run: the TD prior of 10 would give four recent games only 29% of
    the weight). It mirrors `red_zone_rates`.
  - `recent_snap_share(recent_shares, position_share, window=4)` takes the
    latest `window` pre-week games, even across a season boundary, and shrinks
    toward the position with the same `SNAP_PRIOR_GAMES`.
  - `NflSnapCoefficients(intercept, per_share)`.
  - `snap_td_probability(historical_rate, share, coefficients, blend_weight)`
    blends TD history with `intercept + per_share * share` and returns a
    Poisson probability.

  Nothing is wired into the API yet.
  *Done when:* unit tests prove these points:
  - a blend weight of `0` exactly reproduces `anytime_td_rate`'s probability;
  - a higher share raises the probability when `per_share > 0`;
  - a player with no snap history falls back to the position share;
  - the recent form uses only the latest `window` games;
  - negative, above-1, and non-finite shares are clamped to `[0, 1]`.

- [x] **Step 5a - Backtest core.** In `app/core/nfl_td_backtest.py`, cases gain
  pre-week snap evidence: per-season snap seasons, the player's recent shares in
  game order, and the position share from the same season the position TD rate
  uses. Snap evidence comes from **all** stored snap rows for the player, even
  games without a weekly-stat row. Evaluated cases stay exactly the current
  weekly-stat rows, so the baseline arm is unchanged. Add a
  `snap_share_probability(case, coefficients_by_position, form, blend_weight)`
  that returns `baseline_probability(case)` for QB and WR.
  *Done when:* unit tests prove these points:
  - snap evidence never uses the same or a later week, for the player and for
    the position;
  - a snap-only game (no weekly row) adds snap evidence but no case and no TD
    history;
  - QB and WR probabilities equal the baseline;
  - the existing 19j tests still pass unchanged.

- [x] **Step 5b - Backtest runner.** Add a repository query that returns every
  regular-season snap row (player, position, season, week, `offense_pct`). Add a
  `--signal snap-share` mode to `app/backtest/nfl_anytime_td.py`, keeping
  red-zone as the default. All fitting uses 2024 only:
  1. **Coefficients, per position (RB, TE):** fit
     `LinearRegression(positive=True)` of same-game `touchdowns` on same-game
     `offense_pct` over weekly-stat rows that have a snap row.
  2. **Form and blend weight:** choose from {season-weighted, last 4 games} times
     weights `0.0` to `0.6` in steps of `0.1`, by 2024 RB+TE log loss.

  Then score that one configuration on 2025.
  *Done when:* the CLI prints the per-position coefficients, the chosen form and
  weight, and a baseline-versus-snap table (log loss, Brier, games, mean
  predicted versus actual). The table has rows for the 2024 fit set (RB+TE), the
  2025 holdout (RB+TE), 2025 RB, and 2025 TE. The red-zone mode output is
  unchanged. The runner gets no test of its own, because its pure pieces are
  covered in 5a.

- [x] **Step 6 - Record the result and decide.** **Decision: adopted** (see
  Implementation notes). Run the backtest and paste the
  full output into Implementation notes.
  **Adoption rule (pre-registered):** adopt only if all three hold on the 2025
  holdout:
  1. RB+TE log loss improves.
  2. RB+TE Brier improves.
  3. Neither RB nor TE log loss gets worse. Both have well over 500 evaluated
     games.

  If adopted, freeze the coefficients, form, and weight as named constants, with
  a comment that cites the backtest date and the holdout numbers. If not
  adopted, write down why, mark Steps 7 and 8 skipped, and go to Step 9. The
  user approves the decision before either path continues.
  *Done when:* Implementation notes hold the output, each rule line evaluated,
  and the user's decision.

- [x] **Step 7 - (Adopted only) Wire snap share into the anytime-TD API.** Extend
  `_td_history` in `repositories/nfl.py` to return pre-week snap evidence (and
  the position share) under the same `season < s OR (season = s AND week < w)`
  predicate. Route RB and TE anytime-TD baselines in `routers/nfl.py` through
  `snap_td_probability` with the frozen constants, so `/projections` and
  `/slate` still agree. Bump `NFL_PROJECTION_MODEL_VERSION`. Slate lines gain a
  nullable `snap_share` (the pre-week share the model used) and
  `snap_share_games`. Both are `null` except on RB and TE anytime-TD lines.
  Add a new flag, `snap_share_unavailable`, for an RB or TE anytime-TD line with
  no snap evidence.
  *Done when:* repository tests prove that current-week and future snap rows are
  excluded. A router-level test proves `/projections` and `/slate` agree for one
  RB. A live `/nfl/slate` call shows the new model version, `snap_share` on RB
  and TE anytime-TD lines, `null` everywhere else, and unchanged QB and WR
  anytime-TD probabilities.

- [x] **Step 8 - (Adopted only) Show it on `/nfl`.** Add the types to
  `web/src/types/nfl.ts`. The anytime-TD evidence panel gets one row: "Snap share:
  68% (last 4 g)" or "(season-weighted, 14 g)". Add a short label for the new
  flag. Any formatter goes in `src/utils/` with a test.
  *Done when:* web tests and the build pass. A screenshot of an RB anytime-TD
  panel matches the API values. A line without evidence shows the unavailable
  state, not `0%`.

- [x] **Step 9 - Verify.** Run the full API tests, web tests, and web build.
  Confirm migration `0027 (head)`.
  *Done when:* all three pass. On the rejected path, the model version is
  unchanged and the 2026 week 2 anytime-TD output is identical to `master`, the
  same check 19j ran. On the adopted path, a `/nfl` screenshot shows the snap
  row.

## Files / areas

| Path | Change |
|---|---|
| `api/app/db/migrations/versions/0027_nfl_player_snap_counts.py` | New table, with downgrade |
| `api/app/ingest/nflverse_snap_counts.py` | New: two parsers, fetch, CLI |
| `api/app/repositories/nfl.py` | Scoped replace, backtest snap query, and (adopted only) pre-week snap aggregates in `_td_history` |
| `api/app/core/nfl_snap_share.py` | New: pure snap-share rates and blended TD probability |
| `api/app/core/nfl_td_backtest.py` | Snap evidence on cases, snap-share predictor |
| `api/app/backtest/nfl_anytime_td.py` | `--signal snap-share` mode |
| `.github/workflows/nfl-ingest.yml` | Tuesday snap-count step |
| `api/app/routers/nfl.py`, `api/app/schemas/nfl.py` | (Adopted only) blended RB/TE baseline, evidence fields, flag |
| `web/src/types/nfl.ts`, `web/src/pages/NflIntelligencePage.tsx`, `web/src/utils/nflLabels.ts` | (Adopted only) evidence row and flag label |
| `api/tests/test_nflverse_snap_counts.py`, `test_nfl_snap_share.py`, `test_nfl_td_backtest.py`, `test_nfl_repository.py` | Parser, math, backtest, and write coverage |

## Data / contracts

**Sources.** Both are public, with no key and no quota.

- `.../releases/download/snap_counts/snap_counts_{season}.csv`. PFR data, one row
  per player per game, about 2.4 MB a season. Header: `game_id, pfr_game_id,
  season, game_type, week, player, pfr_player_id, position, team, opponent,
  offense_snaps, offense_pct, defense_snaps, defense_pct, st_snaps, st_pct`.
  - `game_id` is the NFLverse id, matching `nfl_games.nflverse_game_id`.
  - `offense_pct` is a fraction from 0 to 1.
  - Team codes are NFLverse codes (`LA`, `JAX`).
  - As of 2026-09-18, 2026 has weeks 1 and 2 (449 skill rows).
- `.../releases/download/players/players.csv`, about 7 MB. It supplies
  `pfr_id -> gsis_id` for 22,582 players, with no PFR id mapped to two gsis ids.
  Measured coverage of skill players in the snap files:

  | Season | Mapped |
  |---|---|
  | 2024 | 628 of 631 |
  | 2025 | 638 of 641 |
  | 2026 | 422 of 423 |

  The unmapped players are fringe, with at most 45 snaps in any game.
  `roster_weekly` also carries `pfr_id`, but it covers fewer players and
  disagrees with `players.csv` on 3 ids, so `players.csv` is the one source.

**Schema (load-bearing, item 17 and any later role model read it), migration
`0027`:**

`nfl_player_snap_counts`
- `player_id` -> `nfl_players.id` (cascade), `game_id` -> `nfl_games.id`
  (cascade); **unique (`player_id`, `game_id`)**
- `season`, `week` smallint (denormalized from the game, for as-of queries)
- `team_id` -> `nfl_teams.id`
- `offense_snaps` smallint NULL, `offense_pct` real NULL. The value is NULL when
  the file leaves it blank and `0` when the player took no offensive snaps.
- `updated_at` timestamptz
- Index on (`player_id`, `season`, `week`) for the pre-week lookup.

**Why a table, not columns on `nfl_player_weekly_stats`.** About 900 to 1,000
skill player-games a season have snaps but no weekly-stat row. Around 190 of
them are TEs with 20% or more of the snaps: blocking roles with no catch. That
is exactly the role evidence this feature is about.

**Missing means unknown.** A weekly-stat row with no snap row (an unmapped id,
or a game not loaded yet) is not evidence. It is never treated as a share of 0.

**Backtest contract.** The 19j harness is extended, not forked. The baseline arm
stays the production `anytime_td_probability` unchanged.

**Adopted-path API (Steps 7 and 8 only).** `NflSlateLineSchema` gains nullable
`snap_share` (float, 0 to 1) and `snap_share_games` (int). Both are `null` except
on RB and TE `anytime_touchdown` lines. New flag: `snap_share_unavailable`.

## Testing

The test gate is on. These steps ship tests in the same diff:

- Step 2: both parsers.
- Step 3: scoped replace, skip-not-create, idempotent rerun.
- Step 4: pure math, including that weight `0` equals production, the
  position fallback, the recent window, and clamping.
- Step 5a: pre-week leakage guard, snap-only games, and QB and WR unchanged.
- Step 7: as-of exclusion, and `/projections` agreeing with `/slate`.
- Step 8: any new `src/utils/` formatter.

Tests make no live downloads. The backfill, rerun checksum, spot check, and
backtest run are explicit verification runs against the local database. Run the
API tests from `api/` with `.venv\Scripts\python.exe -m pytest`, and the web
checks from `web/` with `npm run test` and `npm run build`.

## Notes for the AI

- The backtest decides. Do not wire snap share into the API before Step 6's
  decision is recorded and approved. A rejected result is a valid outcome of
  this feature.
- Do not tune on 2025. Coefficients, form, and weight all come from 2024. The
  RB and TE scope and the adoption rule are fixed here, before any 2025 number
  is seen. If a TE-only or other variant looks tempting after the run, write it
  down as a pre-registered test for 2026. Do not adopt it here.
- QB and WR anytime-TD probabilities must be identical in both arms and in
  production, adopted or not.
- `core/` stays pure. The scikit-learn fit lives in the runner, and production
  reads frozen constants only.
- Follow the 19k and 19l shapes:
  - an `Iterable[str]` parser;
  - a whole-file parse before one transaction;
  - skip and count unknown players, games, and teams, never create them;
  - `SeasonNotPublished(season, asset)`.
- Keep `NULL` distinct from `0` from end to end, as in 19h and 19j.
- **Finding to record, not fix:** the production TD baseline counts only games
  with a weekly-stat row. A player's zero-TD games with snaps but no stats
  (mostly blocking TEs) never enter their TD history, which may overstate their
  TD rate. Note the measured size in Implementation notes as a candidate
  `/fix`. Changing the baseline here would move the comparison target.

## Implementation notes

- Step 1: migration `0027` upgrade, downgrade, and re-upgrade clean; API tests 901 passed.
- Step 2: `HB` kept beside `RB` (49 rows in 2025 use it). Real files parse to
  7,028 / 7,030 / 452 skill rows over 272 / 272 / 17 games; the id map has
  22,582 entries. No blanks, `NA`s, or duplicate player-games in the real files.
- Step 3: backfill stored 6,973 (2024), 6,981 (2025), 433 (2026); unmapped 18 /
  18 / 1; player not stored 37 / 31 / 18; no unknown games or teams. A 2025
  rerun replaced 6,981 with 6,981 and left an identical value checksum. Kamara
  `2025_01_ARI_NO`: 59 snaps, 0.79. API tests 914 passed.
- Step 4: spec amended before any backtest run (user choice B): both forms
  shrink with `SNAP_PRIOR_GAMES = 2`, not `TD_PRIOR_GAMES`. Non-finite shares
  count as 0, like red-zone inputs. API tests 924 passed.
- Step 5a: `build_cases` replays every week that has weekly or snap rows;
  within-week case order is unchanged, so the red-zone backtest output is
  byte-identical to 19j's. API tests 932 passed.
- Step 5b: `get_snap_rows` plus `--signal snap-share`. First run (2026-09-19,
  fit 2024, holdout 2025, about 6 s):

  ```
  Coefficients (fit 2024, TDs per game = intercept + per_share * snap share):
    RB: intercept -0.0463, per_share 0.9656
    TE: intercept -0.0184, per_share 0.3290
  Form and blend weight (by 2024 RB+TE log loss): season, 0.6

  set             games    LL base   LL snap   LL diff   Br base  Br snap   Br diff  p base p snap actual
  2024 RB+TE       1780    0.48935   0.47857  -0.01078   0.15702  0.15499  -0.00203   0.208  0.205  0.221
  2025 RB+TE       2584    0.47489   0.46577  -0.00911   0.15199  0.14989  -0.00210   0.219  0.207  0.211
    2025 RB        1410    0.50581   0.49424  -0.01157   0.16568  0.16284  -0.00283   0.267  0.259  0.247
    2025 TE        1174    0.43774   0.43159  -0.00615   0.13554  0.13433  -0.00121   0.160  0.145  0.169
  ```

  Two observations, not acted on (both would be changes after the holdout was
  printed): the chosen weight `0.6` is the top of the pre-registered grid, and
  `positive=True` constrains the slopes but not the intercepts, so both are
  slightly negative (a near-zero share clamps to a rate of 0). API tests 933
  passed.
- Step 6 decision (2026-09-19, approved by the user): **adopted.** The rule,
  line by line, on the 2025 holdout:
  1. RB+TE log loss improves: yes, 0.47489 -> 0.46577 (-0.00911).
  2. RB+TE Brier improves: yes, 0.15199 -> 0.14989 (-0.00210).
  3. Neither RB nor TE log loss worsens: yes, RB -0.01157 (1,410 games), TE
     -0.00615 (1,174 games).

  Caveat noted at decision time: snap share lowers TE mean predictions (0.160 ->
  0.145) below the actual 0.169, so TE calibration in the mean is worse even
  though log loss and Brier improve. Frozen in `app/core/nfl_snap_share.py`:
  `SNAP_SHARE_BLEND_WEIGHT = 0.6`, season-weighted form, `SNAP_SHARE_COEFFICIENTS`
  RB (-0.046260, 0.965586), TE (-0.018431, 0.328985), from the 2024 fit at
  6-decimal precision. API tests 934 passed.
- Step 7: the pure composition lives in `app/core/nfl_snap_share.py`
  (`production_anytime_td_probability`, `snap_evidence`); the router's
  `_anytime_td` routes both `/projections` and `/slate` through it. The
  repository's `_attach_snap_history` reads the snap table alone (so snap-only
  games count) under the TD cutoff, with the position share from the row's
  `baseline_season`. Model version `opponent-dvp-usage-snap-v1`. The existing
  season-blend slate tests now use a WR fixture (a TE would be blended). Live
  2026 wk2, branch versus `master` (scratch worktree, same database):
  - 8,401 lines, identical ids. 8,010 non-RB/TE-TD lines identical in
    projection, edge, and flags; no snap fields appear on them.
  - 391 RB/TE anytime-TD lines: 353 projections changed, 38 unchanged after
    rounding. Mean projection RB 0.323 -> 0.320, TE 0.198 -> 0.178. No line
    lacks snap history this week, so `snap_share_unavailable` fires on none.
    Examples: Cade Otton TE 0.879 share (31 g) 0.16 -> 0.23; Trey McBride TE
    0.852 (34 g) 0.27 -> 0.23; Tucker Kraft TE 0.783 (26 g) 0.36 -> 0.30.
  - `/projections`: 21,429 rows; only RB/TE anytime-TD values changed (328),
    all 21,076 others identical.
  - The anytime-TD baseline from `/projections` equals the slate's for all 771
    anytime-TD lines (391 RB/TE, 380 other). The slate's displayed projection
    also carries market, home, and opponent adjustments, which is why it matched
    `/projections` on only 168 of 771 lines before this feature too.

  API tests 943 passed.
- Step 8: `web/src/utils/nflSnapShare.ts` (`snapShareLabel`, 4 tests) formats
  "51% · 28 g, season-weighted", "No snap history (position average used)" for
  zero games (never "0%"), and null for lines snap share does not feed; a real
  0% share with games stays "0%". `SnapShareEvidence` renders the row in the
  evidence panel only when the label is non-null. `snap_share_unavailable` has
  a short label, color, and long label. Web tests 88 and build passed. Live
  (`.playwright-mcp/19m-irving-snap-panel.png`, CLE @ TB): Bucky Irving RB
  anytime TD panel shows "Snap share 51% · 28 g, season-weighted", matching the
  API (`snapShare` 0.509, `snapShareGames` 28, model
  `opponent-dvp-usage-snap-v1`); Cade Otton's receiving-yards panel has no snap
  row. No 2026 week 2 RB/TE line lacks snap history, so the unavailable state is
  covered by the unit test only. Console: only the pre-existing favicon 404.
- Step 9 (adopted path, 2026-09-19): API tests 943 passed; web tests 88 passed;
  `npm run build` passed; migration `0027 (head)`. The `/nfl` snap row
  screenshot is Step 8's. The Step 7 branch-versus-`master` check stands: only
  RB/TE anytime-TD values changed. Scratch worktree removed.
- **Finding for a later `/fix` (measured, not fixed):** RB/TE player-games with
  offensive snaps but no weekly-stat row, which never enter the production TD
  history:

  | Season | RB (20%+ snaps) | TE (20%+ snaps) |
  |---|---|---|
  | 2024 | 84 (10) | 422 (198) |
  | 2025 | 65 (17) | 384 (191) |
  | 2026 | 10 (2) | 26 (17) |

  Every one is a zero-TD game (a TD would create a stat row), so the TD
  baseline likely overstates rates for blocking TEs. Snap share already sees
  these games. A fix changes the baseline both backtest arms compare against,
  so it needs its own backtest run.

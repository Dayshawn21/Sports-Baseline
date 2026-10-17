# Feature: Current-season NFL data

**From build-plan:** feature 19d
**Status:** complete (2026-09-15), squash-merged from `feature/19d-current-season-nfl-data`

## Outcome

- **Seasons loaded:** 2024 18,112 rows, 2025 18,522, 2026 1,117 (week 1); `nfl_players` 2,614.
- **Linking:** 2,685 of 2,685 lines linked after the full-name resolver fix, 0 unmatched on the 2026 week-2 slate, every link an exact full-name match.
- **Week-2 baselines:** 252 lines from 2025, 20 from 2026, 1 from 2024, shown per row and summarized in the banner.
- **Follow-up:** nothing reloads NFL stats on a schedule, so stale flags only clear if `nflverse` and `--relink` are re-run weekly. Drafted as a separate fix.

## Goal

Load 2025 and 2026 player stats so baselines describe the season the market is
pricing, and choose which season a baseline comes from rather than averaging
every loaded season together.

Today every baseline is a 2024 average priced against a 2026 line, and the slate
says so in an amber banner. The fix is not only more data: the current baseline
query averages across all loaded seasons and reports `MAX(season)`, so loading
2025 and 2026 would make the warning disappear while the average stayed mostly
2024. That would be worse than the honest warning it replaced.

## Background, already verified

The ingest points at a legacy NFLverse asset that is both frozen and filtered:

| Asset | Seasons | 2024 REG rows | 2024 players |
|---|---|---|---|
| `player_stats/player_stats.csv` (current) | 2023-2024 only | 5,597 | 601 |
| `stats_player/stats_player_week_<season>.csv` | 2022-2026 | **18,130** | **1,997** |

So the legacy file is missing more than recent seasons: it appears to carry only
fantasy-relevant skill players, which is why kickers such as `Harrison Butker` and
`Wil Lutz` were unmatchable in 19c. Re-importing 2024 from the per-season asset
roughly triples coverage on its own.

Confirmed available: 2022 (17,981 REG), 2023 (17,806), 2024 (18,130), 2025
(18,540, weeks 1-18), 2026 (1,041, week 1 only, since week 2 is being played).
The newer file carries 150 columns against the legacy 53, and every column the
parser needs is present. The one rename is `recent_team` to `team`, which
`parse_player_stats` already tolerates via `row.get("recent_team") or row.get("team")`.

## In scope

- Point stats ingest at the per-season asset, keeping the parser's column contract.
- Load 2025 and 2026, and re-import 2024 for the wider player set.
- Choose a baseline season per player instead of averaging every season together.
- Report the season a baseline actually came from, and flag a fallback honestly.
- Re-run linking so newly present players (kickers, rookies) stop being unmatched.
- Surface the chosen season per row on the slate.

## Out of scope

- **A real projection model.** Season choice here is a selection rule, not a model. Weighted blends, opponent adjustment, and regression to the mean are 19e.
- **Backfilling 2022 and 2023.** Available, but nothing needs them until 19e wants a training set.
- **Post-season stats.** `season_type` stays filtered to `REG`.
- **Fixing `nfl_players.team_id` last-write-wins.** Still a known defect; a season-aware roster is its own change.
- **`nfl_games.start_utc` holding naive local time.** Pre-existing in `_schedule_start`, worked around in 19c, still not this feature's job.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

> **Order note.** The selection rule lands before the bulk load, deliberately.
> Loading 2025 and 2026 while the query still averages every season and reports
> `MAX(season)` would leave the app in a state where the warning has cleared but
> the baselines are still mostly 2024: exactly the dishonest outcome this feature
> exists to avoid. With only 2024 present, the new rule selects 2024 and flags the
> fallback, so behavior is unchanged until the data is there to improve it.

- [x] **Step 1 - Point stats ingest at the per-season asset.** `player_stats_url` returns the frozen aggregate and carries a comment claiming year-specific assets "are not guaranteed to exist", which is now false. Return `stats_player/stats_player_week_<season>.csv`. *Done when:* a unit test pins the URL shape per season, the stale comment is gone, and a `--dry-run` for 2025 parses more than 15,000 rows where the old URL yielded zero for that season.

- [x] **Step 2 - Fail clearly on a season that is not published.** The old aggregate URL returned 200 for any season and filtered locally; a per-season URL 404s for a season NFLverse has not released, and `_fetch_pair` currently raises `HTTPStatusError` straight out of the CLI. Catch the 404 and report which season is unavailable. *Done when:* requesting an unpublished future season prints a one-line message naming the season and exits non-zero, with no traceback, and a test covers the 404 path.

- [x] **Step 3 - Prove the parser against the real newer header.** The 150-column file differs from the 53-column one, most notably `recent_team` to `team`. Add parser tests using the newer header so a future column rename fails loudly rather than loading zeros, the way `passing_attempts` and `fantasy_tds` silently did. *Done when:* tests cover the newer header for team resolution and every stat field, and assert non-zero values for a fixture row.

- [x] **Step 4 - Season-aware baselines, pure.** A function choosing which season a player's baseline comes from: prefer the line's own season once the player has at least `MIN_BASELINE_GAMES` (4, matching the existing `small_sample` threshold so one number governs both), otherwise the most recent earlier season that clears the bar, otherwise whatever has the most games. Return the chosen season and the reason. Pure, in `app/core/nfl_baseline.py`. *Done when:* unit tests cover the current-season case, the early-season fallback (a week-2 player with one game falls back to last season), a player with no qualifying season, a player present in only one season, and a player with no stats at all.

- [x] **Step 5 - Per-season aggregation in the baseline query.** The current CTE groups by `player_id` across everything and reports `MAX(season)`. Aggregate by `player_id` and `season`, then apply Step 4's choice. *Done when:* with only 2024 loaded the slate is unchanged from today (2024 baseline, stale flag present), proving the rule is behavior-preserving before new data arrives.

- [x] **Step 6 - Honest flags.** `stale_baseline_season` must fire only on a real fallback, not whenever any older data exists. Add `partial_season_baseline` for a chosen season still in progress. *Done when:* unit tests show the stale flag absent when the baseline is the line's own season, present on fallback, and the partial flag present for an in-progress season.

- [x] **Step 7 - Load the seasons.** Re-import 2024 for the wider player set, then load 2025 and 2026. Ingest is already idempotent, so 2024 upserts in place. *Done when:* 2024's row count rises from 5,333 to roughly 18,130, all three seasons are present, `nfl_players` grows past 601 toward roughly 2,000, and a named kicker absent before (for example `Harrison Butker`) is now in `nfl_players`.

- [x] **Step 8 - Relink and measure.** Re-run `--relink` so lines for players who exist only in the newer data resolve. *Done when:* the reported match rate rises above 19c's 81%, the unmatched count on the 2026 week-2 slate falls below 42, and the remaining unmatched are named rather than summarized.
  - *Found and fixed during measurement:* stats ingest now stores full names, but the resolver still keyed roster names in the old `A.St. Brown` shape, breaking every name with a period (`Chris Godwin Jr.`, `A.J. Brown`) and merging players sharing an initial (`Bijan`/`Brian Robinson`). Roster names are now keyed as full names, and an exact full-name match breaks a shared key before position or team. Result: 2,685 of 2,685 lines linked, 0 unmatched on week 2, and every link is an exact full-name match.

- [x] **Step 9 - Show the season on the slate.** A per-row indicator of which season the baseline came from, and the page banner reworded to reflect per-row fallback rather than a single global season. *Done when:* a row sourced from the line's own season shows no stale flag, a fallback row shows both the flag and its source season, and the banner reflects the real mix rather than asserting one season for the whole page.

## Files / areas

| Path | Change |
|---|---|
| `api/app/ingest/nflverse.py` | per-season URL, stale comment removed |
| `api/app/core/nfl_baseline.py` | new, pure season selection |
| `api/app/core/nfl_projection.py` | flag changes |
| `api/app/core/nfl_names.py`, `nfl_resolution.py` | full-name roster keys and full-name tiebreak |
| `api/app/repositories/nfl.py` | per-season aggregation in `_BASELINES_CTE` and `get_slate_lines` |
| `api/app/routers/nfl.py`, `schemas/nfl.py` | carry the chosen season and reason |
| `web/src/pages/NflIntelligencePage.tsx`, `types/nfl.ts`, `utils/nflLabels.ts` | per-row season, reworded banner |
| `api/tests/test_nflverse.py`, `test_nfl_baseline.py`, `test_nfl_projection.py` | tests |

## Data / contracts

**Load-bearing, because 19e and the NBA slate will both reuse it:**

- `baselineSeason` already exists on `NflSlateLineSchema` but currently means "the newest season with any data". This feature changes it to "the season this baseline was computed from". Same field, materially different meaning: update its docstring so the change is not silent.
- Add `baselineReason` alongside it. 19e replaces the selection rule with a model and will need to say what it used; a bare season number cannot carry that.
- `MIN_BASELINE_GAMES` is a single named constant, not a literal scattered across query and UI.

## Testing

`pytest` and `vitest` are both real, so the test gate is on. Steps 1, 2, 3, 4, and 6 are logic and ship tests in the same diff.

- **Step 1** - URL shape per season.
- **Step 2** - the 404 path, with a stubbed response rather than a live request.
- **Step 3** - `api/tests/test_nflverse.py` against the real newer header, asserting non-zero stat values.
- **Step 4** - `api/tests/test_nfl_baseline.py`: current season, fallback, no qualifying season, single season, no stats. Table-driven.
- **Step 6** - extend `test_nfl_projection.py` for both flags.
- **Steps 5, 7, 8** - verified against the real database and the running API, with counts quoted, not unit tests.
- **Step 9** - browser plus `npm run build`.

## Notes for the AI

- **`core/` purity.** Step 4 takes per-season game counts and returns a choice. No DB, no I/O.
- **Repositories own SQL.** The per-season aggregation belongs in `repositories/nfl.py`.
- **Do not let the warning vanish by accident.** Clearing `stale_baseline_season` is only correct when the baseline genuinely comes from the line's season. If Step 6 makes the banner disappear while baselines are still mostly older data, the step is wrong.
- **A missing column must fail loudly.** `_as_int(None)` returning 0 is exactly how 19c's two dead columns survived a season. Prefer an explicit check over a silent default when adding fields.
- **2026 is one week deep.** Most players will legitimately fall back to 2025; that is the rule working, not a bug.
- **No em dashes** in generated content, per `coding-standards.md`.

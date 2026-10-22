# Feature 43, Step 1 calculation contract

Implemented locally on 2026-10-22. No endpoints or UI are wired in this step.
No database, provider, holdout or model reads were performed for this review.

## History and samples

- Require completed NFL REG games in the target season, week strictly before
  the target week, and a known timezone-aware start before target kickoff.
  A missing/naive target kickoff makes context unavailable.
- The repository in Step 2 must supply one row for each eligible defense game,
  including games with no position aggregate. It must supply played player
  games (including snap-only participation with missing statistical metrics),
  excluding DNPs. The pure core also checks the history cutoff and played flag.
  Duplicate game identities raise rather than inflate coverage.
- Select the last up to three played games before inspecting metrics. Byes,
  DNPs and missing metric values do not pull older games into that window.
- For player metrics, eligibleGames counts played games in the selected window.
  For allowed metrics it counts eligible completed defense games, independently
  of available position stats. observedGames counts only contributing values
  or valid numerator/denominator pairs. Coverage is observedGames / eligibleGames;
  when eligibleGames is zero, coverage is unavailable rather than 0%.
- windowStart/windowEnd are the first/last contributing kickoff dates in UTC
  for each metric. Without contributions both are null. These are not a common
  date range imposed on every metric. teams lists historical team codes in
  chronological first-appearance order for the selected played-game window,
  retaining prior-team history after a trade. Current roster identity remains
  a Step 2 responsibility, separate from these historical teams.

## Values and unavailable reasons

| Condition | Value | reason |
|---|---|---|
| At least one valid observation/pair | Calculated number, including zero | null |
| Target kickoff missing or without timezone | null | unknown_kickoff |
| No eligible history, including opening week | null | no_history |
| Eligible history but no valid observation/pair | null | missing_data |
| Every eligible share pair has a valid zero numerator and denominator | null | zero_denominator |

Mixed missing/zero-denominator games with no contributing pair use missing_data.
If some pairs contribute, return their ratio and explicit partial coverage.
Zero denominators do not contribute dates or observedGames. Nonfinite values,
negative usage counts, numerator above team denominator and snap fractions
outside [0, 1] are missing data. Negative allowed yardage is legitimate.

Shares are sums of paired numerators divided by sums of their denominators.
Step 2 must establish complete recorded team totals per game, including QB
carries, and retain null if completeness cannot be established. Do not use stored
target_share, RB-only carries, pass attempts or mutable current-team identity.
The core accepts normalized team-game totals; it does not aggregate individual
opponents as though each player were a separate defense game. Position sums
must remain null for absent or incompletely covered groups. SQL must not turn
absence into zero; a known complete group can supply an observed zero.

Allowed means are returned rounded to one decimal. Competition ranks use that
same precision; 1 is fewest allowed and ties skip subsequent ranks. rankedTeams
counts only covered teams for that measure. Usage means and shares retain
precision for UI formatting. Shares remain fractions.

The source and stored snap value is already a fraction, not 0-100. Evidence:
`api/app/ingest/nflverse_snap_counts.py`, `NflverseSnapGame.offense_pct` and
`parse_snap_counts`; repository `replace_snap_counts` stores the value unchanged.
`avgGameSnapShare` is its arithmetic mean over valid observations, not weighted
by inferred team snap counts. Never divide the stored fraction by 100.

Unsupported position/market combinations are omitted by the later presentation
mapping, rather than filled with zero. Missing/ambiguous current-week roster
membership must not assign a player to either team; Step 2 must preserve an
empty players list when no usable memberships exist. aDOT has no API field in
this contract.

## aDOT feasibility, read-only source/schema inspection

Inspected local source:

- `api/app/ingest/nflverse.py`: `player_stats_url`, `NflversePlayerWeek`,
  `parse_player_stats`.
- `api/app/repositories/nfl.py`: `upsert_weekly_stat`.
- Migrations `0015_nfl_foundation`, `0021_nfl_player_usage` and shared-table
  conversion `0039_shared_team_sport_tables`.

The configured source is NFLverse's `stats_player/stats_player_week_{season}.csv`
release asset. The parser and writer retain targets, target_share,
air_yards_share and wopr, but no raw receiving air-yard total. The weekly stat
writer does not preserve the source row in raw_json. Thus stored air-yard
numerator coverage is absent in this pipeline; no aDOT can be calculated from
these fields. No live asset or stored-data coverage query was performed.

A follow-up would need a reviewed nullable raw `receiving_air_yards` input (or
the source's verified equivalent), paired with targets for the same player-game.
Units must be yards and targets, yielding yards per target; signed air yards
must remain signed and zero-target games unavailable. For window aDOT, sum the
paired yards and targets rather than averaging game aDOT. The upstream field
name, units and season-by-season non-null paired coverage remain unverified and
must be checked against a reviewed source asset before an ingest amendment.
Air-yard share is dimensionless and cannot supply that numerator.

The join must follow the existing NFLverse GSIS player identity into NFL-scoped
sport_players, and the REG season/week/team/opponent game resolution into
sport_games, with historical stat-row team identity. Source game_id may be
blank; names and current-team guesses are not acceptable joins. Any raw totals
amendment needs schema, ingest, completeness and backfill review first.

Decision: aDOT remains unavailable; no schema migration or ingest amendment.

## Step 1 verification

- `.venv/Scripts/python.exe -m pytest tests/test_nfl_matchup_context.py -q`
  from `api/`: 27 passed.
- Focused new-context plus existing-player-detail regression run: 39 passed.
- Documented Verify gate run as PowerShell halves: `npm.cmd --prefix web run
  verify`, then `.venv/Scripts/python.exe -m pytest -q` from `api/`. Web:
  typecheck, 706 tests and production build passed. API: 3,641 passed.
- The first full API run caught a duplicate name for the new player schema.
  Renamed the new class to NflContextPlayerSchema; retained the original player
  page's NflPlayerUsageSchema unchanged. The final full API run is green.
- Build reports the existing large-bundle warning; API reports a Starlette
  dependency deprecation. No application checks were skipped. Windows requires
  npm.cmd because npm.ps1 is blocked by execution policy; esbuild required a
  permission-approved run outside the filesystem restriction.
- `git diff --check` passed. No commit or shared writes. Step 1 awaits owner
  review; endpoint, browser and stored-data checks belong to later steps.

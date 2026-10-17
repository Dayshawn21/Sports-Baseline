# Feature: NBA data sourcing

**From build-plan:** feature 20a
**Status:** complete (2026-10-05)

## Goal

Pick the free schedule, box-score, and injury sources for NBA, confirm the two
providers the app already uses (PrizePicks, The Odds API) cover NBA at a
budget the free plans allow, and fix the three structural decisions 20b to 20g
build on: NBA's prop period, whether NBA reuses the NFL team tables, and how
NBA games and players key into `sport_*`. This is item 18's job for NBA:
the data source decides the schema, so it is chosen before any ingest exists.

The 2026-27 regular season opens around 2026-10-20, so the decision should land
before then; 20b's backfill is 2025-26.

## In scope

- **Schedule and box-score sources.** Evaluate each candidate on: free and
  keyless, coverage of 2025-26 and the live 2026-27 season, per-player
  per-game box scores (minutes, points, rebounds, assists, threes made, steals,
  blocks, turnovers, field goal and free throw attempts), stable player and
  game ids, freshness (how soon after a final), and whether it works from
  **GitHub Actions** runners, where the cron runs. Candidates:
  - sportsdataverse `hoopR` data releases (ESPN-sourced, GitHub release
    assets, the closest analogue to NFLverse)
  - `nba_api` / stats.nba.com (official numbers; known to block cloud IPs)
  - ESPN's public site API (keyless, unofficial)
  - Basketball-Reference (scraping terms and rate limits; likely rejected)
- **Injury and availability source.** Evaluate the official NBA injury report
  and ESPN's injury feed: status vocabulary, publish times relative to tip-off,
  id mapping. Decide the source only; ingest is not in 20b to 20g (see Out of
  scope).
- **PrizePicks NBA probe.** One bounded read of the leagues list and the NBA
  board: league names and segment suffixes (to fill a `SportPropConfig`:
  `league_prefix`, `segment_suffixes`, `market_aliases`), the stat names
  posted, odds types, and confirm a WNBA league name never matches the NBA
  prefix (`league_segment` already guards this; confirm against real names).
  Honor `Retry-After` on 429.
- **The Odds API NBA probe.** Confirm `basketball_nba` in the free `/sports`
  list and list events with the free `/events` call. **Spend no odds
  credits.** Record the cost from the provider's documented pricing: one
  request covers every event, at one credit per market per region, so
  moneyline, spread and total cost 3 credits a call. Propose a schedule and its
  monthly credits beside NFL's current use (about 3 a week game odds, about 32
  a week anytime TD), keeping the total under 500 with headroom.
- **Decision: NBA's prop period.** The shared ranking rule
  (`app/core/prop_ranking_rule.py`) requires `MIN_PICKS = 200` across
  `MIN_PERIODS = 4` whole periods, so the period's length changes what the
  rule means. Compare at least:
  - a season week (Monday to Sunday, numbered from opening night), the same
    shape as NFL's 4-week minimum
  - a game date (4 periods = 4 days, a much weaker spread requirement)
  Recommend one, and say where it is stored or derived (for example whether
  `sport_games.week` is filled for NBA or the period is computed from
  `game_date`), and how a period counts as finished (every game in it
  completed and box scores loaded).
- **Decision: team tables (open question 11).** Whether NBA reuses
  `nfl_team_elo` and `nfl_team_game_efficiency` as shared concepts, gets its
  own tables, or needs neither for 20a to 20g. Given that item 24 rejected
  every NFL game-line signal, the expected answer is "neither yet"; record the
  reasoning.
- **Decision: id keys.** Which source ids become `sport_players.source_player_id`
  and `sport_games.source_game_id` for NBA, and how PrizePicks names resolve
  to them (aliases through `sport_player_aliases`, as NFL does).
- **Decision: NBA stat table shape.** Column list for the per-game box-score
  table 20b will create (name, grain, unique key), sized to settle the
  PrizePicks markets the probe finds, including combos (Pts+Rebs+Asts and the
  like) from stored columns.
- **Record the decision** in the user-owned `blueprint/project-plan.md` data
  sources table (NBA row) after showing the exact edit for approval, then
  regenerate `project-overview.md` with the `overview` skill.

## Out of scope

- Any ingest, migration, `sports` seed row, or app code (20b onward).
- WNBA sources (item 21), beyond noting whether the chosen source also covers
  WNBA.
- NBA injury ingest. NBA props move on late scratches far more than NFL, so if
  the evaluation finds a usable feed, **propose** a later item (for example
  20h, injuries and availability) in the final report; do not add it to the
  plan in this feature without approval.
- Spending any The Odds API credit or any paid source.
- Game-line modelling for NBA (no item exists; open question 11 records why).

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

Probes run as throwaway scripts in the session scratchpad, never under `api/`
(coding standards: one-off scripts do not belong in the live app tree). Each
step records its findings in the **Findings** section below, so the archive
carries the evidence.

- [x] **Step 1 - Box-score and schedule sources** - probe each candidate for
  one completed 2025-26 game date and one 2026-27 preseason or opening date;
  fill a comparison table (free, keyless, coverage, columns, ids, freshness,
  GitHub Actions reachability, terms). For GitHub Actions reachability, record
  documented or reported behavior; a live runner test is not required.
  *Done when:* the table in Findings has a row per candidate with every column
  filled or marked unknown with a reason, and one source is recommended with a
  fallback.
- [x] **Step 2 - Injury source** - inspect the official report and ESPN's feed
  for one recent game day; record status values, publish cadence and id
  mapping. *Done when:* Findings names a recommended source (or "none usable")
  and whether a later injury item is worth proposing.
- [x] **Step 3 - PrizePicks NBA probe** - one bounded leagues read plus one
  NBA board read. *Done when:* Findings lists the NBA league names, segment
  suffixes, every posted stat name with its proposed market key, odds types
  seen, and the WNBA prefix check result. If the NBA board is empty
  (offseason), say so and record the league names only.
- [x] **Step 4 - The Odds API NBA probe and budget** - free `/sports` and
  `/events` calls only. *Done when:* Findings confirms `basketball_nba`, shows
  the remaining-credit header unchanged before and after, and gives a proposed
  NBA odds schedule with monthly credits beside NFL's, totalling under 500.
- [x] **Step 5 - Structural decisions** - write the period, team-table, id-key
  and stat-table decisions with a one-paragraph rationale each. *Done when:*
  Findings holds all four, the period decision states its interaction with
  `MIN_PERIODS = 4`, and the stat-table column list settles every PrizePicks
  market from Step 3 (or lists which cannot be settled).
- [x] **Step 6 - Record in the plan** - show the exact `project-plan.md` edit
  (NBA row of the data sources table, plus any §4 sentence the period or
  team-table decision needs), apply it on approval, and regenerate
  `project-overview.md`. *Done when:* the plan's NBA row names the chosen
  sources, the overview's data sources table no longer reads TODO for NBA, and
  `git diff` touches only `blueprint/` files.

## Findings

Filled in by Steps 1 to 5. Probed 2026-10-05.

### Step 1 - Box-score and schedule sources

hoopR's data does not live in `hoopR-nba-data` releases (that repo holds the
build scripts); it is published as release assets on
`sportsdataverse/sportsdataverse-data`, one tag per dataset, files named by
**season end year** (`2026` = 2025-26, `2027` = 2026-27), in CSV, parquet and
RDS. The ESPN-sourced and stats.nba.com-sourced datasets sit side by side.

| Candidate | Free, keyless | 2025-26 | 2026-27 | Box-score columns | Ids | Freshness | GitHub Actions | Terms |
|---|---|---|---|---|---|---|---|---|
| **hoopR ESPN releases** (`espn_nba_schedules`, `espn_nba_player_boxscores`) | yes, GitHub release download | `player_box_2026.csv`: 34,883 rows, 1,326 games, 2025-10-21 to 2026-06-13, season types 2 (regular), 3 (playoffs), 5 (play-in) | `nba_schedule_2027.csv`: 1,206 regular-season games, 2026-10-20 to 2027-04-11, all `STATUS_SCHEDULED`; box scores appear once games are played | all needed: `minutes`, `points`, `rebounds` (plus offensive/defensive), `assists`, `three_point_field_goals_made`/`attempted`, `field_goals_*`, `free_throws_*`, `steals`, `blocks`, `turnovers`, `fouls`, `plus_minus`, `starter`, `did_not_play`, `reason`, `home_away`, `opponent_team_id`, `team_score` | ESPN `game_id` (e.g. `401859967`), `athlete_id`, `team_id`, `team_abbreviation` | `daily_nba.yml` cron `0 7 * * *` UTC from Oct 18 through June (07:00 UTC is after the latest West Coast final) | yes: plain HTTPS download from github.com, the same path NFLverse ingest already uses from Actions | unknown: data license not checked; the data is ESPN's, redistributed by sportsdataverse |
| hoopR stats.nba.com releases (`nba_stats_player_boxscores`, `nba_stats_schedules`) | yes | `player_boxscores_2026.csv`: 34,786 rows | schedule file for 2027 not yet published | same core stats, official NBA numbers; `comment` for DNP reason | NBA `game_id`, `person_id`, `team_tricode` | release updated 2026-10-01; fed by the same daily workflow | yes (release download) | as above |
| ESPN site API (`site.api.espn.com/.../basketball/nba/scoreboard`, `summary`) | yes, unofficial | yes (scoreboard 2026-03-10: 11 games, 0.18 s) | yes | summary box: MIN, PTS, FG, 3PT, FT, REB, AST, TO, STL, BLK, OREB, DREB, PF, +/- | ESPN ids, same as hoopR ESPN | live, minutes after a final | not tested; reported to work from cloud IPs | undocumented, can change without notice; one call per game for box scores |
| `nba_api` / stats.nba.com | yes, needs browser-like headers | yes | yes | full official box scores | NBA ids | live | **not tested; widely reported to time out from cloud IPs** (nba_api issue tracker); answered 200 in 0.84 s from this residential machine | unofficial use of an internal API |
| Basketball-Reference | free to browse | yes | yes | full | bbref slugs | next day | not tested | `sports-reference.com/bot-traffic.html` itself returned 403 to a script. Their bot policy (as commonly cited, not confirmed by this probe) caps automated traffic at about 20 requests a minute. **Rejected.** |

**Recommendation: hoopR ESPN releases** (`espn_nba_schedules` +
`espn_nba_player_boxscores`). Same shape as NFLverse (free release assets,
season files, no key, no quota), complete 2025-26 for 20b's backfill, the
2026-27 schedule already published, every PrizePicks core stat as a column,
and one id system (ESPN) for games, players and teams that also matches the
ESPN injury feed (Step 2).

**Fallback: the ESPN site API** for the same ids, if the release workflow
stalls in-season (scoreboard for schedule and status, summary per game for
box scores). Because both use ESPN ids, switching sources never rekeys a row.
The stats.nba.com releases are a second fallback but would need an id
crosswalk (`nba_crosswalk` release exists for that).

Notes for 20b:
- Box-score release lags by up to a day (07:00 UTC run); `nba-scores`-style
  next-morning freshness, same as `nfl-scores.yml`.
- The release's `season` is the end year. 20b must decide whether
  `sport_games.season` stores the end year (hoopR, ESPN, The Odds API
  convention varies) or the start year; see Step 5.
- The 2027 schedule has 1,206 of 1,230 games; the remaining 24 are likely NBA
  Cup knockout games added when set. Ingest must upsert new games, not assume
  a fixed list.
- `did_not_play` and `reason` are rows, so a DNP is distinguishable from a
  missing row (NULL stats, not zero).

### Step 2 - Injury source

| Source | Format | Status values | Timing | Ids | History |
|---|---|---|---|---|---|
| **ESPN injuries** (`site.api.espn.com/.../basketball/nba/injuries`) | JSON, keyless | `Out`, `Day-To-Day` (type `INJURY_STATUS_OUT` / `INJURY_STATUS_DAYTODAY`); fantasy tag `OUT`, `GTD`, `OFS`; body part, side, detail, expected `returnDate`; notes sourced from RotoWire | per-entry `date`, updated within minutes (latest entry 2026-10-05 22:42Z, preseason) | ESPN athlete id (in `athlete.links`) and team id, the same ids as Step 1's source | **none: current snapshot only** (82 entries across 26 teams today). hoopR's `espn_nba_injuries` release is one `injuries_2027.parquet` (54 KB, refreshed 2026-10-04), also a snapshot, not a history |
| **Official NBA injury report** (`ak-static.cms.nba.com/referee/injury/Injury-Report_<YYYY-MM-DD>_<HH_MM><AM/PM>.pdf`) | PDF, keyless | `Out`, `Doubtful`, `Questionable`, `Probable`, `Available`, plus a reason (`Injury/Illness - Right Knee; Sprain`, `G League - Two-Way`, `League Suspension`) | **every 30 minutes** on game days (01:30 PM, 05:00 PM, 05:30 PM, 06:00 PM ET all returned 200 for 2026-03-10 and 2026-04-01) | none: team name and `Last, First` player name only; would need name matching like PrizePicks linking | **yes: the 2025-26 archive is still served**, so a pre-tip snapshot exists for every past game |

The official report is the authoritative one (league-mandated, finer status
scale, timestamped, historical), but it is a PDF: `pypdf` extracts one word
per line with names split across lines, so ingest would need a layout-aware
parser and a new dependency (no PDF library is in `requirements.txt`). ESPN is
JSON with matching ids but coarser statuses and no history.

**Recommendation:**
- **Live display:** ESPN injuries, snapshotted on a pre-tip schedule (the 19l
  NFL pattern: one stored row per player per snapshot, display only). Same ids,
  no parsing risk.
- **Model use, later:** the official report. Its 2025-26 archive means a
  "teammate out" usage signal could be backtested on 20f's harness with
  leak-free, pre-tip statuses, which ESPN cannot offer.

**Worth proposing a later item: yes.** NBA props move on late scratches far
more than NFL, and the starters' availability is a known prop driver. Proposal
for the final report (not added to the plan without approval): **20h. NBA
injuries and availability** - ESPN injury snapshots before tip-off shown on
the slate and game page, display only; the official report archive parsed
only if a later model item tests availability on the 20f harness.

### Step 3 - PrizePicks NBA probe

Two requests through the app's own helpers (`_fetch_leagues`, then
`_fetch_projections` for league 7, `single_stat=True`); no 429.

**NBA leagues in the catalog** (140 leagues total), with what
`segment_for_league_name` returns for a draft `league_prefix="NBA"` config:

| Id | Name | Lines now | Segment | Note |
|---|---|---|---|---|
| 7 | `NBA` | 198 | `full_game` | the board |
| 84 | `NBA1H` | 0 | `first_half` | |
| 80 | `NBA2H` | 0 | `second_half` | |
| 192 | `NBA1Q` | 0 | `q1` | |
| 149 | `NBA4Q` | 0 | None | unknown suffix unless mapped |
| 173 | `NBASZN` | 553 | `season` | season-long props, never board |
| 188 | `NBASZN2` | 0 | None | |
| 237 | `NBAP` | 19 | None | not identified (preseason or playoffs); unknown suffix stays excluded, as intended |
| 40, 310 | `NBASL`, `NBASL2H` | 0 | None | Summer League |
| 250 | `NBA SERIES` | 0 | None | playoff series props |

**WNBA prefix check: passes.** `WNBA`, `WNBA1H`, `WNBA1Q`, `WNBA2H`,
`WNBA4Q`, `WNBASZN`, `WNBA SERIES`, `ALLSTAR WNBA` and `ALLSTAR WNBA 2H` all
return None, because the prefix must start the normalized name.

**The board today is opening night only.** 198 lines, all starting
2026-10-20 (15:10 to 21:40 ET), posted 2026-08-20. Pagination: one page.

| Stat name (posted) | Lines | Proposed market key |
|---|---|---|
| `Points` | 27 | `points` |
| `Rebounds` | 24 | `rebounds` |
| `Assists` | 22 | `assists` |
| `3-PT Made` | 21 | `threes_made` |
| `Pts+Rebs+Asts` | 29 | `points_rebounds_assists` |
| `Pts+Rebs` | 29 | `points_rebounds` |
| `Pts+Asts` | 26 | `points_assists` |
| `Rebs+Asts` | 13 | `rebounds_assists` |
| `Blocked Shots` | 3 | `blocks` |
| `Double-Double` | 4 | `double_double` |

Odds types: `demon` 106, `goblin` 54, `standard` 38. Raw rows carry
`allowed_wager_types: "over"` on demon lines (matching 27i's over-only rule
for goblin and demon), `game_id` (`NBA_game_...`), `event_type: "team"`, and
`player_team` as a team abbreviation (`DET`), which helps linking.

**Not confirmed: the in-season stat list.** A preseason board under-represents
it. PrizePicks has historically also posted Fantasy Score, Steals, Turnovers,
Blks+Stls, Free Throws Made, FG Attempted, 3-PT Attempted, Offensive and
Defensive Rebounds, and "(Combo)" two-player lines. 20c must re-probe after
opening night and map only names actually seen; "(Combo)" lines stay unmapped
(the NFL 34a rule).

### Step 4 - The Odds API NBA probe and budget

Two free calls with `THE_ODDS_API_KEY` from `Settings`:

| Call | Status | `x-requests-remaining` | `x-requests-used` | `x-requests-last` |
|---|---|---|---|---|
| `GET /v4/sports?all=true` | 200 | 466 | 34 | 0 |
| `GET /v4/sports/basketball_nba/events` | 200 | 466 | 34 | 0 |

**No credit spent:** remaining stayed at 466 and each call reported a cost of
0.

- `basketball_nba` is listed and **active**, beside `basketball_nba_preseason`
  (active), `basketball_nba_championship_winner` (outrights) and
  `basketball_wnba` (active; item 21).
- 46 NBA events are listed, 2026-10-20T19:00Z (Celtics at Pistons) to
  2026-12-26T03:30Z, so the provider already lists two months ahead. Event ids
  are provider hashes; games are matched by teams and commence time, as NFL's
  `nfl_odds` ingest does.
- Tip-off times differ slightly between providers (PrizePicks 15:10 ET, The
  Odds API 19:00Z = 15:00 ET for the same game), so matching needs a time
  window, not equality.

**Cost model** (the provider's documented pricing, not measured here): an
`/odds` call costs markets x regions credits and covers every listed event.
Moneyline, spread and total in region `us` is **3 credits a call**, whether a
night has 2 games or 15.

**Monthly budget, October to February** (both sports in season):

| Use | Schedule | Credits a month |
|---|---|---|
| NFL game odds (`nfl-ingest.yml`) | weekly | about 13 |
| NFL anytime TD (`nfl-prop-odds.yml`) | 4 runs a week | about 139 |
| **NBA game odds, proposed** | **twice daily**: 15:00 UTC (morning line) and 22:30 UTC (before the first evening tip) | **about 180** |
| Total | | **about 332 of 500** (168 headroom) |

This month's use so far (34 by 2026-10-05) is in line with the NFL rows.
Twice daily gives each game an early line and a near-tip line, which a later
CLV-style check needs; once daily would cost 90 and lose the near-tip line.
20d should reuse `nfl_odds`'s remaining-credit floor so NBA can never starve
the NFL anytime-TD runs.

**NBA player props from The Odds API are not affordable** on the free plan:
they are billed per event per market, so one market across about 7 games a
night is about 210 credits a month. Not proposed.

### Step 5 - Structural decisions

**1. NBA's prop period: the season week.** Period `n` is the `n`th Monday to
Sunday week of the regular season, counted from the Monday on or before
opening night, by the game's **US Eastern date** (ESPN's `game_date` is
already the Eastern date: a 00:30Z tip is filed under the previous day).
Opening night 2026-10-20 is a Tuesday, so week 1 runs 2026-10-19 to
2026-10-25.
- **Why not the game date.** The shared rule (`prop_ranking_rule.py`)
  takes the first whole periods holding `MIN_PICKS = 200` picks across
  `MIN_PERIODS = 4` periods. NBA's nightly volume (about 7 games, and three
  payout types per player and stat; opening night alone has 198 lines for 3
  games) could plausibly reach 200 picks in 4 days, so a verdict could be
  decided on four slates in one week. A week keeps the
  rule's meaning the same as NFL's: at least four weeks, a month of games,
  before anything is decided, with no change to the shared constants.
- **Stored, not derived.** 20b writes it to `sport_games.week` at ingest (the
  column is nullable and its CHECK requires it only for NFL), so the shared
  period queries read one column for every sport. A pure
  `nba_week(game_date, opening_night)` in `app/core/` computes it, with a test
  pinning week 1 for 2026-27.
- **Regular season only.** Play-in and playoff games (ESPN season types 5
  and 3) store `week` NULL and are never frozen or graded, matching NFL's
  regular-season-only grading. The All-Star break week simply holds fewer
  games.
- **Finished:** a week counts once every regular-season game in it is final
  and its box scores are loaded (NFL's 27j rule, per period).
- **Season label.** `sport_games.season` stores the **start year**
  (`2025` = 2025-26), the convention NFL already uses for a season spanning
  two calendar years. hoopR and ESPN label by end year, so 20b converts at
  ingest (`season - 1`) and pins it with a test; this is the one off-by-one
  risk in the decision.

**2. Team tables (open question 11): neither yet.** NBA needs no team ELO or
team-game efficiency for 20a to 20g: no NBA game-line model is planned, and
item 24 rejected every NFL game-line signal against the close. Prop
projections need opponent context, but per-team allowances can be computed
from the player box-score table itself (the 27c team-game DVP pattern), with
no team table. If a later NBA game-line item appears, decide then; do not
generalize `nfl_team_elo` speculatively.

**3. Id keys: ESPN everywhere.**
- `sport_games.source_game_id` = ESPN `game_id` (e.g. `401859967`).
- `sport_players.source_player_id` = ESPN `athlete_id`.
- `sport_teams.team_code` = ESPN abbreviation (`NY`, `SA`, `GS`, `NO`,
  `UTAH`, `WSH`, ...). ESPN also lists a `TBD` placeholder team for NBA Cup
  knockout slots; ingest skips games with a `TBD` side until they resolve.
- **PrizePicks team codes differ:** the board uses `NYK` and `SAS` where ESPN
  uses `NY` and `SA` (and likely `GSW`, `NOP`, `UTA`, `WAS`). 20c needs a
  small PrizePicks-to-ESPN team code map, tested, before team-assisted
  linking.
- Names resolve through `sport_player_aliases` with `sport = 'nba'`, as NFL
  does; The Odds API games match on both teams plus a commence-time window.
- One id system means the fallback source (ESPN site API) and the injury feed
  (Step 2) key to the same rows.

**4. NBA stat table: `nba_player_game_stats`.** One row per player per game,
**unique on (`player_id`, `game_id`)**, mirroring `nfl_player_weekly_stats`.

| Column | Type | From |
|---|---|---|
| `player_id`, `game_id`, `team_id`, `opponent_team_id` | bigint FKs to `sport_*` | ids above |
| `season` | smallint (start year) | `season - 1` |
| `is_home`, `starter`, `did_not_play` | boolean | `home_away`, `starter`, `did_not_play` |
| `dnp_reason` | text | `reason` |
| `minutes` | real | `minutes` |
| `points`, `rebounds`, `offensive_rebounds`, `defensive_rebounds`, `assists`, `steals`, `blocks`, `turnovers`, `fouls` | smallint | same names |
| `field_goals_made`, `field_goals_attempted`, `three_pointers_made`, `three_pointers_attempted`, `free_throws_made`, `free_throws_attempted` | smallint | `field_goals_*`, `three_point_field_goals_*`, `free_throws_*` |
| `plus_minus` | smallint | `plus_minus` (`+2` parsed) |
| `fetched_at` | timestamptz | ingest time |

NULL means not loaded; a DNP row has `did_not_play = true` and NULL stats,
never zeros.

**Settlement coverage** (every Step 3 market, plus the expected in-season
ones):

| Market | Settles on |
|---|---|
| `points`, `rebounds`, `assists`, `blocks`, `threes_made` | the column |
| `points_rebounds_assists`, `points_rebounds`, `points_assists`, `rebounds_assists` | sum of columns |
| `double_double` | 10 or more in at least two of points, rebounds, assists, steals, blocks |
| Steals, Turnovers, Blks+Stls, Free Throws Made, FG Attempted, 3-PT Attempted, Offensive/Defensive Rebounds (if posted) | columns or sums |
| Fantasy Score (if posted) | components, once 20c confirms PrizePicks' NBA formula (the 27f lesson: never assume it) |
| **Cannot settle:** Dunks or other shot-type lines, "(Combo)" two-player lines | not in a box score; stay unmapped |

## Files / areas

- `blueprint/context/current-feature.md` (this file, Findings section)
- `blueprint/project-plan.md` (NBA data source row, Step 6, on approval)
- `blueprint/context/project-overview.md` (regenerated by `/overview`)
- Read only: `api/app/core/prop_sports.py`, `api/app/core/prop_ranking_rule.py`,
  `api/app/services/sport_props.py`, `api/app/ingest/nfl_odds.py`,
  `api/app/ingest/prizepicks_props.py`, `api/app/services/sport_registry.py`
- Scratchpad probe scripts (not committed)

## Data / contracts

No schema or code change. **Load-bearing outputs** for later items:

- **NBA period definition** - 20g's frozen predictions and ranking check use it,
  and 17c requires it before any NBA frozen row exists.
- **`source_player_id` / `source_game_id` choice** - 20b's ingest keys and
  every NBA `ON CONFLICT` target depend on it.
- **NBA stat table column list** - 20b's migration and 20c's settlement rules.
- **`SportPropConfig` values** (league prefix, segment suffixes, market
  aliases) - 20c fills `NBA_PROP_CONFIG` from them.
- **Odds schedule and credit budget** - 20d's workflow.

## Testing

- No logic ships, so the test gate does not apply; no new tests.
- Evidence is the Findings section: probe outputs (trimmed), the comparison
  table, and the unchanged The Odds API remaining-credit header.
- Run `cd api && .venv\Scripts\python.exe -m pytest` once at the end only to
  confirm nothing in the app tree changed (expected: same pass count as master).

## Notes for the AI

- Read `THE_ODDS_API_KEY` through `Settings` (`app/config.py`) in probes, never
  by hardcoding; never print the key.
- PrizePicks answers 429 with `Retry-After`; honor it and stop after one retry.
- Do not call any odds endpoint that costs credits (`/odds`, `/events/{id}/odds`).
- stats.nba.com needs browser-like headers and may hang; time-box probes (10 s).
- The project plan is user-owned: show the exact edit and wait for a yes before
  Step 6 writes it.
- No em dashes in Findings or the plan edit.
- Prefer free, keyless, release-asset sources (the NFLverse lesson in the
  overview's "Prefer free sources").

# Feature: NHL data sourcing

**From build-plan:** feature 45a (parent 45)
**Status:** complete (2026-10-23)

## Goal

Pick the free schedule, box-score and injury sources for NHL, confirm the two
providers the app already uses (PrizePicks, The Odds API) cover NHL within a
budget the free plans allow, and fix the structural decisions 45b to 45e build
on: id keys, the skater and goalie stat-table shapes, NHL's prop period, the
season convention, and how overtime and shootouts are handled in scores,
moneylines and settlement. This is 20a's job for NHL: the source decides the
schema, so it is chosen before any ingest exists.

The 2026-27 regular season is already underway (it opened in early October),
so live games are available to probe.

## In scope

- **Schedule and box-score sources.** Evaluate each candidate on: free and
  keyless, coverage of 2024-25, 2025-26 and the live 2026-27 season, per-game
  skater stats (goals, assists, points, shots on goal, blocked shots, hits,
  power-play points, time on ice, faceoffs won) and goalie stats (saves, shots
  against, goals against, decision), stable player and game ids, freshness
  after a final, and whether it works from **GitHub Actions** runners.
  Candidates:
  - the NHL's public web API (`api-web.nhle.com`: schedule, boxscore,
    play-by-play; keyless, official, unofficially documented)
  - sportsdataverse `fastRhockey` / hockeyR release assets (the hoopR and
    NFLverse analogue, if published and current)
  - ESPN's public site API (`.../hockey/nhl/scoreboard`, `summary`), the same
    shape as NBA's fallback
  - MoneyPuck or Natural Stat Trick CSVs (check terms; likely rejected for
    ingest)
- **Injury source.** Inspect ESPN's NHL injury feed (NBA's 42c display source)
  and whether any official NHL report exists. Decide the source only; any
  ingest is a later item, proposed in the final report, not added to the plan.
- **Goalie confirmation.** Note whether any free source publishes the
  confirmed starting goalie before puck drop, and when. Saves props and every
  later goalie projection depend on who starts. Record the finding only.
- **PrizePicks NHL probe.** One bounded leagues read and one NHL board read
  through the app's own helpers: league names and segment suffixes (to fill a
  `SportPropConfig`), every posted stat name with a proposed market key, odds
  types, and whether goalie and skater markets share a stat name. Honor
  `Retry-After` on a 429.
- **The Odds API NHL probe.** Confirm `icehockey_nhl` in the free `/sports`
  list and list events with the free `/events` call. **Spend no odds
  credits.** From the provider's documented market list, record whether the
  `h2h` moneyline includes overtime and shootout, and whether a regulation
  (three-way) market exists and what it would cost.
- **Credit budget (binding).** Measure current monthly use from the
  remaining-credit header and the workflow schedules, then propose an NHL
  game-odds schedule that keeps the shared total under 500 with at least 50
  credits of headroom while NFL and NBA run. NFL and NBA use about 330 today,
  so NBA's twice-daily cadence (about 180) does not fit. If no NHL schedule
  fits, give the owner the options (for example once daily, odds only on
  game days, or trimming another sport's cadence) with their monthly cost;
  do not choose for them.
- **Decision: id keys.** Which source ids become `sport_players.source_player_id`,
  `sport_games.source_game_id` and `sport_teams.team_code` for NHL, and how
  PrizePicks and The Odds API team names map to them.
- **Decision: stat tables.** Column lists for the per-game skater and goalie
  tables 45b will create (name, grain, unique key, NULL meaning), sized to
  settle every PrizePicks market Step 3 finds, combos included, or listing
  which cannot be settled.
- **Decision: overtime and shootouts.** How `sport_games` scores record an
  overtime or shootout final (whether the shootout winner's goal counts in
  the stored score), whether a column marks the game's end state, and which
  goals count for player Goals and Points props (shootout goals do not count
  in NHL player stats; confirm how the source reports them).
- **Decision: prop period.** The shared ranking rule needs `MIN_PICKS = 200`
  across `MIN_PERIODS = 4` whole periods. Confirm whether NBA's
  regular-season week (Monday to Sunday, Eastern date, week 1 holding opening
  night, stored in `sport_games.week`) carries over unchanged, and how a week
  counts as finished.
- **Decision: seasons.** The `sport_games.season` convention (NBA uses the
  start year) and which seasons 45b should backfill. 45b's plan line says
  current season; if the later projection harness needs a development and a
  holdout season (as 20f used 2024-25 and 2025-26), say so and **propose**
  widening 45b, without editing the plan.
- **Record the decision** in `blueprint/project-plan.md`'s NHL data sources
  row (and any §4 sentence the decisions need) after showing the exact edit
  for approval, then regenerate `project-overview.md` with the `overview`
  skill.

## Out of scope

- Any ingest, migration, `sports` seed row, or app code (45b onward).
- Spending any The Odds API credit, or any paid source.
- NHL injury or goalie-confirmation ingest; propose a later item if worthwhile.
- Projection, P(over) or game-line modelling (later 45 sub-items).
- Changing NFL's or NBA's odds schedules. If the budget needs it, report the
  option; the owner decides in a separate change.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step
was too big, so split it.

## Build steps

Probes run as throwaway scripts in the session scratchpad, never under `api/`.
Each step records its findings in the **Findings** section below, so the
archive carries the evidence.

- [x] **Step 1 - Schedule and box-score sources** - probe each candidate for
  one completed 2025-26 date and one completed 2026-27 date, including at
  least one overtime or shootout final. Fill a comparison table (free,
  keyless, seasons covered, skater and goalie columns, ids, freshness, GitHub
  Actions reachability, terms; reachability may be documented or reported
  behavior). *Done when:* Findings has a row per candidate with every column
  filled or marked unknown with a reason, one recommended source and a
  fallback, and a note on how the recommended source reports the OT/SO final.
- [x] **Step 2 - Injury and goalie-confirmation sources** - inspect ESPN's NHL
  injury feed for one current game day, and look for a free starting-goalie
  signal. *Done when:* Findings names a recommended injury source (or "none
  usable"), states whether confirmed starters are available and when, and
  says whether a later display item is worth proposing.
- [x] **Step 3 - PrizePicks NHL probe** - one leagues read plus one NHL board
  read. *Done when:* Findings lists the NHL league names and their segments
  under a draft `league_prefix="NHL"`, every posted stat name with line count
  and proposed market key, odds types seen, and which markets are goalie-only.
- [x] **Step 4 - The Odds API NHL probe and budget** - free `/sports` and
  `/events` calls only. *Done when:* Findings confirms `icehockey_nhl`, shows
  `x-requests-remaining` unchanged before and after, records the OT/SO rule
  for `h2h` and any regulation market's cost, and gives a monthly budget table
  (NFL, NBA, proposed NHL) under 500 with 50+ headroom, or the owner options
  if none fits.
- [x] **Step 5 - Structural decisions** - id keys, stat tables, OT/SO
  handling, prop period, seasons and backfill. *Done when:* Findings holds
  each with a one-paragraph rationale; the stat-table columns settle every
  Step 3 market (or list the unsettleable ones); the period decision states
  its interaction with `MIN_PERIODS = 4`.
- [x] **Step 6 - Record in the plan** - show the exact `project-plan.md` edit
  (NHL data sources row, plus any §4 sentence), apply it on approval, and
  regenerate `project-overview.md`. *Done when:* the plan's NHL row names the
  chosen sources with no `> TODO (45a)` left, the overview matches, and
  `git diff` touches only `blueprint/` files.

## Findings

Filled in by Steps 1 to 5. Probed 2026-10-23.

### Step 1 - Schedule and box-score sources

Probe dates: 2026-03-10 (2025-26, 13 games: two OT finals, one shootout,
PIT 4 @ CAR 5, game `2025021018`) and 2026-10-21 (2026-27, 2 games).

| Candidate | Free, keyless | Seasons | Skater columns | Goalie columns | Ids | Freshness | GitHub Actions | Terms |
|---|---|---|---|---|---|---|---|---|
| **NHL stats REST** (`api.nhle.com/stats/rest/en/{skater,goalie}/{report}`, `isGame=true`) | yes | season list through `20262027`; regular season by `gameTypeId=2`; no preseason rows (`gameTypeId=1` returned 0) | `summary`: goals, assists, points, `shots`, `ppPoints`, `ppGoals`, `shPoints`, `otGoals`, `timeOnIcePerGame` (seconds), `skaterFullName`, `positionCode`, team and opponent abbrevs; `realtime`: `hits`, `blockedShots`, `missedShots`, `giveaways`, `takeaways`; `faceoffwins`: `totalFaceoffWins`, `totalFaceoffLosses` | `summary`: `saves`, `shotsAgainst`, `goalsAgainst`, `gamesStarted`, `wins`, `losses`, `otLosses`, `timeOnIce` (seconds), `goalieFullName`; only goalies who played | NHL `playerId` (e.g. `8473533`), `gameId` (`2025021018` = season 2025, type 02, game 1018), team abbrev | live after the final | not tested; plain HTTPS, no Cloudflare challenge seen | unofficial, undocumented; NHL.com terms; personal, non-commercial use |
| **NHL web API** (`api-web.nhle.com/v1/score/{date}`, `gamecenter/{id}/boxscore`, `play-by-play`, `club-schedule-season`) | yes | 2025-26 and 2026-27 checked; full club season schedule (88 CAR games incl. preseason) | box score: goals, assists, points, `sog`, `hits`, `blockedShots`, `powerPlayGoals`, `toi` ("18:07"), `faceoffWinningPctg`; **no power-play points, no faceoff counts**; names abbreviated ("J. Staal") | `saves`, `shotsAgainst`, `goalsAgainst`, `starter`, `decision`, `toi`; dressed backups listed with `toi` "00:00" | same NHL ids | live (0.08 to 0.5 s) | not tested, as above | as above |
| sportsdataverse `nhl_player_boxscores` / `nhl_schedules` (GitHub release assets) | yes | `player_box_2010` to `_2027` (`2026` = 2025-26: 55,758 rows, 1,394 games, to 2026-06-14; `2027`: 6,600 rows, 165 games from 2026-09-29, preseason included) | a mirror of the web API box score: same gaps (no PP points, no faceoff counts, abbreviated names) | as web API | same NHL ids | daily, `last_updated` 2026-10-23 04:04 EDT | yes, the release-download path NFLverse and hoopR already use | unknown; NHL data redistributed |
| ESPN site API (`.../hockey/nhl/scoreboard`, `summary`) | yes, unofficial | 2025-26 checked (13 events, 0.23 s) | `G`, `A`, `SOG`, `BS`, `HT`, `FW`, `FL`, `TOI`, `PPTOI`; **no power-play points** | `SV`, `SA`, `GA`, `SOS`, `SOSA` (shootout saves split out), `TOI` | ESPN ids (`401803363`); a crosswalk to NHL ids would be needed | live | not tested; reported to work from cloud IPs | undocumented |
| MoneyPuck / Natural Stat Trick | free to download or browse | n/a | advanced metrics, not a box-score feed | | own ids | | | not probed: not a box-score source of record. **Rejected.** |

**Recommendation: the NHL's own APIs.**
- **Box scores:** the stats REST per-game reports, one call per report per
  date range with `limit=-1` (a full week returned 2,016 skater-game rows in
  0.1 s, so a season backfill is a handful of calls). It is the only free
  source with power-play points and faceoff wins as counts, plus full names
  for linking.
- **Schedule, status and scores:** the web API (`club-schedule-season` or the
  weekly schedule, and `score/{date}` for finals), on the same ids.

**Fallback:** the sportsdataverse release for every column it carries, on the
same NHL ids, so switching never rekeys a row. It cannot settle power-play
points or faceoffs won; those markets would go unsettled while it is in use.

**OT and shootout (how the source reports them):**
- `gameOutcome.lastPeriodType` is `REG`, `OT` (with `otPeriods`) or `SO`.
- The team score **includes** the shootout winner's goal (CAR 5), but player
  goals do **not**: skater goals summed to 4 and 4 in both the box score and
  the stats REST `summary`. Goalie `saves` and `goalsAgainst` exclude
  shootout attempts (Andersen 24 of 28, Skinner 40 of 44).
- Play-by-play marks shootout events with `periodType: "SO"`.

**Notes for 45b:**
- The stats REST reports list only skaters who dressed (36 rows a game,
  18 a side). Healthy scratches have no row, so a missing row means did not
  play (a void), never zero.
- Time on ice is seconds in the stats REST, "mm:ss" in the web API.
- Not probed: GitHub Actions reachability for `api.nhle.com` and
  `api-web.nhle.com`. 45b's first runner run is the real test; the
  sportsdataverse fallback is known to work from Actions.

### Step 2 - Injury and goalie-confirmation sources

Probed 2026-10-23 about 17:00 UTC, with two games that night (first puck drop
2026-10-24 00:00 UTC).

| Source | Format | Values | Timing | Ids | History |
|---|---|---|---|---|---|
| **ESPN injuries** (`site.api.espn.com/.../hockey/nhl/injuries`) | JSON, keyless | `status` `Day-To-Day` (23), `Out` (12), `Injured Reserve` (102); `type.name` `INJURY_STATUS_DAYTODAY` / `_OUT` / `_IR`; `details.type` (for example `Illness`), `returnDate` | 137 entries across 29 teams; latest entry 2026-10-23 16:48Z, so updated the same day | ESPN athlete id (`athlete.links`, for example `id/4895214`) | **none**: current snapshot only. sportsdataverse `espn_nhl_injuries` (`injuries_2027.parquet`) is also a snapshot |
| **ESPN probable goalies** (scoreboard `competitions[0].competitors[].probables`, name `probableStartingGoalie`) | JSON, keyless | athlete name and id, `status` `Expected` or `Confirmed` (3 Expected and 1 Confirmed across the 2 games) | present about 7 hours before puck drop; flips to Confirmed as teams announce | ESPN athlete id | none: snapshot only |
| NHL web API pre-game (`gamecenter/{id}/landing`, `boxscore`) | JSON | `matchup.goalieComparison` lists the season's goalie **leaders**, not tonight's starter; the box score has no player rows before the game | | NHL ids | post-game `starter` flag only |
| Official NHL injury report | | none found: the NHL publishes no league-mandated report like the NBA's | | | |

**Recommendation:**
- **Injuries:** ESPN's feed, snapshotted before puck drop as NBA's 42c does
  (display only). Its statuses are coarser than NBA's (no Questionable), and
  `Injured Reserve` is most of the list.
- **Starting goalies:** ESPN's `probableStartingGoalie`, with its
  `Expected` or `Confirmed` status kept, snapshotted on the same schedule.
- **Id mapping:** both use ESPN athlete ids, while box scores use NHL ids
  (Step 1). Linking needs a crosswalk by name and team, as PrizePicks linking
  already does. Step 5 records it.

**Worth proposing a later item: yes.** Goalie props (Saves) and every skater
facing a team depend on who starts in net, and a backup's start moves lines.
Proposal for the final report, not added to the plan without approval:
**NHL injuries and starting goalies**, ESPN snapshots before puck drop shown
on the slate and game page, display only. Neither feed has history, so
forward snapshots are the only way to build one for a later model test.

### Step 3 - PrizePicks NHL probe

Through the app's own `_fetch_leagues` and `_fetch_projections`
(`single_stat=True`), about 17:00 UTC. A second read of leagues 8 and 227 met
one 429 each; the helper waited the 60 s `Retry-After` and succeeded.

**NHL leagues** (139 in the catalog), against a draft config
`league_prefix="NHL"`, `segment_suffixes={"1P": "p1", "SZN": "season"}`:

| Id | Name | Lines now | Segment | Note |
|---|---|---:|---|---|
| 8 | `NHL` | 632 | `full_game` | the board |
| 227 | `NHL1P` | 63 | `p1` | first period, Shots On Goal only; off the board (no stored data settles a period) |
| 234 | `NHL2P` | 0 | None | unless mapped |
| 226 | `NHL3P` | 0 | None | |
| 236 | `NHLSZN` | 0 | `season` | season-long, never board |
| 282 | `NHLP` | 0 | None | not identified (preseason or playoffs), stays excluded |
| 251 | `NHL SERIES` | 0 | None | playoff series |

No other league starts with `NHL`, so the prefix rule needs no extra guard.

**The board** (2 games that night, CHI-MTL and COL-TB, starts 20:00 to
21:00 ET). Odds types: `demon` 492, `standard` 70, `goblin` 70.

| Stat name (posted) | Lines | Positions | Proposed market key | Settles from (Step 1 source) |
|---|---:|---|---|---|
| `Shots On Goal` | 152 | F 123, D 29 | `shots_on_goal` | `summary.shots` |
| `Points` | 142 | F 104, D 38 | `points` | `summary.points` |
| `Assists` | 110 | F 75, D 35 | `assists` | `summary.assists` |
| `Goals` | 85 | F 61, D 24 | `goals` | `summary.goals` (excludes shootout) |
| `Power Play Points` | 41 | F 33, D 8 | `power_play_points` | `summary.ppPoints` |
| `Blocked Shots` | 35 | F 18, D 17 | `blocked_shots` | `realtime.blockedShots` |
| `Plus/Minus` | 19 | F 12, D 7 | `plus_minus` | `summary.plusMinus` |
| `Goalie Saves` | 18 | G | `goalie_saves` | goalie `summary.saves` |
| `Hits` | 9 | F 4, D 5 | `hits` | `realtime.hits` |
| `Time On Ice` | 6 | F 3, D 3 | `time_on_ice` | `summary.timeOnIcePerGame` (seconds; line units to confirm in 45c) |
| `Goals Allowed` | 3 | G | `goals_allowed` | goalie `summary.goalsAgainst` |
| `Faceoffs Won` | 2 | F | `faceoffs_won` | `faceoffwins.totalFaceoffWins` |
| `Shots On Goal (Combo)`, `Goals (Combo)` | 7, 3 | F | unmapped | two players summed ("Cole Caufield + Connor Bedard"); not stored, as for NFL and NBA |

Fantasy Score did not appear on this two-game board; a fuller slate may post
more stat names, which 45c logs as unsupported until mapped.

**Goalie and skater markets never share a stat name:** `Goalie Saves` and
`Goals Allowed` are goalie-only, and every other market was posted only on
F and D. PrizePicks positions are `F`, `D`, `G`, while the NHL APIs use `C`,
`L`, `R`, `D`, `G`, so 45c must not pass position to linking (NBA's rule).

**Two things that differ from NBA:**
- **Goalie lines are posted for goalies who may not start.** Jacob Fowler
  (MTL) had 5 `Goalie Saves` lines while ESPN listed Jakub Dobes as MTL's
  expected starter (Step 2). A goalie who does not play has no row, so the
  line voids; any later goalie projection must condition on the starter.
- **Demon and goblin lines are not always over-only.** `allowed_wager_types`
  was `under_or_over` on 138 demon and 26 goblin lines (and missing on 45).
  27i's ranking rule plays goblin and demon over only, so this changes
  nothing stored; it is recorded for any later ranking item.

**Linking:** player rows carry `team` as an abbreviation. `CHI`, `COL`, `MTL`
match the NHL APIs; PrizePicks `TB` is the NHL's `TBL`, so 45c needs a code
map like NBA's `espn_team_code`. Combo rows carry `COL/TB`-style teams.
`game_id` is a PrizePicks hash (`NHL_game_...`), so games are matched by
teams and start time.

### Step 4 - The Odds API NHL probe and budget

Three free calls with `the_odds_api_key` from `Settings`, about 18:20 UTC:

| Call | Status | `x-requests-remaining` | `x-requests-used` | `x-requests-last` |
|---|---|---:|---:|---:|
| `GET /v4/sports?all=true` | 200 | 305 | 195 | 0 |
| `GET /v4/sports/icehockey_nhl/events` | 200 | 305 | 195 | 0 |
| `GET /v4/sports` (repeat) | 200 | 305 | 195 | 0 |

**No credit spent.** `icehockey_nhl` is listed and active (beside
`icehockey_nhl_preseason`, inactive, and the championship outright). 14
events were listed, 2026-10-24 00:10Z to 2026-10-25 02:10Z, so the provider
lists about two days ahead, not NBA's two months. Team names are full names
with accents (`Montréal Canadiens`), so matching needs NBA's accent folding.

**OT and shootout:** not verified by a priced call (that would cost credits).
The provider's `h2h` is a two-outcome moneyline; whether a regulation
(three-way) market exists for NHL on the free plan is unconfirmed. 45d would
learn it from its first paid run.

**The budget does not fit as 45a assumed.** 195 credits were used by
2026-10-23, which matches the schedules (NFL about 160 since 2026-10-01, NBA
about 36 since its window opened 2026-10-18). The full-month cost while both
seasons run:

| Use | Schedule | Credits a month |
|---|---|---:|
| NFL game odds (`nfl-ingest.yml`, Tuesday) | weekly, 3 credits | about 13 |
| NFL Pinnacle (`--pinnacle`, Tuesday plus the four `nfl-prop-odds.yml` runs) | 5 a week, 3 credits | about 65 |
| NFL anytime TD (`nfl-prop-odds.yml`) | 4 a week | about 139 |
| NBA game odds (`nba-odds.yml`) | twice daily, 3 credits | about 180 |
| **Current total** | | **about 397 of 500** |
| NHL at NBA's cadence | twice daily | +180 (577, over) |
| NHL once daily | daily | +90 (487, 13 headroom: fails the 50 rule) |

The overview's "about 330" predates 36a's Pinnacle runs (about 65 a month).
The plan period resets monthly; NBA runs October to June and NFL September
to February, so March to June leaves NBA alone at about 180.

**A credit-free alternative exists: Odds-API.io**, the provider tennis and
36a's NFL Bet365/DraftKings odds already use (100 requests an hour, the two
books DraftKings and Bet365, no credits). Five requests during the probe:

- `/sports` lists `ice-hockey`; `/events?sport=ice-hockey` returned 108
  `usa-nhl` events (alongside AHL, ECHL, college, KHL and others, so the
  league slug must be filtered as 36a filters NFL).
- One `/odds/multi` call for CHI-MTL (2026-10-24 00:00Z): both books post
  `ML` (two-way, Bet365 2.39/1.60, overround 4.3%, so overtime is included),
  `Spread` (the +/-1.5 puck line, one rung) and `Totals` (Bet365 9 rungs,
  DraftKings 1). Bet365 also posts `Draw No Bet`, and both post player props
  (Bet365 305, DraftKings 115 lines) and DraftKings team and period totals.
- `/odds/multi` takes up to 10 events, so a full 16-game night is 2
  requests a run, beside tennis (every four hours) and NFL (every three
  hours, about 3 requests). NHL every three hours fits easily.
- It has no Pinnacle and no multi-book consensus, so a fair price would come
  from de-vigging each book's own two-way price.

**Options for the owner (not chosen here):**

| Option | NHL source and cadence | Credits a month (Oct-Feb) | Trade-off |
|---|---|---:|---|
| A | Odds-API.io, DraftKings and Bet365, every few hours | 397 (no change) | No credit cost and an early plus near-drop line; two books only, no Pinnacle. Changes 45d's plan line and the §5 row from The Odds API to Odds-API.io |
| B | The Odds API once daily, and drop Pinnacle from the four `nfl-prop-odds.yml` runs (keep Tuesday's) | about 435 (65 headroom) | Seven books, consensus de-vig; one line a day; NFL best line keeps Pinnacle only weekly |
| C | The Odds API once daily, and NBA cut to once daily | about 397 (103 headroom) | NBA loses its near-tip line, which item 20d chose twice daily for |
| D | The Odds API paid plan | n/a | Money; out of the plan's free-source preference |

Recommended for discussion: **A**, because it needs no change to NFL or
NBA and keeps two lines a day or more.

**Owner decision (2026-10-23): option A.** NHL game odds come from
Odds-API.io (DraftKings and Bet365), spending no The Odds API credits. Step 6
proposes the matching edits to 45d's build-plan line and the §5 NHL row.

### Step 5 - Structural decisions

Season calendars from the stats REST `game` report (`gameType=2`), weeks
counted Monday to Sunday from the week of opening night:

| Season | REG games | Opening | Last | Weeks | Empty weeks | Fewest games in a week |
|---|---:|---|---|---:|---|---:|
| 2024-25 | 1,312 | 2024-10-04 (Prague) | 2025-04-17 | 29 | 20 (4 Nations break) | 2 (week 1) |
| 2025-26 | 1,312 | 2025-10-07 | 2026-04-16 | 28 | 19, 20 (Olympics) | 31 |
| 2026-27 | 1,344 (84 games a team) | 2026-09-29 | 2027-04-10 | 28 | none | 14 |

**1. Id keys.** `sport_players.source_player_id` is the NHL `playerId`,
`sport_games.source_game_id` the NHL `gameId` (`2026020152`: start year,
type, number), and `sport_teams.team_code` the NHL tri-code (`TBL`, `UTA`;
fits `varchar(8)`). Every Step 1 source (stats REST, web API, the
sportsdataverse fallback) uses these ids, so switching sources never rekeys a
row. Three providers need a map onto them, each as a pure function with a
coverage test (NBA's `espn_team_code` and `nba_odds` pattern):
- PrizePicks: tri-codes except `TB` to `TBL` (the full list is checked in
  45c); players by folded name and team through `sport_player_aliases`, never
  position.
- Odds-API.io: full team names (`Montreal Canadiens`) to tri-codes, matched
  to a stored game by both teams and start within 6 hours.
- ESPN (injuries, starting goalies, a later item): name and team, since ESPN
  athlete ids are not NHL ids.

**2. Stat tables.** Two tables, because skaters and goalies share almost no
stat and no PrizePicks market spans both (Step 3). Both reference
`sport_players`, `sport_games` and `sport_teams` under `sport = 'nhl'`, with
`team_id`, `opponent_team_id`, `season`, `is_home`, `fetched_at`, and
**unique (`player_id`, `game_id`)**.
- `nhl_skater_game_stats`: `position` (`C`, `L`, `R`, `D`), smallint
  `goals`, `assists`, `points`, `shots`, `power_play_goals`,
  `power_play_points`, `shorthanded_points`, `plus_minus`, `hits`,
  `blocked_shots`, `faceoffs_won`, `faceoffs_lost`, `penalty_minutes`,
  `giveaways`, `takeaways`, `ot_goals`, and integer `time_on_ice_seconds`.
- `nhl_goalie_game_stats`: `started` (boolean, `gamesStarted`), `decision`
  (`W`, `L`, `O` or NULL), smallint `saves`, `shots_against`,
  `goals_against`, and integer `time_on_ice_seconds`.
- **Row meaning:** a skater row exists only if he dressed, a goalie row only
  if he played. **No row means did not play: a void, never zero.** A NULL
  column means not loaded. Shootout attempts are in no column.
- **Settles every Step 3 market:** Shots On Goal, Points, Assists, Goals,
  Power Play Points, Blocked Shots, Plus/Minus, Hits, Faceoffs Won and Time
  On Ice from the skater table; Goalie Saves and Goals Allowed from the
  goalie table. Not settleable or not stored: the two `(Combo)` markets, and
  Fantasy Score until PrizePicks' NHL formula is confirmed. 45c must confirm
  Time On Ice's line unit (minutes, by the line values) before settling it.

**3. Overtime and shootouts.**
- `sport_games.home_score` / `away_score` store the **official final**,
  including the shootout winner's goal (CAR 5, PIT 4), which is how books
  settle the moneyline, puck line and total.
- A new nullable `sport_games.end_period` (`REG`, `OT`, `SO`), filled for NHL
  only, records how the game ended. This follows 17b's rule that
  sport-specific nullable columns live on `sport_games` and other sports
  leave them NULL. It is needed because a 1-goal shootout win and a 1-goal
  regulation win settle the puck line the same but mean different things.
- Player and goalie props settle on the stat tables, which exclude shootout
  goals and saves (Step 1), matching how the NHL credits them.
- The moneyline stored from Odds-API.io is the two-way `ML`, overtime and
  shootout included (Step 4). `Draw No Bet` and any regulation market are
  not stored.

**4. Prop period: the regular-season week, unchanged from NBA.** Monday to
Sunday by Eastern date, week 1 holding opening night, stored in
`sport_games.week` (NULL off the regular season), computed by the same rule
as `nba_week`. A week is finished when every `REG` game in it is
`completed`, `postponed` or `canceled` and every completed one has stat
rows. With `MIN_PERIODS = 4`, four weeks span about 180 to 200 games, NBA's
scale. Two consequences, both acceptable:
- A break leaves a week number with no games (2025-26 weeks 19 and 20). It
  has no rows, so it is never a period, and week numbers simply skip it.
- An overseas opening can make week 1 thin (2 games in 2024-25). It still
  counts as one of the four periods; 200 picks is the binding minimum.
45b decides whether `nba_week` moves to a shared module or is duplicated;
the shared prop modules must still never import a sport package.

**5. Seasons and game types.** `sport_games.season` is the **start year**
(2026 = 2026-27), as for NBA, and it matches the first four digits of the
NHL `gameId`. Game types: NHL `gameType` 2 is `REG`, 3 is `PST`; preseason
(1) is not stored (the stats REST has no preseason rows anyway).

**6. Backfill depth: propose widening 45b.** 45b's plan line says
"current-season backfill". The later projection harness needs what 20f had
for NBA: a development season, a holdout season scored once, and a prior
season for early-window history. **Proposal (not applied):** 45b backfills
2023-24 through 2026-27. At about 55,000 skater rows and 2,600 goalie rows a
season, that is about 230,000 rows, a few stats REST calls a season. Step 6
shows it as an optional edit to 45b's line.

## Files / areas

- `blueprint/context/current-feature.md` (this file, Findings section)
- `blueprint/project-plan.md` (NHL data source row, Step 6, on approval)
- `blueprint/context/project-overview.md` (regenerated by `/overview`)
- Read only: `api/app/core/prop_sports.py`, `api/app/core/prop_ranking_rule.py`,
  `api/app/services/sport_props.py`, `api/app/ingest/prizepicks_props.py`,
  `api/app/ingest/nba_odds.py`, `api/app/core/nba_odds.py`,
  `api/app/ingest/hoopr_nba.py`, `api/app/services/sport_registry.py`,
  the `nba-*.yml` and `nfl-*.yml` workflow schedules
- Scratchpad probe scripts (not committed)

## Data / contracts

No schema or code change. **Load-bearing outputs** for later items:

- **`source_player_id` / `source_game_id` / `team_code` choice** - 45b's keys
  and every NHL `ON CONFLICT` target.
- **Skater and goalie stat-table columns** - 45b's migration and 45c's
  settlement rules.
- **OT/SO rule** - 45b's stored scores, 45c's settlement and 45d's moneyline
  meaning; changing it later would rekey or resettle rows.
- **NHL period definition** - later frozen predictions and the ranking check.
- **`SportPropConfig` values** (league prefix, segment suffixes, market
  aliases) - 45c's config.
- **Odds schedule and credit budget** - 45d's workflow and credit floor.

## Testing

- No logic ships, so the test gate does not apply; no new tests.
- Evidence is the Findings section: trimmed probe outputs, the comparison
  table and the unchanged remaining-credit header.
- Run `cd api && .venv\Scripts\python.exe -m pytest` once at the end only to
  confirm the app tree is unchanged (same pass count as `master`).

## Notes for the AI

- Read `THE_ODDS_API_KEY` through `Settings`; never hardcode or print it.
- Never call a credit-costing endpoint (`/odds`, `/events/{id}/odds`).
- PrizePicks: honor `Retry-After`, stop after one retry.
- Time-box every probe (10 s); the NHL web API is unofficial and can change.
- Downloaded files go in their own empty scratchpad folder; read them with
  `python -I`.
- The project plan is user-owned: show the exact edit and wait for a yes
  before Step 6 writes it.
- 44b is parked on `feature/44b-nba-pover-confirmation`; this work branches
  from `master` as `feature/45a-nhl-data-sourcing`. Do not touch 44b files.
- No em dashes in Findings or the plan edit.

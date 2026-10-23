# Lineform - Project Overview

**Product name:** Lineform (formerly SportApp V2; renamed 2026-10-16).

> Multi-sport betting intelligence, tennis first: ingest matches, odds, stats, and
> props on a schedule, blend ELO + LightGBM + market into a calibrated ensemble,
> and surface only the plays where the model disagrees with the market enough to
> bet. NFL runs on shared `sport_*` tables (item 17 converged the stacks),
> its prop model under validation (item 27) and its game-line model under a
> forward CLV check (item 28); NBA (item 20) is complete (schedule, box
> scores, line-only PrizePicks lines and game odds stored, a display-only slate
> and game page with a gray reference projection, P(over) for assists only,
> pre-tip predictions frozen after each line snapshot, and a forward ranking
> check on `/nba/model`, with slice results reported there); NHL (item 45, added 2026-10-23) is next as a new sport, then WNBA and soccer. NFL best line (item 36) is complete: each side's
> best Bet365 or DraftKings price beside a Pinnacle fair price, on the game
> page and slate row. Tennis model validation (item 26) found the market unbeaten, so
> tennis now serves a market-anchored ensemble with moneyline picks off. The
> public read-only demo (item 37) is complete: live on Render, with the code
> public at `github.com/Dayshawn21/Sports-Baseline`. The Lineform structural
> redesign (item 38) is complete: the shared command-bar shell, all three
> table-first slates, tennis/NFL prop boards and NBA game-page prop rows,
> command search, shared detail headings, CT labels and loaded detail tab
> titles are implemented. The palette, fonts, and signal rules stay unchanged.
> NBA now has Slate / Props / Model tabs: the board API and page (42a, 42b)
> are complete and verified locally, with deployment unverified. Display-only
> NBA injuries and team stats (42c, 42d) are complete locally; hosted
> deployment remains unverified. NFL Rec Targets (item 39)
> is graded by 27j as its own sample; its 2024 baseline (39a) is chosen, its
> P(over) failed the one 2025 check and stays hidden (39b), and reference
> serving, freezing and separate-version reporting are complete (39c-39d).
> Rec Targets remains a gray reference without P(over) or probability picks.
> WTA 125 testing (40a) kept the pooled Challenger blend;
> the conditional serving change (40b) was dropped. TennisMyLife box-score
> ingest (41a) is implemented and verified locally, with 22,789 player-match
> rows backfilled into the shared database. Match and player displays fill
> TennisAbstract gaps; grading and model inputs are unchanged. The in-house
> ELO shadow comparison (41b) is engineered and activated locally, its
> forward verdict accruing from 2026-10-22 with zero observations; serving
> it (41c) stays conditional. First runner acceptance and deployment
> remain unverified for both. NFL matchup and usage context (43) is complete
> and merged, display only, with aDOT unavailable. Item 44 adds a second
> NBA over-probability method for the eight markets 20g1 hid: 44a chose a
> family for six of them on 2024-25 alone (complete 2026-10-23), and 44b
> confirms them once on a fresh 2026-27 sample. Two of NFL's four 27j
> ranking slices (standard under, demon over) are now rejected; 27h stays
> blocked on the other two.

> **Generated file. Don't hand-edit.** Produced by `/overview` from
> [../project-plan.md](../project-plan.md) and [../build-plan.md](../build-plan.md).
> When the plans change, re-run `/overview` rather than editing here.

**Regenerated:** 2026-10-23 (fourth refresh) after 45a's approved plan
edits: the NHL sources (§4, §5), 45d on Odds-API.io, 45b's 2023-24 to
2026-27 backfill and the new 45f. The third refresh added item 45 (NHL
support, placed before WNBA) with project-plan §1, §3 and §5 edits. The second refresh followed
44a's completion, retaining existing overview content and completed-work
validation/deployment boundaries. The build plan is the progress authority
where older project-plan prose disagrees. There are 122 checked leaf items
out of 137, including the explicitly dropped 40b; 15 remain unchecked. Feature 43 is complete per its archive. The owner chose
item 44 ahead of WNBA (and a possible NHL addition), with a fresh 2026-27
confirmation sample instead of a third 2025-26 holdout read.
44b is specified and built through its gate run on
`feature/44b-nba-pover-confirmation` (checkpoint `dcabc8f`); its one scoring
run waits until the first four 2026-27 weeks are played (about 2026-11-17).
`master`'s `current-feature.md` is the stub, so 45a is specified next in
parallel. A read-only check
on 2026-10-23 found the hosted NBA board, injuries and team stats live and
every ingest workflow, including the six tennis files, running green; the
secret scan was red from 2026-10-17 until fix `f731dec`. This refresh read
no holdout. It records the 27j verdicts the live `/nfl/model/ranking`
served on 2026-10-23 (graded 15:50 UTC, last settled week 6); it decides
nothing new.

## Problem

Betting markets are efficient enough that casual bettors lose, but not so
efficient that every line is priced correctly. Finding the mispriced ones by hand
means reconciling form, surface history, head-to-head, ELO, and live book odds
across several sites for dozens of matches a day. That does not scale past a
handful of matches.

This app does that reconciliation automatically and outputs a ranked shortlist
with stake sizing, not a wall of data. It also stores its predictions before
each start and grades them against results, so the edge is measurable rather
than assumed. Placed bets are tracked outside the app, in Pikkit.

**Tennis is the first sport, not the only one.** Tennis came first because it is
two-outcome, has no draws, runs daily, and has free ELO and per-match stats, which
made it the cheapest place to prove the pipeline. NFL and NBA are shipped; WNBA
and soccer are planned.

## Users

**One user: the project owner.** This is a settled decision, not a stage.

- no accounts, no per-user data scoping
- no stored data carries a user id
- route protection is a single shared `X-API-Key` on the admin routes, open by
  default on localhost; production refuses to start without one (fix
  2026-10-15, see Deployment)
- visitors to the live public demo (item 37) are anonymous and read-only;
  the only login is the owner's, for the admin surface (37a)

**Multi-user is out of scope for one to two years** (see Monetization). Do not add
accounts, auth, or per-user scoping to any spec unless `project-plan.md` §2 and §6
change first. Sport coverage is the priority. **The owner login (37a) is not
multi-user:** one credential, no sign-up, no stored user data.

## Features

### Build-plan map

This map follows the plan's order. Numbers are stable identifiers, so their
order is not strictly numeric. The detailed notes below group related work
and preserve the model, schema and operational constraints established by it.
Checked items record completed work, including explicitly retired surfaces.

| Item | Outcome | State |
|---|---|---|
| 1 | Match ingest | Complete |
| 2 | Player identity resolution | Complete |
| 3 | ELO ratings | Complete |
| 4 | Rolling player stats | Complete |
| 5 | Odds ingest | Complete |
| 6 | Model ensemble | Complete |
| 7 | Match predictions UI | Complete |
| 8 | Best picks | Complete |
| 9 | Props pipeline | Complete |
| 10 | Bankroll builder | Built; hidden from nav |
| 11 | Bet tracking | Built; later removed |
| 12 | Admin surface | Complete |
| 13 | Declare test dependencies | Complete |
| 14 | Clean up one-off scripts | Complete |
| 15 | Prediction accuracy pass | Complete |
| 16 | Props coverage expansion | 16f parked |
| 26 | Tennis model validation | Complete |
| 40 | WTA 125 blend group | Complete: keep pooled; 40b dropped |
| 41 | TennisMyLife match data | 41a, 41b locally complete; 41c conditional |
| 17 | Multi-sport foundation | Complete |
| 18 | NFL data sourcing | Complete |
| 19 | NFL support | Complete |
| 24 | NFL game-line model | Complete |
| 28 | NFL game-line CLV check | Complete |
| 29 | NFL game notes | Complete |
| 30 | NFL team stats in game notes | Complete |
| 43 | NFL matchup and usage context | Complete; display only, aDOT unavailable |
| 31 | Web redesign | Complete |
| 32 | Tennis detail pages | Complete |
| 33 | NFL redesign and detail pages | Complete |
| 25 | Market-relative prop rating | 25c conditional |
| 27 | NFL prop probability model | 27h conditional |
| 34 | More NFL prop lines | Complete |
| 35 | Line-only prop display | Complete |
| 36 | NFL best line | Complete |
| 39 | NFL Rec Targets projection | Complete: gray reference and separate reporting; P(over) hidden |
| 37 | Public read-only demo | Complete |
| 20 | NBA support | Complete |
| 42 | NBA prop board | 42a-42d complete; hosted responses confirmed 2026-10-23 |
| 44 | NBA over probability, second method | 44a complete; 44b waits for 2026-27 weeks 1-4 |
| 45 | NHL support | Planned (added 2026-10-23); 45a sourcing decided, completing |
| 21 | WNBA support | Planned |
| 22 | Three-way market support | Planned |
| 23 | Soccer support | Planned |
| 38 | Structural redesign | Complete |

15 leaf items remain, with these gates:

| Item | Outcome | Gate |
|---|---|---|
| 16f | Tennis set-handicap projection | Parked until regular, correctly identified provider lines exist |
| 41c | Serve in-house ELO | Conditional on 41b's forward verdict passing (accruing from 2026-10-22); dropped if it fails |
| 25c | Anytime-TD market-relative rating | Requires passing forward validation; no adoption inferred here |
| 27h | NFL probability-based ranking | Requires an `adopt` verdict for a 27j slice. Standard under and demon over are rejected (final for v4); standard over (128 of 200 picks) and goblin over (10 of 200) are accruing |
| 44b | 2026-27 confirmation | Next. Scores 44a's frozen fit once, after 2026-27 weeks 1-4 are fully played with box scores (about 2026-11-17); stops as accruing before then |
| 44c | Serve and freeze | Only for markets 44b shows; own P(over) version and sample |
| 45a | NHL data sourcing | Decisions recorded 2026-10-23 (below); awaiting `/complete` |
| 45b | NHL schedule and box scores | After 45a's source choice |
| 45c | NHL prop lines | After 45b (players and games to link to) |
| 45d | NHL game odds | After 45b; Odds-API.io hourly quota, no The Odds API credits |
| 45e | NHL slate and game page | After 45b-45d |
| 45f | NHL injuries and starting goalies | After 45e; display only |
| 21 | WNBA support | Choose schedule/stats sources when specifying it |
| 22 | Three-way market support | Follows WNBA in plan order; prerequisite for soccer |
| 23 | Soccer support | Depends on three-way markets and sport-specific sources |

Run `/feature 45a` to spec NHL sourcing; 44b resumes on its branch once its gate reads `ready`. Rec Targets reporting now
describes coverage and settlement, but cannot accrue probability-based picks
while P(over) is hidden. Adoption work still requires the pre-registered
verdicts; this refresh makes no new verdict or model claim.

### Detailed feature context

**45. NHL support (planned, added 2026-10-23).** Ingest and surface NHL on
the NBA team-sport pattern: shared `sport_*` tables, the 17c prop pipeline
and the web sport registries, with no third parallel stack (item 17's rule).
Models follow NBA's backtest-first, pre-registered gates, and edges stay gray
until a ranking slice reads `adopt`. Projection, P(over), frozen predictions,
a model page and a prop board are later sub-items, added once 45a-45e ship.

| Step | Outcome |
|---|---|
| 45a | Sourcing and structural decisions (see NHL data below); research only |
| 45b | Seed `nhl` in `sports`; teams, players, games in `sport_*`; skater and goalie box scores in NHL stat tables; 2023-24 through 2026-27 backfill and daily refresh |
| 45c | PrizePicks NHL lines through the shared pipeline, linked, all line-only |
| 45d | DraftKings and Bet365 moneyline (overtime included), puck line and total from Odds-API.io into `sport_game_odds` under provider `odds_api_io`, de-vigged per book; no The Odds API credits |
| 45e | NHL in `SPORTS`, `SPORT_PAGES` and `SPORT_STATUS`; table-first slate and game page with market, movement and gray line-only prop rows |
| 45f | ESPN injury and probable-goalie (`Expected`/`Confirmed`) snapshots before puck drop, linked by name and team; display only |

- **What NHL breaks** (project-plan §3): low scoring, so count props are
  small integers; the puck line is fixed at +/-1.5; moneylines may be priced
  with or without overtime; skaters and goalies have different stat sets.
- **Odds provider (45a, owner option A):** NFL and NBA already use about
  397 of The Odds API's 500 monthly credits in season (the older 330 figure
  predates 36a's Pinnacle runs), so NHL odds come from Odds-API.io instead.
  Its NHL `ML` is two-way with overtime included; no Pinnacle, so fair
  prices de-vig each book's own pair.
- **45a decisions (load-bearing for 45b-45f; evidence in the 45a spec):**
  - **Ids:** NHL `playerId`, `gameId` and tri-codes (`TBL`, `UTA`) as
    `source_player_id`, `source_game_id` and `team_code`. PrizePicks (`TB`
    to `TBL`; players by folded name and team, never position), Odds-API.io
    (full names, league slug `usa-nhl`) and ESPN (name and team) map onto
    them through pure, coverage-tested functions.
  - **Tables:** `nhl_skater_game_stats` (position, goals, assists, points,
    shots, power-play goals and points, shorthanded points, plus/minus, hits,
    blocked shots, faceoffs won and lost, PIM, giveaways, takeaways, OT
    goals, TOI seconds) and `nhl_goalie_game_stats` (started, decision,
    saves, shots against, goals against, TOI seconds); unique (`player_id`,
    `game_id`). No row means did not play, a void, never zero.
  - **Markets** (PrizePicks `NHL` league; `NHL1P` first period stays off the
    board): Shots On Goal, Points, Assists, Goals, Power Play Points, Blocked
    Shots, Plus/Minus, Hits, Time On Ice, Faceoffs Won, and goalie-only Goalie
    Saves and Goals Allowed. `(Combo)` and Fantasy Score are not mapped. Time
    On Ice's line unit is confirmed in 45c.
  - **OT/SO:** stored scores are the official final, shootout winner
    included; nullable `sport_games.end_period` (`REG`, `OT`, `SO`), NHL
    only. Player and goalie stats exclude shootouts.
  - **Period and season:** NBA's regular-season week; break weeks have no
    games and are never periods. `season` is the start year; `REG` and `PST`
    only, no preseason.
  - **Goalie lines** can be posted for a goalie who does not start (that line
    voids); a later goalie projection must condition on the starter (45f's
    data). Some demon and goblin lines allow unders; 27i's rule still plays
    them over only.

**44. NBA over probability, second method (planned, owner-selected 2026-10-23).**
20g1's ratio-quantile fit hid eight of nine NBA markets, and returns no
P(over) for whole-number lines. Its record shows two failure kinds: small
counts (blocks ECE 0.081, worst bin 0.142; threes and rebounds on a worst
bin) and large sums that lose to a plain normal on Brier (points and all
four combos). Item 44 adds a sport-neutral P(over/under/push) method in
`app/core/` (no NBA import, reusable later by NHL or NFL count markets),
with a per-market distribution (discrete count model or fitted-variance
normal) chosen on 2024-25 alone in a pre-registered order.

- **44a result (complete 2026-10-23; archive
  `blueprint/history/features/44a-nba-pover-method.md`):** rules
  pre-registered in `ebd4aea` before any fit; cross-fitted on 2024-25 by
  ISO-week parity (2025-26 and 2026-27 rows read: 0). Selected:
  `scaled_normal` (variance `a + b * projection`) for points and all four
  combos, `negbin` for rebounds; threes (worst bin 0.052) and blocks not
  carried. Frozen in the generated, hook-protected
  `app/core/nba_over_probability_v2_fit.py`; shared math in
  `app/core/count_over_probability.py` (sport-neutral). The `scaled_normal`
  Brier margins over the constant-sigma normal are thin (0.0003 to 0.0011).
  Merged fast-forward so `ebd4aea` stays on `master`. Backtest only.
- **Evidence (option A, decided 2026-10-23):** 2025-26 has been read twice
  (20f, 20g1), so confirmation uses a fresh 2026-27 sample, the first 4
  whole regular-season weeks, scored once under 20g1's display rule
  unchanged (300+ cases, ECE <= 0.02, no 200+-pair bin off by more than
  0.05, Brier no worse than a normal). 44a reads neither 2025-26 nor
  2026-27.
- **Unchanged:** projection `nba-reference-v1`, gaps, ordering, picks and
  gray display. A shown market uses a new P(over) version and its own
  ranking sample, leaving the `nba-pover-v1` assists sample untouched (44c's
  spec decides how, likely 39d's separate-report pattern).

**43. NFL matchup and usage context (complete 2026-10-22).** Game notes
show current-season position production allowed with league ranks; the game
page shows player target/carry shares, and shared prop drawers show neutral
last-three-versus-season usage, with explicit samples, date windows and
missing-data states. Built from existing NFLverse weekly stats, snaps and
as-of rosters; aDOT stays unavailable (no verified raw air-yard totals).
No projection, probability, ordering, signal color or ranking change. Hosted
rendering was not checked by this refresh. Archive:
`blueprint/history/features/43-nfl-matchup-usage-context.md`.


Numerical results and samples below are dated observations from the completed
work. Regenerating this overview does not read a holdout again, retune a rule,
or establish a current slice verdict; the model reports carry those results.

**Shipped: tennis**

1. **Match ingest** - ATP and WTA matches from livetennisapi, today plus tomorrow.
2. **Player identity resolution** - aliases and slugs reconciling names across four sources.
3. **ELO ratings** - overall and per-surface from TennisAbstract, refreshed daily by the local `Lineform ingest_daily` task since fix `elo-refresh-local` (Cloudflare blocks GitHub's runners).
4. **Rolling player stats** - serve and return form over rolling windows, with surface and contextual splits.
5. **Odds ingest** - timestamped book odds for staleness detection (the plan names The Odds API; tennis actually uses Odds-API.io, see Open questions).
6. **Model ensemble** - *the headline feature.* Blends ELO, LightGBM, and de-vigged market probability with tour-specific weights, emitting quality flags.
7. **Match predictions UI** - daily slate with win probabilities, H2H, and player comparison.
8. **Best picks** - ranks +EV plays out of the ensemble. Moneyline picks are off since 26d (see Tennis model today); derived, serve-edge and prop picks remain.
9. **Props pipeline** - PrizePicks and DraftKings ingest, projection, EV scoring, audit view.
10. **Bankroll builder** - Kelly stake sizing and parlay suggestions.
11. **Bet tracking** - *removed 2026-10-15:* bets are tracked in Pikkit; the page and `/bets` API are deleted, and the `bets` table stays until a later migration drops it.
12. **Admin surface** - flagged players, manual stat and ELO refresh, behind the shared key.
13. **Declare test dependencies** - pytest is declared in `api/requirements.txt`.
14. **Clean up one-off scripts** - ad-hoc check, fix, diagnose, and temp files archived outside the live app tree.
15. **Prediction accuracy pass** - calibration and feature quality, measured on held-out results.
16a. **Projection tightening** - opponent double-fault pressure and match-closeness-aware total-games probabilities.
16b. **Odds free-tier rate-budget hardening** - lower scheduled request volume and stop at the quota safety floor.
16c. **Odds market inventory and book-config refactor** - deterministic bookmaker-market inventory and one configured persistence loop.
16d. **Provider compatibility and dynamic Live Odds** - one bounded probe for the supported tennis book scope; Live Odds rendered only returned books. *The Live Odds page and `/tennis/props/live-odds` were removed 2026-10-15;* the best-picks live moneyline fallback keeps the shared fetch.

**Shipped: NFL, item 19 complete (built before item 17)**

18. **NFL data sourcing** - NFLverse for schedules and weekly player stats, PrizePicks for prop lines.
19a. **NFL schedule and stats ingest** - teams, players, games, weekly player stats.
19b. **NFL baselines and prop-line board** - historical player baselines plus PrizePicks prop snapshots.
19c. **Prop-line player linking and unified slate** - resolve provider names to `sport_players`, compute edge, one NFL page.
19d. **Current-season NFL data** - 2025 and 2026 loaded so baselines match live prop lines.
19f. **NFL book odds ingest** - game moneyline, spread, and total from The Odds API, de-vigged into market probabilities.
19e. **NFL projection model** - conservative player-history plus game-moneyline projection.
19g. **Opponent-adjusted NFL prop projections** - bounded, pre-game defense-versus-position adjustments.
19h. **NFL player usage inputs** - NFLverse targets and volume signals stored and used in projections.
19i. **NFL sportsbook anytime TD odds** - per-game `player_anytime_td` prices from The Odds API under a credit floor, shown beside the anytime-TD baseline.
19j. **NFL red-zone usage for anytime TD** - per-game carries and targets inside the 20 and inside the 5 stored from play-by-play, plus a reusable anytime-TD backtest. **Not adopted:** it failed the holdout rule (QB and RB got worse), so the model ignores it.
19k. **NFL weekly rosters** - each player's team per week, so baselines, matchups, and linking use the as-of team instead of last-write-wins `team_id`.
19l. **NFL injuries and depth charts** - pre-game injury status and depth order on the slate. **Display only;** no model use yet.
19m. **NFL snap counts** - per-game offensive snap share. **Adopted for RB and TE anytime TD** after passing the 2025 holdout; QB and WR unchanged.
19n. **NFL scoring environment for anytime TD** - historical NFLverse closing lines, roof, and rest stored on `sport_games`, plus WR/TE end-zone targets. **Neither signal adopted:** both tied the 2025 holdout. The stored game lines are the market baseline item 24 builds on.

**NFL anytime-TD model today** (unchanged by 27c to 27g, which leave anytime TD
alone; the shared projection version is now `opponent-dvp-tg-blend-usage-snap-v4`): recency-weighted
TD history shrunk toward the position; for RB and TE, blended 0.6 with a
snap-share expected TD rate (frozen 2024 fit). Every new NFL signal goes through
the anytime-TD backtest (`python -m app.backtest.nfl_anytime_td`) with a
pre-registered adoption rule before it feeds a projection.

**Shipped: NFL game lines, item 24 complete (no signal adopted)**

A separate model from player props, for spread, moneyline, and total. Each
signal is adopted only when a held-out backtest against closing lines passes.

24a. **Team ELO ratings** - margin-aware team ELO computed pre-game from historical NFLverse scores, stored per team per game (`nfl-elo-v1`).
24b. **Game-line backtest** - ELO-derived spread, win probability, and total plus a scoring rating, scored against closing lines on the 2022-2025 holdout. **All three markets rejected.**
24e. **Totals context** - NFLverse game temperature and wind stored on `sport_games`, plus roof and rest, as closing-line residual adjustments. **Both arms rejected.** Built before 24c.
24c. **Team efficiency ratings** - per-team, per-game offensive plays, EPA, and successes stored from play-by-play for 2012-2026, replayed into EPA-per-play, success-rate, and pace ratings as residual adjustments. **Both arms rejected.**
24d. **Game-line slate** - model spread, win probability, and total in a muted strip beside the market on the NFL slate. **Display only**, with a fixed "not a pick" caveat, because 24b, 24e, and 24c all rejected.

**NFL game-line model today:** none is adopted. The closing market beat ELO,
the scoring rating, weather/roof/rest context, and team efficiency on the
2022-2025 holdout. The slate shows `nfl-elo-v1` spread and win probability and
the 24b scoring-rating total (`NFL_SCORING_V1`, learning rate 0.05) as context
only. The gate for any new signal is `python -m app.backtest.nfl_game_lines`
with `--signal ratings | context | efficiency` (and `--dry-run-fit` to print
the fit only). The 2022-2025 holdout has been scored three times, so any new
signal must be confirmed on 2026 onward. The one forward question still open
is item 28's CLV check, below.

**Shipped: game-line CLV check (item 28, added and shipped 2026-09-26)**

The one exception to the game-line closure. It asks a narrower question than
24b: not whether the model beats the close, but whether the close moves toward
the model from an early-week line the app already stores. If it does, betting
that early number when the model disagrees beats the close.

28. **NFL game-line CLV check** *(shipped; verdict accruing)* - `python -m app.backtest.nfl_game_line_clv [--season 2026]`, also on the Tuesday `nfl-ingest.yml` Summary page. Grades the pinned `nfl-elo-v1` spread and `NFL_SCORING_V1` total (replayed in-process, not read from `nfl_team_elo`) against each game's entry line. Read-only; no model, schema, or UI change.

**The pre-registered CLV rule** (fixed 2026-09-26, before any movement was
read; `app/core/nfl_game_line_clv.py`):
- **Entry line:** the earliest `draftkings` row (else the earliest other
  lowercase The Odds API book) fetched from 6 hours after the previous week's
  last kickoff (7 days before kickoff in week 1) to 24 hours before kickoff.
  The capitalized `DraftKings` / `Bet365` rows from the 2026-09-17 run are
  ignored.
- **Close:** NFLverse `spread_line` (sign flipped to book sign) and
  `total_line`, completed games only; NFLverse fills these before kickoff.
- **Pick:** |model - entry| >= 1.5 points. **CLV:** close movement toward the
  model, in points.
- **Verdict sample:** per market, the first whole, fully played weeks holding
  150 picks. **Pass** only if mean CLV minus 2 SE > 0; a reject is final for
  these model versions.
- **Context only:** entry-line lead time, the toward/away/flat split, W-L-P
  against the entry line, and weeks 1-4 versus 5+.

**First run (2026-09-26):** week 2 only, 8 spread and 9 total picks, accruing.
Week 1 has no stored lines, and every week-2 entry line came from one Friday
run about 47 hours before kickoff, so it is not yet the Tuesday line intended.
The strip stays muted; only a passing verdict justifies a later item that
shows a bettable tag.

**Shipped: NFL game notes (item 29, added and shipped 2026-09-27)**

A pre-bet reading aid, not a model change. Before it, injury and depth context
appeared only as tags on players who have a prop line (19l). Item 29 added one
panel per game, built from data already stored. It shipped on the slate; since
33a it lives on the game page, and 33b's slate cards show its injury counts and
line movement:

- **Injuries:** both teams' QB, RB, WR and TE injury report for the week
  (`nfl_player_injuries`), including players with no prop line.
- **Depth changes:** promoted, demoted and new depth-chart entries for the week
  (`nfl_player_depth_charts`, same rule as `app/core/nfl_availability.py`).
- **Line movement:** spread and total, earliest to latest pre-kickoff
  `sport_game_odds` row from one book. This is not item 28's pre-registered entry
  line.
- **Form and rest:** each team's last three completed results, rest days
  (`sport_games.home_rest` / `away_rest`), and a short-week tag.

**Display only:** it never changes an edge or rank, and never links an injury
to a prop. No schema change. Served by its own `GET /nfl/game-notes?season=&week=`
(`app/services/nfl/game_notes.py`), kept out of `build_slate` so 27a grading
and 27i frozen predictions do not pay for it. **Load-bearing:** later
display-only game context extends this response, not `/nfl/slate`.
Practice-only injury entries list only when the player was limited or did not
practice; depth moves show only at rank 2 or better.

**Shipped: NFL team stats in game notes (item 30, added and shipped 2026-09-28)**

30. **NFL team stats in game notes** - a "Team stats" block in each game's
notes panel, extending the `/nfl/game-notes` response as item 29 requires.
Both teams' season-to-date offense per game, and the same stats allowed on
defense, each with a league rank:

| Stat | Source |
|---|---|
| Points | `sport_games` scores, completed REG games |
| Pass yards, rush yards | summed `nfl_player_weekly_stats` per team-game; allowed via `opponent_team_id` |
| Plays, EPA per play, success rate | `nfl_team_game_efficiency`; allowed = the opponent's row in the same game |

**Display only, no schema change.** It never changes an edge or rank. It uses
the shared as-of cutoff (this season, weeks before the slate week).

**Shipped: web redesign (item 31, added 2026-09-28, complete)**

A restyle of the web app from the `/prototype` mockups in `prototypes/`, after
OddsJam (odds tables), Outlier (prop cards) and Robinhood (large numbers, one
signal color). **Restyle only:** it never changes which numbers are colored,
sorted, ranked, or shown; every display rule below still holds.

31a. **Theme and app shell** *(shipped)* - port `prototypes/theme.css` into `web/src/index.css` and the Ant Design theme, and restyle the nav and page header, so every page takes the new palette with no layout change.
31b. **Tennis slate** *(shipped)* - summary strip, best-pick cards, and the match table grouped by tournament (`prototypes/tennis-slate.html`).
31c. **Tennis prop board** *(shipped)* - prop cards with hit probability against the payout break-even, recent-match bars, and hit rates (`prototypes/tennis-props.html`).
31d. **NFL prop board** *(shipped)* - prop cards with last-games bars and hit rates, keeping every NFL display rule (`prototypes/nfl-prop-board.html`).
31e. **NFL prop detail** *(shipped)* - the evidence panel restyled as a detail view: projection breakdown, game log, lines, game market (`prototypes/prop-detail.html`).

Pages not mocked (NFL slate, Live Odds and My Bets, both since removed, and Admin) took the palette from 31a
and kept their layouts. The item-31 and item-32 mockups were discarded at 31e's
`/complete`; item 33 later redesigned the NFL slate.

**Shipped: tennis detail pages (item 32, added 2026-09-29, complete 2026-09-30)**

Matches, players and the model's graded record get their own linkable pages,
from the approved mockups `prototypes/tennis-match.html`, `tennis-model.html`
and `tennis-player.html`. **Display only:** no page changes a probability,
edge, rank or pick. No schema change.

32a. **Match detail page** *(shipped 2026-09-29)* - `/tennis/match/:matchId` replaced `PlayerComparisonModal` (deleted): model, market and **moneyline EV** (green only for a positive-EV moneyline best bet, the slate's rule; edge shown gray beside it); ELO, LightGBM, market and ensemble with weights and flags; per-book moneyline and total-games movement; last-5 form with box scores; a sidebar with H2H, books (closing prices once finished), serve and return, and the match's PrizePicks lines. The slate's "Open match analysis" is a link to it.
32b. **Model track record page** *(shipped 2026-09-29)* - `/tennis/model`, reached from a Model view in the tennis Slate/Props switch, serves the 26a, 26b and 26f grading as three read-only endpoints: log loss and Brier by component and tour against the market, ATP+WTA calibration, closing-line value, PrizePicks over rates by stat and line type against break-even, and hit rate by confidence tier. First read: the ensemble is not ahead of the market (+0.0060 +/- 0.0068, ATP+WTA); five standard PrizePicks stats sit more than 2 SE below break-even; every tier is accruing.
32c. **Player page** *(shipped 2026-09-30)* - `/tennis/player/:playerId`: ELO over time (overall solid, the next match's surface dashed; all history, no range toggle) with tour rank by ELO; 52-week serve and return by surface against the same-tour average; a match log with box scores; 52-week record splits; settled `props-v2` lines; aliases and data freshness. Player names link to it from the match page header, the match log's opponents, and the slate's detail panel.

**What 32a fixed as load-bearing:**
- **One prediction path.** `predict_today` delegates to
  `predict_matches(db, registry, matches, ref_date)` in
  `app/services/tennis/predictor.py`; the match page predicts one match
  through it with `ref_date = min(match_date, today)`, so page and slate never
  disagree. The old per-match `predict_match` is unused.
- **No leakage on finished matches.** Any status other than scheduled or live
  reads the latest `predictions` row with `generated_at < start_utc`
  (`get_prestart_prediction`), paired with the moneyline that prediction saw
  (as 26a pairs them), never a fresh prediction.
- **`MatchDetailResponse`** (`GET /tennis/matches/{id}`) is extended by later
  match-level features rather than adding endpoints; 32c links its player ids.

**What 32b fixed as load-bearing:**
- **The color rules** (`app/core/track_record.py`, pure):
  - a comparison against the market is green only when it beats the market by
    more than 2 SE, and never red, because losing to the market is expected
  - a rate against break-even is green or red only past 2 SE
  - goblin and demon lines, and a 0% or 100% rate, carry no error bar and are
    never colored
- **The pre-registered tennis tier rule** (fixed 2026-09-29, before any tier
  data was read; tennis's first, the counterpart of NFL's 27i):
  - grades `props-v2` standard lines only, for LOCK, STRONG and LEAN
  - the verdict sample is each tier's first whole snapshot days (UTC date of
    `snapshot_at`), at least 3 days old, holding 200 decided picks; later days
    never change it
  - pass only if the hit rate minus 2 SE beats the 57.7% break-even; a reject
    is final for `props-v2`
  - a constants test pins `TIER_RULE_VERSION` to `PROJECTION_VERSION`, so a
    projection bump fails until the rule is reconsidered
- **The three responses**, each cached 15 minutes with `TimedSingleFlight`,
  built from the CLIs' own pure pieces (`settle_rows`, `grade`, the
  `tennis_grading` core), so page and report cannot disagree. A later tennis
  tier-adoption item reads the tier verdict from `/tennis/model/prop-tiers`.

**What 32c fixed as load-bearing:**
- **One player page.** The route `/tennis/player/:playerId` and
  `PlayerDetailResponse` (`GET /tennis/players/{id}`). Later player-level
  features extend that response or add a sibling endpoint under
  `/tennis/players/{id}/`; they do not add another page.
- **Record splits are pure** (`app/core/tennis_player.py`): a 365-day window;
  vs top 20 uses the opponent's rank at match time; deciding sets and
  tie-breaks count only scores passing `is_completed_score`, so a retirement
  counts in the W-L but not in the set splits.
- **Honest labels.** `break_pct` shows as BP converted, and the two "per game"
  columns as rates per serve point (open question 30).
- **No signal color.** W/L, prop hits and misses, and the model-pick summary are
  weight and gray only; the past-props card is anecdote, graded in full by 32b.
- **Slate predictions carry `p1_id` / `p2_id`** so the slate can link; a name
  with no id stays plain text.

**Shipped: NFL redesign and detail pages (item 33, added and complete 2026-09-30)**

A game-first NFL slate plus linkable game, player and model track record pages,
built from the approved mockups `nfl-slate.html`, `nfl-game.html`,
`nfl-player.html` and `nfl-model.html`. The NFL counterpart of item 32.
`prototypes/` was discarded at 33d's `/complete`; the theme lives in
`web/src/index.css`.

- **Display only.** No page changes a projection, edge, rank or pick.
- **NFL prop edges are gray** on the slate, prop board, game and player pages
  until 27h adopts a slice (resolved open question 28).
- **No UI text below 11px** on these pages, micro-labels included.

33a. **Game page** *(shipped 2026-09-30)* - `/nfl/game/:gameId`: market beside the muted model (spread, win probability, total), spread and total movement from `sport_game_odds`, injuries, depth changes, form and rest, team stats, and the game's props as prop-board cards. It absorbed the slate's matchup bar, model strip and notes panel.
33b. **Game-first slate** *(shipped 2026-09-30)* - `/nfl` is a summary strip, a legend and one card per game grouped by kickoff window (market, muted model, conditions, injury counts, line movement, top three props by edge), each linking to the game page. The signal boards, matchup bar, model strip, notes panel and inline evidence panel left the slate. `/nfl/game-notes` gained `awayScore` / `homeScore` (null until final); `/nfl/slate` and `build_slate` are unchanged. `?gameId=` on `/nfl` redirects to the game page.
33c. **Player page** *(shipped 2026-09-30)* - `/nfl/player/:playerId`: team, depth and injury this week; usage by week (carries, targets, snap share, last 8 games); this week's lines with the evidence drawer; a game log with the stored PrizePicks line per game; past line counts against break-even (anecdote, never colored); record splits. Linked from the evidence panel's player name and the game page sidebar.
33d. **Model track record page** *(shipped 2026-09-30)* - `/nfl/model`, the third NFL Slate / Props / Model view, serving the 27j slice progress, 27a line grading, 28 game-line CLV and 27g P(over) calibration as four read-only endpoints. First read: all four 27j slices accruing after week 3; 27a 51.0% +/- 1.3 on 1,430 calls, more than 2 SE below 57.7%, with all three edge buckets also below; both CLV markets accruing (spread +0.42 +/- 0.23 on 19 picks).

**What 33a fixed as load-bearing:**
- **One game page.** The route `/nfl/game/:gameId` and `NflGameDetailResponse`
  (`GET /nfl/games/{id}`: the game plus pre-kickoff spread and total steps from
  one book per market). Later game-level display context extends that response
  or adds a sibling under `/nfl/games/{id}/`, never another page.
- **Board parity.** Game-page cards take rank and edge share from the week-wide
  prop board (`nflGameProps`), read as of just before kickoff once a game
  starts, so a card never disagrees with `/nfl/board`.
- **Gray edges are scoped.** `--nfl-green` and `--nfl-red` are set to the text
  color on the shared `.nfl-slate` root, which the slate, prop board and game
  page all use (33b moved the override there).
- **The page never calls `build_slate`** beyond the week the slate already
  fetches.

**What 33b fixed:** the card view model (`NflSlateCardModel`, pure, in
`web/src/utils/nflSlate.ts`) is not load-bearing beyond the slate. A final
card's closing lines are the last pre-kickoff line from one book (game notes'
`lineMovement`), not NFLverse's `spread_line` and not item 28's entry line.

**What 33c fixed as load-bearing:**
- **One NFL player page.** The route `/nfl/player/:playerId` and
  `NflPlayerDetailResponse` (`GET /nfl/players/{id}`). Later player-level
  features extend that response or add a sibling under `/nfl/players/{id}/`,
  never another page (32c's rule for tennis).
- **This week's lines come from the week's `/nfl/slate`,** not the player
  response, so ranks and edges match the board.
- **`team_spread` is from the player's side,** book sign: negative means the
  player's team was favored. Snap share is `offense_pct` (0 to 1); a missing
  snap row is null, never 0.

**What 33d fixed as load-bearing:**
- **One NFL model page.** The route `/nfl/model` and four responses:
  - `GET /nfl/model/ranking?season=` (27j): each slice's verdict, sample, hit
    rate, SE and signal, plus the funnel, coverage and last settled week. **27h
    reads the slice verdict here.**
  - `GET /nfl/model/prop-lines?season=` (27a, plus 27g's forward read): model
    calls overall, by edge bucket, market and week, and served P(over) against
    settled lines.
  - `GET /nfl/model/game-line-clv?season=` (28): per market, the headline
    (every pick while accruing, the verdict sample once decided), all, weeks
    1-4 and 5+. A later bettable game-line tag reads the verdict here.
  - `GET /nfl/model/over-probability-fit` (27g): the fit's display table, with
    `served` false once the projection version moves on.
- **Page and report cannot disagree.** The 27a, 27j and 28 CLIs and the
  endpoints share loaders in `app/services/nfl/track_record.py`; each section
  is cached 15 minutes per season with `TimedSingleFlight`. The 27a load
  replays `build_slate` for every week (22 s cold alone, about 46 s beside the
  other sections), so its web request has a 90 s timeout.
- **Pre-registered verdicts stay gray until decided** (`verdict_signal` in
  `app/core/track_record.py`, now shared by both sports). 27a rates, which have
  no verdict rule, are colored past 2 SE against 57.7%. The 27g section is
  never colored.
- **The 27g fit table is frozen** in `app/core/nfl_over_probability_fit_report.py`,
  transcribed from the 27g archive rather than re-run (a re-run reads the 2025
  holdout again). Tests pin it to `nfl_over_probability_fit.py`, so
  regenerating the fit fails until the table is updated from the new run.

**Conditional: market-relative prop rating (item 25; only 25c remains)**

A cross-sport concern that surfaced through NFL, not further NFL modelling. The
sportsbook prop prices item 19i stores are Yes-only, so their probabilities carry
the book's margin: week 2 2026 per-game sums run 3.58 to 5.85 against roughly 4.0
to 4.3 expected distinct scorers, and the model sits a median 1.0 points below
book across 315 players. De-vigging that is the same problem the tennis ensemble
(item 6) already solves separately, so item 17 would have to converge the two
regardless.

25a. **Yes-only de-vig** - per-game normalization of the book consensus as a pure `app/core/` function, shown beside the raw price.
25b. **Forward holdout accrual** - settle stored prop prices against results weekly and report the accumulating sample. No model change.
25c. **Adopt in prop rating** - rate anytime TD against the normalized probability instead of the 0.5 line, only on a passing pre-registered backtest.

> **There is no historical holdout, and this is the binding constraint.** The Odds
> API sells current markets only, so `nfl_player_prop_odds` starts at item 19i:
> one week (2026 week 2, 15 games, 391 players) and zero settled player-games.
> Evidence accrues forward at roughly 350 player-games a week, so 25c is not
> assessable until week 8 to 12 at the earliest, and may never be adopted. The
> anytime-TD board stays at its handful of standard lines until then.

**Conditional: NFL prop probability model (item 27; only 27h remains)**

A 2026-09-25 review found that the PrizePicks prop model behind most NFL edges
(19e, 19g, 19h) was never validated. Graded on 2026 week 2 standard lines, it
hit 49.4% of 681, against a **57.7% per-pick break-even** for the owner's 2-3
pick Power entries (about 52.4% for sportsbook props at -110). The largest edges
did no better.

**Structural causes found:**
- **The edge is mean minus line.** Yards are right-skewed, so means sit above
  PrizePicks' near-median lines and yards lean OVER regardless of matchup.
- **Stale seasons.** A season counts only after 4 games, so about 95% of early
  lines price on last season.
- **Moneyline scaling raises every market for favorites,** the wrong sign for
  passing volume. 27e dropped it for the three passing markets.
- **The matchup (DVP) inputs** count player rows as games and pool all loaded
  seasons equally.
- **Fantasy used NFLverse PPR,** not PrizePicks' formula. 27f fixed settlement;
  the projection still averages PPR.

27a. **PrizePicks line grading** *(shipped)* - `python -m app.backtest.nfl_prizepicks_lines`, also on the Tuesday `nfl-ingest.yml` Summary page. First run, 2026-09-26: **48.1% +/- 1.8 on 750 calls** against 57.7%. Edges of 15% and up hit 49.5%, and receiving yards 40.7%. It replays today's code on past weeks (`build_slate` in `app/services/nfl/slate.py`), so it is not a frozen record.
27b. **Projection backtest harness** *(shipped)* - `python -m app.backtest.nfl_projections [--arms production,<variant>]` replays 2025 through the slate's own `_slate_line` and scores MAE, bias and share-below per market. **F-02 settled: the usage adjustment stays** (removing it is 7-9 SE worse). Every market leans OVER (`share_below` 54% to 64%).
27c. **Matchup by team-game** *(shipped; passing completions only)* - defense-versus-position from per-game position totals over a 17-team-game window (`app/core/nfl_team_game_dvp.py`). Adopted for passing completions (-1.65%, 2.3 SE); the other seven markets rejected.
27d. **Season blending** *(shipped; three passing markets only)* - current and previous season weighted by games, last season's at 0.6 (`app/core/nfl_season_blend.py`), instead of the 4-game switch. Adopted for passing attempts (-4.7%), completions (-4.1%) and yards (-2.5%); receiving, receptions and fantasy rejected, rushing got worse.
27e. **Game environment** *(shipped; moneyline dropped for three passing markets, environment not adopted)* - per-market slopes on implied team total and margin, relative to the player's baseline games, fitted on 2024 (`python -m app.backtest.nfl_game_environment_fit`, `app/core/nfl_game_environment.py`). Only the rushing margin slopes survived the fit, and rushing was rejected on 2025. Passing attempts (-5.9%), completions (-4.0%) and yards (-1.9%, 2.06 SE) passed because removing the moneyline bump helped, so they now skip it.
27f. **PrizePicks fantasy scoring** *(shipped; settlement only, projection not adopted)* - scoring components stored per player-game (`0036`) and `prizepicks_fantasy_points` computed at ingest by `app/core/nfl_fantasy.py` (-1 per interception and lost fumble, +6 per fumble-recovery TD, unlike PPR). Fantasy lines settle on it in 27a, 27b and 27g. Projecting from it was rejected (+0.20% MAE, about 2 SE worse): it exposed an existing QB OVER lean.
27g. **Over probability** *(shipped; display only, 2 of 8 markets shown)* - per market and position, an empirical distribution of actual / projection (41 quantiles) turns a projection into P(over line) (`app/core/nfl_over_probability.py`). Fitted on the 2025 replay, cross-fitted by week parity, and gated by a pre-registered display rule (300 cases, ECE <= 0.02, no bin of 200+ pairs off by more than 0.05, Brier no worse than a normal). **Receiving and rushing yards show; passing, receptions, rushing attempts and fantasy are hidden.** At a line equal to the projection, receiving yards go over only 38%. Frozen tables live in the generated `app/core/nfl_over_probability_fit.py` (`python -m app.backtest.nfl_over_probability_fit --write`).
27i. **Frozen line predictions** *(shipped)* - after each `nfl-prop-lines.yml` snapshot, `python -m app.ingest.nfl_prop_predictions` writes what the slate served for every line not yet kicked off into `sport_prop_predictions`. It also fixes the ranking rule (`app/core/prop_ranking_rule.py` since 17c, formerly `nfl_ranking_rule.py`) before any frozen week existed. 2026 week 3 was the first frozen week (9,163 rows).
27j. **Forward ranking check** *(shipped; standard under and demon over rejected, standard over and goblin over accruing, as of week 6 2026)* - `python -m app.backtest.nfl_ranking_check`, also on the Tuesday `nfl-ingest.yml` Summary page. Grades each provider prop's **latest frozen pre-kickoff row at the line it was frozen on** (`app/core/prop_ranking_check.py` since 17c), applies 27i's rule unchanged, and prints per-week frozen coverage and the pick funnel. First settled week: 3, after the 2026-09-29 stats load.
27k. **Wind for passing props** *(shipped; not adopted)* - a wind slope above 10 mph for the three passing markets, fitted on 2024 (`python -m app.backtest.nfl_wind_fit`, `app/core/nfl_wind.py`) and scored through the 27b `wind` arm. Only passing yards kept a slope (-0.245 per 10 mph, 3.1 SE); on 2025 it improved MAE 0.73% at 1.5 SE and was **rejected**, as were attempts and completions. Windy games alone improved 5.2%, but only 15% of QB-games are windy. The seventh use of the 2025 holdout. Weather is now rejected for totals, spreads, anytime TD and passing props.
27h. **Adopt in ranking** - rank lines by P(over) against each payout's break-even, only for the slices whose 27j verdict reads `adopt`. **Blocked** until one does, and dropped if all four reject. As of 2026-10-23, standard under (53.7% +/- 2.4 on 419 picks against 57.7%) and demon over (39.4% +/- 2.9 on 289 against 41.3%) are rejected, final for `opponent-dvp-tg-blend-usage-snap-v4` and `nfl-pover-v1`; standard over (128 of 200) and goblin over (10 of 200) remain. Spec it only then (decided 2026-09-26).

**NFL prop projection model today** (`opponent-dvp-tg-blend-usage-snap-v4`):
- **Baseline:** the season chooser (4-game switch), except the three passing
  markets, which blend the current and previous season when both exist.
- **Matchup:** per-player-row DVP, except passing completions, which reads
  team-game DVP.
- **Moneyline scaling:** every market except the three passing markets
  (`MONEYLINE_UNSCALED_MARKETS`), which take no moneyline bump and carry no
  `market_missing` or `market_stale` flag.
- **Then:** the receiving usage adjustment, unchanged.
- **Flags and rank are unchanged by the blend:** the stale-season flag still
  follows the line season's own game count.
- **Fantasy** still projects from NFLverse PPR averages (27f rejected the
  switch) but settles on PrizePicks points.
- **P(over)** (`nfl-pover-v1`) is read from the 27g fit only while its
  `FIT_PROJECTION_MODEL_VERSION` equals this projection version. Any version
  bump hides it until the fit is regenerated.

**The pre-registered adoption rule** (27b, fixed 2026-09-26): per market, at
least 300 paired 2025 cases, MAE at least 1.0% lower than production, and the
paired difference below zero by more than 2 SE. Variants stack in build-plan
order (27d on 27c, 27e on both). **The 2025 holdout has been used five
times for projection verdicts** (F-02, 27c, 27d, 27e, 27f), plus a sixth read
by 27g for a display-only distribution fit that takes no projection verdict.
27k was the seventh read (rejected) and 39b's Rec Targets P(over) check the
eighth (hidden, no projection verdict).
Every adoption is confirmed forward by 27a's line grading. Fitted projection
inputs are fitted on 2024 only, never on the holdout.

**The pre-registered ranking rule** (27i, fixed 2026-09-26, before any frozen
week existed; `app/core/prop_ranking_rule.py`, shared by every sport since 17c):
- **Break-even per leg:** standard 57.7%, goblin 75.8%, demon 41.3%, imported
  from the assumed leg payouts in `app/core/prop_ev.py`.
- **Playable sides:** goblin and demon lines are over only.
- **A pick:** the side's frozen probability is at least break-even plus 3
  points. There is one pick per player, game, market, line type and side (the
  rung that clears break-even by the most).
- **Four slices:** standard over, standard under, goblin over, demon over.
- **The verdict sample is fixed:** the first whole weeks holding 200 picks
  over 4 or more weeks. Later weeks never change it.
- **Verdict:** adopt only when the hit rate minus 2 SE beats break-even. A
  reject is final for that model and P(over) version.
- **How 27j applies it** (fixed 2026-09-26, before any frozen week settled):
  - each provider prop is graded once, on its latest frozen pre-kickoff row,
    settled at that row's line; a prop with no frozen row is unfrozen, never
    replayed
  - only fully played weeks count (every REG game completed, stats loaded)
  - pushes, voids and non-full-game lines are never picks
  - rows under another model or P(over) version are excluded, so a version
    bump starts a fresh sample

**Constraints:**
- **Forward line data only.** PrizePicks lines exist only as the app stores
  them, so line-based evidence (27a, 27j, 27h) accrues forward from 2026 week 2.
  The `nfl-prop-lines.yml` snapshots (Thursday to Monday) keep it pre-kickoff.
  Frozen predictions (27i) start at 2026 week 3.
- **Harness-first inputs.** 27c-27f need no lines: they are judged on 2025
  actuals through the 27b harness.
- **Shared probability layer.** It goes in `app/core/`, written sport-agnostic
  for item 17.

**Current NFL prop display rules** (from the 2026-09-26 review fix):
- Anytime TD gets no edge or pick until 25c.
- Trust reads Ready only when a line carries method flags alone.
- A game moneyline older than 8 days at kickoff is flagged `market_stale` and not
  used. Passing lines ignore the moneyline entirely since 27e.
- P(over) (27g) is display only. It is shown muted in the evidence panel and on
  alternative-line tags, and never colored, sorted by, or compared to a payout
  until 27h.

**Shipped: more NFL prop lines (item 34, added and complete 2026-10-05)**

PrizePicks posts many NFL stats the app discards: the ingest keeps only the 9
modelled markets and logs the rest as unsupported. Line history exists only
from the day the app stores it (the binding constraint of items 25 and 27),
so item 34 stores more markets now, before any projection exists.

34a. **Settleable stat lines** *(shipped 2026-10-05)* - store Rec Targets, Pass TDs, INT, Rush+Rec Yds, Pass+Rush Yds and Pass+Rush+Rec TDs. Each settles from columns `nfl_player_weekly_stats` already holds (`targets`, `passing_tds`, `interceptions`, the yards columns, `touchdowns`).
34b. **Kicking and punting lines** *(shipped 2026-10-05)* - store FG Made, Kicking Points and Punts lines, plus per-game `fg_made` and `pat_made` from the NFLverse weekly stats file and `punts` from play-by-play (`0042`), backfilled for 2024 to 2026. Settlement rules: `field_goals_made` on `fg_made`, `kicking_points` on `3 * fg_made + pat_made` (PrizePicks' standard; confirm before grading relies on it), `punts` on `punts`.

- **Store only (load-bearing since 34a).** A line-only market never reaches
  the slate, the prop board, frozen predictions (27i), 27a line grading or
  the 27j ranking check. Since 39c, the serving universe has ten
  `NflPropMarket` markets, including Rec Targets. `V4_MARKET_FILTER` pins
  existing v4 projection, replay, 27a grading, frozen ranking and coverage
  readers to their original nine markets before latest-row selection;
  `MODELLED_MARKET_FILTER` describes the wider modelled universe. New
  readers must apply the filter for their model. `NflLineOnlyMarket` holds
  the eight remaining stored-only markets,
  whose stored strings are never renamed. Moving a market into
  `NflPropMarket` (a later projecting item) widens the filter automatically.
- **34a first run (2026-10-05, MNF board):** 958 lines stored and linked;
  every `interceptions` line was on a QB, so INT settles against
  interceptions thrown. The slate, 27a, 27j and the freeze were proved
  unchanged by the line-only rows.
- **Not stored:** "(Combo)" lines (apparently two players' stats added
  together), defensive stats, longest-play lines, quarter and half splits, and
  Rush TDs (`touchdowns` combines rushing and receiving, so no rushing-only
  count exists).

**Shipped: line-only prop display (item 35, added and complete 2026-10-05)**

35. **Line-only prop display** *(shipped 2026-10-05)* - originally all nine line-only markets from item 34 on the game page; 39c promotes Rec Targets, leaving eight. Item 38d1 changed the gray "Other lines" cards to rows. Each shows current PrizePicks rungs and recent stored results, Full game only and under the same position filter; never a pick, edge, model or drawer.

- **Load-bearing:** `line_only_value(market, row)` in `app/core/nfl_line_only.py`
  is the one settlement rule for every line-only market (a coverage test
  fails if a new `NflLineOnlyMarket` lacks a rule), and
  `GET /nfl/games/{id}/line-only-props` (`NflLineOnlyPropsResponse`) is the
  response later line-only display extends.

- **Display only, no signal.** Never a projection, edge, rank, P(over) or
  green/red; recent results are plain numbers, as on the 33c player page.
- **Its own endpoint.** Served by a sibling `GET /nfl/games/{id}/line-only-props`
  (33a's rule for game-level context), never by `/nfl/slate`, so 34a's
  modelled-market filter and board parity are untouched.
- **Recent results come from stored columns** and the settlement rules item
  34 fixed (for example Kicking Points as `3 * fg_made + pat_made`).

**Shipped: NFL best line (item 36, added and complete 2026-10-07)**

A line-shopping reference, not a model. The NFL game model loses to the
closing line (item 24), so the useful question before a bet is whether a
price beats the market, not whether the model disagrees with it.

36a. **Bet365 and DraftKings NFL odds from Odds-API.io, plus Pinnacle** *(shipped 2026-10-07)* - moneyline, main spread and main total from Odds-API.io's two allowed books into `sport_game_odds` with a new `provider` column, refreshed several times a day within the shared hourly quota; The Odds API's existing NFL odds run adds its `eu` region for Pinnacle (about 3 credits a run).
36b. **Best line and fair price display** *(shipped 2026-10-07)* - per game, each side's best price across Bet365, DraftKings and the stored US books, naming the book and its fetch age, beside the Pinnacle de-vigged fair price (low-vig consensus when Pinnacle is missing), on the game page and slate card.

- **Display only.** Never a pick, edge or signal color.
- **Provider separation (load-bearing).** Every existing reader of
  `sport_game_odds` (the slate market, line movement, game notes, item 28's
  CLV entry line) stays on The Odds API `us` rows. Item 28's pre-registered
  rule reads "any lowercase The Odds API book", so an unmarked Odds-API.io or
  Pinnacle row would enter its frozen sample.
- **Provider roles** (`project-plan.md` §4): Odds-API.io's free plan allows two
  books, shared with tennis (DraftKings and Bet365), and no sharp books; The
  Odds API supplies the other US books and Pinnacle.

**What 36a fixed as load-bearing:**
- **`sport_game_odds.provider`** (`app/core/odds_providers.py`): writers pass
  it keyword-only; every reader filters to a named provider, and pre-36a
  readers (slate market, line movement, game notes, item 28 CLV, the NBA
  slate and game) to `the_odds_api_us` only. The column keeps its default so
  workflows on older code still insert valid rows.
- **Odds-API.io parsing** (`app/core/nfl_odds_io.py`): decimal prices to
  American, de-vigged from the decimals; the main spread and total are the
  ladder rung with the lowest overround, then closest to even (Bet365 sends
  up to 77 rungs); `raw_json` keeps the chosen rung, `updatedAt` and the rung
  count. `fetched_at` is our fetch time.
- **Ingest:** `python -m app.ingest.nfl_odds_io [--days-ahead 7]
  [--min-requests-remaining 20] [--dry-run]` (`/odds/multi`, at most 10 games
  a call, 3 requests a 15-game slate, stops before 20 requests remain in the
  hour); `python -m app.ingest.nfl_odds --pinnacle` (3 credits a run).
- **Schedules:** `nfl-odds-io.yml` every 3 hours September to February;
  Pinnacle after the Tuesday odds step and in all four `nfl-prop-odds.yml`
  runs (about 15 credits a week).

**What 36b fixed as load-bearing:**
- **`bestLine` on each `/nfl/game-notes` game** (`NflBestLineSchema`;
  `best_lines` in `app/core/nfl_best_line.py`): per market, a `fair` price
  (`source` `pinnacle` or `consensus`, line, de-vigged first-side
  probability) and each side's best price, book, provider, fetch time, and
  either `evPct` (at the fair line) or `pointsVsFair` (off it). Null once a
  game kicks off or with no fresh book. The prop-comparison item reuses the
  fair-price shape.
- **The rule:** Pinnacle is the reference, never a candidate; one quote per
  book (the newest, across providers); quotes older than
  `MAX_AGE_HOURS = 36` are dropped; best side by points from that side's
  view, then price. Consensus fair needs 2+ books at the most common line.
  EV across different lines is not computed (no key-number model).
- **Display:** the game page's "Best line" card and the slate card's
  "Best ..." spread row, gray only, "Reference, not a pick".

**Complete: NFL Rec Targets projection (item 39; 39a-39d complete)**

39. **NFL Rec Targets projection** - project PrizePicks Rec Targets lines
    (standard only), the first line-only market from item 34 to get a model.

| Step | Outcome |
|---|---|
| 39a | *Shipped 2026-10-18.* Baseline chosen on 2024 only from season-average, moneyline scaling and recent form in pre-registered order; both candidates rejected, so `nfl-targets-v1` is the season average; backtest only |
| 39b | *Shipped 2026-10-18.* P(over) fitted per position on 2024 and checked once on 2025 under 27g's display rule; **hidden** (ECE 0.043, worst bin 0.078); the frozen fit module holds no tables; no production change |
| 39c | *Implemented and verified locally 2026-10-19.* Serve gray reference rows and freeze under `nfl-targets-v1`; probability fields and served probability version are null; preserve the nine v4 markets and their sample |
| 39d | *Implemented and verified locally 2026-10-19.* Settle targets and report their coverage under their own identity through API, CLI, workflow Summary and `/nfl/model`; P(over) remains hidden and probability picks stay zero |

- **Baselines on 2024 only.** Candidate baselines are compared on 2024. There
  is no incumbent projection, so no holdout verdict is taken on the
  projection itself.
- **P(over) is gated.** It is shown only if a fit on 2024 passes 27g's
  display rule on one 2025 check (the 2025 holdout's eighth read, counted in
  the archive; 20g1's pattern for NBA). 39b's check failed, so Rec Targets
  serves no P(over).
- **Its own versions (load-bearing).** 39c freezes predictions on the
  line-snapshot schedule (27i) under `nfl-targets-v1`. The candidate
  probability method is `nfl-targets-pover-v1`, but its served version is
  NULL while hidden. The default 27j report remains on
  `opponent-dvp-tg-blend-usage-snap-v4` and `nfl-pover-v1` for the nine v4
  markets. 39d adds a separate targets record without changing v4's sample.
  A future served probability needs a separately reviewed version/sample;
  never pool it with today's null-probability rows.
- **Display.** The gap is gray and never a pick until Rec Targets' own 27j
  slice reads `adopt`.
- **Why Rec Targets first** (2026-10-18 read-only count): about 150 standard
  player-games a week, all standard lines, and targets already feed the
  receiving usage adjustment. The other line-only markets have about 32
  distinct player-games a week, mostly goblin and demon rungs.
- **Load-bearing (39c):** adding a market to `NflPropMarket` widens the
  modelled universe, not every model's readers. The dedicated targets
  loader and assembler serve the new rows; explicit v4 filters keep targets
  out of legacy projections, replay, 27a and v4's 27j report. Targets has
  its own 39d loaders and report identity.

**What 39a found** (`python -m app.backtest.nfl_targets_projections --season 2024`,
run once on 2024 REG weeks 1-18; archive `blueprint/history/features/39a-nfl-targets-baseline.md`):

| Candidate vs incumbent | n | MAE change | Paired diff +/- SE | Verdict |
|---|---:|---:|---:|---|
| moneyline vs reference | 3,355 | +1.28% | +0.022 +/- 0.005 | reject |
| recent_form vs reference | 3,355 | -0.40% | -0.007 +/- 0.006 | reject |

- Reference MAE 1.698 pooled (RB 1.267, TE 1.701, WR 1.974), bias -0.165;
  descriptive only.
- **Coverage:** 5,200 completed RB/WR/TE player-games, 3,355 scored; 511 had
  no baseline and 1,334 a thin one. No 2023 stats are stored, so 2024 weeks
  1-4 score nothing and week 5 is the first scored week. Not backfilled.
- **2025 holdout reads by 39a: 0.** Selection on 2024 is a development
  choice, not validation.

**What 39a fixed as load-bearing:**
- **`nfl-targets-v1` is fixed** (`app/core/nfl_targets_projection.py`):
  `round(B, 2)`, where `B` is the mean of valid (finite, nonnegative) target
  counts in the season `choose_baseline_season` picks from per-season valid
  counts; RB, WR and TE; completed REG history strictly before the target
  week; at least `MIN_BASELINE_GAMES = 4` valid counts in that season, else a
  null projection. No moneyline, recent-form, DVP or usage adjustment
  (`SELECTED_MONEYLINE_SCALING` and `SELECTED_RECENT_FORM` are `False`,
  pinned by a test). Any change needs a new version and probability fit.
- **One call:** `project_targets(input)` with its defaults. 39b fits P(over)
  on exactly this projection and eligibility; 39c serves the same call.
- **Separate from v4:** a dedicated loader (`app/repositories/nfl_targets.py`)
  and harness (`app/core/nfl_targets_backtest.py`), never `_slate_line` or
  the 27b replay markets. 39c adds live inputs and a dedicated serving
  assembler without importing the replay harness into production.
- **The CLI accepts 2024 only** and rejects any other season before it
  imports the database module.

**What 39b found** (`python -m app.backtest.nfl_targets_over_probability_fit --write`,
run once on 2026-10-18; archive `blueprint/history/features/39b-nfl-targets-over-probability.md`):

| Cases | Pairs | ECE | Worst bin | Brier vs normal | Verdict |
|---:|---:|---:|---:|---|---|
| 4,624 | 16,822 | 0.043 | 0.078 | 0.2022 vs 0.2033 | hide (ECE, worst bin) |

- **Miscalibrated, not short of data:** it beats the normal on Brier, but ECE
  is more than twice the 0.02 limit.
- **The 2024 shape did not carry to 2025.** At the line nearest the
  projection it predicts 0.434 over against 0.406 observed (normal 0.488);
  every position overstates the over by 2.5 to 3.5 points. No position and no
  projection tercile passes alone (information only).
- **Small counts break ratio scaling,** as for 27g's receptions and 20g1's
  blocks: low predictions (0.05, 0.17) went over 28% and 25%.
- **Coverage:** the 2024 fit used 3,244 cases (39a's 3,355 less 111 that
  project exactly 0 targets); 2025 scored 4,624 of 5,373 driver rows.
- **2025 holdout reads by 39b: 1** (the eighth overall). A different method is
  a new item, developed on 2024 first.

**What 39b fixed as load-bearing:**
- **`NFL_TARGETS_OVER_PROBABILITY_VERSION = "nfl-targets-pover-v1"`**
  (`app/core/nfl_targets_over_probability.py`), separate from `nfl-pover-v1`;
  the rule's constants (300 cases, ECE 0.02, bin gap 0.05, 200-pair bins) are
  Rec Targets' own.
- **The generated fit** (`app/core/nfl_targets_over_probability_fit.py`):
  `FIT_SEASON = 2024`, `SCORED_SEASON = 2025`,
  `FIT_PROJECTION_MODEL_VERSION = "nfl-targets-v1"`, `SHOWN = False`, and an
  empty `QUANTILES_BY_POSITION` (keyed RB, WR, TE when shown). 39c reads
  P(over) only while `SHOWN` is true and the fit's projection version matches
  `NFL_TARGETS_MODEL_VERSION`; today that means null, never 0.5.
- **Consequence for 39c and 39d:** frozen Rec Targets rows carry a projection
  and no P(over), so 27i's rule can make no Rec Targets pick and its 27j
  probability-pick slices remain `insufficient` with zero picks until a
  separately validated probability exists. Coverage and settled calls can
  accrue independently.
- **The fit CLI has no season option** and fits 2024 before it loads any 2025
  row; re-running it would read 2025 again.

**What 39c fixed as load-bearing** (completed 2026-10-19):

- **Eligibility:** linked RB/WR/TE, REG weeks 1-18, full-game standard
  lines only. History is completed REG games strictly before the target
  week; count finite, nonnegative targets, including valid zeros. At least
  four valid counts in the chosen baseline season; otherwise projection
  and gap are null. Live line selection has a strict pre-kickoff cutoff.
- **One serving call:** `services/nfl/targets.py` uses `project_targets`
  defaults and the hidden-fit guard. No DVP, usage, moneyline, wind or
  recent-form adjustment is applied. Inapplicable evidence is null.
- **Mixed-model freezing:** each slate row supplies its own model version.
  Targets carry null `p_over`, `p_under` and `over_probability_version`.
  The existing insert-only key handles a null probability version with
  `NULLS NOT DISTINCT`. Unknown-start and started games are not frozen;
  historical rows are never backfilled.
- **Display:** slate, Props board, game and player flows show discoverable,
  unranked Rec Targets reference rows and truthful evidence. The gap stays
  gray; no OVER/UNDER recommendation or duplicate line-only targets row.
- **Version boundaries:** ten modelled markets, nine explicit v4 markets,
  eight line-only markets. 39d settles targets using the `targets` stat
  under its own identity and preserves existing v4 sample selection.
- **Recorded proof:** 625 web tests, production build and 2,888 API tests
  passed. A fixed-input comparison preserved all 9,317 v4 rows after adding
  132 targets rows; the read-only freeze preview included seven targets.
  The approved Week 6 stored-slate refresh was read back and verified on
  normal localhost pages. Code is merged and pushed; hosted rollout and
  actual targets frozen-row inserts were not verified by this refresh.

**What 39d fixed as load-bearing** (completed 2026-10-19;
archive `blueprint/history/features/39d-nfl-targets-forward-check.md`):

- **Separate reports:** `GET /nfl/model/ranking?season=<year>` defaults to
  `opponent-dvp-tg-blend-usage-snap-v4`; explicit `model_version` accepts
  that version or `nfl-targets-v1`. No API `all` selector or arbitrary model
  discovery. Targets reports JSON null for `overProbabilityVersion`.
- **Targets selection:** dedicated NFL-scoped readers select linked RB/WR/TE,
  completed REG weeks 1-18, full-game standard `receiving_targets` lines and
  `nfl-targets-v1` with a null probability version before latest-row selection.
  Both line fetch and prediction generation precede known kickoff strictly.
  Settle the frozen line against observed `targets`, never receptions or
  today's projection. Unknown/invalid stats are explicit exclusions; valid
  zero targets remain zero. Reuse the finished-week stats-loaded guard.
- **Coverage is independent of picks:** count eligible provider props and
  whether each has any eligible frozen prediction of the same identity;
  a newer unfrozen line does not erase an older frozen call. Settled calls
  can accrue without P(over); `withPOver`, picks and bets remain zero.
- **Consumer parity:** API and CLI share report construction. The CLI defaults
  to v4; `--model-version all` prints v4 then targets as separate records,
  and the weekly `nfl-ingest.yml` Summary uses that selector after stats load.
  `/nfl/model` has independent V4 and Rec Targets sections and query states;
  targets shows two neutral standard slices and explains `Not accruing`.
  The API retains four canonical slices. No combined sample or adoption count.
- **Isolation and cost:** API cache keys include season/model/probability
  version, web query keys include season/model, and failures stay isolated.
  Retain the 15-minute single-flight cache and batched repository reads;
  no slate replay or per-player query. Fixed-input v4 and NBA records matched
  their pre-change values. The recorded additional targets load took 0.413 s
  with zero frozen targets rows; this is local current-volume evidence, not
  production memory or future-volume proof.
- **Recorded evidence:** 630 web tests, production build and 3,005 API tests
  passed, with API/CLI/browser and read-only PostgreSQL checks. The 2026
  sample had zero frozen targets rows and 284 eligible props across weeks
  4-6. Populated settlement and failure paths used labelled fixtures; no rows
  were inserted to manufacture a sample. Existing browser console warnings
  were recorded, so this is not a clean-console claim. Code is merged and
  pushed; current hosted rollout and frozen-row population were not checked
  by this overview. No holdout was rerun.

**Shipped: public read-only demo (item 37, added 2026-10-15, complete 2026-10-16)**

A hosted portfolio demo: anonymous visitors browse every sport page, only the
owner reaches the admin surface, and the code is public. The 2026-10-15 fixes
prepared it (secrets removed from tracked files, API hardening, Live Odds and
My Bets removed, slate caching); item 37 finishes it, in this order:

37a. **Admin-only login** *(shipped 2026-10-15)* - the owner signs in on the Admin page with `ADMIN_API_KEY` itself; the web keeps it per tab and sends it only to `/admin` routes; visitors see no Admin nav entry. No sign-up, no other accounts, no per-user data.
37b. **How it works page** *(shipped 2026-10-15)* - public `/how-it-works`, linked from the nav for everyone: what the app is, how data flows, one card per sport (model today, shown as a pick, reference only, status, with slate and track record links), and how a model earns a pick, with a color legend. Static text, no live numbers.
37c. **CI and secret scanning** *(shipped 2026-10-15)* - one Verify command (`npm --prefix web run verify && cd api && python -m pytest`) run locally and by `.github/workflows/verify.yml` on pull requests and pushes to `master`, beside a pinned gitleaks scan of the tracked tree and the commits each event adds. A failing check does not block a push; GitHub push protection would, as an owner setting after 37e.
37d. **Deploy to Render** *(shipped 2026-10-16)* - `render.yaml` defines the API (`sportapp-api`, always-on `0.5c-512mb`, Virginia beside Neon, `--proxy-headers`) and the static web (`sportapp-web`, built with `VITE_API_BASE_URL`); ingest stays on GitHub Actions; the NFL slate and NFL line grading are precomputed into `report_snapshots`, so production never builds them; a live smoke test passed (production settings, CORS, admin sign-in, per-client rate limits, every page).
37e. **Public repo and README** *(shipped 2026-10-16)* - public `Dayshawn21/Sports-Baseline` from a one-commit snapshot (`2312f3a`), with a README (live links, screenshots, the validation findings, local setup); CI, the crons and both Render services moved to it, and the private `SportAppV2` is archived. It also took tennis prediction and best-picks CPU work off the event loop (a cold build had frozen the API for 5.2 s).

**What 37e fixed as load-bearing:**
- **The public repo `Dayshawn21/Sports-Baseline` is the working repo**
  (remote `origin`); Render, CI and every cron run from its `master`.
  Pre-37e history, and every pre-37e archive's commit hash, lives only in the
  archived private `SportAppV2` (remote `private`).
- **Workflows register only when a push changes their file;** GitHub pauses
  public-repo schedules after 60 days with no commit.
- **The interview guide is local and untracked;** never stage it.
- **The tennis prediction path is off the event loop:** single-row LightGBM
  predicts use `num_threads=1` under a lock; the history index build, the
  predict loop and the best-picks assembly run in worker threads. Output is
  byte-identical.
- **`sportapp-api` needs no provider keys** (`ODDS_API_KEY` left `render.yaml`).

**What 37d fixed as load-bearing:**
- **Service names `sportapp-api` and `sportapp-web`** and their URLs
  (`https://sportapp-api-ftsf.onrender.com`,
  `https://sportapp-web-7v3r.onrender.com`) feed `CORS_ORIGINS` and
  `VITE_API_BASE_URL`; 37e repoints both services to the public repo and
  keeps the names.
- **`VITE_API_BASE_URL`** (`resolveApiBaseUrl` in `web/src/utils/apiBase.ts`)
  is read at web build time; unset, the web uses `/api` through the Vite
  proxy. Changing it needs a web redeploy.
- **Production never builds a heavy report on request.** `report_snapshots`
  (`0045`, one payload per `(report, season)`) holds `nfl_line_grading`
  (`nfl_model_snapshot`, Tuesday) and `nfl_slate_week_<N>`
  (`nfl_slate_snapshot`, the last step of `nfl-prop-lines.yml`,
  `nfl-prop-odds.yml`, `nfl-weather.yml` and `nfl-ingest.yml`). A missing
  row is a 503 in production; dev builds live only when no row exists. **A
  new slate input's writer must refresh the slate snapshot too.** These
  refresh steps run once 37d is on `master`.
- **`build_slate` runs its CPU half in a worker thread** (`asyncio.to_thread`)
  so `/health` answers during a dev or CLI build; output is unchanged.
- **Error responses never carry a traceback or raw exception text.**
- **Migrations stay manual** against the shared Neon database; Render runs no
  migration or cron.
- **Accepted limit:** with `--forwarded-allow-ips '*'` a client can spoof
  `X-Forwarded-For` and dodge the in-memory rate limits.

**What 37c fixed as load-bearing:**
- **The `Verify` command** in `AGENTS.md` is the one gate local work,
  `/implement`, `/complete` and the workflow run; changing its checks means
  changing `AGENTS.md` and `verify.yml` together.
- **Workflow `Verify`, jobs `verify` and `secret-scan`:** a ruleset or 37d's
  deploy may require them by name.
- **No secret in CI:** the `verify` job uses a password-free dummy
  `DATABASE_URL` (`postgresql://localhost/ci`), since `Settings` needs one at
  import and no test connects. A test that needs a real database or key
  breaks CI.
- **`.gitleaks.toml`** is the one place scan exceptions live, one path each
  with a reason; today a saved TennisAbstract page (Cloudflare's public
  beacon token) and, since fix 2026-10-18 (`gitleaks-nba-digest-key`), the
  NBA digest test's `<gameId>-<playerId>-<market>` row key. That second one
  extends the default `generic-api-key` rule with an `AND` allowlist (path
  and value shape), because a top-level path allowlist skips the whole file
  and `targetRules` suppressed nothing in gitleaks 8.28.0.
- **History is not scanned:** the public repo starts from 37e's clean
  snapshot; the archived private repo's history still holds the
  rotated-out credentials.

**What 37b fixed as load-bearing:**
- **Route `/how-it-works`** is public and stable; 37e's README links to it.
- **`SPORT_STATUS`** (`web/src/pages/howItWorksContent.ts`, typed
  `Record<SportCode, SportStatus>` over the `SPORTS` registry, so a sport
  without an entry fails `tsc`) is the one place the page states what each
  sport serves. **An item that changes a sport's picks (25c, 27h, an NBA
  adoption item, tennis moneylines back on) updates its entry in the same
  diff.**
- **No weekly-changing numbers** on the page; it links to the model pages for
  those. The only green and red are the legend's swatches.

**What 37a fixed as load-bearing:**
- **`GET /admin/session`** (behind the admin router's key guard) returns 200
  `{"keyRequired": bool}` when the caller may use admin routes, 401 when not,
  and 429 past the heavy limit (10 a minute per client; it is in
  `HEAVY_PATHS`). 37d's smoke test and later admin features check sign-in
  through it.
- **The credential is `ADMIN_API_KEY` itself,** not a password or cookie
  session: one owner, and no session secret, CSRF or cross-site cookie rules
  for 37d's separate origins.
- **The header rule:** the web sends `X-API-Key` only to `/admin` or `/admin/...`
  URLs (`adminKeyHeaders` in `web/src/utils/adminAuth.ts`), never to a public
  route or in a URL; an admin 401 clears the stored key.
- **Storage:** sessionStorage `sportapp.adminKey`; closing the tab signs out,
  and rotating the server key signs out on the next admin request. Sign in and
  sign out drop every cached `['admin', ...]` query.
- **Nav:** `visibleNavItems` shows Admin only when signed in, or in a Vite dev
  build; `navKeyForPath` still highlights `/admin`.
- **No server key (dev):** `keyRequired` is false and the page opens with no
  card; production cannot start without a key.

**Complete: Lineform structural redesign (item 38, completed 2026-10-18)**

The app is renamed Lineform and restructured so every sport shares one shape.
**Display only:** no page changes a probability, edge, rank, sort or pick, and
the palette, fonts, gray-signal rules and 11px floor are unchanged. The
structure was chosen in an Impeccable surface round: the direction contract is
`.impeccable/surfaces/web-src-pages-nflintelligencepage-tsx.md`, the chosen
sketch `.impeccable/mocks/decision/command.html`, and product context
`PRODUCT.md` at the repo root.

38a. **Lineform shell** *(shipped 2026-10-17)* - finish the rename from SportApp to Lineform in the UI and README; a top bar with logo, sport tabs and Slate / Props / Model / How it works on every page (replacing each page's own view switch); one shared page head (title, period, previous and next); per-route tab titles; phone menu.
38b. **Table-first NFL slate** *(shipped 2026-10-17)* - a plays digest of the week's largest gaps (gray, labeled reference) above one dense row per game grouped by kickoff window, each row opening the game page; two-line rows on phones.
38c. **Tennis and NBA slates on the same shape** *(shipped 2026-10-17)* - both sports now use the shared table-first slate shape.
38c1. **Tennis slate** *(shipped 2026-10-17)* - priced picks use the shared digest strip (green under the existing rule) above a match table whose rows expand inline with the best opportunity, model breakdown, serve and return, decision board, and match-page link; the side panel and pick cards are gone.
38c2. **NBA slate** *(shipped 2026-10-17)* - one row per game replaces the cards, under a gray digest of upcoming standard lines ranked by normalized gap, one per player. This is the one NBA surface allowed to sort a gap; game-page props remain unranked and unsorted.
38d. **Props as tables** *(complete)* - tennis/NFL prop boards and NFL/NBA game pages use dense rows and evidence drawers without changing ranks, edges, or colors.
38d1. **NFL props as rows** *(shipped 2026-10-17)* - the prop board and game-page Props use dense rows per market; the board's side panel is now the game page's evidence drawer, and gray line-only props are plain rows without a drawer. Shared row styles and mini bars are ready for tennis and NBA.
38d2. **Tennis prop board as rows** *(complete)* - one row per line with rank, player and match, line, model, hit probability against break-even, EV, tier, and trust; evidence is in a drawer and last-five bars stay there because they require a per-match request.
38d3. **NBA game-page props as rows** *(complete)* - gray modelled and line-only props are rows with a detail drawer, while staying unranked and unsorted under 20g2.
38e. **Command field** *(complete)* - a search in the top bar, focused with `/`, filters the current slate and jumps to a game, team or player from data already loaded; Enter opens the top match; a search button expands on phones.
38f. **Shape consistency pass** *(complete 2026-10-18)* - game, match and player pages use the shared page head, matching existing model heads; one `h1` per page, CT clocks, loaded detail tab titles, shared gray slate/prop panels and readable NBA phone rows. No backend or model changes.

**What 38a fixed as load-bearing:**
- **One top bar,** driven by `shellNav(pathname, adminVisible)` in
  `web/src/utils/sportNav.ts` (sport tabs, the active sport's view tabs,
  then How it works and Admin through `visibleNavItems`); the phone drawer
  reads `menuSections`. No page carries its own view switch:
  `SportViewSwitch`, `NAV_ITEMS` and `navKeyForPath` are deleted. 38e's
  command field sits in this bar.
- **Tab titles** have one writer, `DocumentTitleProvider` (38f). Loaded detail
  pages register names from their existing query; unavailable states use
  `documentTitle(pathname)`. Route and owner checks prevent stale detail titles.
- **`PageHead`** (`web/src/components/shared/PageHead.tsx`) is the one page
  head: `title`, `meta` (a status line beside the title naming the period
  only, never counts the stats strip shows), `period` (previous and next
  paths), `actions`, `stats`. There is **no eyebrow and no subtitle**
  (decided at owner review, 2026-10-17); the head title is 34px. Every
  slate, prop board, model, game, match, player and How it works page uses it.
  New pages reuse it rather than writing their own heads.
- **Gutter:** the bar pads with the `is-wide` container's
  `clamp(20px, 3.2vw, 56px)` on desktop and 20px on phones, so the
  wordmark and page content share one left edge.

**What 38b fixed as load-bearing:**
- **One row model per game.** `nflSlateRow(game, notes, now)` in
  `web/src/utils/nflSlate.ts` (`NflSlateRowModel`, display strings keyed by
  `gameId`) feeds `NflSlateTable`; 38e's command field filters these rows.
  The NFL slate card (`NflSlateGameCard`, `nflSlateCard`, `topGameProps`,
  `slateBoards`) is deleted. Later slate tables preserve the row model and
  shared tags rather than restoring game cards.
- **The digest order is the board's.** `slateDigest(categories, limit = 4)`
  ranks a board built as of now (started games already dropped) by
  `compareBoardTiers`, then |edge share|, one line per player: the old card's
  top-props order widened to the week. Changing it is a ranking change.
  `NflSlateDigestItem` (`gameId`, `playerName`, `market`, `matchup`, `line`,
  `model`, `gap`) is the strip 38c reuses for tennis and NBA. Hidden when no
  upcoming line is rateable.
- **Columns:** Kickoff (Central weekday and clock, since Prime time spans
  Sunday and Monday), Game, Spread, Total, Moneyline, Model (muted, "not a
  pick"), Props (`groupNflPropRows`, so the column sums to the strip's prop
  lines), Notes. Every column has a fixed pixel width, so windows line up and
  wider screens spread spare room across all eight (Notes 220px, fix
  2026-10-17); at 1100px and below rows go to two lines, hiding the opened
  moves, the model total and conditions. A final shows "Final" in Kickoff
  only; its Game cell keeps the records.

- **Still load-bearing through the redesign:** the `.nfl-slate` gray-signal
  scope and board parity on game-page props (33a), `SPORT_STATUS` on How it
  works (37b), the `SPORTS` and `SPORT_PAGES` registries (17d), and
  `visibleNavItems` hiding Admin from visitors (37a).
- **Not part of the rename:** the Render service names `sportapp-api` and
  `sportapp-web`, their URLs and the public repo name, which feed
  `CORS_ORIGINS` and `VITE_API_BASE_URL` (37d).

**What the completed redesign preserves:**

- Tennis, NFL, and NBA slates now share the table-first shape while preserving
  each sport's existing signal rules: tennis priced picks may be green; NFL
  and NBA reference gaps stay gray.
- NBA digest sorting is a narrow slate-only exception. NBA game-page props
  remain unranked and unsorted.
- Tennis, NFL and NBA reuse shared prop-row styling; numeric values, ranking,
  edge and color rules are unchanged. Tennis last-five bars remain in the
  drawer; NBA props remain gray and unranked.
- The command field filters only the current slate and uses data already
  loaded. It adds no search endpoint or provider request.
- Times use `America/Chicago` with the display label `CT` through winter and
  summer. NBA's API date remains Eastern. New UI text stays at least 11px.
- Acceptance evidence is in `blueprint/reference/38f/acceptance.md`;
  completion archives are under `blueprint/history/features/38*.md`.

**Parked: tennis depth (item 16 stays open for 16f)**

16e. **Prop stat expansion** *(shipped 2026-09-27)* - 1st Set Total Games and 1st Set Total Games Won are projected by an exact first-set chain on the two holds (`app/core/tennis_first_set.py`), flagged `ungraded_stat`, capped at LEAN, and skipped by best picks until 26f grades them. Snapshots moved to `props-v2`. The chain runs about +0.35 games high on 2026 first sets (`python -m app.backtest.tennis_first_set_level`); nothing was fitted. 1st Set Aces stays unsupported.
16f. **Set-handicap projection** *(parked 2026-09-29)* - model tennis set-handicap lines only after provider line shapes are captured. They are not: `match_odds` holds 48 `set_handicap` rows (31 matches, 2026-08-24 to 09-25, all under the old `betonline.ag` name, none since the Bet365 rename), 29% of best-of-3 rows are +/-2.5 or +/-3.5 game lines the Bet365 parser misfiled, and 27 settled matches have a pre-start line. Revisit only if the provider starts offering set handicaps regularly.

**Shipped: tennis model validation (item 26, added 2026-09-25, complete 2026-10-01)**

Before item 26 the tennis ensemble had never been measured against the market
it has to beat: v6 LightGBM scored about 0.71 to 0.73 test AUC, and the blend
weights were hand-set. Item 26 graded the model before changing it, under the
same "backtest before adoption" rule as items 19j to 19n, 24 and 25.

26a. **Prediction grading and CLV** *(shipped)* - score each stored prediction's ELO, LightGBM, market, and ensemble probabilities against settled results (log loss, Brier, calibration, by tour), and measure whether the closing de-vigged moneyline moved toward the model; read-only report, no model change.
26b. **PrizePicks line settlement** *(shipped)* - measure how often props link to a match and a box score, then settle the score-derivable lines (total games, games won, sets, tie breaks, first-set games) against final scores and report over, under and push rates by stat and odds type; read-only, no schema change.
26c. **Historical closing-line backtest** *(shipped 2026-10-01; both candidates rejected against the close)* - `python -m app.backtest.tennis_closing_lines [--holdout]` reads Valuebetennis results with Pinnacle opening and closing odds (2021 onward) and scores computed ELO and the hand-set ELO-plus-market blend against the closing line. Pre-registered split: 2021 burn-in, 2022 development, 2023-2025 holdout, scored once. v6 is not scored: its training covers all stored history. tennis-data.co.uk, the original source, blocks downloads.
26d. **Market-anchored ensemble** *(shipped 2026-10-01; adopted for ATP+WTA and Challenger, served as `ensemble-v3`)* - a log-odds blend `logit(p) = a * logit(close) + b * logit(elo)` fitted on 2022 (`python -m app.backtest.tennis_market_blend_fit --write`, frozen in the generated `app/core/tennis_market_blend_fit.py`), scored once on the 26c holdout and once on 26a's live predictions (`python -m app.backtest.tennis_market_blend --holdout | --live`).
26e. **Box-score join key** *(shipped)* - store opponent and round on `player_match_stats` so aces, double-fault and break-point props join to exactly one box score, then settle those stats through 26b's report.
26f. **Prop projection snapshots** *(shipped; evidence accrues daily from 2026-09-25)* - store the projection, hit probability and confidence tier when a prop is fetched, so calibration by tier is graded forward on pre-match predictions only.

**Complete: WTA 125 blend group (item 40, verdict 2026-10-19: keep pooled)**

40a. **WTA 125 blend backtest** - tested the WTA coefficients and a 125-only fit against 26d's pooled Challenger blend. On 970 verified 2026 WTA 125 cases, both candidates failed G1 (beat the incumbent) and passed G2 (no worse than the close). Keep the pooled group.
40b. **Serve the WTA 125 group** - dropped under 40a's pre-registered rule, not implemented. No routing, serving coefficients, model version or `SPORT_STATUS` change.

- **Why it was tested:** livetennisapi files WTA 125 draws under `challenger`,
  so `matches.tour` is `CHALLENGER` and they take the Challenger
  coefficients (`a` 1.11, `b` +0.08); only `display_tour` labels them
  WTA 125. 26d's D4 fitted that group on Valuebetennis `Challenger`, both
  genders pooled. The WTA group leans away from ELO (`a` 1.46, `b` -0.42).
- **Population:** the women's Valuebetennis `Challenger` category also
  contains ITF events. A frozen tournament-and-season crosswalk verified
  against official WTA metadata identifies the WTA 125 subset; the category
  alone is insufficient.
- **Rules carried from 26c and 26d:** candidates were fitted on 2022 only;
  the comparison rule was fixed before scoring. G1 requires paired
  candidate-minus-incumbent log loss `mean + 2.5 * SE < 0`; G2 requires
  candidate-minus-close `mean - 2 * SE <= 0`. Both gates must pass.
- **Evidence boundary:** 2023-2025 was already read twice and was not fresh
  evidence. 40a scored its frozen 2026 sample once; it is now read evidence
  too. No further tuning or repeat verdict follows from this refresh.
- **Data:** the six downloaded Valuebetennis files remain gitignored under
  `api/data/valuebetennis/`. The recorded result and rule live in
  `blueprint/history/features/40a-wta125-blend-backtest.md`.

**TennisMyLife match data (item 41: 41a and 41b locally complete, 41c conditional)**

TennisMyLife (`stats.tennismylife.org`) publishes free match CSVs, MIT
licensed and updated daily, in the Sackmann column shape: tournament, date,
round, score, both players' rank, hand and age, and per-player aces, double
faults, serve points, first serves in and won, second serves won, service
games, and break points saved and faced. Files cover ATP (per year plus
`ongoing_tourneys.csv`), Challenger, ATP qualifying and WTA tour. There is no
WTA 125, ITF or odds data, and the site flags its WTA files as less reliable.

41a. **Box-score ingest, locally complete** - seven yearly/ongoing CSV files for ATP, Challenger, ATP qualifying and WTA, one batched name index and idempotent upserts under source `tennismylife`. Match recent form, player match logs and player past-prop displays opt in; TennisAbstract stats take precedence. Grading readers remain TennisAbstract-only by default; no projection, rolling-stat or model change. The configured 11:00 UTC daily job and manual dispatch await post-push runner verification.
41b. **In-house ELO, locally complete (2026-10-21)** - overall and surface ELO replayed from TennisMyLife results (2021 onward, full opponent network) with 26c's constants, stored as source `tennismylife-elo-v1` in a separate `tennis_elo_snapshots` table (`0046`), never in `player_elo`; immutable pre-match comparison pairs in `tennis_elo_comparisons` (`0047`). A non-inferiority rule (log-loss margin 0.005) was pre-registered before any forward case. Shadow activated 2026-10-21; first eligible UTC day 2026-10-22; all report groups accruing with zero observations. No serving change. The first real freeze and GitHub runner acceptance are post-completion checks in the archive (`blueprint/history/features/41b-tennis-inhouse-elo.md`). Commands are in `AGENTS.md` (`app.ingest.tennis_elo`, `app.ingest.tennis_elo_comparison`, `app.backtest.tennis_elo`).
41c. **Serve in-house ELO** - conditional on 41b passing: the ensemble reads the in-house ELO under a new model version, and the local `Lineform ingest_daily` ELO step is retired; dropped if 41b fails.

- **41a completion evidence (2026-10-20):** the owner-approved 2026 backfill
  stored 22,789 rows; the repeat added no rows. All 70,587 TennisAbstract rows
  retained the same stored facts, and both grading CLIs were byte-for-byte
  identical immediately before and after. A local browser check showed six
  aces and three double faults for Svitolina versus Noskova on the player log
  and match recent form. Verify passed (632 web tests, build, 3,109 API tests).
  A recent comparable WTA sample had zero disagreements in aces, DFs and
  shared break-point counts across 514 player-matches; this is source agreement,
  not model validation. Archive: `blueprint/history/features/41a-tennismylife-box-score-ingest.md`.
  Code deployment and GitHub runner acceptance remain unverified.
- **Why:** TennisAbstract's ELO page is blocked from GitHub's runners
  (Cloudflare), which is why ELO runs on the owner's PC. Its player match
  pages still work from Actions, so for box scores the gain is coverage, not
  a fix. The 26d blend was fitted on ELO computed from match history, while
  serving reads TennisAbstract's ELO.
- **Read-only probe (2026-10-20, before the item was added):** TennisMyLife
  rows paired with 4,015 stored `player_match_stats` rows since 2026-09-01
  (ATP 763, Challenger 2,358, WTA 894). Where both had stats, aces, double
  faults and break points agreed on all but one row of 3,452, and service
  games on all but four. TennisMyLife had stats for 558 stored rows that
  have none and 5 the other way, and held 443 player-matches for tracked
  players that are not stored at all. The files had that day's matches. The
  host is plain nginx, not Cloudflare; a GitHub runner download was not
  tested.
- **Constraints carried into the specs:**
  - TennisAbstract stays the source for WTA 125 box scores and for
    `player_rolling_stats`. Moving rolling stats or prop projections to
    TennisMyLife would change `PROJECTION_VERSION` and is not in item 41.
  - `player_match_stats` is unique per (`player_id`, `source`,
    `source_match_key`), so the same match from two sources would be two
    rows. Readers must still get one row per match, and
    `join_box_score`'s exactly-one rule must not become ambiguous.
  - Any ELO serving change takes a new model version and a check
    pre-registered before scoring. The 2023-2025 tennis holdout is already
    read twice, and 2026 since 40a, so neither is fresh evidence.

**What 26a and 26b found** (archived under `blueprint/history/features/`):

- **26a:** the de-vigged market beat every component on log loss, within about
  one standard error for the ensemble. v6 was the weakest ATP and WTA component.
  58% of moved prices moved toward the ensemble, by a mean of only +0.36
  points.
- **26b:** standard PrizePicks lines settle close to a coin flip. Total games
  overs hit 48.7% +/- 1.6%, and games won 48.6% +/- 1.8%. ATP leans under by
  about two standard errors; WTA does not. At the app's assumed payouts, blind
  goblin and demon overs lose in every stat.
- **Neither result changed the model.** Adoption waited on 26c and 26d.

**What 26c and 26d found** (holdout 2023-2025, 12,068 ATP+WTA matches):

| Forecast | Paired log loss vs the Pinnacle close, ATP+WTA | Verdict |
|---|---|---|
| Computed ELO | +0.0636 +/- 0.0031 | rejected (26c) |
| Hand-set blend (`ensemble-v2`) | +0.0060 +/- 0.0008 | rejected (26c) |
| Fitted blend (`ensemble-v3`) | +0.0002 +/- 0.0004; -0.0058 +/- 0.0012 vs the hand-set blend | adopted (26d) |

- **The fitted blend is the close, slightly extremized.** Coefficients: ATP
  `a` 1.14, `b` -0.08; WTA `a` 1.46, `b` -0.42 (lean away from ELO); Challenger
  `a` 1.11, `b` +0.08. No group gives ELO a meaningful positive weight.
- **It is a better forecast, not a market-beater.** Betting its 3+ point gaps
  at the close lost 0.5% on 1,824 WTA picks and 2.2% on 7,504 Challenger
  picks; ATP never moves 3 points. Hand-set blend gaps lost 7.1% on 5,214.
- **The close moved toward computed ELO on 53.6%** of matches, by +0.46 points
  on average, close to 26a's live 58% / +0.36.
- **The 2023-2025 holdout has now been read twice** (26c, 26d). A later tennis
  refit must not reuse it as a fresh verdict.

**Why the prop items are split.** The props page computes projections, hit
probabilities and confidence tiers on page load, from `player_rolling_stats`
that are overwritten in place. They were never stored, so a past tier cannot be
graded without leaking the result. 26f stores them so grading can run forward
from the day it ships.

**Tennis model today** (`ensemble-v3+lgbm-v6` since 2026-10-01, after 26d and
the 2026-09-25 review fixes, archived under `blueprint/history/`):

- **Ensemble.** With a market price, `blend()` serves the 26d fitted blend for
  ATP, WTA and Challenger (`market_anchored_prob` with `FIT_COEFFICIENTS[group]`).
  A missing or gated ELO (`elo_is_unreliable`) gives the market alone. v6 gets
  no weight. Stale and overround flags are still raised but no longer move the
  probability. With no market price, the frozen hand-set path
  (`hand_set_blend`, `ensemble-v2`) runs; never retune it in place, since 26c's
  numbers replay through it.
- **`ensemble_weights`** on `ensemble-v3` rows holds coefficients
  (`{"market": a, "elo": b}`, or `{"market": 1.0}`), not shares; readers branch
  on `model_version`, and the match page labels the column "coef".
- **Moneyline best picks are off** (`MONEYLINE_PICKS_ENABLED = False` in
  `app/services/tennis/best_picks.py`, fix 2026-10-01), because 26d's holdout
  showed its gaps lose. The match page's moneyline EV tile reads "-" and is
  never green. Derived, serve-edge and prop picks are unchanged;
  `generate_ml_pick` stays pure and tested for a later re-enable.
- **Model page versions.** `GET /tennis/model/predictions` takes an optional
  `model_version` (default: the served one; unknown is a 404) and returns
  `versions` with settled counts; the page shows a version switch and never
  auto-switches to a retired model.
- **Model routing.** v6 LightGBM is computed for ATP and WTA only. Challenger
  and WTA 125 matches get no ML probability (`ml_not_trained_for_tour`).
  WTA 125 is stored as `CHALLENGER` and takes the Challenger blend group
  (40a tested alternatives and kept that group; 40b was dropped).
- **Future training policy** (completed F-08 repair, 2026-10-19; archive
  `blueprint/history/fixes/tennis-calibration-test-isolation.md`): future v7
  bundles always retain sigmoid calibration fitted on validation predictions.
  Final test outcomes affect descriptive reports only; fit/report failure
  aborts before bundle writes. Metadata records the fixed policy and fitting
  partition. Synthetic tests reverse final test labels/loss rankings without
  changing the model or calibrator. The live registry still supports only
  v6/v5/v4; current artifacts, ensemble weights and 26c/26d decisions are
  unchanged. No real retraining or holdout scoring occurred. Any future
  candidate adoption requires separately specified forward validation.
- **Missing inputs.** Unknown rank, age and ELO reach the model as NaN, as in
  training.
- **Confidence.** Missing-input quality flags lower a pick's tier one step
  (`_DOWNGRADE_FLAGS` in `app/core/bettable_criteria.py`); `elo_unreliable`
  hides it. ML flags (`ml_missing`, `ml_not_trained_for_tour`) no longer
  downgrade, because `ensemble-v3` gives v6 no weight (fix
  `tennis-ml-tier-flags`); a test fails if either list names a flag no tennis
  code emits. The moneyline pick and, since fix `tennis-market-pick-flags`,
  the priced Total Games and Game Spread picks receive the prediction's
  flags. Unpriced derived and serve-edge picks do not (finding F-09).
- **Moneyline source.** The newest odds run wins; ties break DraftKings, then
  Bet365 (formerly stored as `betonline.ag`), then Betfair. Spread and total
  picks use each book's newest line only.
- **Match totals.** Parsed from the market's main two-sided line; Bet365's is now
  stored.
- **Set picks.** Best-of-3 set outcomes (3 sets, 2-0) use a curve fitted to
  settled matches (`app/core/tennis_sets.py`). The total-games set weight stays on
  `2p(1-p)` until clean totals settle; use only `total_games` rows fetched on or
  after 2026-09-25 18:17 UTC.
- **Live lookup.** The best-picks live moneyline lookup is shared for 15 minutes,
  to stay inside the 100-requests-an-hour Odds-API.io plan.

**Grading data already stored:**
- 1,593 predicted matches settled with a winner, 1,217 of them with a pre-start
  moneyline.
- `predictions` keeps `p1_elo_prob`, `p1_ml_prob`, `p1_market_prob`,
  `p1_ensemble_prob` and `feature_snapshot`.
- PrizePicks: 201,886 snapshots from 2026-03-11, one ingest run a day.
  - 28.6% link to a match; linking was poor before late August.
  - 2,858 linked player-matches are settled.
  - Only lines fetched before `start_utc` are gradeable. PrizePicks flags some
    of those as already live, because stored start times can run hours late.
- `match_odds` is append-only, so the closing price is the last row before
  `start_utc`.

**Next: sports expansion** (item 17 complete 2026-10-05, item 20 complete 2026-10-07; NHL next, then WNBA)

17. **Multi-sport foundation** *(complete 2026-10-05)* - converged the tennis and NFL stacks, rather than clearing a path for the first one. Split 2026-10-01:
    - 17a. **Shared team-sport tables** *(shipped 2026-10-02)* - the seven cross-sport NFL tables renamed in place to sport-keyed `sport_*` tables plus a `sports` registry (`0039`), with `nfl_*` compatibility views so NFL code ran unchanged.
    - 17b. **NFL on the shared tables** *(shipped 2026-10-02)* - all NFL SQL moved to `sport_*` with a `sport = 'nfl'` filter on every reference, unique keys scoped by sport (`0040`), the views dropped (`0041`). Every NFL report and response was proved identical before and after.
    - 17c. **Sport-agnostic prop pipeline** *(shipped 2026-10-02)* - PrizePicks league selection, line storage and relink, frozen predictions, 27i's ranking rule, 27j's check and the ranking loader now take a sport. A sport plugs in through one `SportPropConfig` and one `SportPropSource`; NFL's is `NflPropSource`, whose period is the week. Every NFL report, response and stored row was proved identical to master, and a toy sport runs the whole pipeline without loading any NFL module. 27a line grading stays NFL-only.
    - 17d. **Sport-aware web shell and prop registry** *(shipped 2026-10-05)* - `SPORTS` in `web/src/utils/sportNav.ts` drives the nav, the Slate / Props / Model switch and the nav highlight; `SPORT_PAGES` in `web/src/routes/sportPages.tsx` drives the sport routes, and `tsc` fails if a sport lacks a slate, props, or a model page its registry entry promises. `prop_source(code)` in `app/services/sport_registry.py` maps a sport code to its `SportPropSource`. No schema change and every URL unchanged; NFL CLI output was proved identical. `bets.sport` was dropped 2026-10-05 because bets are tracked in Pikkit (open question 42). Tennis `matches` convergence stays out of item 17 (revisit with item 22).

    **Load-bearing for item 20:** a new sport adds one `SPORTS` entry, one `SPORT_PAGES` entry and one `PROP_SOURCES` entry. The shared prop modules must never import `sport_registry`, which imports NFL code.
20. **NBA support** *(complete 2026-10-07)* - reuses NFL team-sport patterns, through item 17. Split 2026-10-05:
    - 20a. **NBA data sourcing** *(shipped 2026-10-05)* - pick free schedule, box-score and injury sources, probe PrizePicks' NBA league and The Odds API `basketball_nba` cost, define NBA's prop period, and decide the team tables; documented before any ingest.
    - 20b. **NBA schedule and box-score ingest** *(shipped 2026-10-06)* - seed `nba` in `sports`; teams, players and games into `sport_*`; per-game player box scores in an NBA stat table; 2025-26 backfill plus a daily refresh.
    - 20c. **NBA prop lines** *(shipped 2026-10-06)* - PrizePicks NBA lines through the shared 17c pipeline, stored and linked, every market line-only until a projection exists. `python -m app.ingest.prizepicks_nba [--dry-run] [--relink]`, snapshotted by `nba-prop-lines.yml`. First run: 194 opening-night lines, all linked to a player and a game.
    - 20d. **NBA game odds** *(shipped 2026-10-06)* - moneyline, spread and total from The Odds API into `sport_game_odds`, de-vigged, under the shared free-plan credit budget. `python -m app.ingest.nba_odds [--days-ahead 2] [--min-credits 100] [--dry-run]`, twice daily by `nba-odds.yml`. First run: 260 rows for the 16 games through 2026-10-22, 7 books, every game with all three markets from at least one book.
    - 20e. **NBA slate and game page** *(complete 2026-10-06)* - NBA entries in the web sport registries; a game-first slate and game page with the market and line-only prop cards; no projection, edge or signal color. Split in three:
      - 20e1. **NBA game API** *(shipped 2026-10-06)* - an `/nba` router: `GET /nba/slate?date=` (one Eastern date's games, scores, records, latest market, line movement, prop line counts), `GET /nba/games/{id}` (the slate's game plus spread and total line history) and `GET /nba/games/{id}/line-only-props` (each linked line with the player's last 5 played games).
      - 20e2. **NBA slate page** *(shipped 2026-10-06)* - NBA in the web registries with a Slate view only; `/nba` is a one-day, game-first slate of cards with previous and next date buttons and `?date=`.
      - 20e3. **NBA game page** *(shipped 2026-10-06)* - `/nba/game/:gameId`: hero (teams, records, tip time, final score), the market block with no model row (closing lines once final), pre-tip spread and total movement, and gray line-only prop cards; slate cards link to it.
    - 20f. **NBA projection backtest harness** *(shipped 2026-10-06)* - `python -m app.backtest.nba_projections [--season 2025] [--arms reference,last_10]` replays a season game by game from box scores dated before each game, scoring nine prop markets (double-double excluded) against a fixed `reference` arm under a pre-registered adoption rule. 2023-24 and 2024-25 box scores were backfilled for it.
    - 20g. **NBA projection and frozen predictions** *(complete 2026-10-07)* - a baseline projection passing 20f, frozen pre-tip predictions, the forward ranking check and a model page through the shared pipeline; edges stay gray until a slice verdict reads `adopt`. Split 2026-10-06:
      - 20g1. **NBA over-probability fit** *(shipped 2026-10-06; assists shown, eight markets hidden)* - P(over) per market from a distribution fitted on 2024-25 and checked once on the 2025-26 holdout under a pre-registered calibration rule; `python -m app.backtest.nba_over_probability_fit [--write]` and a frozen fit table.
      - 20g2. **NBA projection on the game page** *(shipped 2026-10-07)* - `NbaPropMarket` and a modelled-market filter; game-page Props show the reference projection, its gap to the line and P(over) for assists, all gray, from `GET /nba/games/{id}/props`. Item 38d3 changed the cards to rows and evidence drawers without changing these values.
      - 20g3. **Frozen NBA predictions** *(shipped 2026-10-07)* - `NbaPropSource` implements the full `SportPropSource` and joins `PROP_SOURCES`; `nba-prop-lines.yml` freezes predictions after each snapshot. First run: 190 opening-night lines (2026 week 1) frozen, all projected, 20 assists lines with P(over).
      - 20g4. **NBA ranking check and model page** *(shipped 2026-10-07)* - `python -m app.backtest.nba_ranking_check [--season N]`, also on the daily `nba-ingest.yml` Summary page, grades NBA's frozen rows under 27i's rule unchanged; `/nba/model` shows slice progress and verdicts, gray until decided. First read: season 2026, every slice accruing at 0 of 200 picks; picks can come only from assists, the one market with a P(over).

    **NBA data (20a, decided 2026-10-05; `project-plan.md` §4):**
    - **ESPN ids throughout.** hoopR's ESPN release files (free GitHub release assets, the NFLverse shape) for schedules and per-game player box scores; the ESPN site API is the fallback on the same ids.
    - **Shared tables.** Games, players and teams in `sport_*` with `sport = 'nba'`; box scores in a new `nba_player_game_stats`. `season` is the start year (2025 = 2025-26).
    - **Period.** The regular-season week (Monday to Sunday, Eastern date, week 1 holds opening night), stored in `sport_games.week`, so the shared ranking rule's four-period minimum means four weeks, as for NFL.
    - **No NBA team-rating tables** are planned (resolves open question 11).
    - **Injuries.** ESPN's feed for display; the official NBA injury report if a later item tests availability in a model, because its archive is backtestable.

    **What 20c fixed as load-bearing:**
    - **Full game only.** `NBA_PROPS` (`app/nba/markets.py`) boards the `NBA` league alone. Halves, quarters and season lines are recognized but never stored (no stored data settles them); `NBAP` (preseason), `NBA4Q`, `NBASL` and `NBA SERIES` map to no segment.
    - **Ten line-only markets** (`NbaLineOnlyMarket`, stored strings never renamed): `points`, `rebounds`, `assists`, `threes_made`, `blocks`, `points_rebounds_assists`, `points_rebounds`, `points_assists`, `rebounds_assists`, `double_double`. Only stat names seen on a board are mapped; others log as unsupported until a `/fix` maps them. Fantasy Score needs PrizePicks' NBA formula confirmed first.
    - **One settlement rule:** `line_only_value` in `app/core/nba_line_only.py` (double-double: 10+ in two of points, rebounds, assists, steals, blocks). A DNP or missing stat gives None, never 0.
    - **Market scope:** 20c initially stored every market line-only; 20g2 added `NbaPropMarket`. Any reader that projects, grades or freezes NBA lines must apply `NBA_MODELLED_MARKET_FILTER`, as NFL readers apply `MODELLED_MARKET_FILTER`. Line-only markets stay out of those paths.
    - **Linking** (`app/core/nba_resolution.py`): NFL's `resolve_player` and `find_game_id`, reused unchanged, after accent folding (`Egor Dëmin` to `Egor Demin`) and PrizePicks-to-ESPN team codes (`espn_team_code`: `NYK` `NY`, `SAS` `SA`, `GSW` `GS`, `NOP` `NO`, `UTA` `UTAH`, `WAS` `WSH`). **Position is never passed:** PrizePicks sends `F-C` or `G-F`, ESPN stores `G`, `F`, `C`, and a mismatch would read as a different player. NBA aliases are keyed from the folded name.
    - **`PropLineSource`** (`config`, `load_resolver`) is what storing lines needs; `SportPropSource` extends it for freezing and grading. NBA's `NbaPropSource` implemented only the first until 20g3, which made it a full `SportPropSource` in `PROP_SOURCES`.

    **What 20d fixed as load-bearing:**
    - **Rows.** `sport_game_odds` with `sport = 'nba'`, the NFL shape: sides `home`/`away` (moneyline, spread) and `over`/`under` (total), `line` in book sign (negative home spread = home favored), `book` as The Odds API's lowercase key, append-only. 20e reads an NBA game's market from these rows.
    - **Matching** (`app/core/nba_odds.py`, pure): The Odds API full team names to ESPN codes (all 30, checked against the provider's event list), and an event matches one stored `REG`, `PIN` or `PST` game when both teams agree and tip-off is within 6 hours of `start_utc`; NBA `game_date` is the Eastern date, so dates are never compared. Ambiguous or unknown events are skipped and counted. Parsing and de-vigging reuse NFL's `parse_game_markets` unchanged.
    - **Credit floor.** A free `/sports` call reads the balance before the paid call; NBA spends only at 100 or more remaining (or not at all when no game is in the window), so it stops before NFL's anytime-TD floor of 50. Changing either floor means reviewing both. `--dry-run` still spends 3 credits.

    **What 20e fixed as load-bearing:**
    - **The `/nba` responses** (`app/schemas/nba.py`, camelCase): `NbaSlateResponse`, `NbaGameDetailResponse` (= a slate game plus `lineHistory`) and `NbaLineOnlyPropsResponse`. Slate and game share `assemble_games` (`app/services/nba/slate.py`), so a game page never disagrees with its slate card. Later game-level NBA display extends these or adds a sibling under `/nba/games/{id}/`, never another page (33a's rule).
    - **Market rule:** each market independently takes DraftKings' latest row, else the latest lowercase book, and names its book; win probability is the stored de-vigged `first_market_prob` (home). **Movement and history:** pre-tip rows only, one book per market (NFL's rule). Records count completed `REG` games only. `PRE` games are never served (404).
    - **One NBA game page.** The route `/nba/game/:gameId`; its hero and final block read the slate card model `nbaSlateCard` (`web/src/utils/nbaSlate.ts`). The card model itself is not load-bearing beyond the slate (33b's rule).
    - **Props is optional per sport.** `SportViewPaths.props` is optional and `SPORT_PAGES` requires a props page only when the registry promises one; 20g4 added NBA's Model view, and a later item would add its Props view (an NBA prop board, deferred at the 20g split), by adding paths and pages, nothing else.
    - **Shared with NFL:** the NBA pages reuse the `nfl-slate*` and `nfl-game*` classes under the `.nfl-slate` root (gray signal variables), shared prop-table styles since 38d3, `NflLineMovementChart` (prop narrowed to `homeTeam`, `awayTeam`, `startUtc`, `lineHistory`; optional `caveat`), and `lineOnlyBars`, `mainRung` and `overAgainstStandard` from `web/src/utils/nflLineOnly.ts`. The obsolete NBA prop-card stylesheet was deleted in 38d3.
    - **Times** are Central on the web; NBA "today" in the API is the Eastern date.
    - **Not yet known:** whether `nba_odds` stores rows after tip-off. If it does, a started game's "Latest stored price" may be in-play; closing lines and movement stay pre-tip.

    **What 20f fixed as load-bearing** (`app/core/nba_projection_backtest.py`):
    - **Seasons.** 2024-25 (`DEVELOPMENT_SEASON`) is replayed and fitted on freely; 2025-26 (`HOLDOUT_SEASON`) scores each candidate once, and every holdout read is counted in the item's archive (read 1: 20f's descriptive reference run). 2023-24 exists only for 2024-25's early windows.
    - **Inputs are pre-tip:** a player's played games (DNP excluded) in `REG`, `PIN` or `PST` games dated strictly before the game's Eastern date, crossing seasons, because box scores load the next morning.
    - **Eligible player-games** (shared by every arm): the player played, has 10 or more prior played games, and averaged 20 or more minutes over the last 10 (NULL minutes unknown, not zero).
    - **Markets:** the nine summed `NbaLineOnlyMarket` values, settled by `line_only_value`; double-double is excluded (binary).
    - **`reference`:** the mean of each market's settled value over the last 20 prior played games. 20g serves, per market, `reference` or a candidate adopted under the rule, never an unscored or rejected arm.
    - **The pre-registered rule** (2026-10-06): a candidate is adopted for a market only with 300 or more paired holdout cases, MAE at least 1.0% lower than the comparison arm, and the paired mean |error| difference below zero by more than 2 SE. Adopted candidates stack in build-plan order. NBA keeps its own constants; `market_metrics` and `paired` are NFL's, typed against a `ScoredCase` protocol.
    - **What it found:** `last_10` loses to `reference` in every development market. On the holdout the reference is nearly unbiased (|bias| <= 0.04) but runs above the median in every market (`share_below` 52.0% to 57.5%, blocks 68.1%), so over/under calls need a probability, not the mean (20g1).
    - **Backfill run order:** `sport_players.team_id` is last-write-wins and 20e's cards show it, so any older NBA backfill must be followed by `--season 2025` and then `python -m app.ingest.espn_nba_preseason`, checked against a `(id, name, position, team_id)` snapshot.

    **What 20g1 fixed as load-bearing:**
    - **Versions.** `NBA_PROJECTION_MODEL_VERSION = "nba-reference-v1"` (20f's reference arm on 20f's eligibility) and `NBA_OVER_PROBABILITY_VERSION = "nba-pover-v1"`. The generated fit is read only while its `FIT_PROJECTION_MODEL_VERSION` equals the projection version; any projection change hides P(over) until a new fit is scored (27g's rule).
    - **P(over)** is read with 27g's `over_probability(quantiles, projection, line)`: None for a whole-number line or a projection at or below zero, never 0.5. Only 20f-eligible player-games get a projection and P(over).
    - **The pre-registered display rule** (NBA's own constants, 27g's values): shown only with 300+ holdout cases, ECE <= 0.02, no bin of 200+ pairs off by more than 0.05, and Brier no worse than a normal.
    - **What it found:** assists shows (ECE 0.0196, Brier 0.2003 vs 0.2007). Rebounds, threes, points and blocks fail on a thin bin or ECE; the four combos lose to the normal on Brier. The fit captures the median gap (at the nearest line, predicted P(over) within 0.007 of observed in eight of nine markets). A count-aware method for the hidden markets is a new item, tried on 2024-25 first. **Holdout reads: 2** (20f's reference run, this fit), no projection verdict.

    **What 20g2 fixed as load-bearing:**
    - **`NbaPropMarket`** (nine modelled markets) and **`NbaLineOnlyMarket`** (`double_double`), disjoint, stored strings never renamed; moving a market into `NbaPropMarket` widens `NBA_MODELLED_MARKET_FILTER` automatically.
    - **`project_line`** in `app/core/nba_projection.py` is the one projection function: the page serves it, 20g3 freezes it. A test pins it to 20f's `reference` arm in every market (`REFERENCE_GAMES = 20`).
    - **History depth:** every stored played `REG`/`PIN`/`PST` game before the game's Eastern date, any season (20g1's holdout depth).
    - **`NbaPropsResponse`** (`GET /nba/games/{id}/props`, camelCase): `gameId`, `modelVersion`, and per line `projection`, `gamesInSample`, `priorMinutes`, `gap` (projection minus line), `pOver`, `pUnder`, `overProbabilityVersion`, `flags` (`few_prior_games`, `low_minutes`, `no_over_probability`, `integer_line`) and the last 5 played values. Null never means zero.
    - **No signal:** "gap", not "edge"; gap and P(over) are gray, never sorted by or compared to a payout until a later item adopts a slice that 20g4's check reads `adopt`.

    **What 20g3 fixed as load-bearing:**
    - **`prop_source("nba")` resolves** to `NbaPropSource` (`app/services/nba/prop_source.py`): `model_version` `nba-reference-v1`, `over_probability_version` `nba-pover-v1`, so `load_ranking_calls` and 20g4's check run on NBA unchanged.
    - **Period:** the regular-season `sport_games.week`; the current period is the week of the next `REG` game not yet tipped (`get_current_week`, no grace after tip-off, since freezing skips started games). Only the current week freezes, so Monday lines posted before Sunday's 22:15 UTC run freeze on Monday's 16:30 run. **Play-in and playoff lines are never frozen or graded** (`week` is NULL).
    - **Freeze what the page serves:** each linked full-game modelled line in the week at its latest pre-tip snapshot (`get_week_modelled_lines`, the page's line rule), projected by `project_line` from `get_prior_games` before its own game date (keyed by date, then player, because a player can play twice in a week). An ineligible line is frozen with a null projection and its flag; a test pins frozen rows to `/nba/games/{id}/props`.
    - **NBA frozen row** (`app/core/nba_prop_predictions.py`): `edge` always NULL; `quality_flags` are the projection's flags; `feature_snapshot` holds `games_in_sample`, `prior_minutes`, `gap`, `line`, `odds_type`, `market`, `segment` (`full_game`), `line_fetched_at`.
    - **Settlement** (`settle_frozen`, through `line_only_value`): a game with no box-score rows is `stats_not_loaded`; no row or a DNP row is `void_dnp`; a played row missing the stat is `missing_stat`; otherwise `over`, `under` or `push`.
    - **Finished week:** every `REG` game `completed`, `postponed` or `canceled`, and every completed one has box scores loaded (`get_finished_weeks`).
    - **One freeze CLI:** `python -m app.ingest.prop_predictions --sport nfl|nba [--dry-run]`, with `nfl_prop_predictions` (unchanged command and output) and `nba_prop_predictions` as thin entry points. It imports `sport_registry`, so it is an entry point, never a shared module.
    **What 20g4 fixed as load-bearing:**
    - **Shared ranking record.** `build_ranking_record(inputs, season, graded_at, model_version, over_probability_version)` in `app/services/prop_ranking.py`, the report text in `app/core/prop_ranking_report.py` and `PropRankingResponse` in `app/schemas/prop_ranking.py` serve both sports; they never import `sport_registry` or NFL code (17c's rule). NFL's CLI output and `/nfl/model/ranking` were proved identical after the move.
    - **`GET /nba/model/ranking?season=`** returns NFL's ranking shape (camelCase; slices, funnel, coverage, `finishedWeeks`, `lastSettledWeek`), cached 15 minutes per season; the default season is the one `get_current_week` finds, 404 when no `REG` game is loaded, 503 when grading fails. **A later NBA adoption item reads each slice's verdict here**, as 27h reads NFL's.
    - **The report's first line** is `<SPORT> forward ranking check, <season> (model <v>, P(over) <v>)`; NBA's coverage label reads "modelled full-game lines with a frozen row".
    - **`/nba/model`** reuses the NFL model page's ranking components and `nfl-model-*` classes. NBA's switch originally read Slate / Model; 42b adds Props.

42. **NBA prop board** - 42a-42d complete and locally verified;
injuries and team stats are display only. Hosted deployment is unverified. This is display work,
with no projection, probability, version, ranking or pick change.

  - **42a, board API:** `GET /nba/props?date=` returns one Eastern game
    date using the slate's default and adjacent-date rules. Each game's
    modelled `lines` are assembled by the game page's `props_response` and
    `lineOnlyLines` by `line_only_props`. Date-wide modelled and line-only
    reads replace per-game fetches for this endpoint; prior/recent player
    reads are combined. Repository filters for sport, served NBA game types,
    full-game segments, modelled markets and strict pre-tip snapshots remain
    load-bearing. Unit and local endpoint comparisons pin board/game parity.
    Archive: `blueprint/history/features/42a-nba-prop-board-api.md`.
  - **42b, board page:** `/nba/board` is NBA's Props view in both `SPORTS`
    and `SPORT_PAGES`. It requests the board once, groups each game's lines
    with existing NBA helpers, and mounts the selected market only. The URL
    carries optional `date` and `market`; absent/invalid market falls back
    to Points, and invalid dates defer to the API. Shared page head, adjacent
    dates, market pills, game links, CT tips/status, recent bars and both
    evidence-drawer kinds are implemented. Rows follow tip time then player
    name, with missing tips last and stable game/player ties; they never sort
    by gap or probability. Each game/player/market retains its alternate
    rungs. Line-only markets stay plain; null stays missing, never zero.
    Drawer selection resets across date/market navigation, reads current
    response data, and restores keyboard focus when closed. Local browser
    proof covered four board/game parity cases, all ten markets, navigation,
    error/empty states, and 1440/1000/390-pixel layouts. Final Verify passed
    659 web tests plus typecheck/build and 3,470 API tests. Archive:
    `blueprint/history/features/42b-nba-prop-board-page.md`; evidence:
    `blueprint/reference/42b/step4-check.md`.
  - **Operational boundary:** the October 21 response contained 8,097 raw
    lines (7,986 modelled, 111 line-only), 4,877,159 bytes and 1,383 grouped
    rows. Local pure assembly took 3.3-4.3 ms and did not repeat during
    market/drawer interactions. These are development observations, not
    production benchmarks. Hosted latency and Render's 512 MB memory remain
    unverified. Neither the page nor the API truncates the response.
  - **42c, locally complete:** timestamped ESPN injury snapshots in
    `nba_injury_snapshots` (migration 0048), with player tags/detail on board
    rows and evidence, both teams' lists on the game page, six-hour freshness
    and historical pre-tip selection. First snapshot and migration verified;
    hosted deployment and runner acceptance remain unverified. See
    `blueprint/history/features/42c-nba-injuries.md` and `docs/nba-injuries.md`.
  - **42d, locally complete:** pre-game season-to-date team for/allowed stats
    and league ranks from stored regular-season box scores. Opponent allowed
    stats appear in evidence, both teams' stats on the game page. No new
    source, projection input, gap, sort or pick change.

45. **NHL support** - NBA's team-sport shape; 45a-45f cover sourcing, ingest, lines, odds, display, and injuries and starting goalies (see Detailed feature context).
21. **WNBA support** - extends NBA.
22. **Three-way market support** - draws in de-vigging, ensemble, and schema.
23. **Soccer support** - on top of item 22.

**Why this order, and where it already broke.** Item 17 was meant to come first so
no sport needed a parallel stack. NFL was built before it anyway, in its own
`nfl_*` tables (17a and 17b have since moved the cross-sport ones to `sport_*`), because rewriting the working tennis schema for the first team
sport was judged the riskier order. The cost is the duplicate stack the original
rationale warned about: item 17 now converges two working systems instead of
generalizing one. The upside is that NFL has shown which tennis assumptions
actually fail for a team sport. **Items 20 and 21 must not add a third parallel
stack.** Item 22 is split from 23 because draws are the one genuinely hard change.

| Sport | What it breaks that tennis does not |
|---|---|
| NFL | Teams not individuals; weekly cadence means a far smaller training set; spreads and totals over moneyline |
| NBA | Teams, dense daily schedule, heavy prop volume |
| NHL | Teams, dense daily schedule like NBA; low-scoring small-integer count props, fixed +/-1.5 puck line, overtime-inclusive or regulation moneylines, separate skater and goalie stat sets |
| WNBA | NBA shape, shorter season, thinner public data |
| Soccer | **Draws.** Three-way markets break the two-outcome assumption throughout |

## Data model

### NBA prop board response (42a/42b, implemented)

No new database table or migration. `GET /nba/props?date=YYYY-MM-DD` returns
the existing game endpoints' line schemas in this camelCase contract:

```text
NbaPropBoardResponse
  date: string                   # resolved Eastern calendar date
  previousDate: string | null     # adjacent served game dates
  nextDate: string | null
  modelVersion: string
  games: NbaPropBoardGame[]

NbaPropBoardGame
  gameId: number
  awayTeam: string
  homeTeam: string
  startUtc: string | null
  status: string
  lines: NbaPropLine[]
  lineOnlyLines: NbaLineOnlyLine[]
```

**Load-bearing:** raw lines have exact game-endpoint parity, including nulls,
flags, probabilities and recent games. They are the last stored pre-tip
snapshot; started/final games remain in the response. The client groups
within each game before flattening, with identity including kind, game,
market and player. Dates remain Eastern while displayed tip times are CT.
42c/42d add display context through the existing game/board experience;
projection and line fields are unchanged. Their archives document the shared
context read paths and verification evidence.

**Display storage:** 42c stores NBA injury snapshots with ESPN athlete
and team identities, status, detail and fetch time (migration 0048).
42d derives team context from `nba_player_game_stats` and
`sport_games`, without a new source. Neither changes model inputs.

### Stored models

PostgreSQL via Alembic, sequentially numbered, **currently at revision `0048`**
(the plan still says `0019`; see Open questions). All primary keys are
`BigInteger` autoincrement. Timestamps are `TIMESTAMPTZ`.

### Player (`players`)

- `name` (text, required), `name_norm` (text, required, **unique index**)
- `tour` (text, required) - `ATP` | `WTA`
- `sofascore_id` (int), `ta_id` (int), `ta_slug` (varchar 200), `livetennis_id` (int)
- `birth_date` (date), `created_at` (timestamptz)
- `hand` (text) - `R` | `L`, `country` (text) - uppercase ISO code

`name_norm` is the dedupe key. The external id columns exist because players
arrive from four sources (livetennisapi, TennisAbstract, Odds-API.io, PrizePicks)
under different spellings.

### PlayerAlias (`player_aliases`)

- `canonical_player_id` -> `players.id` (cascade delete)
- `alias_name`, `alias_name_norm` (**unique index**), `source`

### Match (`matches`)

- `match_key` (text, **unique index**) - the idempotency key for re-ingest
- `match_date` (date, indexed), `start_utc` (timestamptz)
- `tour`, `surface`, `tournament`, `round`, `best_of` (smallint)
- `p1_id`, `p2_id`, `winner_id` -> `players.id`
- `p1_rank`, `p2_rank` (int), `score` (text)
- `p1_ranking_points`, `p2_ranking_points` (int), `p1_ranking_movement`,
  `p2_ranking_movement` (text) - point-in-time ranking snapshot per match
- `indoor` (boolean), `tournament_id` (text)
- `status` (text, default `scheduled`, indexed)
- `sofascore_id`, `livetennis_id` (int), `created_at`, `updated_at`

> **Locked tennis shape, left outside item 17's team-sport convergence.**
> `match_key` uniqueness and the `p1`/`p2` ordering are assumed by ingest,
> prediction and props linking. Broader convergence waits for item 22.
> Tennis-only assumptions that must generalize: `surface`, `round`, `best_of`; two
> `players` rather than two *teams*; `p1_*`/`p2_*` naming that presumes two
> outcomes; tennis-specific `player_rolling_stats` columns; and tennis-only
> `props.stat_type` values.

### MatchOdds (`match_odds`)

- `match_id` -> `matches.id` (cascade), indexed with `market`
- `book` (text), `market` (text) - `moneyline` | `total_games` | `set1_winner`
- `p1_odds`, `p2_odds` (int, American), `line` (numeric 6,1)
- `fetched_at` (timestamptz) - drives the `market_stale` quality flag

### PlayerElo (`player_elo`)

- `player_id` -> `players.id` (cascade), `as_of_date` (date) - **unique together**
- `elo`, `elo_hard`, `elo_clay`, `elo_grass` (float)
- `source` (text, default `tennisabstract`)

### PlayerRollingStats (`player_rolling_stats`)

Keyed by `player_id` + `stat_period` + `surface`, **unique with `NULLS NOT
DISTINCT`** so `surface IS NULL` (all surfaces) still upserts. Requires PostgreSQL 15+.

- `stat_period` (text), `window_matches` (int), `surface` (text, NULL = all)
- `split_type`, `split_value` (text) - contextual splits
- Core: `win_rate`, `svc_pts_won`, `ret_pts_won`, `aces_per_game`, `df_per_game`, `hold_pct`, `break_pct`, `matches_count`
- Serve detail: `first_in_pct`, `first_won_pct`, `second_won_pct`, `dominance_ratio`
- Opponent-allowed: `allowed_aces_per_sp`, `allowed_df_per_sp`, `allowed_first_in_pct`, `allowed_first_won_pct`, `allowed_second_won_pct`, `allowed_hold_pct`
- Break-point volume: `break_points_created_per_return_game`, `allowed_break_points_per_service_game`
- `computed_at` (timestamptz)

### PlayerMatchStats (`player_match_stats`, `0033`, join key `0035`, stable key `0038`)

Per-match box scores parsed from TennisAbstract and, since 41a, TennisMyLife.
Only TennisAbstract feeds the grading reports; display readers explicitly opt
in to TennisMyLife gap filling after the opponent and score checks.

- `player_id` -> `players.id` (cascade), `source` (text), `source_match_key`
  (text); **unique on** (`player_id`, `source`, `source_match_key`)
- **Since `0038`, `source_match_key` identifies the match, not the raw row:**
  `sha256("v2|<tournament start YYYYMMDD>|<tournament>|<round>|<opponent>")`,
  trimmed and lowercased, so a TennisAbstract refetch updates the row instead of
  inserting a copy. A refetch with no stats never blanks stored stats. Rows
  missing tournament, round or opponent (pre-26e legacy) keep the raw-row hash.
  `0038` merged 644 duplicate groups and left a `player_match_stats_pre_0038`
  snapshot for its downgrade (see Open questions).
- **TennisMyLife key (41a):** `sha256("tml-v1|<tourney_id>|<round>|<opponent>")`,
  with the opponent trimmed and lowercased; source `tennismylife` keeps it
  separate from TennisAbstract. `match_date` is the CSV's `tourney_date`.
- `match_date` (date, **the tournament start**; indexed with `player_id`),
  `surface`, `result` (text)
- `aces`, `double_faults`, `service_games`, `break_points_faced`,
  `break_points_saved`, `break_chances_created`, `break_points_converted`
  (smallint)
- From 26e (`0035`): `opponent_name`, `round`, `tournament`, and `score`
  (winner-first, with tie-break points), all nullable text. NULL means the row
  was ingested before 26e.
- `fetched_at` (timestamptz)

> **Load-bearing: join box scores with `app.core.box_score_join.join_box_score`,
> never on date.** A box score joins a match when exactly one row survives all
> of these checks:
> - same player and result
> - dated -14 to +3 days from the match
> - the opponent's surname matches
> - the set scores agree
>
> After 26e's backfill:
> - 92% of rows carry the join key
> - 85.7% of settled PrizePicks player-matches with a closing line join, from
>   13.5% before
> - 99.4% of joins are confirmed by the score too
>
> The match evidence panel (`/tennis/matches/{id}/recent-form`) uses the same
> join since the 2026-09-25 fix
> (`blueprint/history/fixes/evidence-panel-box-score-join.md`).

### H2H (`h2h`)

- `p1_id`, `p2_id` -> `players.id` (cascade), `surface` (NULL = all)
- **Unique on** (`p1_id`, `p2_id`, `surface`) with `NULLS NOT DISTINCT`, rows
  canonicalized to `p1_id < p2_id` (migration `0013`)
- `p1_wins`, `p2_wins` (int, default 0), `updated_at`

### Prediction (`predictions`)

- `match_id` -> `matches.id` (cascade), indexed with `generated_at`
- `model_version` (text, required)
- `p1_elo_prob`, `p1_ml_prob`, `p1_market_prob`, `p1_ensemble_prob` (float)
- `ensemble_weights` (JSONB), `quality_flags` (text[]), `feature_snapshot` (JSONB)

`feature_snapshot` preserves the inputs a prediction was made from, so calibration
can be evaluated after the fact.

### Prop (`props`)

- `player_id` -> `players.id`, `match_id` -> `matches.id` (both nullable)
- `source` (text) - `prizepicks` | `draftkings`
- `stat_type` (text) - `aces` | `double_faults` | `total_games` | `break_points`
- `line` (numeric 6,1, required), `odds_type` (text) - `standard` | `goblin` | `demon`
- `fetched_at`, `start_time`, `raw_json` (JSONB)

Nullable FKs are deliberate: props arrive before the player or match is matched.

### PropProjectionSnapshot (`prop_projection_snapshots`, 26f, `0034`)

The props page's projection for each upcoming PrizePicks line, frozen before the
start by the daily `app.ingest.prop_snapshots` job. It is the only leak-free
record of what a confidence tier predicted.

- **Keys.**
  - `prop_id` -> `props.id` (cascade)
  - `projection_version` (text, `props-v1`); **unique on** (`prop_id`,
    `projection_version`)
  - `snapshot_at` (timestamptz)
- **The line.**
  - `player_id` -> `players.id`
  - `match_id` -> `matches.id`, the match the page projected against, after its
    relink (indexed)
  - `stat_type`, `odds_type`, `line` (numeric 6,1)
  - `start_time` (always after `snapshot_at`)
- **The projection.**
  - `recommendation` (OVER | UNDER | NULL), `confidence` (LOCK | STRONG | LEAN |
    PASS | NULL)
  - `hit_probability`, `p_over`, `p_under`, `p_push`, `stat_avg`, `ev_pct`,
    `break_even_pct` (double)
  - `matches_count`, `market_total_games`, `projection_status`,
    `data_quality_flags` (text[]), `projection_inputs` (JSONB)

> **Load-bearing:**
> - Bump `PROJECTION_VERSION` in `app/services/tennis/prop_snapshots.py` on any
>   projection, probability, EV or tier change, so grading never pools logic.
> - Box-score stat snapshots are stored now, for 26e to grade.
> - Graded by `python -m app.backtest.tennis_prop_snapshots`, and served by
>   `GET /tennis/model/prop-tiers` under the 32b tier rule.
> - `GradedPropSnapshot` carries `snapshot_at` (32b); the tier rule groups
>   picks by its UTC date.

### Bet (`bets`) - retired

**No reader since 2026-10-15** (fix `remove-my-bets`): bets are tracked in
Pikkit, and the page, `/bets` API, repository and schemas are deleted. The table
and its migrations (`0005`, `0011`) stay until a later migration drops it after
the rows are exported.

- `bet_date` (date, default `CURRENT_DATE`), `label` (text, required), `notes`
- `bet_type` (text) - `single` | `parlay_leg` | `parlay`
- `source` (text) - `bankroll_builder` | `manual`
- `pick_side` (text) - `p1` | `p2` | `over` | `under`
- `odds_american` (int, required), `wager`, `potential_payout` (numeric 10,2, required), `actual_payout` (numeric 10,2)
- `status` (text, default `pending`), `parlay_id` (text)
- Value constraints from migration `0011`. No user foreign key, and none is planned.

### ReportSnapshot (`report_snapshots`, 37d, `0045`)

Precomputed responses the hosted demo serves instead of building them.

- `report` (text) and `season` (int), the **primary key** together
- `payload` (JSONB), `computed_at` (timestamptz)
- Rows: `nfl_line_grading` (an `NflModelPropLinesResponse`) and
  `nfl_slate_week_<N>` (an `NflSlateResponse`, read back as text and sent
  unparsed). Repository: `app/repositories/report_snapshots.py`.

### Sports registry (`sports`, 17a, `0039`)

- `code` (text, **primary key**), `name` (text, required)
- Seeded with `nfl`; `0043` (20b) adds `nba`. 17d's registries live in code
  and do not read it.

### Shared team-sport tables (`sport_*`, 17a and 17b, `0039` to `0041`)

Seven tables that every team sport writes, each with `sport` (text, required,
foreign key to `sports.code`, **no default**, so a missing sport is an error).
NFL and NBA (20b to 20d) write to them. They were the `nfl_*` tables until 17a
renamed them in place (rows, ids and inbound foreign keys carried over); 17b
moved all NFL code onto them and `0041` dropped the `nfl_*` compatibility
views. NFLverse ids are the NFL join keys: gsis id (`source_player_id`) and
game id (`source_game_id`). Ingest matches players, games, and teams and never
creates them; unknowns are skipped and counted.

- **`sport_teams`** - `team_code` (NFLverse codes for NFL), `name`, `conference`, `division`; **unique on** (`sport`, `team_code`)
- **`sport_players`** - `source_player_id`, `name`, `position`, `team_id` (last-write-wins; NFL readers use the weekly roster instead, see below); **unique on** (`sport`, `source_player_id`)
- **`sport_player_aliases`** - provider-name overrides: `player_id`, `alias_name`, `alias_name_norm`, `source`; **unique on** (`sport`, `alias_name_norm`)
- **`sport_games`** - `source_game_id`, `season`, `week` (nullable at the shared schema level; `CHECK (sport <> 'nfl' OR week IS NOT NULL)`; NBA ingest also assigns the regular-season Eastern week defined by 20a), `game_type`, `game_date`, `start_utc`, `home_team_id`, `away_team_id`, `home_score`, `away_score`, `status`; **unique on** (`sport`, `source_game_id`). NFL-only nullable columns stay here (decided in 17b; other sports leave them NULL): from 19n (`0028`), NFLverse closing lines `spread_line` (expected home margin: positive = home favored), `total_line`, `home_moneyline`, `away_moneyline`, plus `roof`, `home_rest`, `away_rest`; from 24e (`0031`), `temp` (°F) and `wind` (mph) smallint, observed rather than forecast, NULL for indoor games and blanks; and `espn_event_id`
- **`sport_prop_lines`** - PrizePicks snapshots: `provider`, `provider_prop_id`, `market`, **`segment`**, `odds_type`, `line`, `start_time`, `player_id`, `game_id`, `fetched_at`, `raw_json`
- **`sport_game_odds`** (19f, `0020`) - append-only: `game_id`, `book`, `market` (`moneyline` | `spread` | `total`), `line`, `first_side`/`second_side`, `first_odds`/`second_odds` (American), de-vigged `first_market_prob`/`second_market_prob`, `fetched_at`, `raw_json`. `provider` (36a, `0044`): `the_odds_api_us` (every row before 36a; the only feed pre-36a readers see), `the_odds_api_eu` (Pinnacle) or `odds_api_io` (Bet365, DraftKings); every reader names its provider, enforced by `tests/test_sport_game_odds_provider.py`
- **`sport_prop_predictions`** (defined in `0015`, first written by 27i, reshaped in `0037`, NBA rows from 20g3, targets freezing from 39c) - one frozen pre-kickoff prediction per line snapshot and version: `prop_line_id`, `model_version`, `over_probability_version` (NULL when no P(over) was served), nullable `projection`, `p_over`, `p_under`, `edge`, `quality_flags`, `feature_snapshot` (baseline games and season, adjustments, line, odds type, market, segment, line fetch time), `generated_at` (always before kickoff); **unique on** (`prop_line_id`, `model_version`, `over_probability_version`) `NULLS NOT DISTINCT`, and never updated. `confidence` is unused. 27j grades each provider prop's latest frozen pre-kickoff row, at its own line. Targets use `nfl-targets-v1` and a null probability version; 39d selects and settles them as a separate report without changing the v4 sample.

> **Load-bearing (17a, 17b):**
> - Every read and write of a `sport_*` table carries its sport filter
>   (`<alias>.sport = 'nfl'` in NFL-only queries, a literal), even across a
>   sport-scoped foreign key. A sport never reaches another sport's rows. The
>   shared prop queries in `app/repositories/sport_props.py` bind `:sport`
>   instead (17c; re-measured, no slower than the literal).
> - The four `(sport, ...)` unique keys above are every sport's `ON CONFLICT`
>   targets.
> - `tests/test_no_nfl_view_names.py` fails if any `app/` file names an old
>   `nfl_*` table or the old columns (`nflverse_id`, `nflverse_game_id`,
>   `nfl_player_id`).
> - `0039` ends with `ANALYZE` on each table: without statistics on the new
>   `sport` column a slate query went from 27 s to over 9 minutes.

> **Load-bearing (17c): the shared prop pipeline.** A new sport supplies only
> these, and reuses everything else:
> - a `SportPropConfig` (`app/core/prop_sports.py`): code, PrizePicks league
>   prefix and segment suffixes, board segments, market aliases, period label
> - a `PropLineSource` (`app/services/sport_props.py`, 20c): `config` and
>   `load_resolver`, all that storing and relinking lines needs
> - a `SportPropSource`, extending it for freezing and grading:
>   `current_period`, `freezable_games` (its projection),
>   `frozen_lines` (settled against its own stat tables), `finished_periods`,
>   `frozen_coverage`, model and P(over) versions
>
> The shared parts are `app/ingest/prizepicks_props.py`,
> `app/core/prop_predictions.py`, `app/services/prop_predictions.py`,
> `app/core/prop_ranking_rule.py`, `app/core/prop_ranking_check.py` and
> `app/services/prop_ranking.py`. **A period** is a per-season integer the
> sport defines; it counts only once every game in it is complete. NFL's is the
> week. NBA's is the regular-season week too (20a), stored in `sport_games.week`.
> `tests/test_sport_props_pipeline.py` fails if the shared modules load NFL
> code.

### NBA box scores (`nba_player_game_stats`, 20b, `0043`)

NBA games, teams and players live in the shared `sport_*` tables under
`sport = 'nba'`, keyed by ESPN ids (20a), loaded daily by
`python -m app.ingest.hoopr_nba` from hoopR's ESPN release files
(`nba-ingest.yml`, 09:30 UTC, October to June, which then relinks stored
PrizePicks NBA lines). Stored seasons: 2023-24 and 2024-25 (backfilled by 20f,
about 35,000 box-score rows each), 2025-26, and the 2026-27 schedule.

- **`sport_games` for NBA:** `season` is the start year; `game_type` `REG`,
  `PIN` (play-in) or `PST` (playoffs); `week` is the regular-season week, NULL
  off the regular season; `status` is `scheduled`, `completed`, `postponed` or
  `canceled`. A postponed game is replayed under a new ESPN id, so **a week is
  finished once every `REG` game in it is `completed`, `postponed` or
  `canceled`** (load-bearing for 20g). All-Star games and NBA Cup `TBD` slots
  are never stored; the Cup final is `REG`.
- **Preseason (`PRE`, fix 2026-10-06):** games between NBA franchises and
  their box scores, from ESPN's site API (`python -m app.ingest.espn_nba_preseason`,
  `nba-preseason.yml`, daily October 1 to 20), with `week` NULL. Overseas
  clubs are skipped (`NBA_TEAM_CODES`). **Load-bearing for 20f and 20g:**
  every NBA reader that builds a baseline, projects or grades filters
  `game_type IN ('REG', 'PIN', 'PST')`, never `PRE`.
- **`sport_teams.team_code`** is `varchar(8)` since `0043` (Utah's ESPN code is
  `UTAH`).
- **`nba_player_game_stats`:** one row per player per game, **unique on
  (`player_id`, `game_id`)**; `team_id`, `opponent_team_id`, `season`,
  `is_home`, `starter`, `did_not_play`, `dnp_reason`, `minutes` (real), and
  smallint `points`, `rebounds`, `offensive_rebounds`, `defensive_rebounds`,
  `assists`, `steals`, `blocks`, `turnovers`, `fouls`, `field_goals_*`,
  `three_pointers_*`, `free_throws_*`, `plus_minus`. NULL means not loaded or
  did not play, never zero. `dnp_reason` is set only on DNP rows.
- **Load-bearing:** a player's team for a past game is the box-score row's
  `team_id`, never `sport_players.team_id` (last team loaded; NBA trades
  mid-season).

### NFL stat and context tables (`nfl_*`)

Genuinely sport-specific columns, so each later sport gets its own stat tables
referencing the shared ids. Added from `0015` through `0036`.

- **`nfl_team_elo`** (24a, `0030`) - `team_id`, `game_id`, `model_version` (unique together), `season`, `week` (copied from the game), `is_home`, `elo_pre`, `elo_post` (NULL until final), `computed_at`. Regular season only, recomputed in full each run (replace per `model_version`); stores `nfl-elo-v1`.
- **`nfl_team_game_efficiency`** (24c, `0032`) - `game_id`, `team_id` (the offense; unique together), `season`, `week` (copied from the game), `is_home`, `plays` (smallint), `epa` (double, **summed**, not averaged), `successes` (smallint, `epa > 0`), `fetched_at`. Counted plays are regular-season `run` and `pass` (sacks and scrambles included; two-point tries, kneels, spikes, `no_play`, special teams, and blank EPA excluded). Only final games are written; the team comes from the game's home or away side, never a team code. A team-game's defense is the opponent's row; a missing row means not loaded, never zero plays.
- **`nfl_player_weekly_stats`** - per player per game, unique on (`player_id`, `game_id`); player and opponent team, passing/rushing/receiving volume, scoring `touchdowns` (rushing plus receiving, not passing), `fantasy_points`; nullable usage from 19h (`targets`, `target_share`, `air_yards_share`, `wopr`); nullable red-zone counts from 19j (`rz20_carries`, `rz20_targets`, `rz5_carries`, `rz5_targets`, smallint); nullable `end_zone_targets` from 19n (`0029`). From 27f (`0036`), nullable scoring components `passing_tds`, `interceptions`, `fumbles_lost`, `two_point_conversions`, `return_tds`, `fumble_recovery_tds` (smallint) and `prizepicks_fantasy_points` (double, computed at ingest; fantasy lines settle on it, while `fantasy_points` stays NFLverse PPR). From 34b (`0042`), nullable `fg_made` and `pat_made` (weekly stats file) and `punts` (play-by-play, zeroed for every row in a loaded game like the red-zone counts; the weekly upsert never writes it). NULL means unknown or not loaded, never zero.
- **`nfl_player_weekly_rosters`** (19k, `0025`) - `player_id`, `season`, `week` (unique together), `team_id`, `status` (NFLverse roster status, verbatim). **Team-as-of rule:** a player's team for a week is the latest roster row at or before it; `CUT` or `RET` means no team; only a player never on a roster falls back to `sport_players.team_id`.
- **`nfl_player_injuries`** (19l, `0026`) - `player_id`, `season`, `week` (unique together), `team_id`, `report_status` (Out | Doubtful | Questionable; NULL = practice report only, never "healthy"), `practice_status`, `primary_injury`
- **`nfl_player_depth_charts`** (19l, `0026`) - `player_id`, `season`, `week` (unique together), `team_id`, `position` (QB | RB | WR | TE), `depth_rank`, `snapshot_at`. One pre-game snapshot per team-week: the latest taken on or before the team's game day.
- **`nfl_player_snap_counts`** (19m, `0027`) - `player_id`, `game_id` (unique together), `season`, `week` (copied from the game), `team_id`, `offense_snaps` (smallint), `offense_pct` (real, 0 to 1). NULL means blank at source; 0 means no offensive snaps. Its own table because many player-games have snaps but no stat row (blocking TEs). Matched from PFR ids through NFLverse `players.csv`.
- **`nfl_player_prop_odds`** (19i, `0023`) - append-only, one row per book per player per fetch: `game_id`, nullable `player_id` (unresolved names kept, not guessed), `provider_player_name`, `provider_event_id`, `market` (check: `anytime_touchdown` only for now), `book`, `line`, `yes_odds`, nullable `no_odds`, `market_prob`, `includes_margin`, `fetched_at`, `raw_json`
- **`nfl_game_weather_snapshots`** (`0022`) - `game_id`, `venue_type` (`outdoor` | `dome` | `retractable`), `provider`, `forecast_for`, temperature, wind, gust, precipitation probability, `fetched_at`. Not in either plan; see Open questions.
- **`nfl_prop_results`** - defined, not yet written to

> **Load-bearing:**
>
> - `nfl_player_prop_odds` is the shape later sportsbook prop markets reuse
>   (`player_rush_yds` next). Market enablement is the `PROP_MARKETS` map in
>   `app/ingest/nfl_prop_odds.py`.
> - Every as-of read uses one cutoff: regular season, and `season < S OR (season
>   = S AND week < W)`. `/projections` and `/slate` share it, so both compute the
>   same anytime-TD baseline.

Next Gen Stats is deliberately not planned: it measures efficiency, while prop
outcomes are driven more by volume.

## Tech stack

**Backend**

- **FastAPI 0.115 + Uvicorn** - the API, with a lifespan hook that loads models once
- **SQLAlchemy 2.0 async + psycopg3** - all DB access, through `app/repositories/`
- **Alembic** - every schema change, sequentially numbered
- **Pydantic 2 + pydantic-settings** - request/response schemas and env config
- **LightGBM / XGBoost / scikit-learn / joblib** - models and calibration; the future tennis v7 policy uses validation-fitted sigmoid calibration (scikit-learn also fits the NFL backtests)
- **Playwright / httpx / requests / tenacity** - ingest and retry

**Frontend**

- **React 19 + Vite 7** - SPA, no metaframework, because it is a pure API client
- **TypeScript strict** - no `any`
- **Ant Design 5** - structural and interactive components
- **Tailwind v4** - utility styling, CSS-first, no config file
- **TanStack Query 5 + axios** - all server state

### Data sources

| Sport | Schedule | Stats / ratings | Odds | Props |
|---|---|---|---|---|
| Tennis | livetennisapi | TennisAbstract (ELO, rolling and per-match stats, WTA 125); TennisMyLife (ATP, Challenger, qualifying and WTA box-score display gaps, 41a; shadow ELO `tennismylife-elo-v1`, 41b, not served) | Odds-API.io | PrizePicks, DraftKings |
| NFL | NFLverse | NFLverse weekly stats, play-by-play, rosters, injuries, depth charts, snap counts | The Odds API (free plan: us books, Pinnacle via eu from 36a); Odds-API.io (Bet365, DraftKings from 36a) | PrizePicks, The Odds API (anytime TD) |
| NBA | hoopR ESPN releases (`espn_nba_schedules`) | hoopR ESPN player box scores (`espn_nba_player_boxscores`); ESPN injuries (display snapshots, 42c locally complete) | The Odds API (free plan, game lines only) | PrizePicks |
| NHL | NHL web API (`api-web.nhle.com`) | NHL stats REST per-game skater and goalie reports; sportsdataverse `nhl_player_boxscores` fallback; ESPN injuries and probable goalies (display, 45f) | Odds-API.io (DraftKings, Bet365) | PrizePicks |
| WNBA / Soccer | > TODO | > TODO | The Odds API (per plan) | > TODO |

**Backtest-only source:** 26c reads Valuebetennis season CSVs (ATP and WTA
results with Pinnacle opening and closing odds, 2021 onward, CC BY 4.0),
downloaded once into a gitignored local folder. Nothing ingests them into the
database and no app code fetches the site.

**Two odds providers, easily confused.**
- **Odds-API.io** (`api.odds-api.io`, `ODDS_API_KEY`): tennis, and from 36a NFL
  Bet365 and DraftKings game lines. Free plan: 100 requests an hour and **two
  books, shared across sports** (DraftKings and Bet365); sharp books and
  exchanges are paid only.
- **The Odds API** (`api.the-odds-api.com`, `THE_ODDS_API_KEY`): NFL and NBA,
  on the **free plan: 500 credits a month**. Event listing is free; odds cost
  one credit per market per region per request. NFL game odds cost about 3
  credits a week, plus about 3 a run for Pinnacle (`eu` region) from 36a;
  player props are billed per game per market, so NFL prop markets are added
  one at a time (`player_anytime_td` alone is about 16 credits a week). NBA
  game odds cost 3 credits a run, twice daily (about 180 a month; 20d), for a
  shared total of about 332 of 500 while both seasons run, before 36a; about 397 with 36a's Pinnacle runs (measured by 45a, 2026-10-23), which is why NHL odds use Odds-API.io.

**Prefer free sources.** Between the two providers odds are covered, so the real
gap per new sport is schedule and stats. NFLverse publishes all its NFL data as
public release assets, with no key and no quota.

**PrizePicks is rate-limited and segment-ambiguous.** It answers `429` with a
`Retry-After` that must be honored, and publishes season, half, and quarter
leagues under the same stat names as the full game, so every stored line records
its `segment`.

## Monetization

**None, and not before roughly 2028.** Deferred one to two years from August 2026.
This is a personal tool that makes money by winning bets, not by selling anything.

Out of scope as a result:

- accounts, billing, subscriptions, entitlement checks
- per-user data scoping; the shared `X-API-Key` stays sufficient
- marketing surface, onboarding, pricing page
- compliance, ToS, and responsible-gambling disclosures

Revisit `project-plan.md` §6 before any product-stage work.

## UI/UX

Dark, dense, data-first. Theme lives as CSS custom properties in
`web/src/index.css`, ported in 31a from the since-discarded `prototypes/theme.css`:
true-black background `#000`, near-black cards, low-contrast borders, green
`#00c805` only for a positive signal and red `#ff5000` only for negatives,
everything else grayscale. 31a shipped this theme app-wide on 2026-09-28,
replacing the old navy one. Tour accents carry meaning (ATP `#3b82f6`,
WTA `#f43f7b`, Challenger `#14b8a6`). **Green is a signal color:** an
unvalidated number never gets it (see the rule under Web routes). Three fonts by role: Barlow Condensed display, DM Sans body,
JetBrains Mono numerics, because the product is scanning columns of numbers.
The tennis model track record page (32b) follows the green rule too: its
grading numbers stay gray unless one beats its stated baseline or break-even
by more than 2 SE, and red marks only a rate more than 2 SE below break-even.
The NFL model page (33d) follows it the same way, and keeps every
pre-registered verdict gray until it is decided. **The NFL prop edge is gray**
on the slate, prop board, game and player pages until 27h adopts a slice,
because 27a graded the model at 48.1% against a 57.7% break-even (decided
2026-09-30; shipped by 33b). **No UI text below 11px**, including
micro-labels, tags and table cells.

**Structure (item 38, 2026-10):** the app is renamed Lineform and restructured:
one command-bar shell across every page (sport tabs, Slate / Props / Model, a
`/` search that jumps to any game, team or player), a table-first slate shared
by tennis, NFL and NBA (a plays digest, then one row per game; tennis rows
expand inline instead of a side panel), and props shown as table rows instead
of cards. Feature 38 is complete. NBA still has no standalone Props board;
its prop tables live on game pages. The theme above is unchanged.

Mobile is a real target: `useIsMobile` swaps the nav to a drawer.

**Guiding principle:** the user should scan a slate and see the actionable plays
without reading everything. Quality flags and EV ranking cut the list down.

### Web routes (HashRouter)

- `/` - Tennis intelligence, the daily slate
- `/tennis/board` - Tennis prop board with dense rows and an evidence drawer (38d2); existing EV colors and ranking rules
- `/tennis/match/:matchId` - Match detail page (32a)
- `/tennis/model` - Model track record page (32b)
- `/tennis/player/:playerId` - Player page (32c)
- `/nfl` - NFL slate (38b), opening on the current week (`/nfl/current-week`): a summary strip, a gray plays digest of the week's four largest prop gaps, and one table row per game grouped by kickoff window (market with line movement, muted model, prop count, injury, QB and short-week tags, conditions), each row opening the game page; `?gameId=` redirects there
- `/nfl/board` - NFL prop board: every player in one market across the week, ranked, with the prop detail drawer (recent form, opponent history, alternates, depth chart, injury report, snap share on RB/TE anytime TD, sportsbook anytime-TD consensus)
- `/nfl/game/:gameId` - NFL game page (33a)
- `/nfl/player/:playerId` - NFL player page (33c)
- `/nfl/model` - NFL model track record page (33d)
- `/nba` - NBA slate (38c2): one Eastern date (`?date=YYYY-MM-DD`, default today else the next game date), a summary strip, gray reference digest and one table row per game, each linking to the game page
- `/nba/game/:gameId` - NBA game page (20e3, 38d3, 38f), with the shared page head, gray modelled and line-only prop rows and evidence drawers; reference projection, gap and P(over) for assists remain unchanged
- `/nba/model` - NBA model track record page (20g4): the forward ranking check's four slices, gray until decided
- `/nba/board` - implemented and locally verified (42b): one Eastern date and one market, gray rows ordered by tip time then player, shared NBA evidence drawers, date/market URL history, game links and CT tips/status. Never sorted by gap or P(over). Injury tags (42c) and opponent allowed stats/rank (42d) are implemented display context. Hosted deployment unverified.
- The shared shell's view tabs read Slate / Props / Model for tennis, NFL and NBA (`web/src/utils/sportNav.ts`); 42b adds NBA Props.
- `/parlays` - Bankroll builder. Hidden from the nav since 2026-09-25; the route and API remain.
- `/how-it-works` - public explainer (37b): pipeline, what each sport shows, how a model earns a pick
- `/admin` - Admin surface: a sign-in card until the owner enters `ADMIN_API_KEY` (37a); its nav entry is hidden from visitors
- `/props`, `/live-odds`, `/bets` - redirect to `/` (`/live-odds` and `/bets` since their pages were removed 2026-10-15)

> Only standard full-game lines with a sufficient sample receive an edge. The
> sportsbook anytime-TD probability is displayed beside the model, not blended,
> until build-plan item 25c passes its backtest; that item may then let it drive
> edge and rank for anytime TD, and only anytime TD. Injury and depth flags warn
> but never change an edge or its rank. The muted game model (slate rows and
> game page) is never colored as a signal, sorted by, or added to a signal board.

### API routes

| Prefix | Endpoints |
|---|---|
| `/tennis` | `predictions/today`, `predictions/best-picks`, `matches/{id}`, `matches/{id}/odds-history?market=moneyline\|total_games`, `matches/{id}/recent-form`, `model/predictions`, `model/prizepicks-lines`, `model/prop-tiers`, `players/{id}`, `players/{id}/serve-return`, `players/{id}/matches?limit=`, `players/{id}/props`, `players/stats`, `players/compare`, `bankroll/today`, `parlays/suggested` |
| `/tennis/props` | `top`, `prizepicks`, `prizepicks/audit`, `dk`, `bet` (Bet365 props) |
| `/nfl` | `current-week`, `games`, `games/{id}`, `games/{id}/line-only-props`, `players/{id}`, `projections`, `prospects`, `slate`, `game-notes`, `model/ranking?season=&model_version=`, `model/prop-lines?season=`, `model/game-line-clv?season=`, `model/over-probability-fit` |
| `/nba` | `slate?date=`, `slate/gaps?date=`, `props?date=`, `games/{id}`, `games/{id}/props`, `games/{id}/line-only-props`, `model/ranking?season=` |
| `/admin` | `session`, `players/flagged`, `players/{id}/fetch-stats`, `players/{id}/fetch-elo`, `players/{id}/set-elo` (all need `X-API-Key` when a key is set) |
| root | `/health` |

`/nfl/slate` lines carry nullable role fields: injury (`injury_status`,
`practice_status`, `injury`), depth (`depth_position`, `depth_rank`,
`previous_depth_position`, `previous_depth_rank`), and, on RB/TE anytime-TD lines
only, `snap_share` and `snap_share_games`. From 27g, `p_over`, `p_under` and
`over_probability_version` (`nfl-pover-v1`) on full-game lines in shown markets
with 4+ baseline games, of any odds type; null means not shown, never 0.5.
Related flags: `injury_out`,
`injury_doubtful`, `injury_questionable`, `depth_promoted`, `depth_demoted`,
`depth_new`, `team_not_in_game`, `snap_share_unavailable`.

`/nfl/slate` games carry `odds` (latest market, DraftKings preferred:
`home_moneyline`, `away_moneyline`, `home_spread`, `total`) and, from 24d, a
nullable `model` block (**load-bearing**: any later adopted game-line signal
extends this block rather than adding another):

| Field | Meaning |
|---|---|
| `model_version` | `nfl-elo-v1` |
| `home_elo`, `away_elo` | pre-game ratings from `nfl_team_elo` |
| `home_win_probability` | ELO, home field 48 |
| `home_spread` | **book sign**, same as `odds.home_spread`: negative = home favored. The negation of NFLverse's expected-home-margin convention. |
| `total` | scoring-rating expected points, replayed per request |
| `market_home_win_probability` | de-vigged from the displayed book's moneylines; null without both |

`model` is null when either team lacks a pre-game rating. Ratings refresh
with the Tuesday ELO recompute, so they can be a week stale in between.

## Deployment

Hosted read-only demo on Render since 2026-10-16 (37d), from `render.yaml` in the public repo `Dayshawn21/Sports-Baseline` (37e); still runnable locally.

- **API:** Render web service `sportapp-api` (always-on `0.5c-512mb`, 512 MB, Virginia); locally `uvicorn app.main:app` on port 8000
- **Web:** Render static site `sportapp-web`; locally the Vite dev server on 3001, proxying `/api` and `/health` to the API
- **Build output:** `web/build`
- **Database:** hosted Neon PostgreSQL (15+) via `DATABASE_URL`
- **Health check:** `GET /health`
- **Env vars:** `DATABASE_URL`, `ODDS_API_KEY` (Odds-API.io, tennis and from 36a NFL Bet365/DraftKings), `THE_ODDS_API_KEY` (The Odds API, NFL and NBA), `LIVETENNIS_API_KEY`, `LIVETENNIS_TIER`, `ADMIN_API_KEY`, `API_ENV` (`dev` default, or `production`), `CORS_ORIGINS` (JSON list), `RATE_LIMIT_DEFAULT` (`120/minute`), `RATE_LIMIT_HEAVY` (`10/minute`)
- **Cron:** remote, in GitHub Actions with repo secrets, September through February for NFL
  - **Tennis uses six workflow files**, preserving the prior UTC schedules
    and commands (completed `tennis-workflow-split` fix). The split is present
    on local `master`; runner registration/execution are unverified here.
    `docs/tennis-actions.md` documents manual operations and dependencies:
    - `tennis-ingest.yml`: matches and H2H, daily 06:30 UTC.
    - `tennis-odds.yml`: odds for the next 14 hours, every four hours at :10 UTC.
    - `tennis-prop-lines.yml`: PrizePicks lines, daily 13:00 UTC.
    - `tennis-predictions.yml`: predictions then projection snapshots (26f),
      daily 13:30 UTC; the dependent ELO shadow freeze runs only after both
      succeed. Manual `tennis-elo-comparison` runs that operation alone.
    - `tennis-box-scores.yml`: TennisMyLife box scores, daily 11:00 UTC;
      its dependent candidate ELO refresh validates the complete roster and
      original files. Manual `tennis-elo` runs that candidate operation alone.
    - `tennis-player-stats.yml`: player stats, daily 10:00 UTC, including
      refetching yesterday's players for box scores (26e).
    Dependencies retain failure/cancellation guards, exact UTC-day cache
    keys, identity/implementation pins and original-file checks. No automatic
    experiment activation, scoring or served-ELO change. Each workflow has
    `DATABASE_URL`; only matches gets `LIVETENNIS_API_KEY`, only odds gets
    `ODDS_API_KEY`; token permission is `contents: read`.
  - **A local Windows scheduled task, `Lineform ingest_daily`** (daily 12:00
    local, registered 2026-10-18), runs `api/ingest_daily.bat` from its own
    folder against the same database, using whatever branch is checked out.
    It holds the TennisAbstract ELO refresh, which left `tennis-ingest.yml`
    because Cloudflare returns 403 to GitHub's runners (fix
    `elo-refresh-local`). It runs only while the PC is on.
  - `nfl-ingest.yml` (Tuesday) - NFLverse stats, team ELO recompute, red-zone counts, team efficiency, snap counts, weekly rosters, injuries, depth charts, NFL game odds, prop relink, then the prop-market holdout, PrizePicks line grading, game-line CLV and forward ranking check reports (read-only, on the Summary page)
  - `nfl-prop-odds.yml` (Wednesday 23:10, Thursday 18:10, Saturday 23:10, Sunday 12:10 UTC; windows 30, 8, 50, 40 hours) - refresh rosters, injuries, and depth charts, then anytime-TD prices with `--confirm-spend`, credit floor 50. About 32 credits a week. Off-the-hour times and early runs exist because GitHub started week-2 runs 2-3 hours late.
  - `nfl-prop-lines.yml` (Thursday 20:00, Saturday 23:00, Sunday 15:00, Monday 20:00 UTC) - free PrizePicks NFL line snapshots before kickoff, the line history item 27 grades, then (27i) `app.ingest.nfl_prop_predictions` freezes the slate's predictions for every line not yet kicked off. Since 17b's `0041` it needs a database at `0041` and code on the shared tables, so the branch is pushed in the same sitting as any destructive migration.
  - `nfl-scores.yml` (daily 13:00 UTC, fix 2026-10-02) - `python -m app.ingest.nflverse --schedule-only`, so finished games read final the next morning instead of on Tuesday. Display only: grading still waits for Tuesday's player stats.
  - `nfl-weather.yml` (daily 14:00 UTC) - weather snapshots for upcoming games (`nfl_game_weather_snapshots`).
  - `nba-ingest.yml` (daily 09:30 UTC, October to June) - hoopR NBA schedule and box scores, then `prizepicks_nba --relink` (20b, 20c), then the NBA forward ranking check report (20g4, read-only, on the Summary page).
  - `nba-prop-lines.yml` (daily 16:30 and 22:15 UTC, October to June) - free PrizePicks NBA line snapshots before tip-off (20c); then (20g3) `app.ingest.nba_prop_predictions` freezes the reference projection and P(over) for every modelled line not yet tipped off.
  - `nba-odds.yml` (daily 15:00 and 22:30 UTC, October to June) - NBA moneyline, spread and total, 3 credits a run, skipped below 100 remaining credits or with no game in the next 2 days (20d).

**CI (37c):** `.github/workflows/verify.yml` on every pull request, push to
`master` and manual run: `verify` (Node 24, Python 3.11, the Verify command)
and `secret-scan` (gitleaks 8.28.0, checksum-pinned). Both run on the public
repo; GitHub push protection is enabled. Keep both job names stable if a
ruleset requires them.

**API hardening (fix `api-hardening`, 2026-10-15):**

- **Production check:** with `API_ENV=production`, startup is refused when `ADMIN_API_KEY` is empty or under 32 characters, or `CORS_ORIGINS` holds `*` or a localhost origin (`validate_production_settings` in `app/core/production_settings.py`). Dev is never checked.
- **Key guard:** `require_api_key` covers the whole `/admin` router, `GET /admin/players/flagged` included; with the key empty (dev) it stays open with a warning.
- **Rate limits** per client IP (`limits`, in-memory, one instance): the default on every route, the heavy limit on `/nfl/model/*`, `/tennis/model/*`, `/nba/model/*` and `/nfl/slate`; over the limit returns 429 with `Retry-After`. `/health` is exempt. Behind a proxy, uvicorn needs `--proxy-headers` or every visitor shares one bucket.
- **Security headers:** `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, and `Strict-Transport-Security` in production.

**Model artifacts** ship from git: the v6 LightGBM files are tracked, so a
deploy needs no artifact step (37d proved they load from a clean checkout).

**Host:** Render (decided 2026-10-15, live 2026-10-16).
**Memory:** 512 MB. Production serves the NFL slate and NFL line grading
from `report_snapshots` and never builds them; keep any new heavy report off
the request path the same way.

## Open questions

1. **Plan §4 data section is behind the completed build plan.** It says
   revision `0019`; the existing schema notes extend through `0047`
   (`0033` adds `player_match_stats`, `0034` adds
   `prop_projection_snapshots`, `0035` adds the box-score join key, `0036` adds
   the 27f fantasy components, `0037` reshapes `nfl_prop_predictions` for 27i,
   `0038` rekeys box scores, `0039` to `0041` move seven NFL tables to
   `sport_*` and add `sports`; `0042` adds kicking/punting stats, `0043`
   adds NBA data, `0044` adds odds providers, `0045` adds report snapshots,
   and `0046`/`0047` add isolated tennis ELO snapshots/comparisons).
   It still describes the `nfl_*` tables as the
   NFL schema, and does not list the 19n `sport_games` line columns or `end_zone_targets`, `sport_game_odds` (19f), the usage and red-zone
   columns (19h, 19j), `nfl_game_weather_snapshots`, `nfl_player_prop_odds`
   (19i), `nfl_player_weekly_rosters` (19k), `nfl_player_injuries` and
   `nfl_player_depth_charts` (19l), `nfl_player_snap_counts` (19m), the
   `sport_games` `temp` and `wind` columns (24e), or `nfl_team_game_efficiency`
   (24c). It still labels `nfl_team_elo` "planned, 24a"; it shipped. Its
   "Planned NFL data (19j to 19m)" table still reads as planned; all four
   shipped.

2. **Plan §4 still says future NFL models need week-aware rosters.** 19k shipped
   them. Refresh the "NFL is deliberately parallel" paragraph.

3. **Plan §3 "Planned sports" is stale.** It says NFL still needs
   opponent-adjusted projections and usage inputs (19g, 19h shipped) and does
   not mention 19i to 19m. Item 19 is now complete. Its item 24 paragraph
   still reads as a plan; item 24 is complete, with ELO, efficiency, and totals
   context all rejected against closing lines and the slate showing the model
   as display-only context.

4. **NFL weather is in neither plan.** Migration `0022` and the slate weather
   context shipped as a fix. Add it to `project-plan.md` §3/§4 if it is a lasting
   feature.

5. **Build-plan item 5 names the wrong tennis provider.** It says The Odds API;
   tennis uses Odds-API.io. NBA is confirmed on The Odds API (20a); the
   WNBA/Soccer odds cell still says The Odds API; confirm which provider those
   sports use.

6. **Resolved (2026-09-26):** the owner confirmed `THE_ODDS_API_KEY` is a
   GitHub repo secret, so `nfl-ingest.yml` and `nfl-prop-odds.yml` can fetch.

7. **Which stored NFL signals the model uses is uneven.** Targets and target
   share feed receiving yards and receptions only; `air_yards_share` and `wopr`
   are stored but unused. Red-zone counts are stored but were rejected by the
   backtest (19j). Injuries and depth are display only (19l). Snap share feeds
   RB/TE anytime TD only (19m). None of this conflicts with the plans; it is the
   "backtest before use" rule working, but a later feature should decide which
   of these to test next.

8. **Resolved (2026-10-15):** deployment is item 37d, on Render.

9. **Legacy `sofascore_id` columns** remain on `players` and `matches` although
   ingest moved to livetennisapi in `0012`. Not a blocker. 17d leaves tennis
   `matches` convergence out of item 17, so this now waits for item 22.

10. **Resolved (2026-10-01):** item 17 is split into 17a to 17d in the build
    plan; 17a and 17b shipped 2026-10-02.

11. **Resolved (2026-10-05, 20a):** item 24's team tables stay NFL-only.
    NBA needs no team ratings for 20a to 20g; opponent context comes from
    `nba_player_game_stats`. Decide again only if an NBA game-line item is
    added.

12. **NFL work reopened for items 25, 27 and 28 (decided 2026-09-19, amended
    2026-09-26 for items 27 and 28).** Items 18, 19, and 24 are complete, and
    NFL game-line modelling stays closed. Item 28 reopens game lines for one
    read-only check (does the close move toward the existing model from the
    Tuesday line); it adds no signal and changes no model. The post-hoc 2026 hypotheses in the 24b, 24c, and 24e
    archives stay recorded there only; do not propose them as build-plan items.
    Item 25 is cross-sport de-vigging surfaced through NFL. Item 27 reopens NFL
    prop modelling, because the prop model was found unvalidated and at coin-flip
    accuracy. The NFL stack stays in scope for item 17's convergence.

13. **Item 25 requires forward evidence, not a historical rerun.** The Odds API
    sells current markets only, so `nfl_player_prop_odds` begins at item 19i.
    Its initial planning read had one week and zero settled player-games;
    that is a dated observation, not a current count. 25a and 25b are complete;
    25c waits for its pre-registered forward evidence, and a failed backtest is
    a live outcome given that 19j, 19n, 24b, 24c, and 24e all failed theirs.

14. **Bankroll builder retired from the UI, still in the plan.** Build-plan item 10
    is checked as a shipped feature, but on 2026-09-25 the user retired it from
    the Tennis page and nav: it duplicated best-picks moneylines, had no
    game-spread picks, and its parlays compound an unproven edge. The backend and
    `/parlays` route remain. Decide whether the plans should record the
    retirement, or whether 26d's outcome should decide its return, singles-only. 26d has
    now decided it in effect: moneyline gaps lose at the close and moneyline
    picks are off, so the builder has nothing validated to size.

15. **Tennis grading is new scope in no plan section.** Item 26 was added to the
    build plan on 2026-09-25, and 26e and 26f on the same day, when 26b was
    split. `project-plan.md` §3 mentions neither model validation nor prop
    projection snapshots. 26f is also a schema change (a new stored snapshot)
    that §4 would need to list. Add them there if they are lasting
    capabilities. The plan's data sources table also omits Valuebetennis,
    26c's backtest-only source, and §3 does not record 26d's outcome (the
    ensemble is now market-anchored and tennis moneyline picks are off).

16. **Resolved (2026-09-30):** 26c's build-plan line drops v6 and names
    Valuebetennis.

17. **Resolved (2026-10-01):** 26c shipped on Valuebetennis data
    (tennis-data.co.uk returns 403), with the 2021 / 2022 / 2023-2025 split.

18. **Item 27 grows the parallel stack's logic more than its tables.** It
    added columns (`0036`) and put the long-unused `sport_prop_predictions` to
    work (`0037`), but no new table. Its probability function
    (`over_probability`) is sport-agnostic by design, and the ranking rule
    reads tennis's `prop_ev.py` payouts. 17a moved `nfl_prop_predictions` to
    `sport_prop_predictions`; whether tennis's `prop_projection_snapshots`
    merges with it is still open, and the 17c spec leaves it out of scope
    (tennis convergence waits for item 22).

19. **`project-plan.md` §3 does not mention item 27, the prop-line snapshot
    workflow, frozen predictions, P(over), 27k's wind test, or model validation for NFL** (as with item 26 in open question
    15). The reopening is recorded in §5 only.

20. **27e's build-plan wording describes an effect the data did not show.** The
    line says "passing volume rises when trailing". In the 2024 fit, the
    passing margin slopes were zero (attempts -0.025 +/- 0.036), and what was
    adopted was simply dropping the moneyline for passing. The archive
    (`blueprint/history/features/27e-game-environment.md`) records this; decide
    whether to reword the checked line so it matches what shipped.

21. **Resolved (2026-09-26):** 27h's build-plan line now gates on 27j's
    slice verdicts, per slice, and drops the item if all four reject.

22. **27f's and 27g's checked lines overstate what shipped.** 27f says
    "adopted only if 27b improves": the projection was rejected, and only
    settlement changed. 27g says "shown beside the edge": only 2 of 8 markets
    show, and on the evidence panel, not the signal rows. As with open question
    20, decide whether to reword the checked lines.

23. **27g's fit bends the "fitted on 2024 only" rule.** The build-plan line
    says "fitted on 2025 residuals", so the fit used 2025, cross-fitted by week
    parity. The 27g archive argues the rule protects projection verdicts, which
    27g does not take. Confirm the exception, or require a 2024 fit for any
    later distribution work.

24. **Resolved by 27j (2026-09-26):** it grades each provider prop's latest
    frozen pre-kickoff row at its own line (27j archive).

25. **`project-plan.md` §3 does not mention item 28.** Its NFL game-lines
    paragraph still describes item 24 only; the reopening for the CLV check is
    recorded in §5 alone (as with item 27 in open question 19).

26. **Item 28's checked line says "Tuesday line"; the rule grades the earliest
    in-window line.** Odds fetches ran Thursday through Wednesday in weeks 2-3,
    so the shipped rule takes the earliest line after the previous week's
    results, whatever the weekday (28 archive). Whether that is early enough
    depends on the Tuesday `nfl-ingest.yml` fetch actually running (the key is
    now confirmed, open question 6). Decide whether to reword the checked line.

27. **`project-plan.md` §3 and §7 do not mention items 29 or 30.** The NFL
    game notes panel and its team stats block are UI additions with no schema
    change. Add them to the plan's NFL features and UI/UX sections if they are
    a lasting part of the slate.

28. **Resolved (2026-09-30):** the NFL prop edge goes gray until 27h adopts a
    slice (`project-plan.md` §7); 33b shipped it on the slate and prop board.

29. **Resolved (2026-09-28):** 31b dropped the mockup's quarter-Kelly suggested
    stake, in line with the bankroll builder's retirement (open question 14).
    `prototypes/` has since been discarded.

30. **Three rolling-stat columns are misnamed.** In `player_rolling_stats`,
    `aces_per_game` and `df_per_game` hold aces and double faults **per serve
    point**, and `break_pct` holds **break points converted**
    (`app/ingest/player_stats.py`). The UI now labels them Ace rate, DF rate
    and BP converted (fix `blueprint/history/fixes/serve-stat-labels.md`), but
    the columns, the `PlayerFormStats` fields and any code reading them keep
    the misleading names. Rename them in item 17 or a migration, not silently.

31. **Plan item 7 still describes the retired modal.** Build-plan item 7 and
    `project-plan.md` §3 (now corrected) mentioned "player comparison"; the
    modal was deleted in 32a and replaced by the match page. Item 7's checked
    line can stay as history.

32. **16f is parked, not dropped.** Its build-plan line stays unchecked with a
    parking note, and item 16 therefore stays open. Decide whether to drop 16f
    from the plan or keep it waiting on the provider.

33. **The Bet365 parser misfiles game handicaps as `set_handicap`.**
    `_parse_bet365_spread` keeps the first `odds` entry of any market named
    like a set handicap, and best-of-3 rows at +/-2.5 and +/-3.5 show it has
    stored game lines there (found in 16f). Only the retired bankroll builder
    reads these rows today. Fix it through `/fix` before anything prices set
    handicaps.

34. **The tennis tier rule lives in code and the 32b archive only.**
    `project-plan.md` §3 and §7 mention the track record page but not the
    pre-registered tier verdict (`app/core/track_record.py`), as with NFL's 27i
    rule (open question 19). Add it to the plan if it is a lasting commitment.

35. **`project-plan.md` §3 does not mention item 33.** Only §7 records its
    rules (gray NFL edge, 11px floor). Item 33 is complete: the game-first
    slate and the game, player and model pages are new NFL surfaces, as items
    29 and 30 were (open question 27). §3's "Match intelligence" list names the
    tennis pages (item 32) but no NFL ones. Add them if they are a lasting part
    of the NFL experience.

36. **`project-plan.md` §7 still names `prototypes/theme.css`** as the theme's
    source. The folder was discarded at 33d's `/complete`; the tokens live only
    in `web/src/index.css`. Harmless as history, but a later `/prototype` run
    would start from the app stylesheet, not that file.

37. **`project-plan.md` §4 still says "NFL is deliberately parallel until
    item 17"** and describes normalized `nfl_*` tables. 17a and 17b moved the
    seven cross-sport ones to `sport_*`; the stat and context tables stay
    `nfl_*`. Refresh that paragraph so the plan matches the shared schema.

38. **Build-plan item 8 reads "ranks +EV plays out of the ensemble"**, but
    tennis moneyline picks have been off since the 26d follow-up fix
    (2026-10-01). Decide whether the plans should record that moneyline picks
    stay off until a later model beats the close, and what would re-enable them.

39. **`player_match_stats_pre_0038` is still in the database.** The 0038 fix
    left the snapshot for its downgrade and asked for a later migration to drop
    it once the fix had settled. No build-plan item or fix spec owns that yet.

40. **`get_slate_lines` stalls intermittently, on master as well as 17b's
    branch** (17b archive): 2 of 5 branch runs and 1 of 5 master runs spent
    33-99 s per call, up to 240 s. Outputs stayed identical. The NFL model
    page's 27a request has a 90 s timeout, so a stall can fail it. A `/debug`
    (compare `EXPLAIN ANALYZE` of a slow and a fast run) was recommended and
    has not run. 17c's timing check hit it on both master and the branch
    (freeze dry runs from 8 s up to 90 s with identical output).

41. **`nfl-scores.yml` and `nfl-weather.yml` are not in the plan's deployment
    notes.** Both are daily GitHub Actions crons against the shared database
    (the scores one added by fix 2026-10-02). Add them to `project-plan.md` §8
    if the plan's cron list is meant to be complete.

42. **Resolved (2026-10-15):** My Bets was removed (fix `remove-my-bets`), and
    the plans now say predictions are graded in the app and placed bets are
    tracked in Pikkit. Build-plan item 11 stays checked, with a removal note.
    The `bets` table remains until a later migration drops it; no build-plan
    item or fix spec owns that yet.

43. **`project-plan.md` §3 and §7 do not mention the NBA slate or game page.**
    Item 20e is complete: `/nba` and `/nba/game/:gameId` are display-only NBA
    surfaces under the same gray-signal and 11px rules as NFL (as open
    question 35 found for item 33's NFL pages). Add them if they are a lasting
    part of the NBA experience. The open in-play odds
    question (whether `nba_odds` stores rows after tip-off) is checkable once
    games start on 2026-10-20. The NBA prop board the 20g split left out is
    now build-plan item 42 (added 2026-10-21).

44. **Resolved (2026-10-07):** the two gaps had separate causes.
    - **NFL:** the 2026-10-06 `nfl-ingest.yml` run failed at its first step
      on a transient NFLverse 404 (NFLverse re-uploads a release asset by
      deleting it first), so every later step, the odds included, was
      skipped. Fix `blueprint/history/fixes/nflverse-download-retry.md`
      retries every NFLverse download (404, 5xx, transport errors; 4
      attempts, about 70 s). Week 4's team ELO, efficiency, snap counts and
      US and Pinnacle game odds stay missing until `nfl-ingest.yml` is
      dispatched on master; a re-run of the failed run uses the old commit.
    - **NBA:** not a fault. `nba-odds.yml` runs with `--days-ahead 2` and
      only `REG`, `PIN` or `PST` games count, so no scheduled run calls the
      provider before 2026-10-18 (the season opens 2026-10-20). The only NBA
      rows are 20d's local first run.
    - **Not the cause:** secrets, the database URL and the credit floor
      (449 of 500 credits left on 2026-10-07).

45. **`project-plan.md` §3 does not mention item 36** or the line-shopping
    purpose behind it; only §4's data sources record the new provider roles
    (as open questions 27, 35 and 43 found for other display items). It also
    names no prop-comparison item yet: the owner wants PrizePicks lines
    compared with Bet365 and DraftKings player props next, and Odds-API.io's
    free plan returns those props in the same request 36a uses.

46. **Resolved (2026-10-15):** the public demo is build-plan item 37, and
    `project-plan.md` §2 and §8 now record the owner-only login, the Neon
    database and Render as the host.

47. **Resolved (2026-10-16, 37e):** the owner rotated the Neon password and
    the Odds-API.io key, and updated Render, the GitHub secrets, `.env` and
    the local MCP settings before the code went public.

48. **Resolved (2026-10-16):** `project-plan.md` §8 now records CI and the
    secret scan, which run green on the public repo.

49. **`project-plan.md` records the Lineform rename and item 38 only in its
    header line and §7.** §3 could name the completed shared shell, table-first
    slates and prop tables. Render's `sportapp-api` and `sportapp-web` names
    are intentionally unchanged; they are not an incomplete rename.

50. **Resolved (2026-10-18):** all of item 38 is checked off, including
    38d2, 38d3, 38e and 38f. Project-plan §7's completed-redesign description
    now agrees with the build plan. Implementation completion is separate
    from verifying the latest Render deployment.

51. **Remaining planning gaps, refreshed 2026-10-21:** the NBA prop board
    API/page (42a/42b) are complete; `project-plan.md` §3 does not name them, as
    question 43 found for the other NBA pages. WNBA/soccer schedule and stats providers are intentionally undecided.
    Project-plan §2 still calls the demo planned while §8 and item 37 say
    it is live; §4 says model files are ignored while §8 says they are tracked.
    These prose gaps do not change the next feature's build order.

52. **`project-plan.md` §3 does not mention item 39** (as open questions 27,
    35, 43 and 45 found for other NFL items). It adds a modelled market under
    rules the plan already states, so no plan edit was proposed. Its one new
    commitment, grading a market under its own model version so 27j runs
    per version, is recorded in the build-plan line and above.

53. **Item 39 is complete without a served P(over).** Its build-plan line
    makes probability conditional, and 39b's check hid it. 39c serves/freezes
    null-probability reference rows; completed 39d settles and reports them
    separately. Coverage and settled calls can grow while probability picks
    stay zero. A different probability method is new, separately reviewed
    work, with no historical holdout reuse or implied approval in this refresh.

54. **Build-plan item 3 still reads "weekly refresh"** for ELO. Since fix
    `elo-refresh-local` it runs daily on the local scheduled task. The
    checked line can stay as history; reword it if the plan should match.

55. **`project-plan.md` §3 does not mention item 40** (as question 15 found
    for item 26). The build plan now records 40a's keep-pooled verdict and
    40b's explicit cancellation. Its checked status means the investigation
    is complete, not that a new WTA 125 serving group shipped.

56. **The checked item 35 still describes nine line-only markets.** That is
    its original scope; 39c promotes Rec Targets and leaves eight. New
    specifications must distinguish the ten-market serving universe from
    the nine-market v4 projection and grading subset.

57. **Item 41's deployment boundary remains explicit.** The project plan now
    records the implemented second box-score source. 41a's local code and
    shared-database backfill are verified; first runner acceptance and
    deployment of this code have not been verified by this refresh. 41b is
    engineered and in shadow with the same runner/deployment boundary; 41c
    remains conditional, and no ELO serving change follows from either.

58. **42a-42d are complete locally.** The build plan checks off the board
    API/page, injuries and team stats. Their completed archives supersede the
    previous overview's planned status; hosted deployment remains unverified. Their archives
    and local browser evidence establish parity and UI behavior, not hosted
    deployment or Render memory acceptance. The existing 4.88 MB daily
    response is a recorded operational follow-up; do not describe it as a
    few-hundred-line payload or add a new heavy request-time report.

59. **Tennis workflow operations changed after the previous overview.**
    The old combined-workflow description is superseded by the six files
    documented above and in `docs/tennis-actions.md`. The split preserves
    commands, quota usage and ELO safeguards. This overview does not verify
    workflow registration, successful runner execution or current experiment
    counts; retain those post-publication checks separately.

60. **Features 43 and 44 are recorded in the build plan, not project-plan
    section 3.** Both are incremental (43 display, 44 a probability method
    under existing gates) and change no product direction, user, provider,
    stack or deployment commitment. 43 is complete with aDOT unavailable.

61. **Resolved (2026-10-23):** NHL is build-plan item 45 (45a-45f), placed
    before WNBA, with project-plan §1, §3, §4 and §5 updated. 45a settled
    the budget question by moving NHL odds to Odds-API.io.

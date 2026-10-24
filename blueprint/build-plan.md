# Build Plan

> Adopted from an existing codebase via `/adopt`. Items 1-12 are already shipped
> and are checked off to reflect reality. Items 13 and up are the roadmap from the
> adoption interview. Run `/feature` with no argument to spec the next unchecked
> item, or `/feature 15` to pick a specific one.

Do not renumber completed items; archived specs refer back to these numbers.

## Shipped (adopted, not built through the Blueprint loop)

These were built before the Blueprint was adopted, so they have no archived specs
under `blueprint/history/`. They are checked because the functionality exists and
works, not because the loop produced them.

- [x] 1. **Match ingest** - pull ATP and WTA matches from livetennisapi with a today plus tomorrow window
- [x] 2. **Player identity resolution** - alias table and slug columns reconciling player names across four data sources
- [x] 3. **ELO ratings** - ingest overall and surface ELO from TennisAbstract, with weekly refresh
- [x] 4. **Rolling player stats** - serve and return form over rolling windows, with surface and contextual splits
- [x] 5. **Odds ingest** - book odds from The Odds API, timestamped so staleness can be detected
- [x] 6. **Model ensemble** - blend ELO, LightGBM, and de-vigged market probability with tour-specific weights and quality flags
- [x] 7. **Match predictions UI** - daily slate with win probabilities, H2H, and player comparison
- [x] 8. **Best picks** - rank +EV plays out of the ensemble output
- [x] 9. **Props pipeline** - PrizePicks and DraftKings ingest, projection, EV scoring, and an audit view
- [x] 10. **Bankroll builder** - Kelly-based stake sizing and parlay suggestions
- [x] 11. **Bet tracking** - record, list, settle, and delete bets with a daily summary. *Removed 2026-10-15:* bets are tracked in Pikkit; page and API deleted, `bets` table kept until a later migration drops it
- [x] 12. **Admin surface** - flagged players with manual stat and ELO refresh, behind a shared API key

## Next

- [x] 13. **Declare test dependencies** - add `pytest` and any test-only packages to `api/requirements.txt`, since the suite currently runs only from an undeclared local `.venv` and would fail in CI
- [x] 14. **Clean up one-off scripts** - remove or relocate the ad-hoc `check_*.py`, `fix_*.py`, `diagnose_*.py`, and `find_dupes.py` files in `api/`, plus the `tmp_ta_zverev.*` files at the repo root
- [x] 15. **Prediction accuracy pass** - improve calibration and feature quality for the tennis ensemble, measured against held-out results rather than by eye
- [ ] 16. **Props coverage expansion** - add prop markets and books beyond PrizePicks and DraftKings, and tighten projection accuracy
  - [x] 16a. **Projection tightening** - use opponent double-fault pressure and match-closeness-aware total-games probabilities
  - [x] 16b. **Odds free-tier rate-budget hardening** - reduce scheduled odds request volume and stop early when provider quota is low
  - [x] 16c. **Odds market inventory and book-config refactor** - record every bookmaker and market Odds-API.io returns on the current tier, and replace the duplicated per-book parse blocks with one config table
  - [x] 16d. **Provider compatibility and dynamic Live Odds** - use one bounded provider-compatibility probe to identify the supported tennis book scope, then render Live Odds columns from the books actually returned. *Live Odds page and endpoint removed 2026-10-15*
  - [x] 16e. **Prop stat expansion** - add additional tennis prop stat types when the source payloads and projections support them
  - [ ] 16f. **Set-handicap projection** - model and evaluate tennis set-handicap lines only after provider-supported line shapes are captured. *Parked 2026-09-29:* only 48 `set_handicap` rows exist (31 matches, 2026-08-24 to 09-25, none since the Bet365 rename), 29% of best-of-3 rows are +/-2.5 or +/-3.5 game lines the parser misfiled, and 27 settled matches have a pre-start line; revisit only if the provider starts offering set handicaps regularly
- [x] 26. **Tennis model validation** - grade stored predictions and picks against results and closing prices, then test and refit the ensemble against the market, adopting a change only when a held-out check passes
  - [x] 26a. **Prediction grading and CLV** - score each stored prediction's ELO, LightGBM, market, and ensemble probabilities against settled results (log loss, Brier, calibration, by tour), and measure whether the closing de-vigged moneyline moved toward the model; read-only report, no model change
  - [x] 26b. **PrizePicks line settlement** - measure how often props link to a match and a box score, then settle the score-derivable lines (total games, games won, sets, tie breaks, first-set games) against final scores and report over, under and push rates by stat and odds type; read-only, no schema change
  - [x] 26c. **Historical closing-line backtest** - import Valuebetennis results with Pinnacle opening and closing odds (2021 onward; tennis-data.co.uk now blocks downloads), and score computed ELO and the hand-set ELO-plus-market blend against the closing line on a pre-registered holdout (v6 cannot be scored historically: its training covers all stored history)
  - [x] 26d. **Market-anchored ensemble** - replace hand-set weights with a fitted log-odds blend on the market, adopted only if 26a and 26c pass a pre-registered rule
  - [x] 26e. **Box-score join key** - store opponent and round on `player_match_stats` so aces, double-fault and break-point props join to exactly one box score, then settle those stats through 26b's report
  - [x] 26f. **Prop projection snapshots** - store the projection, hit probability and confidence tier when a prop is fetched, so calibration by tier is graded forward on pre-match predictions only
- [x] 40. **WTA 125 blend group** - test whether verified WTA 125 matches (stored as `CHALLENGER`) are better served by their own fit group or by the WTA coefficients than by 26d's pooled Challenger blend: candidates fitted on 2022 Valuebetennis only, compared under a rule pre-registered before any scored row is read, scored once on 2026 onward (2023-2025 is already read twice, so it is no fresh verdict); serve a change only on a pass, else keep the pooled group
  - [x] 40a. **WTA 125 blend backtest** - re-download Valuebetennis, identify WTA 125 events within its women's `Challenger` category using a frozen tournament-and-season crosswalk verified against official WTA metadata (the category also includes ITF), count cases per season, pre-register the comparison rule, then fit candidates on 2022 and score once on 2026 (pooled Challenger, WTA coefficients, a 125-only fit); report only, no production change, and stop as accruing before scoring if 2026 is too thin. Local result 2026-10-19: keep pooled on 970 cases; A and B failed G1 and passed G2. Completed 2026-10-19; archived at `blueprint/history/features/40a-wta125-blend-backtest.md`.
  - [x] 40b. **Serve the WTA 125 group** - **dropped, not implemented, by 40a's 2026-10-19 verdict**: neither candidate cleared G1 on 970 cases, so keep the pooled Challenger coefficients. No routing, model version or `SPORT_STATUS` change. Original conditional scope was to route women's Challenger draws in `fitted_group` (by the player-tour rule `display_tour` uses) to winning coefficients only if 40a passed.
- [ ] 41. **TennisMyLife match data** - add TennisMyLife's free daily match CSVs (ATP, Challenger, ATP qualifying and WTA tour; MIT license; no WTA 125 or ITF) as a second tennis box-score source and the basis for an in-house ELO; TennisAbstract stays for WTA 125 and the rolling stats, and any change to what the ensemble or prop projections read is adopted only on a pre-registered check
  - [x] 41a. **Box-score ingest** - store TennisMyLife box scores in `player_match_stats` under source `tennismylife`, with a daily GitHub Actions job; match and player displays fill gaps only when TennisAbstract lacks stats, while grading remains TennisAbstract-only; no projection, rolling-stat or model change. Completed locally 2026-10-20: 22,789 rows backfilled, repeat added no duplicates; GitHub runner verification pending a separately approved push. Archive: `blueprint/history/features/41a-tennismylife-box-score-ingest.md`.
  - [x] 41b. **In-house ELO** - overall and surface ELO computed from TennisMyLife history by 26c's method, stored beside TennisAbstract's under its own source, and compared read-only under a rule pre-registered before any 2026 forward case is scored; no serving change. Engineering completed locally 2026-10-21 UTC; shadow activated, first eligible UTC day 2026-10-22. Forward verdict accruing with zero observations; first real freeze and post-push runner acceptance pending. Archive: `blueprint/history/features/41b-tennis-inhouse-elo.md`.
  - [ ] 41c. **Serve in-house ELO** - conditional on 41b passing: the ensemble reads the in-house ELO under a new model version, and the local `Lineform ingest_daily` ELO step is retired; dropped if 41b fails
## Sports expansion

- [x] 17. **Multi-sport foundation** - generalize the tennis-shaped API, schema, and services so other sports share the ensemble, odds, props, and bets machinery
  - [x] 17a. **Shared team-sport tables** - move the NFL teams, players, aliases, games, prop lines, game odds and prop predictions into sport-keyed `sport_*` tables, leaving the `nfl_*` names as compatibility views so NFL code runs unchanged
  - [x] 17b. **NFL on the shared tables** - point NFL repositories, ingest, backtests and tests at the `sport_*` tables, scope unique keys by sport, drop the views, and prove the NFL reports unchanged
  - [x] 17c. **Sport-agnostic prop pipeline** - PrizePicks league selection per sport, and frozen predictions, ranking rule, forward check and track-record loaders parameterized by sport and market, so a new sport supplies only a projection
  - [x] 17d. **Sport-aware web shell and prop registry** - a sport registry driving the web routes and the Slate / Props / Model nav, and an API registry mapping a sport code to its prop pipeline source; `bets.sport` dropped 2026-10-05 (bets are tracked in Pikkit); tennis `matches` convergence stays out of item 17 (revisit with item 22)
- [x] 18. **NFL data sourcing** - evaluate and pick free schedule and stats sources for NFL, then document the choice before any ingest is written
- [x] 19. **NFL support** - ingest, model, and surface NFL matchups
  - [x] 19a. **NFL schedule and stats ingest** - NFLverse teams, players, games, and weekly player stats
  - [x] 19b. **NFL baselines and prop-line board** - historical player baselines plus PrizePicks prop-line snapshots
  - [x] 19c. **Prop-line player linking and unified slate** - resolve provider player names to `nfl_players`, compute edge, and merge the two NFL pages into one
  - [x] 19d. **Current-season NFL data** - load 2025 and 2026 so baselines and rosters match the live prop lines
  - [x] 19f. **NFL book odds ingest** - game-level moneyline, spread, and total from the existing odds provider, de-vigged into a market probability
  - [x] 19e. **NFL projection model** - replace naive per-player averages with a real model, using the market probability from 19f
  - [x] 19g. **Opponent-adjusted NFL prop projections** - use pre-game, defense-versus-position historical allowances to apply bounded matchup adjustments with sample and freshness safeguards
  - [x] 19h. **NFL player usage inputs** - store NFLverse targets and other available volume signals, then use them in player prop projections
  - [x] 19i. **NFL sportsbook anytime TD odds** - ingest `player_anytime_td` prices from The Odds API per game under a credit safety floor, turn Yes-only prices into a market probability, and compare it to the anytime-TD baseline on the NFL slate
  - [x] 19j. **NFL red-zone usage for anytime TD** - aggregate NFLverse play-by-play to per-player, per-game carries and targets inside the 20 and inside the 5, store only those counts, and use them in the anytime-TD projection only if the 2024-2025 backtest improves
  - [x] 19k. **NFL weekly rosters** - store each player's team for each week so baselines and matchups stop using the most recent team for past games
  - [x] 19l. **NFL injuries and depth charts** - ingest injury status and depth-chart order on a pre-game schedule, and surface role changes on the slate before any model use
  - [x] 19m. **NFL snap counts** - store snap share and test it as an RB and TE role signal against the backtest
  - [x] 19n. **NFL scoring environment for anytime TD** - test implied team totals from historical and live game lines, then separately test WR/TE end-zone targets; adopt either signal only when its held-out backtest passes
- [x] 24. **NFL game-line model** - predict spread, moneyline, and total for NFL games from team strength and game context, adopting each signal only when a held-out backtest against closing lines passes
  - [x] 24a. **Team ELO ratings** - margin-aware team ELO computed pre-game from historical NFLverse scores, stored per team per week
  - [x] 24b. **Game-line backtest** - score ELO-derived spread, win probability, and total against closing lines and results on a held-out season, with a pre-registered adoption rule
  - [x] 24c. **Team efficiency ratings** - per-team, per-game EPA per play, success rate, and pace aggregated from NFLverse play-by-play for 2012-2026, tested through the 24b backtest as spread and total inputs
  - [x] 24e. **Totals context** - NFLverse game temperature and wind, plus the stored roof and rest, tested through the 24b backtest for totals (rest also for spread); built before 24c
  - [x] 24d. **Game-line slate** - model spread, win probability, and total beside the market on the NFL slate, display-only unless 24b/24c adopt it
- [x] 28. **NFL game-line CLV check** - grade the pinned `nfl-elo-v1` spread and `NFL_SCORING_V1` total against the stored pre-kickoff Tuesday line, and measure whether the closing line moves toward the model under a pre-registered rule; read-only report, forward from 2026, no model or schema change
- [x] 29. **NFL game notes** - a per-game panel on the NFL slate with both teams' skill-position injury report, depth-chart changes, spread and total movement from one book (earliest to latest pre-kickoff), and each team's last three results, rest days and short-week tag; display only, never changes an edge or rank, no schema change
- [x] 30. **NFL team stats in game notes** - a team stats block in each game's notes panel showing both teams' season-to-date offense (points, pass yards, rush yards, plays, EPA per play, success rate per game) and the same stats allowed on defense, each with a league rank, built from stored scores, weekly stats and team-game efficiency; display only, never changes an edge or rank, no schema change
- [x] 43. **NFL matchup and usage context** - extend game notes with season-to-date production allowed by position and league ranks, plus player target and carry shares; show relevant opponent context and last-three-games versus season usage in the existing prop evidence drawer, with samples and date windows. Display only; preserve projections, probabilities, ordering and signal colors. Add aDOT only after verifying and storing the required air-yard totals.
- [x] 31. **Web redesign** - restyle the web app from the `prototypes/` mockups (OddsJam tables, Outlier prop cards, Robinhood numbers): true-black theme with one green signal color, restyle only, never changing which numbers are colored, sorted, ranked, or shown
  - [x] 31a. **Theme and app shell** - port `prototypes/theme.css` into `web/src/index.css` and the Ant Design theme, and restyle the nav and page header, so every page takes the new palette with no layout change
  - [x] 31b. **Tennis slate** - summary strip, best-pick cards, and the match table grouped by tournament, per `prototypes/tennis-slate.html`
  - [x] 31c. **Tennis prop board** - prop cards with hit probability against the payout break-even, recent-match bars, and hit rates, per `prototypes/tennis-props.html`
  - [x] 31d. **NFL prop board** - prop cards with last-games bars and hit rates, keeping every NFL display rule, per `prototypes/nfl-prop-board.html`
  - [x] 31e. **NFL prop detail** - the evidence panel restyled as a detail view (projection breakdown, game log, lines, game market), per `prototypes/prop-detail.html`
- [x] 32. **Tennis detail pages** - give matches, players, and the model's graded record their own linkable pages, per `prototypes/tennis-match.html`, `tennis-model.html`, and `tennis-player.html`; display only, never changes a probability, edge, rank, or pick
  - [x] 32a. **Match detail page** - `/tennis/match/:id` replacing the player comparison modal: ensemble, market and edge, component probabilities with weights and flags, per-book moneyline and total movement from `match_odds`, H2H, recent form with box scores, serve and return side by side, and the match's prop lines; slate rows and pick cards link to it
  - [x] 32b. **Model track record page** - `/tennis/model` serving the 26a, 26b and 26f grading as read-only endpoints: log loss and Brier by component and tour against the market, calibration, closing-line value, PrizePicks over rates against break-even, and hit rate by confidence tier; neutral colors unless a number beats its stated baseline or break-even by more than 2 SE, and any tier verdict sample is pre-registered before tier data is read
  - [x] 32c. **Player page** - `/tennis/player/:id`: ELO trend overall and by surface, rolling serve and return stats by surface against the tour average, match log with box scores, record splits, and settled past props; linked from the match page and slate
- [x] 33. **NFL redesign and detail pages** - a game-first NFL slate and linkable game, player, and model track record pages, per `prototypes/nfl-slate.html`, `nfl-game.html`, `nfl-player.html`, and `nfl-model.html`; display only, never changes a projection, edge, rank, or pick; NFL prop edges lose the green signal color until 27h adopts a slice; no UI text below 11px
  - [x] 33a. **Game page** - `/nfl/game/:id`: market beside the muted model (spread, win probability, total), spread and total movement from `nfl_game_odds`, injuries, depth changes, form and rest, team stats, and the game's props as prop-board cards; absorbs the slate's matchup bar, model strip, and notes panel
  - [x] 33b. **Game-first slate** - `/nfl` becomes a summary strip and one card per game grouped by kickoff window (market, muted model, conditions, injury counts, line movement, top three props by edge), each linking to the game page; the signal boards and inline evidence panel leave the slate; NFL edges turn gray on the slate and prop board
  - [x] 33c. **Player page** - `/nfl/player/:id`: weekly carries, targets, and snap share, this week's lines, a game log with the stored line per game, past PrizePicks hit counts against break-even (anecdote, never colored), and record splits; linked from prop cards and the game page
  - [x] 33d. **Model track record page** - `/nfl/model`, a third Slate / Props / Model view serving the 27a line grading, 27j slice progress, 28 game-line CLV, and 27g P(over) calibration as read-only endpoints built from the CLIs' own pure pieces; gray unless a rate clears or falls short of its baseline by more than 2 SE
- [ ] 25. **Market-relative prop rating** - de-vig Yes-only sportsbook prop prices into a normalized market probability, accrue a forward holdout, and rate props against the market only once a backtest passes
  - [x] 25a. **Yes-only de-vig** - per-game normalization of the book consensus as a pure `app/core/` function, unit-tested, surfaced on the slate beside the raw price
  - [x] 25b. **Forward holdout accrual** - settle stored prop prices against results each week and report the accumulating sample, with no model change
  - [ ] 25c. **Adopt in prop rating** - rate anytime TD against the normalized probability instead of the 0.5 line, only if 25b's backtest passes a pre-registered rule
- [ ] 27. **NFL prop probability model** - grade the PrizePicks prop model against real lines, test each projection input on held-out results, and rate lines by over probability against the payout break-even, adopting each change only when a pre-registered check passes
  - [x] 27a. **PrizePicks line grading** - settle stored pre-kickoff NFL PrizePicks lines against weekly stats and report over/under rates and the current model's hit rate by market, odds type, and edge size against the 57.7% Power break-even; read-only, no model change
  - [x] 27b. **Projection backtest harness** - replay 2025 week by week with pre-kickoff inputs only (including moneylines fetched before kickoff) and score each market's projection error, as the gate every input change passes; re-test the usage adjustment (finding F-02) through it
  - [x] 27c. **Matchup by team-game** - rebuild defense-versus-position from per-game position totals over recent seasons with real game counts, adopted only if 27b improves
  - [x] 27d. **Season blending** - replace the four-game season switch with games-weighted blending of the current and previous season, adopted only if 27b improves
  - [x] 27e. **Game environment** - replace moneyline scaling with implied team totals and a per-market direction (passing volume rises when trailing), adopted only if 27b improves
  - [x] 27f. **PrizePicks fantasy scoring** - compute fantasy points from components with PrizePicks' formula instead of NFLverse PPR, adopted only if 27b improves
  - [x] 27g. **Over probability** - per-market outcome distributions fitted on 2025 residuals turn a projection into P(over line), calibrated on held-out weeks and shown beside the edge; display only
  - [x] 27i. **Frozen line predictions** - store each pre-kickoff NFL line's projection, edge, P(over) and model versions in `nfl_prop_predictions` on the line-snapshot schedule, and fix the ranking rule as tested constants before any frozen week exists; no report, no ranking change
  - [x] 27j. **Forward ranking check** - settle frozen predictions weekly and apply 27i's rule per payout (standard, goblin, demon break-even), reporting the running sample and the one-time verdict; read-only
  - [x] 27k. **Wind for passing props** - a per-market wind slope for passing attempts, completions and yards, fitted on 2024 outdoor games and judged on 2025 through the 27b harness, adopted only if 27b improves; live projections read the pre-game forecast, never observed wind
  - [ ] 27h. **Adopt in ranking** - rank and pick lines by P(over) against each payout's break-even, only for the slices (standard over, standard under, goblin over, demon over) whose 27j verdict reads `adopt` under 27i's rule; blocked until one does, dropped if all four reject
- [x] 34. **More NFL prop lines** - store PrizePicks NFL lines for markets the model does not project, so line history accrues before any projection exists; stored lines stay out of the slate, frozen predictions, 27a grading and 27j until a later item projects a market
  - [x] 34a. **Settleable stat lines** - store Rec Targets, Pass TDs, INT, Rush+Rec Yds, Pass+Rush Yds and Pass+Rush+Rec TDs, each settleable from stored weekly stats, with every projection reader limited to the modelled markets
  - [x] 34b. **Kicking and punting lines** - store FG Made, Kicking Points and Punts lines, plus the per-game kicking and punting stats that settle them, from NFLverse
- [x] 35. **Line-only prop display** - show all 9 line-only NFL markets (Rec Targets, Pass TDs, INT, Rush+Rec Yds, Pass+Rush Yds, Pass+Rush+Rec TDs, FG Made, Kicking Points, Punts) on the game page, in a gray section beside the modelled props: each player's current PrizePicks lines (line and payout type) and their last games of that stat from stored weekly stats, served by a sibling `/nfl/games/{id}/line-only-props` endpoint; never a projection, edge, rank, P(over) or signal color, and never part of `/nfl/slate`
- [x] 36. **NFL best line** - each side's best price per game across Bet365, DraftKings and the other stored US books, beside a Pinnacle de-vigged fair price, as a line-shopping reference; display only, never a pick, edge or signal color
  - [x] 36a. **Bet365 and DraftKings NFL odds from Odds-API.io, plus Pinnacle** - moneyline, main spread and main total from Odds-API.io's two allowed books into `sport_game_odds` with a new `provider` column, refreshed several times a day within the shared hourly quota; add The Odds API `eu` region to the existing NFL odds run for Pinnacle (about 3 credits a run); every existing reader (slate market, line movement, item 28 CLV) stays on The Odds API `us` rows
  - [x] 36b. **Best line and fair price display** - per game, each side's best price across Bet365, DraftKings and the stored US books, naming the book and its fetch age, beside the Pinnacle fair price (low-vig consensus when Pinnacle is missing), on the game page and slate card
- [x] 39. **NFL Rec Targets projection** - project PrizePicks Rec Targets lines (standard only), with candidate baselines chosen on 2024 alone, and a P(over) shown only if a fit on 2024 passes 27g's display rule on one 2025 check; freeze predictions on the line-snapshot schedule under their own model and P(over) versions, so 27j grades Rec Targets as a separate sample and the running `opponent-dvp-tg-blend-usage-snap-v4` sample is untouched; gap gray and never a pick until its own 27j slice reads `adopt`
  - [x] 39a. **Rec Targets baseline on 2024** - a pure Rec Targets projection with a pre-registered arm order (season-average reference, then moneyline scaling, then recent form), replayed on 2024 only from the slate's pre-week inputs and chosen under 27b's adoption rule, versioned `nfl-targets-v1`; backtest only, no production change
  - [x] 39b. **Rec Targets over probability** - a P(over) distribution for `nfl-targets-v1` fitted on 2024 and shown only if one 2025 check passes 27g's display rule (the 2025 holdout's eighth read); a frozen fit table, no production change
  - [x] 39c. **Serve and freeze Rec Targets** - Rec Targets lines projected on the slate, prop board, game and player pages under `nfl-targets-v1` and its P(over) version, gray, and frozen after each line snapshot; the nine v4 markets, their versions and their 27j sample unchanged
  - [x] 39d. **Rec Targets in the forward check** - 27j grades each model version as its own sample, and `/nfl/model` shows the Rec Targets slices beside the v4 ones, gray until decided

## Portfolio demo

- [x] 37. **Public read-only demo** - publish the app as a hosted, read-only portfolio demo: anonymous visitors browse every sport page, only the owner can reach the admin surface, and the code is public
  - [x] 37a. **Admin-only login** - one owner credential signs in on the web, and the Admin page sends it, so admin routes work with `ADMIN_API_KEY` set; no sign-up, no other accounts, no per-user data
  - [x] 37b. **How it works page** - a public page explaining the pipeline, the models, and what validation found (which outputs are picks and which are reference only), linked from the nav
  - [x] 37c. **CI and secret scanning** - one Verify command and GitHub checks on pull requests and pushes (via `/ci`), plus a secret scan that fails a push carrying a credential
  - [x] 37d. **Deploy to Render** - API, web and scheduled-job wiring on Render against the existing Neon database, with production settings, model artifacts, `--proxy-headers`, and a smoke test (via `/release render`)
  - [x] 37e. **Public repo and README** - a fresh public snapshot with no private history, and a README covering what the app does, how to run it, and the live demo link
- [x] 20. **NBA support** - ingest, model, and surface NBA, reusing the NFL team-sport patterns
  - [x] 20a. **NBA data sourcing** - evaluate free schedule, box-score, and injury sources, probe PrizePicks' NBA league and The Odds API `basketball_nba` credit cost, define NBA's prop period, and decide whether NBA reuses the NFL team tables; document the choice before any ingest is written
  - [x] 20b. **NBA schedule and box-score ingest** - seed `nba` in `sports`; teams, players and games into the `sport_*` tables; per-game player box scores in an NBA stat table; 2025-26 backfill plus a daily refresh
  - [x] 20c. **NBA prop lines** - PrizePicks NBA lines through the shared 17c pipeline, stored and linked to players and games, every market line-only until a projection exists
  - [x] 20d. **NBA game odds** - moneyline, spread, and total from The Odds API into `sport_game_odds`, de-vigged, under the shared free-plan credit budget
  - [x] 20e. **NBA slate and game page** - NBA entries in the web sport registries; a game-first slate and game page with the market and line-only prop cards; no projection, edge, or signal color
    - [x] 20e1. **NBA game API** - an `/nba` router serving a slate by Eastern date (games, scores, the latest market with DraftKings preferred and de-vigged, prop line counts), a game endpoint with spread and total line history, and a line-only props endpoint with each player's last 5 values
    - [x] 20e2. **NBA slate page** - NBA in the web sport registries with a Slate view only (Props becomes optional per sport until 20g), and `/nba` as a one-day, game-first slate of cards with the market, line movement, prop counts and final scores
    - [x] 20e3. **NBA game page** - `/nba/game/:gameId` with the hero, market block (no model strip), spread and total movement, and gray line-only prop cards
  - [x] 20f. **NBA projection backtest harness** - replay 2025-26 game by game with pre-tip inputs only and score each market's projection error, with a pre-registered adoption rule fixed before any variant is scored
  - [x] 20g. **NBA projection and frozen predictions** - a baseline projection passing 20f, frozen pre-tip predictions, the forward ranking check and a model page through the shared pipeline; edges stay gray until a slice verdict reads `adopt`
    - [x] 20g1. **NBA over-probability fit** - turn the reference projection into P(over) per market with a distribution fitted on 2024-25 and checked once on the 2025-26 holdout under a pre-registered calibration rule; a CLI and a frozen fit table, nothing served
    - [x] 20g2. **NBA projection on the game page** - `NbaPropMarket` and a modelled-market filter; game-page cards show the reference projection and P(over) for markets that passed 20g1, edges gray
    - [x] 20g3. **Frozen NBA predictions** - `NbaPropSource` implements the full `SportPropSource` and joins `PROP_SOURCES`; `nba-prop-lines.yml` freezes predictions after each snapshot
    - [x] 20g4. **NBA ranking check and model page** - the forward ranking check for NBA through the shared pipeline (CLI and workflow Summary), and `/nba/model` with slice progress and verdicts, gray until decided
- [x] 42. **NBA prop board** - an NBA Props view at `/nba/board`: every linked full-game line for one Eastern date in one market, as dense rows (player, game, tip time, line, reference projection, gap, P(over) for assists, last-5 mini bars, flags) with the game page's evidence drawer; values read from the same assembly as `/nba/games/{id}/props` so board and game page never disagree; ordered by tip time then player, gray, unranked and never sorted by gap or P(over) (20g2); line-only markets as plain rows; then injuries and team stats as display context on the board and game page; never a projection, gap, sort or pick change
  - [x] 42a. **NBA prop board API** - `GET /nba/props?date=` returning one Eastern date's games with each game's modelled and line-only lines, built from the game page's own `props_response` and `line_only_props` (parity pinned by test), with the slate's date default and previous/next dates; date-wide line reads instead of per-game queries
  - [x] 42b. **NBA prop board page** - `/nba/board` as NBA's Props view in `SPORTS` and `SPORT_PAGES`: shared page head with date navigation, market pills, rows ordered by tip time then player with game and tip columns, the game page's evidence drawer, gray and unranked; line-only markets as plain rows
  - [x] 42c. **NBA injuries** - ESPN's keyless NBA injury feed (20a's display source) stored as timestamped snapshots on ESPN ids in a new NBA injury table, refreshed on a schedule before tip-off; each player's status (Out, Day-To-Day) and detail as a tag on board rows and in the evidence drawer, and both teams' injury list on the game page; display only, never a model input (no history exists to backtest)
  - [x] 42d. **NBA team stats** - each team's season-to-date points, rebounds, assists, threes and blocks per game, for and allowed, with league rank, from stored regular-season box scores before the game's date (no new source); the opponent's allowed figure and rank for the row's market in the evidence drawer, and both teams' table on the game page; display only, never a model input
- [ ] 44. **NBA over probability, second method** - a sport-neutral P(over/under/push) method in `app/core/` with a per-market distribution (discrete count model or fitted-variance normal) chosen on 2024-25 alone in a pre-registered order, for the eight markets 20g1 hid and for whole-number lines; confirmed once on a fresh 2026-27 sample (the first 4 whole regular-season weeks) under 20g1's display rule unchanged; shown under a new P(over) version only for markets that pass; projection `nba-reference-v1`, gaps, sorting and picks unchanged, and gray until a 20g4 slice reads `adopt`
  - [x] 44a. **Method and 2024-25 selection** - the shared distribution functions plus candidate order and the confirmation rule, pre-registered before fitting; fitted and chosen on 2024-25 only (cross-fitted); backtest only, no production change, zero 2025-26 or 2026-27 reads
  - [ ] 44b. **2026-27 confirmation** - a frozen fit and one scoring run on the pre-registered 2026-27 sample once its weeks are fully played, recording a show or hide verdict per market; stops as accruing if run early
  - [ ] 44c. **Serve and freeze** - markets that pass show P(over) on the game page and board and freeze under the new version; the ranking check treats it as its own sample, and the `nba-pover-v1` assists sample is untouched
- [x] 45. **NHL support** - ingest and surface NHL on the NBA team-sport pattern (shared `sport_*` tables, the 17c prop pipeline, the web sport registries); no third parallel stack; models follow the same backtest-first, pre-registered gates as NBA, and edges stay gray until a ranking slice reads `adopt`; projection, P(over), frozen predictions, model page and prop board are added as later sub-items once 45a-45e ship
  - [x] 45a. **NHL data sourcing** - pick free schedule, box-score and injury sources; probe PrizePicks' NHL league and The Odds API `icehockey_nhl` credit cost; settle the shared 500-credit monthly budget with NFL and NBA; define NHL's prop period and whether the regulation vs overtime moneyline is stored; document the choice before any ingest is written
  - [x] 45b. **NHL schedule and box-score ingest** - seed `nhl` in `sports`; teams, players and games into `sport_*`; per-game skater and goalie box scores in NHL stat tables; 2023-24 through 2026-27 backfill (a development, a holdout and a prior season for a later projection harness) plus a daily refresh
  - [x] 45c. **NHL prop lines** - PrizePicks NHL lines through the shared 17c pipeline, stored and linked, every market line-only until a projection exists
  - [x] 45d. **NHL game odds** - moneyline (overtime included), puck line and total for DraftKings and Bet365 from Odds-API.io into `sport_game_odds` under provider `odds_api_io`, de-vigged per book, within the shared hourly request quota; no The Odds API credits
  - [x] 45e. **NHL slate and game page** - NHL in `SPORTS`, `SPORT_PAGES` and `SPORT_STATUS`; the table-first slate and a game page with the market, line movement and gray line-only prop rows; no projection, edge or signal color
  - [x] 45f. **NHL injuries and starting goalies** - ESPN injury and probable-goalie (`Expected`/`Confirmed`) snapshots before puck drop, linked to NHL players by name and team, shown on the slate and game page; display only, never a model input until a later item tests it on stored snapshots
- [ ] 21. **WNBA support** - extend NBA coverage to the WNBA
- [ ] 22. **Three-way market support** - handle draws in de-vigging, the ensemble, and the schema, which soccer requires and tennis never needed
- [ ] 23. **Soccer support** - ingest, model, and surface soccer on top of three-way market support

> **Why this order.** Item 17 is seam work, not a sport. Almost every backend
> module is named and shaped for tennis: `routers/tennis.py`, `schemas/tennis.py`,
> `services/tennis/`, `core/tennis_props.py`, plus a `matches` table carrying
> `surface`, `round`, and `best_of`. Adding a sport before that pass means either a
> duplicate parallel stack or tennis concepts leaking into other sports.
>
> Item 18 comes before 19 because the data source decides the schema. Picking a
> free NFL source after building ingest means rewriting ingest.
>
> Items 20 and 21 are cheap once 19 lands, because NBA and WNBA are the same
> team-sport shape on a denser schedule.
>
> Item 22 is separated from 23 because draws are the one genuinely hard change.
> Two-outcome logic is load-bearing in `core/odds.py` de-vigging, in `ensemble.py`,
> and in every `p1_*` / `p2_*` column. Soccer is last for that reason.

**Design note for item 17:** generalize for five sports, not two. The foundation
needs a `teams` concept (NFL, NBA, WNBA are team sports, tennis is not) and should
avoid hardcoding two outcomes anywhere new, so item 22 is an extension rather than
a rewrite. `/feature 17` will likely split into sub-items (17a, 17b, ...) since it
spans schema, services, and API.

> **Item 19 was built before item 17, deliberately.** NFL landed in its own
> `nfl_teams` / `nfl_players` / `nfl_games` / `nfl_player_weekly_stats` /
> `nfl_prop_lines` tables rather than waiting on the generalization, because
> rewriting the working tennis schema to add the first team sport was judged the
> riskier order. The ordering rationale above still describes the tradeoff
> correctly: the cost is the duplicate parallel stack it warned about.
>
> So item 17 is now **converging two working stacks**, not clearing a path for the
> first one. That is a different and better-informed job than it would have been
> up front, since NFL has since shown which tennis assumptions actually fail for a
> team sport. Items 20 and 21 should not add a third parallel stack; fold NBA and
> WNBA in through 17 instead.

**Note on item 19f.** NFL odds come from The Odds API (`api.the-odds-api.com`,
`THE_ODDS_API_KEY`), not the similarly named Odds-API.io that tennis uses. The key
is on the free plan (500 credits a month), so no paid subscription is needed. This matters beyond convenience: PrizePicks
is DFS pick'em with fixed payouts, so its lines cannot be de-vigged into a true
probability. Real book odds can, which is what `core/odds.py` already does for
tennis and what feeds the ensemble's `p1_market_prob`. That makes 19f the
prerequisite for 19e rather than a parallel nice-to-have.

> Not planned: monetization, accounts, and multi-user support, per
> `project-plan.md` section 6. Deferred to roughly 2028.

> Deployment is item 37 (decided 2026-10-15): a public read-only demo on Render.

## Lineform redesign

- [x] 38. **Structural redesign** - one app shape for every sport, keeping the palette, fonts and signal rules: a command-bar shell, table-first slates and props as table rows instead of cards, per the Impeccable direction contract (`.impeccable/surfaces/`) and the chosen sketch `.impeccable/mocks/decision/command.html`; display only, never a probability, edge, rank, sort or pick change
  - [x] 38a. **Lineform shell** - finish the rename from SportApp to Lineform in the UI and README; a top bar with logo, sport tabs and Slate / Props / Model / How it works on every page (replacing each page's own view switch); one shared page head (title, period, previous and next); per-route tab titles; phone menu
  - [x] 38b. **Table-first NFL slate** - a plays digest of the week's largest gaps (gray, labeled reference) above one dense row per game grouped by kickoff window, each row opening the game page; two-line rows on phones
  - [x] 38c. **Tennis and NBA slates on the same shape** - tennis's digest holds its priced picks (green under the existing rule) above a match table whose rows expand inline (best opportunity, model breakdown, serve and return, link to the match page), replacing the side panel; NBA's digest holds its largest gaps (gray)
    - [x] 38c1. **Tennis slate** - the priced best picks as the shared digest strip (green under the existing rule) above the match table, whose rows expand inline (best opportunity, model breakdown, serve and return, decision board, link to the match page), replacing the side panel and the pick cards
    - [x] 38c2. **NBA slate** - one table row per game in place of the cards, each opening the game page, under a gray digest of the day's largest gaps: standard lines with a projection, ranked by |gap| / line, one per player, upcoming games only, labeled reference; the one place an NBA gap is sorted, a narrow exception to 20g2 that the game page and props do not share
  - [x] 38d. **Props as tables** - the NFL game page and prop board, the tennis prop board and the NBA game page show props as dense rows (player, market, line, model, gap, last-5 mini bars, rank) instead of cards, with each prop's detail in a drawer; ranks, edges and colors unchanged
    - [x] 38d1. **NFL props as rows** - the prop board and the game page's Props show one dense row per line (rank, player, line, model, gap, last-5 mini bars, sample) per market, read from the unchanged card model; the board's side panel becomes the game page's evidence drawer; the gray "Other lines" become plain rows with no drawer; shared row CSS and mini bars for 38d2 and 38d3
    - [x] 38d2. **Tennis prop board as rows** - one row per line (rank, player and match, line, model, hit against break-even, EV, tier, trust) with the evidence panel in a drawer; EV keeps its green and red rule; last-5 bars stay in the drawer, since they need a request per match
    - [x] 38d3. **NBA game page props as rows** - the gray Props and "Other lines" as rows (player, line, projection, gap, P(over) where shown, last-5 mini bars), unranked and unsorted as 20g2 requires, with a drawer of each line's rungs and recent games from the data already loaded; the prop card CSS is deleted
  - [x] 38e. **Command field** - a search in the top bar, focused with `/`, that filters the current slate as you type and jumps to a game, team or player from data the page already loaded; Enter opens the top match; a search button that expands on phones
  - [x] 38f. **Shape consistency pass** - model, game, match and player pages take the shared page head; game pages get an `h1`; times read `CT` everywhere; the defects from the 2026-10-16 polish captures that survive the new shape

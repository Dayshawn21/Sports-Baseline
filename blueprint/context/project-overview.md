# Lineform - Project Overview

**Product name:** Lineform (formerly SportApp V2; renamed 2026-10-16).

> Multi-sport betting intelligence. Ingest matches, odds, stats and props on a
> schedule, model each outcome, compare it with the market, and surface a play
> only when a pre-registered forward check says the edge is real. Tennis, NFL,
> NBA and NHL are live on a public read-only demo; WNBA and soccer are planned.
> Most model outputs are gray reference today, because the checks that would
> adopt them are still accruing or have rejected them.

> **Generated file. Don't hand-edit.** Produced by `/overview` from
> [../project-plan.md](../project-plan.md) and [../build-plan.md](../build-plan.md).
> When the plans change, re-run `/overview` rather than editing here.

**Regenerated:** 2026-11-12 (fourteenth refresh, slimmed). Completed work is
one line per item here; its detail lives in the archive under
`blueprint/history/features/` (and `fixes/`). This file keeps only what open
work depends on: the rules, the served versions, and what blocks each open
item. The build plan is the progress authority. This refresh read no holdout,
queried no provider, and made no new verdict; numbers below are dated
observations from archives.

## Problem

Betting markets are efficient enough that casual bettors lose, but not so
efficient that every line is priced correctly. Finding the mispriced ones by
hand means reconciling form, surface history, head-to-head, ELO and live book
odds across several sites, for dozens of games a day.

Lineform does that reconciliation automatically, and it stores every
prediction before the start and grades it against results, so an edge is
measured rather than assumed. Placed bets are tracked outside the app, in
Pikkit. Tennis came first (two outcomes, no draws, daily volume, free ELO and
box scores); the machinery is shared so each new sport supplies sources, a
model and its market shapes.

## Users

**One user: the project owner.** A settled decision, not a stage.

- no accounts, no per-user data, no stored user id
- admin routes sit behind one shared `X-API-Key`; production refuses to start
  without a strong one
- public demo visitors are anonymous and read-only; the only login is the
  owner's, for the admin surface (37a)

Multi-user is out of scope until roughly 2028 (see Monetization). Do not add
accounts, auth or per-user scoping to a spec unless `project-plan.md` §2 and
§6 change first.

## Features

### Where things stand (2026-11-13)

- **13 leaf items are open.** Only 68d (web polish; 68a complete 2026-11-12,
  68b and 68c 2026-11-13) is buildable today; the rest wait on a forward
  verdict, a date, or a provider.
- **Next dated event:** 44b's 2026-27 sample (NBA weeks 1-4) is expected to be
  complete about 2026-11-17; work resumes on branch
  `feature/44b-nba-pover-confirmation`.
- **Next new sport:** 21 (WNBA). The WNBA season runs May to September, so
  sourcing can be specced now but live data will not exist until 2027.
- **No-argument `/feature` would pick parked 16f.** Name the item instead
  (`/feature 68d`, `/feature 21`, `/feature 44b`).

### What's left and what blocks it

| Item | Outcome | Blocked by | If it passes / fails |
|---|---|---|---|
| 44b | NBA P(over) second method, one confirmation run | 2026-27 weeks 1-4 fully played with box scores (about 2026-11-17); stops as accruing if run early | Records show or hide per market |
| 44c | Serve and freeze the markets 44b shows | 44b | Own version `nba-pover-v2` and its own ranking sample; `nba-pover-v1` assists sample untouched |
| 66b | Serve the shrunk tennis ensemble for a passing slice | 66a's forward check (`tennis-shrink-check-v1`): not yet activated; needs 400 affected matches and 30 days per slice | Pass: new ensemble version for that slice. Fail: dropped for that slice |
| 41c | Serve in-house tennis ELO | 41b's forward non-inferiority check, accruing since 2026-10-22 | Pass: new model version, retire the local ELO task. Fail: dropped |
| 27h | NFL ranking by P(over) | A 27j slice reading `adopt`. Standard under and demon over are rejected (final for v4); standard over and goblin over accrue | Dropped if all four reject |
| 25c | Anytime TD rated against the de-vigged market | 25b's forward sample passing a pre-registered rule (no historical holdout exists) | May never adopt |
| 21 | WNBA support | Sourcing decision; no live games until 2027 | Extends NBA, no third stack |
| 22 | Three-way market support | Needs a spec; prerequisite for 23 | Draws in de-vig, ensemble and schema |
| 23 | Soccer support | 22 | |
| 16f | Tennis set-handicap projection | Parked 2026-09-29: provider sends too few, misfiled lines | Revisit only if lines become regular |
| 48d2, 48d3 | Store and show sportsbook tennis player props | Parked 2026-10-30: the free books send moneylines only | Revisit only if the free plan adds them |
| 68d | Interface polish: swipe-to-dismiss drawers | Nothing | Display only; no API, model, rank or color change |

**Open decisions found in this refresh** (owner calls, not build steps):

1. **41c and 66b both change the served tennis ensemble.** Both are judged
   against `ensemble-v3`. If 41c ships first, 66's verdict describes a model
   no longer served, and vice versa. Decide the order (or that the second must
   re-register its check against the new base) before either is specced.
2. **NBA and NHL have no "adopt in ranking" item.** NFL has 27h and tennis
   has 48g, but an NBA (20g4) or NHL (56d) slice that reads `adopt` has no
   item that would rank or color it. Add one per sport when the first slice
   nears a verdict (NHL: not before about 2026-12-01).
3. **48d2 and 48d3 stay unchecked under a closed parent 48,** and 16f keeps
   parent 16 open. Consider one "Parked" list so parked items stop reading as
   pending work.

### Status of every item

Archives are `blueprint/history/features/<item>-*.md`. "Gray" means shown as
reference, never colored, ranked or picked.

| Item | Outcome | State |
|---|---|---|
| 1-12 | Tennis app as adopted: ingest, identity, ELO, rolling stats, odds, ensemble, slate, best picks, props, bankroll, bets, admin | Built before Blueprint; 10 hidden from nav, 11 removed 2026-10-15 (Pikkit) |
| 13-15 | Test deps, script cleanup, accuracy pass | Complete |
| 16 | Props coverage expansion (16a-16e) | Complete except parked 16f |
| 26 | Tennis model validation (26a-26f) | Complete: market unbeaten; `ensemble-v3` market-anchored blend served; moneyline picks off |
| 40 | WTA 125 blend group | Complete: kept pooled Challenger; 40b dropped |
| 41 | TennisMyLife data (41a box scores, 41b shadow ELO) | 41a, 41b complete; 41c conditional |
| 48 | Tennis prop rebuild (48a-48g) | Closed 2026-10-30: `props-v3` served gray, `props-v4` simulation stored as shadow, tiers retired, forward check and adoption wired; no slice adopted; 48d2-48d3 parked |
| 66 | Tennis shrinkage toward the market | 66a engineering complete 2026-11-11 (`shrink-v1` shadow, migration `0054`); activation and verdict pending; 66b conditional |
| 17 | Multi-sport foundation (17a-17d) | Complete: shared `sport_*` tables and sport-agnostic prop pipeline |
| 18-19 | NFL sourcing and support (19a-19n) | Complete |
| 24 | NFL game-line model (24a-24e) | Complete: no signal adopted; model shown muted |
| 28-30 | NFL game-line CLV check, game notes, team stats | Complete; display or read-only |
| 43 | NFL matchup and usage context | Complete; aDOT unavailable |
| 31-33 | Web redesign, tennis and NFL detail pages | Complete |
| 25 | Market-relative prop rating | 25a, 25b complete; 25c conditional |
| 27 | NFL prop probability model (27a-27l) | Complete except 27h; 27l3 kicker projection rejected (K fantasy hidden) |
| 34-36 | More NFL lines, line-only display, NFL best line | Complete |
| 39 | NFL Rec Targets projection | Complete: gray reference, P(over) hidden, graded as its own sample |
| 49 | NFL market-anchored prop model (49a-49e) | Complete: receptions only, `nfl-volume-v1` gray, frozen and graded forward |
| 37 | Public read-only demo (37a-37e) | Complete: live on Render since 2026-10-16 |
| 47 | Ask Lineform (47a-47e) | Complete; production off unless `ASK_ENABLED` |
| 20 | NBA support (20a-20g4) | Complete |
| 42 | NBA prop board (42a-42d) | Complete |
| 44 | NBA over probability, second method | 44a complete; 44b, 44c open |
| 65 | NBA injury-aware minutes | Closed 2026-11-11: rejected in every market at 65a; 65b-65c dropped |
| 45 | NHL support (45a-45f) | Complete |
| 56 | NHL prop board and model (56a-56d) | Complete: `nhl-reference-v1` gray, P(over) in four markets, frozen, forward check accruing |
| 67 | NHL opposing-goalie adjustment | Closed 2026-11-11: `beta = 0` in every market on development; holdout not read; 67b-67c not built |
| 38 | Structural redesign (38a-38f) | Complete |
| 46 | Analysis workspace (46a-46d) | Complete; outside the app |
| 50-52 | NFL props as player pages, form window, other markets as tabs | Complete |
| 53-54 | NBA, NHL and tennis player pages; shared player-page shell | Complete |
| 55 | Home page | Complete |
| 57 | One slate shape for every sport (57a-57d) | Complete |
| 58 | Team logos | Complete |
| 59 | Record strip on the prop boards | Complete |
| 60 | Projection history chart (60a tennis, 60b NHL) | Complete; NBA and NFL not planned |
| 61 | Calculators page (`/tools`) | Complete |
| 62 | Prop board row polish | Complete |
| 63 | Why over / Why under on tennis props | Complete; other sports are later items |
| 64 | Context filters on the prop boards (64a-64c) | Complete; 64b's NBA filter moves to the player page in 69 |
| 68 | Interface polish (68a-68d) | 68a complete 2026-11-12 (CSS polish); 68b (view transitions) and 68c (skeleton loaders) complete 2026-11-13; 68d planned; display only |
| 69 | NBA teammate-out split on the player page | Complete; the props-page filter removed, board filters fixed on phones |
| 21-23 | WNBA, three-way markets, soccer | Planned |

Unless an archive says otherwise, recent items (50 onward) are complete on
`master` but hosted deployment was not separately verified.

### Served versions

| Sport | Served (gray unless noted) | Shadow or hidden |
|---|---|---|
| Tennis match | `ensemble-v3+lgbm-v6` (ATP, WTA); `ensemble-v3+lgbm-none` (Challenger, WTA 125); no-market fallback `ensemble-v2` hand-set path, frozen | `shrink-v1` in `prediction_shadows` (66a); `tennismylife-elo-v1` (41b) |
| Tennis props | `props-v3` P(over) against each payout's break-even; colored only in a slice 48e adopts (none yet) | `props-v4` match simulation (48c); `props-v2` tiers readable as history |
| NFL props | `opponent-dvp-tg-blend-usage-snap-v4` with `nfl-pover-v1` (receiving and rushing yards only); `nfl-targets-v1` (no P(over)); `nfl-volume-v1` + `nfl-volume-anchor-v1` receptions companion | Kicker projection `nfl-kicker-v1` rejected, not served |
| NFL game lines | `nfl-elo-v1` spread and win probability, scoring-rating total, muted | |
| NBA props | `nba-reference-v1`; `nba-pover-v1` (assists only) | `nba-pover-v2` fit frozen (44a), unserved until 44b/44c |
| NHL props | `nhl-reference-v1`; `nhl-pover-v1` (Shots on Goal, Time On Ice, Goals Allowed, Faceoffs Won) | |

A version bump always starts a fresh forward sample, and any projection
change hides a P(over) whose fit names a different projection version.

### Load-bearing rules

**Signal rule.** An unvalidated number is context, never a pick: it may sit
beside the market, but it never colors a row, drives an edge, sets a rank, or
reaches a board of plays. Model pages stay gray unless a rate clears its
baseline or break-even by more than 2 SE. No UI text below 11px.

**Validation discipline.**

- Every adoption is decided by a rule committed before the data that judges
  it is read; cited pre-registration commits merge `--ff-only`, never squash.
- A reject is final for that version. A new candidate needs a new
  pre-registration.
- Fitted inputs are fitted on development seasons only, never the holdout.
- Holdout read counts (each archive records its reads):

| Sport | Holdout | Reads so far | Consequence |
|---|---|---|---|
| Tennis | 2023-2025 Valuebetennis | 2 (26c, 26d); 2026 also read by 40a | Neither is fresh evidence; new tennis changes are judged forward |
| NFL | 2025 season | 9 (F-02, 27c-27g, 27k, 39b, 27l3) | Fresh NFL evidence comes from forward 2026 lines |
| NBA | 2025-26 season | 2 (20f, 20g1) | 44 confirms on fresh 2026-27 weeks 1-4 instead |
| NHL | 2025-26 season | 1 (56c2's P(over) fit); unread for projection verdicts, including 67 | Any projection candidate reads it once, under its own pre-registration |

**The shared ranking rule** (27i, `app/core/prop_ranking_rule.py`, used by
NFL, NBA and NHL unchanged):

- Break-even per leg: standard 57.7%, goblin 75.8%, demon 41.3%
  (`app/core/prop_ev.py`); goblin and demon are over only.
- A pick: the frozen side probability is at least break-even plus 3 points;
  one pick per player, game, market, line type and side.
- Four slices: standard over, standard under, goblin over, demon over.
- Verdict sample: the first whole periods holding 200 picks over 4 or more
  periods, then fixed. Adopt only when hit rate minus 2 SE beats break-even.
- Graded on each prop's latest frozen pre-start row at its own line; only
  fully played periods count; rows under another version are excluded.

**Tennis prop check** (`tennis-props-check-v1`, 48e,
`app/core/tennis_prop_check.py`): slices are stat, tour, anchor (book total of
17+ games or model), payout and side, weekly periods, Power break-evens only,
and a 3 SE gate because there are hundreds of slices. The first real
`tennis_prop_check` and `tennis_prop_adoption` runs each need a separate yes
in chat.

**Cross-sport plumbing.**

- A new sport adds one `SPORTS` entry (`web/src/utils/sportNav.ts`), one
  `SPORT_PAGES` entry (`web/src/routes/sportPages.tsx`) and one
  `PROP_SOURCES` entry (`app/services/sport_registry.py`), and no third
  parallel stack.
- Shared prop modules never import `sport_registry` (it imports NFL code).
- Every reader that projects, grades or freezes lines applies the sport's
  modelled-market filter (`MODELLED_MARKET_FILTER`,
  `NBA_MODELLED_MARKET_FILTER`); line-only markets stay out of those paths.
- Every `sport_*` read filters by sport; every odds read names its provider.
- Model history reads carry an explicit lower season bound as a named
  constant, so a later backfill cannot change a served version's output.
- Production (512 MB) never builds a heavy report on request; it serves
  `report_snapshots` and returns 503 when one is missing (see Deployment).

### Notes on open items

**Tennis model today** (`ensemble-v3`, since 2026-10-01):

- With a market price, `blend()` serves 26d's fitted log-odds blend per group
  (ATP `a` 1.14, `b` -0.08; WTA 1.46, -0.42; Challenger 1.11, +0.08). It is
  the close, slightly extremized: a better forecast, not a market-beater.
  Without a price, the frozen hand-set `ensemble-v2` path runs; never retune
  it, since 26c replays through it.
- v6 LightGBM gets no weight and runs for ATP and WTA only. WTA 125 is stored
  as `CHALLENGER` and takes the Challenger group (40a).
- Moneyline best picks are off (`MONEYLINE_PICKS_ENABLED = False`), because
  26d's holdout showed its gaps lose. The slate shows a gray model lean.
- Odds: Odds-API.io's free books (DraftKings, FanDuel) send tennis moneylines
  only since 2026-10-27; total games come from The Odds API for ATP and WTA
  tour-level matches only (48b). Challenger and WTA 125 props carry
  `no_market_total`.
- `ensemble_weights` on `ensemble-v3` rows holds coefficients, not shares;
  readers branch on `model_version`.

**66. Shrinkage toward the market.** `shrink-v1` keeps half the gap when the
served ensemble and the de-vigged market differ by 3+ points. Pre-registered
in `5d99a7f0` with amendments A1 (each slice pins its served version) and A2
(a match unresolved 14 days is dropped). ATP+WTA and Challenger are judged
apart, 400 affected matches and 30 days per slice, adopt only beyond 2 SE.
Never score `ensemble-v3` rows from before activation, even to look. The
read-only diagnostic leaned WTA in favor and Challenger against; neither
tripped its stop test.

**41. In-house ELO.** `tennismylife-elo-v1` is stored in
`tennis_elo_snapshots` (`0046`), never `player_elo`, with immutable pre-match
pairs in `tennis_elo_comparisons` (`0047`; experiments revised in `0051`,
`0052`). The rule is non-inferiority with a 0.005 log-loss margin. TennisAbstract
stays the source for WTA 125 box scores and rolling stats; the TennisAbstract
ELO refresh runs on the owner's PC (`Lineform ingest_daily`) because
Cloudflare blocks GitHub's runners.

**44. NBA second P(over) method.** 44a chose on 2024-25 alone
(rules in `ebd4aea`): `scaled_normal` for points and the four combos,
`negbin` for rebounds; threes and blocks not carried. Frozen fit in
`app/core/nba_over_probability_v2_fit.py`, shared math in
`app/core/count_over_probability.py`. 44b scores once under 20g1's display
rule unchanged (300+ cases, ECE <= 0.02, no 200+-pair bin off by more than
0.05, Brier no worse than a normal). Projection, gaps, ordering and gray
display are unchanged.

**27h and 49. NFL prop ranking.** As of 2026-10-23, standard under (53.7%
+/- 2.4 on 419 picks) and demon over (39.4% +/- 2.9 on 289) are rejected for
v4; standard over and goblin over accrue. `nfl-volume-v1` is judged by its
own rule (`b869a492`: 27i's pick rule plus a log-loss clause); its pick slices
are expected to stay insufficient through 2026. v4's frozen readers exclude
`nfl-volume-v1` rows before newest-row selection.

**25c. Anytime TD.** The Odds API sells current markets only, so evidence
accrues forward from 19i. The sportsbook probability stays beside the model,
never blended, until 25c passes; it may then drive edge and rank for anytime
TD only.

**NBA and NHL forward checks.** Both run 27i's rule through the shared
pipeline (`/nba/model`, `/nhl/model`). NBA picks can come only from assists
until 44c; NHL from its four P(over) markets. NHL's slices sat at 0 of 200
picks on 2026-11-05.

**21-23. New sports.** WNBA reuses NBA's shape (shorter season, thinner
data). Item 22 is split from soccer because draws break the two-outcome
assumption in `core/odds.py` de-vigging, `ensemble.py` and every `p1_*` /
`p2_*` column. Tennis `matches` convergence waits for item 22.

| Sport | What it breaks that tennis does not |
|---|---|
| NFL | Teams; weekly cadence and a small training set; spreads and totals over moneyline |
| NBA | Teams, dense daily schedule, heavy prop volume |
| NHL | Small-integer count props, fixed +/-1.5 puck line, overtime-inclusive moneyline, separate skater and goalie stats |
| WNBA | NBA shape, shorter season, thinner public data |
| Soccer | **Draws.** Three-way markets break the two-outcome assumption |

## Data model

### NHL display response (45e/45f, implemented)

`GET /nhl/slate?date=YYYY-MM-DD` returns `date`, nullable `previousDate` and
`nextDate`, and `games[]`. Each game carries internal `gameId`, season/week,
REG/PST type, Eastern date, nullable aware start, status, team codes/names,
nullable final scores/end period, eligible prop count, nullable per-book
moneyline/spread/total, line movement and `context`.
`GET /nhl/games/{id}` shares those fields and adds `lineHistory`.
`GET /nhl/games/{id}/line-only-props` returns `gameId` and eligible `lines[]`:
provider/offering id, internal player id, stored player name/position,
provider-reported team, market,
offering type, provider line and fetch timestamp. No player detail link or
projection is fabricated. Missing/wrong-sport/PRE ids return 404, malformed
ids/dates 422; an empty slate returns 200 without a context query.

Both slate/detail use camelCase `context: {injuries, goalies}`. Each component
has `source='ESPN'`, nullable aware `fetchedAt`/`sourceTimestamp`, independent
`freshness='fresh'|'stale'|'unavailable'`, and away/home values. Injury arrays
retain source athlete id/name/team, nullable internal player id, raw status,
detail, sourceUpdatedAt/returnDate, linkReason and teamMismatch. Goalie sides
retain team, nullable athlete/player ids/name, rawStatus, linkReason and status
Expected/Confirmed/unknown/not_reported/unavailable on the wire as lowercase
codes. Missing tables produce an explicit migration-required 503, not empty
reports. Reads use two batched context queries, frozen links and no provider
I/O/writes. Full contracts: `docs/nhl-display.md`, `docs/nhl-context.md`.

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
  - `projection_version` (text, `props-v1` to `props-v3`, served `props-v3`
    since 48a); **unique on** (`prop_id`,
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
- Seeded with `nfl`; `0043` (20b) adds `nba`, `0049` (45b) adds `nhl`.
  17d's registries live in code and do not read it. Seeding a database sport
  does not enable a public page or prediction source.

### Shared team-sport tables (`sport_*`, 17a and 17b, `0039` to `0041`)

Seven shared tables available to team sports, each with `sport` (text, required,
foreign key to `sports.code`, **no default**, so a missing sport is an error).
NFL, NBA (20b to 20d) and NHL (45b to 45d) write to them. They were the `nfl_*` tables until 17a
renamed them in place (rows, ids and inbound foreign keys carried over); 17b
moved all NFL code onto them and `0041` dropped the `nfl_*` compatibility
views. NFLverse ids are the NFL join keys: gsis id (`source_player_id`) and
game id (`source_game_id`). NBA uses ESPN ids, NHL the league's own ids.
Schedule/stat ingest creates canonical teams, players and games; prop/odds
ingest matches those existing identities and never creates them from a line.

- **`sport_teams`** - `team_code` (NFLverse codes for NFL), `name`, `conference`, `division`; **unique on** (`sport`, `team_code`)
- **`sport_players`** - `source_player_id`, `name`, `position`, `team_id` (last-write-wins; NFL readers use the weekly roster instead, see below); **unique on** (`sport`, `source_player_id`)
- **`sport_player_aliases`** - provider-name overrides: `player_id`, `alias_name`, `alias_name_norm`, `source`; **unique on** (`sport`, `alias_name_norm`)
- **`sport_games`** - `source_game_id`, `season`, `week` (nullable at the shared schema level; `CHECK (sport <> 'nfl' OR week IS NOT NULL)`; NBA ingest also assigns the regular-season Eastern week defined by 20a), `game_type`, `game_date`, `start_utc`, `home_team_id`, `away_team_id`, `home_score`, `away_score`, `status`; **unique on** (`sport`, `source_game_id`). NFL-only nullable columns stay here (decided in 17b; other sports leave them NULL): from 19n (`0028`), NFLverse closing lines `spread_line` (expected home margin: positive = home favored), `total_line`, `home_moneyline`, `away_moneyline`, plus `roof`, `home_rest`, `away_rest`; from 24e (`0031`), `temp` (°F) and `wind` (mph) smallint, observed rather than forecast, NULL for indoor games and blanks; and `espn_event_id`
- **`sport_prop_lines`** - PrizePicks snapshots: `provider`, `provider_prop_id`, `market`, **`segment`**, `odds_type`, `line`, `start_time`, `player_id`, `game_id`, `fetched_at`, `raw_json`
- **`sport_game_odds`** (19f, `0020`) - append-only: `game_id`, `book`, `market` (`moneyline` | `spread` | `total`), `line`, `first_side`/`second_side`, `first_odds`/`second_odds` (American), de-vigged `first_market_prob`/`second_market_prob`, `fetched_at`, `raw_json`. `provider` (36a, `0044`): `the_odds_api_us` (every row before 36a; the only feed pre-36a readers see), `the_odds_api_eu` (Pinnacle) or `odds_api_io` (DraftKings and FanDuel; Bet365 rows before 2026-10-27); every reader names its provider, enforced by `tests/test_sport_game_odds_provider.py`
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

**NHL additions to the shared contracts (45b-45f):**

- `sport_games.end_period` is nullable `varchar(3)`, `REG`/`OT`/`SO`, added
  by `0049`. A check requires NULL outside NHL. NHL scores are the official
  final including a shootout winner's goal; NHL `game_date` is Eastern,
  `season` the start year, `week` the shared regular-season week (NULL in PST).
- NHL `sport_prop_lines` use `provider='prizepicks'`, `segment='full_game'`
  and twelve line-only keys: `shots_on_goal`, `points`, `assists`, `goals`,
  `power_play_points`, `blocked_shots`, `plus_minus`, `goalie_saves`, `hits`,
  `time_on_ice`, `goals_allowed`, `faceoffs_won`. TOI lines are minutes;
  raw numeric values and original fetch/start timestamps remain intact on relink.
- NHL `sport_game_odds` use `provider='odds_api_io'`, `book='draftkings'`
  or `'fanduel'` (`'bet365'` on rows stored before 2026-10-27). FanDuel sends
  spread and total ladders; rungs priced past 75% on either side are dropped
  before the least-vig main-line pick (`near_even_rungs`, shared with NFL). Moneyline is two-way OT/SO-inclusive with NULL `line` and
  home/away sides. Puck line is stored as `market='spread'`, signed for the
  stored home team, +/-1.5, home/away sides. Total has a positive goal line
  and over/under sides. American prices are integer; `line` is numeric(7,2),
  probabilities are double precision and sum to one per book/rung. Each
  new snapshot has a database statement-time `fetched_at` and provider event
  id in `raw_json`. A missing book or market never deletes earlier history.
- **Load-bearing for NHL display:** NHL reads must name both `sport='nhl'` and
  `provider='odds_api_io'`. Existing NFL/NBA readers retain their named feeds.
  A book's fair pair is market context, never a model recommendation.
- NHL shares the pure `regular_season_week` helper with NBA (45b). Empty
  break weeks have no games and do not count as finished periods. NHL has
  no projection/freezing/ranking source, so no grading readiness is implied.

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

### NHL box scores (`nhl_skater_game_stats`, `nhl_goalie_game_stats`, 45b, `0049`)

NHL games/teams/players live in shared tables under `sport='nhl'`. Canonical
keys are NHL `gameId`, `playerId` and tri-codes (`TBL`, `UTA`; historical
`ARI` stays separate). Player team is the latest loaded game's team; a past
game's team is always the stat row's `team_id`. No ESPN-to-NHL id equivalence
is assumed; 45f resolves ESPN display data conservatively by full name/team.

Both stat tables have:

- `id` bigint PK; required `player_id`/`game_id` FKs to shared players/games
  (cascade on delete), `team_id`/`opponent_team_id` FKs to shared teams.
- `season` smallint, `is_home` boolean, nullable `time_on_ice_seconds`
  integer, `fetched_at` timestamptz; unique (`player_id`, `game_id`), indexes
  on (`player_id`, `season`) and `game_id`.
- Skaters: nullable text `position`; nullable smallint `goals`, `assists`,
  `points`, `shots`, `power_play_goals`, `power_play_points`,
  `shorthanded_points`, `plus_minus`, `hits`, `blocked_shots`, `faceoffs_won`,
  `faceoffs_lost`, `penalty_minutes`, `giveaways`, `takeaways`, `ot_goals`.
- Goalies: required boolean `started`; nullable text `decision` checked to
  `W`/`L`/`O`; nullable smallint `saves`, `shots_against`, `goals_against`.

Only completed REG/PST games have stat rows. A skater row means he dressed,
a goalie row means he played; no player row means did not play, never zero.
Before treating missing stats as a void, establish that the game's stat load
is complete; NULL stat columns mean not loaded. Player/goalie stats exclude
shootout attempts. Goalie goals are not stored in these columns; five
documented goalie-goal exceptions explain skater-total versus official-score
differences. Do not infer a data repair from that difference alone.

The recorded 45b backfill inventory was 5,536 games, 156,830 skater rows and
9,222 goalie rows across 2023-24 through 2026-27. The designated 2025-26
future holdout was imported and integrity-checked, not fitted or evaluated.
No NHL model, fit, frozen prediction or ranking report is introduced by this
schema or by 45c/45d. NHL props remain line-only until later model items.

### NHL context snapshots (45f, `0050`)

Migration 0050 is applied to the shared database (53d and 53e read these
tables; a missing table is a 503). All reads and writes
retain NHL/REG/PST ownership; ESPN ids are never NHL source ids.

- `nhl_context_snapshots`: `id` bigint PK; `source` text fixed ESPN; `kind`
  injuries/goalies; `scope_date` nullable date (NULL for global injuries,
  Eastern scoreboard date for goalies); aware `fetched_at` and nullable
  `source_timestamp`; nonnegative integer `entry_count`. Injury source time
  is required. Unique source/kind/scope/fetch uses NULLS NOT DISTINCT.
  Indexed kind/scope/fetch DESC/id DESC supports newest-header selection.
- `nhl_player_injuries`: snapshot FK, ESPN team/athlete ids, canonical team,
  source player name/status/detail, aware nullable source_updated_at,
  return-date text, nullable nested athlete team id and internal player FK,
  frozen link_reason. PK snapshot/team/athlete; index snapshot/team.
- `nhl_goalie_observations`: snapshot FK, ESPN event/date/start/time-valid,
  ordered home/away teams, reported team and athlete identity/status, nested
  athlete team/position, nullable internal player/game FKs and frozen link
  reasons. PK snapshot/event/team; index snapshot/game. Source statuses are
  expected/confirmed/unknown/not_reported. A no-announcement competitor has
  null athlete fields. Source names remain when internal ids are unresolved.

Player link reasons: matched/no_candidate/ambiguous/team_mismatch/missing_team/
position_mismatch/not_reported. Event reasons: matched/no_game/ambiguous/
missing_start/start_mismatch. IDs are present iff reason is matched. Repository
validation checks NHL FKs and G position, and savepoints keep each complete
batch atomic. Ingest commits feeds independently. Exact timestamp/content
retries reuse the batch; conflicting content fails. No update/relink/cleanup
rewrites history; current roster joins are absent on reads.

Select the newest successful header with `fetched_at < start_utc` and
`fetched_at <= response_as_of` before looking for entries, independently per
feed and with id tie-breaking. Injuries filter to the game's teams; goalies
use its Eastern date and frozen game/event match. Rescheduled or ambiguous
events become unavailable. A missing event does not resurrect an older
Confirmed goalie. Known batch times remain visible for missing events; no
eligible batch or TBD start has unavailable/null timestamps. Exactly six
hours at `min(response_as_of, start_utc)` is fresh, over six is stale. Historical
pages retain pre-game observations; post-start downloads cannot backfill them.
Successful empty injuries mean No injuries reported by ESPN, never healthy.
These snapshots authorize no retrospective scoring or model adoption.

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

### Other tables by migration (`0042` to `0054`)

Shapes are in each migration file and the named archive.

| Migration | Adds | Item |
|---|---|---|
| `0042` | NFL kicking and punting stat columns | 34b |
| `0043` | NBA games and `nba_player_game_stats` | 20b |
| `0044` | `provider` on `sport_game_odds` | 36a |
| `0045` | `report_snapshots` | 37d |
| `0046`, `0047` | `tennis_elo_snapshots`, `tennis_elo_comparisons` (shadow ELO, never `player_elo`) | 41b |
| `0048` | `nba_injury_snapshots` | 42c |
| `0049` | NHL games, `end_period`, skater and goalie stat tables | 45b |
| `0050` | NHL context snapshots (below); applied to the shared database | 45f |
| `0051`, `0052` | Tennis ELO experiment revisions | fixes `tennis-elo-experiment-v2`, `-v3` |
| `0053` | NFL kicking by distance band and `pat_missed` | 27l1 |
| `0054` | `prediction_shadows` (the `shrink-v1` shadow beside each prediction) | 66a |

## Tech stack

**Backend**

- **FastAPI 0.115 + Uvicorn** - the API, with a lifespan hook that loads models once
- **SQLAlchemy 2.0 async + psycopg3** - all DB access, through `app/repositories/`
- **Alembic** - every schema change, sequentially numbered
- **Pydantic 2 + pydantic-settings** - request/response schemas and env config
- **LightGBM / XGBoost / scikit-learn / joblib** - models and calibration; the future tennis v7 policy uses validation-fitted sigmoid calibration (scikit-learn also fits the NFL backtests)
- **Playwright / httpx / requests / tenacity** - ingest and retry
- **Anthropic Python SDK** - Ask Lineform (item 47), Messages API with a hand-written tool loop; model in Settings

**Analysis workspace (item 46, `analysis/.venv`)**

- **Jupyter, pandas, matplotlib, SQLAlchemy + psycopg** - read-only notebooks and branded chart export
- **nfl_data_py, nba_api** - free public data, cached locally
- **Playwright** - renders the HTML/CSS thumbnail template to PNG

**Frontend**

- **React 19 + Vite 7** - SPA, no metaframework, because it is a pure API client
- **TypeScript strict** - no `any`
- **Ant Design 5** - structural and interactive components
- **Tailwind v4** - utility styling, CSS-first, no config file
- **TanStack Query 5 + axios** - all server state

### Data sources

| Sport | Schedule | Stats / ratings | Odds | Props |
|---|---|---|---|---|
| Tennis | livetennisapi | TennisAbstract (ELO, rolling and per-match stats, WTA 125); TennisMyLife (ATP, Challenger, qualifying and WTA box-score display gaps, 41a; shadow ELO `tennismylife-elo-v1`, 41b, not served) | Odds-API.io (DraftKings and FanDuel, moneyline only); The Odds API (total games, Pinnacle first, tour-level only, 48b) | PrizePicks, DraftKings |
| NFL | NFLverse | NFLverse weekly stats, play-by-play, rosters, injuries, depth charts, snap counts | The Odds API (free plan: us books, Pinnacle via eu from 36a); Odds-API.io (DraftKings and FanDuel; Bet365 from 36a until 2026-10-26) | PrizePicks, The Odds API (anytime TD) |
| NBA | hoopR ESPN releases (`espn_nba_schedules`) | hoopR ESPN player box scores (`espn_nba_player_boxscores`); ESPN injuries (display snapshots, 42c) | The Odds API (free plan, game lines only) | PrizePicks |
| NHL | NHL web API (`api-web.nhle.com`) | NHL stats REST per-game skater and goalie reports (45b); sportsdataverse fallback choice; ESPN injuries and probable goalies (45f, display and board filter) | Odds-API.io (DraftKings and FanDuel; Bet365 until 2026-10-26) | PrizePicks |
| WNBA / Soccer | > TODO | > TODO | The Odds API (per plan) | > TODO |

**Backtest-only source:** 26c reads Valuebetennis season CSVs (ATP and WTA
results with Pinnacle opening and closing odds, 2021 onward, CC BY 4.0),
downloaded once into a gitignored local folder. Nothing ingests them into the
database and no app code fetches the site.

**Two odds providers, easily confused.**
- **Odds-API.io** (`api.odds-api.io`, `ODDS_API_KEY`): tennis, NFL (36a) and
  NHL (45d) DraftKings/FanDuel game lines. Account contract: 100 requests an
  hour and **two books, shared across sports** (DraftKings and FanDuel since
  2026-10-27); Bet365, sharp books and exchanges are paid only. Bet365 became
  paid-only on 2026-10-26; free keys get a 403. Tennis receives moneylines
  only from both free books.
- **The Odds API** (`api.the-odds-api.com`, `THE_ODDS_API_KEY`): NFL, NBA and
  tennis total games (48b: 1 credit per tour-level key with a stored match,
  usually 1 to 4 a day, stopping below 150 credits so tennis yields first),
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

**Structure (items 38 and 57, 2026-10 and 2026-11):** one command-bar shell
across every page (sport tabs, Home, Slate / Props / Model, Tools, How it
works, and a `/` search that jumps to any game, team or player). Every sport's
slate has the same shape: a period line with one Previous / period picker /
Next control, a gray reference digest (none for NHL; tennis shows gray model
leans while its picks are off), a one-line legend stating source and
freshness once, and one dense row per game or match. Props are dense table
rows with a `+N alts` chip and Last 5 bars against the line (62), and every
prop row opens its player page (50, 53). The theme above is unchanged.

Mobile is a real target: `useIsMobile` swaps the nav to a drawer. Item 68
adds display polish only: tabular figures, balanced headings, squircle
corners, 44px tap targets, View Transitions API crossfades between sport pages
(the app uses `HashRouter`, so React Router's `viewTransition` prop is
unavailable and `useViewTransitionLocation` feeds `<Routes location>`; Back
stays instant), table
skeletons on slates and prop boards, and swipe-to-dismiss drawers; all motion
is skipped under `prefers-reduced-motion`.

**Guiding principle:** the user should scan a slate and see the actionable plays
without reading everything. Quality flags and gray-versus-green cut the list
down.

### Web routes (HashRouter)

Sport routes come from `SPORTS` (`web/src/utils/sportNav.ts`) and
`SPORT_PAGES` (`web/src/routes/sportPages.tsx`); every sport has Slate, Props
and Model views.

| Sport | Slate | Props | Model | Detail pages |
|---|---|---|---|---|
| Tennis | `/tennis` | `/tennis/props` (source, tour, surface, format and line-type filters; Why over / Why under panel) | `/tennis/model` | `/tennis/match/:matchId`, `/tennis/player/:playerId` (props as tabs, projection history) |
| NFL | `/nfl` (opens the current week) | `/nfl/props` | `/nfl/model` | `/nfl/game/:gameId`, `/nfl/player/:playerId` (model and line-only markets as tabs) |
| NBA | `/nba` (`?date=`) | `/nba/props` | `/nba/model` | `/nba/game/:gameId`, `/nba/player/:playerId` (teammate-out split, 69) |
| NHL | `/nhl` (`?date=`) | `/nhl/props` (starting-goalie filter) | `/nhl/model` | `/nhl/game/:gameId`, `/nhl/player/:playerId` (projection history) |

Player-page state lives in the URL (`?market=`, `?form=10|opp`, history
filters such as `?hstat=`), so Back restores the row that was opened.

- `/` - cross-sport home (55): a card per sport, a gray "Largest gaps across
  sports" table, and model record cards reading "Accruing" until a slice adopts
- `/tools` - five client-side calculators (61), checked against
  `api/tests/fixtures/calculator_cases.json` by both pytest and Vitest
- `/how-it-works` - public explainer (37b)
- `/admin` - sign-in card until the owner enters `ADMIN_API_KEY` (37a); hidden
  from visitors
- `/parlays` - bankroll builder, hidden from the nav since 2026-09-25
- `/props`, `/live-odds`, `/bets` redirect to `/`; `/nfl/prospects` to `/nfl`

> Only standard full-game lines with a sufficient sample receive an edge. The
> sportsbook anytime-TD probability is displayed beside the model, not blended,
> until 25c passes. Injury, depth, goalie and teammate-out context warns and
> filters but never changes a projection, edge or rank. The muted NFL game
> model is never colored, sorted by, or added to a signal board.

### API routes

| Prefix | Endpoints |
|---|---|
| `/tennis` | `predictions/today`, `predictions/best-picks`, `matches/{id}`, `matches/{id}/odds-history?market=moneyline\|total_games`, `matches/{id}/recent-form`, `model/predictions`, `model/prizepicks-lines`, `model/prop-tiers`, `players/{id}`, `players/{id}/serve-return`, `players/{id}/matches?limit=`, `players/{id}/props`, `players/{id}/projection-history`, `bankroll/today`, `parlays/suggested` |
| `/tennis/props` | `prizepicks`, `prizepicks/audit`, `prizepicks/{id}/reasons` (63), `dk` |
| `/nfl` | `current-week`, `games`, `games/{id}`, `games/{id}/context`, `games/{id}/line-only-props`, `line-only-props`, `players/{id}`, `players/{id}/other-markets`, `projections`, `slate`, `game-notes`, `model/ranking?season=&model_version=`, `model/prop-lines?season=`, `model/game-line-clv?season=`, `model/over-probability-fit` |
| `/nba` | `slate?date=`, `slate/gaps?date=`, `props?date=`, `games/{id}`, `games/{id}/props`, `games/{id}/line-only-props`, `players/{id}/props?date=`, `model/ranking?season=` |
| `/nhl` | `slate?date=`, `props?date=`, `games/{id}`, `games/{id}/line-only-props`, `players/{id}/props?date=`, `players/{id}/projection-history`, `model/ranking` |
| `/ask` | `POST /ask` (SSE stream, off unless `ASK_ENABLED`), `status` |
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
- **Env vars:** `DATABASE_URL`, `ODDS_API_KEY` (Odds-API.io, tennis and NFL/NHL DraftKings/FanDuel), `THE_ODDS_API_KEY` (The Odds API, NFL and NBA), `LIVETENNIS_API_KEY`, `LIVETENNIS_TIER`, `ADMIN_API_KEY`, `API_ENV` (`dev` default, or `production`), `CORS_ORIGINS` (JSON list), `RATE_LIMIT_DEFAULT` (`120/minute`), `RATE_LIMIT_HEAVY` (`10/minute`), `ANTHROPIC_API_KEY` (Ask Lineform, read only through Settings, never in the web build; an Anthropic Console monthly spend limit backs the in-app daily cap)
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
  - `nfl-scores.yml` (daily 07:17 and 13:17 UTC; fix 2026-10-02, times moved 2026-11-09) - `python -m app.ingest.nflverse --schedule-only`, then `nfl_slate_snapshot`, so finished games read final the next morning instead of on Tuesday. Display only: grading still waits for Tuesday's player stats.
  - `nfl-weather.yml` (daily 11:17 UTC, plus 19:17 UTC Sun/Mon/Thu for primetime) - weather snapshots for upcoming games (`nfl_game_weather_snapshots`).
  - `nba-ingest.yml` (daily 09:30 UTC, October to June) - hoopR NBA schedule and box scores, then `prizepicks_nba --relink` (20b, 20c), then the NBA forward ranking check report (20g4, read-only, on the Summary page).
  - `nba-prop-lines.yml` (daily 16:30 and 22:15 UTC, October to June) - free PrizePicks NBA line snapshots before tip-off (20c); then (20g3) `app.ingest.nba_prop_predictions` freezes the reference projection and P(over) for every modelled line not yet tipped off.
  - `nba-odds.yml` (daily 15:00 and 22:30 UTC, October to June) - NBA moneyline, spread and total, 3 credits a run, skipped below 100 remaining credits or with no game in the next 2 days (20d).
  - **NHL (45b-45f), September-June, manual dispatch available:**
    `nhl-ingest.yml` at 09:45 UTC loads schedule and recent box scores via
    `python -m app.ingest.nhl_api`, then relinks stored props provider-free,
    and ends with the read-only NHL forward ranking check on its Summary page
    (56d).
    `nhl-prop-lines.yml` at 17:15 and 22:45 UTC runs
    `python -m app.ingest.prizepicks_nhl`; an exhausted PrizePicks rate limit
    exits 75, then freezes pre-puck-drop predictions with
    `python -m app.ingest.nhl_prop_predictions` (56c4; first GitHub run passed
    2026-11-05). Both use only `DATABASE_URL` and `contents: read`.
    `nhl-odds.yml` at `40 */3 * 1-6,9-12 *` runs
    `python -m app.ingest.nhl_odds_io`, needs `DATABASE_URL`/`ODDS_API_KEY`,
    uses `contents: read`, a ten-minute timeout and non-canceling concurrency
    for its own runs. Default two-day window and floor 20; one event request
    plus one odds request per ten matches, no The Odds API credits. Dry run
    spends hourly requests but makes no inserts/commit; HTTP/network/payload
    failure exits 1 without retry, quota stop exits 75, and missing coverage
    is reported. `nhl-context.yml` at `17 * * 1-6,9-12 *` runs
    `python -m app.ingest.nhl_context` for current injuries and Eastern
    today/tomorrow goalie scoreboards, using only `DATABASE_URL`, read-only
    repository permissions, serialized non-canceling runs and ten-minute
    timeout. It makes no odds or PrizePicks request. `--dry-run` enforces
    read-only candidate reads and requires no new tables; `--date YYYY-MM-DD`
    scopes goalies only, never historical injuries. Each
    feed/date commits separately; failure leaves earlier successes intact,
    exits nonzero, and prior snapshots age stale. Bounded retry and Retry-After
    behavior is documented in `docs/nhl-context.md`.
    Render runs no cron.

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

> Gaps between the two plans and unowned follow-ups. Resolved questions from
> earlier refreshes were dropped; their answers are in the build plan, the
> archives, or the sections above. Numbers restart here.

**Decisions for the owner**

1. **41c versus 66b order** (see What's left). Both change the served tennis
   ensemble against the same base.
2. **No NBA or NHL "adopt in ranking" item** (see What's left).
3. **Parked items sit in the open list.** 16f, 48d2 and 48d3 keep parents 16
   and 48 reading as unfinished. Drop them or move them under one Parked
   heading.
4. **Bankroll builder (item 10)** is hidden from the nav with its route and
   API kept. Moneyline picks are off, so it has nothing validated to size.
   Record its retirement, or name what would bring it back.
5. **Item 8 (best picks) reads "ranks +EV plays"** while tennis moneyline
   picks have been off since 2026-10-01. Record what would re-enable them.
6. **Which stored NFL signals to test next** is undecided: `air_yards_share`
   and `wopr` are stored but unused; injuries and depth are display only.
7. **27g's fit used 2025 residuals** (cross-fitted), bending "fit on 2024
   only". Confirm the exception, or require a development-season fit for any
   later distribution work.

**`project-plan.md` lags the build plan** (prose only; no scope change)

8. §3 and §7 name none of the NFL, NBA or NHL pages, game notes, player pages,
   home page, calculators, filters or record strip (items 29-30, 33, 36,
   39, 42, 50-64), and §3's "Planned sports" paragraph predates items 19-20
   and 45.
9. §3 does not mention model validation work: items 26, 27, 28, 40, 44, 48,
   49, 65, 66, 67, or the frozen-prediction and forward-check pipeline.
10. §4 says revision `0019` and describes `nfl_*` as the NFL schema; the
    schema now runs to `0054` on shared `sport_*` tables. Its "Planned NFL
    data" table (19j-19m) shipped. NFL weather (`0022`) is in neither plan.
11. §4 and §8 still name Bet365 as an Odds-API.io book (paid-only since
    2026-10-26; the code uses DraftKings and FanDuel), and do not record that
    tennis is moneyline-only with tour-level totals from The Odds API (48b).
12. §2 calls the demo planned while §8 says it is live; §4 says model files
    are gitignored while §8 says they are tracked (they are tracked).
13. §7 still names the discarded `prototypes/theme.css`; the tokens live in
    `web/src/index.css`.

**Checked build-plan lines that overstate or misstate what shipped**
(history; reword only if the plan should match)

14. Item 3 says "weekly refresh"; ELO refreshes daily on the local task.
15. Item 5 names The Odds API for tennis; tennis odds use Odds-API.io.
16. 27e says "passing volume rises when trailing"; what was adopted was
    dropping the moneyline for passing. 27f's projection was rejected (only
    settlement changed). 27g shows 2 of 8 markets.
17. Item 28 says "Tuesday line"; the rule grades the earliest in-window line.
18. Item 35 lists nine line-only markets; 39c promoted Rec Targets, leaving
    eight.
19. The build plan names prop boards `/nba/board` and `/nhl/board`; the
    registry routes are `/<sport>/props`.

**Unowned technical follow-ups**

20. `player_rolling_stats` columns `aces_per_game`, `df_per_game` and
    `break_pct` hold per-serve-point rates and break points converted. The UI
    labels are fixed; the names are not. Rename through a migration, not
    silently.
21. Leftover tables: `player_match_stats_pre_0038` (0038's downgrade
    snapshot) and `bets` (retired 2026-10-15) await a migration that drops
    them.
22. Legacy `sofascore_id` columns on `players` and `matches`; waits for item
    22's tennis convergence.
23. The Bet365 parser misfiled game handicaps as `set_handicap`. Only stored
    rows are affected now; fix through `/fix` before anything prices set
    handicaps.
24. `get_slate_lines` stalled intermittently (33-240 s, 17b and 17c); a
    `/debug` comparing slow and fast `EXPLAIN ANALYZE` was recommended and has
    not run.
25. Whether tennis `prop_projection_snapshots` merges into
    `sport_prop_predictions` is open; it waits for item 22.
26. Ask Lineform's per-IP limit and in-memory spend cap reset on restart; the
    Anthropic Console limit is the backstop. A persisted cap would need a
    table and a manual migration.
27. The NBA board response was 4.88 MB for one busy date (42b). Hosted
    latency and memory for it were not measured.
28. Hosted and runner acceptance is unverified by this refresh for recent
    work: tennis workflow split, 41a/41b jobs, NHL workflows, and items 50
    onward unless their archive says otherwise.

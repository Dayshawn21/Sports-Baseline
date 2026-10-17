# Project Plan

> Adopted from an existing codebase via `/adopt`. Sections 1, 2, 6, and parts of 7
> came from the user interview; sections 3, 4, 5, and 8 were read from the code.
> Items marked `> TODO (confirm)` are inferences that need your review.
>
> Updated 2026-09-16 with shipped NFL data, prop-line, and slate work.

## 1. Problem - What problem are we solving?

Sports betting markets are efficient enough that casual bettors lose, but not so
efficient that every line is correctly priced. Finding the mispriced ones by hand
means reconciling player form, surface history, head-to-head records, ELO, and
live book odds across several sites, for dozens of matches a day. That is hours of
work per slate, and it does not scale past a handful of matches.

This project does that reconciliation automatically. It ingests matches, odds,
player stats, and props on a schedule, runs a calibrated model ensemble against
them, and surfaces only the plays where the model's probability diverges from the
market's implied probability by enough to be worth a bet. The output is a ranked
shortlist with stake sizing, not a wall of data to interpret.

The second problem it solves is honesty about results. Picks that are never
graded cannot be evaluated, so the app stores its predictions before each start
and grades them against results, making the edge measurable rather than assumed.
Placed bets are tracked outside the app, in Pikkit.

**Tennis is the first sport, not the only one.** The intended scope is NFL, NBA,
WNBA, and soccer as well. The core machinery is deliberately sport-agnostic in
principle: ingest a schedule, ingest odds, model an outcome, compare to market,
size a stake, track the result. Only the feature engineering and the market shapes
are sport-specific. Tennis came first because it is a two-outcome sport with no
draws, dense daily volume, and freely available ELO and per-match statistics,
which made it the cheapest place to prove the pipeline.

## 2. Users - Who is this for?

**A single user: the project owner.** Every design decision reflects that, and
that is the correct assumption for the foreseeable future. There are no accounts,
no per-user data scoping, and route protection is a single shared `X-API-Key`
secret on the admin routes that defaults to open on localhost.

**Multi-user is explicitly out of scope for the next one to two years**, in line
with the monetization deferral in section 6. The following are therefore accepted
design decisions rather than debt to be repaid soon:

- no stored data carries a user id
- the only login is the owner's, for the admin surface (item 37a); visitors are
  anonymous and read-only
- the app runs locally against a hosted Neon Postgres today; a public read-only
  demo is planned (item 37), and it adds no accounts

Do not add accounts, auth, or per-user scoping to any feature spec unless this
section changes first. Sport coverage is the priority; user management is not.

The owner login (37a) is not multi-user: one credential, no sign-up, no stored
user data.

## 3. Features - What does the MVP need?

These already exist and are working. This section describes the shipped app.

**Match intelligence**

- Daily ATP and WTA match ingest with today and tomorrow lookahead
- Ensemble win probabilities blending ELO, LightGBM, and de-vigged market odds
- Tour-specific ensemble weights (ATP leans on market, WTA leans on model)
- Quality flags surfacing stale odds, partial features, and ELO fallbacks
- Head-to-head records, surface splits, and rolling player form
- Match detail, player, and model track record pages (build-plan item 32),
  replacing the player comparison modal

**Betting surfaces**

- Best picks: ranked +EV plays derived from the ensemble
- Props: PrizePicks and DraftKings ingest with projection and EV scoring
- Props audit view for verifying projection quality against posted lines
- Bankroll builder with Kelly-based stake sizing
- Parlay suggestions

**Operations**

- Admin surface for flagged players, with manual stat and ELO refresh
- Scheduled ingest via GitHub Actions and a local Windows batch fallback

### Planned sports, in intended order

Tennis is shipped. NFL data sourcing, schedule and stats ingest, prop-line
linking, the unified slate, current-season loading, and book-odds ingest are
shipped out of order in a separate `nfl_*` stack. The current NFL projection is
a conservative player-history and game-moneyline model; it still needs
opponent-adjusted prop projections and player-usage inputs before it becomes a
full matchup model. NBA, WNBA, and soccer follow after the multi-sport foundation
converges the tennis and NFL stacks. Each new sport needs a schedule source, an
odds source, a model, and market shapes. It reuses the ensemble blending, EV
ranking, Kelly sizing, and UI shell.

NFL game lines (spread, moneyline, total) are a separate model from player
props: team ELO first, then play-by-play efficiency and totals context, each
backtested against closing lines before it is shown as more than display
(build-plan item 24).

**What each sport breaks that tennis does not:**

| Sport | New constraint it introduces |
|---|---|
| NFL | Teams rather than individuals. Weekly rather than daily cadence, so far fewer rows and a much smaller training set. Spreads and totals matter more than moneyline. |
| NBA | Teams, but back to a dense daily schedule. Heavy player-prop volume. |
| WNBA | Same shape as NBA, but a shorter season and thinner public data. |
| Soccer | **Three-way markets.** Draws break the two-outcome assumption baked into the ensemble, de-vigging, and every `p1`/`p2` column in the schema. |

Soccer is the hardest and belongs last. The two-outcome assumption is currently
load-bearing in `core/odds.py` de-vigging, in `ensemble.py`, and in the `p1_*` /
`p2_*` column naming throughout the schema.

## 4. Data - What are we storing?

Postgres, managed by Alembic (currently at revision `0019`).

| Table | Holds |
|---|---|
| `players` | Player identity, tour, TennisAbstract slug, livetennis id |
| `player_aliases` | Name variants for cross-source matching |
| `matches` | Scheduled and completed matches, tournament, surface, round |
| `match_odds` | Book odds per match, timestamped for staleness checks |
| `player_elo` | ELO ratings, overall and by surface |
| `player_rolling_stats` | Serve/return form over rolling windows, with surface and contextual splits |
| `h2h` | Head-to-head records between player pairs |
| `predictions` | Stored model output per match |
| `props` | Player prop lines from PrizePicks and DraftKings |
| `bets` | Retired 2026-10-15 (bets tracked in Pikkit); kept until a later migration drops it |
| `nfl_teams` | NFL team identity and codes |
| `nfl_players` and `nfl_player_aliases` | NFLverse players and provider-name overrides |
| `nfl_games` | NFLverse schedule, teams, scores, and status |
| `nfl_player_weekly_stats` | Per-player, per-game passing, rushing, receiving, and fantasy stats |
| `nfl_prop_lines` | PrizePicks snapshots, segment, line type, and resolved player or game links |
| `nfl_prop_predictions` and `nfl_prop_results` | Reserved NFL prop model outputs and settlement records |
| `nfl_team_elo` (planned, 24a) | Pre-game team ELO per team per week, derived from NFLverse scores |

Model artifacts live on disk in `api/models/` and are deliberately gitignored
because of their size. `ModelRegistry` loads them once at API startup.

**Cross-source identity is the hard part of this schema.** Players arrive from
livetennisapi, TennisAbstract, Odds-API.io, and PrizePicks under different name
spellings, which is why `player_aliases` and the slug columns exist. Every new
sport adds its own sources and its own spelling mismatches, so this machinery
generalizes rather than being replaced.

**The schema is tennis-shaped and will need generalizing** (build-plan item 17).
The specific assumptions that do not survive contact with other sports:

- `matches` has `surface`, `round`, and `best_of`, which are tennis-only
- `matches` links two `players`, but NFL, NBA, and WNBA link two *teams*, and
  there is no `teams` table
- `p1_*` / `p2_*` naming assumes exactly two outcomes, which soccer breaks
- `player_rolling_stats` columns are serve and return metrics specific to tennis
- `props.stat_type` values (`aces`, `double_faults`) are tennis-only

None of this is wrong today. It is the cost of having proven the pipeline on one
sport first, and item 17 is where it gets paid.

**Planned NFL data (build-plan 19j to 19m), one dataset per feature, each
backtested before it feeds a projection:**

| Dataset | Stored as | Why |
|---|---|---|
| Red-zone usage (19j) | per-player, per-game carries and targets inside the 20 and inside the 5, aggregated from NFLverse play-by-play; raw plays not stored | predicts touchdowns better than total volume |
| Weekly rosters (19k) | player, season, week, team | fixes last-write-wins `nfl_players.team_id` |
| Injuries and depth charts (19l) | status and depth order per player per week, fetched pre-game | role changes a history-based model misses |
| Snap counts (19m) | snap share per player per game | steadier RB and TE role signal than targets |

Next Gen Stats is not planned: it measures efficiency, while prop outcomes are
driven more by volume. Injury data only helps when fresh, so 19l needs a
schedule later in the week than the Tuesday stats ingest.

**NFL is deliberately parallel until item 17.** Its normalized `nfl_*` tables
avoid forcing team sports into tennis matches, but duplicate cross-sport
concepts. `nfl_players.team_id` is the most recently loaded roster, not historical
team membership, so future NFL models need week-aware roster and matchup features.

**NBA data (20a, decided 2026-10-05).** NBA uses ESPN ids throughout:
hoopR's ESPN release files (free GitHub release assets, the NFLverse
shape) for schedules and per-game player box scores, with the ESPN site
API as the fallback on the same ids. Games, players and teams go in the
shared `sport_*` tables with `sport = 'nba'`; box scores in a new
`nba_player_game_stats`. `season` is the start year (2025 = 2025-26).
NBA's prop period is the regular-season week (Monday to Sunday, Eastern
date, week 1 holds opening night), stored in `sport_games.week`, so the
shared ranking rule's four-period minimum means four weeks, as for NFL.
No NBA team-rating tables are planned. Injuries come from ESPN's feed for
display; the official NBA injury report is the source if a later item
tests availability in a model, because its archive is backtestable.

## 5. Tech - What stack are we using?

**Backend**

- Python 3.11, FastAPI 0.115, Uvicorn
- SQLAlchemy 2.0 async over psycopg3, Alembic migrations
- Pydantic 2 and pydantic-settings for config and schemas
- LightGBM, XGBoost, scikit-learn, joblib for models and calibration
- Playwright, httpx, requests, tenacity for ingest

**Frontend**

- React 19, Vite 7, TypeScript in strict mode
- Ant Design 5 for components, Tailwind v4 for utility styling
- TanStack Query 5 for server state, axios for transport
- HashRouter, `~/*` path alias to `src/`

**Why this split:** the ML libraries are Python-only, so the model layer sets the
backend language. The frontend is a plain Vite SPA rather than a metaframework
because it is a pure client for an API that already exists.

**Data sources, current and needed**

| Sport | Schedule | Stats / ratings | Odds | Props |
|---|---|---|---|---|
| Tennis | livetennisapi | TennisAbstract (ELO, per-match stats) | Odds-API.io | PrizePicks, DraftKings |
| NFL | NFLverse | NFLverse weekly player stats | The Odds API (free plan: us books, Pinnacle via eu); Odds-API.io (Bet365, DraftKings; free plan's 2-book cap, shared with tennis) | PrizePicks, The Odds API (anytime TD) |
| NBA | hoopR ESPN releases (`espn_nba_schedules`) | hoopR ESPN player box scores (`espn_nba_player_boxscores`); ESPN injuries (display) | The Odds API (free plan, game lines only) | PrizePicks |
| WNBA / Soccer | > TODO | > TODO | The Odds API | > TODO |

**Cost constraint: prefer free sources.** The stated preference is to source as
much NFL data as possible for free, and the same applies to the sports after it.
Two odds providers are in use: Odds-API.io for tennis and for NFL Bet365 and
DraftKings game lines (item 36; its free plan allows two books, shared across
sports, and no sharp books), and The Odds API for NFL and NBA, including
Pinnacle through its `eu` region as the fair-price reference.
Between them odds are covered across sports, so the gap for each new sport is
schedule and stats, not pricing. The Odds API free plan gives 500 credits a month,
and player props are billed per game per market, so NFL prop markets are added one
at a time.

NFLverse publishes the NFL schedule and weekly player-stat CSVs as public release
assets. PrizePicks supplies player prop lines. Real book odds come from The Odds
API: game markets through build-plan item 19f (a prerequisite for the projection
model in 19e), and anytime-TD player prices through item 19i.

**NFL work reopens for items 25 and 27, superseding the 2026-09-19 closure.**
Items 18, 19, and 24 stay complete, and NFL game-line modelling stays closed.
Item 28 (decided 2026-09-26) reopens game lines for one read-only check only:
whether the closing line moves toward the existing model from the stored
Tuesday line. It adds no signal and changes no model. Only a passing
pre-registered verdict would justify a later item that shows a bettable tag.
Item 25 is
not really NFL work: 19i proved the stored sportsbook prop prices are usable but
never validated them, and the de-vigging they need is a cross-sport concern the
tennis ensemble (item 6) already solves separately. One shared implementation is
what item 17 would have to converge anyway.

**Item 27 reopens NFL prop modelling (decided 2026-09-26).** A review found the
prop projection model (19e, 19g, 19h) was never validated. Graded against 2026
week 2 PrizePicks standard lines, it hit 49.4% of 681, against the 57.7% per-pick
break-even of the owner's 2-3 pick Power entries (about 52.4% for sportsbook
props at -110). Item 27 grades the model forward, tests each input change on 2025
results, and replaces mean-minus-line edges with an over probability, adopting
each change only when its pre-registered check passes. The probability layer is
written sport-agnostic in `app/core/`, so item 17 converges it rather than
duplicating it.

**Anytime TD cannot be validated on history.** The Odds API sells current
markets, not past ones, so `nfl_player_prop_odds` only holds prices from item
19i onward. There is no historical holdout, and the evidence has to accrue
forward week by week. Item 25 is sequenced around that: the de-vig (25a) and the
accrual job (25b) are buildable now, while adoption (25c) waits on a sample that
does not exist yet and may never justify the change.

## 6. Monetize - How will this make money?

**It does not, and will not before roughly 2028.** Monetization is explicitly
deferred one to two years from August 2026. This is a personal tool that makes its
owner money by winning bets, not by selling anything.

Consequences for how work gets planned, all of them simplifying:

- No accounts, billing, subscriptions, or entitlement checks
- No per-user data scoping; the shared `X-API-Key` remains sufficient
- No public marketing surface, onboarding flow, or pricing page
- No compliance, ToS, or responsible-gambling disclosure work that a paid picks
  service would require

Spend the effort on sport coverage and model accuracy instead. Revisit this
section before starting any product-stage work; until it changes, treat
multi-user features as out of scope rather than merely unscheduled.

## 7. UI/UX - How should this look and feel?

A dark, dense, data-first interface, restyled in build-plan item 31 after OddsJam
(odds tables), Outlier (prop cards) and Robinhood (large numbers, one signal
color). The theme is defined as CSS custom properties in `web/src/index.css`,
ported from `prototypes/theme.css`: true-black background (`#000`), near-black
cards, low-contrast borders, green (`#00c805`) only for a positive signal, and red
(`#ff5000`) only for negatives, with everything else grayscale. Tour accent colors
still carry meaning (ATP blue `#3b82f6`, WTA pink `#f43f7b`, Challenger teal
`#14b8a6`). Green follows the rule below: an unvalidated number never gets it.

Typography is deliberately three-part: Barlow Condensed for display, DM Sans for
body, JetBrains Mono for numbers. Numeric alignment matters here because the whole
product is scanning columns of probabilities and prices.

Mobile is a real target, not an afterthought. There is a `useIsMobile` hook and a
drawer-based navigation swap.

The design principle throughout: **the user should be able to scan a slate and see
the actionable plays without reading everything.** Quality flags and EV ranking
exist to cut the list down, not to decorate it.

**An unvalidated number is context, never a pick.** A signal that has not passed
a held-out backtest may be displayed beside the market, but it must not colour a
row as a signal, drive an edge, set a rank, or reach a board of plays. The NFL
game-model strip (item 24d) and the sportsbook anytime-TD probability (item 19i)
are both display-only under this rule. The sportsbook probability may drive edge
and rank for anytime TD, and only anytime TD, once build-plan item 25c passes its
pre-registered adoption rule; until then it stays context. The tennis model track record page (item 32b)
follows the same rule: its grading numbers stay gray unless one beats its stated
baseline or break-even by more than 2 SE. The NFL prop edge follows it too: 27a
graded the model at 48.1% against a 57.7% break-even, so the edge is shown gray on
the slate, prop board, and detail pages until build-plan item 27h adopts a slice.
No UI text is set below 11px, including micro-labels, tags, and table cells.

## 8. Deployment - Where and how will this ship?

Hosted read-only demo on Render since 2026-10-16 (item 37d), deployed from
`render.yaml`; still runnable locally.

- API: Render web service `sportapp-api` (always-on `0.5c-512mb` plan, $7 a
  month, Virginia, beside Neon),
  `uvicorn app.main:app --proxy-headers`; locally on port 8000
- Web: Render static site `sportapp-web`, built with `VITE_API_BASE_URL`;
  locally the Vite dev server on port 3001 proxies `/api` and `/health`
- Database: hosted Neon Postgres via `DATABASE_URL`
- Scheduled ingest for every sport runs in GitHub Actions using repo secrets;
  Render runs no cron jobs

**Environment variables** (see `api/app/config.py`): `DATABASE_URL`,
`ODDS_API_KEY` (Odds-API.io: tennis, and NFL Bet365 and DraftKings),
`THE_ODDS_API_KEY` (The Odds API: NFL and NBA), `LIVETENNIS_API_KEY`,
`LIVETENNIS_TIER`, `ADMIN_API_KEY`, `API_ENV` (`dev` or `production`),
`CORS_ORIGINS`, `RATE_LIMIT_DEFAULT`, `RATE_LIMIT_HEAVY`.

**Health check:** `GET /health`.

Production settings are enforced since the 2026-10-15 hardening fix: with
`API_ENV=production` the API refuses to start without a strong `ADMIN_API_KEY`
or with a localhost or `*` CORS origin, and it rate-limits per client.

**Memory (37d):** 512 MB. Production never builds a heavy report per request.
The NFL slate (one row per week, refreshed by the four NFL workflows that write
its inputs) and the NFL line grading are precomputed into `report_snapshots`
and served from there, or a 503 when missing. The model files are tracked in
git, so a deploy needs no separate artifacts.

**CI (37c):** `verify.yml` runs the Verify command and a pinned gitleaks secret
scan on pull requests and pushes to `master`.

**Repository (37e):** public at `github.com/Dayshawn21/Sports-Baseline`, from a
one-commit snapshot; CI, the scheduled ingest and both Render services run from
it. Pre-37e history is kept in the archived private `SportAppV2`.

**Host:** Render (decided 2026-10-15, live 2026-10-16).

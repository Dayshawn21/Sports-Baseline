# Feature: 25b - Forward holdout accrual

**From build-plan:** 25b, under 25. Market-relative prop rating.
**Status:** complete

## Goal

Settle the sportsbook anytime-TD prices item 19i stores against what actually
happened, and report the accumulating sample: how many settled player-games
exist, and how the raw book price, the 25a de-vigged price, and the production
model score against them.

Nothing about the model, the edge, the rank, or the board changes. This is the
evidence 25c is gated on, and it also writes down the adoption rule now, before
any data exists, so the rule cannot be chosen after seeing the result.

## The sample today, measured 2026-09-19

| Fact | Value |
|---|---|
| Stored prop-odds rows | 2,627, all 2026 week 2, 15 games |
| Distinct priced players | 391 |
| Rows with no `player_id` | 254 of 2,627 |
| Week 2 games completed | 1 of 16 (DET @ BUF, which carries no book prices) |
| **Settled priced player-games** | **0** |

The first real sample lands with the Tuesday ingest after week 2 finishes, at
roughly 350 player-games a week. The report must therefore be correct and
readable at n = 0, and that is a build step, not an afterthought.

## In scope

- A pure settlement rule turning a priced player-game into scored, not scored,
  or excluded, with the did-not-play case handled explicitly.
- A repository read joining stored prices to game results, snap evidence, and
  the game's market total.
- A read-only CLI report, `python -m app.backtest.nfl_prop_market`, printing per
  week and cumulative: sample size, coverage counters, and log loss, Brier, mean
  predicted, and actual rate for three arms (raw book, de-vigged book, model).
- The pre-registered 25c adoption rule, recorded in the module and in this spec.
- A weekly run of the report in the existing Tuesday NFL cron.

## Out of scope

- **Any model, projection, edge, rank, board, or slate change.** That is 25c, and
  only on a passing rule. If a step starts touching `isRateable`, `edge`,
  `nfl_projection.py`, or the router's line assembly, it is out of scope.
- Any schema change. The odds table is append-only and weekly stats are already
  stored, so the settled sample is re-derivable on every run; nothing new is
  persisted. `nfl_prop_results` stays unwritten.
- Markets other than `anytime_touchdown`, and segments other than full game.
- Any web or API surface. The report is a CLI, like the other backtests.
- Re-fitting the 25a scorer constants. The report measures them; changing them
  is a later decision that needs this same evidence.
- Tennis, and any shared cross-sport de-vig. That is item 17.

## Build loop

Per [ai-interaction.md](ai-interaction.md): one small step at a time, diff shown
and approved before the next, a passing test in the same diff for any step that
adds logic.

## Build steps

- [x] **Step 1 - settlement rule in `app/core/nfl_prop_market.py`**

  A new pure module. `settle(touchdowns: int | None, offense_snaps: int | None)
  -> PropOutcome` returning `SCORED`, `NOT_SCORED`, or `DID_NOT_PLAY`:

  | Evidence | Outcome | Why |
  |---|---|---|
  | Weekly stat row, `touchdowns > 0` | `SCORED` | Rushing plus receiving, the market's definition |
  | Weekly stat row, `touchdowns == 0` | `NOT_SCORED` | Played and did not score |
  | No stat row, snap row with `offense_snaps > 0` | `NOT_SCORED` | Played, recorded nothing; NFLverse weekly stats omit statless players |
  | Neither | `DID_NOT_PLAY` | Inactive or not loaded; the book voids these, so they cannot be scored as misses |

  Plus `PropCase`, a frozen dataclass holding player, season, week, game,
  outcome, raw book probability, de-vigged book probability, and the model
  probability, all nullable except the keys.

  **Done when:** `pytest tests/test_nfl_prop_market.py` passes with a case per
  table row, including `touchdowns = None` with no snap row, and
  `offense_snaps = 0` with no stat row resolving to `DID_NOT_PLAY` rather than a
  miss.

- [x] **Step 2 - the settled read in `app/repositories/nfl.py`**

  `get_settled_prop_prices(db) -> list[SettledPropRow]`: one row per priced
  player per completed game, with the latest price per book collapsed by the
  existing `consensus` median, the outcome evidence, and the game's total.

  Four things this query has to get right:

  1. **Completed games only.** `g.status = 'completed'`. A scheduled game has no
     result and must not enter the sample as a miss.
  2. **Latest price per book,** the same `DISTINCT ON (game_id, player_id, book)
     ... ORDER BY fetched_at DESC, id DESC` shape as `get_slate_prop_odds`, so
     the settled price is the one the slate last showed.
  3. **`player_id IS NULL` rows are counted, not dropped.** They are a coverage
     number the report prints; an unresolved name silently vanishing would
     overstate linking quality.
  4. **The total comes from the book, with a named fallback.** Prefer the latest
     `nfl_game_odds` row with `market = 'total'` for the game; fall back to
     `nfl_games.total_line`; carry which source was used so the report can show
     it. 25a normalizes against the market total, and the settled sample has to
     use the same input or the de-vigged arm is not the number the app showed.

  **Done when:** running the report's data load against the live DB prints one
  row per completed priced player-game with its total source, and prints zero
  rows today, since no priced game is completed yet.

- [x] **Step 3 - the report, `python -m app.backtest.nfl_prop_market`**

  Assemble cases and print the table. Three arms on the same rows:

  | Arm | Source |
  |---|---|
  | `book_raw` | the stored consensus, margin included |
  | `book_devig` | `devigged_book_probabilities` from 25a, per game, deduplicated by player |
  | `model` | `production_probability` over `build_cases` from `nfl_td_backtest`, keyed by player, season, week |

  Scoring reuses `log_loss`, `brier`, and `NflTdScore` from
  `app/core/nfl_td_backtest.py` rather than restating them.

  **Arms are scored only on the common subset,** the settled rows where all
  three probabilities exist. A player with too little history has no model case,
  and comparing a book arm on 340 rows against a model arm on 300 is not a
  comparison. Print the subset size next to the settled count so the gap is
  visible.

  Coverage counters, printed every run: priced player-games, settled, excluded
  as `DID_NOT_PLAY`, unresolved `player_id`, games with no total (no de-vigged
  arm), and rows with no model case.

  **Done when:** `python -m app.backtest.nfl_prop_market` run today prints the
  per-week table with zero settled rows, the coverage counters, and an explicit
  line saying the sample is not yet assessable, with no crash, no division by
  zero, and no `nan`; a unit test over hand-built cases pins the per-week
  grouping, the common-subset rule, and the empty-sample path.

- [x] **Step 4 - pre-register the 25c rule and run weekly**

  Record the adoption rule as a module docstring block in
  `app/backtest/nfl_prop_market.py`, and mirror it in the Pre-registered rule
  section below, before any sample exists:

  - **Minimum sample:** 2,000 settled common-subset player-games.
  - **Pass:** `book_devig` beats `book_raw` on log loss **and** Brier on the
    accrued sample, and its mean predicted sits closer to the actual rate.
  - **Model context, not a gate:** the `model` arm is reported so 25c knows
    whether rating against the market is worth doing; it does not decide 25a's
    correction.
  - **Scored once.** The accruing sample is printed every week, but the pass or
    fail call is made one time, at the first run that clears the minimum. Weekly
    peeking is a coverage check, not a decision point.

  Then add the report to the Tuesday `nfl-ingest.yml` job, after the stats and
  snap steps so it settles the week that just finished. It spends no API credits
  and writes nothing, so it cannot break the ingest run.

  **Done when:** the docstring and this spec state the same rule; the workflow
  step runs the module from `api/` after the NFLverse steps; the file parses and
  the job's step ordering is checked by reading the workflow, since it cannot be
  run locally.

## Files / areas

| Path | Change |
|---|---|
| `api/app/core/nfl_prop_market.py` | New, Step 1: settlement rule and case shape, pure |
| `api/tests/test_nfl_prop_market.py` | New, Steps 1 and 3 |
| `api/app/repositories/nfl.py` | Step 2: `get_settled_prop_prices` |
| `api/app/backtest/nfl_prop_market.py` | New, Steps 3 and 4: the CLI report |
| `.github/workflows/nfl-ingest.yml` | Step 4: one weekly step |

No router, schema, web, or migration file is touched. If a step wants to, stop.

## Data / contracts

No migration and no persisted output. The sample is re-derived from
`nfl_player_prop_odds` (append-only), `nfl_player_weekly_stats`,
`nfl_player_snap_counts`, `nfl_game_odds`, and `nfl_games` on every run, so the
report is reproducible for any week already loaded.

`PropOutcome` and `PropCase` in `app/core/nfl_prop_market.py` are the shapes 25c
reads when it rates against the market. Name them now and do not rename them.

The de-vigged arm reuses `devigged_book_probabilities` and
`expected_distinct_scorers` from 25a unchanged. If the report suggests the
scorer constants are off, that is a finding to record, not a change to make here.

## Pre-registered rule for 25c

Fixed at 25b, before any settled sample exists. Copied into the report module so
it travels with the numbers.

- Minimum sample: 2,000 settled common-subset player-games.
- Pass: `book_devig` beats `book_raw` on log loss and Brier, and its mean
  predicted is closer to the actual rate.
- The `model` arm is reported as context and does not decide the correction.
- Judged once, at the first run clearing the minimum.

At roughly 350 settled player-games a week, that is week 8 to 12 of 2026 at the
earliest, matching what the overview already states. **A fail is a live outcome:**
19j, 19n, 24b, 24c, and 24e all failed their backtests, and 25c does not ship on
a near miss.

## Testing

The gate is on. Step 1 is pure logic and ships `pytest` cases in the same diff.
Step 3 ships a unit test over hand-built cases for grouping, the common-subset
rule, and the empty-sample path. Step 2 is SQL and is proven by running the
report against the live DB, per the Testing section of
[coding-standards.md](coding-standards.md). Step 4 is config and is verified by
reading the workflow.

Run `.venv\Scripts\python.exe -m pytest` from `api/` if bare `pytest` is not on
PATH.

## Notes for the AI

- **The report must be honest at n = 0 and stay honest.** Today there is nothing
  to settle. Anything that only looks right because a count happened to be zero
  is untested; build the empty path deliberately and test it.
- **Void is not a miss.** A priced player who did not play is the single easiest
  way to bias every arm downward at once. It has its own outcome and its own
  counter for that reason.
- **Do not deduplicate players away.** A player carries several lines in a game;
  25a already settled that the de-vig sums per player, not per line. The settled
  sample is one row per player per game, so the same trap applies here.
- **Do not touch 25a's constants or 19i's ingest.** The report reads what exists.
- `core/` purity is load-bearing: Step 1 takes plain numbers, no session, no rows.
- The report prints; it does not write files, rows, or state.
- No em dashes in new content, per the Writing section of the standards.

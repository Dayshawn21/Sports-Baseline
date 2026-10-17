# Feature: NFL game-line CLV check

**From build-plan:** feature 28
**Status:** completed (2026-09-26)

## Goal

Find out whether the closing line moves toward the display-only game model
(`nfl-elo-v1` spread, `NFL_SCORING_V1` total) from the earliest line the app
stored that week. If it does, betting that early number when the model disagrees
beats the close, and the strip becomes usable. 24b already showed the model
cannot beat the close itself, so this asks the narrower question.

This is a read-only weekly report with a rule fixed before any movement number
is read. There is no model, schema, or UI change.

## In scope

- A pure `app/core/nfl_game_line_clv.py` holding the pre-registered rule as
  tested constants, entry-line selection, per-pick CLV, the summary, and the
  one-time verdict.
- A repository read of candidate pre-kickoff odds rows and closing lines for
  completed 2026 regular-season games.
- `python -m app.backtest.nfl_game_line_clv [--season 2026]`, a printed report.
- A step in the Tuesday `nfl-ingest.yml` that writes the report to the Summary
  page.

## Out of scope

- Any change to the game-model strip, its caveat, or `/nfl/slate`. A passing
  verdict justifies a later build-plan item; it changes nothing here.
- Moneyline. It is redundant with the spread and the sample is too small.
- New odds fetches, credits, or cadence changes to `nfl_odds`.
- Re-tuning `nfl-elo-v1` or `NFL_SCORING_V1`, or testing a new signal.
- Historical seasons. NFLverse keeps closing lines only, so there is nothing to
  measure movement from before 2026.

## Pre-registered rule (fixed 2026-09-26, before any CLV number was read)

Coverage was checked by counts only: weeks 2-4 have stored pre-kickoff spread
and total rows for all 16 games, week 1 has none, and weeks 2-3 were fetched on
Thursday through Wednesday rather than Tuesday only. No line value or movement
was read.

**Sign.** Everything is in book sign: a home spread is negative when the home
team is favored.
- The model spread is `game_model_line(...).home_spread`.
- The entry line is the stored `nfl_game_odds.line` for `market = 'spread'`,
  which is already the home point in book sign (`core/nfl_odds.py`).
- The close is `-nfl_games.spread_line`, because NFLverse uses the opposite sign.
- Totals need no conversion.

**Model.** Replay pinned `NFL_ELO_V1` (`core/nfl_elo.replay`) and `NFL_SCORING_V1`
(`core/nfl_scoring_ratings.replay`) over `get_elo_games`. Both read only earlier
games, so the pre-game numbers are leak-free, and pinning the config means a
later code change cannot alter what is graded.

**Game eligibility.** A game is graded only when all of these hold. Every
exclusion is counted by reason in the report.
- It is a regular-season game with `status = 'completed'` and a non-null
  `start_utc`, `spread_line` / `total_line`, and scores.
- It has an entry line for that market.

**Entry line**, per game and market:
- **Window.** Rows fetched after the previous week's last regular-season kickoff
  plus 6 hours (so that week's results are known), and at least 24 hours before
  this game's kickoff. For week 1 of a season, the window opens 7 days before
  kickoff.
- **Books.** Only the lowercase The Odds API keys the current ingest writes. The
  capitalized `DraftKings` / `Bet365` rows from the 2026-09-17 run (an earlier
  code path) are excluded.
- **Choice.** The earliest `draftkings` row in the window. With none, the
  earliest row from any other allowed book (ties broken by book name, then id).

**Pick.** |model - entry| >= 1.5 points. The model's direction is
`d = sign(model - entry)`.

**CLV per pick.** `(close - entry) * d`, in points. Positive means the close moved
toward the model. Zero movement counts as 0 and stays in the mean.

**Verdict sample, per market.** Weeks are taken in order, and the sample is the
first whole weeks whose cumulative picks reach 150. Later weeks never change it.

**Verdict.** **Pass** only if the mean CLV minus 2 SE is above 0, where SE is the
sample standard deviation over sqrt(n). Otherwise the verdict is **reject**,
final for `nfl-elo-v1` / `NFL_SCORING_V1`. Until the sample is complete, the
report reads "accruing: N of 150 picks".

**Context only (cannot pass a market):**
- the entry-line lead time (median and minimum hours before kickoff)
- the share of picks that moved toward the model, away, or not at all
- the model side's W-L-P against the entry line
- separate rows for weeks 1-4 and 5+

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Rule constants, entry line, per-pick CLV** - create
  `app/core/nfl_game_line_clv.py`:
  - the constants: `PICK_THRESHOLD = 1.5`, `VERDICT_PICKS = 150`,
    `MIN_LEAD = 24h`, `WINDOW_AFTER_PREVIOUS_KICKOFF = 6h`,
    `FIRST_WEEK_WINDOW = 7 days`, `PREFERRED_BOOK = "draftkings"`
  - an `OddsCandidate` dataclass
  - `entry_line(candidates, window_open, kickoff)`
  - `clv_pick(market, model, entry, close, home_margin_or_total)`, which returns
    a `ClvPick` or None under the threshold

  Add `tests/test_nfl_game_line_clv.py`. *Done when:* tests pass covering:
  - DraftKings preferred over an earlier other book
  - fallback to another book, and the tie-break
  - capitalized books ignored
  - rows outside the window, or under 24h before kickoff, ignored
  - the threshold edge at exactly 1.5
  - spread sign (the model likes home, the close moves home, and CLV is positive)
  - totals direction
  - zero movement giving CLV 0
- [x] **Step 2 - Summary and one-time verdict** - in the same module, add:
  - `summarize(picks)`: n, mean CLV, SE, the toward/away/flat share, and W-L-P
    against the entry line, reusing `pick_record` from `core/nfl_game_lines.py`
    with the NFLverse-sign conversion
  - `verdict_sample(picks)`: the first whole weeks reaching 150
  - `verdict(summary)`: pass, reject, or accruing

  *Done when:* tests pass for:
  - SE on a fixed sample
  - a week that crosses 150 being included whole
  - later weeks not changing the sample
  - pass versus reject at the 2 SE boundary
  - n = 1 giving no SE, which reads as accruing, not a crash
- [x] **Step 3 - Repository read** - add `get_game_line_clv_rows(db, season)` in
  `app/repositories/nfl.py`. It returns, per completed regular-season game:
  - game key, week, and `start_utc`
  - the closing `spread_line` / `total_line`, and the scores
  - the previous week's last kickoff
  - every pre-kickoff `nfl_game_odds` spread and total row (book, line,
    `fetched_at`, id)

  Window filtering stays in core. *Done when:* a repository test in the existing
  `test_nfl_repository.py` style passes, and a local run returns 16 week-2 games
  with candidate rows.
- [x] **Step 4 - Report entry point** - create `app/backtest/nfl_game_line_clv.py`:
  - a pure `report(...)` that prints, per market:
    - coverage and exclusions by reason
    - the median and minimum entry-line lead (hours before kickoff), because a
      late entry line leaves little room to move, and the Tuesday GitHub run
      has not been reliable (overview open question 6)
    - an all-weeks row, plus weeks 1-4 and 5+ context rows
    - the verdict line
  - `_main` wires the repository, the pinned ELO and scoring replays, and core
    together, in the same shape as `nfl_prizepicks_lines.py`
  - only weeks whose regular-season games are all completed reach `verdict`.
    `verdict_sample` treats every week it sees as whole, so a half-played week
    could otherwise close the sample early and then change it. The report
    counts games in unfinished weeks as their own exclusion.

  *Done when:*
  - a formatting test on fixed picks passes
  - a local run prints weeks 2-3 as "accruing" for both markets
  - one game's entry line, close, and CLV match a manual SQL spot check
- [x] **Step 5 - Weekly Summary** - add a "Report game-line CLV" step to
  `nfl-ingest.yml` after "Refresh NFL game odds". It uses the same
  `tee` + `$GITHUB_STEP_SUMMARY` block as the PrizePicks grading step. *Done
  when:* the YAML parses and the step mirrors the existing report step exactly
  apart from the command and heading.

## Files / areas

- New: `api/app/core/nfl_game_line_clv.py`, `api/app/backtest/nfl_game_line_clv.py`,
  `api/tests/test_nfl_game_line_clv.py`
- Edit: `api/app/repositories/nfl.py`, `api/tests/test_nfl_repository.py`,
  `.github/workflows/nfl-ingest.yml`
- Reuse:
  - `core/nfl_elo.py` (`replay`, `NFL_ELO_V1`, `NFL_ELO_MODEL_VERSION`)
  - `core/nfl_scoring_ratings.py` (`replay`, `NFL_SCORING_V1`)
  - `core/nfl_game_lines.py` (`game_model_line`, `pick_record`)
  - `repositories/nfl.get_elo_games`

## Data / contracts

- No schema change. `nfl_game_odds`, `nfl_games` and `nfl_teams` are read only.
- **Load-bearing:** the rule constants in `core/nfl_game_line_clv.py` are the
  pre-registration. Changing one after a verdict exists is a new rule, not an
  edit. Any later "bet the entry number" item reads the verdict from here.
- `ClvPick` (core-internal): `game_key`, `week`, `market` (`spread` | `total`),
  `model`, `entry`, `close`, `direction` (+1 | -1), `clv`, `outcome` (the actual
  home margin or total points).

## Testing

- The test gate is on. Every function in `core/nfl_game_line_clv.py` gets
  focused tests with fixed timestamps. The report's formatter gets one test.
- Integration evidence: the Step 3 and Step 4 local runs with printed output,
  plus the SQL spot check.
- Final gate: `.venv\Scripts\python.exe -m pytest` from `api/`. No web change, so
  no web build is needed.

## Notes for the AI

- **Do not read or print any line movement before Steps 1 and 2 are merged into
  the branch.** Step 3's check is a row count only. The rule must be in code
  before the first CLV number exists.
- `nfl_game_odds` spread rows store the home point (`first_side = 'home'`) in
  book sign. `nfl_games.spread_line` is NFLverse sign (positive means the home
  team is favored). Verified in the 24b archive and `core/nfl_odds.py`.
- NFLverse fills `spread_line` / `total_line` before games are played (week 3
  had all 16 filled with 1 game completed). That is why only completed games
  count: their line is final.
- `core/` stays pure. Time windows take `datetime` arguments; never call
  `now()` in core.
- Don't use `nfl_team_elo` rows. Replaying in-process pins the model even if the
  Tuesday recompute is late or its config changes.
- The earlier plan said "newest pre-kickoff row". The coverage check showed
  several runs per week, so the newest row sits close to the close and would
  measure almost no movement. The earliest row in the window is the line that
  could actually have been bet early.

## Outcome

Shipped as a read-only report; nothing is adopted and the game-model strip is
unchanged. The verdict comes later, once 150 picks per market accrue.

First run, 2026-09-26 (`python -m app.backtest.nfl_game_line_clv`), after the
rule was in code. Week 2 only: week 3 was not finished, week 1 has no stored
lines, and every week-2 entry line came from one Friday run (median 47.3 hours
before kickoff), so it is not yet the Tuesday line the check is meant to grade.

```
SPREAD  games graded 15, picks 8   mean CLV +0.31  SE 0.16  toward/away/flat 3/0/5  W-L-P 3-5-0
TOTAL   games graded 15, picks 9   mean CLV +0.11  SE 0.11  toward/away/flat 1/0/8  W-L-P 5-4-0
Verdict: accruing (8 and 9 of 150 picks)
```

Spot check: `2026_02_CAR_ATL` matched raw SQL (model -3.957, DraftKings entry
+2.5 fetched 2026-09-18 17:42 UTC, close +2.5, CLV 0), and the replayed
`nfl-elo-v1` rating equals the stored `nfl_team_elo` value the strip shows.

**Follow-up:** the entry line is only as early as the odds fetches. Confirm
`THE_ODDS_API_KEY` is a GitHub repo secret (overview open question 6), or the
Tuesday `nfl-ingest.yml` run stores no early lines and the check measures
late-week movement only.

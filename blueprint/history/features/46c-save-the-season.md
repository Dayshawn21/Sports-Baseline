# Feature: Save the Season, week 1

**From build-plan:** feature 46c (parent 46, Analysis workspace)
**Status:** complete (2026-10-24)
**Branch:** `feature/46c-save-the-season`

## Goal

The first real Numbers Behind the Game notebook. One notebook,
`analysis/week01-save-the-season.ipynb`, answers "Can <team> save their
season?" for one team at a time (run for DAL and PHI, both 2-4 through week 6
of 2026). It teaches **luck vs skill**: a record says what happened, point
differential and efficiency say how good a team has played, and a rough
simulation turns that into a plain-language chance of reaching the playoffs.

Every number comes from functions in `analysis/lib/`, so the second team (and
every later Save the Season) is a parameter change, not a rewrite. The notebook
ends with both chart sizes, three thumbnails and draft posts for that team.

## Design reference

- No mockup. The chart follows `lib/style.py` (46a): title states the answer,
  logo blue marks the point, everything else gray, source line and credit.
- The thumbnail follows 46b's template; this feature only writes configs.
- The first DAL feed PNG from Step 5 is the visual reference, reviewed before
  PHI is run.

## In scope

- **`analysis/lib/nfl_team_report.py` (pure, unit-tested):** every
  calculation, on pandas DataFrames, no database or network.
  - record (wins, losses, ties) and point differential
  - Pythagorean wins (exponent 2.37) against actual wins
  - one-score record (games decided by 8 points or fewer)
  - turnover margin (giveaways vs takeaways) and its league rank, plus a
    carryover check: how well turnover margin through the cutoff week
    predicted the rest of the season in 2024-2025 (the only seasons with player
    turnovers stored; labelled a small sample)
  - efficiency ranks: offensive and defensive EPA per play and success rate,
    1 = best of 32
  - team ratings: point differential per game shrunk toward zero by a slope
    fitted on 2012-2025 history at the same week cutoff
  - home-field edge and game-margin spread, both measured from 2021-2025 games
  - per-game win chance and remaining strength of schedule (average opponent
    rating, ranked among 32)
  - a seeded Monte Carlo of the remaining schedule (10,000 seasons)
  - the playoff bar: share of 2021-2025 teams that made the playoffs at each
    final win total, and the resulting playoff chance
  - a verdict label and a luck label from pre-stated thresholds
- **`analysis/lib/nfl_queries.py`:** read-only SQL through `read_engine()` into
  DataFrames: completed and scheduled REG games with scores, team-game
  efficiency, team-game giveaways (interceptions plus fumbles lost from
  `nfl_player_weekly_stats`). Every query filters `sport = 'nfl'`.
- **`analysis/lib/nflverse.py`:** the one `nfl_data_py` wrapper.
  `load_schedules(seasons)` caches nflverse schedules to `analysis/data/` and
  returns them; the playoff bar reads playoff participants (`WC`, `DIV` games)
  from it, because the database stores regular-season games only.
- **`analysis/lib/team_posts.py` (pure, unit-tested):** builds the draft posts
  (video script, on-screen captions, X/Threads, LinkedIn, follow-up clip) from a
  `TeamReport`, under the README's language rules.
- **`analysis/tools/run_notebook.py`:** runs a notebook top to bottom from a
  clean kernel with parameters (`--param TEAM=PHI`), by injecting a cell after
  the parameters cell (papermill style) and executing a temporary copy with
  `nbclient`. The committed notebook is never modified.
- **`analysis/week01-save-the-season.ipynb`:** the template's nine sections,
  filled for this week. Parameters `TEAM = "DAL"`, `SEASON = None`,
  `THROUGH_WEEK = None` (latest week whose REG games are all final).
- **The chart (one point: the playoff chance):** bars of simulated final
  wins, the share of simulated seasons at each total. Totals where at least
  half of 2021-2025 teams made the playoffs are logo blue, the rest gray, with
  a labelled line at that bar. The title states the answer, for example
  "Dallas reaches the playoffs in about 1 of 5 seasons" (rounded to a plain
  fraction or percentage); the subtitle names the record and the cutoff week.
- **Team names:** a static 32-team table in `nfl_team_report.py` (city and
  nickname), because `sport_teams.name` holds the team code. The full name for
  prose; the nickname ("Cowboys") for headlines, so a thumbnail headline stays 3 to 5 words
  ("Can the Cowboys recover?").
- **Outputs (gitignored):** `output/week01-<team>-feed.png`,
  `output/week01-<team>-vertical.png`, three thumbnails per team,
  `output/week01-<team>-posts.md`.
- **Committed configs:** `thumbnails/configs/week01-dal.json` and
  `week01-phi.json`, written by the notebook.
- **Docs:** first glossary terms in `lib/glossary.md`; README folder map and
  "Run a notebook" gain the new modules and the runner.

## Out of scope

- Fumble recovery luck (needs play-by-play downloads; a later week can add it).
- Neutral-site flags for international games (treated as listed home games;
  stated as a caveat).
- A full league simulation with division races and tiebreakers. The playoff
  chance maps simulated final wins through the historical playoff bar instead.
- Any other week's notebook, Real or Lucky?, or posting anything.
- Any change to `api/`, `web/`, the database, models, probabilities or picks.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Season snapshot** - `nfl_queries.py` (games, efficiency,
  giveaways) and the first half of `nfl_team_report.py`: week cutoff, record,
  point differential, Pythagorean wins, one-score record, turnover margin,
  efficiency ranks, luck label, turnover carryover. *Done when:* tests cover
  each function on small hand-made frames (ties count half a win, a bye week,
  a week that is not fully final is excluded, takeaways are the opponent's
  giveaways in the same game); a scratch read prints the 2024-2025 carryover
  figure and DAL 2-4 and PHI 2-4 through week 6
  with point differentials -8 and -31, matching the database probe.
- [x] **Step 2 - Playoff bar** - `nflverse.py` (`load_schedules`, cached CSV in
  `analysis/data/`, a second call reads the cache with no network) and
  `playoff_rate_by_wins` in the report. *Done when:* tests cover the rate table
  on a hand-made schedule (bye teams count as playoff teams through `DIV`
  games; win totals outside the observed range clamp to 0 and 1); the real
  2021-2025 table prints, and its 14 playoff teams per season check out.
- [x] **Step 3 - Ratings and simulation** - shrinkage slope, home-field edge,
  margin spread, win chance, remaining strength of schedule, the seeded
  simulation, playoff chance, verdict label. *Done when:* tests pin the
  simulation (same seed, same result; a team favored in every game by a huge
  margin wins them all; win chances sum to the expected wins), the verdict
  thresholds and the slope fit on a synthetic history; real DAL and PHI
  playoff chances print with the fitted slope, edge and spread.
- [x] **Step 4 - Draft posts** - `team_posts.py`. *Done when:* tests check, for
  a fixed report, that the LinkedIn post is 150 to 250 words, no text contains
  an em dash or a banned word (bet, lock, guaranteed, pick, odds, parlay), the
  video script's first sentence states the verdict, and the "not betting
  advice" line is present.
- [x] **Step 5 - Notebook and runner** - `run_notebook.py` and
  `week01-save-the-season.ipynb` (all nine sections, both chart sizes, config
  and thumbnail render, posts file). *Done when:* the injection function has a
  test, and an unknown parameter name or a missing parameters cell fails with
  a clear message; `run_notebook.py analysis/week01-save-the-season.ipynb
  --param TEAM=DAL` runs clean on the notebook's `nbtg` kernel (a missing
  kernel fails naming the README's install line); the DAL feed and vertical PNGs are exactly 1080x1350 and
  1080x1920 and are shown for review; the committed notebook still has no
  outputs.
- [x] **Step 6 - PHI, glossary, docs and checks** - run for PHI, add the
  glossary terms, update the README. *Done when:* both teams' charts, three
  thumbnails each and posts files exist; both configs are committed; the
  glossary lists every term the notebook defines; `check_notebooks.py` passes;
  analysis tests pass; Verify passes, proving the app is untouched; the diff is
  limited to `analysis/` and `blueprint/`.

## Files / areas

- New: `analysis/lib/nfl_team_report.py`, `analysis/lib/nfl_queries.py`,
  `analysis/lib/nflverse.py`, `analysis/lib/team_posts.py`
- New: `analysis/tools/run_notebook.py`, `analysis/week01-save-the-season.ipynb`
- New: `analysis/thumbnails/configs/week01-dal.json`, `week01-phi.json`
- New: `analysis/tests/test_nfl_team_report.py`, `test_nflverse.py`,
  `test_team_posts.py`, `test_run_notebook.py`
- Changed: `analysis/lib/glossary.md`, `analysis/README.md`

## Data / contracts

**`TeamReport` (load-bearing for later Save the Season and Real or Lucky?
notebooks):**

```python
@dataclass(frozen=True)
class TeamReport:
    team: str                      # team code, e.g. "DAL"
    season: int
    through_week: int              # last week with every REG game final
    wins: int
    losses: int
    ties: int
    points_for: int
    points_against: int
    pythagorean_wins: float        # over games played, exponent 2.37
    one_score_wins: int
    one_score_losses: int
    turnover_margin: int           # takeaways minus giveaways
    turnover_margin_rank: int      # 1 = best of 32
    offense_epa_rank: int          # EPA per play, 1 = best
    defense_epa_rank: int          # EPA per play allowed, 1 = best (lowest)
    offense_success_rank: int
    defense_success_rank: int
    rating: float                  # shrunk point differential per game
    remaining_games: int
    remaining_sos_rank: int        # 1 = hardest remaining schedule
    expected_final_wins: float
    final_win_distribution: dict[int, float]   # whole final wins -> share of simulations
    playoff_chance: float          # 0 to 1
    luck: Literal["unlucky", "about right", "lucky"]
    verdict: Literal["savable", "long shot", "very unlikely"]
```

**Pre-stated rules (fixed before any real team is read):**

- **Week cutoff:** a week counts once every REG game in it is completed,
  postponed or canceled; later games are the remaining schedule.
- **Pythagorean wins:** `PF^2.37 / (PF^2.37 + PA^2.37) * games played`.
- **Luck label:** Pythagorean wins minus actual wins (ties as half) of +0.75 or
  more is `unlucky`, -0.75 or less is `lucky`, otherwise `about right`.
- **Rating:** point differential per game times a slope fitted, through the
  origin, on 2012-2025 team-seasons: rest-of-season PD per game regressed on
  PD per game at the same week cutoff.
- **Win chance:** `Phi((rating_diff +/- home_edge) / sigma)`, with `home_edge`
  the mean home margin and `sigma` the standard deviation of game margins, both
  from 2021-2025 REG games. Simulated games have no ties.
- **Simulation:** 10,000 seasons, `numpy` generator seeded with 2026.
- **Playoff bar:** for each final win total (ties as half, rounded down), the
  share of 2021-2025 teams (17 games, 14-team field) that reached the playoffs.
  Below the lowest observed total it is 0; above the highest, 1.
- **Verdict:** playoff chance 35% or more is `savable`, 10% to 35% `long shot`,
  under 10% `very unlikely`.

**Thumbnail config:** 46b's JSON contract, `name` `week01-<team>`, `chart`
`week01-<team>-feed.png`, `sport` `nfl`, callout the playoff chance as "1 in N"
or a percentage.

## Testing

- **Runner:** pytest in `analysis/.venv` (`analysis/tests`), outside Verify, as
  in 46a and 46b. No test touches the database or the network: queries and the
  nflverse download are exercised by the real runs in Steps 1, 2 and 5.
- **Logic under test:** every function in `nfl_team_report.py`, the cache and
  table logic in `nflverse.py` (with the download function monkeypatched),
  `team_posts.py`, and the parameter injection in `run_notebook.py`.
- **Not unit-tested:** chart appearance (reviewed from the PNGs) and the
  notebook itself (proved by the runner from a clean kernel).
- **Verify** runs in Step 6 to prove the app is untouched.

## Notes for the AI

- **Read-only:** the database only through `lib/db.read_engine()`. Never read,
  print or commit `api/app/.env`. Every SQL query names `sport = 'nfl'` on each
  `sport_*` table it reads.
- **Isolation:** nothing in `analysis/` imports `api/` or `web/`, and the app
  never imports `analysis/`.
- **No betting language:** this is a playoff chance, never odds, a line or a
  pick. Say "rough estimate" and "simulated seasons" in plain words, and name
  the caveats: six games is a small sample, no tiebreakers or division races,
  neutral-site games treated as home games. Claim that turnovers do not repeat
  only as far as the 2024-2025 carryover figure supports it.
- **Fixed rules first:** the thresholds above are written and tested before
  DAL or PHI are read in Step 3. Do not tune them after seeing a result.
- **nfl_data_py is deprecated upstream.** Only `nflverse.load_schedules` imports
  it, so swapping to `nflreadpy` or the raw nflverse `games.csv` is one change.
- **Commits:** the notebook is committed with outputs cleared;
  `check_notebooks.py` must pass. Draft posts live in `output/` (gitignored);
  the owner edits them before posting.
- **Writing:** no em dashes in any generated text, notebook markdown, posts or
  docs. Keep comment density at the repo bar.
- **Data observed while specifying (2026-10-24, read-only):** 2026 REG weeks
  1-6 fully final, week 7 1 of 14; DAL 2-4 (PD -8), PHI 2-4 (PD -31); team
  efficiency 2012-2026 through week 6; player turnovers 2024-2026 only.
- **Interview guide:** `docs/SportApp-Employer-Interview-Guide.md` is local and
  untracked. Check whether it mentions the analysis workspace; update only if a
  claim changes, never stage it.

## Completion evidence (2026-10-24)

- Analysis tests (`analysis/.venv/Scripts/python -m pytest analysis/tests`):
  166 passed.
- Verify (`npm --prefix web run verify && cd api && python -m pytest`): 903 web
  tests, typecheck and build passed; 4,462 API tests passed. The app is
  untouched; the diff is limited to `analysis/` and `blueprint/`.
- `tools/run_notebook.py analysis/week01-save-the-season.ipynb --param TEAM=DAL`
  and `TEAM=PHI`: all 12 code cells ran from a clean `nbtg` kernel (about 9 s
  each). Charts exactly 1080x1350 and 1080x1920; thumbnails 1280x720,
  1080x1920 and 1080x1350; posts files written. `check_notebooks.py`: 0
  problems.
- Fitted from history (rules fixed and tested before any team was read):
  carryover slope 0.47 over 448 team-seasons (2012-2025, week 6 cutoff); home
  edge 2.1 points and margin spread 14.2 points (2021-2025); turnover-margin
  carryover r = 0.31 over 64 team-seasons (2024-2025, small sample); playoff
  bar 10 wins (15 of 16 made it; 59 of 60 at 10 or more; 9 of 23 at 9), 14
  entrants in each of 2021-2025.
- Results through 2026 week 6: DAL 2-4, PD -8, Pythagorean 2.8 (unlucky),
  1-3 in one-score games, offense 8th and defense 32nd in EPA per play,
  playoffs in about 1 in 5 simulated seasons (long shot). PHI 2-4, PD -31,
  Pythagorean 2.1 (about right), playoffs in about 1 in 8 (long shot).
- Changes made during the build: `sport_teams.name` holds the team code, so a
  static team-name table was added; the chart note sums the playoff table (59
  of 60 for 10+ wins) and shows the 9-win rate, because the blue bars alone
  undercount the chance; drafts dropped an untested "close games even out"
  claim, quote the real playoff-bar count, and phrase bottom-half schedules as
  easiest.
- Machine setup: the `nbtg` kernel was installed with the README's one-time
  `ipykernel install --user` line. The nflverse schedule cache in
  `analysis/data/` and everything in `analysis/output/` stay gitignored.
- Interview guide checked: it does not describe the analysis workspace, so no
  claim changed.


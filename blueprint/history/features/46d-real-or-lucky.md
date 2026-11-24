# Feature: Real or Lucky?, week 1

**From build-plan:** feature 46d (parent 46, Analysis workspace)
**Status:** complete (2026-10-27)
**Branch:** `feature/46d-real-or-lucky`

## Goal

A second week 1 notebook, `analysis/week01-real-or-lucky.ipynb`, that answers
"Are the <team> as good as their record?" for one team at a time, first the
6-0 Minnesota Vikings. It teaches the same concept as 46c (luck vs skill) from
the other side: a hot team's record can run ahead of how well it has played.

It reuses 46c's library for every number. What is new is the question's
framing: a "for real?" verdict, a league-wide chart that shows where the team
sits against its points, and draft posts written for a winning (or any) team.

## Design reference

- No mockup. The chart follows `lib/style.py` (46a): the title states the
  answer, logo blue marks the team, everything else gray, source line and
  credit.
- The thumbnail follows 46b's template; this feature only writes configs.
- The first MIN feed PNG from Step 3 is the visual reference, reviewed before
  docs and final checks.

## In scope

- **`SeasonSnapshot` in `lib/nfl_team_report.py`:** the record-and-luck half
  of `TeamReport` (record, points, Pythagorean wins, one-score record,
  turnover margin and rank, per-play ranks, luck label), built by
  `season_snapshot(...)` without the simulation, the nflverse download or the
  league fit. `team_report` is refactored to build on it; `TeamReport`'s fields
  and 46c's results do not change.
- **Pure helpers:** `points_record(pythagorean_wins, games)` ("5-1": the
  record a team's points usually produce, rounded to whole games), and
  `real_verdict(snapshot)` from pre-stated rules (below).
- **`lib/real_or_lucky_posts.py` (pure):** `chart_title(snapshot)` and the
  draft posts (video script, on-screen captions, X/Threads, LinkedIn,
  follow-up clip) for a `SeasonSnapshot`, reusing 46c's language helpers
  (`BANNED_WORDS`, `ordinal`) from `lib/team_posts.py`. **No "Not betting
  advice." (owner decision 2026-10-26):** the guide keeps it for prop and
  line content, and a record-vs-points piece offers nothing to bet; tests
  check it never appears in the posts or the video JSON.
- **`analysis/week01-real-or-lucky.ipynb`:** the template's nine sections.
  Parameters `TEAM = "MIN"`, `SEASON = None`, `THROUGH_WEEK = None`.
  Runs through `tools/run_notebook.py` unchanged.
- **The chart (one point: record vs points):** every team as a dot, x =
  Pythagorean wins, y = actual wins, with a dashed "record matches points"
  diagonal. Above the line means a record better than its points. The team is
  logo blue and labelled; every other team gray. The title comes from
  `chart_title`, for example "The Vikings are 6-0, but their points say 5-1";
  the subtitle names the cutoff week and "above the line = record better than
  points".
- **Thumbnail config:** `thumbnails/configs/week01-real-or-lucky-min.json`,
  headline "Are the Vikings for real?", callout the points record ("5-1",
  label "record their points usually produce").
- **Outputs (gitignored):** `output/week01-real-or-lucky-<team>-feed.png`,
  `-vertical.png`, three thumbnails, `-posts.md`.
- **Docs:** README folder map and roadmap; glossary entries only for terms
  not already defined.
- **Video data export (added 2026-10-26, owner-approved):**
  `lib/real_or_lucky_video.py` (pure) builds one JSON-ready dict from a
  `SeasonSnapshot`, the team's game-by-game scores through the cutoff and the
  turnover carryover; the notebook writes it to
  `output/week01-real-or-lucky-<team>-video.json`. Every number on screen
  comes from this file.
- **`RealOrLucky` Remotion composition (added 2026-10-26):**
  `video/src/RealOrLucky.tsx`, registered in `video/src/index.ts`. **Look
  (changed 2026-10-26, owner choice "chart comes alive"):** the clean Lineform
  look (black, logo blue, Barlow/DM Sans/JetBrains Mono, no comic frame,
  mascot, bubbles, burst or speed lines); the centrepiece is the feed
  chart's record-vs-points scatter, animated: grid, then the dashed "record
  matches points" line draws, every other team drops in gray, the team's dot
  rises into place in logo blue with its label. On top: a broadcast score bug
  (team, record, week, "Real or lucky?") and a fixed source strip carrying
  the source for the whole video (owner chose this mix
  after comparing clean and broadcast renders). Step 5's comic version is
  superseded by Step 5b. It takes the JSON as input props
  (`--props`), so a new team or week needs a rerun, not a code edit. Its
  `defaultProps` are a labelled made-up example for Remotion Studio, never
  real numbers. 1080x1920, 30 fps, about 45 seconds, no audio. Scenes:
  1. **Hook:** "The <Nickname> are <record>." then "Are they for real?"
  2. **The chart:** the animated scatter above, titled with `chart_title`,
     axes as on the feed chart, then the points sentence ("<scored> scored,
     <allowed> allowed usually add up to <points record>").
  3. **Close games:** each game's margin through the cutoff, one-score games
     (8 or fewer) in logo blue, the one-score record.
  4. **Per play:** offense and defense EPA ranks.
  5. **Turnovers:** margin and league rank, with the carryover caveat in
     words ("only loosely predicts" when r < 0.5).
  6. **Verdict:** the `real_verdict` label and its sentence from
     `real_or_lucky_posts.VERDICT_SENTENCES`, plus "Not betting advice."
  7. **Question** ("Real or lucky? Tell me below.") and the existing `Outro`.
- **`video/` enters version control:** it is untracked today; the new
  composition imports `Video.tsx` and `comic/Comic.tsx`, so 46d commits the
  `video/` project as it stands (its `.gitignore` already drops
  `node_modules/` and `out/`). Existing Dallas compositions are committed
  unchanged, not edited.

## Out of scope

- Playoff chance or simulation (46c has it; this question is about the record
  so far, not the rest of the season).
- Opponent-adjusted point differential (roadmap week 8).
- Any change to `TeamReport`'s fields, 46c's notebook, verdict or outputs.
- Any change to `api/`, `web/`, the database, models, probabilities or picks.
- SaveTheSeason and GamePreview video templates, `tools/make_video.py`,
  voiceover recording, CapCut editing and posting. Converting the existing
  Dallas compositions to read JSON.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Season snapshot and verdict** - `SeasonSnapshot`,
  `season_snapshot`, `team_report` rebuilt on it, `points_record`,
  `real_verdict`. *Done when:* all 46c tests pass unchanged; new tests cover
  the snapshot on 46c's toy league (and a team with no games refused),
  `points_record` rounding (4.66 of 6 is "5-1"; 3.5 of 6 is "4-2", halves up,
  not Python's banker's rounding), and every verdict branch at its thresholds;
  only then a scratch read prints MIN's snapshot and verdict at the current
  cutoff.
- [x] **Step 2 - Chart title and draft posts** - `real_or_lucky_posts.py`.
  *Done when:* tests check, for snapshot variants covering every verdict, that
  `chart_title` fits 2 lines at the style's title width, the LinkedIn post is
  150 to 250 words, the video script 110 to 160 words, no em or en dash, no
  banned word outside the disclaimer, the disclaimer in every piece, and the
  first sentence states the record and the points record.
- [x] **Step 3 - Notebook and chart** - `week01-real-or-lucky.ipynb`, the
  league chart, thumbnail config and render, posts file. *Done when:*
  `run_notebook.py analysis/week01-real-or-lucky.ipynb --param TEAM=MIN` runs
  clean; PNGs are exactly 1080x1350 and 1080x1920; the feed chart is shown for
  review; `check_notebooks.py` passes with the notebook saved without outputs.
- [x] **Step 4 - Video data export** - `lib/real_or_lucky_video.py`, its
  tests, and a notebook cell that writes the JSON. *Done when:* tests on
  46c's toy league check every field against the snapshot, game margins and
  the one-score flag at the 8-point edge, the verdict sentence taken from
  `VERDICT_SENTENCES`, no em or en dash and no banned word outside the
  disclaimer in any string; the notebook (week 6 cutoff) writes MIN's JSON.
- [x] **Step 5 - RealOrLucky composition** - `video/src/RealOrLucky.tsx` and
  its registration. *Done when:* `npx remotion render` with `--props` on
  MIN's JSON produces a 1080x1920 MP4 of about 45 seconds; stills from every
  scene are shown for review; every number on screen matches the JSON; no
  existing composition changes. If `npm install` or the render cannot run in
  the sandbox, the exact command is handed to the owner and the step waits
  for that render, not a workaround.
- [x] **Step 5b - Clean look and animated chart** - add `chartTitle` and
  `league` to the export, rebuild `RealOrLucky.tsx` in the clean look with
  the animated scatter. *Done when:* tests check `league` against
  `standings` (one entry per team with games through the cutoff, ties as
  half a win, the team included) and `chartTitle` against `chart_title`;
  the MIN render is 1080x1920 at about 45 seconds; stills from every scene,
  including three moments of the chart build, are shown for review; the
  composition imports nothing from `comic/`; no existing composition
  changes.
- [x] **Step 5c - "Every unbeaten team looks lucky" (added 2026-10-26,
  owner chose angle 1)** - for an unbeaten team, compare it with every past
  team that started with the same perfect record: `unbeaten_history` in
  `lib/nfl_team_report.py` (pure; completed regular seasons from 2012 to the
  season before, each team's first N games, N = the team's games played)
  gives how many such starts there were, how many had points that said they
  should have lost at least once (points record not N-0), how many had more
  Pythagorean wins than the team, and their rest-of-season win rate (ties as
  half); `is_last_unbeaten(table, team)`. Posts open with "the NFL's last
  unbeaten team" when true and add the history sentence (script, X,
  LinkedIn); the video JSON gains `lastUnbeaten` and `history` (null when the
  team has lost or tied), and a new scene between the chart and close games
  shows the past starts as gray dots by Pythagorean wins with the team in
  blue. A team that has lost or tied gets today's output unchanged.
  *Done when:* tests on a toy league check the start selection (first N
  games, perfect records only, ties not perfect, seasons before the current
  one only), the counts and the rest-of-season rate, and the post length
  limits still hold with the new sentence; MIN's history read is printed
  before any wording is final; stills of the new scene are reviewed.
- [x] **Step 5d - Where the points come from (added 2026-10-26, owner
  choice: follow-up clip only)** - `nfl_queries.scoring` (read-only, NFL
  regular season) gives each team-game's touchdowns (rushing/receiving,
  return and fumble-recovery), field goals and extra points;
  `scoring_run(scoring, games, team, season, through_week, last_n)` (pure)
  sums the team's last N games through the cutoff and stops with "not
  loaded" when a played game has no scoring rows. When the kicker scored at
  least half the points in that run, `surprising_fact` leads with it ("X
  touchdowns in their last N games; their kicker scored Y of their Z
  points"); otherwise the existing rules apply. *Done when:* toy-league tests
  cover the window (last N played games, byes skipped), the kicking points
  (3 per field goal, 1 per extra point), the half-or-more threshold and the
  "not loaded" stop; the main video and other posts are unchanged.
- [x] **Step 5e - Research stats (added 2026-10-26, owner chose all four)**
  - all pure, from scores and the 5d scoring rows, through the cutoff:
  1. `unbeaten_history` also counts past perfect starts that scored fewer
     points (and allowed fewer) than the team; the history scene and
     script say "fewest points of any team to start N-0 since 2012" when
     none scored fewer.
  2. `opponent_adjustment`: per game, points allowed vs that opponent's
     median in its other games (and points scored vs its median allowed),
     averaged, plus the biggest hold; median, not mean, so one blowout does
     not set an opponent's "usual" (owner, 2026-10-27); shown in the per-play scene
     and LinkedIn.
  3. The same adjustment's scoring side and 4. `field_goal_rank` (league
     field goals through the cutoff) join the kicker follow-up clip.
  4. `opponents_record`: opponents' combined record in their other games, as
     a LinkedIn caveat.
  LinkedIn's limit rises to 300 words and the script's to 110 to 180 for this
  content (owner, 2026-10-27: the video may run past a minute). *Done when:* toy-league tests cover each function
  (other games only, opponents met twice counted per meeting, missing
  scoring rows stop with "not loaded") and the post limits hold.
- [x] **Step 5f - Kicker line in the main video (added 2026-10-27, owner
  chose the middle path)** - when 5d's rule holds (kicker scored at least
  half the points in the run), the main video script adds one sentence after
  the per-play line ("Their kicker scored 56 of their last 86 points."), the
  video JSON gains `kicker` (`kickPoints`, `points`, `games`, `allGames`;
  null otherwise) and the per-play scene shows it. X, LinkedIn and the
  follow-up clip are unchanged; the follow-up stays the later post.
  *Done when:* tests cover the line at and below the half threshold, the
  whole-season wording, the JSON field and that X/LinkedIn do not change;
  the script stays within 180 words; MIN is rerun and re-rendered with a
  still of the per-play scene reviewed.
- [x] **Step 6 - Week 7 run, render, docs and checks** - once week 7 is
  fully final and Tuesday's `nfl-ingest` has loaded its turnovers and
  efficiency, rerun MIN so the cutoff is week 7 (6-0) and re-render the
  video from the new JSON; README (folder map, roadmap, video section) and
  glossary. *Done when:* the MIN outputs and video say 6-0 through week 7
  (or, if week 7 stats are still missing, the run stops with the "not
  loaded" error and that is reported, not worked around); analysis tests
  pass; Verify passes; the diff is limited to `analysis/` and `blueprint/`.

## Files / areas

- Changed: `analysis/lib/nfl_team_report.py`, `analysis/tests/test_nfl_team_report.py`
- New: `analysis/lib/real_or_lucky_posts.py`, `analysis/tests/test_real_or_lucky_posts.py`
- New: `analysis/week01-real-or-lucky.ipynb`,
  `analysis/thumbnails/configs/week01-real-or-lucky-min.json`
- Changed: `analysis/README.md`, possibly `analysis/lib/glossary.md`
- New: `analysis/lib/real_or_lucky_video.py`, `analysis/tests/test_real_or_lucky_video.py`
- New: `analysis/video/src/RealOrLucky.tsx`; changed `analysis/video/src/index.ts`
  (one `Composition` added) and `analysis/video/README.md`
- Newly tracked as is: the rest of `analysis/video/`

## Data / contracts

**`SeasonSnapshot` (load-bearing for later Real or Lucky? and Save the Season
notebooks):**

```python
@dataclass(frozen=True)
class SeasonSnapshot:
    team: str
    season: int
    through_week: int
    games: int
    wins: int
    losses: int
    ties: int
    points_for: int
    points_against: int
    pythagorean_wins: float
    one_score_wins: int
    one_score_losses: int
    turnover_margin: int
    turnover_margin_rank: int
    offense_epa_rank: int
    defense_epa_rank: int
    offense_success_rank: int
    defense_success_rank: int
    luck: Luck                      # 46c's label, unchanged

RealVerdict = Literal["Real", "Better than their record", "Mostly real, some luck", "Lucky"]

def season_snapshot(team, season, through_week, *, games, efficiency, giveaways) -> SeasonSnapshot
def points_record(pythagorean_wins: float, games: int) -> str   # "5-1"
def real_verdict(snapshot: SeasonSnapshot) -> RealVerdict
```

**Pre-stated verdict rules (fixed and tested before MIN is read):**

| Luck label (46c's, +/-0.75 wins) | Point differential | Verdict |
|---|---|---|
| about right | any | `Real` (the record matches the points) |
| unlucky | any | `Better than their record` |
| lucky | positive | `Mostly real, some luck` (good team, record ahead of its points) |
| lucky | zero or negative | `Lucky` |

- **Points record:** Pythagorean wins rounded to the nearest whole win
  (halves round up), losses = games played minus that; ties are not shown.
- **Video JSON (`RealOrLuckyVideo`, camelCase, the composition's props):**
  `team`, `nickname`, `teamName`, `season`, `throughWeek`, `record`,
  `pointsRecord`, `actualWins` (ties as half), `pythagoreanWins`, `games`
  (list of `week`, `opponent` nickname, `home`, `scored`, `allowed`,
  `margin`, `oneScore`), `oneScoreWins`, `oneScoreLosses`, `turnoverMargin`,
  `turnoverMarginRank`, `turnoverCarryover`, `offenseEpaRank`,
  `defenseEpaRank`, `verdict`, `verdictSentence`, `source`
  ("Source: nflverse · data through week N, YYYY"; owner chose 2026-10-26
  to cite the original source, not Lineform), and from Step 5b
  `chartTitle` (from `chart_title`) and `league` (list of `team`,
  `nickname`, `actualWins`, `pythagoreanWins` for every team with games
  through the cutoff, from `standings`). Built only from
  `season_snapshot` inputs; no number is typed by hand.
- **Data cutoff:** 46c's rule (every REG game in the week final). Turnovers
  and per-play ranks need that week's stats; a missing team-game row stops the
  run with "not loaded", never a zero.

## Testing

- **Runner:** pytest in `analysis/.venv` (`analysis/tests`), outside Verify.
  No test touches the database or the network.
- **Logic under test:** `season_snapshot`, `points_record`, `real_verdict`, the
  `team_report` refactor (46c's tests are the guard), `chart_title` and every
  post builder.
- **Not unit-tested:** chart appearance (reviewed from the PNG) and the
  notebook (proved by the runner from a clean kernel).

## Notes for the AI

- **Read-only** through `lib/db.read_engine()`; every `sport_*` read names
  `sport = 'nfl'`. Never read, print or commit `api/app/.env`.
- **Isolation:** nothing in `analysis/` imports `api/` or `web/`.
- **Language:** "points say", "record their points usually produce", never
  odds, lines or picks. A lucky verdict is not a prediction that the team will
  lose; say the record ran ahead of the points. Say close games and turnovers
  often do not hold up only as far as 46c's evidence supports
  (turnover-margin carryover r = 0.31, 2024-2025).
- **Data timing:** as of 2026-10-26 the Vikings' 16-10 week 7 win is loaded
  (scores only, after a manual `nfl-scores` run); week 7 is 13 of 14 final and
  has no turnover or efficiency rows. Steps 1-3 may build against the week 6
  cutoff (5-0); Step 4 is the 6-0 run.
- **Overview:** refreshed for 46d by the owner-approved scripted patch
  (2026-10-26), because the overview hook refuses partial edits.
- **Writing:** no em dashes in generated text, notebook markdown, posts or docs.
- **Commits:** notebook committed with outputs cleared; `check_notebooks.py`
  must pass.

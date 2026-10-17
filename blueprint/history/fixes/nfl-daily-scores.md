# Load NFL final scores daily

**Type:** Fix
**Completed:** 2026-10-02
**Branch:** `fix/nfl-daily-scores`

## The problem

The NFL slate shows a finished game as **LIVE** for up to five days. On
2026-10-02, PIT @ CLE (Thursday, week 4) still read LIVE the next day and the
summary said 0 / 16 final.

- A card reads final only when `sport_games.status = 'completed'`
  (`cardState` in `web/src/utils/nflSlate.ts`); any game past kickoff that is
  not completed reads live.
- `status` and the scores are written only by `python -m app.ingest.nflverse`
  (`upsert_game` in `app/repositories/nfl.py` sets `completed` once both
  scores exist).
- That ingest runs only in the Tuesday `nfl-ingest.yml` job (15:00 UTC). None
  of the Thursday-to-Monday workflows (prop lines, prop odds, weather) touch
  scores.

So a Thursday game stays LIVE until Tuesday, and Sunday games until Tuesday too.

## The fix

Add a new workflow, `.github/workflows/nfl-scores.yml`, that runs
`python -m app.ingest.nflverse --schedule-only` every day at 13:00 UTC
(8:00 AM CT), September through February, plus `workflow_dispatch`. Same
shape as `nfl-weather.yml`: checkout, Python 3.11, pip install, one step,
`contents: read`, `DATABASE_URL` from secrets.

**Why a separate workflow, daily:** it is free (public NFLverse release asset,
no key, no quota) and takes seconds, so a daily run gets every game day
(Thursday, Saturday late in the season, Sunday, Monday) final by the next
morning without timing it to each slot. Keeping it out of `nfl-weather.yml`
means a weather failure never hides a scores failure, or the reverse.

**`--schedule-only` loads games only, no player stats.** It upserts
`sport_games` (scores, status, NFLverse closing lines, roof, rest, temp, wind)
for the current season, the same columns the Tuesday run already writes.

**What it must not break** (checked while writing this spec):
- **27a / 27j grading** still needs the week's player stats: `settle_line`
  returns `week_not_loaded` until `nfl_player_weekly_stats` has the week, and
  that still loads only on Tuesday. A game marked final early grades nothing
  early.
- **27j and 28 verdict samples** count only weeks where every REG game is
  completed (`get_finished_weeks`, `unfinished_weeks`), so a partly final
  week stays excluded.
- **Baselines, DVP, team stats, form** all read `week < W`, so a game in the
  slate's own week finishing early changes nothing for that week.
- **Team ELO** still recomputes Tuesday only; `nfl_team_elo` is unchanged.

No app code, schema, or UI change.

## Build steps

- [x] **Step 1 - Daily NFL scores workflow.** Add
  `.github/workflows/nfl-scores.yml` as described, with a short header comment
  (why daily, why schedule-only, display only). Add the workflow to the
  Commands or cron notes only where `AGENTS.md` already lists NFL ingest
  commands, if a line is needed there.
  **Done when:** the YAML parses; running
  `python -m app.ingest.nflverse --schedule-only` locally from `api/` exits 0
  and the slate shows PIT @ CLE as final with the summary at 1 / 16.

## Verify

1. From `api/`: `python -m app.ingest.nflverse --schedule-only` prints
   `NFLverse loaded N games for season 2026`.
2. Reload `/nfl` (week 4): PIT @ CLE shows its final score, not LIVE, and the
   summary strip reads 1 / 16 final.
3. `/nfl/model` still shows week 4 as not settled (stats not loaded).
4. After merge and push, trigger **NFL Scores** once with "Run workflow" in
   GitHub Actions and confirm it succeeds.

## Result

- `python -m app.ingest.nflverse --schedule-only` loaded 272 games for 2026;
  `2026_04_PIT_CLE` moved to `completed` (PIT 24, CLE 27), and `/nfl/slate`
  for week 4 served it as completed (1 of 16).
- The workflow has not yet run on GitHub; trigger **NFL Scores** once with
  "Run workflow" after the push.

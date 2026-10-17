# QB change warning on the NFL game model

**Type:** Fix

## The problem

The muted game model (`nfl-elo-v1` spread and win probability, `NFL_SCORING_V1`
total) is built from past final scores only. When a team's usual starting QB is
out, the model still rates the team as if he plays, and the slate card and game
page show a large model-vs-market gap with nothing explaining it.

Found on 2026 week 5, DAL at TB: market DAL -9.5, model DAL -2.8 (6.7 points),
win probability 80.4% vs 59.8%, total 47.5 vs 52.1. Baker Mayfield threw every
TB pass in 2025 and weeks 1 to 3 of 2026; Jalon Daniels threw 27 of TB's passes
in week 4 and Mayfield threw none. A reader can mistake that gap for value on
TB +9.5.

**The depth chart alone does not show it.** TB's latest stored chart (week 4,
2026-10-04) still lists Mayfield as QB1, and no week 5 chart is stored yet.
The chart names the usual starter; the injury report and box scores show he
is not playing.

## The fix

A display-only "QB change" warning per team, computed from data already stored,
served through `/nfl/game-notes` and shown on the slate card and the game page's
Market and model block.

**The rule** (pure, new `app/core/nfl_qb_change.py`), per team in a week's game:

- **Usual starter:** QB1 on the team's latest stored depth chart at or before
  the week. Teams keep an injured starter at QB1, so this names the starter a
  reader means. Only with no stored chart does it fall back to the QB with the
  most passing attempts in the latest season's games among the team's last 8
  completed regular-season games. Only players whose position is `QB` count.
- **Warn when any of these hold** (reasons, in this order):
  1. `injured` - the usual starter is Out or Doubtful in the team's latest
     stored injury report this season (the latest report week at or before the
     slate week; a player absent from that report is healthy). Names the week.
  2. `backup_started` - a different QB led the team in attempts in its latest
     completed game that has stats loaded. Names that game's week.
  3. `depth_chart` - QB1 changed between the team's two latest stored charts.
     Names the previous QB1.
- **No warning** when no reason holds.
- (Rule revised twice during step 1, 2026-10-07. First, counting attempts
  across seasons let 2025 outvote 2026 (NYJ, ATL). Second, the owner noted
  attempts cannot tell a starter from his injury fill-ins: ATL's starter is
  Penix, WAS's is Jayden Daniels, and both teams' charts keep them at QB1 while
  hurt. ATL's week 4 Monday game also had no stats loaded, and no week 5 chart
  or report was stored yet, so every input reads "latest stored" and names its
  week.)

**Display:**

- **Slate card:** a `QB change: TB` tag in the card's tag row, styled
  `is-caution` like the Doubtful and Questionable tags. Never green or red.
- **Game page:** one line in the Market and model block, under the model row,
  such as: `TB QB change: Baker Mayfield, the usual starter, was listed Out in
  week 4. Jalon Daniels led TB in passes in week 4. The model is built from
  past scores and does not adjust for this.` Shown only when the game has a
  model row.
- The text helper is a pure function in `web/src/utils/` with a Vitest test.

**Must not break:**

- **Display only.** It never changes a projection, edge, rank, pick, the model
  numbers, or item 28's CLV rule and sample.
- **Item 29's rule:** this extends the `/nfl/game-notes` response; nothing is
  added to `/nfl/slate` or `build_slate`, so 27a grading and 27i freezing are
  untouched.
- No schema change and no migration.
- No UI text below 11px.
- Every new query carries `sport = 'nfl'` on each `sport_*` reference.

## Build steps

- [x] **1. API: the rule and the response.** Add `app/core/nfl_qb_change.py`
  (pure rule above), repository queries for each week team's per-game QB
  attempts over its last 8 completed REG games, its two latest QB1 charts, and
  its QBs in its latest injury report, and nullable `away_qb_change` /
  `home_qb_change` (`NflQbChangeSchema`: team, usual starter, reasons, and the
  injury status and week, last-game QB and week, and previous QB1 that go with
  them) on `NflGameNotesSchema`, built in `app/services/nfl/game_notes.py`.
  Tests in `tests/test_nfl_qb_change.py` for each reason, the chart beating
  fill-ins, practice-only reports, the no-chart fallback, ties, and no data;
  extend `tests/test_nfl_game_notes_service.py` for the new fields.
  **Done when:** `pytest` passes and `GET /nfl/game-notes?season=2026&week=5`
  returns an `awayQbChange` for TB at DAL naming Mayfield as usual starter,
  `injured` (Out, week 4) and `backup_started` (Jalon Daniels, week 4), and
  `null` for DAL. **Result:** as stated, plus WAS (Jayden Daniels; Kaliakmanis)
  and CHI (Williams; Bagent); ATL waits on its week 4 box score or week 5
  report.
- [x] **2. Web: tag and note.** Add the type fields, a pure
  `qbChangeText` helper in `web/src/utils/` with a Vitest test, the slate card
  tag, and the game page line.
  **Done when:** `npm run build` and `npm run test` pass, the week 5 slate shows
  `QB change: TB` on the DAL at TB card, and that game page shows the line under
  the model row; a game with no change shows neither.

## Verify

- `cd api && .venv\Scripts\python.exe -m pytest`
- `cd web && npm run build && npm run test`
- Open `/nfl` on week 5: DAL at TB carries the `QB change: TB` tag; other cards
  carry it only where a QB actually changed. Open the DAL at TB game page and
  read the line under the model row.
- Spot-check one team with a stable starter all season: no tag.

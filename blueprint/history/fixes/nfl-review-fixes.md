# Fix: NFL review fixes

**Type:** Fix
**Branch:** `fix/nfl-review-fixes`
**Status:** complete

## The problem

A 2026-09-25 review of the NFL section found bugs in data freshness, display and
labeling. The prop model itself was also found to be unvalidated: week 2 of
2026 graded 49.4% on 681 standard lines against a 57.7% Power break-even. That
part is **not** in this fix; it becomes a build-plan item later.

This fix covers what is plainly wrong today:

| # | Problem | Where |
|---|---|---|
| 1 | PrizePicks NFL lines are never fetched on a schedule, only relinked. The newest line is 2026-09-23, and week 1 has only 912 lines, so there is no pre-kickoff snapshot to grade. | `.github/workflows/` |
| 2 | Both NFL pages open on 2026 week 2, hard-coded; the current week is 3. | `NflIntelligencePage.tsx:87-88`, `NflPropBoardPage.tsx:63-64` |
| 3 | "Trust: Ready" can never show. Every line carries at least three always-present flags, so every row reads Watch or Review. | `web/src/utils/nflSignal.ts` `trustLabel` |
| 4 | `market_is_stale` is hard-coded `False`, so `market_stale` never fires. | `api/app/routers/nfl.py:232` |
| 5 | "BUF allows 160.0" beside a 55.5 WR line. `opponentAllowedHistory` is a position **total** per game, but it reads as per-player. | `nflSignal.ts` `signalSummary`, both evidence panels |
| 6 | The Prop Board's evidence panel is a thin copy of the slate's. It shows the raw `segment` key, anytime-TD history as `100.0%` / `0.0%`, and no book odds, snap share, injury, alternates or quality notes. | `web/src/components/NflEvidencePanel.tsx` |
| 7 | Anytime-TD standard lines are rated `probability - 0.5`, so nearly every one is labeled UNDER. The model sits about 12 points below the de-vigged book (0.37 vs 0.49), which is item 25's open problem. | `edge_is_comparable` (`nfl_projection.py`), `isRateable` (`nflPropBoard.ts`) |

## The fix

Seven small steps. The only projection-input change is step 4, a staleness flag
that already has a code path in `model_projection`.

**Must not break:**
- The `/nfl/slate` response shape (fields are only added)
- The anytime-TD probability itself
- The book-odds comparison
- The game-model strip
- The ingest's 429 handling (exit code 75)

## Build steps

- [x] **Step 1 - Scheduled line fetch.** Add `.github/workflows/nfl-prop-lines.yml`,
  which runs `python -m app.ingest.prizepicks_nfl` (free, no credits). Schedule,
  months `1,2,9-12` only:
  - Thursday 20:00 UTC (before TNF)
  - Saturday 23:00 UTC
  - Sunday 15:00 UTC (before the 17:00 UTC kickoffs)
  - Monday 20:00 UTC (before MNF)

  Also add `workflow_dispatch`, `permissions: contents: read`, and the same setup
  steps as `nfl-prop-odds.yml`. Exit code 75 (rate limited) must not fail the
  job silently: log it and fail visibly.

  *Done when:*
  - The YAML parses.
  - The workflow diff is reviewed.
  - A local `python -m app.ingest.prizepicks_nfl --dry-run` still runs.
- [x] **Step 2 - Current week by default.**
  - **Repository:** `get_current_week(db)`. It returns the (season, week) of the
    earliest REG game with `start_utc` no earlier than now minus 12 hours, and
    falls back to the latest loaded REG week.
  - **Router:** `GET /nfl/current-week` returns `{season, week}`.
  - **Web:** `fetchNflCurrentWeek` in `src/api/nfl.ts`, and `useNflCurrentWeek` in
    `src/hooks/useNfl.ts`. Both pages seed season and week from it. A URL param
    still wins on `/nfl`, and a user's selection is never overwritten after load.

  *Done when:*
  - A recorded-SQL pytest shows the time cutoff and the fallback.
  - `/nfl` and `/nfl/board`, opened with no params, show 2026 week 3.
- [x] **Step 3 - Reachable trust label.** `trustLabel` ignores the always-present
  flags (`historical_baseline`, `recent_market_model`, `opponent_adjusted`,
  `usage_adjusted`) before counting.

  *Done when:*
  - Vitest shows a clean row reads Ready, a stale row Review, and a row with
    `small_sample` Watch.
- [x] **Step 4 - Real stale-moneyline flag.**
  - `get_slate_market_probabilities` also returns the row's `fetched_at`.
  - The router passes `odds_are_stale(fetched_at, now=min(now, kickoff),
    max_age_hours=NFL_STALE_ODDS_HOURS)` (`app/core/odds.py`) into
    `NflProjectionInput`.
  - `NFL_STALE_ODDS_HOURS = 192`: game odds are fetched weekly (Tuesday), so 8
    days catches a stopped job without flagging a healthy week.
  - Measuring against kickoff keeps past weeks from turning stale when revisited.

  *Done when:*
  - A pytest shows a moneyline fetched 9 days before kickoff flags
    `market_stale` and skips the adjustment.
  - One fetched 2 days before does neither.
- [x] **Step 5 - Honest "allowed" label.** `signalSummary` reads
  `BUF allowed WRs 160.0/g` (a position total per game). The history block title
  in the evidence panel reads the same way.

  *Done when:* the Vitest for `signalSummary` is updated and passing.
- [x] **Step 6 - One evidence panel.** Move the slate page's inline
  `EvidencePanel` into `src/components/NflEvidencePanel.tsx`, replacing the thin
  copy, and use it on both pages. The board passes its alternates from
  `groupNflPropRows`. Keep the "allowed" history block the board panel has now.

  *Done when:*
  - `npm run build` passes.
  - On `/nfl/board`, the panel shows TD / No TD history, a readable segment,
    sportsbook odds on anytime TD, and quality notes.
- [x] **Step 7 - No anytime-TD pick until 25c.**
  - `edge_is_comparable` takes the market and returns False for
    `anytime_touchdown`.
  - `isRateable` mirrors it, with the comment updated.
  - The board still ranks anytime TD by probability under "show all" and still
    shows the book comparison, but with no pick label.

  *Done when:*
  - pytest and Vitest cover the anytime-TD refusal.
  - A live `/nfl/slate?season=2026&week=3` returns `edge: null` on every
    anytime-TD line.
- [x] **Step 8 - Anytime-TD price runs that land before kickoff.** Added
  2026-09-26. Last week, GitHub started the scheduled runs 2-3 hours late:
  - the Thursday fetch landed one minute before TNF
  - the Sunday run missed every 1 PM ET game

  In `.github/workflows/nfl-prop-odds.yml`, each window is matched to its run:

  | Run | Cron (UTC) | Central | `--hours-ahead` | Covers |
  |---|---|---|---|---|
  | Wednesday (new) | `10 23 * 1,2,9-12 3` | 6:10 PM | 30 | TNF |
  | Thursday (from 22:00) | `10 18 * 1,2,9-12 4` | 1:10 PM | 8 | TNF refresh |
  | Saturday (new) | `10 23 * 1,2,9-12 6` | 6:10 PM | 50 | Sunday + MNF |
  | Sunday (from 14:00) | `10 12 * 1,2,9-12 0` | 7:10 AM | 40 | Sunday + MNF refresh |

  - The header comment's credit estimate is updated: about 32 a week for
    anytime TD, about 160 a month worst case, within 500. The credit floor stays
    at 50.

  *Done when:*
  - The YAML parses.
  - The `HOURS_AHEAD` expression gives 30, 8, 50 and 40 for the four crons, and
    the `workflow_dispatch` input for a manual run.

## Verify

- `cd api && .venv\Scripts\python.exe -m pytest`
- `cd web && npm run test && npm run build`
- Open `/nfl` and `/nfl/board` with no URL params:
  - both show week 3
  - clean rows say Ready
  - the "allowed" text says /g
  - the board panel matches the slate panel
  - no anytime-TD row says UNDER

## Notes for the AI

- **Out of scope:** any change to the projection math (mean vs median, season
  blending, market-adjustment sign, DVP pooling, fantasy scoring). That is the
  planned build-plan item from the review, "NFL prop probability model".
- **Known, not fixed here:** on `/nfl`, rows with `edge: null` land on the
  "Positive signals" board (`(line.edge ?? 0) >= 0`). After step 7 that includes
  anytime TD. Record it in the archive as a follow-up rather than widening this
  fix.
- Standards: `X | None`, no `Any`, no em dashes, comment only the why, and the
  `~/` import alias.

## Results

All 8 steps are built.

- **Checks:**
  - `pytest`: 1,473 passed
  - `npm run test`: 177 passed
  - `npm run build`: clean
- **Browser, 2026-09-26:**
  - `/nfl` and `/nfl/board` open on 2026 week 3.
  - A URL param still wins.
  - The board panel shows TD / No TD history, "Standard · Full game", snap
    share, depth, alternates and quality notes.
  - The Anytime TD tab has 0 rateable lines, and under "show all" it ranks by
    probability with no pick.
- **Live slate, week 3:**
  - Trust labels were 326 Review, 17 Watch, 0 Ready; now 326 Review, 9 Watch,
    8 Ready.
  - 824 anytime-TD lines, 0 with an edge, all with a probability.
  - No `market_stale` flags: every latest moneyline was 29-125 hours old at
    kickoff.
- **Data fixes run alongside:**
  - **Kickoff times.** The Eastern-to-UTC conversion (`nflverse._schedule_start`)
    shipped on 2026-09-24, after the 9/22 weekly ingest, so every week-3 kickoff
    was stored 4 hours early.
    `python -m app.ingest.nflverse --season 2026 --schedule-only` reloaded 272
    games. Sunday early games now read 12:00 PM CT. Before this, the board would
    have hidden them at 9 AM ET, and times displayed 4 hours early.
  - **Anytime-TD prices.** A manual run on Saturday 2026-09-26 at 9:42 AM CT
    priced all 14 Sunday games for 14 credits (443 left):
    - 2,259 prices
    - 1,697 matched by unique name and 359 by full name
    - 197 with no candidate and 6 ambiguous
    - MNF fell outside the 50-hour window.
- **Why step 8 was added:** in week 2, GitHub started the Sunday 14:00 UTC run at
  17:22 UTC, after the 1 PM ET kickoffs. Those games had prices only from an
  extra Saturday-night run. Thursday's week-3 fetch landed at 00:14 UTC, one
  minute before kickoff.

## Follow-ups

1. **Unrated rows on "Positive signals".** On `/nfl`, rows with `edge: null`,
   now including every anytime-TD line, land on that board
   (`(line.edge ?? 0) >= 0` in `NflIntelligencePage.tsx`).
2. **In-game moneylines reach the model.** `get_slate_market_probabilities` takes
   the latest moneyline even when it was fetched after kickoff. One week-2 game's
   latest row is 1.6 hours after its start. Add `o.fetched_at <= g.start_utc`;
   it changes projections, so it goes through the model item.
   *Update 2026-09-26 (27a):* moot for 2026. That case was an artifact of the
   kickoff times stored 4 hours early; after the schedule reload, 0 of 18 graded
   games had a post-kickoff moneyline. 27b still guards the cutoff.
3. **Starting the API on Windows.** A plain `uvicorn app.main:app` fails
   (psycopg needs the selector event loop). A small launcher that sets
   `WindowsSelectorEventLoopPolicy` would help.
4. **Unsupported PrizePicks stats.** Skipped in the 2026-09-26 dry run: Rush+Rec
   Yds (235), Pass+Rush Yds (202), Pass TDs (187), Rec Targets (134).
5. **The NFL prop probability model**, a new build-plan item from the 2026-09-25
   review. Week 2 of 2026 graded 49.4% on 681 standard lines against a 57.7%
   Power break-even. Scope:
   - forward line grading
   - P(over) from a distribution, not mean minus line
   - season blending
   - the market-adjustment sign for passing
   - the matchup (DVP) inputs counted by team-game and limited to recent seasons
   - PrizePicks fantasy scoring
   - ledger finding F-02 (usage regression)


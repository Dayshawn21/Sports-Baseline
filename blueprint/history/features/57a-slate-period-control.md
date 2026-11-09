# Feature: Shared period control and period line

**From build-plan:** feature 57a (parent 57, One slate shape for every sport)
**Branch:** `feature/57a-slate-period-control` (cut from `master` at `7a39bf1e`)
**Status:** complete (2026-11-08)

## Goal

Every slate (NFL `/nfl`, NBA `/nba`, NHL `/nhl`, tennis `/tennis`) shows the same
page head: the title, one period line that replaces the stat tiles, and one
`← Previous · [period picker] · Next →` control. Learning to move between days or
weeks on one sport teaches all four. On a phone the first game moves up the
page, because the tile rows are gone.

## Design reference

No new visual target. Follow the incumbent Lineform look and the slate surface
brief `.impeccable/surfaces/web-src-pages-nflintelligencepage-tsx.md` ("Page head:
title, period line, previous and next"). The shape brief is the 2026-11-08
`/impeccable shape` round, recorded under item 57 in `project-overview.md`.

## In scope

- **`PageHead` picker slot.** `PageHeadPeriod` gains an optional `picker` node
  rendered between `← Previous` and `Next →`. The controls stay one row on
  phones, with 44px targets.
- **Period line.** The page head's `meta` becomes one line per sport, built from
  values each page already loads:

  | Sport | Line |
  |---|---|
  | NFL | `Week 9 · 15 games · 1 final · odds Tue 3:12 PM CT` |
  | NBA | `Sat, Nov 8 · 7 games · 0 final · odds 4:05 PM CT` |
  | NHL | `Sat, Nov 8 · 12 games · 0 final · odds 4:05 PM CT` |
  | Tennis | `Today and tomorrow · 33 matches · 124 player props` (or one date) |

  Parts with no value are left out rather than shown as `--`.
- **Stale-odds marker.** When the newest odds fetch is more than 6 hours old and
  at least one game on the slate has not started, the odds part reads
  `odds Tue 3:12 PM CT (stale)`. It is text, in the line's own gray, not a color.
  The 6-hour threshold is a proposed default, not a product rule; confirm it at
  spec review.
- **NFL.**
  - The week moves into the URL (`/nfl?season=2026&week=9`), read on every render
    rather than once on mount. No params means the current week, as today.
  - One week picker, grouped by season (2026, 2025, 2024 historical; weeks 1-18),
    replaces the Season and Week selects.
  - Previous and Next step one week. Week 1 steps back to the previous listed
    season's week 18; week 18 of the newest season disables Next; week 1 of the
    oldest season disables Previous.
- **NBA and NHL.** A date picker between the arrows that navigates to
  `?date=YYYY-MM-DD`. The arrows keep the API's `previousDate` / `nextDate`.
- **Tennis.**
  - The date moves into the URL (`/tennis?date=YYYY-MM-DD`). No date means
    today and tomorrow, as today.
  - A date picker with a clear action that returns to today and tomorrow.
  - In the two-day view, Previous opens yesterday and Next opens the day after
    tomorrow. In a one-day view the arrows step one day.
  - The tour filter, sort, "Upcoming only", "Show Leans" and the admin prop-source
    select stay as they are until 57d.
- **Stat tiles removed.** The tiles leave all four slates; their counts move into
  the period line. NFL's "Prop lines" and "Out or doubtful" tiles and NBA's and
  NHL's "Prop lines" tile are dropped, because each row already carries its
  prop count and injury tags. Tennis's LOCKS and STRONG+ tiles go here, since the
  tile row is removed; 57d removes the rest of tennis's pick wording.
- **Empty slate.** It names the next period with a link:

  > No NFL games loaded for week 9. **Week 10 →**

  > No NBA games on Sat, Nov 8. **Next slate: Sun, Nov 9 →**

## Out of scope

- The legend (57b), NHL row shape (57c), tennis wording and filters (57d).
- Game, player, props and model pages, including the game pages' "← Week 9 slate"
  crumbs.
- The digest, the NFL gap label (a later `/impeccable clarify`), search (#15).
- Any API change. Every value comes from responses the pages already load.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Shared pieces.**
  - `PageHead` renders `period.picker` between the arrows. Phone CSS keeps the
    period controls on one row with 44px targets.
  - New pure helpers in `web/src/utils/slatePeriod.ts`: `slatePeriodLine(parts)`
    (joins the non-empty parts with ` · `) and
    `isOddsStale(latestOddsMs, upcomingStartsMs, now)`, with tests.
  - No page uses them yet.

  *Done when:* the helpers' tests pass, and all four slates render exactly as
  before (unchanged screenshots at 1440px and 375px).
- [x] **Step 2 - NFL.**
  - The week is read from the URL, through a tested `nflWeekNeighbors(season, week)`
    for the season wrap and both ends.
  - The grouped week picker and Previous/Next links replace the selects.
  - The period line replaces `Summary`.
  - The empty slate links to the next week.

  *Done when:* `/nfl?season=2026&week=9` shows week 9, and Previous goes to week 8.
  Week 1 of 2026 goes back to 2025 week 18, and the newest week 18 disables Next.
  The back button returns to the previous week, and an empty week shows the
  "Week N →" link. Search still clears when the week changes.
- [x] **Step 3 - NBA and NHL.**
  - A date picker between the arrows navigates to `?date=`.
  - The period line replaces both stat sections.
  - Empty days name the next slate date.

  *Done when:* picking a date on `/nba` and `/nhl` navigates to that date, the
  arrows still use the API's neighbors, the tile rows are gone, and the period
  line shows the games, finals and odds time.
- [x] **Step 4 - Tennis.**
  - The date is read from the URL, through a tested `tennisDateNeighbors(date, today)`
    for the two-day view and one-day steps.
  - The date picker is moved between the arrows, with a clear action.
  - The period line replaces `TennisSlateSummary`, and the LOCKS and STRONG+
    tiles go.

  *Done when:* the arrows on `/tennis` go to yesterday and the day after
  tomorrow, `/tennis?date=...` steps one day, clearing the picker returns to
  today and tomorrow, and the other filters still work.
- [x] **Step 5 - Check all four.**
  - Desktop 1440px and phone 375px on all four slates.
  - The first game row's position on a phone, before and after.
  - Run Verify.

  *Done when:*
  - no page scrolls sideways
  - no text is under 11px
  - the period controls are one row at 44px on phones
  - the first game row sits higher on all four phone slates than before
  - Verify passes

## Files / areas

- **Shared:** `web/src/components/shared/PageHead.tsx`, `web/src/index.css`
  (page-head period styles).
- **New:** `web/src/utils/slatePeriod.ts` and `slatePeriod.test.ts`.
- **NFL:** `web/src/pages/NflIntelligencePage.tsx`, `web/src/utils/nflLabels.ts`
  (week options), a tested week-neighbor helper (`web/src/utils/nflSlate.ts` or a
  new `nflWeekPeriod.ts`).
- **NBA and NHL:** `web/src/pages/NbaSlatePage.tsx`, `web/src/pages/NhlSlatePage.tsx`.
- **Tennis:** `web/src/pages/TennisIntelligencePage.tsx`; `TennisSlateSummary.tsx`
  is deleted if nothing else uses it.
- `StatChip` stays; other pages use it.

## Data / contracts

- **No API change.**
- **URL contracts (load-bearing: links, Ask Lineform and home cards may point at
  these):**
  - `/nfl?season=<int>&week=<1-18>`. A missing or invalid value falls back to the
    current week.
  - `/nba?date=`, `/nhl?date=`: unchanged.
  - `/tennis?date=YYYY-MM-DD`: new. Missing means today and tomorrow; an invalid
    value falls back the same way.
- **Contract:** `PageHeadPeriod` becomes
  `{ label, previous?, next?, picker?: ReactNode }`. 57b and 57c read the page
  head through it.

## Testing

- **Unit tests (Vitest, beside the source):**
  - `slatePeriodLine`: part joining, and missing parts left out.
  - `isOddsStale`: the 6-hour edge, no upcoming games, no odds.
  - `nflWeekNeighbors`: the season wrap, both ends, the 2024 historical season.
  - `tennisDateNeighbors`: the two-day view, a one-day view, and crossing a month
    end.
- **Not unit-tested** (per the coding standards): pages and `PageHead`. They get
  browser and screenshot evidence in steps 1-5.
- **Gate:** the Verify command (`npm --prefix web run verify && cd api && python -m pytest`).

## Notes for the AI

- **Display only.** No probability, edge, rank, sort or pick changes. Everything
  stays gray, including the stale marker. 11px floor, `CT` times.
- **Use the existing pieces:**
  - the date parsers (`parseSlateDate`)
  - the label helpers (`slateDateLabel`, `nhlTimeLabel`)
  - the odds-time fields the summaries already compute (`nflSlateSummary`,
    `nbaSlateSummary`, `nhlSlateSummary`)

  Don't add new time math beyond the stale check.
- **TanStack Query keys** already include the period, so URL-driven periods
  refetch correctly. Keep the 5-minute `staleTime`.
- **Search:** the command field's `periodKey` (`${season}-${week}` for NFL, the
  date elsewhere) must change with the URL, so search clears on a period change.
- **Ant Design pickers** use the existing dark theme. The NFL week picker is an
  Ant `Select` with option groups, and the date pickers are `DatePicker`.
- **Production NFL slates** come from `report_snapshots`. Only stored weeks
  (the previous, current and next) load there; other weeks may return 503, which
  must render as the existing error state with a working Previous/Next.
- **Coordination:** the kicker zero-projection fix (another session) touches
  only API files. If it lands first, merge `master` before step 2.

## Result

- All four slates share the page head: title, one period line, and
  `← Previous · picker · Next →`. The stat tiles are gone.
- First game row on a 375px phone, before and after: NFL 767 → 658, NBA
  724 → 632, NHL 564 → 451, tennis 648 → 620. No sideways scroll, no text
  under 11px, period controls one row at 44px.
- NFL week, tennis date and the NBA/NHL date pickers are URL-driven. The empty
  NFL week and the NFL 503 were proven with stubbed API responses, since no
  stored week is empty.
- Additions beyond the spec's file list: a shared `SlateDatePicker`,
  `gameSlateLine` / `countPart` / `startTimes` in `slatePeriod.ts`, an exported
  `ctDayKey`, `oddsUpdatedMs` on the three summaries, and `dayjs` declared as a
  direct web dependency (already installed through `antd`). NHL's odds time
  uses the short `Sun 4:28 PM CT` form.
- Known limits: pickers truncate at 320px; tennis's "Upcoming only" default
  leaves past days empty until it is turned off (57d).
- Verify: `npm --prefix web run verify` (1278 tests, build) and API `pytest`
  (5937 passed).

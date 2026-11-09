# Feature: Tennis wording and filters

**From build-plan:** feature 57d (parent 57, One slate shape for every sport)
**Branch:** `feature/57d-tennis-wording-filters` (cut from `master` at `d3185d91`)
**Status:** complete 2026-11-08 (digest label `Model leans · reference`; a priced EV stays green)

**Outcome notes:** today-and-tomorrow grew from 47 to 75 matches with leans always shown. The default view still keeps a match for 3 hours after its start (the unchanged `UPCOMING_BUFFER_MS`). No tennis pick was priced in the window, so the green lean-cell EV and the priced digest are covered by tests, not seen live.

## Goal

The tennis slate (`/tennis`) stops speaking in pick language it can't back up and
loses most of its filter bar. Today the table's "Best pick" and "EV" columns, the
"Best picks · priced" digest and the "Show Leans" toggle read as a picks product,
though no tennis pick in the current window carries a price. After 57d the
column is a gray **Model lean**, the EV column is gone, the digest shows the next
matches' gray leans, and six controls become search (already in the top bar) plus
the tour tabs. The admin prop-source choice moves into the legend. Rows sort by
start time, and every row says its day.

## Decisions (taken in chat, 2026-11-08)

The plan line says these go "while tennis picks are off". Only tennis
**moneyline** picks are off (`MONEYLINE_PICKS_ENABLED = False`); book-priced
Total Games and Game Spread picks still come from `generate_market_odds_picks`
whenever a book line is stored. None is priced in the current window (0 of 181
picks on 2026-11-09). So:

| Question | Decision |
|---|---|
| EV column and priced digest | **Hide unless priced.** No EV column. A priced best bet shows its EV inside its Model lean cell, green as today. The priced digest appears only on a slate that has a priced best bet; otherwise the lean digest shows. How it works stays true. |
| What the lean digest shows | **The next 4 matches by start time** that have a lean, gray. No ranking. |
| "Upcoming only" | **Hidden only in the default view.** Today-and-tomorrow still hides started matches; a picked date shows every match that day (fixes the empty past days 57a noted). |
| LEAN-tier picks without "Show Leans" | **Always shown.** Every match's top lean fills the column, LEAN included. |

## Design reference

No new visual target. The 2026-11-08 critique
(`.impeccable/critique/2026-11-08T17-40-11Z__web-src-pages-nflintelligencepage-tsx.md`,
finding 4: rename "BEST PICK" to a gray "Model lean" and drop pick tiles while
picks are off) and the item 57 plan set the direction. 57a already removed the
LOCKS and STRONG+ tiles; nothing of them remains to delete.

## In scope

- **Model lean column.** "Best pick" becomes `Model lean`, muted. The cell shows
  the row's top pick text as today (`row.primaryPick`, else the first prop's
  player and stat, linked as today). A priced best bet adds its EV after the
  text (`+7.2%`), green, as the EV cell does today; nothing else in the column is
  colored.
- **EV column removed** from the header, rows, tournament-header colspan (9
  columns, 10 with the admin Flags column, become 8 and 9) and phone grid.
- **A day on every row.** The Time cell's day line reads `Today`, `Tomorrow` or
  the date (`Thu Nov 12`); today's rows are blank there now.
- **Filters: search plus one tour control.**
  - Remove "Upcoming only", the tour select, the sort select and "Show Leans"
    from the page head. The tour tabs (All · ATP · WTA · Challenger · WTA 125)
    are the one tour control. Search is the existing top-bar slate search.
  - Sort is fixed at start time (soonest), so the table keeps its tournament
    headers (`isGroupedSort('start')`).
  - Leans always on (`showLeans: true`); started matches hidden only when no
    date is picked (`upcomingOnly: date === undefined`); no `tour` sent to the
    API (the tabs filter in the browser, as today).
- **Prop source in the legend.** The legend's `Props` part shows `PrizePicks`
  to visitors. For the admin view it renders the existing source select there
  (57b made `text` a `ReactNode` for this). The admin props-health notice stays.
- **Digest.** With a priced best bet on the slate, the "Best picks · priced"
  digest shows as today. Without one, a gray `Model leans · reference` digest
  shows the next four upcoming matches that have a lean: lean text, the match,
  tournament and start. No tier badge, odds or EV. When no row qualifies (a past
  date, every match started) there is no digest, as NHL has none.
- **Wording.** Loading reads `Loading tennis slate...`; the source-error notice
  names `Model leans` instead of `Best Picks` and says "Other rows are still
  shown"; the empty state reads `No tennis matches for <period>.` with no
  "include Lean picks" button.
- **Legend sentences (tennis pick disclosure).** Replace "Total Games and Game
  Spread picks carry their expected value." with "Model lean is the model's view
  of each match, shown gray." and "A Total Games or Game Spread pick shows its
  expected value only when a book price is stored." The moneyline and PrizePicks
  sentences stay.

## Out of scope

- Any API change, model, probability, tier, price, EV threshold or pick
  selection change. `isPricedBestBet`, `bestBetPicks` and `anglePicks` are
  unchanged; only which already-computed values are shown changes.
- How it works (`howItWorksContent.ts`): still accurate after the decisions.
- The match, player, props and model pages, and the props board's own filters.
- The ELO, ML, Market, Model and Odds columns and the admin Flags column.
- Grouping by start window (tennis keeps tournament headers; NBA and NHL are not
  grouped either).
- Removing the now-unused sort comparators (`opportunity`, `ev`, ...) from
  `unifiedTennis.ts`: they are tested and harmless; a later cleanup can drop them.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Helpers, tested, unused.**
  - In `web/src/utils/tennisSlate.ts`:
    - `slateDayTime(startUtc, now)` returns `{ day, time }` with `day` one of
      `Today`, `Tomorrow`, a date, or `''` when the time is unknown (`time` then
      `TBA`)
    - `modelLeanCell(row)` returns `{ text, ev, link }`: `ev` is the formatted EV
      only for a priced best bet (`row.primaryIsBestBet`), else `null`
    - `leanDigest(rows, now, limit)` returns up to `limit` display items for the
      upcoming rows with a lean and an analysis page, in start order
  - Tests in `web/src/utils/tennisSlate.test.ts`.
  - Record the baseline: page-head control count, `/tennis` table and digest at
    375px and 1440px for one date (screenshots and numbers in
    `blueprint/reference/57d/`).

  *Done when:* the new tests pass, Verify's web half passes, and `/tennis`
  renders exactly as before.
- [x] **Step 2 - The table.**
  - `TennisSlateTable`: `Model lean` header, the step 1 cell (EV only when
    priced), no EV column, the day on every row.
  - `tennis-slate.css`: the lean cell muted, the EV column and its phone grid
    area gone.

  *Done when:*
  - no `EV` header or EV cell at 1440px; the lean column is gray on a date with
    no priced pick
  - every row's Time cell has a day line (`Today` on today's rows)
  - at 375px no page scrolls sideways and the lean text is not cut to nothing
- [x] **Step 3 - Filters and wording.**
  - Page head keeps only the period control; the tour tabs stay on the table.
  - Fixed start sort, leans on, started matches hidden only without a date, no
    API tour.
  - Admin prop source in the legend's `Props` part.
  - Loading, source-error and empty-state wording.

  *Done when:*
  - the page head has no Upcoming, tour, sort or leans control (visitor and
    admin)
  - the default view lists rows in start order under tournament headers and
    shows no started match
  - a past date (`/tennis?date=<yesterday>`) shows that day's matches, not an
    empty slate
  - the tour tabs and top-bar search still filter rows
  - with the admin view on, the legend's `Props` part switches PrizePicks and
    DraftKings and the props-health notice still appears when degraded
- [x] **Step 4 - Digest, legend sentences, check.**
  - `TennisSlateDigest`: the priced digest when `featuredPicks` finds a priced
    best bet, else the gray lean digest from step 1.
  - The two tennis legend sentences.
  - Desktop 1440px and phone 375px against the step 1 baseline.

  *Done when:*
  - on a slate with no priced pick the digest reads `Model leans · reference`,
    shows up to four upcoming matches in start order, and has no green, tier,
    odds or EV
  - the tennis disclosure no longer says "carry their expected value" and names
    when EV appears
  - no text under 11px, phone targets at least 44px tall, no sideways scroll
  - the 57b legend tests still pass
  - Verify passes

## Files / areas

- **Logic:** `web/src/utils/tennisSlate.ts` and `tennisSlate.test.ts`.
- **Table:** `web/src/components/tennis/TennisSlateTable.tsx`,
  `web/src/components/tennis/tennis-slate.css`.
- **Page:** `web/src/pages/TennisIntelligencePage.tsx`.
- **Digest:** `web/src/components/tennis/TennisSlateDigest.tsx`.
- **Legend:** `web/src/utils/slateLegend.ts` (`tennisLegend` pick sentences) and
  its test.
- **Unchanged:** `unifiedTennis.ts` logic, `howItWorksContent.ts`, the API.

## Data / contracts

- **No API change.** Every value comes from the predictions, best-picks and
  props responses the page already loads.
- **Display shapes (local to the tennis slate, not load-bearing):**

  ```ts
  interface SlateDayTime { day: string, time: string }
  interface ModelLeanCell { text: string, ev: string | null, link: string | null }
  interface TennisLeanDigestItem {
    matchKey: string
    analysisPath: string
    lean: string
    what: string   // "Sinner vs Alcaraz"
    when: string   // "Paris Masters · Tomorrow · 12:00 PM CT"
  }
  ```

## Testing

- **Unit tests (Vitest, `tennisSlate.test.ts`):**
  - `slateDayTime`: today, tomorrow, a later date, a CT-midnight edge, null and
    unreadable times
  - `modelLeanCell`: a priced best bet (EV shown), an unpriced lean (no EV), a
    prop-only row (linked prop text), an empty row (the existing dash placeholder)
  - `leanDigest`: start order, the limit, started rows skipped, rows with no lean
    or no analysis page skipped, an empty slate
  - fixed `now` and start times, per the coding standards
- **Legend:** the existing 57b tests, plus one that the tennis disclosure does not
  claim picks "carry their expected value".
- **Not unit-tested:** the table, page and digest components; browser and
  screenshot evidence in steps 2-4.
- **Priced path:** no stored tennis pick is priced in the current window, so the
  green EV in the lean cell and the priced digest are proven by the
  `modelLeanCell` tests and an unchanged `featuredPicks`, not in the browser. The
  review packet says so.
- **Gate:** the Verify command (`npm --prefix web run verify && cd api && python -m pytest`).

## Notes for the AI

- **Display only.** No probability, edge, tier, price, EV threshold or pick
  selection change. The one green left is a priced best bet's EV, which exists
  today; it appears only when `isPricedBestBet` is already true.
- **The sort change is the plan's**, not a new rank: start time replaces "Best
  opportunity" as the only order.
- **More rows by default.** Leans always on means matches whose only pick is a
  LEAN now appear, so the period line's match count grows (47 today with leans
  off). That is the decision, not a regression; step 3 reports the new count.
- **Reuse:** `fmtStartCT`'s day rules (CT calendar day) for `slateDayTime`;
  `matchAnalysisPath`, `fmtTournament`, `fmtEv` and `propMatchPath` as they are.
- **Command scope:** the slate search's `periodKey` drops the removed filters
  (`date` and `source` remain).
- **Coordination:** 57c is merged. Parent 57 is checked off when this completes.

## Open questions for review

1. **Lean digest label.** Drafted as `Model leans · reference`. Keep, or
   `Next up · model leans`?
2. **Priced EV in the lean cell** stays green, as the EV cell and digest are
   today. Keep the green, or make it gray too (all of 57 gray)?

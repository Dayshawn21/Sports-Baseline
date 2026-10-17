# Feature: How it works page

**From build-plan:** feature 37b (second sub-item of 37, public read-only demo)
**Status:** complete (2026-10-15)

## Goal

A public page that tells a visitor (most likely an employer) what the app does,
how data flows through it, and which outputs are picks versus reference, in
plain language and without overstating anything. It is reachable from the nav
and links into each sport's slate and model track record page, where the live
numbers are.

## Design reference

No mockup. The page reuses the app shell (`page-shell`, `page-container`), the
theme tokens in `web/src/index.css`, and the eyebrow, title and card styling of
the model pages (`nfl-model.css`). No new visual language: dark, gray by
default, green and red only in the legend's samples.

## In scope

- Route `/how-it-works` and a "How it works" nav entry, visible to everyone.
- Four sections of static content (below), with links to each sport's slate
  and model page taken from the `SPORTS` registry.
- Desktop and mobile layouts, no text under 11px.

## Out of scope

- Live numbers from the model endpoints: they are rate-limited, slow when cold
  (the NFL model page takes about 46 s), and change weekly. The page links to
  the model pages instead.
- Charts, image diagrams, or new visual components.
- Changes to any other page, model or API. No backend change.
- The README (37e), which may reuse this text later.

## Content

Every claim the page makes, fixed here so it can be reviewed before it is
written. No number that changes week to week; the model pages carry those.

**1. What it is.** A sports betting research tool built for one person. It
gathers schedules, stats, odds and PrizePicks prop lines on a schedule, runs
models, compares them with the market, and shows where they disagree. It does
not place bets and has no user accounts.

**2. How data flows** (a numbered list):
1. Scheduled jobs (GitHub Actions) collect schedules, box scores, sportsbook
   odds and prop lines for tennis, the NFL and the NBA.
2. Each provider's names are matched to the same players, teams and games.
3. Models produce win probabilities and stat projections. Sportsbook odds are
   de-vigged (the book's margin removed) into a fair market probability.
4. Predictions are stored before each event starts, then graded against the
   result once it ends.
5. The web app shows the slate, each game or match, and each model's track
   record.

**3. What each sport shows** (one card per sport):

| Sport | Model today | Shown as a pick | Reference only | Status |
|---|---|---|---|---|
| Tennis | The closing market price, adjusted by an ELO term, with weights fitted on 2022 matches and checked once on 2023-2025 | Derived, serve-edge and prop picks, with their expected value | Moneyline picks are off: the model's moneyline disagreements lost money against the closing line | Prop confidence tiers are still being graded on lines frozen before each match |
| NFL | Player-history prop projections; ELO-based game lines | None | Prop edges, the game-line model, and the best available price beside a fair price | The prop model graded below the 57.7% break-even, so its edges stay gray; forward checks of the prop ranking and of game-line movement are still accruing |
| NBA | A player's average over their last 20 games, with an over probability for assists | None | Projections, gaps to the line, and the assists over probability | The forward ranking check is accruing from the 2026-27 season |

Each card links to that sport's slate and model page.

**4. How a model earns a pick:**
- Every new signal is tested on games it was not fitted on, against a rule
  written down before the test ran. Most signals tried so far failed and were
  left out.
- Forward checks grade predictions frozen before each event, so a result can
  never leak into its own grade.
- **Color legend** (with one green, one red and one gray sample):
  - **Green:** on a slate, the positive expected value of a tennis pick; on a
    track record page, a result more than 2 standard errors better than its
    baseline.
  - **Red:** on a track record page, a result more than 2 standard errors
    worse than its baseline.
  - **Gray:** everything else. Gray means reference, not a recommendation.
    NFL and NBA numbers are always gray until a check passes.
- The market is hard to beat. Where the evidence says it wins, the app says so
  and turns the pick off.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Route, nav entry and the first two sections** -
  `web/src/pages/HowItWorksPage.tsx` with `how-it-works.css`, the route
  `/how-it-works` in `App.tsx`, and `{ key: '/how-it-works', label: 'How it works' }`
  in `NAV_ITEMS` after the sports and before Admin. Sections 1 and 2.
  - *Done when:* `sportNav.test.ts` expects the new order (Tennis, NFL, NBA,
    How it works, Admin), `visibleNavItems(..., false)` still drops only
    Admin, and `navKeyForPath('/how-it-works')` highlights the entry;
    `npm run build` and `npm run test` pass; a screenshot shows the page with
    the entry highlighted.
- [x] **Step 2 - What each sport shows** - section 3: one card per `SPORTS`
  entry. Its text comes from `SPORT_STATUS` in
  `web/src/pages/howItWorksContent.ts`, typed
  `Record<SportCode, SportStatus>` with `SportCode` derived from `SPORTS`, so a
  sport added to the registry without a status fails `tsc`. Its links come from
  the registry's `slate` and `model` paths.
  - *Done when:* `npm run build` and `npm run test` pass; a screenshot shows
    the three cards with the content above; each card's two links reach that
    sport's slate and model page.
- [x] **Step 3 - How a model earns a pick, and the mobile pass** - section 4,
  with the legend's three color samples.
  - *Done when:* screenshots at 1280 and 390 px wide show every section with
    no horizontal scroll; a Playwright check finds no rendered text under 11px
    on the page; the mobile drawer lists How it works; `npm run build` and
    `npm run test` pass.

## Files / areas

- `web/src/pages/HowItWorksPage.tsx`, `web/src/pages/how-it-works.css`,
  `web/src/pages/howItWorksContent.ts` (new)
- `web/src/App.tsx`, `web/src/utils/sportNav.ts`, `web/src/utils/sportNav.test.ts`

## Data / contracts

No API, schema or migration change.

**Load-bearing:**
- **Route `/how-it-works`** is public and stable; 37e's README links to it.
- **`SPORT_STATUS`** (`model`, `picks`, `reference`, `status` strings per
  sport) is the one place the page states what each sport serves. A later item
  that changes a sport's picks (25c, 27h, an NBA adoption item, re-enabling
  tennis moneylines) updates its entry in the same diff.

## Testing

Test gate on.

- **Step 1:** `sportNav.test.ts` covers the nav order, the Admin filter and the
  highlight.
- **Step 2:** `tsc` enforces one status per sport; the cards add no other
  logic.
- **All steps:** screenshots plus the build. The 11px check runs in Playwright
  through the system Edge (`channel="msedge"`), as in 37a.

## Notes for the AI

- **Accuracy is the feature.** Write only what the Content section says. If a
  claim looks wrong against the code or `project-overview.md`, stop and raise
  it rather than rewording it.
- Plain language for a non-specialist: "over probability", "break-even", and
  explain "de-vigged" in a few words the first time.
- No weekly-changing numbers. The fixed ones (57.7% break-even, 2022 fit,
  2023-2025 holdout, last 20 games) are fine.
- Gray by default. The only green and red on the page are the legend samples,
  using the theme's `--positive` and `--negative` tokens.
- Use they/them for players ("their last 20 games").
- No UI text under 11px. No em dashes in new text.

## Outcome (2026-10-15)

- **Checks:** `npm run build` succeeded and `npm run test` passed 44 files and
  527 tests (nav order, Admin filter and highlight in `sportNav.test.ts`). No
  API change, so `pytest` was not affected.
- **Live (Playwright in Edge, Vite dev on port 3011):** the page renders all
  four sections at 1280 and 390 px with no horizontal scroll; "How it works" is
  the selected nav entry and appears in the mobile drawer; the smallest
  rendered text is 11px; all six card links reach the right slate and model
  page.
- **`tsc` completeness:** deleting the NBA entry from `SPORT_STATUS` fails with
  "Property 'nba' is missing"; restored, the file is unchanged.
- **Departures from the spec:**
  - the legend uses color swatches instead of sample numbers, so no invented
    figure could be read as a real result
  - `list-style: decimal` / `disc` are set explicitly, because Tailwind's base
    styles strip list markers (the first screenshot lost the step numbers)
- **Interview guide:** the public-access answer now mentions the page and why
  it carries no live numbers.
- **Housekeeping:** test Vite servers on 3011 and 3012 from 37a had outlived
  their shells; both were confirmed as this session's Vite processes and
  stopped.

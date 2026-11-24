# Feature: CSS polish

**From build-plan:** feature 68a (parent 68, Interface polish)
**Status:** complete (2026-11-12)
**Branch:** `feature/68a-css-polish`

## Goal

Four CSS-only refinements that make the dense tables and cards read better
on every sport: numbers that don't jitter as they change, headings that break
evenly, smoother card corners where the browser supports them, and phone tap
targets of at least 44px without changing how anything looks. Display only.

## In scope

- **Tabular figures** on every table and numeric display. JetBrains Mono is
  already fixed-width, so this matters for DM Sans numbers: Ant Design tables,
  the hand-built `<table>`s, `stat-chip` values, and the period and time text.
- **Balanced headings**: `text-wrap: balance` on `h1` to `h3`, the shared page
  title (`.unified-page-title`) and section titles. Short labels and table
  cells are left alone.
- **Continuous corners**: `corner-shape: squircle` inside
  `@supports (corner-shape: squircle)` on cards and raised panels (Ant `Card`,
  `Modal`, `Popover`, `Drawer` content, and the hand-built card classes such as
  `.nfl-game-card` and `.nfl-player-card`). Browsers without support keep
  today's plain radius exactly.
- **Hit slop**: under `@media (pointer: coarse)`, interactive controls whose
  rendered box is under 44 x 44px get an invisible, absolutely positioned
  `::before` hit area that extends them to at least 44px. Visual size, layout
  and spacing do not change.

## Out of scope

- View transitions (68b), skeletons (68c), swipe-to-dismiss (68d).
- `text-wrap: pretty` on body copy, font or size changes, new radii tokens.
- Desktop pointer targets (the hit slop applies to coarse pointers only).
- Any API, model, rank, sort, version or color change.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Tabular figures and balanced headings** - global rules in
  `web/src/index.css`: `font-variant-numeric: tabular-nums` on `table`,
  `.ant-table`, `.stat-chip__value`, `time` and the page-head period line;
  `text-wrap: balance` on `h1`-`h3`, `.unified-page-title` and the shared
  section-title class. Existing per-file `tabular-nums` declarations stay;
  removing them is churn with no visible gain.
  *Done when:* in the browser at 1280px and 375px, `getComputedStyle` reports
  `tabular-nums` on a DM Sans cell in each of the four slates and prop boards,
  and `text-wrap: balance` (or `text-wrap-style: balance`) on the page title of
  each; a long title on a game or player page at 375px wraps into
  near-equal lines in a screenshot; no layout shift in before/after screenshots
  of the NFL slate and tennis prop board.
- [x] **Step 2 - Continuous corners** - one `@supports (corner-shape: squircle)`
  block in `index.css` applying `corner-shape: squircle` to the card and panel
  selectors listed in scope. If the squircle looks visibly tighter than today's
  corner at the same radius, raise the radius only inside that block, by one
  stated factor.
  *Done when:* in the in-app (Chromium) browser, `getComputedStyle(card).cornerShape`
  is `squircle` on a home sport card, an NFL game card and an open popover;
  a zoomed screenshot shows the smooth corner; with the rule disabled
  (simulating an unsupported browser) the radius is identical to `master`.
- [x] **Step 3 - Tap-target audit** - at 375px with touch emulation, run a
  read-only script in the browser that lists every visible `a`, `button`,
  `[role=button]`, `[role=tab]`, `input` and `.ant-*-close` under 44px in either
  dimension, on Home, each sport's slate, prop board and one game or player page,
  and the open phone drawer. Save the list to
  `blueprint/reference/68/tap-targets-before.md`. No source change.
  *Done when:* the file exists, names each undersized control by page,
  selector and size, and marks which already get 44px from existing
  `min-height` rules.
- [x] **Step 4a - Hit slop on standalone controls** - one hit-area rule in
  `index.css` under `@media (pointer: coarse)`: `position: relative` on the
  control and a transparent `::before` (or `::after` where `::before` is taken)
  with a negative inset sized to reach 44px, applied by selector to the
  "Fix in Step 4" controls that stand alone: drawer close, small switches,
  `+N alts` chips (hit area kept inside the chip's cell), Ant tabs, select and
  date-picker wrappers, Tools inputs and buttons, market buttons and tennis
  pills (width), the "Model page" and "How it works" links, the tennis slate
  toggle and the game crumb. Also scan one player page directly.
  *Done when:* a re-scan measuring each control's hit area with
  `elementFromPoint` at 22px from its center reports none of these under 44px;
  before/after screenshots at 375px show no visual change; the alts chip and its
  row, and the drawer close and the first drawer item, each still receive their
  own tap.
- [ ] **Step 4b - Stretched row links** - the slate row links (NFL, NBA, NHL),
  the Home card matchup lines and the NHL prop board player and game links get
  a hit area that covers their row (or half the gap to the next line on Home),
  with any other control in the row raised above it so it keeps its own tap.
  *Done when:* the same re-scan reports no control from the audit under 44px,
  saved with 4a's results as `tap-targets-after.md`; a tap anywhere on a slate
  row opens that game; neighbouring Home matchup lines each open their own game.

## Files / areas

- `web/src/index.css` (all four steps)
- Per-component CSS files only to drop duplicated `tabular-nums` (Step 1) or
  where a selector from Step 4 needs a local rule
- `blueprint/reference/68/` (audit output, Steps 3 and 4)

## Data / contracts

- None. No types, routes or API shapes change.

## Testing

- The test gate covers logic; this item is CSS only, so no new unit test.
  Evidence is browser computed styles, screenshots and the audit files, plus
  the Verify command (`npm --prefix web run verify && cd api && python -m pytest`)
  passing unchanged.
- Check at 1280px and at 375px (mobile preset), dark mode only.

## Notes for the AI

- Theme values stay in `web/src/index.css` custom properties; no hardcoded hex.
- Ant Design 5 uses CSS-in-JS with `:where` selectors, so plain class selectors
  in `index.css` win without `!important`; if one doesn't, raise specificity
  before reaching for `!important`.
- `corner-shape` is Chromium-only as of 2026; the `@supports` guard is the whole
  fallback story. Do not polyfill.
- `::before` hit areas need the control to be a positioning context; check the
  control doesn't already use `::before` for an icon or indicator before
  applying the pattern to it, and skip or use `::after` where it does.
- No UI text below 11px still holds; nothing here changes text size.
- No em dashes in comments or docs.

## Outcome

Completed 2026-11-12 on `feature/68a-css-polish`, CSS only, no API or model change.

- Tabular figures on tables, Ant tables, stat-chip values, the page-head period line
  and `<time>`; `text-wrap: balance` on `h1`-`h3` (the tennis model's closing-line
  heading went from 332px + 45px lines to 181px + 196px at 375px).
- `corner-shape: squircle` on 22 card and panel surfaces inside
  `@supports (corner-shape: squircle)`, with radii raised 1.5x there (`--radius`
  14px to 21px, 10px surfaces to 15px) so the squircle covers the same area as the
  old round corner; unsupported browsers keep today's radii.
- Touch hit areas (`@media (pointer: coarse)`, transparent pseudo-element) on the
  standalone controls from the audit, and NHL prop-board player and game links
  stretched over their cells. Layout identical with the rule removed (CSSOM toggle
  on five pages).
- Known limits: the `+N alts` chip reaches 33px (its cell clips at 37px); market
  pills and player-page market tabs stay 38-40px; Home matchup lines unchanged.
  Slate rows needed nothing (each `tr` already opens its game). Audit and results:
  `blueprint/reference/68/tap-targets-before.md` and `tap-targets-after.md`.
- Verify: `npm --prefix web run verify` (111 files, 1,791 tests, build) and
  `python -m pytest` (6,422 passed).

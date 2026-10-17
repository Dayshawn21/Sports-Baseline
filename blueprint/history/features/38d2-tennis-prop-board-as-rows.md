# Feature: Tennis prop board as rows

**From build-plan:** feature 38d2
**Status:** implementation complete

## Goal

Replace the tennis prop board's cards and permanent evidence side panel with one
dense row per line and an on-demand evidence drawer. The board becomes easier to
scan while preserving every existing rank, recommendation, probability, EV,
tier, trust decision, filter, and signal color.

## Design reference

- No tennis-props mockup remains. The direction contract
  `.impeccable/surfaces/web-src-pages-nflintelligencepage-tsx.md` and chosen
  sketch `.impeccable/mocks/decision/command.html` establish the dense,
  border-light table direction.
- Reuse the shipped shared row foundation in
  `web/src/components/shared/prop-table.css` and the interaction pattern in
  `web/src/components/nfl/NflPropTable.tsx` from 38d1.
- Match the current tennis cards for content and color semantics. This is a
  presentation change, not a redesign of the prop model.

## In scope

- One tennis prop table for the selected market, with these columns:

  | Column | Content | Existing source |
  |---|---|---|
  | `#` | Board rank, or `--` when not rateable | Category order |
  | Player | Player, matchup, tournament, start time, and tour | `TennisPropCardModel` |
  | Line | Recommendation plus line, odds, or unpriced market value; source and payout tier below | `pickLabel`, `valueText`, `valueLabel`, `source`, `payoutTier` |
  | Model | Projection | `projectionText` |
  | Hit / BE | Hit probability against the break-even marker; missing values remain `--` | `hitPct`, `breakEvenPct`, `breakEvenLabel` |
  | EV | Existing signed EV, with the existing positive, negative, or neutral tone | `evText`, `evTone` |
  | Tier | Existing confidence tier, or `--` | `confidence` |
  | Trust | Ready, Lean, or Review; sample size and quality notes | `trust`, `sampleText`, `flags` |

- Continue to render moneyline and unpriced Win a Set rows through the same
  columns. Missing line, break-even, EV, or tier data stays explicitly missing;
  the table does not invent a value.
- Preserve market pills, source and tour filters, the Show all lines switch,
  partial-load notice, loading and error states, and both empty states.
- Preserve the current category order and ranking. Rateable rows keep their
  current rank; Show all lines adds dimmed, unranked rows after the existing
  Not rateable divider and explanation.
- A row click, or Enter or Space on its player button, opens the existing
  `TennisPropEvidencePanel` in an Ant Design `Drawer` (460px on desktop, full
  width on phones). Escape and the close control close it.
- Nothing is selected automatically. The board uses its full width until the
  user opens a row. Closing the drawer clears selection; changing source, tour,
  market, or Show all closes a selection that is no longer visible.
- The drawer retains Why this signal, context, projection inputs, recent bars,
  serve and return comparison, match histories, and quality notes. Last-five
  data stays in the drawer because `useMatchRecentForm` requires one request per
  match; rows never fetch it.
- The open row receives the shared selected treatment and exposes
  `aria-pressed`. Quality flags remain available through the Trust tooltip.
- At 1100px and below, rows use the shared two-line layout. At 390px there is no
  horizontal page scroll, no text below 11px, and the drawer uses the full
  viewport width.
- Remove the retired card component and card-only CSS after the evidence
  summary styles it still uses are moved to table or evidence-specific classes.

## Out of scope

- NFL prop rows, completed in 38d1, and NBA prop rows, deferred to 38d3.
- Last-five mini bars in the table. Tennis recent form is fetched per match and
  remains drawer-only by plan.
- Any change to `buildTennisPropBoard`, rateability, rank order, confidence
  tiers, trust labels, EV math, break-even math, or quality flags.
- New sorting, pagination, virtualization, bulk expansion, or a command field.
- API, schema, ingest, model, or stored-data changes.
- Changes to the evidence content beyond adapting its header summary and
  container styles to the drawer.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Tennis prop table and evidence drawer (web)** - add
  `components/tennis/TennisPropTable.tsx` and tennis-specific table styles on
  top of `components/shared/prop-table.css`. Replace `TennisPropCardGrid` and
  the permanent side panel on `TennisPropBoardPage` with the table and an
  on-demand drawer. Rows read `propCard(row)` unchanged. *Done when:*
  - for one player-prop market and Moneyline, up to the first 10 rows keep the same
    order, rank, recommendation, line, model, hit probability, break-even, EV,
    tier, trust, source, payout type, and sample shown by the cards on master
  - positive EV stays green, negative EV stays red, missing EV stays neutral,
    and the existing recommendation colors do not change
  - Show all lines adds dimmed, unranked rows below the Not rateable divider
  - no drawer or recent-form request exists until a row is opened; click and
    keyboard activation open the correct evidence, and Escape closes it
  - source, tour, market, and Show all changes cannot leave hidden evidence open
  - partial failures and empty categories still show their existing messages
  - `npm run build` passes

- [x] **Step 2 - Responsive pass and card cleanup (web)** - finish the two-line
  phone layout, adapt the evidence header summary to table-specific classes,
  and delete `TennisPropCard.tsx`, `tennis-prop-card.css`, the old two-column
  board layout, stacked-panel scroll code, and unused selectors. *Done when:*
  - at 1440px the table uses the available page width, columns align, and the
    460px drawer does not change the table's rank or order
  - at 390px each row is two readable lines with no horizontal page scroll;
    the drawer is full width and all text is at least 11px
  - recent bars and both players' recent histories still render inside the
    drawer when available; unsupported or missing history remains a clean
    absent, loading, or unavailable state
  - `rg` finds no `TennisPropCard.tsx`, `TennisPropCardGrid`, `tennis-prop-grid`,
    `tennis-prop-layout`, or `STACKED_QUERY` in `web/src`
  - Verify passes

## Files / areas

- **Web, new:** `web/src/components/tennis/TennisPropTable.tsx`,
  `web/src/components/tennis/tennis-prop-table.css`
- **Web, changed:** `web/src/pages/TennisPropBoardPage.tsx`,
  `web/src/pages/tennis-prop-board.css`,
  `web/src/components/tennis/TennisPropEvidencePanel.tsx`
- **Web, reused unchanged unless implementation exposes a missing display
  contract:** `web/src/utils/tennisPropCards.ts`,
  `web/src/utils/tennisPropBoard.ts`,
  `web/src/components/shared/prop-table.css`
- **Web, deleted:** `web/src/components/tennis/TennisPropCard.tsx`,
  `web/src/components/tennis/tennis-prop-card.css`
- **No API or database change.** Client only.

## Data / contracts

- No schema, endpoint, response type, or stored-data change.
- **Load-bearing:** rows consume `propCard(row)` unchanged. It remains the one
  tennis prop display model, with its existing Vitest coverage. The table does
  not recompute rank, recommendation, probability, EV, tier, trust, payout, or
  labels.
- **Load-bearing:** `buildTennisPropBoard` remains the source of category order,
  rateable order, and the split between `rateable` and `other`.
- **Load-bearing:** `useMatchRecentForm` remains inside the mounted evidence
  panel. With the drawer closed, no row-level recent-form request is allowed.
- **Load-bearing for 38d3:** `prop-table.css` stays the shared row and responsive
  primitive. Tennis-specific widths and signal colors belong in
  `tennis-prop-table.css`.

## Testing

- Existing pure logic coverage remains in `tennisPropCards.test.ts` and
  `tennisPropBoard.test.ts`. If implementation adds or changes a formatter or
  display-model field, update the corresponding utility test in the same step.
- Do not add React component tests. Verify the table and drawer in the running
  app with desktop (1440px) and phone (390px) screenshots.
- Compare displayed values and order against the pre-change card view or
  `master` for a normal player-prop market, Moneyline, and a Show all state.
- Confirm through the browser network panel that opening one row triggers only
  that match's recent-form request and the closed board triggers none.
- Final gate: `npm --prefix web run verify && cd api && python -m pytest`, using
  `api/.venv/Scripts/python.exe -m pytest` for the API half in this shell.

## Completion evidence

- `npm --prefix web run verify && cd api && python -m pytest`, with `api/.venv`
  active: 45 web test files and 546 tests passed, the production build passed,
  and 2,608 API tests passed on 2026-10-17.
- Browser captures in `.playwright-mcp/` cover the tennis prop table and evidence
  drawer at desktop and 390px, including player props, Moneyline, Show all,
  keyboard opening and closing, and the full-width phone drawer.
- Browser network evidence confirmed no recent-form request before opening a
  row and one match-specific request after opening it.
- Manual try path: open Tennis Props, choose a player-prop market or Moneyline,
  click a row to inspect and close the evidence drawer, then turn on Show all
  lines and repeat at desktop and phone widths.

## Notes for the AI

- Keep EV's current color rule exactly: positive is green, negative is red,
  zero or missing is neutral. Do not color hit probability merely for clearing
  break-even.
- Keep Over and Under recommendation colors exactly as the cards show today.
- Use a real button for the row's accessible open action. Do not put one button
  inside another or make a bare `<tr>` the only keyboard target.
- `Drawer` should use `destroyOnHidden`, as the NFL board does, so the evidence
  hook unmounts and stale recent-form content cannot survive selection changes.
- Do not move recent bars into rows or prefetch every match. That would turn one
  user-triggered request into a request fan-out across the board.
- Preserve the current 11px minimum text size and the global Lineform palette.
- This restyle does not materially change employer-facing product claims, so
  the local interview guide does not need an update.

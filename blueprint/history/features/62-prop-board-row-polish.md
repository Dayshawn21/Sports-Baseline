# Feature: Prop board row polish

**From build-plan:** feature 62
**Status:** complete (2026-11-11)
**Branch:** `feature/prop-board-row-polish` (this worktree; the session branch is `claude/board-ui-polish-0cc9c6`)

## Outcome

Built on `feature/prop-board-row-polish`, 2026-11-11. Display only, `web/` only.

- **Alt chip (1a-1c):** `AltLinesChip` with a popover replaces the alternate-line walls on the NBA board (both tables), NFL line-only and NHL; NHL keeps its never-promote-an-alternate rule.
- **Bars (2a-2b):** `lineOnlyBars` draws the line at the main rung, so goblin-only and demon-only rows get one; `MiniBars` shows over filled, under hollow, push mid-gray, with an optional `signal` prop.
- **Ring and strip (3a-3c):** `ProbabilityRing` on NBA, NHL and tennis (replacing the tennis 4px bar, keeping the break-even tick); `StatStrip` (L5, L10 when ten games are served, Avg, Diff) on NBA and NFL; `recentStatStrip` keeps NFL's full-game, non-TD rule.
- **Color:** every decision goes through `propRowVisuals.ts`; NBA, NFL and NHL pass `REFERENCE`, tennis uses `tennisRowSignal` (`adoptedPick`). No line was adopted on the check date, so the green path is proven by tests only.
- **Spec corrections during the build:** the tennis adopted side comes from `row.adoptedPick.side` (`card.isUnder` is false on every PrizePicks line); the ring track uses `--border-card` (`--bg-raised` vanished against the card); strip labels raised to 11px after the invariants review.
- **Evidence:** `npm --prefix web run verify` (101 files, 1584 tests, build) and `pytest` from `api/` with CI's dummy `DATABASE_URL` (6090 passed); browser checks on `/nba/props`, `/nfl/props`, `/nhl/props`, `/tennis/props` and `/nba/game/21153` against production data; `invariants-reviewer` found no gray-rule violation.
- **Left open:** duplicate alternates on some NBA rows inflate the chip count; the Record column still counts against the standard line only; NFL `Avg` covers ten games when L10 shows.

## Goal

Make prop board rows faster to read without changing what they say. Three
row-rendering changes, built and reviewed in this order:

1. Alternate goblin and demon lines collapse to the main line plus a `+N alts`
   chip that opens a popover, so an NBA row is one or two lines tall again.
2. The Last 5 bars always carry the dashed prop line, and each bar reads
   clearly over, under or push against it.
3. A small P(over) ring and a compact stat strip (L5, L10, average, diff vs
   line) put the row's evidence in one glance.

Modeled on competitor boards (Outlier's line-through bars, PickFinder's ring
and stat cells) but in Lineform's dense dark table style.

## Design reference

No image target: this is a restyle of existing cells, not a replica. Live
before-state, checked 2026-11-11:

- `https://sportapp-web-7v3r.onrender.com/#/nba/props` - the Line cell prints
  `standard · Also 7.5 goblin, 9.5 goblin, 12.5 goblin, 14.5 demon, 19.5
  demon, 27.5 demon` across three or more lines; the bars already draw a dashed
  line, but over and under bars are `--text-primary` vs `--text-muted`, and
  `--text-muted` (#85858f) is barely distinguishable from the default bar
  color `--text-secondary` (#9a9aa3).
- `https://sportapp-web-7v3r.onrender.com/#/tennis/props` - each alternate is
  already its own row, there are no recent bars, and P(over) / BE is a 4px
  bar with a break-even tick.

## The color rule (load-bearing)

Gray means reference, not a recommendation. Green (`--positive`) and red
(`--negative`) appear only on a row whose line 48e adopted.

| Board | Signal state today | Ring | Bars | Stat cells |
|---|---|---|---|---|
| Tennis, `row.adoptedPick` set | adopted, side = `row.adoptedPick.side` (`tennisRowSignal`) | adopted side's arc in `--positive` | n/a (no bars served) | n/a (no per-match values served) |
| Tennis, every other row (rated or for review) | reference | gray | n/a | n/a |
| NBA (modelled and line-only) | reference | gray | gray | gray |
| NFL (modelled and line-only) | reference | n/a (no P(over) on the board) | gray | gray |
| NHL | reference | gray | n/a (no recent values served) | n/a |

Correction to the brief: on tennis, **rated is not adopted**. `TennisPropTable`
documents that a rated line is gray and unranked unless 48e adopted it
(`TennisPropCardModel.adopted`), and the live board shows rated rows with trust
`Reference`. This spec keys color on `adopted`, not `rated`.

The rule lives in one tested function (`agreementTone`, below). Every component
takes a `RowSignal` and asks that function for a tone; no component decides
color on its own. NBA, NFL and NHL pass the exported `REFERENCE` constant, so
when one of their slices adopts later, the only change is what that board
passes in.

## In scope

- `AltLinesChip`: main line stays in the cell, alternates move behind a
  `+N alts` chip with an Ant Design `Popover` listing every alternate (and its
  P(over) where NBA serves one). Used on the NBA board (modelled Line cell and
  line-only Also cell), the NFL line-only Also cell and the NHL Other lines
  cell.
- `MiniBars`: distinct gray treatment for over (filled `--text-primary`),
  under (hollow, `--text-muted` outline) and push (`--text-secondary`); the
  dashed line drawn above the bars; tone classes only when a signal is adopted.
- `lineOnlyBars` draws the line at the row's main rung (the one the Line cell
  shows), so a row with only goblin or demon rungs still gets a line.
- `ProbabilityRing`: a ~20px SVG ring beside the existing P(over) text on the
  NBA modelled table, the NHL board and the tennis P(over) / BE cell (where it
  replaces the 4px bar and keeps the break-even tick).
- `StatStrip`: compact cells under the Last 5 bars on the NBA board (both
  tables) and the NFL prop and line-only tables, built only from values the
  row already carries.

## Out of scope

- **Filters and the filter bar** (`BoardFilterBar`, `NflPropBoardFilters`,
  `PropBoardFilters`, `propFilters.ts`): the board-filters session owns them.
  Touch row rendering only.
- **Any API or payload change.** The NBA board serves 5 recent games, NFL up
  to 10 (`recentFormLong`), NHL and tennis boards none. A Season cell and an
  NBA L10 cell need a wider board payload; the NBA board is a stored snapshot
  on a 512 MB service, so that is its own feature (see Notes).
- Tennis alternates: each is already its own row; no chip.
- Tennis EV column colors and every other existing signal color: unchanged.
- Game pages and player pages: they inherit the `MiniBars` styling (shared
  component) but get no ring, strip or chip in this feature.
- Projections, P(over), ranks, sorts, versions, adoption: unchanged.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

### 1. Alt-line chip

- [x] **Step 1a - Signal and alt-grouping helpers** - new
  `web/src/utils/propRowVisuals.ts` with `RowSignal`, `REFERENCE`, `Tone`,
  `agreementTone` and `groupAltLines` (contracts below), plus
  `propRowVisuals.test.ts`. No UI change. *Done when:* `npm run test` passes
  with tests that `agreementTone` returns `neutral` for every direction under
  `REFERENCE`, `positive` for the adopted side, `negative` for the opposite
  side and `neutral` for push or null; and that `groupAltLines` keeps the main
  rung out of `alts`, orders alts by line then standard/goblin/demon, counts
  them, returns `count: 0` for a single rung and an empty list for no rungs.
- [x] **Step 1b - `AltLinesChip` on the NBA board** - new
  `web/src/components/shared/AltLinesChip.tsx` (plus rules in
  `components/shared/prop-table.css`), used in `NbaPropTable.tsx` `Line` (the
  `card.also` text) and `LineOnlyRow` (the Also cell). The chip is a button,
  stops row-click propagation (as `MiniBars` does), closes on Escape and
  renders nothing when there are no alts. *Done when:* on `/nba/props` a row
  with six alternates is at most two text lines tall in the Line cell at
  1280px, the chip reads `+6 alts`, clicking it opens a popover listing all
  six (NBA modelled rows keep each alt's P(over), e.g. `9.5 goblin · 31%`)
  without navigating to the player page, a row with no alts shows no chip,
  and `npm --prefix web run build` passes.
- [x] **Step 1c - Chip on NFL line-only and NHL** - use `AltLinesChip` in
  `NflLineOnlyProps.tsx` (Also cell) and `NhlPropBoardMarket.tsx` (Other
  lines cell, which keeps each rung's gap in the popover). *Done when:* on
  `/nfl/props` (line-only section) and `/nhl/board` the alternates collapse
  the same way, with screenshots of each, and build passes.

### 2. Line through the Last 5 bars

- [x] **Step 2a - Bar line at the main rung, bar tone helper** - change
  `lineOnlyBars` in `utils/nflLineOnly.ts` to place the line at `mainRung(row)`
  (standard, else the first rung) instead of only a standard rung; add
  `barTone(signal, vsLine)` to `propRowVisuals.ts` (a thin wrapper over
  `agreementTone` mapping `above`/`below` to `over`/`under`). Tests in
  `nflLineOnly.test.ts` and `propRowVisuals.test.ts`. *Done when:* tests
  prove a goblin-only row gets a non-null `linePct` and `vsLine` per bar, a
  standard row is unchanged, and `barTone(REFERENCE, ...)` is always
  `neutral`.
- [x] **Step 2b - `MiniBars` gray over/under/push and signal prop** - in
  `MiniBars.tsx` add an optional `signal?: RowSignal` (default `REFERENCE`)
  and a `is-tone-positive` / `is-tone-negative` class from `barTone`; in
  `prop-table.css` style `is-above` filled `--text-primary`, `is-below` hollow
  with a 1px `--text-muted` border, `is-push` `--text-secondary`, tone classes
  `--positive` / `--negative`, and the dashed line above the bars
  (`z-index`). *Done when:* on `/nba/props` and `/nfl/props` every row with
  recent games shows the dashed line, over and under bars are distinguishable
  in a grayscale screenshot, no bar anywhere is green or red (computed
  `background-color` of every `.mini-bars > span` checked in the browser), an
  NBA game page and NFL game page still render their bars, and build passes.

### 3. P(over) ring and stat strip

- [x] **Step 3a - Ring and strip helpers** - add `probabilityRing`,
  `statStrip` and `tennisRowSignal` to `propRowVisuals.ts` with tests
  (`card.isUnder` is false on every PrizePicks line, so the adopted side
  comes from `row.adoptedPick.side`; corrected during 3a). *Done when:* tests cover:
  ring percent clamps to 0-100 and is null for a null probability; ring tone
  is `neutral` under `REFERENCE` and `positive` only for an adopted signal;
  the break-even tick passes through when given; `statStrip` on 5 values
  gives `L5` hits over the line (pushes excluded from the numerator, shown as
  `3/5`), the 5-game average and the signed diff vs line, and omits `L10`;
  on 10 values adds `L10`; on no values or a null line returns no cells; every
  cell tone is `neutral` under `REFERENCE`.
- [x] **Step 3b - `ProbabilityRing`** - new
  `components/shared/ProbabilityRing.tsx` (inline SVG, track `--bg-raised`,
  arc `--text-secondary`, tone arc `--positive`, break-even tick
  `--text-primary`, `aria-label` with the percent). Used in the NBA modelled
  P(over) cell (`card.main.pOver`, 0-1 scale), the NHL board P(over) cell
  (`row.standardPOver`, 0-1) and the tennis P(over) / BE cell (`card.hitPct`
  and `card.breakEvenPct`, already 0-100; the ring replaces
  `.tennis-prop-table__prob`). The existing percent text stays. On an
  adopted tennis under, the toned arc is the under share (100 minus P(over)),
  so the green arc is always the adopted side. *Done when:*
  NBA and NHL rings are gray on every row; on `/tennis/props` a ring is
  `--positive` only on a row whose card is adopted (if no line is adopted on
  the check date, say so and show the gray state plus the passing tone test);
  a missing probability renders `--` with no ring; screenshots of all three
  boards; build passes.
- [x] **Step 3c - `StatStrip`** - new `components/shared/StatStrip.tsx`
  rendering `statStrip` cells as a one-line mono strip (label over value,
  `--text-secondary` labels, `--text-primary` values, tone classes only when
  adopted), placed under the bars in the NBA board's Last 5 cells and the NFL
  prop and line-only tables' bar cells. NFL passes `recentFormLong` values
  when present so `L10` shows. *Done when:* an NBA row shows `L5 3/5 · Avg
  14.2 · Diff +0.7` style cells matching a hand count from that row's bars,
  an NFL row with 10 served games also shows `L10`, a row with no recent games
  shows no strip, every strip is gray, the row height grows by at most one
  line at 1280px, the 1100px wrapped layout is checked, and build passes.
- [x] **Step 3d - Verify** - run the Verify command from the repo root and
  dispatch `invariants-reviewer` on the branch for the gray-signal rule.
  *Done when:* Verify passes and the review reports no gray-rule violation.

## Files / areas

| File | Change |
|---|---|
| `web/src/utils/propRowVisuals.ts` | new: signal, tone, alt grouping, bar tone, ring, strip |
| `web/src/utils/propRowVisuals.test.ts` | new |
| `web/src/utils/nflLineOnly.ts` + `.test.ts` | `lineOnlyBars` line at the main rung |
| `web/src/components/shared/AltLinesChip.tsx` | new |
| `web/src/components/shared/ProbabilityRing.tsx` | new |
| `web/src/components/shared/StatStrip.tsx` | new |
| `web/src/components/shared/MiniBars.tsx` | `signal` prop, tone class |
| `web/src/components/shared/prop-table.css` | chip, bar states, ring, strip rules |
| `web/src/components/nba/NbaPropTable.tsx` | chip, ring, strip |
| `web/src/components/nfl/NflLineOnlyProps.tsx` | chip, strip |
| `web/src/components/nfl/NflPropTable.tsx` | strip |
| `web/src/components/nhl/NhlPropBoardMarket.tsx` | chip, ring |
| `web/src/components/tennis/TennisPropTable.tsx` + `tennis-prop-table.css` | ring replaces the P(over) bar |

Not touched: the four `*PropBoardPage.tsx` files, filter components and
`propFilters.ts` (board-filters session), `index.css` (existing tokens
suffice), anything in `api/`.

## Data / contracts

All new, in `web/src/utils/propRowVisuals.ts`. `RowSignal` is load-bearing: a
later adoption on NBA, NFL or NHL flips color by passing an adopted signal,
nothing else.

```ts
export type RowSignal = { kind: 'reference' } | { kind: 'adopted', side: 'over' | 'under' }
export const REFERENCE: RowSignal
export type Tone = 'neutral' | 'positive' | 'negative'
export function agreementTone(signal: RowSignal, direction: 'over' | 'under' | 'push' | null): Tone

export interface AltRung { line: number, oddsType: string | null, note?: string | null }
export interface AltGroup<R extends AltRung> { main: R, alts: R[], count: number }
export function groupAltLines<R extends AltRung>(rungs: readonly R[]): AltGroup<R> | null

export function barTone(signal: RowSignal, vsLine: 'above' | 'below' | 'push' | null): Tone

export interface RingModel { pct: number, breakEvenPct: number | null, tone: Tone }
/** `pct` is 0-100; callers convert NBA and NHL 0-1 probabilities. */
export function probabilityRing(pct: number | null, signal: RowSignal, breakEvenPct?: number | null): RingModel | null

export interface StatCell { key: 'l5' | 'l10' | 'avg' | 'diff', label: string, value: string, tone: Tone }
/** `values` newest first; `line` is the main rung the Line cell shows. */
export function statStrip(values: readonly number[], line: number | null, signal: RowSignal): StatCell[]
```

`groupAltLines` picks the main rung the same way `mainRung` does (standard,
else the first) so the chip, the Line cell and the bar line always agree.
`diff` tone is `agreementTone` on the sign of avg minus line; `l5` / `l10`
tone on whether hits are over half. Under `REFERENCE` all are `neutral`.

No API, type, schema or stored-shape change.

## Testing

- **Unit (Vitest, test gate on):** everything in `propRowVisuals.ts` and the
  `lineOnlyBars` change, per the done-whens of 1a, 2a and 3a. The gray rule is
  tested directly: every helper returns `neutral` for `REFERENCE`.
- **Components:** not unit tested (per `coding-standards.md`); verified in the
  browser with screenshots on `/nba/props`, `/nfl/props`, `/nhl/board` and
  `/tennis/props` at 1280px and at the 1100px wrapped layout, plus a computed
  color check that no reference row has a `--positive` or `--negative` value.
- **Gate:** `npm --prefix web run verify && cd api && python -m pytest` before
  `/complete`, then `invariants-reviewer`.

## Notes for the AI

- Client only. No `any`, `~/` imports, theme variables only (no hex), no em
  dashes, comments only for the why.
- Chip and popover clicks must not trigger the row's navigate handler
  (`followFromRow` in NBA ignores `button, a`; tennis's `onRowClick` ignores
  only `a`, but tennis gets no chip).
- `MiniBars` is shared with the NBA and NFL game pages; its gray restyle lands
  there too, which is intended. Keep `MiniBars`' existing props working.
- Keep the stat strip to values the row already has. Do not compute a season
  figure from 5 or 10 games and label it Season.
- Rebase concern: board-filters, record-strip and prop-reasons sessions touch
  the same pages. This feature stays inside row components and
  `prop-table.css`; if a sibling has merged first, rebase before 1b.
- **Overview not regenerated.** `/feature` normally runs `/overview` after a
  plan addition. With five sibling branches each adding a plan item, it is
  left for one regeneration after they merge, to avoid five conflicting
  copies of `project-overview.md`.
- **Follow-up, not this feature:** serve 10 recent games and a season average
  on the NBA and NHL board payloads (and per-match recent values on tennis
  lines) so the strip can show `L10` and `Season` everywhere. That is an API
  change against the stored NBA board snapshot and the 512 MB plan.

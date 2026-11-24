# Remove dead tennis evidence body and orphaned game-market CSS

**Type:** Fix
**Fixes:** F-43, F-44
**Branch:** `claude/player-page-dead-code-19b957`

## The problem

- **F-43:** `966f51d6` (#35) replaced the only use of
  `web/src/components/tennis/TennisPropEvidenceBody.tsx` in `PlayerPropTabs.tsx`
  with `TennisMarketPanel`. Its two exports, `TennisRecentBars` and
  `TennisPropEvidenceBody` (88 lines), have no importer now. Its side-cell logic
  is a third copy of the rule in `TennisPropTable.tsx` and `TennisMarketPanel.tsx`,
  so a later color change could update a copy nobody renders.
- **F-44:** `.nfl-prop-detail__model` in `web/src/components/nfl/nfl-prop-detail.css`
  styled the `DetailGameMarket` block that `ac73e775` (#34) removed. No `.tsx` or
  `.ts` file uses the class now.

## The fix

- Delete `web/src/components/tennis/TennisPropEvidenceBody.tsx`.
- Delete both `.nfl-prop-detail__model` rules (around lines 138 and 152) in
  `web/src/components/nfl/nfl-prop-detail.css`.

**Must not break:**

- Keep the `tennis-prop-evidence__*` classes in `web/src/pages/tennis-prop-board.css`;
  `TennisMarketPanel` and the props board still use them.
- Keep `.nfl-prop-detail__kv` and the other nearby rules.

## Build steps

- [x] **1. Remove the dead file and the orphaned rules.** Done when
  `rg "TennisPropEvidenceBody|TennisRecentBars|nfl-prop-detail__model" web/src`
  returns nothing and `npm --prefix web run verify` passes. No API file changes,
  so `pytest` is not needed.
- [x] **2. Let the tennis lines-table colors win over the shared table colors.**
  Found while checking step 1 in the browser; the rules predate this fix. In
  `web/src/components/shared/player-panel.css`, `.nfl-prop-detail__table td`
  (0,1,1), `td small` (0,1,2) and `tr.is-selected td` (0,2,2) outrank the tennis
  side, EV and margin classes (0,1,0 and 0,2,0). So an adopted side or margin
  shows gray instead of green, and the selected row turns every tone white. Move
  only those three `color` declarations into `:where(...)` rules, so a class on a
  cell or its `<small>` wins; layout, weight and the note row stay as they are.
  Other sports pass no cell classes, so their tables do not change. CSS only, no
  logic, so no new test. Done when, on a tennis player page, the selected and
  unselected Side and EV cells compute to the `tennis-prop-board.css` colors
  (checked in the browser, forcing the classes where today's data has no green
  or red line), an NBA or NFL lines table computes the same colors as before,
  and `npm --prefix web run verify` passes.

## Verify

- A tennis player page with lines keeps its Side and EV cell colors, on the
  selected row too.
- The NFL player page's Evidence section looks the same as before.

## Result (2026-11-09)

- Step 1: `rg "TennisPropEvidenceBody|TennisRecentBars|nfl-prop-detail__model" web/src`
  returns nothing. F-43 and F-44 are marked `fixed` in the findings ledger and
  stay there until a later `/audit` closes them; F-45 stays `unverified`.
- Step 2: on `/#/tennis/player/36?market=total_tie_breaks&match=98430`, with and
  without `prop=336408` selected, the Side `is-none` cell computes to
  `--text-muted` and the EV cell to `--text-secondary` (before: both white on the
  selected row). With the classes forced by hand (no green or red line on
  2026-11-09), the adopted side, `is-positive` EV and margin compute to
  `--positive`, and `is-negative` to `--negative`, on selected and unselected rows.
- Other sports unchanged: all 35 cells on `/#/nba/player/322612` match a
  pre-change snapshot, and all 33 cells on
  `/#/nfl/player/4453?market=receiving_yards&season=2026&week=9` (selected
  standard row included) match with the pre-fix stylesheet swapped back in.
  The NFL Evidence section renders with no `.nfl-prop-detail__model` element.
- Verify: `npm --prefix web run verify` (96 files, 1,435 tests, typecheck,
  build) after each step. No API file changed, so `pytest` was not run.

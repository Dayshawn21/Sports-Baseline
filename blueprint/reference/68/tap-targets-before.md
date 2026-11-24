# 68a tap-target audit (before)

Run 2026-11-12 on `feature/68a-css-polish` at 375x812 with the mobile preset
(touch emulation, page reloaded), against the local dev server and API. A read-only
script listed every visible `a[href]`, `button`, `[role=button]`, `[role=tab]`,
`input`, `.ant-select-selector`, `.ant-drawer-close` and `.ant-modal-close` whose
box is under 44px in either dimension. Sizes are the smallest seen, as width x height.

Controls that already reach 44px through existing rules (`.slate-finals__toggle`,
`.nfl-prop-toggle`, the tennis segment buttons' height, the top-bar search and menu
buttons' height) are not listed unless their other dimension is short.

## Fix in Step 4

| Control | Where | Size | Notes |
|---|---|---|---|
| `.ant-drawer-close` | Phone menu drawer | 24x24 | Standalone; clear space around it |
| `.ant-switch-small` | NFL props, tennis props, NFL game | 28x16 | Label beside it; hit area may cover the label |
| `.alt-lines-chip` | NBA props, NHL props, NFL game | 56x22 | Inside a row; keep its hit area inside its own cell |
| `.ant-tabs-tab` (button inside) | NFL game (Matchup / Props tabs) | 57x22 | Measure the `.ant-tabs-tab` box first; may already be taller |
| `.ant-select-selector` | NFL slate Week, NFL props Season, player filters, tennis Prop source | 101x24 to 335x32 | Wrapper is the target; the inner 4px `input` is not |
| Slate date picker (`.ant-picker`) | NBA, NHL, tennis slates | 111x22 input | Wrapper is the target |
| `.ant-input`, `.ant-btn` | Tools calculators | 167x22 inputs, 32px buttons | Inputs sit in a form grid; vertical slop only |
| Market buttons (`.nfl-prop-seg`-style rows) | NFL, NBA, NHL props | as small as 8x39 | Height is 39-40px from existing rules; width is set by label |
| Tennis filter pills | Tennis props | 15x44 to 23x44 | Height fine; width short on "All" and "ATP" |
| `a.home-card__match` | Home sport cards | 95x16 | Stacked lines; slop limited to half the gap between lines |
| Row link in NFL, NBA, NHL slate rows | Slates | 68x14 inside a 44px `li` | Candidate to stretch the link over its row |
| `a.nhl-prop-board__player`, `a.nhl-prop-board__game` | NHL props | 43x17, 21x52 | Row (`tr`, 76px) is not clickable |
| Text links "Model page →", "How it works →" | Prop boards, tennis slate | 80x18, 82x14 | Standalone line |
| `a.tennis-slate-table__toggle` | Tennis slate | 231x39 | 5px short in height |
| `a.game-crumb` | NFL game | 66x40 | 4px short in height |

## Leave alone

| Control | Where | Why |
|---|---|---|
| `a.prop-table__open` (player names) | NBA, NFL and tennis prop rows | The whole `tr` is clickable (175px tall) |
| Inner `input` of Ant selects | Every select | The `.ant-select-selector` wrapper takes the tap |
| `button.tsqd-open-btn` | Every page | TanStack Query devtools, dev builds only |

## Not covered

- A player page: the scan's link lookup found no player link from the NBA board,
  so the "nba player" pass re-scanned the NBA slate. Step 4 scans one player page
  directly.

# 68a tap-target results (after)

Measured 2026-11-12 on `feature/68a-css-polish` at 375x812 with the mobile preset
(coarse pointer). "Hit" is the real tap area: `elementFromPoint` probed outward from
the control's center until a point stopped landing on it (probe capped at 40px each
side, so a hit width of 81 means "at least 81").

## Step 4a - standalone controls

| Control | Page | Visible | Hit | Result |
|---|---|---|---|---|
| `.ant-switch-small` | NFL props, NFL game | 28x16 | 44x44 | Pass |
| "Model page" link (`.board-record__live a`) | NFL props | 80x18 | 80x44 | Pass |
| `.tennis-slate-table__toggle` | Tennis slate | 231x39 | 81x44 | Pass |
| `.game-crumb` | NFL game | 66x40 | 67x44 | Pass |
| `.nfl-player-crumb` | NBA player | 82x18 | 81x44 | Pass |
| `.ant-input-affix-wrapper` | Tools | 298x32 | 81x44 | Pass (uses `::after`; Ant Design's `::before` is a hidden height strut) |
| Tools buttons (`.tools-card .ant-btn`) | Tools | 83x32 | 81x44 | Pass |
| `.ant-tabs-tab` | NFL game | 57x46 | 58x46 | Already 44+ once the tab box is measured |
| `.ant-select-selector`, `.ant-picker` | Slate heads, prop filters | 154-335x44 | 81x44 | Already 44 tall at 375px; the audit read the inner input |
| `.ant-drawer-close` | Phone menu | 24x24 | 44x44 | Pass, from computed `::before` insets of -10px (the hidden pane stalls the drawer animation, so `elementFromPoint` could not reach it); hit area ends at y=50, first menu item starts at y=61 |
| `.alt-lines-chip` | NBA props | 69x22 | 68x33 | Capped: its table cell is 37px tall with `overflow: hidden` (needed for the line ellipsis). A tap below the cell still reaches the row, not the chip |

## Not changed, by decision

| Control | Size | Why |
|---|---|---|
| Market pills (`.nfl-prop-pills button`) | 38-40px tall | Wrapped rows sit flush, so the whole strip is already tappable; a taller hit area would take taps meant for the row above or below |
| Player-page market tabs (`.nfl-player-jump a`) | 38x40 | Inside a horizontal scroll strip that clips any hit area; 4px short |
| Tennis filter pills | 15-23px wide, 44 tall | Segmented and edge to edge; widening would cover the neighbour |
| `.slate-legend__pick a` ("How it works") | 82x14 | Not visible at 375px (inside a hidden region); rule applied for wider touch screens |

## Layout check

With the `@media (pointer: coarse)` block deleted and reinserted through CSSOM, the
position and size of the first 1,500 elements in `main` and the page height were
identical on NFL props, NBA props, Tools, the tennis slate and an NBA player page.
The hit areas change no layout.

## Step 4b - row links

| Control | Page | Visible | Hit | Result |
|---|---|---|---|---|
| `.nhl-prop-board__player` | NHL props | 71x35 | 101x75 (its whole cell) | Pass; the row is not clickable, so the link now covers its cell |
| `.nhl-prop-board__game` | NHL props | 24x52 | 48x75 (its whole cell) | Pass; a tap just right of the cell lands on the line cell, not the link |
| Slate row links (NFL, NBA, NHL) | Slates | 87x18 | Whole row | No change needed: each `tr` already opens its game on click. A click on the kickoff cell opened the row's own game on all three slates (NFL `#/nfl/game/137`, NBA `#/nba/game/21149`, NHL `#/nhl/game/57163`) |

## Not changed in 4b, by decision

| Control | Size | Why |
|---|---|---|
| Home card matchup lines (`a.home-card__match`) | 16px tall, inline | They are inline links that wrap within one sentence-like line; two sit on the same line with no gap, so any hit area would overlap the neighbour. Each card's own Slate link reaches the same games |

---
target: "NbaPlayerPage, NhlPlayerPage, NflPlayerPage, TennisPlayerPage: cross-sport consistency"
total_score: 26
max_score: 40
na_heuristics: 
p0_count: 1
p1_count: 4
target_identity: "file:C:\\dev\\SportAppV2\\.claude\\worktrees\\slate-clarify-af4b00\\web\\src\\components\\shared\\PlayerPageShell.tsx"
target_fingerprint: "sha256:997e74e032628a77729c1bab250ef6f6273fdd4dac5059cc548661cafaae2156"
target_path: "C:\\dev\\SportAppV2\\.claude\\worktrees\\slate-clarify-af4b00\\web\\src\\components\\shared\\PlayerPageShell.tsx"
timestamp: 2026-11-09T23-31-38Z
slug: web-src-components-shared-playerpageshell-tsx
---
# Critique: NBA, NHL, NFL and tennis player pages (cross-sport consistency)

Method: dual-agent (A: design review, built-in browser + source; B: detector + Playwright overlay). Note: B finished first and its report reached the parent before A's; the parent did not read B's findings into synthesis until A was in hand.

Captures: 1440x900 and 375x812 full-page, worktree slate-clarify-af4b00 at 966f51d6. Players: Jamal Murray (NBA, rebounds), Adam Fox (NHL, shots on goal), Josh Allen (NFL, passing yards, wk 9), Quentin Halys (tennis, aces).

## Why they still look different

The PRs shared the frame (`PlayerPageShell`), the tab strip (`PlayerMarketTabs`) and `PlayerEvidence`. Those three are identical on all four pages. But the regions that take most of the screen are still each sport's own components: the recent-form chart, the lines table, the first context section, the game log and the model record. On top of that, tennis does not import the stylesheets its panel classes rely on, so it renders differently depending on which page loaded first.

## Design Health Score

| # | Heuristic | Score | Key issue |
|---|---|---|---|
| 1 | Visibility of system status | 3 | NBA/NHL hero names the goblin line, the chart beside it shows no line |
| 2 | Match system / real world | 3 | Bettor language fits; "Basis: model total" is jargon |
| 3 | User control and freedom | 3 | URL-backed tabs and switches, collapsible Evidence |
| 4 | Consistency and standards | 1 | Three switch styles, three tag styles, two table systems, two projection blocks, section names disagree, tennis styling depends on navigation history |
| 5 | Error prevention | 3 | Disabled-window reasons live only in `title` |
| 6 | Recognition rather than recall | 2 | "Gap" unexplained; tennis bar axis drops the opponent |
| 7 | Flexibility and efficiency | 3 | Deep links per market, match and prop |
| 8 | Aesthetic and minimalist design | 2 | Tennis 20-row log and 3,700px page; NFL card head repeats the hero |
| 9 | Error recovery | 3 | Empty states link back; tennis not-found copy diverges |
| 10 | Help and documentation | 3 | Good captions, phrased differently per sport |
| **Total** | | **26/40** | **Acceptable** |

## Design Specificity Verdict

LLM assessment: specific in its parts, generic in the whole. Barlow uppercase section rules, mono numerics and gray-only bars are on-brand and shared. The top half (head, tabs, projection, Evidence) honors PRODUCT.md principle 3 ("one app, not three"); the bottom half is four different products.

Deterministic scan: `impeccable detect` over the four pages, the four panels, `components/shared/` (30 files), `components/tennis/player/` and every sport component they import returned 0 findings. The browser overlay found 6 (NBA), 6 (NHL), 12 (NFL), 7 (tennis): mostly tiny-text at exactly 11px (consistent across sports, at the floor, not a violation); one real low-contrast (tennis "Open match", AntD blue #1668dc on #0d0d0f, 3.7:1); one line-length (tennis `.tennis-match-aside__note`, about 112 characters). False positives: shape-assembled-illustration on every page is the TanStack Query Devtools logo (dev only); NFL weekbar label contrast is measured against the bar but the label sits above it on the card. No overlay is left visible.

## Ranked cross-sport differences (most to least "they look different")

| Rank | Difference | Diverges | Cause | Sev | Fix | Command |
|---|---|---|---|---|---|---|
| 1 | Tennis panel unstyled on a cold load: Lines table header 12px DM Sans not uppercase, no row rules, no section padding/border, Last 5/Last 10 switch is run-together 18px text buttons | Tennis | `TennisMarketPanel.tsx` uses `nfl-prop-detail__*` classes but never imports `components/nfl/nfl-prop-detail.css`; `.tennis-prop-seg` lives in `pages/tennis-prop-board-filters.css`, imported only by `TennisPropBoardPage.tsx:12` | P0 | Move panel primitives (section, section-head, table, switch) into a shared `player-panel.css` imported by `PlayerPageShell` | extract |
| 2 | First section content: NBA/NHL a one-row averages `dl`; NFL three week-bar charts plus a usage table card; tennis a 56px ELO number with a free-scaling SVG line chart plus surface numbers | All | `PlayerContextSections.tsx:20-29`, `NflPlayerUsage`/`NflPlayerContext`, `PlayerEloCard.tsx:29-60` | P1 | One `PlayerSeasonForm` frame: stat tiles on top (the `player-form-averages` style), one optional chart below in a fixed-height slot | layout |
| 3 | Tennis recent-form chart: 72px plot vs 112px, bars stretch about 250px wide vs 40px max, values in a row above, dates only (no opponent), below-line bars as outlined boxes, 11px DM Sans title, legend below the chart, no "N avg" | Tennis | `PlayerPropTabs.tsx:28-40`, `TennisPropEvidenceBody.tsx:24-37`, `tennis-prop-board.css:149-223` | P1 | Adapt tennis samples to `GameLogBars` + `FormSwitch` with the "Recent form · N avg" head | extract |
| 4 | Window/match switch: tennis `.tennis-prop-seg` vs shared `.nfl-prop-detail__switch` (28px, squared); serve/return adds a third pill `segment-toggle` (24px) | Tennis | `PlayerPropTabs.tsx:48-52,118-121`, `PlayerServeReturn.tsx:21-30` | P1 | One shared `SegmentSwitch` for window, match and surface choices | extract |
| 5 | Tennis game log uses `tennis-player-table` (DM Sans 600 th, 13px td, row hover, 20 rows) vs `nfl-player-table` (Barlow 700 11px th, 12px mono td, 10 to 12 rows) | Tennis | `PlayerMatchLog.tsx:20-41,51`, `tennis-player.css:66-96` | P1 | Render `nfl-player-table` (or a shared `PlayerTable`); cap at 10 to 12 rows | extract |
| 6 | NBA/NHL form bars all one gray with no dashed line while NFL shows above/below shading and a dashed line; the NBA/NHL hero says "vs 2.5 goblin line" on the same card | NBA, NHL | Charts only key on a standard rung: `nbaPlayer.ts:65-67,105-107`, `nhlPlayer.ts:66-68` | P1 | Chart against the line the hero names, labeled "Line 2.5 goblin" (display only, no number changes) | clarify |
| 7 | NFL projection block is `DetailProjection`: no Model/Sample facts row, white delta instead of gray, own CSS | NFL | `NflPlayerPropSection.tsx:34`, `NflPropDetailSections.tsx:13-20`, `nfl-prop-detail.css:23-56` | P1 | Feed `PlayerProjectionHero` from the NFL detail (display only) | extract |
| 8 | Tennis head has no stat chips; a right-aligned "Next match" block instead; blue ATP pill | Tennis | `TennisPlayerPage.tsx:47`, `PlayerHeader.tsx:10-19,34,36` | P1 | `PlayerHeadChips` (ELO, rank, 52-week W-L); Next match into the availability row; gray tour tag | layout |
| 9 | Model record: NBA/NHL one empty card; NFL meters + splits grid; tennis two `tennis-match-card`s with different padding | All | `PlayerContextSections.tsx:45-48`, `NflPlayerRecord`, `PlayerSidebar.tsx:14-22,111` | P2 | Shared two-slot `PlayerRecordGrid`; empty state keeps the grid | layout |
| 10 | Section title "Recent averages" (NBA, NHL) vs "Season form" (NFL, tennis); "PrizePicks lines" vs "Lines"; "Props on 2026-11-09" / "Props for week 9" / "Today's props" | All | `PlayerContextSections.tsx:19`, `NflPlayerPage.tsx:91`, `TennisPlayerPage.tsx:49`, `TennisMarketPanel.tsx:22`, the four `*PropTabs` | P1 | One vocabulary: "Season form", "Lines", "Props · {date or week}" | clarify |
| 11 | NFL odds-type tags colored (Goblin gold, Demon volcano orange-red); NBA/NHL gray | NFL | `nflLabels.ts:41-42`, `NflPropDetailSections.tsx:132` | P1 (signal rule) | Plain gray `Tag` | polish |
| 12 | Lines table columns differ: NBA Type/Line/Gap/P(over)/P(under); NHL adds Updated (CT) on every row; NFL Type/Line/P(over); tennis Type/Side/Line/Model/Gap/Hit/EV | All | `NbaPlayerMarketSection.tsx:21-24`, `NhlPlayerMarketSection.tsx:23`, `NflPropDetailSections.tsx:130`, `TennisMarketPanel.tsx:25` | P2 | One `PlayerLinesTable`: fixed core plus optional trailing columns; NHL timestamp to one caption | extract |
| 13 | Tennis ELO SVG text scales with width: about 23px at 1440, about 10px at 375 | Tennis | `PlayerEloCard.tsx:34` (viewBox 600), `tennis-player.css:21,113` | P1 (11px floor) | Fixed-pixel labels or the Recharts line from #31 | adapt |
| 14 | Extra tennis h2 "Serve and return · 52 weeks" styled 13px/600 with no rule, unlike every other h2 (12px/800 + rule) | Tennis | `PlayerServeReturn.tsx:21-30` | P2 | Fold into Season form as a sub-card with the shared section head | layout |
| 15 | Panel card-head caption is different content per sport (disclaimer / probability note / NFL repeat of the hero / start time + AntD-blue "Open match") | All | `NbaPlayerMarketSection.tsx:50-52`, `NhlPlayerMarketSection.tsx:44`, `NflPlayerPropSection.tsx:29-31`, `TennisMarketPanel.tsx:76` | P2 | Fixed slot: start time · reference/adopted status; themed gray link | clarify |
| 16 | Availability tags: three components with different weight, padding and height (`.nba-injury-tag`, `.nhl-player-injury-tag`, `.nfl-player-tag`); tennis has none | NBA, NHL, tennis | `NbaInjury.tsx:13`, `NhlPlayerPage.tsx:44`, `nfl-player.css:12-16` | P2 | One `PlayerTag` with tone variants | extract |
| 17 | h4 sub-heads vary: 13/700 (NBA), 11/600 (NHL), 12/600 (tennis); NHL team h3s and tennis "Lines" in DM Sans | NBA, NHL, tennis | per-sport CSS | P2 | One sub-head style in the shared sheet | typeset |
| 18 | Title suffix `<small>` ("#1", "reference") at 10.4px | NFL, NBA | `nfl-player.css:84` sets no size | P1 (11px floor) | `font-size: 11px` | typeset |
| 19 | NFL lines table has no overflow wrapper on phone | NFL | `NflPropDetailSections.tsx:129` | P2 | Wrap it | adapt |
| 20 | Source footer on NFL and tennis only | NBA, NHL | `NflPlayerFooter`, `PlayerIdentityFooter` | P3 | Shared `PlayerFooter` | extract |
| 21 | Small stuff: NFL builds chips by hand; tennis crumb 13px vs 12px; bar x-axis "Oct / 28" two lines vs tennis one; selected-row treatment differs; NBA/NHL table cell padding per sport; tennis not-found copy; game-log subtitles phrased differently | Various | see A's table | P3 | Fold into the shared components above | polish |

## Divergences that should stay

- Tennis match switch (a player can have props in two matches); restyle only.
- Tennis Side/Hit/EV columns (adopted-slice pipeline, 48g; a green margin there is legitimate); keep as optional trailing columns.
- Sport-specific game-log columns and the NFL model-record content; unify the frame only.
- Tennis ELO and serve/return as the content of Season form; NBA double-double yes/no list (binary market).

## Priority issues

1. [P0] Tennis panel CSS missing on cold load (rank 1). Fix: shared `player-panel.css`. Command: extract.
2. [P1] Lower half drawn by four sport-specific component sets (ranks 2 to 5, 9). Fix: shared `PlayerSeasonForm`, `GameLogBars` adapter, `SegmentSwitch`, `PlayerTable`, `PlayerRecordGrid`. Command: extract then layout.
3. [P1] NBA/NHL chart and hero disagree on the reference line (rank 6). Command: clarify.
4. [P1] Constraint breaches: NFL colored tags, 10.4px suffix, about 10px ELO axis on phone, AntD blue link. Command: polish / typeset / adapt.
5. [P1] Tap targets under 44px on all four at 375: crumbs 18 to 20px, market tabs 41px, form switch 28px, tennis segments 18px and 24px. Command: adapt.

## Persona red flags

- Alex (power user): tennis bars drop the opponent; NFL card head and hero repeat each other; no line to read hits against on NBA/NHL.
- Sam (accessibility): 10.4px suffix, about 10px ELO labels on phone, disabled reasons only in `title`, AntD-blue link at 3.7:1, tennis segments lose their focus ring on cold load.
- Casey (phone): tap targets above; NFL lines table with no scroll wrapper; tennis settled-props rows wrap to 2 to 3 lines.

## Minor observations

- NHL "Updated (CT)" repeats one timestamp per row.
- NBA "P(over) not fitted" sits under a column of dashes; hide the columns.
- `player-projection.css:1` comments that NFL keeps its own block, documenting gap 7 in code.
- 11px secondary notes sit exactly at the floor on every sport (detector tiny-text); consistent, not a violation.

## Questions to consider

- Is Season form one section with a fixed chart slot and tiles above, or is it four sports' season stories forced into one name?
- Should the form chart always draw the line the hero names, goblin and demon included?
- Is a 20-row match log or a 13-column NFL log what a player page is for, or a 10-row preview that opens the full log?

# Feature: NFL prop board

**From build-plan:** feature 31d (parent: 31. Web redesign)
**Status:** complete (2026-09-30)
**Branch:** `feature/nfl-prop-board`

## Goal

Rebuild the NFL prop board (`/nfl/board`) after
`prototypes/nfl-prop-board.html`. The ranked table becomes a grid of prop
cards, each showing the pick, line, model, edge and the player's last five
games as bars against the line. The evidence panel stays beside the grid. The
board shows the same lines, in the same order, with the same numbers and
colors it shows today.

## Design reference

- `prototypes/nfl-prop-board.html`: summary strip, market pills, position
  segment, card anatomy (player row, tags, line row, bars, foot), and the
  anytime-TD card.
- `prototypes/theme.css`: already ported into `web/src/index.css` in 31a;
  nothing to port.
- 31c's `components/tennis/TennisPropCard.tsx`, `tennis-prop-card.css` and
  `TennisPropBoardControls.tsx` are the pattern for cards, grid, pills and
  the sticky panel.
- **Where the mockup and this spec differ, the spec wins.** Item 31 is
  restyle only. User decisions, 2026-09-30:
  - **Bars only, no hit rates.** Each card draws the last five game values
    from `recentForm` with the line marked, grayscale. No L5 / L10 /
    vs-opponent counts and no meters: counts would be a new, unvalidated
    number, and lines carry no tenth game.
  - **Cards plus today's evidence panel,** sticky beside the grid and
    unchanged inside. 31e restyles it as the detail view; it is shared with
    the `/nfl` slate.
  - **P(over) stays in the panel only** (the 27g display rule). No card
    shows it.
  - **Anytime TD keeps today's visibility:** its rows appear only under
    "Show all lines", but render as a TD card.
- Also dropped from the mockup, because each is a new number or a new
  coloring:
  - "With an edge", "Stats through" and the projection-version summary cards
  - the L5 / L10 / Season range toggle
  - the green "Ready" trust dot (trust stays today's gray text, with the
    thin-sample caution)
  - the green-or-gray edge pill by sign (the pick and edge keep today's side
    coloring: OVER green, UNDER red, per open question 28)
  - the TD card's best price ("-140 DK"): lines carry no price or book name
  - the nav's lines-snapshot time

## In scope

- A pure `web/src/utils/nflPropCards.ts` mapping an `NflBoardLine` to what a
  card shows, with unit tests.
- **Page head.** Eyebrow, title and subtitle as today, the Slate/Board switch,
  the season and week selects, and a summary strip of two counts the page
  already has: Games (the game filter's option count) and Rateable (the sum
  of the market tabs' counts).
- **Controls.** Market tabs as pills with their rateable count; positions as
  a `.seg` group; the game select and "Show all lines" switch on the tokens.
  Behavior is unchanged.
- **Card grid.** Replaces `BoardTable` and `BoardRow`. Cards follow
  `category.rateable` order and keep their rank. With "Show all lines" on,
  today's "Not rateable" divider and note follow, then dimmed cards with no
  rank. Clicking a card selects it and moves the panel, as a row click does
  today; the selected card has a visible outline.
- **Stat card:** team badge, player, position, matchup and kickoff (plus the
  segment when not full game); tags; the line large in mono with the market
  unit; pick chip and edge share (side-colored), raw edge small; "Model" value;
  last-five bars (fewer when fewer games; "No completed history", the panel's
  wording, when none); foot with trust, `Ng` sample (caution when thin) and
  flags on hover, and "Why" as today's `signalSummary`, clamped to two lines
  with the full text on hover.
- **TD card:** model probability, the sportsbook consensus from
  `nflBookOddsEvidence` (or "No book price"), snap share when present, and
  tags. No bars (a TD game is 0 or 1), no pick, no edge, no rank change.
- **Layout.** Grid left, panel right and sticky; at 860px and below one card
  column with the panel stacked under it, and selecting a card scrolls the
  panel into view.
- Loading, error, empty-week and empty-category states, restyled in place.

## Out of scope

- Any new number: hit rates, over counts, P(over) on cards, an edge count,
  stats-through week, snapshot time, book prices.
- Any change to rateability, ranking, the reference line, edge share, the
  anytime-TD rule, or which lines exist. `utils/nflPropBoard.ts` is read, not
  changed.
- Recoloring the pick or edge, or removing their green (open question 28 is
  a separate decision).
- Restyling `NflEvidencePanel` or the `/nfl` slate (31e and later).
- The prop detail view (31e).
- Any API, schema or backend change.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit
   at the end.

Never accept a step you haven't read. If a diff is too big to review, the step
was too big, so split it.

## Build steps

- [x] **Step 1 - Baseline and card model.** First record the current page for
  the current week:
  - 1440px and 390px screenshots of `/nfl/board`, under `.playwright-mcp/31d/`
    (gitignored)
  - the game count and each market tab's rateable count
  - for the first five rows of two markets (the default and Receptions):
    player, pick, line, model, edge share, raw edge and trust
  - the order of `recentForm.values` (newest first or oldest first), read
    from `api/app/services/nfl/slate.py` and one live row

  Then add `web/src/utils/nflPropCards.ts` with `nflPropCard(row, rank,
  referenceLine)` and `recentBars(row)`, and `nflPropCards.test.ts`. No UI
  change.

  *Done when:* the baseline is recorded, `npm run test` passes, and the tests
  cover:
  - an OVER and an UNDER stat line (pick, `isUnder`, edge strings)
  - a null edge and a null reference line (`--`, no pick)
  - the team badge: the player's team from `opponentTeam` against
    away/home, and the position when the opponent is unknown
  - a non-full-game segment in the meta
  - an anytime-TD row (kind `td`, model as %, book summary or "No book
    price", snap share or null, and no bars)
  - an unknown market (unit falls back to the raw market name)
  - `recentBars`: bars oldest to newest, each above / below / push against
    the line, heights scaled to the largest of the values and the line, an
    empty `recentForm` returning `[]`, and a null line returning bars with
    `vsLine` null
  - thin-sample and flag pass-through
- [x] **Step 2 - Head, summary and controls.** Add
  `components/nfl/NflPropBoardControls.tsx`: the head (eyebrow, title,
  subtitle, view switch, season and week selects), the Games and Rateable
  counts as `.stat` blocks in large mono numbers, market pills with counts,
  position `.seg`, game select and the "Show all lines" switch on the tokens.

  *Done when:*
  - a 1440px screenshot shows the strip, pills and filters
  - both counts match the step 1 baseline
  - every control still changes the board as before
  - the build passes
- [x] **Step 3 - Stat cards.** Add `components/nfl/NflPropCard.tsx` (the card
  and the grid) and `nfl-prop-card.css`, rendered where `BoardTable` is
  today; delete `BoardTable`, `BoardRow` and their table CSS. Cards follow
  the card model from step 1, with the bars drawn in grayscale: above the
  line `--text-primary`, below `--text-secondary`, and a dashed line mark.
  Not-rateable cards are dimmed under today's divider.

  *Done when:*
  - the first five cards of both baseline markets match step 1 (order, pick,
    line, model, edge share, raw edge, trust)
  - one card's bars match the panel's "Recent form" values for that line, and
    a player with no history shows "No completed history"
  - clicking a card moves the panel to it, and on load the first card is
    selected, as the first row is today
  - an empty category shows today's message
  - the build passes

  Found while building:
  - `recentBars` returns `{ bars, linePct }` so the dashed mark sits on the
    bars' scale, and a partial-segment line (half, quarter) draws no mark and
    no above/below split, since the history is whole-game.
  - Bars read above `--text-primary`, push `--text-secondary`, below
    `--text-muted`.
  - The unit ("passing yards") sits on its own line under the value, which
    wrapped beside it.
  - A pick or edge of "--" (no edge, so no side) is gray, not today's green:
    it carries no number to color.
  - No stat line this week lacks history, so the "No completed history"
    branch is covered by its unit test; TD rows show it until step 4.
- [x] **Step 4 - Anytime-TD card.** The TD variant of `NflPropCard` for rows
  whose market is `anytime_touchdown`, shown only under "Show all lines" as
  today.

  *Done when:*
  - with "Show all lines" on, the Anytime TD tab lists TD cards in today's
    order, each with model %, book consensus or "No book price", and snap
    share where the panel shows one
  - with it off, the tab shows today's empty message
  - no TD card carries a pick, edge or rank
  - the build passes

  Found while building: no week-4 TD line is priced yet (the TD odds job runs
  Wednesday and Thursday), so every card reads "No book price"; the priced
  text is covered by the unit test. A player can appear once per segment
  (full game, 1st quarter, 1st half), as the table listed them.
- [x] **Step 5 - Layout and mobile.** The grid sits left and the panel right,
  sticky at `calc(var(--nav-height) + 16px)` and scrolling inside itself when
  taller than the viewport. At 860px and below: one card column, the panel
  stacked under the grid, and a card tap scrolls the panel into view.

  *Done when:*
  - at 1440px the panel stays pinned while the grid scrolls
  - at 390px there is 0px horizontal page overflow and tapping a card shows
    its evidence
  - the `/nfl` slate's panel looks as before (screenshot)
  - the build passes
- [x] **Step 6 - Visual pass.** Screenshot `/nfl/board` at 1440px and 390px
  loaded, loading, and errored (block `/nfl/slate` in the browser), plus an
  empty week. Run the impeccable detector on the page.

  *Done when:*
  - each state has a screenshot
  - the counts and first five cards of both baseline markets match the
    original page read at the same moment (stash the page edits and
    `reload()`, never a same-URL `goto`, as in 31c)
  - no `side-tab`, `border-accent-on-rounded` or `tiny-text` finding comes
    from this page's new CSS
  - `npm run build` and `npm run test` pass

  Found while building:
  - Same-moment check (2026-09-30): with the two page files stashed and the
    page reloaded, the old table and the new cards gave identical tab counts
    (28, 7, 6, 45, 8, 69, 10, 0, 10) and identical first five rows in Passing
    yards and Receptions (`same-old.json`, `same-new.json`).
  - Detector: no `side-tab` or `border-accent-on-rounded` finding, and no
    `tiny-text` from this page's CSS. The one 11px sentence-case text is in
    the unchanged evidence panel. The team badge and pick were raised to 12px
    anyway. Remaining findings are not ours: the panel's 8-10px labels and
    "Selected signal" kicker (31e), the shell's `transition: width` and the
    "App" wordmark contrast (known since 31b), and
    `first-viewport-column-overflow`, inherent to a long grid beside a pinned
    panel.
  - The empty week (week 1) shows today's message with both counts at 0.

## Files / areas

| File | Change | Steps |
|---|---|---|
| `web/src/utils/nflPropCards.ts` | new | 1 |
| `web/src/utils/nflPropCards.test.ts` | new | 1 |
| `web/src/pages/NflPropBoardPage.tsx` | head, controls, grid, layout | 2-5 |
| `web/src/components/nfl/NflPropBoardControls.tsx` | new | 2 |
| `web/src/components/nfl/NflPropCard.tsx` | new: stat card, TD card, grid | 3-4 |
| `web/src/components/nfl/nfl-prop-card.css` | new | 3-5 |
| `web/src/pages/nfl-prop-board.css` | table rules replaced by head, control and layout rules | 2-5 |

`NflEvidencePanel.tsx`, `nfl-slate.css` and `utils/nflPropBoard.ts` are not
edited. No API, schema or backend change.

## Data / contracts

Internal to this page (31e may reuse the card model, but nothing depends on
it yet):

```ts
interface NflPropCardModel {
  key: number                       // lineId
  kind: 'stat' | 'td'
  rank: number | null               // null for not-rateable cards
  playerName: string
  badge: string                     // player's team code, else position, else '--'
  meta: string                      // today's row text: 'WR · MIA @ LAC · 3:05 PM CDT', plus ' · 1st half' when not full game
  unit: string                      // marketLabel(market) lowercased
  lineText: string                  // '58.5' or '--'
  modelText: string                 // formatProjection(market, projection)
  pickLabel: 'OVER' | 'UNDER' | '--'  // today's pickLabel(edge)
  isUnder: boolean                  // edge < 0, today's is-negative rule
  edgeShareText: string             // edgePctLabel(edgeShare(row, referenceLine))
  edgeText: string                  // edgeLabel(edge), raw points
  trust: string                     // trustLabel(row)
  sampleText: string                // '12g', or '4g thin'
  thin: boolean                     // !isConfidentSample(row)
  injury: { label: string, color: string } | null   // today's injuryTag
  depthText: string | null          // depthLabel(row) when a depth_* flag is present
  flags: string[]                   // qualityFlags minus historical_baseline, for the hover
  why: string                       // signalSummary(row)
  bookText: string | null           // TD only: nflBookOddsEvidence(row, now) summary, else 'No book price'
  snapText: string | null           // TD only: snapShareLabel(row)
}

interface NflRecentBar {
  value: number
  opponentTeam: string | null
  heightPct: number                 // 0-100, scaled to max(values, line)
  vsLine: 'above' | 'below' | 'push' | null   // null without a full-game line
}

interface NflRecentBars {
  bars: NflRecentBar[]              // [] for anytime TD or no history
  linePct: number | null            // the line on the same scale; null for a partial segment
}
```

- `nflPropCard` reuses `edgeShare`, `isConfidentSample` (`nflPropBoard.ts`),
  `edgeLabel`, `edgePctLabel`, `trustLabel`, `signalSummary`
  (`nflSignal.ts`), `formatProjection`, `formatKickoffTime`, `marketLabel`,
  `segmentLabel` (`nflLabels.ts`), `injuryTag`, `depthLabel`
  (`nflAvailability.ts`), `snapShareLabel` and `nflBookOddsEvidence`. It must
  produce the strings the table cells produce today.
- `pickLabel` moves from the page into `nflPropCards.ts`.
- **Green:** as today, only the pick and edge use it, and only for OVER
  sides. Bars, trust, tags and the summary strip are grayscale.

## Testing

- **Step 1 baseline** (2026-09-30 13:54 UTC, `.playwright-mcp/31d/`): 2026
  week 4, 16 upcoming games, 183 rateable across nine tabs (Passing yards 28,
  Pass attempts 7, Pass completions 6, Rushing yards 45, Rush attempts 8,
  Receiving yards 69, Receptions 10, Anytime TD 0, Fantasy points 10).
  Default tab Passing yards; first five rows of it and Receptions in
  `baseline.json`. `recentForm.values` arrive newest first (repository orders
  season, week, start descending).
- **Step 1 ships unit tests** (`nflPropCards.test.ts`) for the card model and
  `recentBars`: pure logic with real branches (side, nulls, team badge,
  segment, TD, bar scaling and the line comparison).
- `nflPropBoard.test.ts` and `nflSignal.test.ts` must pass unchanged.
- Steps 2-6 are layout and styling, checked with the build, screenshots at
  1440px and 390px, the impeccable detector, and the step 1 baseline.
- Run `npm run build` and `npm run test` after every step.
- This page makes no The Odds API request; nothing here spends credits.

## Notes for the AI

- **Restyle only.** If a card needs a number `NflBoardLine` does not carry,
  stop and ask rather than deriving one.
- **The panel is shared.** `NflEvidencePanel` also renders on `/nfl`; do not
  edit it or `nfl-slate.css`. Layout rules for the board go in
  `nfl-prop-board.css` under `.nfl-prop-board`.
- **The edge tooltip stays.** Today's "Edge ?" header tooltip explains the
  shared reference line; keep it on the edge share (on the value or a small
  "?" beside it), since cards have no header row.
- Tint token colors with `withAlpha()` (`utils/color.ts`), never by appending
  hex alpha. No new hex outside `:root`. The pick and edge keep today's
  `--nfl-green` / `--nfl-red`, so their colors cannot drift.
- 11px is for uppercase labels and chips only; sentence text is 12px or more
  (31c's detector finding).
- The page's JSX is packed into long single lines. Split it into components
  under about 50 lines as you touch it.
- Data fetching stays in the page's existing hooks; new components take
  props only.
- `prototypes/` stays until 31e's `/complete`.
- Browser checks: if the Playwright MCP browser is locked, use the API
  venv's Python Playwright, as in 31c and 32c.

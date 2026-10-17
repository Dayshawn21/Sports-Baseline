# Feature: Tennis prop board

**From build-plan:** feature 31c (parent: 31. Web redesign)
**Status:** complete (2026-09-28)
**Branch:** `feature/tennis-prop-board`

## Goal

Rebuild the Tennis Props page (`/tennis/board`) after
`prototypes/tennis-props.html`. The ranked table becomes a grid of prop cards,
each showing the pick, line, projection and hit probability against the
payout break-even. The evidence panel stays beside the grid. The page shows
the same lines, in the same order, with the same numbers it shows today.

## Design reference

- `prototypes/tennis-props.html`: summary strip, market pills, card anatomy
  (player row, side and line, projection, hit bar with break-even tick, foot).
- `prototypes/theme.css`: `.card`, `.tag`, `.seg`, `.stat` and `.bars`. The
  tokens were already ported into `web/src/index.css` `:root` in 31a, so this
  feature builds against them and does not port them again.
- 31b's side panel (`web/src/components/tennis/tennis-slate.css`) is the
  pattern for the sticky panel.
- **Where the mockup and this spec differ, the spec wins.** Item 31 is restyle
  only. These are user decisions from 2026-09-28:
  - **No recent-match bars or L5/L10/surface hit rates on cards.** Board rows
    carry no match history. Bars appear only in the evidence panel, drawn from
    the last-5 box scores it already fetches, with the line marked and no
    "3/5"-style counts.
  - **EV and pick keep today's side coloring:** OVER green, UNDER red,
    whatever the EV's sign. The mockup's sign coloring is not adopted.
  - **Cards plus the side panel,** not the mockup's panel-less grid.
- Also dropped from the mockup, because each would be a new number or new
  behavior:
  - the "Linked to a match" % and projection-version summary cards
  - the Standard/Goblin/Demon filter (goblins are already excluded from the
    board) and the L5/L10/Surface toggle
  - player-initial avatars (the tour shows as a tag instead)
  - the green fill on the hit bar (it stays neutral, with the break-even tick
    as the reference)
  - green or black-on-green tier chips (the confidence tier shows as a
    neutral chip)

## In scope

- A pure `web/src/utils/tennisPropCards.ts` that maps a `TennisBoardLine` to
  what a card shows, with unit tests.
- **Page head.** Title, subtitle, and a summary strip of two counts the page
  already has: Lines (today's `visibleLineCount`) and Rateable (the sum of
  every category's rateable count, which is today's tab counts added up).
- **Controls.** Market tabs restyled as pills with their rateable count, and
  the filter bar (source, tour, Show all lines) restyled as `.seg` groups.
  Behavior is unchanged.
- **Card grid.** Replaces `BoardTable` and `BoardRow`. Cards follow
  `category.rateable` order, and each card keeps its rank number. With Show
  all lines on, the "Not rateable" divider follows, then dimmed cards with no
  rank. Clicking a card selects it; the selected card has a visible outline.
- **Card types.** Each kind of row renders on the same card:
  - prop lines (PrizePicks, DK, Bet365)
  - moneyline rows: the value reads "Odds"
  - win-a-set rows: the value reads "Market" or "Unpriced", and the pick shows
    the confidence
- **Side panel.** The evidence panel, sticky beside the grid, restyled on the
  tokens: no stripes, labels at 11px or larger.
- **Panel recent bars.** For aces, double faults and break points, the
  selected player's last completed matches become bars, with the line drawn
  across them and each value labeled. Other markets keep today's text list.
- Loading, all-failed error, partial-error notice, empty category and empty
  source states, restyled in place.
- **Mobile (390px).** One card column; the panel stacks under the grid, and
  selecting a card scrolls it into view.

## Out of scope

- Any new number: hit rates, L5/L10 counts, linked %, projection version,
  stakes.
- Any change to rateability, ranking, tiers, EV, which markets exist, or the
  goblin exclusion. `utils/tennisPropBoard.ts` logic is read, not changed.
- Recoloring EV or the pick by sign (user decision: keep side coloring).
- A "Slate / Props" segmented switch in the page head. The nav already links
  both pages; adding the switch is a navigation change.
- NFL prop board and prop detail (31d, 31e).
- Any API, schema, or backend change.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Baseline and card model.** First record the current page:
  - 1440px and 390px screenshots of `/tennis/board`, saved under
    `.playwright-mcp/` (gitignored)
  - the line count and each category's rateable count
  - for the first five rows of the default category: player, pick, line,
    model, EV and trust

  Then add `web/src/utils/tennisPropCards.ts` with `propCard(row)` and
  `tennisPropCards.test.ts`. No UI change.

  *Done when:* the baseline is recorded, `npm run test` passes, and the tests
  cover:
  - a standard prop
  - an UNDER prop (side is `under`)
  - a goblin/demon payout tag
  - a moneyline row (value label "Odds", signed odds, model as %)
  - a win-a-set row with and without a market (pick is the confidence; value
    reads "Unpriced" when missing)
  - missing hit probability or break-even (no bar)
  - `hitPct` and `breakEvenPct` clamped to 0-100
  - flags passed through for tags
- [x] **Step 2 - Head, summary strip and controls.** Restyle the page head:
  eyebrow, title, subtitle, and the Lines and Rateable counts as `.stat`
  cards in large mono numbers. Market tabs become pills with counts. Source,
  tour and Show all lines become `.seg` groups and a switch on the tokens.

  *Done when:*
  - a 1440px screenshot shows the strip, pills and filters
  - both counts match the step 1 baseline
  - every control still changes the board as before
  - the build passes
- [x] **Step 3 - Card grid.** Add `TennisPropCard` and `TennisPropCardGrid`,
  rendered where `BoardTable` is today; delete `BoardTable`, `BoardRow` and
  their table CSS. Each card shows:
  - **Head:** rank, player, then matchup, tournament and start time, plus a
    neutral confidence chip
  - **Tags:** tour, payout tier (goblin or demon), and quality flags
  - **Value:** the side label and the line (or odds, or market) large in mono,
    with the projection on the right
  - **Hit bar:** hit % and EV (side-colored), the bar, and "Break-even X% ·
    tier"
  - **Foot:** "Opp allows X" when known, trust label, source, and `n=`
    sample, with all flags on hover

  Not-rateable cards are dimmed under the existing divider.

  Decided while building: quality-flag chips are neutral gray, at most two
  plus "+N"; moneyline rows carry 3-5 `ctx_*` flags, and caution yellow
  drowned the card. Caution stays on the foot's trust text, as today's
  `is-flagged` sample did. The value keeps today's label under it (Line,
  Odds, Market), and the projection reads "Model", today's column name.

  *Done when:*
  - the first five cards match the step 1 baseline (order, pick, line, model,
    EV, trust)
  - clicking a card moves the panel to it
  - a moneyline card and a win-a-set card each render without "NaN" or
    "undefined"
  - empty categories show today's empty messages
  - the build passes
- [x] **Step 4 - Layout and panel restyle.** The grid is wide on the left and
  the panel sits on the right, sticky at `calc(var(--nav-height) + 16px)`,
  scrolling inside itself when taller than the viewport. Restyle
  `TennisPropEvidencePanel` sections on the tokens (header, metrics, reason,
  grid, inputs, form, quality notes) with no side-tab or top stripes and
  labels at 11px or larger. Its fields and text stay as today.

  *Done when:*
  - at 1440px the grid and panel sit side by side, and scrolling keeps the
    panel pinned
  - the panel shows the same fields as the baseline for the selected line
  - the impeccable detector reports no `side-tab`, `border-accent-on-rounded`
    or `tiny-text` finding on `/tennis/board`

  Found while building: the detector reads 11px sentence-case text as
  `tiny-text`, so 11px is kept for uppercase labels and chips only; value
  labels, form stats, history lines and input tags moved to 12px. Pill counts
  use a text color instead of `opacity`, which the detector flagged as
  low-contrast. Remaining findings are either not ours or not in scope:
  - `layout-transition` (`transition: width`) comes from the shared app shell,
    and `/` reports it too
  - the "App" wordmark contrast is the known 31b artifact
  - `kicker-above-heading` ("Selected signal") and the player name repeated 3x
    are panel text, which stays as today
  - `first-viewport-column-overflow` is inherent to a long grid beside a
    pinned panel
- [x] **Step 5 - Panel trim.** (User decision, 2026-09-28, after step 4.)
  The cards now carry the headline numbers, so the panel drops what repeats
  the selected card and keeps the evidence. No number leaves the page: every
  cut value is on the selected card beside the panel.
  - **Header:** the player name, with market and source under it. The
    "Selected signal" label, the payout tier and the EV are dropped.
  - **Cut:** the Model / Line / Trust row, and Matchup, Start, Sample, Hit
    probability and Break-even.
  - **Kept:** Why this signal, projection inputs, player form, and quality
    notes, unchanged.
  - **The context block keeps three facts:**
    - Event: tournament and surface. Surface is on no card.
    - Opponent allows: with the opponent's sample.
    - Projection basis.
  - **Mobile summary:** at 860px and below, where the panel sits away from its
    card, one line opens the panel: pick, value and EV, in the card's strings
    and side coloring. It is hidden when the panel sits beside the grid.

  *Done when:*
  - at 1440px the panel shows none of the cut fields
  - at 390px the summary line shows the selected card's pick, value and EV
  - the detector no longer reports `kicker-above-heading` or the repeated
    player name
  - the build passes

  Found while building: `kicker-above-heading` is gone, but the repeated-name
  finding stays. The name's other two appearances are the serve-and-return
  comparison and the last-5 history, which name both players by design.
  The summary line shows wherever the panel stacks (1180px and below until
  step 7 moves the stack to 860px).

- [x] **Step 6 - Panel recent bars.** Add `recentStatBars(matches, statType,
  line)` to `tennisPropCards.ts`, with tests. It returns one bar per match
  (date, opponent, value or null, and above, below or push against the line)
  for aces, double faults (`doubleFaults`) and break points
  (`breakPointsConverted`), and returns null for other markets. The panel
  draws the selected player's bars:
  - a dashed line at the prop line
  - values above the line in `--text-primary`, below in `--text-secondary`
  - a null value as an empty slot marked "--"

  No green, and no count or rate text. Today's text list stays under the
  bars. Markets without bars show the list only.

  *Done when:* tests cover each supported stat, an unsupported stat, a null
  value, and a push; an aces line's bar values match the list beside them;
  a total-games line shows the list with no bars; the build passes.

  Found while building:
  - Many lower-tier players have no box scores, so a chart of five empty
    slots said nothing. The chart is hidden when every value is missing
    (2 of the first 5 double-faults lines).
  - The bars sit above the 52-week comparison, and today's list stays below
    that.
  - Bars read oldest to newest, while the list reads newest first.
- [x] **Step 7 - Mobile.** At 860px and below, the grid is one column and the
  panel stacks under it; selecting a card scrolls the panel into view.

  *Done when:* 390px screenshots show readable cards with no horizontal page
  scroll, and tapping a card shows its evidence.

  Found while building: the panel is the last thing on the page, so the scroll
  can stop short of the top (at 188px in the test) while the new player's
  recent form loads. The panel header and summary are still in view.
  Between 861px and 1180px the grid (one card column) and the panel stay side
  by side.
- [x] **Step 8 - Visual pass.** Screenshot `/tennis/board` at 1440px and 390px
  in four states:
  - loaded
  - loading
  - all sources failed
  - partial error (block one props request in the browser)

  Then run the impeccable detector on the page.

  *Done when:*
  - each state has a screenshot
  - the counts and the first five cards match the original page read at the
    same moment. Stash the page edits and `reload()`; never use a same-URL
    `goto`, which keeps filter state. Lines drift as matches start (31b
    step 8).
  - there is no low-contrast finding beyond the known wordmark artifact
  - `npm run build` and `npm run test` pass

## Files / areas

| File | Change | Steps |
|---|---|---|
| `web/src/utils/tennisPropCards.ts` | new | 1, 6 |
| `web/src/utils/tennisPropCards.test.ts` | new | 1, 6 |
| `web/src/pages/TennisPropBoardPage.tsx` | head, controls, grid, layout | 2-4 |
| `web/src/components/tennis/TennisPropBoardControls.tsx` | new: head and summary, market pills, filter segments | 2 |
| `web/src/components/tennis/TennisPropCard.tsx` | new, holds the card and the grid | 3 |
| `web/src/components/tennis/tennis-prop-card.css` | new: card, grid, divider and empty-state rules | 3 |
| `web/src/components/tennis/TennisPropEvidencePanel.tsx` | restyle, trim and recent bars | 4-6 |
| `web/src/pages/tennis-prop-board.css` | table rules replaced by card and panel rules | 2-7 |
| `web/src/pages/tennis-prop-board-filters.css` | control rules | 2-7 |

No API, schema, or backend change.

## Data / contracts

Internal to this page (no later feature depends on them):

```ts
interface TennisPropCardModel {
  key: string                        // `${source}-${id}`
  playerName: string                 // 'Unknown player' when missing
  meta: string                       // matchup (else tour · surface) · tournament, parts omitted when null
  startText: string                  // today's CT format: 'Sep 28, 11:10 PM CDT', or 'Time unavailable'
  tour: string | null
  confidence: string | null          // neutral chip
  payoutTier: 'standard' | 'goblin' | 'demon' | null  // payoutTier(row); today's rows tag STANDARD too (found in step 1)
  flags: string[]                    // dataQualityFlags
  isUnder: boolean                   // today's `is-under` rule: recommendation === 'UNDER'; OVER and BET stay green
  pickLabel: string                  // OVER / UNDER / BET, or confidence ?? 'MODEL' for win-a-set
  valueLabel: 'Line' | 'Odds' | 'Market'
  valueText: string                  // '11.5', '+145', 'Unpriced', or '--'
  unit: string | null                // marketLabel(statType) lowercased for props, else null
  projectionText: string             // statAvg as '13.4', or '62.0%' for moneyline and win-a-set
  hitPct: number | null              // hitProbability * 100, clamped 0-100
  breakEvenPct: number | null        // breakEvenPct, clamped 0-100; market probability for moneyline
  breakEvenLabel: string | null      // 'Break-even 57.7% · standard', or 'Market 54.0%' for moneyline
  evText: string                     // '+14.4%', or '--'
  opponentText: string | null        // 'Opp allows 0.6' when opponentStatAvg is known
  trust: string                      // trustLabel(row)
  source: string                     // sourceLabel(row.source)
  sampleText: string                 // 'n=34', or '--'
}

interface RecentStatBar {
  matchDate: string
  opponentName: string
  value: number | null
  vsLine: 'above' | 'below' | 'push' | null   // null when value is null
}
```

- `propCard` (in `tennisPropCards.ts`, with `startLabel`, moved from the page) reuses `lineNumber`, `isMoneyline`, `isWinASet`, `payoutTier`,
  `trustLabel`, `sourceLabel` and `marketLabel` from `tennisPropBoard.ts`,
  and must produce the same strings the table cells produce today.
- `recentStatBars(...)` returns `RecentStatBar[] | null`, where null means an
  unsupported market.
- **Green:** as today, only the pick and EV use it, and only for OVER sides.

## Testing

- **Step 1 baseline** (2026-09-28, `.playwright-mcp/31c/`): 953 lines, 123
  rateable. Default tab Aces holds 1 rateable row, so the first-five
  comparison also uses Moneyline, total games won and Double faults
  (`baseline-tabs.json`).
- **Step 1 ships unit tests** (`tennisPropCards.test.ts`) for the card model,
  and **step 6 adds tests** for `recentStatBars`. Both are pure logic with
  real branches: row type, missing values, clamping, and the line comparison.
- Steps 2, 3, 4, 5, 7 and 8 are layout and styling. They are checked with:
  - the build
  - screenshots at 1440px and 390px
  - the impeccable detector
  - a comparison against the step 1 baseline: both counts and the first five
    rows
- Run `npm run build` and `npm run test` after every step.
- This page makes no Odds-API.io request. Keep Live Odds out of the checks.

## Notes for the AI

- **Restyle only.** If a card needs a number `TennisBoardLine` does not carry,
  stop and ask rather than deriving one.
- The existing `tennisPropBoard.test.ts` must keep passing unchanged.
- Reuse the page's `startLabel` Central-time format, or `fmtStartCT` from
  `utils/format` if it produces the same string, rather than adding a third
  formatter.
- Tint token colors with `withAlpha()` (`utils/color.ts`), never by appending
  hex alpha. No new hex outside `:root`.
- The page's current JSX is packed into long single lines. Split it into
  components under about 50 lines as you touch it.
- Data fetching stays in the page's existing hooks; new components take props
  only. The panel keeps its own `useMatchRecentForm(row.matchId)`.
- The recent-form response holds both players. Pick the bar player by
  `row.playerId`, and fall back to a name match for rows whose `playerId` is
  null.

## Completion notes

- **Evidence:**
  - `npm run build` and `npm run test` pass (250 tests, 21 files; 14 in
    `tennisPropCards.test.ts`).
  - Same-moment comparison against the original page: the edits in `web/src`
    were stashed, the page was reloaded with `reload()`, and the stash was
    popped. Aces, Moneyline, total games won and Double faults matched
    exactly on both counts (953 / 123) and the first five rows (player, pick,
    value, model, EV, trust).
  - Loaded, loading, all-sources-failed and partial-error (DraftKings forced
    to 500) states were screenshotted at 1440px and 390px
    (`.playwright-mcp/31c/step8-*`).
- **Decisions made while building** (recorded in the steps above):
  - payout tier includes STANDARD
  - quality-flag chips are neutral
  - 11px only for uppercase labels
  - the panel trim (new step 5, user decision)
  - the bar chart is hidden when every box score is missing
  - the bar caption drops the player name (the header already names them;
    the detector read the uppercase name as `all-caps-body`)
- **Remaining detector findings** (all soft or not ours):
  - `layout-transition` comes from the shared shell (`/` has it too)
  - the "App" wordmark contrast is the known artifact
  - the player name appears 3x because the form sections name both players
  - `first-viewport-column-overflow` is inherent to a long grid beside a
    pinned panel
  - `text-overflow` on the card matchup line is an intended ellipsis
- **Follow-ups (not changed here):**
  - With DraftKings forced to fail, the line count stayed 953, which suggests
    the DK props endpoint returns no lines on today's slate. Worth a look
    separately.
  - The Playwright MCP browser was locked by another session all feature, so
    checks ran through the API venv's Python Playwright.

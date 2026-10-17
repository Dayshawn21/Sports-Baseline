# Feature: NFL prop detail

**From build-plan:** feature 31e (parent: 31. Web redesign)
**Status:** complete (2026-09-30)
**Branch:** `feature/nfl-prop-detail`

## Goal

Restyle `NflEvidencePanel`, the side panel shared by the NFL slate (`/nfl`)
and the NFL prop board (`/nfl/board`), as the detail view in
`prototypes/prop-detail.html`: player header, a large projection against the
line, the last games as bars, a "How the projection is built" breakdown, the
PrizePicks lines, the game market, and a status card. It stays a panel, shows
the same numbers it shows today, and adds only the one-book game market the
slate already shows. This is the last item-31 sub-feature, so its
`/complete` discards `prototypes/`.

## Design reference

- `prototypes/prop-detail.html`: section order and anatomy (player row, big
  projection, game-log bars with a dashed line mark, breakdown rows with a
  muted "why" line, lines table, game market table with a muted model strip,
  status key-values).
- `prototypes/theme.css`: already in `web/src/index.css` since 31a; nothing
  to port.
- 31d's `components/nfl/NflPropCard.tsx` and `nfl-prop-card.css`: the bar and
  line-mark pattern to match, drawn from the same `recentBars`.
- **Where the mockup and this spec differ, the spec wins.** User decisions,
  2026-09-30:
  - **A restyled panel, not a page.** No new route; the panel keeps its place
    on `/nfl` and `/nfl/board`.
  - **Dropped, because the data does not exist or it is new behavior:**
    - the L5 / L10 / L20 / season toggle and a ten-game log (lines carry
      five recent games, with no week label)
    - the hit-rate row (L5 over, L10 over, vs opponent, L10 average)
    - the four-book game market (the slate carries one book)
    - practice status by day (one status is stored)
    - the "Track bet" button
  - **Kept from one book:** the game market card shows the slate's one book
    (moneylines, home spread, total) and the muted team-strength model strip.
- Also dropped from the mockup, as in 31d, because each is a new number or a
  new coloring:
  - the "+8.7% edge" share (the board's reference-line share; the panel shows
    the raw edge, as today)
  - a baseline value and a "Game moneyline +1.3%" breakdown row (lines carry
    no baseline number or moneyline adjustment)
  - "Proj - line" and "L10 over" on alternate lines, and green on the
    standard row
  - green "best price" dots in the game market
  - the "Snapshot" time
  - the amber trust color (trust stays gray text)

## In scope

- A pure `web/src/utils/nflPropDetail.ts` turning a line, its alternates and
  its game into what the panel shows, with unit tests.
- **Header:** team badge (as the card's), player name, and a meta line of
  position, market, matchup and kickoff, plus the segment when not full game.
  The "Selected signal" kicker goes.
- **Projection:** "Projected <market unit>", the projection large in mono, and
  under it the raw edge with today's side color and the line ("+5.6 vs 64.5
  line"). "--" and gray when there is no edge.
- **Game log:** the five `recentForm` values as bars, oldest to newest, with
  the value above and the opponent below each bar and a dashed line mark,
  grayscale as on the cards; "No completed history" when empty; the average
  and game count as today. TD lines show no bars (0 or 1), only the text.
- **Context:** today's "Vs <opp>" and "<opp> allowed to all <pos>s" history
  blocks, restyled, with the same text.
- **How the projection is built:** today's "Why this signal" sentence, then
  rows for Baseline (games and season, with `BASELINE_REASON_LABELS` as the
  muted line), Matchup (signed %, with today's allowed text), Usage (signed %
  or "Not applicable"), Snap share (TD only, when present), and the
  Projection total.
- **PrizePicks lines:** a table of the selected line and its alternates: type
  tag, line, and P(over) where today's tags show one. The 27g note keeps
  today's tooltip text and stays muted.
- **Sportsbooks:** today's TD consensus block, when present.
- **Game market:** book name, away and home moneyline, home spread, total, and
  the model strip text from `nflGameModelSummary` with "Model · not a pick",
  all gray. "No game market" when the game has no odds; no strip without a
  model.
- **Status:** line shape (type and segment), injury (with practice, as
  today's `injuryLabel` joins them), depth, trust.
- **Quality notes:** today's flag tags and tooltips.
- Both pages pass the selected line's game to the panel. The board finds it by
  `gameId` in the slate it already loaded; no new request.
- Panel CSS moves out of `nfl-slate.css` into its own file; loading and empty
  cases are unchanged (the panel renders only when a line is selected).

## Out of scope

- A detail route, deep links, or a "back to board" crumb.
- Any number lines do not carry: hit rates, a ten-game log, per-day practice,
  more books, a baseline value, a moneyline adjustment, edge share, snapshot
  time.
- Tracking a bet from the panel.
- Recoloring the edge (open question 28), coloring P(over) or the model strip.
- The slate's signal boards, matchup bar, model strip and game notes, and the
  board's cards and controls.
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

- [x] **Step 1 - Baseline and detail model.** First record, for the current
  week, under `.playwright-mcp/31e/` (gitignored):
  - 1440px, 1280px and 390px screenshots of the panel on `/nfl` and
    `/nfl/board`
  - the panel's full text for three lines: an OVER stat line with
    alternates, an UNDER stat line, and an anytime-TD line (with "Show all
    lines" on)

  Then add `web/src/utils/nflPropDetail.ts` with `nflPropDetail(row, game,
  alternates, now)` and `nflPropDetail.test.ts`. No UI change.

  *Done when:* the baseline is recorded, `npm run test` passes, and the tests
  cover:
  - header: badge and meta from the game (away and home, kickoff), a
    non-full-game segment, and a null game (meta without matchup or kickoff)
  - projection: OVER and UNDER delta text and `isUnder`, a null edge and a
    null line (`--`)
  - breakdown: a known and an unknown `baselineReason`, null matchup and
    usage, snap share only on TD
  - lines: selected line first, then alternates in given order, P(over) only
    where `pOver` is not null
  - game market: signed spread, moneylines, a null odds block ("No game
    market"), and a null model (no strip)
  - status: injury "Clear" and depth "Not listed" defaults, trust text
  - every string matches what today's panel renders for the same field
- [x] **Step 2 - Header, projection and game log.** Rebuild the top of
  `NflEvidencePanel` from the detail model: header, projection, and game-log
  bars from `recentBars`. Add
  `components/nfl/nfl-prop-detail.css`. Both pages pass `game`. The rest of
  the panel stays as today, below.

  *Done when:*
  - the three baseline lines show the same player, market, model, line, edge
    and recent values as in step 1
  - one line's bars match its recent-form values oldest to newest, with the
    dashed mark at the line; a TD line shows no bars
  - both pages still select lines and move the panel as before
  - the build passes
- [x] **Step 3 - Context, breakdown, lines and sportsbooks.** The two
  context history blocks, the "How the projection is built" card, the
  PrizePicks lines table with the muted P(over) note, and the sportsbook
  block, replacing today's metrics, reason, grid rows and alternate tags.

  *Done when:*
  - each baseline line's vs-opponent and allowed history, baseline, matchup,
    usage, snap share, alternates and P(over) text match step 1
  - no number is green or red except the header edge
  - the build passes
- [x] **Step 4 - Game market, status and notes.** The game market card, the
  status card and the quality notes; delete the old panel rules from
  `nfl-slate.css`.

  *Done when:*
  - the game market matches the slate's matchup bar and model strip for the
    same game (book, spread, total, model spread, win probability, total)
  - a game with no odds shows "No game market"
  - status and flags match step 1
  - `nfl-slate.css` holds no `.nfl-evidence-*`, `.nfl-alternate-lines` or
    `.nfl-quality-notes` rule
  - the build passes
- [x] **Step 5 - Layout and mobile.** Widen the panel toward the mockup's
  440px only as far as the slate's signal rows and the board's card grid keep
  their current columns at 1280px; keep it sticky and scrolling inside
  itself, and keep the board's (860px) and slate's (1180px) stacking
  breakpoints. The slate panel gains the board's inner scroll.

  *Done when:*
  - at 1280px neither page's rows or cards lose a column or truncate more
    than in the step 1 screenshots
  - at 1440px the panel stays pinned on both pages and scrolls inside itself
  - at 390px there is 0px horizontal page overflow on both pages, and bars,
    tables and the game market fit
  - the build passes

  Found while building: the width is `--nfl-detail-width: clamp(360px, 28vw,
  440px)` on `.nfl-slate`, used by both layouts, so 1280px keeps today's
  360px (identical row columns, 0 clipped player names, two card columns),
  1440px gets 403px (three card columns at 302px), and 440px arrives at
  about 1570px.
- [x] **Step 6 - Visual pass.** Screenshot the panel at 1440px and 390px on
  both pages for the three baseline lines, run the impeccable detector, and
  compare against the original panel read at the same moment (stash the
  panel edits and `reload()`, never a same-URL `goto`, as in 31c and 31d).

  *Done when:*
  - every number and label the old panel showed is present in the new one
    for the three lines, and the only addition is the game market card
  - the detector reports no `tiny-text`, `side-tab` or
    `border-accent-on-rounded` finding from the panel's CSS
  - `npm run build` and `npm run test` pass

  Found while building (2026-09-30):
  - **Comparison method.** `git stash` was dropped: it cannot stash the new
    untracked files, and a failed push made the `pop` reach an older,
    unrelated stash (git aborted it; nothing changed). Instead, `/nfl/slate`
    for week 4 was refetched and game 49, the three lines and their ladders
    were identical to the step 1 fetch, so `baseline.json` is the same-moment
    reading.
  - Every baseline string is present in the new panel for all three lines,
    except the stat lines' "value vs opponent" recent-form pairs, which are
    now the bars (value above, opponent below; same five values).
  - All three lines open on `/nfl/board` too (the TD line under "Show all
    lines"), at 1440px and 390px (`step6-*`).
  - Detector (injected `detect-antipatterns-browser.js`): 0 findings inside
    `.nfl-prop-detail` on either page at 1440px or 390px; a planted 9px
    sentence in the panel was caught as `tiny-text`, so the filter is real.
    The rest are not ours: the slate's game strip and signal rows
    (`undersized-ui-text`, `text-overflow`, `tiny-text`), the shell's
    `layout-transition`, and one `edge-flush-cards` and one `all-caps-body`
    outside the panel.

## Files / areas

| File | Change | Steps |
|---|---|---|
| `web/src/utils/nflPropDetail.ts` | new | 1 |
| `web/src/utils/nflPropDetail.test.ts` | new | 1 |
| `web/src/components/NflEvidencePanel.tsx` | rebuilt from the detail model; takes `game` | 2-4 |
| `web/src/components/nfl/NflPropDetailSections.tsx` | new: section components | 2-4 |
| `web/src/components/nfl/nfl-prop-detail.css` | new | 2-5 |
| `web/src/pages/nfl-slate.css` | panel rules removed; layout width | 4-5 |
| `web/src/pages/nfl-prop-board.css` | panel wrapper width | 5 |
| `web/src/pages/NflIntelligencePage.tsx` | pass `game` to the panel | 2 |
| `web/src/pages/NflPropBoardPage.tsx` | look up and pass `game` | 2 |

`utils/nflPropCards.ts` exports its badge rule as `teamBadge(row, awayTeam,
homeTeam)` (step 1) so the card and the panel share it; `recentBars` is read
as is. No API, schema or backend
change.

## Data / contracts

Internal to the panel:

```ts
interface NflPropDetailModel {
  badge: string                       // same rule as the card's badge
  playerName: string
  meta: string                        // 'WR · Receiving yards · MIA @ LAC · 3:05 PM CDT' (+ ' · 1st half')
  projectionLabel: string             // 'Projected receiving yards'
  projectionText: string              // formatProjection(market, projection)
  deltaText: string                   // '+5.6 vs 64.5 line', or '--'
  isUnder: boolean                    // edge < 0, today's is-negative rule
  hasEdge: boolean                    // edge !== null; gray when false
  why: string                         // today's reason sentence, opponent adjustment included
  breakdown: { label: string, value: string, note: string | null }[]
  lines: { key: number, typeLabel: string, typeColor: string, lineText: string, pOverText: string | null, selected: boolean }[]
  pOverNote: string | null            // overProbabilityLabel(row)
  gameMarket: {
    book: string
    rows: { label: string, value: string }[]   // away ML, home ML, spread, total
    modelText: string | null          // spread · win prob · total from nflGameModelSummary
    modelVersion: string | null
  } | null                            // null: 'No game market'
  status: { label: string, value: string, note: null }[]  // line shape, injury (with practice), depth, trust
  flags: { key: string, label: string, tooltip: string }[]
}
```

- `nflPropDetail(row: NflSlateLine, game: NflSlateGame | null, alternates:
  NflSlateLine[], now: number)`.
- Reuses today's helpers: `edgeLabel`, `overProbabilityLabel`,
  `overShareLabel`, `signalSummary`, `trustLabel` (`nflSignal.ts`),
  `formatProjection`, `formatKickoffTime`, `marketLabel`, `segmentLabel`,
  `matchupAllowedLabel`, `ODDS_TYPE_LABELS`, `ODDS_TYPE_COLORS`,
  `FLAG_LABELS`, `BASELINE_REASON_LABELS` (`nflLabels.ts`), `depthLabel`,
  `injuryLabel` (`nflAvailability.ts`), `snapShareLabel`,
  `nflBookOddsEvidence`, `nflGameModelSummary`, `recentBars`.
- **Green:** only the header edge, and only for OVER, as today. Bars, lines,
  P(over), the game market and model strip, status and flags are grayscale.

## Testing

- **Step 1 baseline** (2026-09-30, `.playwright-mcp/31e/`): 2026 week 4,
  game 49 PIT @ CLE (DraftKings, CLE +2.5, total 38.5, model `nfl-elo-v1`).
  Lines opened by `/#/nfl?season=2026&week=4&gameId=49&lineId=<id>` in a
  fresh page each (a hash change keeps the page mounted and its selection):
  - `38919` Jerry Jeudy receiving yards 13.5, OVER +25.6, Over 68%, six
    alternates (goblin 4.5, 9.5; demon 19.5, 29.5, 39.5, 83.5)
  - `38760` Aaron Rodgers passing yards 212.5, UNDER -20.1, eight alternates
    with no P(over)
  - `39038` Blake Whiteheart anytime TD (demon 0.5), 11.0%, snap share 30%
  - the board's default selection, Kirk Cousins passing yards 217.5, -39.7

  Panel text per line in `baseline.json`; screenshots at 1440, 1280 and 390
  on both pages.
- **Step 1 ships unit tests** (`nflPropDetail.test.ts`) for the detail model:
  pure logic with real branches (null game, null edge and line, segment,
  baseline reason, TD-only rows, alternates, null odds and model).
- `nflPropCards.test.ts`, `nflSignal.test.ts`, `nflGameModel.test.ts` and
  `nflPropBoard.test.ts` must pass unchanged.
- Steps 2-6 are layout and styling, checked with the build, screenshots at
  1440px and 390px on both pages, the impeccable detector, and the step 1
  baseline.
- Run `npm run build` and `npm run test` after every step.
- The panel makes no new request; nothing here spends The Odds API credits.

## Notes for the AI

- **Restyle only.** If a section needs a number `NflSlateLine` or
  `NflSlateGame` does not carry, stop and ask rather than deriving one.
- **The panel is shared.** Every change must hold on both `/nfl` and
  `/nfl/board`; check both after each step.
- **Keep the P(over) rule (27g).** Muted, never colored, sorted by, or
  compared to a payout break-even; keep today's tooltip text.
- **The game market is context, not a pick.** Keep the "not a pick" wording
  and no color, as the slate's model strip does.
- Tint token colors with `withAlpha()` (`utils/color.ts`); no new hex outside
  `:root`. The edge keeps `--nfl-green` / `--nfl-red`.
- 11px is for uppercase labels and chips only; sentence text is 12px or more.
  Today's 8-10px panel labels were a 31d detector finding; raise them.
- Split the panel's long JSX lines into section components under about 50
  lines each; they take props only, no data fetching.
- `prototypes/` is discarded at this feature's `/complete` (item 32 is
  complete, so 31e is the last user).
- Browser checks: if the Playwright MCP browser is locked, use the API venv's
  Python Playwright, as in 31c, 31d and 32c.

## Completion notes

- **Evidence:** `npm run test` (366 tests, 30 files; 19 in
  `nflPropDetail.test.ts`) and `npm run build` pass. Screenshots, the step 1
  baseline and the step 6 captures are in `.playwright-mcp/31e/`.
- **Decisions made while building** (recorded in the steps above): practice
  stays inside the injury text; the selected line's own P(over) fills its
  table cell; the card's badge rule is shared as `teamBadge`; the "not a
  pick" caveat is shared as `NFL_GAME_MODEL_CAVEAT`; the panel width is
  `clamp(360px, 28vw, 440px)`.
- **Only new text:** the game market card (user decision) and the Baseline
  reason line from `BASELINE_REASON_LABELS`.
- **Covered by unit tests only** (no live week-4 case): "No game market" and a
  priced sportsbook block.
- **Not changed here:** the slate's signal rows and game strip still carry
  detector `undersized-ui-text`, `text-overflow` and `tiny-text` findings.
- `prototypes/` was deleted at this `/complete`; item 31 is the last item
  that used it (item 32 completed 2026-09-30).

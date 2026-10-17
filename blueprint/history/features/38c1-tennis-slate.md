# Feature: Tennis slate on the shared shape

**From build-plan:** feature 38c1 (38c split 2026-10-17 into 38c1 tennis, 38c2 NBA)
**Branch:** `feature/38c1-tennis-slate`
**Status:** complete (2026-10-17)

> **Built as specified, with three small additions found in the browser:** the digest
> strip gets a bottom margin on tennis (it touched the table); rows carry
> `scroll-margin-top` so a digest pick's row clears the sticky top bar; and the
> intelligence and serve columns use `align-content: start` so stretching them to full
> height does not spread their content. A missing start time now reads "Time TBA" (the
> old card's `?? 'Time TBA'` never fired, since `fmtStartCT` returns `''`).
>
> **Owner review before merge:** the tennis summary cards became the shared `StatChip`
> strip (`page-head__stats`) that the NFL and NBA slates use, so every slate head
> matches; Locks and Strong+ keep their green. The filters moved from their own "Best
> bets" toolbar band into the page head's controls, as NFL's season and week selects
> sit, so the page reads head, chips, digest, table; on phones they sit two a row.
> The open row's detail was redrawn as a compact ledger: a slim context line (round,
> start, tags, both players with odds and win probability, the match link) replaces the
> big name header, the "Best opportunity" box folded into a Picks list it duplicated
> (top pick first), and Picks, Match and Serve and return sit as three hairline columns
> (picks full width over two columns at 1100px and below, one column on phones). The
> best-pick cell's ellipsis moved to an inner span, since `overflow: hidden` on a
> collapsed-border cell broke the row's border.
> **Owner-only diagnostics:** the quality flags (the Flags column and the detail's flag
> tags), the props health warning and the prop source switch now show only in the
> owner's view, `useAdminView()` in `web/src/hooks/useAdmin.ts` (signed in with the
> admin key, or a dev build), the rule that already hides the Admin nav. Visitors get
> PrizePicks props only, and DraftKings and Bet365 props are fetched only while chosen.
> The match page's flags are not changed here (38f or a later `/fix`).
>
> **Left for the owner (raised at the end of 38c1):** Model and Market percentages are
> no longer in the digest box (the spec omitted them; they stay in the row and its
> detail); ELO, ML and Odds columns still appear only at 1680px and up; the detail is
> one column from 769px to 1100px; the 38a top bar's links run together.

## Goal

Put the tennis slate on the shape 38b set for NFL: a plays digest at the top,
then one table where each match is a row. Tennis differs in two ways:

- **The digest holds priced picks.** These are the same best bets the pick cards
  show today, with their EV green under the existing rule. They are labeled as
  picks, not reference.
- **Rows expand inline.** Today a sticky side panel sits beside the table.
  Instead, clicking a row opens that match's detail under the row: best
  opportunity, model breakdown, serve and return, decision board and a link to
  the match page. The table gets the full page width back, and on phones the
  detail opens where you tapped instead of below the whole table.

**Display only.** No probability, EV, tier, sort, filter or pick changes, and
no API or schema change. Every number shown already reaches the page today.

## Design reference

- Chosen sketch: `.impeccable/mocks/decision/command.html` (digest strip, then
  the table).
- Direction contract: `.impeccable/surfaces/web-src-pages-nflintelligencepage-tsx.md`.
  Its "Unresolved" note (tennis digest is priced picks, green; NFL and NBA are
  gray gaps; same strip) is resolved here: same strip, different label and
  signal rule.
- The shipped NFL strip, `web/src/components/nfl/NflSlateDigest.tsx` and
  `nfl-slate-digest.css`, is the visual reference for the digest box.
- Tokens stay in `web/src/index.css`, with the 11px floor.

## In scope

- **A shared digest strip.** The 38b strip's markup and CSS move to
  `components/shared/` as `SlateDigest`, a label plus up to four boxes, so
  tennis and later NBA (38c2) use the same strip. NFL switches to it with
  identical output.
- **The tennis digest.** It replaces `TennisPickCards`.
  - **Which picks:** `featuredPicks(matches, 4)`, unchanged. That is the first
    priced best bet of each match, in the page's current sort order.
  - **Label:** "Best picks · priced".
  - **Box contents:**
    - the pick, in bold
    - `label · P1 vs P2`
    - tournament and start time (CT)
    - the odds on the left and the EV on the right, green (`--positive`, as
      `.tennis-pick-card__ev` is today)
    - the tier tag (`.tennis-tier`) and the tour tag
  - **Empty:** with no priced pick, nothing renders (the same as
    `TennisPickCards` today).
  - **Click or Enter on a box** expands that match's row, scrolls the row into
    view, and moves focus to the row's toggle. If the table's tour tab hides
    that match, the tab switches to All first.
- **Rows that expand inline.** The `TennisSlateTable` columns do not change:
  Time, Match, ELO, ML, Market, Model, Best pick, EV, Odds, Flags.
  - **Toggle:** the Match cell holds a `<button aria-expanded>` with the players'
    names. It is the keyboard path, labeled "P1 vs P2, show match detail".
    Clicking anywhere else on the row toggles too, except inside the expansion
    or on a link.
  - **One open at a time.** Opening a row closes the one before. Nothing is open
    on first load (the side panel used to default to the first match with a
    pick; now the digest is the starting point).
  - **The expansion** is a `<tr>` under the row with one cell spanning all
    columns. It holds the side panel's content, moved without changing it:
    - **Matchup line:** tournament, round and start; both players linked to
      their player pages; odds and win probability; surface, tour and
      quality-flag tags.
    - **Open match analysis →**, linking to `/tennis/match/:id`.
    - **Best opportunity.**
    - **Match intelligence:** H2H, surface ELO, model breakdown, and serve and
      return over the last 52 weeks.
    - **Decision board:** best bets, angles and props.
    - **Layout:** three columns on desktop (opportunity and decision board,
      intelligence, serve and return), stacked at 1100px and below.
  - **Prop-only rows** (no prediction) expand to the best opportunity and the
    decision board, with no match link, as the panel does today.
  - **Player stats load on expand.** They are fetched only when a row opens
    (`usePlayerStats`, unchanged), so a collapsed table makes no extra requests.
  - **Row state:** the open row is raised to `--bg-raised` (today's
    `.is-selected` look), and hover raises any row to `--bg-card-hover`.
- **Phone (768px and below).**
  - The digest scrolls sideways (the shared strip already does this).
  - Rows stay two lines, as today: time and players, then best pick and EV.
  - The expansion stacks to one column across the full row width, and the page
    never scrolls sideways.
- **Removed:**
  - `TennisCommandCenter` (the side-by-side layout and the sticky workspace).
  - `TennisPickCards` and the `.tennis-pick-card*` CSS.
  - The `.tennis-command-layout` and `.tennis-command-workspace` rules.
  - **Dead code found while speccing:** `UnifiedMatchCard.tsx`, which nothing
    imports, and its `.unified-match-*` rules in `index.css`. This step deletes
    them, so your approval of the spec approves that deletion. Strike it here if
    you want to keep them.

## Out of scope

- The NBA slate (38c2).
- Props as rows on the prop board (38d) and the command field (38e). 38e
  filters `SlateRow`s, so this spec leaves that shape unchanged.
- **Toolbar and filters:** the toolbar (upcoming only, tour, date, sort,
  source, leans), the summary stats, the notices and the empty state keep their
  behavior.
- **Previous and next day** in the page head (38f decides).
- **Panel EV color.** The panel colors every EV in the decision board green,
  angles and props included (`.tennis-panel-ev`), while the table colors only
  a priced best bet. That inconsistency predates this item. It moves into the
  expansion unchanged, because fixing it is a color change. Raise it as a
  `/fix` if wanted.
- Any API, schema, ranking, EV, tier or color change.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Shared digest strip** - move the 38b strip's shell into
  `web/src/components/shared/SlateDigest.tsx` with
  `components/shared/slate-digest.css`, renaming `.nfl-slate-digest*` to
  `.slate-digest*`. The shell takes `label`, `labelId` and its boxes as
  children. Box styles become a `.slate-digest__play` class that either a
  `Link` or a `button` can carry. `NflSlateDigest` renders through it.
  *Done when:*
  - `/nfl` at 1440px and 390px matches the pre-change digest: same four boxes,
    same text and sizes, same sideways scroll on phones. Compare screenshots
    before and after.
  - `nfl-slate-digest.css` is deleted and
    `rg "nfl-slate-digest" web/src` finds nothing.
  - `npm run build` passes.
- [x] **Step 2 - Tennis digest view model** - in `web/src/utils/tennisSlate.ts`,
  add `TennisDigestItem` and `tennisDigest(featured: FeaturedPick[])`. Each item
  carries display strings only: `matchKey`, `pick`, `what`, `when`, `odds`,
  `ev`, `tier`, `tourLabel` and `tone`. Also add
  `revealTab(rows, key, tab): TourTab`, which returns `tab` when the row with
  `key` is visible under it and `'all'` otherwise.
  *Done when:* new Vitest cases pass for:
  - an item built from a priced pick, using the same strings the pick card shows
    today (`fmtEv`, `fmtAmerican`, `fmtStartCT`, `fmtTournament`)
  - a WTA 125 pick, which keeps the WTA tone and its label
  - a pick with no start time, which reads "Time TBA"
  - an empty list
  - `revealTab` keeping the tab when the row is visible, falling back to All
    when it is hidden (a WTA 125 row under the Challenger tab, for example), and
    keeping the tab for an unknown key
  - The existing `featuredPicks` tests stay green. `npm run test` passes.
- [x] **Step 3 - Digest replaces the pick cards** - `TennisSlateDigest` uses
  the shared strip with button boxes and renders above the table. On the page,
  `selectedMatchKey` becomes `expandedKey`. The tour tab moves up from
  `TennisSlateTable` into the page so the digest can reveal a row. For this
  step the side panel still shows the selected match.
  *Done when:*
  - `/` at 1440px shows up to four boxes in the same order and with the same
    content as today's pick cards, EV green and tier tags unchanged.
  - Clicking a box selects that match in the side panel. With the WTA tab
    active, clicking an ATP pick switches the tab to All.
  - A date with no priced pick renders no strip.
  - No console errors.
- [x] **Step 4 - Extract the match detail** - move `MatchupHeader`,
  `FeaturedOpportunity`, `InlineAnalysis`, the decision board rows and
  `usePlayerStats` from `TennisCommandCenter.tsx` into
  `components/tennis/TennisMatchDetail.tsx`. Its CSS moves too:
  `tennis-command-center.css` is renamed with `git mv` to
  `tennis-match-detail.css`, keeping the `.tennis-panel-*` class names.
  `SelectedMatchWorkspace` renders `TennisMatchDetail`. This is a pure move.
  *Done when:*
  - The side panel looks and behaves exactly as before at 1440px (compare
    screenshots).
  - `TennisCommandCenter.tsx` holds only the layout and the selection logic.
  - `npm run build` passes.
- [x] **Step 5 - Rows expand inline; panel removed** - `TennisSlateTable`
  takes `expandedKey` and `onToggle`, adds the toggle button in the Match cell
  and renders the expansion row with `TennisMatchDetail` in its three-column
  layout. The page renders `TennisSlateTable` directly. `TennisCommandCenter` is
  deleted along with the `.tennis-command-layout` and
  `.tennis-command-workspace` rules.
  *Done when:*
  - At 1440px the table spans the full width with no side panel.
  - Clicking a row opens its detail beneath it with every panel section listed
    above. Clicking it again closes it, and opening another row closes the
    first.
  - Tab to a row's toggle and press Enter: it opens and `aria-expanded` reads
    true.
  - Clicking a player link or "Open match analysis" inside the detail navigates
    without toggling the row.
  - A prop-only row opens without a match link.
  - A digest box opens its row and scrolls it into view.
  - Network shows player-stats requests only after a row opens.
  - No console errors.
- [x] **Step 6 - Phone layout** - at 768px and below the expansion stacks and
  fits the row. Between 769px and 1100px it is a single column too.
  *Done when:*
  - At 390px wide there is no horizontal page scroll with a row open.
  - Rows are two lines as today, and the detail reads top to bottom: matchup,
    opportunity, intelligence, serve and return, decision board.
  - The digest scrolls sideways.
  - At 1000px the detail is one column with no overflow.
- [x] **Step 7 - Remove the dead paths** - delete `TennisPickCards.tsx`, the
  `.tennis-pick-card*` and stale pick-card phone rules in `tennis-slate.css`,
  `UnifiedMatchCard.tsx`, and the `.unified-match-*` rules in `index.css`.
  *Done when:*
  - `rg "TennisPickCards|TennisCommandCenter|UnifiedMatchCard|tennis-pick-card|unified-match-|tennis-command-" web/src`
    finds nothing.
  - `/` still renders as in step 6.
  - The NFL slate's digest is unchanged.
  - Verify passes.

## Files / areas

- **New:**
  - `web/src/components/shared/SlateDigest.tsx` and `slate-digest.css` (step 1)
  - `web/src/components/tennis/TennisSlateDigest.tsx` (step 3)
  - `web/src/components/tennis/TennisMatchDetail.tsx` (step 4)
- **Changed:**
  - `web/src/components/nfl/NflSlateDigest.tsx` (step 1)
  - `web/src/utils/tennisSlate.ts` and `tennisSlate.test.ts` (step 2)
  - `web/src/components/tennis/TennisSlateTable.tsx` (steps 3, 5)
  - `web/src/pages/TennisIntelligencePage.tsx` (steps 3, 5)
  - `web/src/components/tennis/tennis-slate.css` (steps 5 to 7)
  - `web/src/index.css` (step 7)
- **Renamed:** `tennis-command-center.css` to `tennis-match-detail.css` (step 4).
- **Deleted:**
  - `web/src/components/nfl/nfl-slate-digest.css` (step 1)
  - `TennisCommandCenter.tsx` (step 5)
  - `TennisPickCards.tsx` and `UnifiedMatchCard.tsx` (step 7)
- **Not touched:** the API, `unifiedTennis.ts` (composition, sort and pick
  rules), `TennisSlateSummary`, `qualityFlags`.

## Data / contracts

- No API or schema change. Inputs are `/tennis/predictions/today`,
  `/tennis/predictions/best-picks`, the props sources and per-player stats, as
  today.
- **`SlateDigest` (load-bearing for 38c2).** It is the one strip shell for
  every sport: `label`, `labelId`, and boxes carrying `.slate-digest__play`.
  The signal rule belongs to each sport's box, never to the shell.
- **`TennisDigestItem`** is display strings only. Its order is
  `featuredPicks`'s, which follows the page's sort. Changing that order is a
  ranking change, not a display one.
- **`SlateRow` stays the tennis row model**, keyed by match `key`. 38e's
  command field filters it, the same way it filters NFL's `NflSlateRowModel`.
- **`expandedKey`** is page state, not in the URL. One open row at a time.

## Testing

- The test gate is on. Step 2 ships the logic tests (`tennisDigest`,
  `revealTab`). Steps 1 and 3 to 6 are components and CSS, checked in the
  browser at 1440px, 1000px and 390px with screenshots, plus the build.
- Step 7 removes no tests: the removed components had none. The suite must
  still pass.
- **Final gate:** `npm --prefix web run verify && cd api && python -m pytest`.
- **Browser checks** need the local API (see memory: the Windows selector-loop
  launcher) or the hosted API through `VITE_API_BASE_URL`.
- **Empty digest:** tennis has picks most days. For the empty-strip check, pick
  a date with no priced pick, or filter to a tour with none.

## Notes for the AI

- **Green is a signal.** In the digest, only the EV of a priced best bet is
  green, and every `featuredPicks` entry is one. Do not color odds, model or
  market numbers. The NFL boxes stay gray through the shared shell.
- **Keep the stat labels.** `acesPerGame` and `dfPerGame` are per serve point
  and `breakPct` is break points converted (open question 30). The labels "Ace
  rate", "DF rate" and "BP converted" move unchanged with `InlineAnalysis`.
- **One row model.** Do not add a parallel row model. The expansion reads
  `row.match` through the existing `unifiedMatchToPrediction`, `bestBetPicks`
  and `anglePicks`.
- **Click handling.** Ignore clicks that start inside the expansion `<tr>` or on
  an `a` or `button` other than the toggle, and ignore modified clicks, so links
  open normally and nothing toggles twice.
- **Valid table markup.** Drop `tabIndex`, `aria-selected` and the row-level
  key handler from the `<tr>`. The toggle button is now the keyboard path.
- **Tab title.** The page head stays "Tennis slate" through `PageHead`, and
  `documentTitle` is unchanged.
- **No em dashes** in new copy or comments. The existing dash placeholders in
  moved tennis code (`fmtEv`, `measureValue`) stay as they are, since this is a
  move, not a copy rewrite.
- **Interview guide:** a restyle with no claim change, so skip it unless a step
  changes how the tennis slate can be described.

# Feature: NFL game-first slate

**From build-plan:** feature 33b (parent: 33. NFL redesign and detail pages)
**Status:** complete (2026-09-30)
**Branch:** `feature/nfl-game-first-slate`

## Goal

Turn `/nfl` from a one-game signal board into a week at a glance: a summary
strip, then one card per game grouped by kickoff window. Each card shows the
market, the muted model, conditions, injury counts, line movement, and the
game's top three props, and links to the 33a game page, which now holds
everything the old slate showed per game. NFL prop edges also turn gray on the
slate and prop board, because 27a graded the model at 48.1% against a 57.7%
break-even (open question 28).

**Display only.** Nothing here changes a projection, edge, rank or pick.

## Design reference

- [prototypes/nfl-slate.html](../../prototypes/nfl-slate.html) is the target layout.
- [prototypes/theme.css](../../prototypes/theme.css) holds the tokens. They
  already match `web/src/index.css` `:root` (ported in 31a), so **there is no
  token port step**. Build against the existing variables (`--chart-low`,
  `--chart-mid`, `--caution`, `--negative` and the others are all there).

**Where the build departs from the mockup:**
- **Stadium name.** It is not stored. Card meta shows the venue type and
  conditions (`conditionsLabel`), as the game page does.
- **"4 of 8 games shown".** Every game in a window is shown, so the count reads
  "8 games".
- **"Graded in the model record".** The record page is 33d. A final card's
  footer says "Final" and links to the game page.
- **"Prop lines post Thursday" empty note.** No schedule is inferred. A game
  with no lines reads "No prop lines stored for this game yet".
- **The Model tab** in the view switch stays off until 33d.

## In scope

- **API: final scores on game notes.** `NflGameNotesSchema` gains nullable
  `away_score` and `home_score`, read by `get_week_game_rest`. Item 29 requires
  display-only game context to extend `/nfl/game-notes`, not `/nfl/slate`.
- **Summary strip:**
  - games in the week
  - prop lines (the count of primary rows after grouping alternates, the same
    count the board uses)
  - finals, as `n / games`
  - players whose report status (`injuryStatus`) is Out or Doubtful, from game
    notes; practice-only entries never count
  - odds updated (the latest `currentFetchedAt` across game notes' line
    movement, in CT)

  A stat whose source has not loaded reads `--`.
- **Legend.** One line each: the market is the named book, de-vigged; the model
  is `nfl-elo-v1`, context only; the edge is gray until the ranking check (27j)
  adopts a slice.
- **Kickoff windows.** Games are grouped by their Central-time weekday and
  kickoff time, for example "Sunday · 12:00 PM CT". Sunday and Monday games
  kicking off at 6:00 PM CT or later merge into one "Prime time" window
  ("SNF and MNF"). A game with no kickoff time goes in a final "Kickoff time
  not set" window. Windows are ordered by their earliest kickoff, and games
  within a window by kickoff, then away team.
- **Game card, before kickoff:**
  - **Meta row:** conditions on the left. On the right, injury count tags
    (`n Out` in `--negative`, `n D` and `n Q` in `--caution`) and a short-week
    tag per team.
  - **Teams:** away @ home, with each team's record and rest days.
  - **Win bar:** the market's de-vigged home win probability as a gray bar,
    labelled on both sides. It is omitted without both moneylines.
  - **Market row:** spread, total and moneyline in the primary color. Under
    spread and total, "opened X" from game notes' line movement, "no move", or
    nothing when one line is stored. The moneyline cell shows the favorite's
    price, with the other side under it.
  - **Model row:** the model's spread, total and win probability, muted, with
    "Not a pick". "Model unavailable" when there is no model.
  - **Top three props:** player, market, line and edge share, all gray.
  - **Footer:** "n rateable props · m not rateable" and "Open game →".
- **Game card, kicked off but not final:** a "Live" marker replaces the
  kickoff, and the top props read as of kickoff under "Lines closed at kickoff".
  There are no live scores.
- **Game card, final:** the score (the loser's score muted); the closing spread
  and total, with covered, pushed or failed and over or under by n; the prop
  line count; no model row or top props. The whole card is muted like the
  mockup's `is-final`.
- **Top three props rule:**
  - take the game's full-game rateable lines from the week-wide board, read as
    of `min(now, kickoff - 1 ms)` as on the game page
  - order them by the board's own tiers (available before doubtful before out,
    confident sample first, stale last), then by edge share magnitude, each
    line scored against its own category's reference line
  - keep three, one per player
  - the edge share uses the same `edgeShare` formatting as the prop cards
  - with lines but none rateable, the block reads "No rateable props"; with no
    lines, "No prop lines stored for this game yet"
- **Whole card is a link** to `/nfl/game/:gameId` (keyboard-focusable, visible
  focus ring).
- **Removed from the slate:** the game selector strip, matchup bar, model strip,
  notes panel, filter bar, both signal boards, and the inline evidence panel.
  All of them now live on the game page.
- **Deep links.** `?season=&week=` still seeds the week. A legacy
  `?gameId=` redirects to `/nfl/game/:gameId`. `lineId` is ignored.
- **Gray edges on the slate and prop board.** `.nfl-slate` (the root class of
  the slate, the prop board and the game page) sets `--nfl-green` and
  `--nfl-red` to `var(--text-primary)`. The game page's own override goes, as
  it is now redundant. The alternates table's "Standard" odds-type tag drops
  antd `green` for `default`, so no green is left on NFL prop surfaces. The
  prop card and detail CSS comments that describe side coloring are updated.
- **Cleanup (deletions need your OK at this review):**
  - delete `web/src/components/NflGameNotesPanel.tsx`, used only by the old
    slate and superseded by `NflGameSidebar`
  - delete `web/src/utils/nflSlateSort.ts` and its test, used only by the old
    slate
  - remove the `nfl-slate.css` rules only the removed sections used
    (`nfl-game-strip`, `nfl-matchup-bar`, `nfl-team`, `nfl-scoreline`,
    `nfl-market-stat`, `nfl-model-strip`, `nfl-model-cell`, `nfl-filter-bar`,
    `nfl-filter-chips`, `nfl-signal-*`, `nfl-no-signals`, `nfl-notes*`), after a
    grep confirms nothing else uses each one
  - keep the `.nfl-slate` root variables and `.nfl-empty`, which the prop board
    and game page use
- **States:**
  - Loading and error use the shared states.
  - A week with no games reads "No games loaded for this season and week".
  - Game notes loading or failing never blocks the cards. The fields that come
    from notes (movement, injuries, rest, scores, summary stats) show `--` or
    are omitted.
  - A game with no book odds says "No market odds stored".
- **Layout and text.** An `auto-fill` grid of cards at least 400 px wide, one
  column at 390 px, with no horizontal scroll. No text below 11px, including
  tags and labels.

## Out of scope

- **Player links** on the top props (33c).
- **The model record page** and the Model view tab (33d).
- **Live scores or in-play odds.**
- **Any schema change, and any change to `build_slate`, `/nfl/slate`, or the
  prop board's ranking.** 27a and 27i replay `build_slate`.
- **The game page itself,** apart from removing its now-redundant gray
  override.
- **A kickoff-window filter or collapsing windows.** The mockup has neither.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Final scores on game notes** - add `away_score` and
  `home_score` to `get_week_game_rest`, `game_notes`, and
  `NflGameNotesSchema`, and the matching nullable fields to `NflGameNotes` in
  `web/src/types/nfl.ts`. *Done when:*
  - `test_nfl_game_notes_service.py` covers a completed game carrying both
    scores and a scheduled game carrying nulls
  - `curl /nfl/game-notes?season=2026&week=3` shows the scores
  - `pytest` passes
- [x] **Step 2 - Kickoff windows and summary utils** - add
  `web/src/utils/nflSlate.ts` with two pure functions:
  - `kickoffWindows(games)`, which applies the window rule above
  - `nflSlateSummary(games, notes)`, which returns the five strip values, each
    nullable

  *Done when:* `nflSlate.test.ts` covers:
  - a Thursday, Sunday early, Sunday late, SNF and MNF week, including a
    Monday doubleheader and a Sunday morning London game
  - a null kickoff, and ordering within a window
  - a summary with notes missing (nulls) and with notes present

  and `npm run test` passes.
- [x] **Step 3 - Top props and per-game boards** - in `utils/nflPropBoard.ts`,
  extract the tier part of `compareBoardLines` (availability, confident sample,
  staleness) into an exported `compareBoardTiers`. `compareBoardLines` then
  calls it, with no behavior change. In `utils/nflSlate.ts`, add:
  - `slateBoards(games, now)`, which builds the week board once per distinct
    as-of instant (all upcoming games share one build) and returns each
    game's categories
  - `topGameProps(categories, gameId, limit = 3)`, which applies the top-three
    rule

  *Done when:*
  - the existing `compareBoardLines` tests pass unchanged
  - new tests cover the top-three order across two markets (an out player
    sinks below a clear one, one row per player, partial and alternate lines
    excluded)
  - a started game reads its props as of kickoff
  - an all-upcoming week triggers exactly one board build
  - `npm run test` passes
- [x] **Step 4 - Card view model** - add `nflSlateCard(game, notes, props, now)`
  to `utils/nflSlate.ts`, returning `NflSlateCardModel`. It sets:
  - **state:** final when `status === 'completed'`; live once kickoff has
    passed; upcoming otherwise
  - meta, injury counts and the short-week tags
  - teams with record and rest, the win bar, and the market cells with their
    "opened" text
  - the model cells, the prop counts, and the final result lines

  *Done when:* tests cover:
  - the covered, push and failed spreads and the over, under and push totals
    of a final game, with the home spread in book sign
  - a final game whose notes carry no scores, which shows "Final" and no
    results
  - injury counts from `injuryStatus` only, so practice-only entries do not
    count
  - the moneyline favorite: the lower price, home on a pick'em
  - a game with no odds and no model, and one with notes missing

  `npm run test` passes.
- [x] **Step 5 - `NflSlateGameCard` component** - add
  `web/src/components/nfl/NflSlateGameCard.tsx` and
  `web/src/components/nfl/nfl-slate-card.css`. It renders the Step 4 model in
  all three states as a `Link` card. *Done when:* `npm run build` passes. The
  card is not mounted yet; Step 6 shows it.
- [x] **Step 6 - Rebuild the slate page** - rewrite `NflIntelligencePage.tsx`
  as: head (eyebrow "NFL · 2026 Week n", title, subtitle, view switch, season
  and week selects), the summary strip, the legend, then the window sections of
  card grids, with every state above. Add the legacy `?gameId=` redirect. *Done
  when:*
  - the week-4 slate renders at 1440 and 390 px against the mockup
  - a week-3 slate shows final cards with scores and closing results
  - clicking a card opens the right game page
  - `/nfl?gameId=<id>` lands on that game page
  - `npm run build` passes
- [x] **Step 7 - Gray edges and cleanup** - move the gray variables to the
  `.nfl-slate` root, drop the game page's override, and set the "Standard" tag
  to `default`. Update the two CSS comments. Delete `NflGameNotesPanel.tsx`,
  `nflSlateSort.ts` and `nflSlateSort.test.ts`, and remove the dead
  `nfl-slate.css` rules. *Done when:*
  - `/nfl/board` edges, picks and the evidence panel render gray, and the game
    page is unchanged
  - a grep finds no remaining reference to any removed file or class
  - no computed text on `/nfl`, `/nfl/board` or `/nfl/game/:id` is below 11px
    (browser check)
  - `npm run build`, `npm run test` and `pytest` pass

## Files / areas

**API**
- `api/app/repositories/nfl.py` - `get_week_game_rest` gains scores
- `api/app/services/nfl/game_notes.py`, `api/app/schemas/nfl.py`
- `api/tests/test_nfl_game_notes_service.py`

**Web**
- `web/src/types/nfl.ts` - scores on `NflGameNotes`
- `web/src/utils/nflSlate.ts` and `nflSlate.test.ts` - new
- `web/src/components/nfl/NflSlateGameCard.tsx` and `nfl-slate-card.css` - new
- `web/src/pages/NflIntelligencePage.tsx` - rewritten
- `web/src/pages/nfl-slate.css` - gray variables, dead rules removed
- `web/src/pages/nfl-game.css` - override removed
- `web/src/utils/nflLabels.ts` - `ODDS_TYPE_COLORS.standard`
- `web/src/utils/nflPropBoard.ts` - `compareBoardTiers` extracted, no rank change
- `web/src/components/nfl/nfl-prop-card.css` and `nfl-prop-detail.css` -
  comments only
- **Deleted:** `web/src/components/NflGameNotesPanel.tsx`,
  `web/src/utils/nflSlateSort.ts` and `nflSlateSort.test.ts`

## Data / contracts

```python
class NflGameNotesSchema(_CamelModel):
    ...                        # unchanged fields
    away_score: int | None     # null until the game is final in nfl_games
    home_score: int | None
```

```ts
/** One card's view model; pure, built from the slate game, its notes and the week board. */
interface NflSlateCardModel {
  gameId: number
  state: 'upcoming' | 'live' | 'final'
  kickoff: string                          // kickoffLabel
  conditions: string                       // conditionsLabel
  injuries: { out: number, doubtful: number, questionable: number } | null  // null without notes
  shortWeek: string[]                      // team codes on a short week
  away: NflSlateCardTeam                   // { code, record, rest: string | null, score: number | null }
  home: NflSlateCardTeam
  winBar: { awayPct: number, homePct: number } | null
  market: { spread: string, spreadOpened: string | null, total: string, totalOpened: string | null,
            moneyline: string, moneylineOther: string } | null
  model: { spread: string, total: string, winProbability: string } | null
  topProps: { lineId: number, playerName: string, market: string, line: string, edge: string }[]
  rateableCount: number
  otherCount: number
  final: { spread: string, spreadResult: string, total: string, totalResult: string } | null
}
```

- **Not load-bearing beyond this page.** 33c may add a player link to
  `topProps`, keyed by the line's `playerId`.
- **Closing lines for a final card** come from game notes' `lineMovement`
  `currentLine`, which is the last pre-kickoff line from one book. It is not
  NFLverse's `spread_line`, and not item 28's entry line. The card names no
  book. The game page's chart does.
- **Spread sign.** `homeSpread` and a spread `currentLine` are both the home
  line in book sign. Home covers when `homeScore - awayScore + line > 0`.
- **No schema change.**

## Testing

Test gate on: `pytest` and `npm run test`.

**Logic tests:**
- the scores on `game_notes` (Step 1)
- `kickoffWindows` and `nflSlateSummary` (Step 2)
- `compareBoardTiers`, `slateBoards` and `topGameProps` (Step 3); the existing
  `nflPropBoard.test.ts` guards the board's ranking against the extraction
- `nflSlateCard` (Step 4)

**Browser evidence:**
- screenshots of `/nfl` at 1440 and 390 px for an upcoming week and a finished
  week
- `/nfl/board` with gray edges
- the `?gameId=` redirect
- a computed-font-size sweep for text under 11px on the three NFL pages

**Final gate:** `npm run build` plus both test suites.

## Notes for the AI

- **Launching the API on Windows.** Plain `uvicorn` fails here; set the selector
  event loop first (see memory).
- **Layering.** SQL stays in `app/repositories/nfl.py`; the service only maps
  the new fields.
- **Reuse, don't fork:** `buildNflPropBoard`, `gameBoardAsOf`, `edgeShare`,
  `isConfidentSample`, `gameMarket`, `nflGameModelSummary`, `spreadLabel`,
  `conditionsLabel`, `kickoffLabel`, `recordLabel`, `restLabel` and
  `devigP1`. The top-three tiering must match `compareBoardLines`, so it
  calls `compareBoardTiers` rather than copying the tiers. That extraction is
  the only change to the board's code, and it must not change a rank.
- **Performance.** Never build the week board once per card; use `slateBoards`
  and memoize it on the slate data.
- **Colors and sizes.** Theme variables only, with no hex in component CSS, and
  nothing below 11px. Nothing on the slate is green. The win bar is
  `--chart-low` and `--chart-mid`.
- **No em dashes** in new comments or docs.
- **Prototypes.** `prototypes/` stays until the last item-33 sub-feature that
  uses it (33d uses `nfl-model.html`, 33c uses `nfl-player.html`).

## Outcome

- **Shipped as specced.** `/nfl` is a summary strip, a legend, and one card per
  game grouped by kickoff window, each linking to `/nfl/game/:gameId`. The
  signal boards, matchup bar, model strip, notes panel and inline evidence panel
  left the slate. NFL edges and picks are gray on the slate, prop board and game
  page through the shared `.nfl-slate` root.
- **API:** `/nfl/game-notes` carries `awayScore` and `homeScore` (null until
  final). `/nfl/slate` and `build_slate` are unchanged.
- **Board ranking unchanged.** `compareBoardTiers` was extracted from
  `compareBoardLines`; the existing board tests pass unmodified.
- **Beyond the spec:**
  - `market` and `final` on `NflSlateCardModel` are lists of label, value and
    detail cells rather than named fields, so one component renders both rows.
  - The shared `stat-chip__label` is 10px app-wide; the slate raises it to 11px
    in scope, and lays the five chips out three to a row below 600 px.
  - The mockup's 55% fade on final cards was dropped, since it pushed 11px
    muted text below readable contrast.
- **Deleted:** `NflGameNotesPanel.tsx`, `nflSlateSort.ts` and its test, and
  the old slate rules in `nfl-slate.css` (69 lines to 24).
- **Known limits:**
  - Final cards show each team's record entering the week, not after the game.
  - The game page's back link opens the current week, not the week it came from
    (33a behavior).
  - `SEGMENT_COLORS` in `nflLabels.ts` still holds `green` but is not imported
    anywhere.
  - Week-4 injury reports were not yet ingested, so "Out or doubtful" read 0.
- **Checks.** `pytest` 1,928 passed; `npm run test` 412 passed; `npm run build`
  passed. Headless Chromium (the API venv's Playwright, as the MCP browser was
  locked): `/nfl` weeks 3 and 4 at 1440 and 390 px with no horizontal scroll
  and no text under 11px; a card click lands on its game page; `?gameId=52`
  redirects to `/nfl/game/52`; no computed green on the slate, prop board, game
  page or its evidence drawer except the nav logo; week-3 spread and total
  results checked by hand against the scores.

# 54b. NFL onto the shell

**Status:** complete (2026-11-03)
**Branch:** `feature/nfl-player-shell` (off master `1fe45188`, which has 54a)
**Parent:** 54 Shared player-page shell (54a done; 54c tennis follows)

## Goal

Put the NFL player page on the shared shell and give it the same top-to-bottom order as NBA
and NHL: **Props first, supporting context below.**

Today the NFL page opens with the usage-by-week card and the "This week's lines" card, then a
"This week's props" heading with the game and usage context card, and only then the market tab
strip and the selected market's evidence. NBA and NHL open straight on the market tabs. Moving
the NFL tabs to the top is the visible change; everything else is a move, not a rewrite.

Display only. No change to projections, ranks, edges, versions, gray signal colors, data,
hooks or endpoints.

## Target order

| # | Section | Today | After |
|---|---|---|---|
| 1 | Crumb, head (title, season chips), availability line | same | same, through the shell |
| 2 | Props: title, market tab strip, selected market's evidence | 4th | **first** |
| 3 | Supporting context: usage by week, this week's lines, game and usage context | first | **below the tabs** |
| 4 | Game log, record splits, footer | same | same |

## Scope

**In**
- `PlayerPageShell` gains two optional inputs so NFL can use it: `stats` (the season chips
  `PageHead` already supports) and `sportClass` becomes optional (NFL adds no class of its own).
- `NflPlayerPage` renders through `PlayerPageShell`, `PlayerNotFound` and `PlayerMarketTabs`.
- The Props block uses the shared strip. Heading `Props for week N`, the note is the market
  count ("6 markets"); with no slate lines it keeps today's "Recent results only, no model
  comparison" note.
- The game and usage context card moves out of `NflPlayerProps` into a supporting section under
  one title, `Supporting context`, with the usage card and the lines card.
- The deep-link scroll effect is removed: it existed because the usage card above the tabs grew
  as it loaded, and nothing above the tabs grows any more.

**Out**
- Removing or redesigning the "This week's lines" card. It repeats what the tab strip lists, but
  deleting it is a product call for you, not part of this move. It keeps its click-to-switch.
- Tennis (54c), CSS renames, the NFL evidence sections' content or wording, the game log,
  record splits and footer.
- The player-week link fix (already shipped) stays as is: `?season=&week=` still decide the slate.

## Contracts (load-bearing for 54c)

```ts
// PlayerPageShell: the two changes
sportClass?: string        // was required
stats?: ReactNode          // new, passed to PageHead
```

- `PlayerMarketTabs` is unchanged. NFL passes `heading`, `note` only for the no-slate case,
  `tabs` from `playerTabs`, `hrefFor` built with `playerSearch`, and the evidence as children.
- Section ids stay `prop-<market>`; `scrollToPropTabs` and `#prop-tabs` stay, since the lines card
  jumps to the strip.
- Query params are untouched: `?market=`, `?form=`, `?season=`, `?week=`.

## Build steps

- [x] **Step 1 - NFL on the shell, same order.** Add the optional `sportClass` and `stats` to
  `PlayerPageShell`; move the NFL page's container, loading, error and not-found states, crumb,
  head and availability line onto the shell and `PlayerNotFound`. No section moves yet.
  *Done when:* verify passes and a before and after capture of an NFL player (container classes,
  crumb, head, availability, section order, document title) is identical.
- [x] **Step 2 - Split the props block.** Split `NflPlayerProps` into the tabs-and-evidence part
  (on `PlayerMarketTabs`) and a context part holding the game and usage context card. Remove
  the settling-scroll effect and its imports. The page still renders the old order.
  *Done when:* verify passes, no unused imports, and the page output is unchanged apart from the
  `Props for week N` heading text and its market-count note.
- [x] **Step 3 - Reorder.** Render Props directly after the availability line, then a
  `Supporting context` section (usage and lines grid, then the game and usage context card),
  then the game log, record splits and footer.
  *Done when:* verify passes and a live NFL page shows the order in the table above.
- [x] **Step 4 - Prove it.** On local dev against real data: a model player (QB), a receiver, a
  kicker (no usage card), a player with only line-only markets, a player with no lines and an
  unknown id. Check deep links (`?market=`, `?form=`, `?season=&week=`), the lines card jumping to
  the tabs, narrow width, and the console.
  *Done when:* each case renders the target order, the tab strip is the first block after the
  availability line, no new console errors, and the lines card still switches the market.

## Files and areas

- Changed: `NflPlayerPage.tsx`, `NflPlayerProps.tsx`, `PlayerPageShell.tsx`
- New: a small `NflPlayerContext.tsx` holding the game and usage context card
- Likely touched: `nfl-player.css` only if the heading spacing needs it
- Untouched: every API file, `NflPlayerLines`, `NflPlayerUsage`, game log, record, footer, the NBA
  and NHL pages

## Testing

- No new pure logic is expected, so no new unit test. If the `Props for week N` heading is pulled
  into a helper, it gets a test beside `playerPage.test.ts`.
- Gate: `npm --prefix web run verify`. No API change, so `pytest` is not part of this item.
- Step 4 is the real check: the page is layout and data wiring, which the project verifies by
  running the app.

## Notes for the AI

- Behavior must not change except the order and the heading. A deep link must still open its
  market, and the lines card must still switch it.
- `useNflGameContext`, `evidenceContextGameId` and `useRef` are used only by the scroll effect in
  `NflPlayerProps`; remove those imports with it, but leave `NflUsageContext` alone.
- Keep `components/shared/` free of sport imports.
- Update the 54b plan line and archive at `/complete`; the parent 54 stays open until 54c.
- No em dashes in code, comments or commit messages. Comment only what the code cannot say.

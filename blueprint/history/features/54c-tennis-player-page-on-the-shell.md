# 54c. Tennis onto the shell

**Status:** complete (2026-11-03)
**Branch:** `feature/tennis-player-shell` (off master `7c844765`, which has 54a and 54b)
**Parent:** 54 Shared player-page shell (54a NBA/NHL and 54b NFL done; this is the last piece)

## Goal

Put the tennis player page on the same frame as NFL, NBA and NHL: the shared shell, and the
shared market tab strip. The tennis page is already props first, so this is mostly the frame
and the strip, plus a "Supporting context" title above the Elo, serve and return, match log
and sidebar cards.

Display only. No change to projections, ranks, edges, versions, gray signal colors, data,
hooks or endpoints.

## What is different about tennis

| | NFL, NBA, NHL (shared) | Tennis today |
|---|---|---|
| Frame | `PlayerPageShell` | its own `page-shell tennis-player` container and `PlayerHeader` wrapping `PageHead` |
| Head | title, status line, injury or availability | title, tour tag and rank, hand, country, age; a "Next match" block in the actions slot |
| Tabs | `PlayerMarketTabs`: links to `?market=`, `aria-current` | `tennis-prop-pills`: buttons with `aria-pressed` that set `?market=` |
| Heading | "Props on <date>" or "Props for week N" | "Today's props" |
| Under the strip | the market's evidence | a match picker (when the player has more than one match today), a form-window picker, then each line's evidence |
| Below | game log, record, footer | Elo card, serve and return, match log, sidebar |

Tennis has no single slate date (its "today" is a Central-time day that spans two UTC dates),
so the heading keeps its tennis wording, **Today's props**. Each sport already words its own
heading; what is shared is the frame around it.

## Scope

**In**
- `PlayerPageShell` gains an optional `actions` slot (the "Next match" block), passed to `PageHead`.
- `PlayerHeader` stops rendering `PageHead` itself and returns the title, status line and actions
  for the shell; the tour tag and the next-match link are unchanged.
- `TennisPlayerPage` renders through the shell, with its own not-found copy and its own crumb.
- The market buttons become the shared strip (`PlayerMarketTabs`), as links that keep every other
  query param. The match picker, the form-window picker and each line's evidence stay as they are,
  as the strip's children.
- A `Supporting context` title above the Elo card, serve and return, match log and sidebar.
- The shared components import the CSS they depend on (`nfl-slate.css`, `nfl-player.css`), so a
  page that is not an NFL page does not rely on another page having loaded it.

**Out**
- The content of the Elo card, serve and return, match log and sidebar.
- The tennis match page, the prop board, and the prop evidence body.
- NFL, NBA and NHL pages.
- Removing the `tennis-prop-pills` CSS: the prop board filters use it too.
- Renaming CSS classes.

## Contracts

```ts
// PlayerPageShell: one more optional input
actions?: ReactNode        // passed to PageHead, e.g. the Next match block
```

```ts
// web/src/utils/tennisPlayerProps.ts: pure, tested
tennisTabSearch(params: URLSearchParams, market: string, firstMarket: string): string
// the first tab is the default, so it removes ?market=; other tabs set it; all other params are kept
```

- Behavior that must hold: choosing a tab keeps `?match=`, `?form=` and `?prop=`, as it does today.
- Tabs become links, so `aria-pressed` becomes `aria-current` and a modified click opens a new tab.
  That is the one intended behavior change, and it matches the other three sports.

## Build steps

- [x] **Step 1 - Tennis on the shell.** Add `actions` to `PlayerPageShell`, add the CSS imports
  to the shared components, make `PlayerHeader` return head props, and render `TennisPlayerPage`
  and its loading, error and not-found states through the shell, keeping the tennis crumb and
  not-found copy.
  *Done when:* verify passes, and a before and after capture of a tennis player (head text, the
  Next match block, section order, document title) is identical apart from the two added shell
  classes on the container.
- [x] **Step 2 - Shared market strip.** Add `tennisTabSearch` with tests, and render the market
  strip through `PlayerMarketTabs`. The match picker, form-window picker and the evidence become
  its children. The loading and could-not-load states keep their message under the same heading.
  *Done when:* verify passes, the tests cover the first tab, another tab and param preservation,
  and clicking a tab changes `?market=` while keeping `?match=` and `?form=`.
- [x] **Step 3 - Supporting context title.** Add the `Supporting context` title above the Elo
  card, serve and return, match log and sidebar.
  *Done when:* verify passes and the live page shows Props, then Supporting context, in that order.
- [x] **Step 4 - Prove it.** On local dev against real data: a player with props today, one with
  none, one with more than one match, an unknown id. Check `?market=`, `?match=`, `?form=` and
  `?prop=` deep links, the Next match link, narrow width and the console.
  *Done when:* each case renders the shell order, no new console errors, and the strip's links
  keep the other params.

## Files and areas

- Changed: `TennisPlayerPage.tsx`, `PlayerHeader.tsx`, `PlayerPropTabs.tsx`, `PlayerPageShell.tsx`,
  `PlayerMarketTabs.tsx`, `tennisPlayerProps.ts` and its test
- Untouched: every API file, the Elo card, serve and return, match log, sidebar, the NFL, NBA and
  NHL pages

## Testing

- `tennisTabSearch` is pure logic and gets unit tests beside `tennisPlayerProps.test.ts`.
- The page itself is layout and wiring, so it rides on the build and the Step 4 live checks.
- Gate: `npm --prefix web run verify`. No API change, so `pytest` is not part of this item.

## Notes for the AI

- Display only: do not touch projections, ranks, edges, versions or gray colors.
- Keep `components/shared/` free of tennis imports.
- The `?prop=` scroll effect in `PlayerPropTabs` stays; it scrolls a deep-linked line into view.
- When the player has no tabs the strip renders nothing, as today.
- Update the 54c plan line and archive at `/complete`, and tick parent 54 then, since 54a and
  54b are done.
- No em dashes in code, comments or commit messages. Comment only what the code cannot say.

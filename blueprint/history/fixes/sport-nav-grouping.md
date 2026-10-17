# Group tennis and NFL navigation by sport

**Type:** Fix

## The problem

The top nav lists each sport's slate and prop board as separate entries:
`Tennis`, `Tennis Props`, `NFL`, `Prop Board`, `Live Odds`, `My Bets`, `Admin`
(`NAV_ITEMS` in `web/src/App.tsx`). Four entries for two sports read like four
sports, `Prop Board` does not say which sport it belongs to, and the mobile
drawer is longer than it needs to be.

The item 31 mockups group each sport's two views instead: one sport page title
with a `Slate | Props` segmented switch in the header
(`prototypes/tennis-slate.html`, `prototypes/tennis-props.html`). In the
mockups the switch links between two pages; it does not merge them.

## The fix

Keep the four routes and pages exactly as they are. Change only how you move
between them:

- **Nav:** one `Tennis` entry (`/`) and one `NFL` entry (`/nfl`), so the nav
  becomes `Tennis`, `NFL`, `Live Odds`, `My Bets`, `Admin`. The sport entry
  stays highlighted on both of its routes:

  | Path | Nav entry | Switch |
  |---|---|---|
  | `/` | Tennis | Slate |
  | `/tennis/board` | Tennis | Props |
  | `/nfl` | NFL | Slate |
  | `/nfl/board` | NFL | Props |

- **Switch:** a small shared `SportViewSwitch` component
  (`web/src/components/shared/SportViewSwitch.tsx`) that takes a sport,
  renders `Slate | Props` as two router links, and marks the active one from
  the current path. It goes in the header of all four pages, beside the
  existing controls (the NFL pages keep their Season and Week selects).
- **Active state is neutral, not green.** The mockup's `.seg button.on` uses
  `--positive`, but green is a signal color (UI/UX rules). The active segment
  uses `--text-primary` on a raised surface; inactive uses
  `--text-secondary`. Styles go in `web/src/index.css` as theme variables.
- **Mapping is a pure helper** (`web/src/utils/sportNav.ts`): path to nav key,
  and path to active view, with a unit test.

**Must not break:**
- Direct links and bookmarks to all four routes, the back button, and the
  `/props` and `/nfl/prospects` redirects.
- Each page's own queries and filters. Nothing is shared or refetched by the
  switch beyond what navigating to the route already does.
- Unknown paths keep today's fallback (Tennis highlighted).
- No change to any number, color, sort, or rank on the pages.

## Build steps

- [x] **Step 1 - sport nav mapping.** Add `web/src/utils/sportNav.ts`
  (`navKeyForPath`, `sportViewForPath`) and `sportNav.test.ts`. Collapse
  `NAV_ITEMS` to five entries and select the nav key through the helper, on
  desktop and in the mobile drawer.
  **Done when:** the nav shows five entries; `Tennis` is highlighted on `/` and
  `/tennis/board`, `NFL` on `/nfl` and `/nfl/board`; `npm run test` passes with
  the new test.

- [x] **Step 2 - Slate | Props switch.** Add `SportViewSwitch` and its styles,
  and place it in the headers of `TennisIntelligencePage`,
  `TennisPropBoardPage` (via `TennisPropBoardControls` if the header lives
  there), `NflIntelligencePage`, and `NflPropBoardPage`.
  **Done when:** on each of the four pages the switch shows the right active
  view, clicking the other segment navigates to its route, the back button
  returns, and the switch fits beside the NFL selects at desktop and phone
  width.

## Verify

- `cd web && npm run build` and `npm run test` pass.
- In the running app:
  1. Open `/`: the nav shows `Tennis` selected and the switch shows `Slate`.
  2. Click `Props`: the URL becomes `#/tennis/board`, the nav still shows
     `Tennis`, and the switch shows `Props`. Press back and you return to `/`.
  3. Repeat on `/nfl` and `/nfl/board`, and check the Season and Week selects
     still work.
  4. At phone width, open the drawer: five entries, and the correct one is
     highlighted on each of the four routes.
  5. Load `#/nfl/board` directly: it opens on the props view with `NFL`
     highlighted.

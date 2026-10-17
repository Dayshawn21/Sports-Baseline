# Feature: Lineform shell

**From build-plan:** feature 38a
**Branch:** `feature/38a-lineform-shell`
**Status:** complete (2026-10-17)

## Goal

Give every page one shell: a top bar that carries the sport tabs and the
active sport's Slate / Props / Model views, one shared page head, and a tab
title per route, and finish the SportApp-to-Lineform rename. After 38a a
visitor learns the navigation once and it works the same on every sport; the
later 38 sub-features only change what sits inside the page.

## Design reference

- Chosen structure sketch: `.impeccable/mocks/decision/command.html` (open in
  a browser; the top bar and page head are the parts 38a builds).
- Direction contract: `.impeccable/surfaces/web-src-pages-nflintelligencepage-tsx.md`
  (FIRST VIEWPORT block: bar layout, page head, phone behavior).
- Product context: `PRODUCT.md`. Theme tokens stay in `web/src/index.css`.

## In scope

- **Rename (already built).** The uncommitted rename in the working tree:
  wordmark, `index.html` title, API title, package name, How it works eyebrow,
  README, `AGENTS.md`, `CLAUDE.md`, `api/.env.example`, a type comment and the
  local interview guide. It passed Verify on 2026-10-16 (530 web tests, 2,597
  API tests, typecheck and build) but was never checked in a browser.
- **Top bar (desktop).** Wordmark; sport tabs (Tennis, NFL, NBA); the active
  sport's views as tabs (Slate, Props, Model, only those the `SPORTS` registry
  lists); How it works; Admin under the existing `visibleNavItems` rule. On a
  sport's detail page (game, match, player) the sport tab is active and no view
  tab is.
- **Top bar (phone, 768px or narrower, `useIsMobile`'s breakpoint).** Wordmark, the active sport's name and a
  menu button; the active sport's views as a second row of tabs; the drawer
  lists each sport with its views nested, then How it works and Admin.
- **Per-route tab titles.** `<Page> · Lineform` on every route, for example
  `NFL slate · Lineform`, `Tennis props · Lineform`, `NBA model · Lineform`,
  `How it works · Lineform`, `Admin · Lineform`; detail pages use a generic
  name in 38a (`NFL game · Lineform`, `Tennis match · Lineform`) and 38f makes
  them specific; any other route (the hidden `/parlays`, an unknown path)
  reads `Lineform`.
- **Shared page head.** One `PageHead` component (eyebrow, title, optional
  subtitle, optional period navigation, optional actions, optional stats
  strip) used by the three slates, two prop boards, three model pages and How
  it works. Titles share one casing (the existing uppercase display style)
  and one naming pattern, so two titles change wording:

  | Page | Eyebrow | Title today | Title in 38a |
  |---|---|---|---|
  | Tennis slate | Tennis · Daily intelligence | Best Opportunities | Tennis slate |
  | NFL slate | NFL · 2026 Week 6 | NFL Slate | NFL slate |
  | NBA slate | NBA · Tue, Oct 20, 2026 | NBA Slate | NBA slate |
  | Tennis props | Tennis · Prop board | Best picks by category | Tennis props |
  | NFL props | NFL · Prop board | Best picks by category | NFL props |
  | Tennis model | Tennis · Model | Model track record | Track record |
  | NFL model | NFL · Model · 2026 | Track Record | Track record |
  | NBA model | NBA · Model · 2026 | Track Record | Track record |
  | How it works | Lineform · How it works | How it works | How it works |

  Step 6 (added 2026-10-17, after review) then replaces the eyebrow and the
  subtitle with one status line beside the title, as the chosen sketch does.
- **The per-page view switch goes away.** `SportViewSwitch` is deleted once
  the bar carries the views.
- **How it works** moves to the `is-wide` container like every other page,
  with its prose capped at a readable measure (from the parked polish spec).

## Out of scope

- The command field (38e); the bar leaves no placeholder for it.
- Slate, prop and table layouts (38b to 38d); each page's body is unchanged.
- Game, match, player and admin page heads, the game-page `h1`, `CT` labels
  and the remaining polish defects (38f).
- Render service names, their URLs, the repo name and the admin key's storage
  name (`sportapp.adminKey`): renaming them signs the owner out or breaks
  `CORS_ORIGINS` / `VITE_API_BASE_URL` for no visible gain.
- Any change to a probability, edge, rank, sort, pick or signal color.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Rename review and shell model** - create the branch with the
  working-tree rename on it, show its diff for review, and finish any visible
  leftover; add pure helpers in `web/src/utils/sportNav.ts`:
  `shellNav(pathname, adminVisible)` (sport tabs with an active flag, the
  active sport's view tabs with an active flag, the extra links) and
  `documentTitle(pathname)` (the route's tab title). *Done when:* no rendered
  text reads "SportApp" (grep of `web/src` and `README.md`, excluding service
  URLs and the storage key); `sportNav.test.ts` covers both helpers for every
  sport route, a detail page, How it works, Admin hidden and shown, and an
  unknown path; `npm run test` passes.
- [x] **Step 2 - Desktop top bar and tab titles** - `App.tsx` renders the bar
  from `shellNav` (sport tabs, view tabs, How it works, Admin) and sets
  `document.title` from `documentTitle` on every route change;
  `SportViewSwitch` is removed from all eight pages that use it and deleted.
  *Done when:* at 1440px, every sport page shows its sport and view selected
  in the bar and no in-page switch; NBA shows Slate and Model only; a game
  page highlights its sport with no view selected; How it works and Admin
  show no view tabs; each route's tab title matches the list above; the
  wordmark reads Lineform. Until steps 4 and 5, each page head keeps its old
  layout with the switch's slot empty; that is expected, not a defect.
- [x] **Step 3 - Phone top bar** - at 768px and narrower the bar shows the wordmark, the
  active sport and the menu button, the views row sits beneath it, and the
  drawer groups views under each sport. *Done when:* at 390px no page scrolls
  sideways, the views row switches views, the drawer opens a sport's view and
  closes, and Admin stays hidden from visitors.
- [x] **Step 4 - `PageHead` on the slates** - add
  `web/src/components/shared/PageHead.tsx` and use it on the tennis, NFL and
  NBA slates, keeping each slate's controls (week and season selects, NBA
  previous and next, tennis filters) and stats strip. *Done when:* the three
  slate heads share one layout and title casing at 1440px and 390px, every
  existing control still works, and the NFL season and week selects read in
  full at 390px.
- [x] **Step 5 - `PageHead` on boards, model pages and How it works** - the two
  prop boards, the three model pages and How it works use `PageHead`; How it
  works moves to `is-wide` with prose capped near 75 characters. *Done when:*
  all nine pages share the head at both widths, the boards' and model pages'
  stats strips render unchanged, How it works lines up with the bar's gutter,
  and `npm --prefix web run verify && cd api && python -m pytest` passes.

- [x] **Step 6 - Status line instead of eyebrow and subtitle** - added
  2026-10-17 after the owner reviewed the heads: the 11px eyebrow repeated
  the top bar and the subtitles were generic. `PageHead` drops `eyebrow` and
  `subtitle` for one `meta` status line beside the title (wrapping under it
  on phones), in readable gray, as `.impeccable/mocks/decision/command.html`
  does. It names the period only, since the stats strips already carry the
  counts:

  | Page | Status line |
  |---|---|
  | Tennis slate | Today and tomorrow, or the picked date |
  | NFL slate, NFL props | 2026 · Week 6 |
  | NBA slate | Tue, Oct 20, 2026 |
  | Tennis props | Next 24 hours |
  | NFL and NBA model | 2026 season · last graded Sat, Oct 17 9:33 AM CT |
  | Tennis model | Settled matches · last graded Sat, Oct 17 9:33 AM CT |
  | How it works | none |

  *Done when:* no page head shows an eyebrow or subtitle; each status line
  matches the table at 1440px and 390px with no text under 11px and no
  sideways scroll; Verify passes.

## Files / areas

- `web/src/App.tsx` - the bar, phone bar, drawer, tab titles.
- `web/src/utils/sportNav.ts` and `sportNav.test.ts` - `shellNav`,
  `documentTitle`.
- `web/src/components/shared/PageHead.tsx` (new), `SportViewSwitch.tsx`
  (deleted).
- `web/src/index.css` - bar, views row and page head styles (theme tokens only).
- Pages: `TennisIntelligencePage`, `NflIntelligencePage`, `NbaSlatePage`,
  `TennisModelPage`, `NflModelPage`, `NbaModelPage`, `HowItWorksPage` (+
  `how-it-works.css`); components `TennisPropBoardControls`,
  `NflPropBoardControls`.
- Rename, already modified in the working tree: `README.md`, `AGENTS.md`,
  `CLAUDE.md`, `api/.env.example`, `api/app/config.py`, `web/index.html`,
  `web/package.json`, `web/package-lock.json`, `web/src/App.tsx`,
  `web/src/pages/HowItWorksPage.tsx`, `web/src/types/tennis.ts`.
- Planning files from the 38 intake, also uncommitted: `PRODUCT.md`,
  `.impeccable/`, `blueprint/build-plan.md`, `blueprint/project-plan.md`,
  `blueprint/context/project-overview.md`, and the Web Design Guidelines skill
  under `.claude/skills/` and `.agents/skills/`.

## Data / contracts

- **`PageHead` props (load-bearing for 38b to 38f):** `title: string`,
  `meta?: ReactNode` (the status line beside the title; step 6 replaced
  `eyebrow` and `subtitle` with it),
  `period?: { label: string, previous?: string | null, next?: string | null }`
  (paths; null or missing renders that link disabled; `label` names the nav
  for screen readers),
  `actions?: ReactNode` (page controls such as selects), `stats?: ReactNode`.
  Later sub-features add pages to it rather than writing their own heads.
- **`shellNav` output (load-bearing for 38e):**
  `{ sports: { code, label, path, active }[], views: { view, label, path, active }[], links: { key, label, active }[] }`.
  38e's command field sits in the bar this model drives.
- **`SPORTS` registry** keeps its shape; `documentTitle` reads labels from it,
  so a new sport gets its tab titles from its registry entry.
- No API or schema change.

## Testing

- **Logic with tests (Vitest):** `shellNav` and `documentTitle` in
  `sportNav.test.ts`, extending the existing `navKeyForPath`,
  `sportViewForPath` and `visibleNavItems` cases; `navKeyForPath` stays green.
- **UI evidence:** captures at 1440px and 390px of every route touched (the
  capture script used for the 2026-10-16 polish pass, run against the local
  web pointed at the hosted API with `VITE_API_URL`), checked for: selected
  sport and view, no in-page view switch, no text under 11px, no page-level
  sideways scroll.
- **Gate:** `npm --prefix web run verify && cd api && python -m pytest`.
- **Evidence log:**
  - **Steps 1 to 3:** checked in earlier sessions (rename grep, `sportNav`
    tests, bar captures at 1440px and 390px); those captures lived in a
    session scratchpad only.
  - **Steps 4 and 5 (2026-10-17):** local web against the hosted API, at
    1440px and 390px, measured in the browser on all nine pages: the
    shared head renders with its title, the stats strip where the page has
    one, no text under 11px, no page-level sideways scroll; the NFL season
    and week selects (slate and board) read in full at 390px; tab titles
    match the list above; the only console error is a missing
    `favicon.ico`.
  - **Gutter (step 5, beyond the spec):** the bar padded 24px (desktop)
    and 12px (phone) while `is-wide` content starts at
    `clamp(20px, 3.2vw, 56px)`, so no page lined up with the bar. The bar
    now uses the same clamp on desktop and 20px on phones; measured 46px
    for both bar and head at 1440px, 20px at 390px.
  - **Step 6 (2026-10-17):** no head shows an eyebrow or subtitle; every
    status line matches its table at both widths, beside the title at
    1440px; no text under 11px, no sideways scroll. After owner review the
    head title is 34px (the sketch's size) and the status line 16px,
    scoped to `.lf-page-head`, so detail pages keep their titles until 38f.
  - **Cleanup:** `SportViewSwitch`, `NAV_ITEMS`, `navKeyForPath`, and the
    now unused `.unified-page-head`, `.unified-page-subtitle`,
    `.nfl-model__head` and board head rules are deleted.
    `.unified-eyebrow` stays for the NFL player page (38f).
  - **Verify at `/complete`:** `npm --prefix web run verify` (534 tests,
    typecheck, build) then `python -m pytest` in `api/` (2,597 passed).
  - **Interview guide:** already says Lineform and does not describe the
    navigation, so 38a changes no claim in it; not edited.

## Notes for the AI

- Display only: no edge, rank, sort, pick or color logic moves. The
  `.nfl-slate` gray-signal scope stays on the pages that have it.
- `visibleNavItems` keeps Admin hidden from visitors (37a); the drawer and the
  bar both go through it.
- `SPORTS` / `SPORT_PAGES` remain the one place a sport is declared (17d);
  the bar must not hardcode sports or views.
- Use theme variables from `index.css`; no new colors. Inline styles on Ant
  Design layout components are the house pattern.
- No em dashes, en dashes or ellipsis characters in new copy or comments.
- The parked polish spec's surviving fixes are split: tab titles and How it
  works here; the layout defects, `CT` labels, projection-input labels and
  game-page `h1` in 38f. Its before captures are in the session scratchpad
  only, so 38f retakes them.
- The interview guide (`docs/SportApp-Employer-Interview-Guide.md`,
  untracked, never staged) already records the rename; update it again at
  `/complete` only if the shell changes how the app is described.

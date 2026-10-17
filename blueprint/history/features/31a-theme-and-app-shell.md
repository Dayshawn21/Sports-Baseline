# Feature: Theme and app shell

**From build-plan:** feature 31a (parent: 31. Web redesign)
**Status:** complete (2026-09-28)
**Branch:** `feature/web-redesign-theme`

## Goal

Swap the whole web app from the old navy palette to the redesign's true-black,
one-green theme, and restyle the nav, without moving any layout. After this, every
page reads as the new design in color and type, and sub-features 31b to 31e only
have to change layout.

## Design reference

- `prototypes/theme.css` - the source of truth for every token (colors, fonts,
  radius, spacing). Port its `:root` block; the rest of that file is mockup
  scaffolding.
- `prototypes/tennis-slate.html` and `prototypes/nfl-prop-board.html` - the nav
  bar (black, translucent, sticky; wordmark "Sport**App**"; white active link,
  gray inactive) and the page width (content up to 1680px).
- The mockups are **not** the layout target for this sub-feature. Pages keep
  today's layout; only colors, the nav, and the container width change.

## In scope

- The new tokens in `web/src/index.css` `:root`, replacing the navy values.
- One shared Ant Design theme built from those tokens, applied once at the app
  root, replacing the four copy-pasted `DARK_ANTD_THEME` constants.
- The nav: desktop header, mobile header, and drawer.
- `.page-container` max width 1200px -> 1680px (the user asked for wider pages).
- Every hardcoded navy, signal, and accent color in `web/src` mapped to a token,
  per the color map below, including the page-scoped `--nfl-*` and `--tennis-*`
  palettes.

## Out of scope

- Any layout change: card grids, summary strips, prop cards, the detail view
  (31b to 31e).
- Adding or removing any displayed number, flag, or column.
- Changing which numbers are colored, sorted, or ranked. An element that is
  colored today may change hue per the color map, but never loses its color, and
  nothing uncolored today gains one. (Deciding whether the NFL
  prop edge should lose its green is overview open question 28, not this item.)
- The retired bankroll builder's page beyond its color sweep.
- Deleting `prototypes/` (31b to 31e still use it).

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Port the tokens** - replace the `:root` values in
  `web/src/index.css` with `prototypes/theme.css`'s, keeping every existing
  variable name and adding the new ones (`--bg-raised`, `--positive`,
  `--positive-soft`, `--negative`, `--negative-soft`, `--caution`,
  `--caution-soft`, `--goblin`, `--demon`, `--radius`, `--radius-sm`,
  `--space-1` to `--space-6`). Keep the existing Google Fonts import; do not
  copy theme.css's. *Done when:* `npm run build` passes, and the Tennis page
  background is `#000` (checked in the browser's computed style).
- [x] **Step 2 - One Ant Design theme** - add `web/src/theme/antdTheme.ts`
  exporting `APP_ANTD_THEME` (dark algorithm; `colorBgBase` `#000`,
  `colorBgContainer` `#0d0d0f`, `colorBgElevated` `#1a1a1e`, `colorPrimary`
  `#f5f5f7`, `colorText` `#f5f5f7`, `colorBorder` `rgba(255,255,255,0.1)`, font
  families from the tokens). Wrap `App` once in `ConfigProvider` with it, and
  delete the four page-level `DARK_ANTD_THEME` constants and their
  `ConfigProvider` wrappers (Admin, Bets, Parlays, Tennis). *Done when:*
  `grep -r DARK_ANTD_THEME web/src` returns nothing, the build passes, and a
  Select dropdown, DatePicker, and Modal on Bets open with black/near-black
  surfaces.
- [x] **Step 3 - Nav and page width** - restyle the desktop header (black at 85%
  opacity with blur, sticky, 56px, bottom border `--border-subtle`), the
  wordmark (`Sport` white + `App` green, Barlow Condensed 700 20px), the menu
  (gray links, white active, no blue underline), the mobile header, and the
  drawer (replace `#001529`). Do it through `APP_ANTD_THEME` component tokens
  (`Layout.headerBg`, `Menu.darkItemBg`, `Menu.darkItemSelectedBg`,
  `Menu.darkItemColor`, `Menu.darkItemSelectedColor`) where Ant Design exposes
  one, and inline styles only where it does not. Raise `.page-container` max
  width to 1680px.
  Nav items and routes stay exactly as they are. *Done when:* screenshots at
  1440px and 390px show the new nav on Tennis and NFL, the drawer opens black,
  every nav link still routes, and the build passes.
- [x] **Step 4 - Page-scoped palettes** - point the `--nfl-*` variables
  (`nfl-prop-board.css`, `nfl-slate.css`) and the `--tennis-*` variables
  (`tennis-prop-board.css`, `tennis-command-center.css`) at the global tokens
  (`--nfl-surface: var(--bg-card)`, `--nfl-green: var(--positive)`, and so on),
  and replace the remaining raw hex in those four CSS files and
  `tennis-prop-board-filters.css` per the color map.
  *Done when:* those files contain no hex from the navy family, and the NFL
  board, NFL slate, and Tennis Props screenshots show black surfaces with the
  same elements colored as before.
- [x] **Step 5 - Shared component rules in index.css** - map the raw hex in
  `index.css`'s component rules (`.unified-*`, `.props-audit*`, notices, tier
  pills) per the color map. *Done when:* `index.css` has raw hex only inside
  `:root`, and the Tennis page screenshot shows the same flags, tiers, and edges
  colored as before, in the new shades.
- [x] **Step 6 - Bets page** - map `BetsPage.tsx`'s raw hex (110) per the color
  map. Includes the inline `styles` overrides on its two modals and the
  date picker (lines ~170, ~314, ~718), which keep them navy despite the shared
  theme (found in step 2). *Done when:* no navy-family hex remains in the file,
  won/lost/pending states keep their meaning (won green, lost red, pending
  amber as `--caution`), the Add Bet modal and date picker render near-black, and the build
  passes.
- [x] **Step 7 - Live Odds page** - map `LiveOddsPage.tsx`'s raw hex (73) per
  the color map. *Done when:* no navy-family hex remains, plus odds stay green,
  and the build passes. (The page has no best-price marking, so the original
  "best price still marked" check does not apply; found in step 7.)
- [x] **Step 8 - Remaining components** - map the raw hex in `ParlaysPage.tsx`,
  `AdminPage.tsx`, `TennisIntelligencePage.tsx`,
  `components/tennis/PlayerComparisonModal.tsx`,
  `components/tennis/UnifiedMatchCard.tsx`, and `App.tsx`. *Done when:*
  `grep -rEi "#0(60c18|c1528|b1628|f1e38)|#10(1e36|2039)|#001529" web/src`
  returns nothing, and the build and tests pass.
- [x] **Step 9 - Visual pass** - screenshot every route at 1440px and 390px,
  fix any unreadable text or invisible border the sweep caused, and run the
  impeccable contrast check on the running app. *Done when:* every route has a
  screenshot with no navy surface left, no text under 4.5:1 contrast is
  reported, and `npm run build` and `npm run test` pass.

## Files / areas

- `web/src/index.css` - tokens (step 1), container width (step 3), component rules (step 5)
- `web/src/theme/antdTheme.ts` - new (step 2)
- `web/src/App.tsx` - root `ConfigProvider`, nav (steps 2, 3)
- `web/src/pages/AdminPage.tsx`, `BetsPage.tsx`, `ParlaysPage.tsx`, `TennisIntelligencePage.tsx` - drop page themes (step 2), color sweep (steps 6, 8)
- `web/src/pages/LiveOddsPage.tsx` (step 7)
- `web/src/pages/nfl-prop-board.css`, `nfl-slate.css`, `tennis-prop-board.css`, `tennis-prop-board-filters.css`, `components/tennis/tennis-command-center.css` (step 4)
- `web/src/components/tennis/PlayerComparisonModal.tsx`, `UnifiedMatchCard.tsx` (step 8)
- No API, schema, or backend change.

## Data / contracts

**Load-bearing: the token names.** 31b to 31e build against these names, so
they are fixed here. Existing names keep their meaning; new ones are:

| Token | Value | Use |
|---|---|---|
| `--bg-app` | `#000000` | page background |
| `--bg-card` | `#0d0d0f` | cards, tables |
| `--bg-card-hover` | `#141417` | hover |
| `--bg-raised` | `#1a1a1e` | pills, inputs, inactive meters |
| `--border-subtle` / `--border-card` | `rgba(255,255,255,.06)` / `.1` | dividers / card borders |
| `--text-primary` / `--text-secondary` / `--text-muted` | `#f5f5f7` / `#9a9aa3` / `#85858f` | text roles |
| `--positive` / `--positive-soft` | `#00c805` / 12% | a positive signal only |
| `--negative` / `--negative-soft` | `#ff5000` / 12% | negatives only |
| `--caution` / `--caution-soft` | `#e8b931` / 12% | warnings, flags, questionable |
| `--goblin` / `--demon` | `#7c9cff` / `#c77dff` | PrizePicks line types |
| `--atp-blue` / `--wta-pink` / `--challenger-teal` | unchanged | tour meaning |
| `--radius` / `--radius-sm`, `--space-1..6` | 14px / 8px, 4-40px | scale |

**The color map for the sweep** (steps 4 to 8):

| Old | New |
|---|---|
| navy backgrounds `#060c18` | `var(--bg-app)` |
| navy surfaces `#0c1528`, `#0b1628`, `#0f1e38`, `#101e36`, `#102039`, `#001529` | `--bg-card`, `--bg-card-hover`, or `--bg-raised` by role |
| old text `#dde5f8`, `#5e7394`, `#3a4d65`, `#94a3b8` | `--text-primary`, `--text-secondary`, `--text-muted` |
| signal greens `#22c55e`, `#4ade80`, `#4ee39a` | `--positive` (tints: `--positive-soft`) |
| negative reds `#ef4444`, `#f87171`, `#fb7185`, `#ff747c` | `--negative` (tints: `--negative-soft`) |
| ambers `#f59e0b`, `#fbbf24`, `#d7a443` | `--caution` (tints: `--caution-soft`) |
| blue meaning ATP | `--atp-blue`, unchanged |
| blue as a generic accent (active filter, focus, link, info notice) | neutral: `--text-primary` on `--bg-raised` |
| goblin green / demon pink tier tags | `--goblin` / `--demon` |
| confidence tier LOCK (green) | `--positive` text on `--positive-soft` |
| confidence tier STRONG (blue `#60a5fa`) | `--positive` text on `--positive-soft`, outlined, so it reads weaker than LOCK (as in `prototypes/tennis-props.html`) |
| trust label (Ready / Review), pale mint `#8be8bd` for every value | `--text-secondary`: it never carried a signal (decided in step 4); 31c and 31d may give Ready and Review their own states |
| parlay purple `#a78bfa` (Bets: parlay tag, borders, Add Parlay button, odds numbers) | neutral: gray chip, white odds, outlined button (decided in step 6) |
| OVER / UNDER direction (green / pink) | `--positive` / `--negative`, unchanged meaning; 31b and 31c decide whether direction keeps any color |

Green then means "positive signal": goblin tags and generic accents stop using
it. STRONG moves from blue to green because it is already a colored confidence
signal, and the approved mockups show it green; nothing uncolored becomes green.

## Testing

- **No new logic, so no new unit test.** This is a color and style change: CSS
  values, one theme constant, and a nav restyle. The test gate applies to logic;
  this rides on build, screenshot, and contrast evidence.
- Every step: `npm run build` (typechecks) and `npm run test` stay green.
- Steps 3 to 9: before/after screenshots of the touched routes at 1440px and
  390px. Compare which elements are colored; the set must not change.
- Step 9: impeccable contrast scan of every route on the running dev server.

## Notes for the AI

- **Restyle only.** Never change a number's value, visibility, sort, rank, or
  whether it is colored. If a color's meaning is unclear (for example a blue
  that might mean ATP or might be an accent), check the component before
  mapping it, and ask when still unsure.
- **Prefer tokens over hex** in every changed line (coding-standards: theme
  values live in `index.css`). Inline `style` objects stay the pattern; just
  point them at `var(--token)`.
- **`colorPrimary` is neutral (`#f5f5f7`), not green.** Ant Design paints
  primary buttons, focus rings, and selected states with it, and those are not
  signals.
- Dark mode is the only mode; do not add a light theme.
- Keep the steps' diffs color-only. If a sweep step turns up a layout bug,
  note it for 31b to 31e instead of fixing it here.
- Check the Windows API launch memory before starting the API for screenshots.

## Completion notes

- **Evidence:** `npm run build` and `npm run test` (207 tests, 19 files) passed
  after every step. Every route was screenshotted at 1440px and 390px with an
  automated scan for navy backgrounds (none left). The impeccable contrast scan
  reported one finding per route: the green wordmark "App" at 7.9:1 median,
  whose 1.6:1 minimum is anti-aliased edge pixels under the header's backdrop
  filter. Live Odds was checked against a mocked response, so no Odds-API.io
  quota was spent.
- **Found during the build:** 17 places built translucent colors by appending a
  hex alpha suffix (`${color}35`), which silently produces invalid CSS once the
  color is a `var()`. Fixed with `withAlpha()` in `web/src/utils/color.ts`
  (unit-tested). Any later code tinting a token must use it.
- **`.page-container` max width** moved 1200px -> 1680px but changes nothing
  visible today: every data page uses the full-width `is-wide` variant, and
  Admin, Bets and Live Odds set their own widths.
- **Follow-ups for 31b to 31e (not changed here, restyle only):**
  - side-tab accent stripes on the notices and props audit, and the tour stripe
    on the rounded tennis match card (impeccable `side-tab`,
    `border-accent-on-rounded`)
  - undersized 9-10px table text (644 hits on the NFL slate) and text overflow
  - the comparison modal's Grass surface color is still a signal-like green
  - the tennis match card's CHALLENGER tag renders ATP blue (unchanged behavior)

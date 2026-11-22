# Home page first paint (Lighthouse performance)

**Type:** Fix
**Branch:** `fix/home-first-paint`

## The problem

Lighthouse 13.6 on the live home page after #62 (2026-11-22): performance
**35 mobile / 66 desktop**, LCP **10.4 s / 3.7 s**, total blocking time
**2,060 ms / 220 ms**. Accessibility, best practices and SEO are all 100.

Three causes, from the run's network trace and a source-mapped build:

1. **The page waits on the API before painting anything real.**
   `HomePage` returns one `LoadingState` spinner while every sport is loading
   (`home.loading`), so the page head, the LCP element, appears only after
   the first slate answers (tennis, about 2.9 s into the run). The slowest
   slates, `/nba/slate` and `/nhl/slate`, take about 7.7 s each. The cards
   already have their own `loading` tone, so the page-wide spinner adds
   nothing.
2. **Fonts load through a chain.** `index.css` pulls Google Fonts with an
   `@import`, so the font CSS starts only after the app CSS arrives (about
   560 ms in). The JetBrains Mono and two Barlow Condensed files then start
   at about 3.4 s.
3. **The shell chunk carries code the first paint does not use.** The entry
   chunk is 151 KiB compressed (502 KB minified), and Lighthouse counts
   83 KiB of it as unused on home. Routes are already lazy (`App.tsx`,
   `routes/sportPages.tsx`). What remains is the shell: Ant Design, plus
   `rc-menu` (the phone `Menu` drawer), `rc-dialog` (the `Modal` in
   `ShortcutsPanel`), axios and the query client.

## The fix

1. Render the home page head and section headings at once. Cards, gaps and
   records show their own loading states while the slates arrive. Keep the
   all-failed `ErrorState`.
2. Load the fonts from `index.html` with `preconnect` and a stylesheet
   `<link>` instead of the CSS `@import`.
3. Load the phone menu drawer and the shortcuts panel only when they are
   first opened, so `rc-menu` and `rc-dialog` leave the entry chunk if
   nothing else in it needs them.

**Must not break:**

- The gaps table must not say "No gap lines yet." while every sport is still
  loading. Today `gapsBody('all', ...)` returns empty rows in that state,
  which the page-wide spinner hides.
- The phone menu and the `?` shortcuts panel must open on the first tap or
  keypress with no visible delay or layout jump.
- No change to the data, the queries or the API.

**Out of scope (follow-ups, not this fix):**

- The slow `/nba/slate`, `/nhl/slate` (about 7.7 s) and
  `/nhl/model/ranking` (about 14 s) responses on Render.
- The home page downloads the whole NFL week (`/nfl/slate`, 586 KiB
  compressed) to build its digest, and parsing it adds to blocking time. A
  smaller home summary needs API and snapshot work.

## Build steps

- [x] **1. Home paints its head at once.** In `pages/HomePage.tsx`, drop
  the `home.loading` early return and the `loading` field from `HomeView` in
  `hooks/useHomeData.ts`. In `utils/home.ts`, make `gapsBody` return
  `{ kind: 'loading' }` for the `all` tab while it has no rows and a sport
  feeding it is still loading (any sport for props; NFL or tennis for
  moneyline), so "none yet" never shows before the answers are in. Add cases to `utils/home.test.ts`.
  **Done when:** with the API slowed or stopped, the home page shows
  "Today", the date and time line, four loading cards and a loading gaps
  table; `npm run test` passes, including the new cases.
- [x] **2. Fonts load without the `@import` chain.** Move the Google Fonts
  URL from `index.css` to `index.html` as `preconnect` hints for
  `fonts.googleapis.com` and `fonts.gstatic.com` (crossorigin) plus a
  stylesheet `<link>`, same families and weights. **Done when:** a build
  shows no `@import` in the built CSS, the fonts request starts with the
  document's own requests, and the page renders in the same fonts.
- [x] **3. Shell drawers load on first open.** Lazy-load the phone menu
  drawer content and `ShortcutsPanel`, mounting each only after its first
  open. Record the entry chunk size before and after (`npx vite build` size
  report). If `rc-menu` or `rc-dialog` stay in the entry because something
  else in the shell imports them, stop and report instead of chasing it.
  **Done when:** the entry chunk is smaller, and the phone menu and `?`
  panel open on first use in the browser at 390 px and desktop.

## Verify

- `npm --prefix web run verify && cd api && python -m pytest`.
- Local production build (`web-preview`): the home page head shows before
  any slate answers; the menu, `?` panel and fonts still work.
- After merge and the Render deploy, rerun Lighthouse 13.6 on the live home
  page, mobile and desktop, run one at a time (parallel runs inflated blocking
  time last time). Compare with the 2026-11-22 baseline (35 / 66, LCP
  10.4 s / 3.7 s). Expected: LCP no longer tracks the slowest slate request,
  and the score moves up. Report the measured numbers whatever they are;
  no score target is promised, because the slow API responses stay.

## Result

Completed 2026-11-22 on `fix/home-first-paint`.

- Step 1: the home page paints its head, cards, gaps table and records at once,
  each in its own loading state. The All gaps tab stays loading while it has no
  rows and a sport feeding it has not answered (tighter than the "every sport"
  wording first drafted, which missed the partly answered case). Three new
  cases in `utils/home.test.ts`.
- Step 2: Google Fonts load from `index.html` with `preconnect` hints; the
  built CSS has no `@import`. All three families load and render as before.
- Step 3: the phone menu (`components/shared/PhoneMenu.tsx`) and
  `ShortcutsPanel` are lazy, mounted on first open and fetched when the
  browser is idle (`hooks/usePreloadWhenIdle.ts`). Entry chunk 502 KB to
  366 KB minified, 167 KiB to 123 KiB compressed. The Ask drawer stayed in
  the entry (about 7 K, and its `Drawer` is shared with the sport switcher).
- Checks: `npm --prefix web run verify` (1,874 tests, build) and
  `python -m pytest` in `api/` (6,592 passed). Browser: home loading layout
  with no API; `?` panel opens and closes on desktop; phone menu opens,
  highlights the current page and navigates at 375 px.
- Not yet measured: the live Lighthouse rerun, which needs the merge and the
  Render deploy.

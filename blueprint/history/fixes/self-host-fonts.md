# Fix: Self-host the web fonts

**Type:** Fix
**Branch:** `fix/self-host-fonts` (worktree `.claude/worktrees/sharp-elbakyan-f84efc`, cut from `master` at `060d8199`)
**Status:** completed 2026-11-23 (step 3, the post-deploy Lighthouse runs, recorded after the push)

## The problem

`web/index.html` links the Google Fonts stylesheet
(`fonts.googleapis.com/css2?family=Barlow+Condensed...&family=DM+Sans...&family=JetBrains+Mono...&display=swap`).
It is render-blocking and on another origin, so first paint waits for its DNS,
TLS and round trip before the app CSS and the empty `#root` can paint.
Lighthouse 13.6 (mobile, 2026-11-23, run 7) estimates **950 ms** of FCP savings
from it alone; the fonts it then pulls are 140 KB from `fonts.gstatic.com`. FCP
median is 2.66 s and LCP 4.64 s simulated (four runs, score median 63.5).

The three families are SIL Open Font License, which allows self-hosting.

## The fix

Serve the same faces from the app's own origin, so nothing renders differently:

- Fetch the Google CSS once as Chrome does (woff2), and download exactly the
  woff2 files it references (the same families, weights, italic and unicode
  ranges: Barlow Condensed 400/600/700/800 and italic 600, DM Sans variable
  `opsz` 9-40 / `wght` 300-600, JetBrains Mono 400/500) into
  `web/public/fonts/`, with each family's `OFL.txt`.
- `web/src/fonts.css`: those `@font-face` rules with `url(/fonts/...)` and
  `font-display: swap`, imported first by `index.css` (bundled, so no extra
  request).
- `index.html`: drop the Google stylesheet and both preconnects; add
  `<link rel="preload" as="font" type="font/woff2" crossorigin>` for the latin
  files of DM Sans and Barlow Condensed (the body and display faces first paint
  uses). JetBrains Mono loads on use.
- `render.yaml` / static headers: long cache for `/fonts/*` if the static site
  allows it (check the existing `headers` block; otherwise leave it).

**Must not change:** font families, weights or ranges in use, `--font-*`
tokens, any component CSS, what any page looks like.

## Build steps

- [x] **Step 1 - Fetch the fonts (separate yes in chat: downloads files).**
  Done 2026-11-23: 23 woff2 files (383,936 bytes, matching the sizes Google
  reported) named `<family>-<google file name>`, plus the three `OFL.txt`
  files from `google/fonts`, in `web/public/fonts/`.
  The Google CSS (Chrome user agent) and its woff2 files into
  `web/public/fonts/`, plus the three `OFL.txt` files from the font
  repositories; list names and sizes. *Done when:* every `url()` in the Google
  CSS has a local file, and the total matches about 140 KB plus latin-ext faces.
- [x] **Step 2 - Serve them.** Done 2026-11-23: `src/fonts.css` is Google's
  CSS with 35 `url()`s rewritten to `/fonts/` (all files present, all
  `font-display: swap`); `index.css` imports it; `index.html` drops the Google
  links and preloads DM Sans latin and Barlow Condensed 700 latin (the two faces
  the shell paints first, measured). Verify passed (1,887 web tests and build);
  app CSS 8.5 KB gzip. Local production preview: no Google request, only the
  latin files load (5 of 23), the preloads start at 18 ms (were 97 ms), no
  preload warnings; home and NFL screenshots match production at 1280x800 and
  load the same faces. No cache header: `render.yaml` edits do not reach Render
  (set `/fonts/*` caching in the dashboard if wanted). `fonts.css`, the `index.css` import,
  `index.html` preloads with the Google links removed, cache header if
  supported. *Done when:* Verify passes; a local production preview loads no
  `fonts.googleapis.com` or `fonts.gstatic.com` request, the home, NFL and
  tennis pages look the same as `master` (side-by-side screenshots), and
  computed `font-family` resolves to the self-hosted faces.
- [ ] **Step 3 - Measure after deploy (no code).** Open at `/complete`
  (2026-11-23): it needs the deploy, so the runs are recorded after the push. Four Lighthouse 13.6 mobile
  runs against the 01:54 medians (score 63.5, FCP 2.66 s, LCP 4.64 s). *Done
  when:* recorded here.

## Verify

- Verify: `npm --prefix web run verify && cd api && python -m pytest`.
- Local preview Network: fonts from `/fonts/`, none from Google; no FOIT.

## Out of scope

- Subsetting or dropping weights (would change rendering), variable-font
  conversions, lazy-loading the Ask drawer or command palette (the next fix),
  React render cost.

## Notes for the AI

- Step 1 downloads files from `fonts.googleapis.com` and `fonts.gstatic.com`:
  state the files and sizes and wait for a yes in chat.
- Keep `unicode-range` from the Google CSS so latin-ext faces load only when a
  page needs them.
- Run the Verify command from the repo root; `web/` has its own `node_modules`.

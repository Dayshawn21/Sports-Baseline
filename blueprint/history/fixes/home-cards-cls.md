# Fix: Stop the home page head and sport cards growing when the slates load

**Type:** Fix
**Branch:** `claude/home-cards-cls-4c8c9b` (worktree `.claude/worktrees/silly-noether-01b517`, cut from `master` at `409e63b8`)
**Status:** complete (2026-11-24)

## The problem

Lighthouse mobile reports CLS about 0.12 on `/`, above the 0.1 limit, and names
`div.home-cards` as the element that moves. Measured 2026-11-24 on a local
production build (`npm --prefix web run build`, `vite preview` on :4173, local
API, Playwright with a buffered `PerformanceObserver('layout-shift')` and a
per-frame log of element heights). Local runs score worse than production
because every slate lands within about 150 ms:

| Width | Run | CLS | Shifts |
|---|---|---|---|
| 412 (mobile) | 1 | 0.236 | 0.195 at 281 ms, 0.004 at 296, 0.037 at 394 |
| 412 (mobile) | 2 | 0.238 | 0.197 at 306 ms, 0.004 at 317, 0.037 at 412 |
| 412, 4x CPU | 1 | 0.255 | 0.023, 0.195, 0.037 |
| 1350 (desktop) | 1 | 0.246 | 0.079 at 270 ms, 0.062 at 323, 0.098 at 418, 0.007 at 937 |

Nothing arrives late from fonts, images or the route fallback (the home page
renders directly since `6e65ba59`). The page paints with loading cards, and two
things grow when the first slate query resolves:

1. **The status line under the title (the big mobile shift).**
   `todayStatus(now, null)` is `Tue Nov 24 · 12:00 PM CT` (24 characters), which
   fits beside "Today". When the first slate lands, `refreshedAt` is set and the
   line becomes `... · slates refreshed 12:00 PM` (52 characters). At 412 px it
   no longer fits beside the title, so it wraps onto its own row and onto two
   lines: `.lf-page-head__meta` moves from y 79 to 104 and grows from 21 to 42 px,
   pushing the "Slates" heading and `.home-cards` down 46 px (184 to 230). That
   is most of the 0.195 shift. At desktop width the longer line still fits, so
   it moves nothing there.
2. **Loading cards have no "Next" block.** `HomeSportCard` renders
   `.home-card__next` only when `card.next` is set, and a loading card has none.
   A ready card adds a 1 to 4 line block (border, padding, 18-20 px per line):
   - Mobile (one column): a loading card is 121 px, loaded cards are 157 (NHL,
     1 line), 175 (NBA and NFL, 2 lines) and 193 (tennis, 3 lines). Each card
     that grows pushes the cards below it; NFL landing last is the 0.037 shift.
   - Desktop (four columns, rows stretch): the row goes from 174 to 284 px when
     the first card lands, pushing the gaps panel and the records down 110 px
     (the 0.079 shift).

Out of scope, measured for the record: at desktop width the gaps panel's
loading line (`Loading`, 167 px panel) growing to its rows (669 then 1107 px)
pushes the model records, about 0.16 of the desktop 0.25. Mobile is unaffected,
because the gaps panel is below the fold there. That is a separate follow-up.

## The fix

1. **Reserve the refreshed time from first paint.** `todayStatus` returns its
   parts instead of one string: the date and clock, and the refreshed suffix,
   with a placeholder time (`12:00 PM`, the widest clock string) and a `pending`
   flag while `refreshedAt` is null. `HomePage` renders the suffix in a span
   that is `visibility: hidden` while pending, so the line wraps to its final
   shape on the first paint and the text only becomes visible later. Hidden
   text is not read by screen readers, so nothing announces a fake time.
2. **Reserve the "Next" block on loading cards.** `HomeSportCard` renders an
   empty, `aria-hidden` `.home-card__next` while `card.tone === 'loading'`, and
   `.home-card__next` gets a two-line `min-height` at both breakpoints
   (`calc(padding-top + border + 2lh)`). Two lines is the common loaded height
   (NBA and NFL); a 1-line block keeps its two-line box, a 3 or 4 line block
   still grows by one or two lines.

**Visible trade-off:** a card whose next block is one line (NHL today) gains
one blank line of card height on mobile (157 to 175 px). On desktop the row
already stretches to its tallest card, so nothing changes there.

**Must not change:** what any card or the status line says once loaded; the
first-render path in `web/src/main.tsx` (`isHomeRoute`, `preloadHomePage`,
`prefetchHome`) and its NBA/NHL board prefetch branch from `409e63b8`; query
keys; the gaps panel and records (out of scope); quiet and error cards, which
keep no next block.

## Build steps

- [x] **Step 1 - Status line reserves the refreshed time.** Done 2026-11-24:
  `home.test.ts` 34 passed. Preview at 412 px, 3 runs: the status line is 42 px
  and `.home-cards` sits at y 230 from the first painted frame (was 21 px and
  y 184, then 42 and 230); mobile CLS 0.119 / 0.119 / 0.123 (was 0.236 / 0.238),
  the rest being card growth. Desktop unchanged at 0.244. Specced: `todayStatus` in
  `web/src/utils/home.ts` returns `{ when, refreshed, pending }`; `HomePage`
  renders the parts, hiding the suffix while pending (one class in `home.css`).
  `home.test.ts` covers both cases, including the placeholder. *Done when:*
  `npm --prefix web run test` passes, and in the preview at 412 px the status
  line has its final height and the "Slates" heading its final top on the first
  frame the home page paints.
- [x] **Step 2 - Loading cards reserve the next block.** Done 2026-11-24: preview
  at 412 px, 3 runs: loading cards are 174 px and every card stays 174-175 px as
  it loads; CLS 0.0037 / 0.0033 / 0.0038, no shift above 0.004. The NHL card
  (one Next line) shows one blank line, as specced. Desktop 0.241-0.277: the card
  row now grows 240 to 264 px (three Next lines at four columns, about 0.07) and
  the gaps panel (out of scope) adds about 0.17. A fixed `line-height` on
  `.home-section-title` (the heading's Barlow 600 swaps in at the same moment)
  was tried in the browser and changed nothing, so it is not in the diff.
  Specced: `HomeSportCard.tsx`
  renders the empty block for loading cards; `home.css` adds the two-line
  `min-height` at both breakpoints. *Done when:* in the preview at 412 px a
  loading card is 175 px, the NBA, NFL and NHL cards keep that height when
  they load, and no layout shift above 0.01 fires while the cards load.
- [x] **Step 3 - Before and after CLS.** Done 2026-11-24. A is the `master`
  build (`409e63b8`, saved before any edit), B this branch, both previewed
  against one local API.

  Playwright layout-shift observer, 3 runs each:

  | Width | A CLS | B CLS |
  |---|---|---|
  | 412 x 823 | 0.041 / 0.222 / 0.218 | 0.0037 / 0.0033 / 0.0038 |
  | 1350 x 940 | 0.283 / 0.245 / 0.246 | 0.277 / 0.241 / 0.242 |

  The 0.041 A run had the data before the home page's first paint. Desktop is
  unchanged: about 0.17 is the gaps panel (out of scope) and about 0.07 the card
  row growing a third Next line at four columns.

  Lighthouse 13.6.0 mobile (default simulated throttling), one warm-up each,
  then 16 runs in A B B A order, medians of 8:

  | | Score | CLS (range) | LCP (sim.) | LCP (obs.) | FCP |
  |---|---|---|---|---|---|
  | A master | 46 | 0.204 (0.037-0.238) | 5.64 s | 749 ms | 3.01 s |
  | B branch | 55 | 0.007 (0.000-0.019) | 5.75 s | 783 ms | 3.00 s |

  Every B run is under 0.02. Local scores are far below production's 83 because
  the simulated LCP here is a data-arrival paint (the NFL Next text in every B run
  and 6 of 8 A runs; the other 2 A runs took the status line, at 2.98-3.01 s).
  LCP is flat within that noise. Verify passed: web 1898 tests and build; API
  6681 passed (run from the worktree with CI's dummy
  `DATABASE_URL=postgresql://localhost/ci`, as the worktree has no `.env`). Specced: production builds of `master` (A,
  :4173) and this branch (B, :4174) against one local API. Per build: three
  Playwright `PerformanceObserver` runs at 412 x 823 and at 1350 x 940, and
  Lighthouse mobile runs (one warm-up each, then 8 runs in A B B A order).
  Record median CLS, score and LCP here. *Done when:* the numbers are recorded,
  the mobile median CLS is under 0.1, and Verify passes.

## Verify

- Verify: `npm --prefix web run verify && cd api && python -m pytest` (API venv active).
- Manual: load `/` at a phone width with network throttling; the title line
  and the cards do not jump when the slates arrive.
- After deploy (outside this fix): production Lighthouse mobile runs, compared
  with the earlier median CLS of about 0.12.

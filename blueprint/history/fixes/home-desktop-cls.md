# Current Feature

## Home page desktop CLS: gaps panel and four-column card row

**Type:** Fix

**Branch:** `fix/home-desktop-cls`, cut from `master` only after
`claude/home-cards-cls-4c8c9b` (the mobile CLS fix, which edits the same
`home.css` and `HomeSportCard.tsx`) has merged.

## The problem

Desktop CLS on the home page is about 0.30 at 1350 x 940 (local production
build, `vite preview` against a local API, Playwright `layout-shift` observer,
measured 2026-11-24 on `master` at `efdc391e`). Shifts in load order:

| t (ms) | Score | What moved | Cause |
|---|---|---|---|
| 769 | 0.018 | everything below the cards, 5 px | status line and card row settling (mobile fix covers the status line) |
| 2203 | 0.029 | gaps panel and records, 66 px | card row 179 -> 245 px when the first slate lands (no Next block on loading cards; the mobile fix reserves 2 lines) |
| 2799 | 0.020 | records cards 102 -> 119 px | record sub-lines arrive; goes below the fold once the panel holds its height |
| 3146 | 0.068 | panel note and records leave the viewport | All tab leaves `Loading` (panel 167 px) on the **first** gap sport's 10 rows (NBA, panel 669 px) |
| 3273 | 0.161 | the 10 NBA rows (y 665-796) pushed out; panel down 19 px | NFL's 10 rows land and insert **above** NBA's (All lists NFL then NBA, panel 1107 px); card row 245 -> 264 px as a 3-line Next block lands |

So the gaps panel accounts for about 0.23, from two things:

1. `propsBody('all')` in `web/src/utils/home.ts` leaves `loading` as soon as
   any sport has rows. NFL, NBA and tennis feed gap rows (NHL never does;
   tennis had none locally), listed in that order, so whenever NBA answers
   first its rows are shoved down by NFL's.
2. The loading body is one `Loading` line (`.home-gaps__empty`, 54 px), while
   the loaded All body is a 36 px header, 20 rows of 44 px and two 40 px
   footers (992 px). A single sport tab is 10 rows plus footers.

The card row: at 1350 px the Next blocks are 3 (NFL day groups, tennis
matches), 2 (NBA) and 1 (NHL) lines, at 19.5 px a line. The mobile fix's
2-line reservation leaves the row 19 px short of its loaded 264 px. (At
1100 px tennis wraps to 4 lines; this fix does not chase every width.)

## The fix

1. **Rows only ever land below shown rows.** `allGapRows` lists the gap
   sports (NFL, NBA, tennis) in order and stops at the first one still
   loading, so a late NFL never pushes NBA's rows down. NHL (no rows) and a
   failed sport never hold it up. Cost: NBA's and tennis's rows wait for
   NFL's slate (the larger home call). (Revised during build: the first
   draft gated on NFL and NBA only, missing that tennis also feeds rows.)
2. **A loading body as tall as the loaded one.** `{ kind: 'loading', rows }`
   carries how many blank rows to hold: `GAPS_PER_SPORT` on the All, NFL, NBA
   and tennis props tabs, 0 elsewhere. Once NFL lands, its 10 rows already
   reach past the fold at 1350 x 940, so later rows grow the panel off
   screen. `HomeGaps` renders the count as the rows table (same header
   height) with a gray `Loading` first row and blank non-breaking-space rows,
   `role="presentation"`. Moneyline, NHL games and errors keep the one-line
   `Loading`. `GAPS_PER_SPORT` moves to `home.ts`, since `homeSources.ts`
   already imports from it.
3. **Three Next lines at four columns.** Above the 1000 px breakpoint (where
   the card row is four columns), `.home-card__next` reserves 3 lines instead
   of the mobile fix's 2. Grid rows already stretch to the tallest card, so
   loaded rows look the same whenever any card's Next block is 3 lines.

Must not break:

- `web/src/main.tsx`'s first-render path (`isHomeRoute`, `preloadHomePage`,
  `prefetchHome`) and the NBA/NHL board prefetch: untouched.
- The mobile result from the prerequisite fix: mobile CLS stays under 0.01.
- Gray reference styling, tab and kind links, and the error and empty texts
  ("No gap lines yet.", "Gap lines could not load.").
- A sport tab or All with fewer than 10 rows a sport still renders; the panel
  just ends shorter (a shrink after load, accepted).

## Build steps

- [x] **Step 1 - All tab waits for both gap sports; loading carries a row count.**
  `home.ts`: `propsBody` gates All on NFL and NBA having answered, and its
  `loading` results carry the expected row count. `home.test.ts`: All stays
  loading while NFL loads even if NBA has rows; All renders once both answer
  (and when one errors); NHL or tennis loading does not hold it; the counts are
  20 for All and 10 for a gap sport's tab.
  *Done when:* the new tests pass and `npm run build` typechecks.
- [x] **Step 2 - placeholder rows and the four-column Next reservation.**
  `HomeGaps.tsx` renders the counted loading body; `home.css` gives
  placeholder rows the loaded row's height and reserves 3 Next lines above
  1000 px.
  *Done when:* on the same production build, desktop CLS (1350 x 940) is under
  0.1 and mobile (412 x 823) under 0.01, median of 3 runs each, before and
  after recorded here.

## Result

Same production build per side, `vite preview` plus local API, Playwright
`layout-shift` observer, 3 runs each (2026-11-24):

| | Before (`master` 60487c18) | After |
|---|---|---|
| Desktop 1350 x 940 | 0.256, 0.241, 0.241 (median 0.241) | 0.053, 0.061, 0.007 (median 0.053) |
| Mobile 412 x 823 | 0.007, 0.004, 0.004 (median 0.004) | 0.007, 0.004, 0.007 (median 0.007) |

The desktop remainder (about 0.06 in two of three runs) is one shift at about
540 ms: card content above the Next block grows about 6 px, moving the Next
block, the gaps heading and the panel. Before the fix a 5 px shift sat at the
same moment (0.003, folded into the larger card-row shift); its cause was not
pinned down.

Hash-route checks with the API held open, then loaded (1350 px): the NFL and
NBA tabs go from 588 to 669 px (growing only at the bottom); NHL and Moneyline
show the one-line `Loading`; the tennis tab holds 10 blank rows and shrinks to
208 px when it loads with no rows.

## Verify

- Measure desktop (1350 x 940) and mobile (412 x 823) CLS on a local
  production build against the local API, before (on `master` after the
  prerequisite merge) and after, 3 runs each, same script.
- Load `/#/`, `/#/?gaps=nfl`, `/#/?gaps=nba`, `/#/?kind=ml` and `/#/?gaps=nhl`: loading
  shows blank rows on the props tabs and `Loading` elsewhere; loaded panels look
  as before.
- Run the Verify command from `AGENTS.md`.

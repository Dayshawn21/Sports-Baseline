# Fix: Re-render only the home section whose data changed

**Type:** Fix
**Branch:** `fix/home-memo` (worktree `.claude/worktrees/sharp-elbakyan-f84efc`, cut from `master` at `6e56f213`)
**Status:** completed 2026-11-23

## The problem

A React profile of the home page (dev build, a minimal DevTools hook injected
by Playwright, 60 s after load, 2026-11-23) counted 15 commits and 351 ms of
render. `HomePage` rendered 12 times, once per query landing, because
`useHomeData` reads all of the home page's queries (about 11) in one hook. Each
render rebuilds every card object and its `retry` closure (`homeCard(...)`,
`() => { ...refetch() }`), `gapTabs(...)`/`gapsBody(...)` and the two href
callbacks inline in `HomePage`, and no child is memoized. So all four
`HomeSportCard`s (48 renders), `HomeGaps`/`GapRows` and `HomeRecords`
re-render on every query, with about 45 router `Link`s each time (548 `Link`
renders, the largest self time at 113 ms).

The gain is modest: LCP's render delay is mostly waiting for data, and TBT is
already 0.27 s (median of four Lighthouse runs). This trims main-thread work
after the data lands.

## The fix

- `useHomeData`: each sport's card is a `useMemo` on that sport's own query
  results, status and `now`; each `retry` is a `useCallback` on that sport's
  `refetch`es; `records` and `sports` are memoized on their inputs. A query
  landing then changes only the objects that depend on it.
- `HomePage`: `gapTabs(...)`, `gapsBody(...)` and the two href functions are
  memoized on `home.sports`, `home.now`, `selected` and `kind`.
- `React.memo` on `HomeSportCard`, `HomeRecords` and `HomeGaps` (default
  shallow comparison; the props above are now stable).

**Must not change:** anything the home page shows or links to, the 60 s clock
(it still refreshes every card's times once a minute), retry behavior, query
keys or options.

## Build steps

- [x] **Step 1 - Stable data in `useHomeData` and `HomePage`.** *Done when:*
  `tsc -b` is clean and the home tests pass. Done 2026-11-23: `tsc -b` clean;
  home, hook and home-component suites pass (124 tests in 9 files). Tennis
  retry now refetches the active `['tennis', 'today']` queries through the
  query client, since `useTennisToday`'s `refetch` is rebuilt every render.
- [x] **Step 2 - Memoize the sections.** Done 2026-11-23: `React.memo` on
  `HomeSportCard`, `HomeRecords`, `HomeGaps`; Verify's web half passed (1,887
  tests and build; no API change). The profile in "The problem" overcounted: it
  treated fibers React left untouched as re-rendered. Corrected profiler (a
  fiber counts only when it is a new fiber object since the last commit and
  carries PerformedWork), 45 s from load, `master` copy on :3012 vs this branch
  on :3011, same dev API:

  | | master | branch |
  |---|---|---|
  | Render self time | 275 ms (13 commits) | 173 ms (15 commits) |
  | `Link` | 305 | 232 |
  | `HomeSportCard` | 36 | 19 |
  | `HomeRecords` | 9 | 5 |
  | `GapRows` | 3 | 1 |
  | `HomeGaps` | 9 | 12 (its tabs change with every sport's data) |
  | `HomePage` | 9 | 12 |

  The page renders as before at 1280x800; the NBA gap tab
  (`#/?gaps=nba`), the Moneyline switch (`#/?gaps=nba&kind=ml`) and the NBA
  card's Slate link (`#/nba`) work. `React.memo` on the three
  components. *Done when:* Verify passes, and the same profile (dev build,
  injected hook, 60 s, warm caches) shows `HomeSportCard` and `Link` renders
  falling from 48 and 548 to roughly one per section per data change, with the
  page looking and linking the same (screenshot and a click on a card link and
  a gap tab).
- [x] **Step 3 - Measure after deploy (no code).** Four Lighthouse 13.6 mobile
  runs against the 02:30 medians (score 81, TBT 0.27 s). Little change expected.
  Done 2026-11-23. Eight production runs after `13684411` deployed scored 63-83
  (median 74.5, LCP 4.01 s, TBT 0.32 s) against four at 81 before, too spread to
  call. A local A/B settled it: production builds of `6e56f213` (A) and
  `13684411` (B) served by `vite preview` against one warm dev API, 12 runs in
  A B B A order:

  | Median of 6 | A (before) | B (memo) |
  |---|---|---|
  | Score | 66.5 (59-76) | 67 (63-73) |
  | FCP | 2.25 s | 2.23 s |
  | LCP | 6.38 s | 6.34 s |
  | TBT | 377 ms (275-608) | 346 ms (319-458) |
  | Script evaluation | 1,073 ms | 993 ms |

  No regression; B does about 7% less script evaluation and its TBT varies
  less, so the production dip was server and timing noise. Local absolutes are
  lower because the dev API builds slates live; only the A-B difference counts.

## Verify

- Verify: `npm --prefix web run verify && cd api && python -m pytest`.
- No React component test runner is set up (no Testing Library), so render
  counts come from the profile, per the testing standards for UI work.

## Out of scope

- Splitting `useHomeData` into per-card hooks, react-router `Link` itself,
  the `useNow` tick interval, bundle size.

## Notes for the AI

- The profile script is in the session scratchpad (`react_profile.js`); the
  hook must be injected before the app loads (`page.addInitScript`).
- Dev-build times run higher than production: compare counts and ratios.

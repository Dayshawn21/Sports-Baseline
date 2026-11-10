# Fix the Home page critique issues

**Type:** Fix
**Completed:** 2026-11-09
**Branch:** `fix/home-critique`

## The problem

The 2026-11-10 design critique of Home (`/`) scored it about 28/40. Seven
issues, all on Home only:

1. At 375px the "Largest gaps" rows hide Market, Line and Model, leaving
   "+5.0 · 43%" with no unit, and the gap cell wraps to 3 lines.
2. The gap sport tabs read "NBA · 9:00 PM" with no `CT`.
3. The "Next: NO @ GS" segment on each sport card shows logos but is not a link.
4. While an NFL game is in progress the card says "No upcoming games".
5. Model records cards end on "--" before their data arrives.
6. "Largest gaps" lists a +0.0 gap row (a tennis total tie breaks line).
7. The four sport cards fill about 1000px on a phone before the gaps start.

## The fix

- **Phone gap rows (1).** Under 640px the gap table drops its column layout:
  each row becomes two lines: player, sport tag and gap · share, then
  market · line · model and the CT time. Desktop is unchanged. The longest
  market label ("Pass completions") pushes the time to a third, right-aligned
  line; the gap never wraps.
- **CT on tabs (2).** `gapTabs` appends ` CT` to a tab's start time.
- **Next matchup links (3).** `HomeNextGame` and `HomeDay` carry the game's
  page path (`/nfl|nba|nhl/game/:id`, `/tennis/match/:id`), built from the
  ids the slate responses already carry. A matchup segment carries that path,
  and the card renders it as a link above the card's cover link. No new
  endpoint.
- **In progress (4).** For team sports a game that has started and is not
  `completed` counts as in progress; with no upcoming game the card says
  "1 in progress" (normal tone) instead of "No upcoming games". Tennis keeps
  its current text, because its feed marks nothing done.
- **Records (5).** A record still loading reads "Loading"; one that answered
  with nothing to grade reads "Not graded yet". Both stay gray. (Locally the
  NFL ranking takes about 16 s, which is where the "--" came from.)
- **Zero gaps (6).** A gap row whose displayed gap rounds to 0.0 is left out
  of the Home gaps list (`isZeroGap`), before the per-sport cut. No other row's
  order, rank or sort changes.
- **Compact cards (7).** Under 640px each card folds to a grid: name and count
  on one row, then the start line, a two-line next list and the view links.
  One card per row, since three 44px view links do not fit half a phone.

Display only: no probability, edge, rank, sort or pick changes. Signal colors
stay gray.

## Build steps

- [x] **Step 1 - logic in `web/src/utils/`.** `gapTabs` CT, `isZeroGap` filter
  in `homeSources.ts`, game paths on next games and days, matchup segments with
  a path, in-progress card text, record labels. Tests in `home.test.ts`,
  `homeSources.test.ts`, `homeRecords.test.ts`.
- [x] **Step 2 - components and CSS.** Matchup links in `HomeSportCard.tsx`,
  two-line phone rows in `HomeGaps.tsx` / `home.css`, compact phone cards.
- [x] **Step 3 - check.** The running app at 1440 and 375, then Verify.

## Evidence

- Running app (own dev server on :3013, API on :8000), 2026-11-09 9:05 PM CT:
  NFL card "1 in progress" (MNF), NBA "8 in progress", NHL "3 in progress";
  tab "Tennis · 10:00 PM CT".
- With the home clock shifted back 4 hours (temporary, reverted): every next
  matchup is a link (`/nfl/game/136`, `/nba/game/21172`, `/nhl/game/57146`,
  `/tennis/match/98885`, ...) and wins the hit test over the card's cover
  link; tabs "NFL · 7:15 PM CT"; at 375px all ten NFL gap rows fold to two
  lines except Josh Allen (Pass completions, time on a third line).
- No live zero-gap row was on the board tonight; `isZeroGap` and the NBA and
  tennis filters are covered by unit tests.
- Verify: web typecheck, 1,442 tests and build pass; API 6,043 passed.

## Done when

- All seven issues are fixed or reported as blocked.
- Verify passes.
- Stopped for review before `/complete`.

# Fix: Home gaps as tabs, ten rows per sport, start times

**Type:** Fix (sized as a fix, not a build-plan feature: one section of one page plus a one-parameter API change)
**Follows:** feature 55 and fix `home-cards` (master `4ba0f4ed`, local, not pushed)
**Status:** complete (2026-11-04)
**Proposed branch:** `fix/home-gaps-tabs` (this worktree, `.claude/worktrees/home-gaps-tabs-c899fe`, cut from `master`)

## The problem

"Largest gaps across sports" shows 3 rows per sport in one flat table with no
times. The owner wants up to 10 rows per sport, tabs to look at one sport at a
time, and start times on the tabs and in the rows.

## Design reference

The existing look: `prototypes/home.html` (the owner's prototype; untracked in
the old worktree `fix-home-cards`, not needed for this change because the table
and tokens already exist in `web/src/components/home/home.css`). No new visual
language: tabs reuse the app's existing tab-strip styling if one fits
(`PlayerMarketTabs` is the closest in `web/src/components/shared/`), else a few
lines of CSS on the same tokens. If the owner wants a mockup of the tab strip
first, say so at review and `/prototype` it before Step 3.

## Decisions fixed here (change them at review, not mid-build)

1. **Ten rows per sport.** `GAPS_PER_SPORT` goes from 3 to 10. The NFL digest is
   client-side (`slateDigest(board, limit)`), so the home passes the limit. The
   NBA digest is capped at 4 by the API: the gaps route gains an optional
   `limit` query parameter (default stays `DIGEST_LIMIT = 4`, cap 10), so the NBA
   slate page, which sends no limit, is unchanged. Ask Lineform calls the service
   directly with its own limit and is untouched. One row per player stays (both
   sports' rules), so a quiet slate can show fewer than 10.
2. **Tabs:** `All`, `NFL`, `NBA`, `NHL`, `Tennis`, in the cards' fixed order.
   The selected tab is the URL param `?gaps=nfl|nba|nhl|tennis` (absent = All,
   written with `replace`), so Back from a player page returns to the same tab.
   An unknown value reads as All.
3. **Tab label and time.** Each sport tab reads `NFL · Thu 7:15 PM`: the sport
   and that sport's next start from `nextStart` plus `startLabel` (Central, the
   weekday only when not today; no `CT` on the tab, the table's time column
   carries it). A sport with no upcoming start, still loading or failed shows
   the label alone. `All` has no time.
4. **Row time column.** Each gap row gets a `Time` column from the digest
   item's existing `when` string (`Thu 7:15 PM CT` for the NFL, `7:30 PM CT` for
   the NBA). No new time formatting for gap rows. Rows stay in the sport's own
   digest order.
5. **`All` is grouped, never merged.** NFL rows first, then NBA rows, each in
   its own digest order. No sort across sports (an NFL gap is a share of a
   reference line, an NBA gap is points plus a share). The Sport column stays
   in `All` and is hidden on a sport tab, where it repeats the tab.
6. **NHL and Tennis tabs show their next games, not gaps.** NHL props are
   line-only with no projection, and tennis has no gray gaps, so neither has
   anything honest to rank. Each tab lists that sport's next games from the
   existing slate data (up to 10, soonest first, `Time` column from
   `startLabel`, no Line/Model/Gap columns), titled plainly: "NHL props are
   line-only with no model projection, so there are no gaps to show. Next
   games:" and "Tennis has no reference gaps. Next priced matches:". Rows are
   not links; a footer link opens the sport's slate (`/nhl`, `/tennis`). `All`
   gets one muted line under the table: "NHL and Tennis have no gap rows; see
   their tabs for next games." Sport-card data is untouched (`nextGames` stays
   at 3 for the cards; the tab uses a new longer `schedule` list).
7. **Gray stays gray.** Rows keep the gray reference styling and the note
   under the table; rows still open the player page (`nflPlayerMarketLink`,
   `nbaPlayerPath`). No color, rank, rule or model change.
8. **"View all" per sport.** On the NFL and NBA tabs a footer link goes to the
   props board (`/nfl/board`, `/nba/board`, from `sportViews`). `All` has none.
9. **Empty and failed states per tab.** A sport tab with no rows says why: no
   games, "No gap lines yet", or (NBA gap query failed) "Gap lines could not
   load" with the games still counting, as today. A loading or failed sport
   shows its state in its tab body instead of an empty table.
10. **Phone (as built: Line is hidden too).** The tab strip is one horizontally scrolling row (no wrap, no
    page-level horizontal scroll). The table keeps hiding Market and Model at
    640px, and as built also Line, because Gap clipped at 375px with the Time column added; the hiding moves from `nth-child` to column classes because the
    Sport and Time columns now vary by tab. Player, Sport (All tab), Time and Gap stay visible.

## In scope

- API: optional `limit` (1 to 10, default 4) on `GET /nba/slate/gaps`, passed to
  `build_slate_gaps`; web `fetchNbaSlateGaps` and `useNbaSlateGaps` take an
  optional limit, in the query key only when sent.
- Web: ten rows per sport, `when` on `HomeGap`, a `schedule` list on
  `HomeSource`, a tested tab/row view model, the tab UI, URL tab state, CSS.

## Out of scope

- Any sort across sports, any color or pick, any model or rule change.
- Other new endpoints or API changes (the one `limit` parameter is the whole
  API change).
- Changing the NBA slate page's own digest (still 4) or the NFL slate page's.
- Matchup text in rows (not asked for), pagination, a "show more" control.
- Tennis or NHL gap rules; a time column on the Model records cards.
- Pushing, deploying, or the interview-guide edit (small UI change; the guide
  claims no home layout detail, to be confirmed at `/complete`).

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real commit at the end.

## Build steps

- [x] **Step 1 - NBA gaps `limit` parameter** - `get_slate_gaps` takes
  `limit: int = Query(DIGEST_LIMIT, ge=1, le=SLATE_GAPS_MAX)` (new constant, 10,
  next to `DIGEST_LIMIT` in `core/nba_slate_gaps.py`) and passes it to
  `build_slate_gaps`. Web: `fetchNbaSlateGaps(date, limit?)` adds `limit` to the
  params only when given; `useNbaSlateGaps(date, limit?)` puts it in the query
  key only when given, so the NBA slate page's key and cache are unchanged.
  *Done when:* `GET /nba/slate/gaps?date=...` still returns at most 4 items;
  `?limit=10` returns up to 10 (one per player); `?limit=0` and `?limit=11`
  return 422; `npm run build` passes; new API tests pass (route default, route
  forwards the limit, route bounds) and the existing
  `test_nba_slate_gaps*` tests pass untouched.
- [x] **Step 2 - Data layer: ten rows, times, schedule** - `GAPS_PER_SPORT = 10`;
  `HomeGap` gains `when`; `gapOf` copies it from the digest item;
  `HomeSource` gains `schedule: HomeNextGame[]` (up to 10 upcoming, soonest
  first; `EMPTY_SOURCE` and the sources updated; `nextGames` stays 3);
  `useHomeData` passes `limit` 10 to `slateDigest` and the NBA gaps hook.
  *Done when:* unit tests prove NFL and NBA sources keep 10 and drop the 11th,
  `when` reaches the gap, `schedule` is soonest-first, capped at 10 and drops
  finished or started games, and the card text and `nextGames` are unchanged;
  `npm run test` and `npm run build` pass; the existing home still renders
  (now with more rows) in the browser.
- [x] **Step 3 - Tab view model (pure)** - in `web/src/utils/home.ts`: a
  `HomeGapTab` model (`key`, `label`, `start: string | null`, body kind
  `rows | games | loading | error`) built from the four sports' data and
  sources and `now`, plus `parseGapTab(param)` (unknown to `all`) and the
  `All` rows (NFL rows then NBA rows, each in order). *Done when:* tests prove
  the tab order and labels; `NFL · Thu 7:15 PM` style start text (today drops
  the weekday); no start when nothing is upcoming, loading or failed;
  `All` is NFL then NBA with no cross-sport sort (an NBA row with a larger
  share still comes after every NFL row); `parseGapTab` handles absent, valid
  and junk values; NHL and Tennis bodies are `games` with their schedule.
- [x] **Step 4 - Tabs UI** - `HomeGaps` renders the tab strip (real buttons or
  links with `aria-selected`/`role="tab"` semantics matching the app's tab
  strip), the table with the `Time` column (and the Sport column on `All`
  only), the NHL and Tennis next-games body, the per-tab empty/error lines,
  the "View all" or slate footer link, and the `All` note; `HomePage` wires
  the `?gaps=` param. CSS for the strip and the class-based column hiding.
  *Done when* (checked in the browser at desktop width): `/` opens on `All`
  with NFL rows then NBA rows, each up to 10, with a Time column; clicking
  `NBA` shows only NBA rows and updates the URL to `?gaps=nba`; reloading that
  URL keeps the tab; opening a row and pressing Back returns to the same tab;
  `NHL` and `Tennis` show next games with times and a slate link, no
  Line/Model/Gap columns; tab labels show each sport's next start; every row
  still opens its player page; no console errors; `npm run build` passes.
- [x] **Step 5 - Phone layout and wrap-up** - check at 375px: the tab strip
  scrolls sideways inside its row with no page-level horizontal scroll, the
  table hides Market and Model and keeps Player, Time and Gap readable, and
  the NHL/Tennis body fits. Run Verify. *Done when:* screenshots at 375px and
  desktop for `All`, `NBA` and `NHL`; the full Verify command passes.

## Files / areas

- `api/app/core/nba_slate_gaps.py`, `api/app/routers/nba.py`,
  `api/tests/` (new `test_nba_slate_gaps_route.py`, or beside the existing gaps tests)
- `web/src/api/nba.ts`, `web/src/hooks/useNba.ts`, `web/src/hooks/useHomeData.ts`
- `web/src/utils/homeSources.ts` (+ test), `web/src/utils/home.ts` (+ test)
- `web/src/components/home/HomeGaps.tsx`, `web/src/components/home/home.css`,
  `web/src/pages/HomePage.tsx`
- `blueprint/history/fixes/home-gaps-tabs.md` at `/complete`

## Data / contracts

- **Load-bearing:** `GET /nba/slate/gaps` keeps its response shape and its
  default of 4 items; `limit` is additive and optional. The query key
  `['nba','slate',date,'gaps']` is unchanged when no limit is sent (the NBA
  slate page and the home no longer share this cache entry once the home sends
  `limit=10`; the home adds its own key).
- Deploy order is not a hazard: a web build sending `limit` to an API that does
  not know it gets the old 4 rows, not an error.
- `HomeGap` gains `when: string`; `HomeSource` gains `schedule`. Both are
  internal to the home; nothing else reads them.
- Tab state lives only in the URL (`?gaps=`).

## Testing

Gate is on; logic ships tests.

- API (pytest, `DATABASE_URL=postgresql://localhost/ci`, main checkout venv
  `C:/dev/SportAppV2/api/.venv/Scripts/python.exe`): route default, forwarded
  limit and 422 bounds, with `build_slate_gaps` monkeypatched; service tests
  already cover `limit` widening the digest.
- Web (Vitest): `homeSources.test.ts` (ten-row cap, `when`, `schedule`),
  `home.test.ts` (tab model, `parseGapTab`, `All` ordering). Fixed `NOW`
  timestamps, no clock mocking, as in `format.test.ts`.
- Components and CSS ride on browser evidence: desktop and 375px screenshots,
  console clean. A worktree has no `node_modules`: run `npm ci` in `web/` first.
- Final gate: `npm --prefix web run verify && cd api && python -m pytest`.

## Notes for the AI

- Gaps are gray reference, never picks. Never sort or compare across sports.
- No em dashes in code, comments, copy or the archive. Comment the why only.
- Use the existing `home-*` CSS tokens; no hardcoded hex.
- Digest `when` strings are already Central with `CT`; do not reformat them.
- Do not touch `slateDigest`'s default limit (4) or `DIGEST_LIMIT`; the NFL and
  NBA slate pages depend on them.
- Ask before committing; the project rule is no AI attribution in commit messages.
- NHL and Tennis tabs must say plainly why they list games and not gaps.

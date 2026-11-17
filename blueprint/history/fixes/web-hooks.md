# Fix: NBA and NFL hooks on the NHL query pattern

**Type:** Fix
**Fixes:** F-68
**Branch:** `fix/web-hooks` (cut from `fix/web-player-pages`, so merge the
four earlier web branches first)

**Completed:** 2026-11-16. Squash-merged to master at the user's request.

### The problem

`hooks/useNhl.ts` builds each query with `queryOptions`, skips a fetch with
`skipToken` when its id is missing or invalid, and puts the normalised slate
date (`parseSlateDate`) in the key. `useNba.ts` and `useNfl.ts` predate that:

- They gate on `enabled: x !== null` and then cast inside the fetcher
  (`gameId as number`, `season as number`, `date as string`), so the type
  checker cannot see that the fetcher never runs without a value.
- NBA keys and fetches the date as given, so `2026-02-30` and the default
  slate are different cache entries and the bad date reaches the API.
- `useNbaModelRanking` and `useNhlModelRanking` are the same hook with a
  different sport and fetcher.
- The 15-minute track-record stale time is declared in
  `useModelTrackRecord.ts:6` and `useNflModelTrackRecord.ts:7`, and written
  inline in both ranking hooks; the 5-minute slate stale time is inline
  about 20 times.

### The fix

- New `hooks/queryTimes.ts` exports `SLATE_STALE_MS` (5 minutes) and
  `TRACK_RECORD_STALE_MS` (15 minutes); every hook uses them.
- `useNba.ts` and `useNfl.ts` get a `queryOptions` builder per query, as
  `useNhl.ts` has, with `skipToken` in place of `enabled` plus a cast. The
  hooks keep their names and signatures, so no page changes.
- NBA date queries key and fetch on `parseSlateDate(date)`.
- One `modelRankingQuery(sport)` for NBA and NHL; `useNbaModelRanking` and
  `useNhlModelRanking` both call it, keeping their query keys.

**Behavior change (edge case only):** an impossible date in an NBA URL
(`?date=2026-02-30`, which passes the player page's format check) now loads
the default slate, as NHL does, instead of sending the bad date to the API.
Valid dates, and every key a valid date produces, are unchanged.

Stays inside `web/`.

### Build steps

- [x] **Step 1 - stale times and ranking.** `queryTimes.ts`, the shared
  ranking query, and the two track-record files use the shared constant.
  Done when: `15 * 60 * 1000` and `5 * 60 * 1000` appear only in
  `queryTimes.ts` among the hooks, and Verify passes.
- [x] **Step 2 - `useNba.ts`.** `queryOptions` builders with `skipToken` and
  the normalised date, plus a `useNba.test.ts` on the `useNhl.test.ts`
  model (invalid ids never fetch, an impossible date shares the default
  slate's entry). Done when: no `as number`/`as string` casts remain in
  `useNba.ts` and Verify passes.
- [x] **Step 3 - `useNfl.ts`.** The same for NFL (season and week, player
  and game ids), with tests. Done when: no casts remain in `useNfl.ts` and
  Verify passes, and the NBA and NFL slates, boards, game and player pages
  load in the app.

### Verify

- `npm --prefix web run verify` after each step.
- In the running app: NBA and NFL slates, props boards, game pages, player
  pages and model pages load; the NHL ones are untouched.

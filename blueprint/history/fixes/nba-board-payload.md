# Fix: NBA prop board payload and request start

**Type:** Fix
**Status:** complete (owner approved via `/complete` on 2026-11-24)
**Fixes:** F-46, F-45
**Branch:** `fix/nba-board-payload`

## The problem

- **F-46 (P2):** `/nba/props` repeats each player's full injury object on
  every line, across every market. On 2026-11-13 that was about 1.6 MB of a
  3.0 MB body (4,432 lines, about 95 of them rendered). Parsing it, plus the
  grouping and GC it causes, makes a 207-259 ms main-thread task on a fast
  desktop and several times that on a phone. The same data is already in each
  game's `injuryReport`, which the board also sends.
- **F-45 (P2):** on a direct load of `#/nba/props` (or `#/nhl/props`), the
  board request starts only when the lazy page chunk mounts. Chunks finished
  at 230-400 ms but the request started at 455-580 ms, and the API answers in
  about 100 ms, so the wait for the chunk is the larger share.

## The fix

- **Payload (F-46), revised 2026-11-24 after measuring:** the 2026-11-23
  board is 2,768,884 B raw (95,825 B gzipped), 10 games, 4,208 lines for 120
  players. Per-line `recent` (last-5 games) is 61.8% of the bytes and per-line
  `injury` only 4.5% (191 lines tagged), so F-46's injury figure is out of
  date and `recent` is the repeat worth removing.
  - The service still builds full lines, so the board/game-page parity test
    holds. The board also gets `playerRecent` per game: each player's recent
    games once (date, opponent, and a `values` map with one entry per market
    that player has a line in).
  - `board_json` omits `recent` and `injury` from every board line.
  - The web expands both back in `fetchNbaPropBoard`: `recent` from the
    player's `playerRecent` games and the line's market, `injury` from the
    game's `injuryReport` with the API's `injury_index` rule (an entry with a
    `playerId`, whose `athleteTeam` is null or equals its `team`, keyed by
    player and team; a line with no team gets none). The cached query data,
    page, drawer and utils see today's shape.
  - A game without `playerRecent` (an older API) is passed through
    unchanged, so the web can deploy first. An older web against the new API
    would show no sparklines or tags until it redeploys; Render builds both
    from the same push.
  - The game page (`/nba/games/{id}/props`) and line-only endpoint are
    unchanged: they send one game, so the repeat is small.
- **Request start (F-45):** a pure `boardPrefetchTarget(hash)` in `utils/`
  returns `{ sport: 'nba' | 'nhl', date }` for a props-board hash (parsing
  `date` as the page does) or null. `main.tsx`, beside the home prefetch,
  imports a small `hooks/boardPrefetch.ts` on demand for a match and calls
  `prefetchQuery(nbaPropBoardQuery(date))` or `nhlPropBoardQuery(date)`, so
  the request runs while the chunk loads. Same query key as the page, so the
  page reads the prefetched data instead of a second request.

**Must not break:**

- Board and game page agree on every value (the 42a parity test stays
  green). Board rows keep their injury tags, freshness and drawer text.
- Gray, unranked board order and the P(over) display rule are untouched.
- The home route's prefetch and first-render path (`isHomeRoute`,
  `preloadHomePage`) are unchanged; `boardPrefetch` is never in the entry
  bundle.
- No schema change, no migration, no new endpoint.

## Build steps

- [x] **Step 1 - Board recent games and injuries once per player.**
  `playerRecent` on `NbaPropBoardGameSchema`, built in `prop_board_response`;
  `board_json` omits line `recent` and `injury`;
  `web/src/utils/nbaPropBoardWire.ts` (`nbaExpandPropBoard`) rebuilds them in
  `fetchNbaPropBoard`. Update the cache docstring's size figures.
  *Done when:*
  - an API test shows the serialized board lines have no `recent` or
    `injury`, and that expanding `playerRecent` (a test helper mirroring the
    web) gives back exactly the full lines' `recent`, including a `null` value
  - a web test shows the expansion reproduces each line's `recent` and
    `injury` for a fixture (matching player and team, a mismatched
    `athleteTeam`, a null `playerId`, a line with no team, a player with no
    recent games) and passes a game without `playerRecent` through unchanged
  - the 2026-11-23 body is measured after the change (raw and gzipped bytes
    recorded below), and the expanded body equals the pre-change body for
    that date (a script comparison of the two JSON files)
  - the board in the browser shows the same sparklines and injury tags
- [x] **Step 2 - Start the board request with the chunk.** `boardPrefetchTarget`
  plus `boardPrefetch.ts`, wired in `main.tsx`. *Done when:*
  - a web test covers `#/nba/props`, `#/nba/props?date=2026-11-20&market=points`,
    `#/nhl/props`, `#/nba` (null), `#/nba/props/x` (null) and a bad date
    (prefetches the default date, as the page would)
  - a direct load of `#/nba/props` in the browser shows `/nba/props` starting
    before the page chunk finishes (network timings recorded below), with
    exactly one `/nba/props` request
  - `npm run build` shows `boardPrefetch` outside the entry chunk

## Verify

- `npm --prefix web run verify && cd api && python -m pytest`
- Open `#/nba/props` directly: injury tags match the game page for the same
  player, one board request, and it starts early in the network panel.
- Open `#/nhl/props` directly: one request, board renders as before.
- `/audit` re-reviews F-45 and F-46 before `/complete`.

## Notes

- Out of scope: F-47 (digest waits for the board), F-48 (re-gzip per
  request, unverified) and per-market fetching. Re-measure F-48 after this
  lands, since the body it compresses shrinks.
- Prefetch on in-app navigation (the Props nav link) is not part of this fix;
  F-45 measured direct loads.

## Results

- **Step 1 (2026-11-24, local, shared database):** the 2026-11-23 board
  (10 games, 4,208 lines, 120 players):

  | Body | Raw | Gzipped |
  |---|---:|---:|
  | Before | 2,768,884 B | 95,825 B |
  | After | 1,561,980 B (-43.6%) | 75,397 B (-21.3%) |

  Expanding the after body with the web's rule gives JSON identical to the
  before body (script comparison, `True`). In the browser
  (`#/nba/props?date=2026-11-23&market=points`), the request returned
  1,561,980 B with `playerRecent` on every game and no line `recent` or
  `injury`; all 7 injured players in the before body show their tag, L5
  averages match (Miller 14.0, Powell 23.4, Brown 24.4), and the console has no
  errors. Verify: web 1,894 tests, typecheck and build; API 6,681 tests.

- **Step 2 (2026-11-24, local production build, `vite preview` on 3001
  against the local API, desktop, unthrottled):** a direct load of
  `#/nba/props?date=2026-11-23&market=points`, start of the `/nba/props`
  request:

  | Build | Runs | Board request starts | Page chunk |
  |---|---:|---|---|
  | Without the prefetch (same code, prefetch line disabled) | 3 | 391, 398, 400 ms | 76-98 ms |
  | With the prefetch | 5 | 103, 132, 151, 158, 169 ms | 56-101 ms |

  One `/nba/props` request in every run, and the board rendered its 120
  rows. `#/nhl/props` made one request (start 157 ms) and rendered.
  `boardPrefetch` builds as its own 0.46 kB chunk, reached from the entry
  only by a dynamic import.
  - **Done-when, in substance only:** the request starts about 250 ms
    sooner, but just after the page chunk's own file, not before it. The
    prefetch's imports (`useNba`, `useNhl` and their shared chunks) arrive by
    about 68 ms, and the import's callback then runs after React's first
    render task on the main thread. Starting it any earlier would mean
    putting the board fetch in the entry bundle or holding the first render
    for it, as the home route does; neither is in this fix.
  - Dev mode (`vite` on 3011) shows no gain, because it serves the prefetch's
    imports one module at a time. Production is the case that matters.
  - Verify: web 1,897 tests, typecheck and build; API 6,681 tests.

## Findings

### nba-board-payload/F-45 [P2] closed - The board request waits for the lazy page chunk before it starts

**File:** web/src/routes/sportPages.tsx:19; web/src/routes/sportPages.tsx:23; web/src/pages/NbaPropBoardPage.tsx:25
**Found:** 2026-11-13 by /audit (scope: NBA and NHL prop pages; lens: performance)
**Why it matters:**
- The query starts only when the lazily imported page mounts. On a direct load (desktop, headless Chromium) the NBA chunk set (54 files) finished at 230-400 ms but `/nba/props` started at 455-580 ms; NHL started at 420-580 ms. The API answers in about 100 ms, so the chunk wait is the larger share.
- Phones pay this on slower parse and network.
**Suggested fix:** start the board query beside the chunk import, for example a `prefetchQuery(nbaPropBoardQuery(date))` fired from the route or the nav link (NHL already exposes `nhlPropBoardQuery`; NBA needs the same `queryOptions` factory).
**Resolution:** Fixed on `fix/nba-board-payload` (step 2, 2026-11-24), pending `/audit`. `main.tsx` imports `hooks/boardPrefetch` on demand for an NBA or NHL props hash (`boardPrefetchTarget`) and prefetches with the page's own query options. On a local production build the NBA request started at 103-169 ms (5 runs) against 391-400 ms without it (3 runs), one request each; it still starts just after the page chunk's file, because the prefetch callback runs after React's first render task. Direct loads only; in-app navigation to Props is unchanged. Closed 2026-11-24 by /audit (scope: current; all lenses): `boardRoute.ts`, `boardPrefetch.ts` and `main.tsx` re-read; the request no longer waits for the page to mount, the key matches the page's (`parseSlateDate` on both sides), the home path is untouched, and `boardPrefetch` is a separate 0.46 kB chunk. No new defect.

### nba-board-payload/F-46 [P2] closed - The NBA board ships 3 MB of JSON and costs a 200-260 ms main-thread task to show one market

**File:** api/app/services/nba/prop_board.py:40; web/src/pages/NbaPropBoardPage.tsx:26
**Found:** 2026-11-13 by /audit (scope: NBA and NHL prop pages; lens: performance)
**Why it matters:**
- The 2026-11-13 body is 3.0 MB raw (124 KB gzipped) for 4,432 lines, though one market (about 95 rows) renders. Each line repeats its player's `injury` object (about 360 B, roughly 1.6 MB of the body) across every market.
- After the response lands, a 207-259 ms long task runs on a fast desktop: grouping and filtering every market, React render, about 75 ms of forced layout (first read is rc-select's `scrollWidth` in `BoardFilterBar`) and 30-45 ms of GC. A mid-range phone runs several times slower. The NHL board (190 KB raw) costs 60-80 ms and is fine.
**Suggested fix:** send injuries once per player (or per game, as `injuryReport` already is) and join them on the client, as `nhlJoinProjections` does for NHL projections. That roughly halves the body, parse and GC. Per-market fetching is the larger option if the task stays heavy on phones.
**Resolution:** Fixed on `fix/nba-board-payload` (step 1, 2026-11-24), pending `/audit`. Re-measured first: on 2026-11-23 per-line `recent` was 61.8% of the 2.77 MB body and `injury` only 4.5%, so the board now sends recent games once per player (`playerRecent`, a value per market) and omits each line's `recent` and `injury`; `nbaExpandPropBoard` rebuilds both in `fetchNbaPropBoard`. Body 2,768,884 to 1,561,980 B raw (-43.6%), 95,825 to 75,397 B gzipped; the expanded body equals the old one. The main-thread task was not re-profiled. Closed 2026-11-24 by /audit (scope: current; all lenses) for the payload: `prop_board.py`, `prop_board_cache.py`, `nbaPropBoardWire.ts` and `api/nba.ts` re-read; the repeat is gone, `board_player_recent`'s `zip(strict=True)` holds because every line of a player reads the same `rows_by_player` list, the web join mirrors `line_fields` and `injury_index`, and both endpoints have one consumer each. The long-task half is tracked as F-77 (unverified). The stale contract description is F-76.


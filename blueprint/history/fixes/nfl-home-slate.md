# Fix: Serve the home page a small stored NFL slice

**Type:** Fix
**Branch:** `fix/nfl-home-slate` (worktree `.claude/worktrees/sharp-elbakyan-f84efc`, cut from `master` at `9c4667d7`)
**Status:** completed 2026-11-23

## The problem

The home page fetches the whole current NFL week, the same `/nfl/slate` the NFL
page uses (`useHomeData` -> `useNflSlate`), only to build the NFL card and its
10-row gap digest. On 2026-11-23 week 11 was 14.2 MB raw (601 KB compressed):
13 games, 9,438 lines (11.6 MB) and 1.4 MB of history samples. Lighthouse
13.6 (mobile) timed it at 1.99 s, the slowest home call, followed by a 563 ms
long task in `index` (likely its parse and `expandNflSlate`, not verified).

What the card reads:
- the digest: `buildNflPropBoard` -> `slateDigest`. Rows group by
  `playerId:market:segment`; the primary is the newest standard line; only
  `isRateable` rows (standard, full game, edge and line set, enough games, not
  a reference) are ranked, against each category's median rateable line;
- `propLines`: the count of those groups across **all** lines;
- games, kickoffs, teams and moneylines.

Every rateable row is a standard full-game line, and keeping every standard
full-game line keeps each group's primary and each category's rateable set
unchanged. That slice is 904 lines, about 1.1 MB raw without samples (measured
from the week-11 body).

## The fix

- **Core (pure, `app/core/nfl_slate_wire.py`)**: `home_slate(body)` keeps each
  game's standard full-game lines, adds `propRowCount` (distinct
  `playerId:market:segment` over all lines, the web's `groupNflPropRows` key),
  then `compact_slate` so only referenced samples stay.
- **Stored copy**: report `nfl_slate_home_<week>` keyed by season, written by
  `app.ingest.nfl_slate_snapshot` right beside each week it stores (no new
  workflow step). `GET /nfl/slate/home?season&week` serves it; production with
  none answers 503 (never builds), dev builds it from the stored or live week.
- **Web**: `fetchNflHomeSlate` + `useNflHomeSlate`
  (`['nfl', 'slate', 'home', { season, week }]`, 5-minute `staleTime`);
  `useHomeData` uses it and `nflSource` reads `propRowCount` instead of
  re-grouping. The NFL page and game page keep the full `/nfl/slate`.

**Load-bearing contract:** `NflHomeSlateWire = NflSlateWire & { propRowCount: number }`;
the lines keep the full `NflSlateLine` shape.

**Must not change:** `/nfl/slate`, its stored weeks, the NFL page, the digest's
rows or order, ranks, colors, or any model. No migration (`report_snapshots`, `0045`).

**Trade-off:** the home page no longer warms the NFL page's cache, so opening
the NFL page from home fetches the full week once.

## Build steps

- [x] **Step 1 - `home_slate` core.** Done 2026-11-23: 4 new tests, 11 passed
  in `test_nfl_slate_wire.py`; on the real week 11 body: 904 lines, 2,643 prop
  rows, 2,561 samples, 2.08 MB raw (the kept lines' history samples are kept
  because `NflSlateLine` types them non-null; the home code never reads them). Pure function + tests in
  `api/tests/test_nfl_slate_wire.py`: drops non-standard and partial lines,
  keeps every standard full-game line (null edge included), `propRowCount`
  counts groups over all lines, samples only those referenced. *Done when:*
  tests pass.
- [x] **Step 2 - Stored report, route, writer.** Done 2026-11-23: 4 new tests,
  API suite 6,635 passed; dev `GET /nfl/slate/home?season=2026&week=11` built
  live against Neon: 200, 2,084,391 bytes, 904 lines, 2,643 prop rows (40.5 s
  locally, the full week's live build). `slate_cache.py` home report
  and read (`report_source`: stored wins, production 503, dev live), `GET
  /nfl/slate/home`, and `nfl_slate_snapshot` storing both per week
  (`--dry-run` stores neither, prints both sizes). Tests on the NBA ranking
  pattern. *Done when:* tests pass; dev `/nfl/slate/home` returns the slice.
- [x] **Step 3 - Web.** Done 2026-11-23: 2 new Vitest cases; Verify passed
  (1,876 web tests and build, 6,635 API). Local browser on the dev API: home
  requests only `/nfl/slate/home` (2,084,391 bytes vs 14,163,676); on week 11 the
  page's own `slateDigest(buildNflPropBoard(...))` gives the same 10 rows from
  both bodies and the row count matches (2,643); NFL card renders 13 games. API function, hook, `useHomeData`, `nflSource`; a
  Vitest that `slateDigest(buildNflPropBoard(...))` and the prop count match
  between a full fixture and its home slice. *Done when:* Verify passes and the
  local home page shows the same NFL card and digest as before.
- [x] **Step 4 - Store copies (separate yes in chat) and docs.** Done
  2026-11-23 01:07 UTC: dry run then real run stored weeks 10-12 and
  `nfl_slate_home_10..12` (2.3, 2.1, 0.1 MB); a production-mode read served the
  week 11 slice (904 lines, 2,643 rows). `AGENTS.md` memory list names
  `/nfl/slate/home`; `docs/commands.md` has no NFL slate snapshot entry to extend.
  `nfl_slate_snapshot --dry-run`, then the real run for the stored weeks;
  `AGENTS.md` memory list and `docs/commands.md`. *Done when:* production-mode
  reads serve the stored slice, and the docs name the new report.

## Verify

- Verify: `npm --prefix web run verify && cd api && python -m pytest`.
- Local browser: home NFL card and digest identical to `master`; Network shows
  `/nfl/slate/home`, about 1 MB raw, not `/nfl/slate`.
- After deploy (outside this fix): Lighthouse mobile on the home page, compared
  with 47 / LCP 5.1 s / TBT 1,240 ms on 2026-11-23.

## Out of scope

- The tennis home calls (separate diagnosis, cold pass pending).
- Shrinking `/nfl/slate` itself or the NFL page's payload.
- JavaScript bundle size and boot-up time.

## Notes for the AI

- Read `app/services/nfl/slate_cache.py`, `app/ingest/nfl_slate_snapshot.py`,
  `app/core/nfl_slate_wire.py`, `web/src/utils/nflPropBoard.ts`,
  `nflPropRows.ts`, `homeSources.ts`, `hooks/useHomeData.ts` first.
- Deploy order: store the home copies before merging, or the home NFL card
  shows its error state until the next snapshot run.
- Any non-dry snapshot run writes the shared Neon database: ask in chat first.

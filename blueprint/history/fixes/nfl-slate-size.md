# Fix: Store each NFL slate history sample once

**Type:** Fix
**Branch:** `fix/nfl-slate-size` (worktree `.claude/worktrees/fix-nfl-slate-size`, cut from `origin/master` at `d3185d91`)
**Status:** code completed 2026-11-08; step 4 (rewrite the stored weeks) runs after the deploy is confirmed

## The problem

The stored week-9 2026 NFL slate is 27.6 MB as served (25.2 MB compact). The
API keeps the serialized body in a cache of up to 4 weeks (`MAX_ENTRIES = 4` in
`app/services/nfl/slate_cache.py`), so the cache alone can hold ~110 MB of the
512 MB instance. Reading one week from `report_snapshots` peaked about +75 MB
above startup (the text from Postgres plus its encoded copy). The 37d note in
`slate_cache.py` recorded 10.7 MB on 2026-10-16; prop lines have since grown to
about 10,300 a week.

Measured on week 9 (10,345 lines, 2026-11-08):

| Per-line field | Share of payload |
|---|---|
| `recentFormLong` | 25.5% |
| `recentForm` | 13.9% |
| `opponentAllowedHistory` | 12.9% |
| `opponentHistory` | 3.2% |

These are history samples (`NflHistorySample`: an average plus up to ten
games). They describe a player's market or an opponent's position, not a
line, so every demon, goblin and standard line for the same player repeats
them. Week 9 has only about 1,481 distinct player-market samples and 756
distinct opponent-allowed samples. All four are read by the web (form window
toggle, prop detail drawer, signal label), so none can be dropped.

## The fix

Keep the in-memory `NflSlateResponse` exactly as it is; change only the JSON
that is stored and served.

- **Wire shape.** `slate_json` (the one serializer, used by the snapshot CLI
  and dev live builds) writes a top-level `samples` array holding each
  distinct history sample once. On each line, `recentForm`,
  `recentFormLong`, `opponentHistory` and `opponentAllowedHistory` become an
  integer index into `samples` (`null` stays `null`). Identical samples share
  one index, so the dedup is lossless by construction rather than depending
  on a key such as player and market.
- **Pure compaction.** The rewrite is a pure function in
  `app/core/nfl_slate_wire.py`, with no I/O, so it is fully unit-tested.
- **One reader on the web.** `fetchNflSlate` in `web/src/api/nfl.ts` passes the
  body through `expandNflSlate` (`web/src/utils/nflSlateWire.ts`), which puts
  the samples back on each line and drops `samples`. Every component, hook and
  util keeps receiving today's `NflSlateResponse`, unchanged. A body without
  `samples` (an old stored copy) passes through as is, so the web works with
  both shapes while the stored weeks are rewritten.
- **Smaller cache.** `MAX_ENTRIES` 4 to 2 (the current week and one neighbor);
  other weeks read their stored copy on demand, which is a database read in
  production, not a build.
- **Unchanged:** every number on every page, the Ask tool (`trim_nfl_slate`
  only counts lines), `prop_predictions` and `targets` (they use the Python
  model, never the JSON), and the route's URL and status codes.

**Expected:** week 9 from 25.2 MB to about 13 MB compact; the cache's worst
case from ~110 MB to ~26 MB.

**Rollout order matters.** The new web must be live before any stored week is
rewritten, or the old web would meet lines without samples. So: merge, push,
confirm the API and web deploys, then rewrite the stored weeks with
`python -m app.ingest.nfl_slate_snapshot --weeks all` (separate yes in chat;
it writes to the shared database). The four NFL workflows that end with the
snapshot step will also write the new shape on their next run, which is safe
once the web is deployed.

## Build steps

- [x] **Step 1 - API: compact wire shape and the smaller cache.** Done
  2026-11-08: 7 new tests, full API suite 6,015 passed; the week-9 dry run
  printed 15 games, 10,345 lines, 13.9 MB (was 25.2 MB compact, 27.6 MB as
  stored).
  - `app/core/nfl_slate_wire.py`: `compact_slate(body) -> body`.
  - `app/services/nfl/slate_cache.py`: `slate_json` compacts; `MAX_ENTRIES = 2`;
    update the module note with the new numbers.
  - `api/tests/test_nfl_slate_wire.py`: identical samples share one index;
    expanding the compact body gives back the original exactly (a Python test
    helper mirrors the web expansion); `null` samples stay `null`; other line
    fields and game fields are untouched; a body without lines still has
    `samples: []`.
  - Measure: `nfl_slate_snapshot --weeks 9 --dry-run` prints the new size
    (dry run stores nothing).

  *Done when:* tests pass; the week-9 dry run prints about 13 MB.

- [x] **Step 2 - Web: expand in the transport.** Done 2026-11-08: 5 new tests;
  `tsc -b` clean. Local APIs served week 9 as the old stored shape (27.6 MB)
  and the new shape (13.9 MB, 3,818 shared samples). The BUF @ MIN game page's
  73 prop rows matched exactly on both, and Josh Allen's pass completions page
  (Last 5, Last 10, vs MIN, MIN allowed, projection breakdown) matched
  text for text; the slate, prop board and home gaps rendered; 375px had no
  sideways scroll and no console errors. The squeezed "VS MIN" heading at
  375px is the same on both shapes (pre-existing, not this fix).
  - `web/src/types/nfl.ts`: the wire types (`NflSlateWire`, line refs).
  - `web/src/utils/nflSlateWire.ts`: `expandNflSlate(raw)`, and
    `web/src/utils/nflSlateWire.test.ts`: a compact body expands to the full
    shape; an old-shape body passes through unchanged; a missing
    `recentFormLong` stays absent; an out-of-range index fails loudly rather
    than showing an empty history.
  - `web/src/api/nfl.ts`: `fetchNflSlate` returns `expandNflSlate(data)`.
  - Browser check against a local API serving the new shape (a dev launcher
    in the scratchpad that hides the stored copy so the dev build runs live):
    `/nfl` slate, the prop board, a prop detail drawer (last 5, last 10,
    opponent, opponent allowed), and the form window toggle, at desktop and
    375px, compared with the same views on the old shape.

  *Done when:* the tests pass and the browser views match on both shapes.

- [x] **Step 3 - Docs and Verify.** Done 2026-11-08: `AGENTS.md` notes the
  stored shape and the rollout order; Verify passed (web 1,310 tests and build,
  API 6,015).
  - `AGENTS.md` Deploy memory list: the slate is stored deduplicated and the
    web expands it; note the rollout order for any future shape change.
  - Verify.

  *Done when:* Verify passes.

- [ ] **Step 4 - After deploy: rewrite the stored weeks.** Only after the
  push and a confirmed live web and API deploy, and a separate yes:
  `nfl_slate_snapshot --weeks all`. Then check on the live site that
  `/nfl/slate` for the current week is about half its old size and the NFL
  pages render as before.

  *Done when:* every stored week is the new shape, and the live `/nfl` page
  and a prop drawer render correctly from it.

## Verify

- Verify: `npm --prefix web run verify && cd api && python -m pytest`.
- Memory probe (scratchpad `memprobe.py`): `/nfl/slate` week 9 peak and kept
  memory roughly halve against the 27.6 MB copy (+75 MB peak, +64 MB kept).

## Out of scope

- The extra ~2.4 MB of spaces Postgres's `jsonb::text` output adds (needs a
  storage-type change).
- Other repeated per-line strings (`qualityFlags`, model version names), worth
  about 2 MB more; a follow-up if needed.
- Gzip in FastAPI (the wire is likely already compressed by Cloudflare).
- The tennis history cache (~55 MB, kept on purpose).

## Notes for the AI

- Do not change `NflSlateResponse` or `NflSlateLineSchema`: Python callers
  (`prop_predictions`, `targets`, the Ask tools) use them.
- The route returns the stored text without validation, so `response_model`
  only feeds the API docs; leave it, and say so in a one-line comment.
- Never rewrite a stored week before the new web is live (see rollout order).
- Interview guide: update the memory paragraph at `/complete`, on disk only.

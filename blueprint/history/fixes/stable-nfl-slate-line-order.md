# Fix: Stable NFL slate line order

**Type:** Fix
**Status:** complete

## The problem

Two `/nfl/slate` queries in `api/app/repositories/nfl.py` sort by columns that
are not unique, so lines that tie come back in whatever order Postgres's plan
produces:

- **`_slate_line_rows`** sorts by `p.name, l.market, l.line, b.season`. A
  player's q1 demon and full-game goblin at the same number tie. `build_slate`
  then sorts each game with a stable sort on `slate_line_rank`, so the query's
  order survives among lines with the same rank.
- **`get_unmatched_slate_lines`** sorts by `player_name, market`, so an
  unmatched player's lines on different segments or lines tie.

Found in 27e Step 1: adding three columns to the baselines CTE changed the
plan and reordered tied lines. The JSON stayed the same length but got a new
SHA-256, and the content was identical once sorted by `line_id`. The same
thing can happen after a Postgres upgrade, an `ANALYZE`, or data growth, so the
board can reshuffle tied lines between loads, and byte-identical checks like
27b's, 27d's and 27e's cannot be trusted.

## The fix

Add the line id as the final tiebreaker in both queries:

- `ORDER BY p.name, l.market, l.line, l.id, b.season`. The id goes before
  `b.season` so each line's season rows stay together, and `by_line` keeps its
  first-seen order.
- `ORDER BY l.raw_json ->> 'player_name', l.market, l.id`

**Must not break:**
- No values change, only the order of lines that tie on every existing key.
  Non-tied lines keep their current order.
- Ranking is still `slate_line_rank` first. The query order only settles ties
  within a rank.
- The projection harness (`get_replay_rows`) runs the same query. Replay cases
  are paired by key, not by position, so its scores are unaffected.

## Build steps

- [x] **Step 1 - Tiebreak both queries on line id.** Edit the two `ORDER BY`
  clauses, and extend the SQL-shape tests in `api/tests/test_nfl_repository.py`
  to assert them.

  *Done when:*
  - The repository tests assert both `ORDER BY` clauses and pass.
  - `/nfl/slate` weeks 2 and 3 of 2026 have the same content as before, with
    lines sorted by `line_id` (SHA-256 of the JSON, as in 27e Step 1).
  - Two runs after the change are byte-identical.
  - Every tied group in week 3 is in ascending `line_id` order.
  - `pytest` passes.

## Verify

- `cd api && .venv\Scripts\python.exe -m pytest`
- The ordered-content and repeat-run hashes above, from a scratch script that
  calls `build_slate` with a fixed `now`.
- Manual: open `/nfl` for 2026 week 3 and reload. A player's same-number lines
  (for example a q1 demon and a full-game goblin) stay in the same order.

# Fix: Mark NFL's stricter finished-week and coverage rules as deliberate

**Type:** Fix
**Fixes:** F-52
**Branch:** `fix/nfl-finished-week-rule`

**Completed:** 2026-11-18. Re-reviewed by an independent reviewer (confirmed: no other NFL status writer, the 39c reason matches the code, comment-only diff); finding set `invalid`; left for the user to merge.

### The problem

The 2026-11-15 audit found two places where NFL's frozen-ranking SQL differs
from NBA's and NHL's, and asked which rule each sport should have before F-51
merges the copies:

- `get_finished_weeks` in `api/app/repositories/nfl.py` requires
  `bool_and(g.status = 'completed')`. NBA (`nba.py:707`) and NHL (`nhl.py:759`)
  also accept `postponed` and `canceled`, so on paper a canceled NFL game keeps
  its week open and out of the ranking record.
- `get_frozen_coverage` matches `fl.market = latest.market` in its `EXISTS`;
  NBA and NHL do not.

### The decision (option A)

Both differences stay; the code says why.

- **Finished weeks.** `upsert_game` (`nfl.py:425`) is the only writer of NFL
  `sport_games` rows and sets `status` to `completed` when both scores exist and
  `scheduled` otherwise. No NFL row can be `postponed` or `canceled`, so the
  stricter rule selects exactly the weeks NBA's rule would. Teaching the
  nflverse ingest those statuses is a separate ingest change, left as a
  possible follow-up; until then the NFL rule must not pretend to handle them.
- **Coverage market match.** Added by 39c (`4b79aa00`, "Coverage also requires
  the frozen line's market to match the gradeable line's market"). `latest`
  is restricted to the nine v4 markets, but the `EXISTS` is not, so without
  the match a Rec Targets freeze stored under the same provider prop would
  count as v4 coverage. F-51 must keep it as an NFL-specific predicate rather
  than drop it in the merge.

### Build steps

- [x] **Step 1 - comment both rules.** Docstring sentences on
  `get_finished_weeks` and `get_frozen_coverage` in
  `api/app/repositories/nfl.py`. No SQL changed, so no test: the existing
  recorded-SQL tests in `test_nfl_repository.py` still pin both statements.

### Evidence

- `grep -rn "INSERT INTO sport_games\|UPDATE sport_games" api/app`: the NFL
  writer is only `repositories/nfl.py:428`, whose status is `completed` or
  `scheduled`.
- Verify: web verify passed (1,861 tests, build clean); API `pytest` 6,553 passed.

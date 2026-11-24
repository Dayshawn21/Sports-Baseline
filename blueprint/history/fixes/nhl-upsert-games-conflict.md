# Fix: NHL `upsert_games` takes NBA's conflict rule

**Type:** Fix
**Fixes:** F-53
**Branch:** `fix/nhl-upsert-games-conflict`

**Completed:** 2026-11-18. Re-reviewed by an independent reviewer (confirmed: clause matches NBA apart from `end_period`, no behaviour change, tests fail on the old statement); finding set `closed`; left for the user to merge.

### The problem

The 2026-11-15 audit found NBA's and NHL's `upsert_games` resolve a conflict
on `(sport, source_game_id)` differently:

| Column | NBA (`nba.py:89-99`) | NHL before (`nhl.py:82-94`) |
|---|---|---|
| `start_utc` | `COALESCE(EXCLUDED.start_utc, sport_games.start_utc)` | `EXCLUDED.start_utc` |
| `season` | never updated | `EXCLUDED.season` |

So on NHL a feed row with no start time could null a known one, and a refresh
could move a game to another season.

### The decision (option A)

NBA's rule for both. A known start time survives a feed row without one, and
a stored game's season is fixed at insert. NHL keeps its extra
`end_period = EXCLUDED.end_period`, since NBA has no such column.

**No behaviour change today.** `NhlGame.start_utc` is a required `datetime`
(`ingest/nhl_api.py:71`), so every NHL row carries a start time, and `season`
is the first four digits of the NHL game id (`nhl_api.py:157`), so a
conflicting row always has the stored season. The rule guards against a
future feed or caller that breaks either assumption.

### Build steps

- [x] **Step 1 - conflict rule.** `api/app/repositories/nhl.py`: drop
  `season = EXCLUDED.season`, coalesce `start_utc`. Test
  `api/tests/test_nhl_games_repository.py` records the statement through a
  fake session (the pattern of `test_nhl_freeze_repository.py`) and pins the
  coalesced start, no `season` in the conflict clause, and the `status` and
  `end_period` refresh. The first two tests fail on the old statement.

### Not in this fix

The audit's second half, moving `_chunks`, `_ids_by_source`, `upsert_team` and
`get_player_candidates` into a shared `repositories/sport_common.py` that takes
`sport` as a required argument, is left for later (it also overlaps F-51).

### Evidence

- `pytest tests/test_nhl_games_repository.py`: 3 passed.
- Verify: web verify passed (1,861 tests, build clean); API `pytest` 6,556 passed.

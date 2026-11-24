# NBA and NHL home latency

**Type:** Fix
**Fixes:** F-43, F-44
**Completed:** 2026-11-11
**Branch:** `fix/nba-nhl-home-latency`

### The problem

On the home page, the NBA and NHL cards and the NBA gaps tab arrive well after
NFL and tennis. Measured on production on 2026-11-11, with all home calls fired
together:

| Endpoint | Time | Why |
|---|---|---|
| `/tennis/predictions/today` | 0.13-0.25s | one cheap read |
| `/nfl/slate` | 0.25-0.29s | served from `report_snapshots` |
| `/nhl/slate` | 0.97-1.18s | rebuilt every request, 8 sequential queries |
| `/nba/slate` | 1.06-1.27s | rebuilt every request, 6 sequential queries |
| `/nba/slate/gaps` | 3.9-4.6s | one query per game, then every line projected in Python |

- **F-44:** `build_slate` in `app/services/nba/slate.py` and
  `app/services/nhl/slate.py` has no cache. Each awaits dates, games, season
  results, latest markets, line movement and prop counts in turn (NHL adds
  injury and goalie snapshots).
- **F-43:** `build_slate_gaps` in `app/services/nba/slate_gaps.py:27` awaits
  `get_modelled_lines` once per game, although `get_date_modelled_lines` runs
  the same `_game_prop_lines` query for the whole date. It then projects every
  line on the 0.5 CPU instance on every request. The web only starts the call
  once `/nba/slate` returns, so the NBA gaps tab lands about 4.5s after load.

### The fix

Reuse the in-process `SerialBuildCache` (`app/services/serial_build_cache.py`)
that the NBA and NHL prop boards already use. Five minutes matches the web's
`staleTime`, and only the build result is kept, so memory stays small (the
slate bodies are 11-24 KB).

1. **NBA gaps N+1:** load the date's modelled lines with one
   `get_date_modelled_lines` call and keep only the not-yet-tipped games' ids.
   Same SQL with a date condition, so the lines and gaps do not change.
2. **NBA gaps cache:** split the build so the date-level work is cached and the
   time-dependent part runs per request:
   - cached per date: the unfiltered gap candidates (all markets) for games
     scheduled at build time, plus the game rows the response needs
   - per request: the `market` filter, `rank_slate_gaps(candidates, now, limit)`
     (which already drops tipped games against `now`), and the schema mapping
   - the router and Ask Lineform (`app/services/ask/tools.py:146`) both read
     through it, so neither can show a game that has tipped since the build
3. **Slate caches:** cache the `/nba/slate` and `/nhl/slate` responses per
   `(requested, today)`, as `cached_prop_board_json` keys on its date
   resolution. A failed build still raises the same error as today rather than
   being cached as an empty slate.

Must not change:

- Any projection, gap, record, market or context value. Only timing changes.
- `get_prior_games`' history depth. It is the depth 20g1's holdout was scored
  on, so bounding it would change model output under the same version. Out of
  scope here.
- `assemble_games`, which the game detail pages share. Only the slate entry
  point is cached.
- The NHL migration `0050` 503 path in `load_contexts`.

Accepted staleness: a slate can be up to 5 minutes behind an ingest write
(odds, scores, injuries, goalies). Ingest runs on hourly or slower schedules,
and the web already holds the data for 5 minutes.

### Build steps

- [x] **1. NBA gaps: one query per date.** Replace the per-game loop in
  `build_slate_gaps` with `get_date_modelled_lines`, filtered to not-tipped
  games. Test that the service makes one line read for a multi-game date and
  returns the same items as before.
  *Done when:* `test_nba_slate_gaps_service.py` passes with the new test.
- [x] **2. NBA gaps cache.** Cache the date's candidates and rank per request,
  for the router and Ask. Tests with a fake clock: a second call within the
  TTL does not rebuild; a game that tips between calls drops out of the
  second response; `market` and `limit` still apply.
  *Done when:* the new tests pass and `test_nba_slate_gaps_route.py` is
  unchanged and green.
- [x] **3. NBA and NHL slate caches.** Wrap both `build_slate` routes in a
  `SerialBuildCache`. Tests: a repeat call within the TTL does not rebuild;
  different `(requested, today)` keys build separately; a build error still
  reaches the client as an error.
  *Done when:* the tests pass and Verify is green.

### Verify

- Verify: `npm --prefix web run verify && cd api && python -m pytest`
- Locally (API on `127.0.0.1:8000`): time `/nba/slate`, `/nhl/slate` and
  `/nba/slate/gaps?date=<today>&limit=5` twice each. The second call of each
  should drop to network time (target under 0.1s locally), with identical bodies.
- Open the home page: the NBA and NHL cards and the NBA gaps tab should arrive
  with NFL and tennis on a warm reload.
- After deploy: rerun the concurrent production timing from the audit. Target:
  warm NBA and NHL slates under 0.3s and NBA gaps under 0.5s. The first call
  after a deploy or a TTL expiry still pays the full build.

### Outcome

- Verify passed on the branch: `python -m pytest` (6085 passed) and
  `npm --prefix web run verify` (typecheck, tests, build).
- Each step's done-when is met by its tests (`test_nba_slate_gaps_service.py`,
  `test_slate_caches.py`); the route test is unchanged.
- `SerialBuildCache` gained a `reraise` option so the NHL missing-migration 503
  keeps its message uncached. Other build failures are now a 503 for 10 s
  instead of a 500 on every call.
- Not measured yet: local or production timings. The post-deploy concurrent
  timing above is the proof still owed. F-43 and F-44 stay `fixed` in the
  ledger until an `/audit` re-review closes them.

## Findings

### nba-nhl-home-latency/F-43 [P2] closed - NBA slate gaps run one query per game and project every line on request

**File:** api/app/services/nba/slate_gaps.py:27; api/app/repositories/nba.py:745
**Found:** 2026-11-11 by /audit (scope: home page path; lens: performance)
**Why it matters:**
- `build_slate_gaps` awaits `get_modelled_lines` once per game (an N+1), although `get_date_modelled_lines` already loads a whole date in one query.
- `get_prior_games` ranks every stored season of every slate player's box scores with `ROW_NUMBER()` before keeping the last few, and every line is then projected in Python on the 0.5 CPU instance.
- Measured on production 2026-11-11 (11-game date): `/nba/slate/gaps?limit=5` took 3.4s alone and 3.9-4.6s beside the other home calls. The home page only fires it after `/nba/slate` returns, so the NBA gaps tab lands about 4.5s after load.
**Suggested fix:** store the digest like `report_snapshots` (written by `nba-ingest.yml` after props refresh), or at minimum swap the loop for `get_date_modelled_lines` and bound `get_prior_games` with a season floor.
**Resolution:** Fixed on `fix/nba-nhl-home-latency` (2026-11-11), awaiting re-review. `build_slate_gaps` reads the date's lines with one `get_date_modelled_lines` call and caches each date's projected candidates for 5 minutes in a `SerialBuildCache`; market filter and ranking run per request against `now`, so a game that tips drops out without a rebuild. A failed build is a 503 for 10 s. The `get_prior_games` history depth is unchanged (it is the depth 20g1's holdout was scored on). Closed 2026-11-11 by /audit (lens: performance) after re-reading `b6dee2f4`: one date line read, per-request ranking against `now`, no new defect (the triggering request's session is the only one used; a cancelled build caches nothing). Production after deploy, home calls fired together: `/nba/slate/gaps` 0.15-0.23s warm, down from 3.9-4.6s.

### nba-nhl-home-latency/F-44 [P2] closed - NBA and NHL slates are rebuilt from 6-8 sequential queries on every request

**File:** api/app/services/nba/slate.py:92; api/app/services/nhl/slate.py:107
**Found:** 2026-11-11 by /audit (scope: home page path; lens: performance)
**Why it matters:**
- NFL's slate is served from `report_snapshots` and tennis from a cheap read, but `/nba/slate` and `/nhl/slate` each await dates, games, season results, latest markets, line movement and prop counts one after another (NHL adds injury and goalie snapshots), with no cache.
- Measured on production 2026-11-11: 0.50s and 0.55s alone, 1.0-1.3s when fired with the rest of the home page, against 0.25s for the 3.4 MB NFL slate and 0.13-0.25s for tennis. That gap is the delay on the home NBA and NHL cards.
**Suggested fix:** a short in-process TTL cache (the props boards already use `cached_prop_board_json`), or a stored snapshot refreshed by the NBA and NHL ingest workflows. Running the independent reads with one round trip each in parallel sessions is a smaller option.
**Resolution:** Fixed on `fix/nba-nhl-home-latency` (2026-11-11), awaiting re-review. `/nba/slate` and `/nhl/slate` read through `cached_slate`, a 5-minute `SerialBuildCache` keyed on `(requested, today)`; `build_slate` and the shared `assemble_games` are unchanged. `SerialBuildCache` gained a `reraise` option so the NHL missing-migration 503 keeps its message uncached; any other build failure is a 503 for 10 s. Closed 2026-11-11 by /audit (lens: performance) after re-reading `b6dee2f4`; no new defect. Production after deploy, home calls fired together: `/nba/slate` 0.15-0.18s and `/nhl/slate` 0.14s warm, down from 1.0-1.3s. The first call after a deploy still pays the build (1.4s and 2.0s cold).

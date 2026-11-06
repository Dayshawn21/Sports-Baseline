# Remove the unused `GET /tennis/players/stats` route

**Type:** Fix
**Fixes:** F-44
**Branch:** `fix/f44-player-stats-route`

### The problem

F-41 removed the web's only caller of `GET /tennis/players/stats`
(`api/app/routers/tennis.py:413`). Nothing in `web/src`, the Ask tools, the API
tests, the docs or the workflows calls it now, so the route, its repository
helper and its response schema are maintained for no reader.

The user chose to remove it on 2026-11-06.

### The fix

- `api/app/routers/tennis.py`: delete `get_player_stats` and the imports only it
  used (`find_player_id_for_stats`, `get_rolling_stats`, `get_latest_elo`,
  `normalize_name`, `SMALL_SAMPLE_MATCHES`, `PlayerStatsResponse`), checking
  each one has no other use in the router.
- `api/app/repositories/players.py`: delete `find_player_id_for_stats` (only this
  route called it).
- `api/app/schemas/tennis.py`: delete `PlayerStatsResponse`.
- `blueprint/context/project-overview.md`: drop `players/stats` from the `/tennis`
  route table.

Must not break: the other `/tennis` routes, the shared helpers that other modules
still import (`get_rolling_stats`, `get_latest_elo`, `normalize_name`,
`SMALL_SAMPLE_MATCHES`), and the admin page's own player-stats refresh, which is a
different route.

### Build steps

- [x] **Step 1 - remove the route and what only it used.** Done when Verify
  passes, a grep for `find_player_id_for_stats`, `PlayerStatsResponse` and
  `players/stats` in `api/app`, `api/tests` and `web/src` finds nothing, and a
  local `GET /tennis/players/stats?name=x` returns 404 while
  `GET /tennis/predictions/today` still answers.

### Verify

- `npm --prefix web run verify && cd api && python -m pytest`
- Local API: `curl -i "http://127.0.0.1:8000/tennis/players/stats?name=x"` is 404.

## Findings

### f44-player-stats-route/F-44 [P3] closed - `GET /tennis/players/stats` has no client left

**File:** api/app/routers/tennis.py:413
**Found:** 2026-11-06 by /audit (scope: current; lens: quality)
**Why it matters:** F-41 removed the web's only caller (`fetchPlayerStats` in `web/src/api/tennis.ts`, used by the drawer's serve and return section). Nothing in `web/src` or the Ask tools calls the route now, so the router function, its repository read and `PlayerStatsResponse` are maintained for no reader. Out of scope for the F-41 fix, which did not touch `api/`.
**Suggested fix:** remove the route and whatever only it uses, or record why it stays public (for example an external consumer).
**Resolution:** fixed 2026-11-06 in f44-player-stats-route (the user chose to remove it): deleted `get_player_stats`, `find_player_id_for_stats`, `PlayerStatsResponse` and the six router imports only the route used, and dropped `players/stats` from the project overview route table. Closed 2026-11-06 by /audit (scope: current; lens: all): no reference left in `api/`, `web/src`, docs or workflows; the shared helpers it imported (`get_rolling_stats`, `get_latest_elo`, `normalize_name`, `SMALL_SAMPLE_MATCHES`) all keep other callers; Verify passes (web 1249, API 5937); a local API answered 404 for `/tennis/players/stats?name=x` and 200 for `/tennis/predictions/today` and `/tennis/players/1/serve-return`.

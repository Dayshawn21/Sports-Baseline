# Retry NFLverse release downloads

**Type:** Fix

**Branch:** `fix/nflverse-download-retry`

## The problem

The Tuesday 2026-10-06 `nfl-ingest.yml` run failed at its first step,
`python -m app.ingest.nflverse`, with `404 Not Found` for
`https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv?season=2026`.
Every later step was skipped: team ELO, red-zone usage, team efficiency, snap
counts, rosters, injuries, depth charts, The Odds API US game odds, Pinnacle,
the prop relink and the four reports. Week 4's ELO, efficiency, snaps and game
odds were never stored (open question 44).

The 404 was transient. NFLverse updates a release asset by deleting it and
uploading it again (`games.csv` shows `created_at` equal to its update time,
2026-10-07 16:06:49 UTC), so the download URL answers 404 for the length of the
upload. The same URL answers 200 now, and `nfl-scores.yml` fetched it the same
day.

No NFLverse ingest retries a download. Each calls `client.get` (depth charts:
`client.stream`), treats a 404 as `SeasonNotPublished`, then calls
`raise_for_status()`:

| Module | Downloads |
|---|---|
| `app/ingest/nflverse.py` | schedule and weekly stats (`_fetch_pair`), schedule only (`fetch_schedules`) |
| `app/ingest/nflverse_pbp.py` | play-by-play |
| `app/ingest/nflverse_team_efficiency.py` | play-by-play |
| `app/ingest/nflverse_snap_counts.py` | snap counts, `players.csv` |
| `app/ingest/nflverse_rosters.py` | weekly rosters |
| `app/ingest/nflverse_injuries.py` | injury reports |
| `app/ingest/nflverse_depth_charts.py` | depth charts (streamed to a temp file) |

`nfl-ingest.yml`, `nfl-prop-odds.yml` and `nfl-scores.yml` all run these, so any
of them can hit an upload window.

## The fix

One shared, bounded retry for NFLverse release downloads, in
`app/ingest/nflverse.py` beside `NFLVERSE_RELEASE_BASE`, which every sibling
already imports:

- **Retried:** HTTP 404, any 5xx, and `httpx.TransportError` (timeouts and
  connection errors are subclasses).
- **Not retried:** any other 4xx (403, 429 and so on), which still fails at the
  caller's `raise_for_status()`.
- **Budget:** 4 attempts with exponential waits capped at 60 s, about 70 s
  worst case per asset. The wait is a parameter so tests run with no wait.
- **Returns the last response** rather than raising on a final 404, so each
  caller keeps its own `if response.status_code == 404: raise
  SeasonNotPublished(...)` check unchanged. An unreleased season still ends in
  `SeasonNotPublished` and exit 1, only later.
- **Logs each retry** at WARNING with the URL and status, so the Actions log
  shows a near miss.
- **Built on `tenacity`** (`AsyncRetrying`, as in `espn_nba_preseason.py`),
  already in `requirements.txt`, per the coding standard for transient network
  failures.

**Depth charts** stream to a temp file, so their retry wraps the whole
open-check-copy and truncates the spool before each attempt; a partial body
from a failed attempt is never parsed.

**Must not break:**

- Parsers, stored rows and every CLI's output on a successful download.
- `SeasonNotPublished` for a season NFLverse has not released, including its
  message and exit code 1.
- The `_fetch_pair` order: the schedule is checked first, then the stats 404
  names the season.

**Out of scope:**

- Splitting `nfl-ingest.yml` so a stats failure cannot skip the odds steps.
  That is a workflow-shape change worth its own fix if retries prove
  insufficient.
- Retrying any non-NFLverse source.
- Backfilling week 4. That is a manual **Re-run all jobs** on the failed
  2026-10-06 run (or a dispatch) after this ships.

## Build steps

- [x] **1. Shared retry and the core ingest.** Add the retrying download helper
  to `app/ingest/nflverse.py` and use it for both `_fetch_pair` downloads and
  `fetch_schedules`. Tests in `api/tests/test_nflverse.py` with
  `httpx.MockTransport` and no wait:
  - 404 then 200 returns the 200 after two requests
  - 503 then 200, and a `ConnectTimeout` then 200, both succeed
  - a persistent 404 makes exactly 4 requests and `fetch_season` raises
    `SeasonNotPublished` for a stats 404
  - a 403 makes exactly 1 request and raises `HTTPStatusError`

  **Done when:** the new tests and the existing `test_nflverse.py` pass, and
  `python -m app.ingest.nflverse --dry-run` still reports 272 games and the
  season's player-week rows.

- [x] **2. The sibling ingests.** Route the downloads in `nflverse_pbp`,
  `nflverse_team_efficiency`, `nflverse_snap_counts` (both files),
  `nflverse_rosters`, `nflverse_injuries` and `nflverse_depth_charts` through
  the helper, keeping each `SeasonNotPublished` check. Add a depth-charts test
  where the first stream answers 404 and the second 200, proving the parsed
  result comes from the second body only.

  **Done when:** the full `pytest` suite passes, and each sibling's `--dry-run`
  (where it has one) still reports the same counts as on master.

## Verify

- `cd api && .venv\Scripts\python.exe -m pytest` passes.
- Dry runs of `nflverse`, `nflverse --schedule-only` and each sibling report the
  same counts as master.
- After merge and push: re-run the failed 2026-10-06 `nfl-ingest.yml` run (or
  dispatch it). Every step goes green, `nfl_team_elo.computed_at` reads the run
  date, and `sport_game_odds` gains fresh `the_odds_api_us` and
  `the_odds_api_eu` NFL rows.

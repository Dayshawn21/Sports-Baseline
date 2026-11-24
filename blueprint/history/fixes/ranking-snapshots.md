# Fix: Serve the model ranking pages from stored snapshots

**Type:** Fix
**Branch:** `fix/ranking-snapshots` (worktree `.claude/worktrees/fix-ranking-snapshots`, cut from `master` at `e398c325`)
**Status:** completed 2026-11-08

## The problem

On 2026-11-08 at 7:26 PM Render restarted `sportapp-api` for exceeding its
512 MB. The memory graph showed it idling at 75-90% all day, and the logs
showed two bursts (6:35 PM and 7:25 PM) of one visitor loading every sport's
slate and model page within seconds. The second burst crashed it.

Measured locally (Windows working set, a fresh process per endpoint, against
the shared Neon database):

| Endpoint | Peak above startup | Cold build |
|---|---|---|
| Startup (imports, tennis LightGBM models) | ~255 MB baseline | |
| `/nba/model/ranking` | **+98 MB** | 9.8 s |
| `/nfl/model/ranking` (v4, the default) | **+91 MB** | 12.6 s |
| `/nfl/model/ranking?model_version=nfl-volume-v1` | +0 MB | 15.8 s |
| `/nfl/model/ranking?model_version=nfl-targets-v1` | +0 MB | 3.1 s |
| `/nfl/model/game-line-clv`, `/nhl/model/ranking`, slates except NFL | under +25 MB | |

The full burst, one request at a time, peaked at 423 MB. In production the
pages request in parallel, so the two ranking builds overlap and pass 512 MB.

Both ranking endpoints are built live on the request path behind a 15-minute
`TimedSingleFlight` cache, so every expiry rebuilds and spikes again. That
breaks the `AGENTS.md` rule that production never builds a heavy report on
request (37d). The NFL model page fires all three NFL ranking versions at
once; the volume version is light but takes 16 s cold.

## The fix

Store the rankings in `report_snapshots` from GitHub Actions and serve the
stored copy, exactly as `/nfl/model/prop-lines` does (37d):

- A stored snapshot wins. Production with no snapshot answers 503 (the
  existing "The ranking check is unavailable" message). Dev with no snapshot
  builds live, as today. All three cases go through `report_source`.
- **NFL:** one report per model version, `nfl_model_ranking_<version>`, for all
  three versions in `NflRankingModelVersion`, so the page's three parallel
  requests are all stored reads. The stored payload is the full
  `NflModelRankingResponse` (the volume version's `log_loss` included), so the
  router stops assembling it.
- **NBA:** one report, `nba_model_ranking`, keyed by season. The router still
  resolves a missing `season` with `nba_season` before the read, so the stored
  season and the served season agree.
- **Writers:** a CLI each, modeled on `app.ingest.nfl_model_snapshot`:
  - `python -m app.ingest.nfl_ranking_snapshot [--season 2026] [--dry-run]`
    (all three versions), added to `nfl-ingest.yml` beside the line-grading
    snapshot step.
  - `python -m app.ingest.nba_ranking_snapshot [--season N] [--dry-run]`
    (default: `nba_season(now)`), added to `nba-ingest.yml` right after the
    "Report NBA forward ranking check" step, so it reads the same freshly
    settled calls.
- The live builders (`track_record.get_ranking_record`,
  `volume_ranking.get_volume_record`) stay as they are: the backtest CLIs and
  dev still use them. The snapshot CLIs call the uncached builders directly so
  a stored copy is never a stale cache entry.

**Must not change:** the response shape of either endpoint, the ranking
numbers, the pick rule, or the web code. No migration (`report_snapshots`
exists since `0045`).

**Freshness trade-off:** the NFL ranking moves from "rebuilt every 15 minutes"
to "rebuilt by the Tuesday ingest". It only grades settled calls, which change
after games, so the Tuesday run covers it. NBA settles daily, and the daily
`nba-ingest.yml` run refreshes it.

**Seasons:** the pages request only the current season. Any other season gets
503 in production unless someone stores it with `--season` (same as prop-lines).

## Build steps

- [x] **Step 1 - NFL ranking snapshot.** Done 2026-11-08: 13 new tests, full
  API suite 5,964 passed; the three 2026 copies stored; served from them, all
  three versions peak at startup's 272 MB (v4 live peaked 362 MB) and answer in
  0.3-1.2 s (live: 2-13 s).
  - `app/services/nfl/ranking_snapshot.py`: `ranking_report(version)`,
    `build_ranking_response(db, season, version)` (uncached), `to_payload`,
    and `get_ranking_response(db, season, version, production)`.
  - `app/routers/nfl.py`: `/nfl/model/ranking` calls `get_ranking_response`
    and raises the existing 503 on `None`.
  - `app/ingest/nfl_ranking_snapshot.py`: stores all three versions, prints a
    one-line headline each, `--dry-run` stores nothing.
  - `api/tests/test_nfl_ranking_snapshot.py`: snapshot served without a live
    build; production without one is `None`; dev without one builds live; each
    version reads its own report name.

  *Done when:* the tests pass; locally with no stored copy `/nfl/model/ranking`
  responds as before for all three versions; after a real CLI run (separate yes
  in chat, it writes to the shared database) the endpoint serves the stored
  copy and the probe shows no spike.

- [x] **Step 2 - NBA ranking snapshot.** Done 2026-11-08: 6 new tests, full
  API suite 5,970 passed; the 2026 copy stored; served from it the route peaks
  at startup's 272 MB (live peaked 369 MB) and answers in 1.1 s (live: 8.2 s).
  - `app/services/nba/ranking_snapshot.py` and `app/ingest/nba_ranking_snapshot.py`,
    the same shape as step 1 with one report.
  - `app/routers/nba.py`: `/nba/model/ranking` serves it.
  - `api/tests/test_nba_ranking_snapshot.py`: the same three cases.

  *Done when:* as step 1, for `/nba/model/ranking`.

- [x] **Step 3 - Workflows and docs.** Done 2026-11-08: both workflows parse
  with the new steps after their ranking checks; the `AGENTS.md` memory list
  names all four stored reports; Verify passed (web typecheck, tests, build;
  API 5,970 passed).
  - `nfl-ingest.yml` and `nba-ingest.yml` gain the snapshot steps.
  - `AGENTS.md` Deploy, Memory list: add both endpoints and their CLIs.
  - `docs/commands.md`: the two new commands.

  *Done when:* both workflow files parse (`python -c "import yaml; ..."`),
  the memory list names all four stored reports, and Verify passes.

## Verify

- Verify: `npm --prefix web run verify && cd api && python -m pytest`.
- Memory probe (scratchpad `memprobe.py`, run from `api/`): with snapshots
  stored, `/nfl/model/ranking` and `/nba/model/ranking` add under +20 MB each,
  and the full crash burst peaks well under the 423 MB measured before.
- Browser: `/nfl/model` and `/nba/model` render the same ranking tables as
  before the change.

## Out of scope

- The 27.6 MB NFL slate payload and its 4-week cache (the next memory fix).
- The tennis history cache (~55 MB, kept on purpose).
- `/nhl/model/ranking` and `/nfl/model/game-line-clv` (light, under +25 MB).
- Upgrading the Render plan.

## Notes for the AI

- Read `app/services/nfl/prop_lines_snapshot.py`, `app/ingest/nfl_model_snapshot.py`
  and `api/tests/test_nfl_prop_lines_snapshot.py` first; mirror them.
- Every CLI run that writes (not `--dry-run`) touches the shared Neon database
  that production reads: ask in chat first.
- Workflow files only register on a push that changes them; that happens at merge.
- Interview guide: a fit for the "keeping a 512 MB host up" passage if one
  exists; update it on disk at `/complete`, never stage it.

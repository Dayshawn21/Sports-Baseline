# Fix: Serve the NHL model ranking from a stored snapshot

**Type:** Fix
**Branch:** `fix/nhl-ranking-snapshot` (worktree `.claude/worktrees/sharp-elbakyan-f84efc`, cut from `master` at `7fc871e8`)
**Status:** completed 2026-11-23

## The problem

On 2026-11-22 a Lighthouse run of the live home page waited about 14 s on
`/nhl/model/ranking`. Timed alone with `curl -w` against production:

| Call | Time |
|---|---|
| Cold, alone | 3.6 s, then 8.3 s |
| Warm (15-minute cache hit) | 0.19 s |
| `/nba/model/ranking` (stored snapshot) | 0.3 to 0.7 s |

`/nhl/model/ranking` is the last ranking still built on the request path behind
the 15-minute `TimedSingleFlight` in `app/services/nhl/track_record.py`. Each
miss grades the whole season in Python (27,690 frozen rows and about 50,000
coverage lines today, more every week) on the one 0.5 CPU Render process, where
it competes with the home page's other cold builds. The 2026-11-08 fix
(`blueprint/history/fixes/ranking-snapshots.md`) left it out as "light, under
+25 MB"; it is now the slowest call on the home page and the same pattern NBA
had at 160,000 rows. That breaks the `AGENTS.md` rule (37d) that production never
builds a heavy report on request.

## The fix

Mirror the NBA ranking snapshot exactly:

- **Service** `app/services/nhl/ranking_snapshot.py`: `RANKING_REPORT =
  "nhl_model_ranking"` keyed by season, `build_ranking_response(db, season)`
  (uncached), `to_payload`, and `get_ranking_response(db, season, production)`
  through `report_source`: a stored snapshot wins, production with none returns
  `None` (the existing 503), dev with none builds live through the cache.
- **Router** `app/routers/nhl.py`: `/nhl/model/ranking` calls
  `get_ranking_response(db, season, is_production(settings.api_env))`. The
  `nhl_season` resolution before the read stays, so stored and served seasons
  agree.
- **Writer** `python -m app.ingest.nhl_ranking_snapshot [--season N] [--dry-run]`,
  defaulting to `nhl_season(now)`, added to `nhl-ingest.yml` right after the
  "Report NHL forward ranking check" step so it stores freshly settled calls.

**Must not change:** the response shape, the ranking numbers, the pick rule,
`track_record.get_ranking_record` (the backtest CLI and dev still use it), or
the web. No migration (`report_snapshots` exists since `0045`).

**Freshness trade-off:** "rebuilt every 15 minutes" becomes "rebuilt by the
daily 09:45 UTC NHL ingest". The record only grades settled calls, which change
when box scores load in that same run.

**Rollout gap:** after deploy and before the first stored copy, production
answers 503 for the NHL model card. Store one copy (step 2, separate yes) before
merging, as the NBA fix did.

## Build steps

- [x] **Step 1 - NHL ranking snapshot service, router and CLI.** Done
  2026-11-22: 6 new tests, the 5 route tests given NBA's no-snapshot dev
  fixture; API suite 6,598 passed. Local live call not run (no `.env` in the
  worktree); dev's live build is covered by
  `test_dev_without_a_snapshot_builds_live`.
  - `app/services/nhl/ranking_snapshot.py` as above.
  - `app/routers/nhl.py`: serve it; 503 on `None` unchanged.
  - `app/ingest/nhl_ranking_snapshot.py`: one-line headline, `--dry-run`
    stores nothing, Windows selector loop as the NBA CLI.
  - `api/tests/test_nhl_ranking_snapshot.py`: the stored payload rebuilds the
    same response; the headline names NHL, the season and the model version; a
    snapshot is served without a live build; production without one is `None`;
    dev without one builds live.

  *Done when:* the new tests pass and the full API suite passes; locally with
  no stored copy `/nhl/model/ranking` answers as before (dev builds live).

- [x] **Step 2 - Store the first copy (separate yes in chat).** Done
  2026-11-23 00:07 UTC: dry run and real run both 2026, `nhl-reference-v1`,
  27,694 frozen rows, 4 slices, weeks 1-7, matching production; a
  production-mode read served the stored copy with the live build stubbed to fail. Run
  `python -m app.ingest.nhl_ranking_snapshot --dry-run`, then the real run,
  which writes to the shared Neon database production reads.

  *Done when:* the dry run prints the same frozen-row count and finished weeks
  as `/nhl/model/ranking` today, and a local production-mode read serves the
  stored copy with no live build.

- [x] **Step 3 - Workflow and docs.** Done 2026-11-23: `nhl-ingest.yml`
  parses with "Store the model page's ranking check" last, after the ranking
  report; `AGENTS.md` names `/nhl/model/ranking` in the memory list. API half of
  Verify passed (6,598); web half not run in this worktree (no `node_modules`,
  no web file changed).
  - `nhl-ingest.yml`: a "Store the model page's ranking check" step after the
    ranking-check report.
  - `AGENTS.md` Deploy, Memory list: add `/nhl/model/ranking` and its CLI.
  - `docs/commands.md`: the new command.

  *Done when:* the workflow parses (`python -c "import yaml; ..."`), the memory
  list names `/nhl/model/ranking`, and Verify passes.

## Verify

- Verify: `npm --prefix web run verify && cd api && python -m pytest`.
- After deploy (outside this fix's commits): cold `/nhl/model/ranking` answers
  under 1.2 s, like `/nba/model/ranking`, and `/nhl/model` shows the same table.

## Out of scope

- `/nhl/slate` (8.2 s cold alone, a query regression to find with `/debug`
  first), `/nba/slate`, `/nba/slate/gaps`: separate fixes.
- Seasons other than the current one: 503 in production unless stored with
  `--season`, same as NBA.
- Deploying, pushing, or upgrading the Render plan.

## Notes for the AI

- Read `app/services/nba/ranking_snapshot.py`, `app/ingest/nba_ranking_snapshot.py`
  and `api/tests/test_nba_ranking_snapshot.py` first; mirror them.
- `NhlModelRankingResponse` is built with `model_validate(record)` today; keep
  the payload `model_dump(mode="json")` so a stored copy round-trips.
- Every non-dry CLI run writes to the shared Neon database: ask in chat first.
- The workflow only registers its change on a push; that happens at merge.
- Interview guide: if the "keeping a 512 MB host up" passage exists, add NHL to
  it on disk at `/complete`; never stage it.

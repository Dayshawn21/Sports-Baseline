# Fix: tennis PrizePicks re-runs keep frozen prop snapshots

**Type:** Fix
**Fixes:** F-20
**Branch:** `fix/prizepicks-rerun-snapshots`

## The problem

`api/app/ingest/prizepicks.py:209` (`_store_props`) starts every real run with
`DELETE FROM props WHERE source = 'prizepicks' AND fetched_at >= CURRENT_DATE`,
then inserts every line again with new ids. `prop_projection_snapshots.prop_id`
references `props.id` with `ON DELETE CASCADE` (migration `0034:26`).

- `tennis-prop-lines.yml` runs at 13:00 UTC and allows `workflow_dispatch`;
  `prop_snapshots` freezes the lines at 13:30. A manual re-run after 13:30
  deletes that day's `props-v3` and `props-v4` frozen rows, which 48e grades
  and 48g adopts from. Nothing logs it.
- If the snapshot job then runs again, it freezes the new ids, so the frozen
  record is now later than it should be (a different `snapshot_at` and inputs).
- A league whose fetch fails is logged and skipped (`prizepicks.py:291-296`),
  but the delete has already removed that league's earlier lines for the day.

Why the delete exists: `props` has no unique key, `upsert_prop` is a plain
`INSERT`, and the delete was the only thing stopping duplicate rows on a
re-run.

## The fix

Make a re-run reuse today's row for the same line instead of deleting and
reinserting it. The `props.id` stays the same, so its snapshots survive, and
the snapshot job's `ON CONFLICT (prop_id, projection_version) DO NOTHING`
skips a line it has already frozen.

1. **Natural key.** A line is the same line when these all match:
   - `source`
   - the player key: `player_id`, else `raw_json ->> 'player_name'`
   - `start_time`
   - `stat_type`
   - `line`
   - `COALESCE(odds_type, '')`

   This is the key `get_today_props` already uses with `DISTINCT ON`, so the
   board shows the same line it does today. A moved line is a new line (new
   row, which can get its own snapshot), as it is now.
2. **Store in place.** A repository function in `repositories/props.py`
   updates today's matching row (`fetched_at >= CURRENT_DATE`) and returns its
   id: it refreshes `fetched_at`, `match_id` and `raw_json`. If no row
   matches, it inserts one. This replaces `upsert_prop`, whose only caller is
   this ingest. The SQL moves out of the ingest module.
3. **Pulled lines.** After storing, delete today's PrizePicks rows that this
   run did not touch **and** that have no snapshot. That keeps the current
   behavior of a re-run dropping lines PrizePicks pulled. It is skipped
   entirely when any league fetch failed, so a partial run removes nothing.
4. **Must not break:**
   - The 13:00 single daily run: the result should be the same rows as today.
   - `get_today_props` and the props board: no read path changes.
   - The `--dry-run` path, which writes nothing.
   - NBA, NFL and NHL PrizePicks, which use `sport_prop_lines` through
     `prizepicks_props.py`: not touched.

**Out of scope:**
- A migration changing the FK to `ON DELETE RESTRICT`. That would be a
  belt-and-braces guard, but it is a manual Neon migration; propose it
  separately if wanted.
- Rows already lost on a past re-run cannot be recovered.

## Build steps

- [x] **Step 1 - store lines in place in the repository.** Add the
  match-or-insert function and the "delete untouched, unsnapshotted rows"
  function to `repositories/props.py`. `_store_props` calls them instead of
  the raw `DELETE`. `run` passes whether every league fetched, and the delete
  runs only when they all did. Remove `upsert_prop`.
  **Done when:**
  - `prizepicks.py` contains no SQL.
  - Tests cover:
    - the player key falls back to the name when `player_id` is NULL
    - a matching line reuses the returned id
    - a new line inserts
    - a league failure skips the delete
    - the delete statement excludes snapshotted rows
  - Verify passes.

- [x] **Repair F-19 - rate limits key on a client-supplied X-Forwarded-For.**
  37d accepted this as a known limit for a read-only demo. 47d's paid Ask cap
  makes it worth fixing now.

  Render fronts every service with Cloudflare and appends to
  `X-Forwarded-For`. So the leftmost entry is the client's own text, and the
  rightmost is likely a Cloudflare edge IP: taking it would put visitors into
  a few shared buckets. Cloudflare writes `CF-Connecting-IP` itself at its
  edge.

  One helper, `client_ip(request)`, returns `CF-Connecting-IP` when present
  and falls back to the socket peer (local dev, tests). The rate-limit
  middleware (`main.py`) and Ask's per-visitor cap (`routers/ask.py`) both use
  it.

  `render.yaml` keeps `--proxy-headers`. Dropping it would make every request
  read as `http`, so FastAPI's redirects would point at `http://`. With the
  Cloudflare header present, the limiters never read the spoofable
  `request.client.host`. Also update the two notes that describe the old
  limit: `docs/commands.md` and the `AGENTS.md` deploy line.
  **Done when:**
  - The helper has tests:
    - the Cloudflare header wins over a spoofed `X-Forwarded-For`
    - a blank header falls back to the peer
    - no header falls back to the peer
    - no peer gives `unknown`
  - Both call sites use the helper.
  - Verify passes.
  - **Not verified until deployed (sources: a Render community thread and a
    blog post, not official docs):**
    - Cloudflare overwrites a client-sent `CF-Connecting-IP`.
    - Every request reaching the API passes through Cloudflare.

    After the deploy, send 11 requests to a heavy route, each with a
    different fake `CF-Connecting-IP` and `X-Forwarded-For`. The 11th should
    get a 429. If it doesn't, the Cloudflare header is client-controlled:
    reopen F-19.
- [x] **Repair F-21 - tennis tiers and signals render green.** Widened after
  the live page showed green edge, EV and rank on an unvalidated tennis
  moneyline.

  `ParlaysPage.tsx`:
  - Every tier (LOCK, STRONG, LEAN, PASS) uses one muted style, as
    `TennisMatchDetail` does.
  - Edge, EV, positive odds, top-3 rank, the singles count badge and the
    "Singles" chip lose `--positive` / `--negative`.

  `TennisSlateSummary.tsx`: the "Locks" and "Strong+" chips lose
  `var(--positive)`.

  Unchanged: tour identity colors and bet-type labels, which mark category,
  not a judgment.
  **Done when:**
  - Neither file uses `--positive`, `--negative` or `--caution` for a
    signal.
  - Verify passes.
  - A screenshot of `/parlays` and the tennis slate shows no green signal.

- [x] **Repair F-34 - a pulled line with a snapshot stays on the board.** The
  prune keeps a pulled row that has a snapshot, so the snapshot survives. It
  now also marks that row `withdrawn` in `raw_json` (no migration).
  `get_today_props` skips withdrawn rows, so the board and the snapshot job
  stop treating the row as live.

  If PrizePicks offers the line again, the refresh overwrites `raw_json` with
  the new payload, and the line is live again. The settled closing-line read
  is unchanged: the row was offered when it was fetched.
  **Done when:**
  - Tests cover:
    - the prune marks kept snapshotted rows withdrawn, and only rows not
      stored this run
    - `get_today_props` excludes withdrawn rows
    - a refresh clears the mark
  - Verify passes.

## Verify

- `npm --prefix web run verify && cd api && python -m pytest` passes.
- **Real-data check (needs a separate yes in chat, because it writes to the
  shared database):**
  1. Note today's count of `prop_projection_snapshots` joined to today's
     PrizePicks `props`.
  2. Run `python -m app.ingest.prizepicks` a second time.
  3. Confirm the count is unchanged and today's `props` row count did not
     grow.
  4. On the next real `prop_snapshots` run, lines frozen before the re-run
     count under `already_stored`, not `inserted`. Its `--dry-run` skips the
     insert, so it cannot show this.

## Findings

### prizepicks-rerun-snapshots/F-14 [P2] closed - The NHL board repeats one projection on every rung and is uncached

**File:** api/app/services/nhl/line_only_props.py:36
**Found:** 2026-11-04 by /audit (scope: current; lenses: all)
**Why it matters:** The board for 2026-10-24 grew from 764 KB to 1,119 KB of
JSON (46 KB gzipped, up from 32 KB) because the identical value, flags and
sample are attached to each of 3,416 lines although there are 1,781
player-market rows. Each request also builds it live in about 0.3 s warm and
1.05 s cold, where the NBA board is served through `prop_board_cache`. No gzip
middleware appears in `app/main.py`, so whether the host compresses is not
verified. The deployed size and latency impact is unmeasured.
**Suggested fix:** Measure first on the hosted API. If it matters, carry the
projection once per player-market (as the player endpoint already does) with a
per-line gap, and consider the NBA board's cache pattern.
**Resolution:** Fixed 2026-11-05, awaiting re-review: `/nhl/props` is served through `prop_board_cache` (5 min, 5 entries, same `SerialBuildCache` as NBA), and the board and game line-only responses carry each player-market projection once in `projections` while a line keeps only its gap, P(over) and line flags. The web rejoins them in `nhlJoinProjections` at the API layer. The hosted payload size was not measured; the gain is by construction (1,781 projections for 3,416 lines on 2026-10-24). Closed 2026-11-06 by /audit (scope: full; lens: all): re-read `prop_board_cache.py`, `line_only_props.py`, `prop_board.py` and `nhlJoinProjections`. Only `integer_line` and `no_over_probability` depend on the line (`core/nhl_projection.py:111-115`); value and gated flags come from availability, so taking the first rung's market projection loses nothing. The cache keys on `(requested, today)` like NBA. No new defect.

### prizepicks-rerun-snapshots/F-17 [P3] closed - Duplicated row formatting and a test module that imports another test module

**File:** api/app/backtest/nhl_over_probability_fit.py:119; api/tests/test_nhl_over_probability_fit.py:13
**Found:** 2026-11-05 by /audit (scope: current; lens: all)
**Why it matters:** The cross-fit table rows and the confirmation rows build the
same fixed-width f-string twice, so a column change must be made in two places.
`test_nhl_over_probability_fit.py` imports `weekly_cases` from
`tests.test_nhl_over_probability_crossfit`, coupling two test files; a shared
helper module would be sturdier.
**Suggested fix:** One row-formatting helper used by both tables; move the
fixture builders to a small helper module under `tests/`.
**Resolution:** Fixed 2026-11-05: one `_family_row` and `_TABLE_HEADER` serve both tables; `weekly_cases` moved to `tests/nhl_replay_cases.py`. Awaiting re-review. Closed 2026-11-06 by /audit (scope: full; lens: all): both tables call `_family_row`, and the NHL fit tests import `tests.nhl_replay_cases`. The wider test-imports-test pattern elsewhere is tracked as F-32.

### prizepicks-rerun-snapshots/F-18 [P3] closed - `_confirm` keeps a write flag that is now always true, and records the read after printing

**File:** api/app/backtest/nhl_over_probability_fit.py:248
**Found:** 2026-11-05 by /audit (scope: current; lens: all)
**Why it matters:** Since F-15's repair, `--confirm` implies `--write`, so
`_confirm(write)` and its `if write:` are dead. Separately the module is written
after the report prints, so a crash between the holdout read and the write
would leave no marker and a rerun would pass the guard. This is an unverified
edge (no such failure was observed) and only matters for the once-only claim.
**Suggested fix:** Drop the parameter and write the module before printing, or
write it in the same step that scores.
**Resolution:** Fixed 2026-11-05: `_confirm()` takes no flag and writes the module before printing. Awaiting re-review. Closed 2026-11-06 by /audit (scope: full; lens: all): `_confirm()` has no flag and `FIT_MODULE_PATH.write_text` runs before the first `print`; `__main__` calls `_confirm()`. No new defect.

### prizepicks-rerun-snapshots/F-19 [P1] closed - Rate limits and Ask's per-visitor cap key on a client-supplied X-Forwarded-For

**File:** render.yaml:20; api/app/main.py:62; api/app/routers/ask.py:38
**Found:** 2026-11-06 by /audit (scope: full; lens: security)
**Why it matters:** uvicorn runs with `--proxy-headers --forwarded-allow-ips '*'`, and with `*` its `ProxyHeadersMiddleware` returns the leftmost `X-Forwarded-For` entry (`uvicorn/middleware/proxy_headers.py:132-133`, installed 0.34.0), which the client writes. Both the rate-limit middleware and `require_ask_budget` key on `request.client.host`. A script that sends a fresh `X-Forwarded-For` per request gets a fresh bucket: the 10/min heavy limit on replay routes and `/admin/session`, the 120/min default, and Ask's 20 questions a day all fall away, and one client can spend the $1 global Ask cap for everyone. Not verified: whether Render's edge overwrites rather than appends the header (appending is the usual behavior).
**Suggested fix:** drop `--proxy-headers` and add one helper that reads the rightmost `X-Forwarded-For` entry (the hop Render's edge appended), falling back to `request.client.host`; use it at both call sites, with a unit test. Confirm Render's header behavior with one request from a known IP.
**Resolution:** Fixed 2026-11-06 on `fix/prizepicks-rerun-snapshots`, awaiting re-review: `core/rate_limits.client_key` keys both the rate-limit middleware and Ask's per-visitor cap on Cloudflare's `CF-Connecting-IP`, falling back to the socket peer. The suggested rightmost-X-Forwarded-For fix was not used: Render sits behind Cloudflare, so that entry is likely an edge address shared by many visitors. `render.yaml` keeps `--proxy-headers` for the https scheme. Not verified until deployed: that Cloudflare overwrites a client-sent header (11 heavy requests with rotating fake headers should end in a 429). Closed 2026-11-06 by /audit (scope: current; lens: all): both call sites (`main.py:62`, `ask.py:39`) key on `client_key`, which reads `cf-connecting-ip` case-insensitively through Starlette `Headers`; nothing else uses `request.client.host` for a security decision, and the start command is unchanged. The deploy-time assumption and the spoofable fallback are tracked as F-35 (unverified); the weak XFF tests as F-36.

### prizepicks-rerun-snapshots/F-20 [P1] closed - A same-day re-run of tennis PrizePicks cascade-deletes that day's frozen projection snapshots

**File:** api/app/ingest/prizepicks.py:209; api/app/db/migrations/versions/0034_prop_projection_snapshots.py:26
**Found:** 2026-11-06 by /audit (scope: full; lens: quality)
**Why it matters:** the ingest clears `props` with `DELETE ... WHERE source = 'prizepicks' AND fetched_at >= CURRENT_DATE`, and `prop_projection_snapshots.prop_id` references `props.id` with `ON DELETE CASCADE` (no later migration changes it). `tennis-prop-lines.yml` runs at 13:00 UTC with `workflow_dispatch`; `prop_snapshots` freezes at 13:30. A manual re-run after 13:30 silently deletes that day's `props-v3` and `props-v4` frozen rows, which the 48e check and 48g adoption grade. A league that fails mid-run (logged and skipped) also loses its earlier lines. It is also the only raw-SQL DML in ingest.
**Suggested fix:** replace the delete with the upsert `prizepicks_props.py` already uses, moved into `repositories/props.py`; or a new migration that makes the FK `ON DELETE RESTRICT` so the delete fails loudly. Until then, do not re-run tennis PrizePicks after 13:30 UTC.
**Resolution:** Fixed 2026-11-06 on `fix/prizepicks-rerun-snapshots`, awaiting re-review: the ingest's day-wide `DELETE` is gone. `repositories/props.store_today_prop` refreshes today's row for the same line (the `get_today_props` DISTINCT ON key) and keeps its id, or inserts one; `delete_pulled_today_props` then removes only today's rows this run did not store and that have no snapshot, and is skipped when any league failed to fetch. Tests in `tests/test_prizepicks_rerun.py`. The SQL has not yet run against Postgres; the spec's real-data re-run check is pending a separate yes. Re-reviewed 2026-11-06 by /audit (scope: current): the cascade path is gone (same-line rows keep their id; the prune never deletes a row with a snapshot; a failed league skips it), but the repair introduced prizepicks-rerun-snapshots/F-34, so this stays `fixed` until prizepicks-rerun-snapshots/F-34 is repaired and re-reviewed. Nameless unresolved props re-insert each run but are pruned (they can never be snapshotted), so that is not a defect. Closed 2026-11-06 by /audit (scope: current; lens: all): with prizepicks-rerun-snapshots/F-34 repaired, a same-day re-run neither deletes nor re-ids a snapshotted line, and the board no longer shows pulled ones; the 13:00 run's rows are unchanged. The SQL is reviewed, not executed: the real-database re-run check in the spec is still pending a separate yes. Remaining test and rounding notes are F-36 and F-37 (P3). Real-data check 2026-11-06 (approved in chat), this branch against the shared database: before, 146 of today's PrizePicks rows and no snapshots (today's freeze had not run; the 13:00 and 13:30 crons actually ran at about 17:00 and 20:45 UTC on recent days). Run 1 at 19:01 UTC stored the 141-line feed: 96 rows refreshed in place, 45 inserted, 50 pulled rows removed, 0 withdrawn. Run 2 at 19:02: 141 rows, 140 ids reused, and one insert plus one removal, which was a real line move (PrizePicks `updated_at` 19:02:38 UTC, between the runs). No duplicate line keys. Every new statement executed on Postgres, including the withdraw UPDATE (0 rows). Not shown: a snapshot surviving a re-run, since none existed today.

### prizepicks-rerun-snapshots/F-21 [P1] closed - Tennis LOCK and STRONG render green on /parlays and the slate chips though no tier passed

**File:** web/src/pages/ParlaysPage.tsx:30; web/src/components/tennis/TennisSlateSummary.tsx:15
**Found:** 2026-11-06 by /audit (scope: full; lens: quality)
**Why it matters:** the signal-colors invariant says nothing unvalidated turns green, and `TennisMatchDetail.tsx:18` grays the same tiers because "no tennis tier has passed the 32b tier rule". `CONF_STYLES` gives LOCK and STRONG `var(--positive)` (used at lines 64, 211, 384), and the "Locks" and "Strong+" chips are colored `var(--positive)`, so one tier reads as a validated pick on two surfaces and as reference on a third. Edge, EV and odds coloring elsewhere on ParlaysPage was not checked.
**Suggested fix:** give LOCK and STRONG the muted PASS style and drop `color` from the two chips; run `/invariants-review` on the rest of ParlaysPage.
**Resolution:** Fixed 2026-11-06 on `fix/prizepicks-rerun-snapshots`, awaiting re-review: widened after the live page showed green edge, EV and rank on an unvalidated tennis moneyline. `ParlaysPage.tsx` uses one muted `TIER_STYLE` for every tier and neutral text for edge, EV, odds, rank, the singles badge and chip; `TennisSlateSummary.tsx` drops green from Locks and Strong+. Tour colors and bet-type labels are unchanged. Screenshot of `/parlays` on 2026-11-06 data showed no green signal. Closed 2026-11-06 by /audit (scope: current; lens: all): no `--positive` or `--negative` remains in `ParlaysPage.tsx` or `TennisSlateSummary.tsx`; `CONF_STYLES` has no references left; `withAlpha` builds a `color-mix`, so `var(--text-muted)` works; `edgePositive` is still used for the sign. Remaining colors are tour identity and the Total Games type label.

### prizepicks-rerun-snapshots/F-34 [P2] closed - A pulled line that has a snapshot stays on the tennis props board after a re-run

**File:** api/app/repositories/props.py:425; api/app/repositories/props.py:49
**Found:** 2026-11-06 by /audit (scope: current; lens: all)
**Why it matters:** introduced by prizepicks-rerun-snapshots/F-20's repair. `delete_pulled_today_props` keeps a row PrizePicks no longer offers when it has a snapshot, and `get_today_props` (24-hour window, `line` in the DISTINCT ON key) still returns it. A manual re-run after the 13:30 freeze, on a day a line moved from 4.5 to 5.5, shows both lines on the board as current. Before the repair, the re-run's delete removed 4.5 (and its snapshot). Only manual same-day re-runs reach it; the 13:00 cron runs once.
**Suggested fix:** when pruning, mark kept snapshotted rows as withdrawn instead of leaving them live (for example `raw_json = jsonb_set(raw_json, '{withdrawn}', 'true')`), and have `get_today_props` skip withdrawn rows. No migration, and the snapshot keeps its prop. Add a test for both halves.
**Resolution:** Fixed 2026-11-06, awaiting re-review: `retire_pulled_today_props` replaces the delete. It marks today's pulled rows that have a snapshot `withdrawn` in `raw_json` and deletes the rest; `get_today_props` skips withdrawn rows; a refresh overwrites `raw_json`, so a re-offered line is live again. Four tests in `tests/test_prizepicks_rerun.py`. Closed 2026-11-06 by /audit (scope: current; lens: all): the withdraw UPDATE and the DELETE share one pulled-today filter (excluding ids stored this run) and split on whether a snapshot exists, so a snapshotted row is never deleted. `get_today_props` skips `withdrawn`, and the refresh matches withdrawn rows too and replaces `raw_json`, so a re-offered line goes live again. The boolean cast is safe: `store_today_prop` is the only `props` writer, and its `raw_json` is the PrizePicks projection object (`id`, `type`, `attributes`, `relationships`) plus the ingest's own keys. No new defect.

### Re-audit evidence, 2026-11-06 (scope: current)

**Scope:** current, all lenses, on `fix/prizepicks-rerun-snapshots`. Merge base and `HEAD` are `eaa95078` (`master`); the whole change is uncommitted (12 modified files plus `api/tests/test_prizepicks_rerun.py`). Reviewed the full diff myself and by one independent reviewer given the code, not my conclusions.
**Signals:** web verify (81 files, 1,235 tests, build) passed; API `pytest` 5,814 passed with a dummy `DATABASE_URL`. No lint command. No database, deploy or network check ran; the SQL's Postgres validity was reviewed, not executed.
**Ledger:** closed prizepicks-rerun-snapshots/F-19 and prizepicks-rerun-snapshots/F-21. prizepicks-rerun-snapshots/F-20 stays `fixed`: its repair introduced prizepicks-rerun-snapshots/F-34. Added prizepicks-rerun-snapshots/F-34 to F-37.

### Re-audit evidence, 2026-11-06, second pass (scope: current)

**Scope:** current, all lenses, on `fix/prizepicks-rerun-snapshots` against `master` (`eaa95078`), all uncommitted. Re-read the full repository and ingest change after the prizepicks-rerun-snapshots/F-34 repair, plus the readers of `props` (`get_today_props`, the settled closing-line read, link coverage) and its only writer.
**Signals:** Verify after the prizepicks-rerun-snapshots/F-34 repair: web 1,235 tests and build passed; API 5,817 passed (dummy `DATABASE_URL`). No source changed since. No database or deploy check ran.
**Ledger:** closed prizepicks-rerun-snapshots/F-20 and prizepicks-rerun-snapshots/F-34. No new findings. Open from this work: F-36 (P3); unverified: F-35, F-37.

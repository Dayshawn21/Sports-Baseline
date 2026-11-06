# Fix: Ledger leftovers: router clocks, live-odds guard, shared test helpers

**Type:** Fix
**Fixes:** F-31, F-32, F-42
**Branch:** `claude/fix-ledger-leftovers-368b4e` (worktree branch)
**Also re-reviewed:** F-33, F-39, F-40 (closed by `/audit current`)

### The problem

- **F-31 (router part).** The props staleness check (`api/app/routers/props.py`, `_enrich`) and the Ask route (`api/app/routers/ask.py`) read the wall clock. Their tests (`test_best_picks`, `test_props_audit_projection`, `test_props_router_best_of`, `test_prop_projection_best_of`, `test_ask_route`) build dates from `datetime.now`, and the Ask spend tests can flake across UTC midnight.
- **F-32 (leftovers).**
  - `/tennis/predictions/best-picks`, `/tennis/bankroll/today` and Ask's best-picks tool call Odds-API.io from a public GET whenever a prediction lacks stored odds and `ODDS_API_KEY` is set.
  - Test modules import helpers from other test modules (`from tests.test_x import ...`), coupling them.
- **F-42.** Record the CRLF byte-check result and close or leave open.

### The fix

- Props: `_enrich`, `_enrich_with_total`, `enrich_with` and `_enrich_props` take a required keyword `now`. Routes and `prop_snapshots` read the clock once at the edge and pass it (the PrizePicks route already reads it for adoption). Tests pass a fixed `NOW`.
- Ask: an `ask_clock` dependency (like `ask_client_factory`) supplies `now`; `test_ask_route.py` overrides it with a fixed instant, and `_today()` derives from it.
- Live overlay: `overlay_live_moneyline` returns before any fetch unless `settings.odds_api_key` is set and `is_production(settings.api_env)` is false (user chose the code guard on 2026-11-06). Tests cover production-with-key, dev-without-key and dev-with-key.
- Test helpers: move every name another test module imports into shared modules under `api/tests/helpers/` (one per source module); both the source and the importing test modules import from there. No test logic changes. The subprocess self-import string in `test_sport_props_pipeline.py` stays.
- Must not break: snapshot output (`prop_snapshots` stores what the page computes), the Ask guardrails, best-picks DB odds.

### Build steps

1. [x] **Props and Ask clocks.** Done when: no `datetime.now` in `_enrich`, the Ask route takes `now` from `ask_clock`, and the five named tests use fixed instants and pass.
2. [x] **Live-overlay guard.** Done when: the overlay never calls `fetch_live_tennis_odds` in production or without a key, with a passing test for each case.
3. [x] **Shared test helpers.** Done when: `grep -rn "from tests.test_" api/tests` finds only the subprocess string in `test_sport_props_pipeline.py`, and the full API suite passes with the same test count.
4. [x] **Ledger.** F-31, F-32 resolutions written; F-42 resolution recorded (stays open: two other checkouts keep a CRLF overrides CSV a merge will not rewrite); F-33, F-39, F-40 re-reviewed by `/audit current`.

### Verify

- `npm --prefix web run verify && cd api && python -m pytest` (with `DATABASE_URL=postgresql+psycopg://audit@localhost/audit` in this worktree).
- The Ask route tests pass with the clock frozen at 23:59:59 UTC.

## Findings

### ledger-leftovers/F-31 [P3] closed - Wall-clock reads in a helper that takes `now`, and in tests

**File:** web/src/utils/nflPropDetail.ts:83; api/tests/test_player_stats_sources.py:51; api/tests/test_ask_route.py:354
**Found:** 2026-11-06 by /audit (scope: full; lens: tests)
**Why it matters:** `history()` calls `formHistoryDate(..., new Date())` though `nflPropDetail` is passed `now`; its test stays stable only because it uses a 2020 date. API tests build dates from `date.today()` / `datetime.now` because `player_stats._fetch_matches` and the props staleness check read the clock (`test_best_picks.py:165`, `test_props_audit_projection.py:61,281`, `test_props_router_best_of.py:24`, `test_prop_projection_best_of.py:38`); the Ask spend test can flake across UTC midnight.
**Suggested fix:** thread `now` through `history()`; inject `today`/`now` into the two API functions and pass fixed values.
**Resolution:** Partly fixed 2026-11-06, still open for the router part (re-reviewed by /audit current the same day). `history()` takes `now`; `nflPropDetail` passes its `now` and `DetailGameLog` its own; a new test passes a 2021 `now` and gets no year on a 2020 game, which the wall clock would add. `player_stats._fetch_matches` takes `today`, both callers pass theirs (the parameter is required, so no wall-clock fallback is left), and `test_player_stats_sources.py` uses a fixed `TODAY` plus a test that a later `today` makes the same page stale. Left for later, because a sibling session owns `api/app/routers/` this round: the props staleness check (`routers/props.py:410`, read by the `test_best_picks`, `test_props_audit_projection`, `test_props_router_best_of` and `test_prop_projection_best_of` dates) and the Ask route clock (`routers/ask.py:73`, behind the `test_ask_route.py` midnight flake). Router part fixed 2026-11-06 (fix ledger-leftovers): `_enrich`, `_enrich_with_total`, `enrich_with` and `_enrich_props` take a required keyword `now`, read once by each route and by `prop_snapshots` (which keeps its capture time after the simulation, as its test pins); the Ask route takes `now` from an `ask_clock` dependency. The four props test files and `test_ask_route.py` use fixed instants (the Ask client fixture freezes the route at 23:59:59 UTC), and a new test shows the same stats are fresh at 47 hours and stale at 49 from the `now` passed in. Closed 2026-11-06 by /audit (scope: current; lenses: all): no wall-clock read is left in `_enrich` or the Ask route body, and the repair introduced no new defect.

### ledger-leftovers/F-32 [P3] closed - Small consistency cleanups

**File:** api/app/routers/props.py:4; api/app/ingest/livetennis.py:940; api/app/ingest/odds_api.py:719; web/src/hooks/useBestPicks.ts:5; web/src/pages/AdminPage.tsx:137; web/src/utils/askError.ts
**Found:** 2026-11-06 by /audit (scope: full; lenses: quality, tests)
**Why it matters:** each is minor; together they are standards drift.
- `Any` in `routers/props.py` (lines 4, 493, 508, 527, 542, 611) and `repositories/props.py:7,28`.
- `os.getenv` fallbacks in `livetennis.py:940-942` and `odds_api.py:719-721` beside `Settings`.
- `useBestPicks.ts` and `useTennisToday.ts` are near copies with their own untested `new Date()` day helpers, already drifted (`dataUpdatedAt`).
- `AdminPage.tsx:137-160` defines its queries and mutations inline instead of in `hooks/useAdmin.ts`.
- `utils/askError.ts` has branching logic and no test.
- `_provider_status_error` (`routers/props.py:536`) would echo 260 characters of a provider body in `detail`; no current caller surfaces it.
- `/tennis/predictions/best-picks` and `/tennis/bankroll/today` can spend Odds-API.io quota from a public GET when `ODDS_API_KEY` is set (dev only; production has none).
- 33 `from tests.test_x import ...` cross-imports couple test files.
**Suggested fix:** take them as they are touched; `askError.test.ts` and the two `os.getenv` removals are the cheapest.
**Resolution:** partly fixed 2026-11-06 (fix p3-layering-cleanup). Fixed: `Any` gone from `routers/props.py` (the client moved with TypedDicts); the two `os.getenv` fallbacks removed (`Settings` already reads the environment); `useBestPicks` / `useTennisToday` share `hooks/useTennisSlate.ts` and a tested `defaultSlateDates(now)` (tomorrow is now the next UTC date, not local-clock +1 day); AdminPage reads `useFlaggedPlayers` and three mutation hooks in `hooks/useAdmin.ts`; `askError.test.ts` added; `_provider_status_error` logs the body and returns only the label. `repositories/props.py` uses `pydantic.JsonValue` instead of `Any` (a sibling fix). Left open: the public-GET Odds-API.io spend (dev only), and the test cross-imports. Both fixed 2026-11-06 (fix ledger-leftovers). By the user's choice of a code guard over an accepted exception, `overlay_live_moneyline` returns before any fetch unless `ODDS_API_KEY` is set and `api_env` is not production (`live_overlay_allowed`, tested for production with a key, dev without one, and the allowed case), so best picks, bankroll and Ask's best-picks tool can never spend Odds-API.io quota in production. The names other test modules imported moved into one module per source under `api/tests/helpers/` (18 modules); `grep "from tests.test_"` now finds only the subprocess string in `test_sport_props_pipeline.py`, and the suite collects the same 5,937 test IDs and passes. Closed 2026-11-06 by /audit (scope: current; lenses: all) after re-reading the guard, its callers and the moved helpers (the moved fixture path and the autouse `_fresh_caches` import were checked).

### ledger-leftovers/F-33 [P3] closed - `streamAsk` drops a final SSE frame that lacks a trailing blank line

**File:** web/src/api/ask.ts:60
**Found:** 2026-11-06 by /audit (scope: full; lens: quality)
**Why it matters:** when the reader finishes, whatever is left in `buffer` is discarded. If the server's last frame ends without a blank line, the `done` event is lost and the drawer reports a cut-off answer. Not verified that the server ever ends that way.
**Suggested fix:** after the loop, parse the leftover buffer plus a blank line when it is not empty.
**Resolution:** Fixed 2026-11-06 defensively. The server never ends a frame without a blank line: every frame `ask_frames` (`api/app/services/ask/answer_stream.py`) yields comes from `sse_frame` or `SSE_PING` (`stream.py`), and both end in `

`. `streamAsk` now passes the leftover to `flushSseBuffer` (`web/src/utils/askStream.ts`), which reads a non-empty one as a final frame; `askStream.test.ts` covers an unterminated `done`, a single-newline ending, and empty, blank and ping-only leftovers. Closed 2026-11-06 by /audit (scope: current, re-review of `web/src/api/ask.ts` and `web/src/utils/askStream.ts`): `streamAsk` flushes the leftover once after the read loop, `flushSseBuffer` returns nothing for a blank tail, and nothing new was introduced.

### ledger-leftovers/F-39 [P3] closed - An Ask spend cap below one question's hold silently refuses every question

**File:** api/app/services/ask/guardrails.py:37; api/app/config.py:54
**Found:** 2026-11-06 by /audit (scope: current; lens: quality)
**Why it matters:** `ask_daily_spend_cap_usd` accepts any value above 0, but since ask-spend-reservation/F-26 a question is admitted only when its worst-case hold fits (`question_reserve_usd`, about $0.021 at the defaults and up to about $0.041 at the largest `ask_max_tokens` and `ask_max_tool_iterations`). A cap of, say, $0.02 makes every `POST /ask` a 503 "reached today's limit" with nothing spent and no log line saying why. The default $1 cap is unaffected.
**Suggested fix:** in `Settings`, reject (or warn at startup on) a cap below `question_reserve_usd(settings)` when `ask_enabled`, so the misconfiguration fails at boot like the other Ask bounds.
**Resolution:** Fixed 2026-11-06. A `Settings` model validator rejects `ask_daily_spend_cap_usd` below one question's hold when `ask_enabled`, so the API fails at construction with a message naming the hold. The hold formula moved onto `Settings` (`ask_prices`, `ask_question_reserve_usd`), and `client.question_reserve_usd` delegates to it, so the check and the reservation share one formula. `test_production_settings.py` covers below, exactly at, disabled, and the default $1 against the largest allowed hold (about $0.041). Closed 2026-11-06 by /audit (scope: current, re-review of `config.py` and `services/ask/`): the validator and `question_reserve_usd` share `Settings.ask_question_reserve_usd`, the route reserves that amount, and nothing new was introduced.

### ledger-leftovers/F-40 [P3] closed - Evicting a just-released lock can let one duplicate build start

**File:** api/app/services/tennis/live_odds_cache.py:80
**Found:** 2026-11-06 by /audit (scope: current; lenses: quality, performance)
**Why it matters:** `asyncio.Lock.release()` clears `locked()` before the woken waiter re-acquires, so an eviction in that window drops a lock a waiter is about to take; a new caller then makes a fresh lock and can build the same key twice. It needs `max_entries` other stores within one loop turn, so it is practically negligible.
**Suggested fix:** track in-flight keys explicitly and skip their locks on eviction.
**Resolution:** Fixed 2026-11-06. `TimedSingleFlight` counts callers holding or waiting on each key's lock (`_users`, decremented in a `finally`, so a cancelled waiter leaves too), and eviction drops a lock only for a key with none. `test_a_lock_handed_to_a_waiter_survives_eviction` reproduces the window with scheduler yields only (`asyncio.sleep(0)`, no timed sleeps): a waiter woken by release, an eviction in the same step, then a new caller. It saw two concurrent builds on the old code and sees one now. Closed 2026-11-06 by /audit (scope: current, re-review of `live_odds_cache.py`): `_users` is incremented before the lock is awaited and decremented in a `finally`, eviction skips any key with users, and a lock kept that way is reused by the waiter's rebuild, so the dict stays bounded. Nothing new was introduced.

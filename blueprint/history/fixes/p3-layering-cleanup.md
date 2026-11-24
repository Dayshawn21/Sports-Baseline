# Fix: P3 layering and consistency cleanup

**Type:** Fix
**Fixes:** F-29, F-30, F-32, F-38
**Branch:** `claude/fix-p3-layering-cleanup-8d2ab9` (worktree branch)

## The problem

Four low-priority audit findings, all standards drift:

- **F-29** - `services/tennis/best_picks_response.py` and `services/tennis/prop_sim.py`
  import from `routers/props.py`. That router holds four raw-SQL helpers
  (`_fetch_win_probs`, `_fetch_market_win_probs`, `_fetch_market_totals`,
  `_fetch_opponent_ids`) and the Odds-API.io client. `/tennis/players/stats`
  builds four `text()` queries inline, and `history_cache.py` runs its two
  queries directly.
- **F-30** - a `/tennis/players/compare` stub returning `{}`, unreferenced
  repository functions, a diagnostic script (`ingest/odds_probe.py`) in the
  live tree, and an unused `ingest/espn_nfl.py`.
- **F-32** - `Any` in `routers/props.py`; `os.getenv` fallbacks beside
  `Settings` in two ingest modules; near-copy hooks `useBestPicks` /
  `useTennisToday` with untested `new Date()` helpers; AdminPage's inline
  queries; no test for `askError.ts`; `_provider_status_error` echoes up to
  260 characters of a provider body in `detail`.
- **F-38** - `build_best_picks_response` swallows an overlay failure with
  `except Exception: pass`.

## The fix

Moves keep behavior identical: same SQL text, same return shapes.

- `MarketTotal` and the four SQL helpers move to `repositories/matches.py`
  as public functions (`get_prediction_win_probs`, `get_market_win_probs`,
  `get_market_totals`, `get_opponent_ids`). The router, `prop_sim`,
  `best_picks_response` and the backtest import them from there.
- The Odds-API.io client (`fetch_live_tennis_odds` and its parsers) moves to
  `services/tennis/live_odds_client.py`; `best_picks_response` imports it at
  module level (no lazy import, no router dependency).
- `/players/stats`'s player lookup moves to `repositories/players.py`
  (`find_player_id_for_stats`); `history_cache`'s two queries move to
  `repositories/matches.py` (`count_completed_results`,
  `get_completed_results`).
- Delete the compare stub and the unreferenced `get_match_by_key`,
  `mark_completed`, `update_birth_date`, `get_latest_prediction`. Of the
  test-only functions: drop `_fetch_market_total_games` (its tests read
  `get_market_totals`) and the NFL repository's `get_latest_game_odds` and
  `upsert_player_alias` with their tests; keep `predict_match` (the batch-path
  oracle in the tennis ELO comparison test) and `volume_unavailable_reason`
  (it pins the reason contract). File deletions (`odds_probe.py`,
  `espn_nfl.py`) only with the user's yes.
- F-32: concrete types replace `Any` in the moved client; drop the two
  `os.getenv` fallbacks; one shared `useTennisSlate` hook plus a tested
  `slateDefaultDates(now)` helper; `useFlaggedPlayers` and three mutation
  hooks in `hooks/useAdmin.ts`; `askError.test.ts`; `_provider_status_error`
  logs the body and returns only the label. The test cross-imports and the
  public-GET quota bullet are left for other work (recorded in the ledger).
- F-38: log the overlay failure with `exc_info=True`.

Must not touch: `api/app/repositories/props.py`, `api/app/ingest/prizepicks.py`,
`api/tests/test_rate_limits.py`, `api/tests/test_prizepicks_rerun.py`,
`web/src/api/ask.ts`, `api/app/services/ask/`,
`api/app/services/tennis/live_odds_cache.py` (sibling sessions).

## Build steps

- [x] **1. F-29 SQL moves** - helpers and `MarketTotal` in `repositories/matches.py`,
  stats lookup in `repositories/players.py`, history queries in
  `repositories/matches.py`; callers and tests repointed.
  Done when: no `text(` in `routers/props.py`, `routers/tennis.py` or
  `history_cache.py`, and pytest passes.
- [x] **2. F-29 client move + F-38 + `_provider_status_error`** - client in
  `services/tennis/live_odds_client.py` with concrete types; overlay failure
  logged. Done when: no service imports `app.routers`, `Any` is gone from
  `routers/props.py`, and pytest passes.
- [x] **3. F-30 dead code** - stub and functions removed; files per the user's
  answer. Done when: grep finds no reference and pytest passes.
- [x] **4. F-32 API** - `os.getenv` fallbacks removed. Done when: grep finds no
  `os.getenv` in the two modules and pytest passes.
- [x] **5. F-32 web** - shared slate hook with tested date helper, admin hooks,
  `askError.test.ts`. Done when: `npm run verify` passes.

## Verify

The Verify command from `AGENTS.md`. Manual: the tennis slate, best picks and
props pages load, and Admin's flagged list and its three actions behave as
before.

## Findings

### p3-layering-cleanup/F-29 [P3] closed - A service imports a router, and SQL lives in routers and a service

**File:** api/app/services/tennis/best_picks_response.py:75; api/app/routers/props.py:675; api/app/routers/tennis.py:403; api/app/services/tennis/history_cache.py:48
**Found:** 2026-11-06 by /audit (scope: full; lens: quality)
**Why it matters:** `best_picks_response` lazily imports `_fetch_live_tennis_odds` from `app.routers.props` to dodge a cycle. `routers/props.py` (931 lines) holds four raw-SQL helpers, the Odds-API.io client and a 254-line `_enrich` (moving them is noted as deferred to item 17); `/tennis/players/stats` builds four `text()` queries inline; `history_cache` queries directly. This breaks "repositories own SQL".
**Suggested fix:** move the SQL helpers into `repositories/matches.py` and `players.py` and the odds client into `services/tennis/`.
**Resolution:** fixed 2026-11-06 (fix p3-layering-cleanup). `MarketTotal` and the four SQL helpers moved to `repositories/matches.py` (`get_prediction_win_probs`, `get_market_win_probs`, `get_market_totals`, `get_opponent_ids`); `/players/stats`'s lookup to `repositories/players.py:find_player_id_for_stats`; `history_cache`'s queries to `count_completed_results` / `get_completed_results`. The Odds-API.io client is `services/tennis/live_odds_client.py`, imported at module level, so no service imports a router. SQL text unchanged; `_enrich` stays in the router (item 17). Closed 2026-11-06 by /audit (scope: current): an independent diff review and the invariants review found no behavior drift in the moves; the one defect found (the apiKey reaching logs through the chained httpx error) is fixed with a test. Verify passed (web 1248 tests, API 5918).

### p3-layering-cleanup/F-30 [P3] closed - Dead code and orphan ingest modules

**File:** api/app/routers/tennis.py:499; api/app/ingest/odds_probe.py; api/app/ingest/espn_nfl.py
**Found:** 2026-11-06 by /audit (scope: full; lens: quality)
**Why it matters:** `/tennis/players/compare` is a `TODO` stub returning `{}`. Unreferenced anywhere: `repositories/matches.py:279` `get_match_by_key`, `:378` `mark_completed`, `repositories/players.py:217` `update_birth_date`, `repositories/predictions.py:61` `get_latest_prediction`. Referenced only by tests: `routers/props.py:732` `_fetch_market_total_games`, `repositories/nfl.py:368` `get_latest_game_odds`, `:1101` `upsert_player_alias`, `services/nfl/volume.py:77` `volume_unavailable_reason`, `services/tennis/predictor.py:106` `predict_match`. `odds_probe.py` is a diagnostic script that reads `os.getenv` and parses `.env` itself (the standards keep these out of `api/`); `espn_nfl.py` has no caller or test.
**Suggested fix:** confirm no script outside `app/` uses them, then delete; move `odds_probe.py` out of the live tree.
**Resolution:** fixed 2026-11-06 (fix p3-layering-cleanup). Removed the compare stub, `get_match_by_key`, `mark_completed`, `update_birth_date`, `get_latest_prediction` (and its now-unused `Prediction` dataclass), and the test-only `_fetch_market_total_games`, NFL `get_latest_game_odds` and `upsert_player_alias` with their tests; grep of `api/`, `.github/workflows/` and `analysis/` found no other caller. Kept on purpose: `predict_match` (the single-match oracle the tennis ELO comparison test checks the batch path against) and `volume_unavailable_reason` (pins the no-reference reason contract). `odds_probe.py` and `espn_nfl.py` deleted with the user's yes (git history keeps them). Closed 2026-11-06 by /audit (scope: current): an independent diff review and the invariants review found no behavior drift in the moves; the one defect found (the apiKey reaching logs through the chained httpx error) is fixed with a test. Verify passed (web 1248 tests, API 5918).

### p3-layering-cleanup/F-38 [P3] closed - Best picks still swallows a live-moneyline overlay failure

**File:** api/app/services/tennis/best_picks_response.py:154
**Found:** 2026-11-06 by /audit (scope: current; lenses: all)
**Why it matters:** `build_best_picks_response` wraps `overlay_live_moneyline` in `except Exception: pass`, the pattern F-23 removed from the Bankroll Builder. A provider or parsing failure silently drops live prices from best picks with no log line.
**Suggested fix:** log a warning with `exc_info=True`, as `bankroll_builder.py` now does.
**Resolution:** fixed 2026-11-06 (fix p3-layering-cleanup). The overlay failure logs a warning with `exc_info=True`; a test pins the log line and that the response still builds. The audit found that `exc_info` would print the chained httpx error, whose message holds the request URL and `apiKey`, so the client now raises `from None` (which also covers the Bankroll Builder log F-23 added); a test checks the traceback for the key. Closed 2026-11-06 by /audit (scope: current): an independent diff review and the invariants review found no behavior drift in the moves; the one defect found (the apiKey reaching logs through the chained httpx error) is fixed with a test. Verify passed (web 1248 tests, API 5918).

# Current Feature

**Feature:** Three small P3 repairs: the Ask stream's leftover frame, an Ask cap below one hold, and a lock evicted mid-handoff
**Type:** Fix
**Fixes:** F-33, F-39, F-40
**Branch:** `claude/fix-p3-ask-cache-dd4fc1` (this worktree's branch)
**Status:** Completed 2026-11-06. Verify passed (web 82 files / 1,241 tests and build; API 5,921 tests). Audit of the diff found one issue, fixed in place: `app.config` would have loaded the Anthropic SDK through `app.core.ask_cost`, so its `AskUsage` import is now type-only.

## The problem

- **F-33.** `streamAsk` (`web/src/api/ask.ts`) discards `buffer` when the reader
  finishes. A last frame without a trailing blank line would lose the `done`
  event. The server never sends one today: every frame comes from `sse_frame`
  or `SSE_PING` in `api/app/services/ask/stream.py`, both ending in `\n\n`, and
  `ask_frames` (`answer_stream.py`) yields nothing else. So this is defensive.
- **F-39.** Since F-26 a question is admitted only when its worst-case hold
  (`question_reserve_usd`) fits `ask_daily_spend_cap_usd`. A cap below the hold
  refuses every question with a 503 and no log line.
- **F-40.** `TimedSingleFlight._store` drops an evicted key's lock when
  `locked()` is false. `asyncio.Lock.release()` clears that flag before the
  woken waiter re-acquires, so a lock with a waiter about to take it can be
  dropped, and a new caller builds the same key alongside that waiter.

## The fix

- **F-33:** a pure `flushSseBuffer(rest)` in `web/src/utils/askStream.ts` that
  parses a non-empty leftover as a final frame; `streamAsk` calls it after the
  loop.
- **F-39:** a `model_validator` on `Settings` that, when `ask_enabled`, rejects a
  cap below one question's hold, so it fails at construction like the `Field`
  bounds. The hold formula moves onto `Settings` (`ask_prices`,
  `ask_question_reserve_usd`) so config and `client.question_reserve_usd`
  share one formula without a circular import.
- **F-40:** count callers holding or waiting on each key's lock; eviction skips
  a key with users. No extra cleanup is needed: a caller holding the lock always
  stores its key before it leaves, so a kept lock belongs to a cached key again.

Must not break: the Ask route's reservation tests, the default $1 cap, and the
existing `TimedSingleFlight` eviction tests.

## Build steps

- [x] **Step 1 - F-33.** `flushSseBuffer` plus vitest cases (unterminated `done`,
  empty or whitespace leftover, a ping leftover). Done when `npm run test` passes.
- [x] **Step 2 - F-39.** Validator plus pytest cases (cap below the hold refused
  when enabled, allowed when disabled, defaults pass at the largest bounds).
  Done when `pytest tests/test_production_settings.py tests/test_ask_cost.py tests/test_ask_route.py` passes.
- [x] **Step 3 - F-40.** In-flight counting plus a deterministic test (no time
  sleeps) that fails on the old code: a waiter woken by release, an eviction in
  the same loop step, then a new caller; at most one build runs at a time.
  Done when `pytest tests/test_live_odds_overlay.py` passes.

## Verify

Verify command from `AGENTS.md`, run when no sibling session is running it.

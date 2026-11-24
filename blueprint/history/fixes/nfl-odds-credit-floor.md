# NFL odds credit floor checked before the paid call

**Type:** Fix
**Fixes:** F-22

### The problem

`api/app/ingest/nfl_odds.py` `run` calls the paid The Odds API `/odds`
endpoint first and only then compares the returned `x-requests-remaining`
with `min_requests_remaining`, returning without storing when it is below.
The floor therefore never prevents a spend: every scheduled run under it
burns a credit and throws the response away. It also calls the provider
when there are no upcoming NFL games (offseason), unlike `nba_odds.py`.

### The fix

Follow the `nba_odds.py` order:

1. Return before any provider call when `get_upcoming_games` returns nothing.
2. Read the balance with the free `/sports` call and skip the paid call
   unless `credit_gate(remaining, min_requests_remaining)` passes; an unknown
   balance never spends (a change from today, where an unknown balance stored).
3. Only then fetch `/odds` and store, with no post-call floor check.

`credit_gate` and `_free_remaining` move from `nba_odds.py` into
`nfl_odds.py`, which `nba_odds.py` already imports from, so both ingests
share one gate. NBA behavior is unchanged. The NFL floor default (5), CLI
flags, workflows and the Pinnacle path stay as they are.

### Build steps

- [x] **1. Gate the paid call.** Reorder `run`, move the gate helpers, and
  add tests with a fake HTTP client (no real calls) for: no games makes no
  request; a balance below the floor or unknown makes only the `/sports`
  request; at or above the floor makes `/sports` then `/odds` and stores.
  Update the two existing `run` tests to stub the free balance call.
  **Done when:** the new tests fail on the old order and pass on the new one,
  and Verify passes.

### Verify

- `cd api && pytest tests/test_nfl_odds.py tests/test_nba_odds.py`
- The Verify command from `AGENTS.md`.
- Never run the real ingest: every run, dry run included, spends credits.

## Findings

### nfl-odds-credit-floor/F-22 [P2] closed - `nfl_odds` spends its credit before the floor check and with no games

**File:** api/app/ingest/nfl_odds.py:72
**Found:** 2026-11-06 by /audit (scope: full; lens: performance)
**Why it matters:** `run` calls the paid `/odds` endpoint first and only then returns without storing when `remaining < min_requests_remaining`, so the floor never prevents a spend and every scheduled run below it burns a credit for nothing. With no upcoming games (offseason) it still calls, unlike `nba_odds.py:56-58`.
**Suggested fix:** follow `nba_odds.py:37-63`: return early on no games, check the floor with the free `/sports` call, then fetch.
**Resolution:** 2026-11-06 fixed by /fix F-22: `run` returns before any provider call with no upcoming games, reads the balance with the free `/sports` call and skips `/odds` unless `credit_gate` passes (an unknown balance never spends). The gate and `_free_remaining` moved into `nfl_odds.py` and `nba_odds.py` imports them. Tests in `tests/test_nfl_odds.py` drive a fake HTTP client and failed on the old order. Closed 2026-11-06 by /audit (scope: current; all lenses): re-reviewed `nfl_odds.py` and `nba_odds.py`; the paid `/odds` call now runs only after the no-games return and the free-balance gate, on both the us and Pinnacle paths, NBA behavior is unchanged, and no new defect was found. Verify passed (web 1235 tests, API 5821).

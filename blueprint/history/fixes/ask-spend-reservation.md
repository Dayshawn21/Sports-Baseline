# Ask spend cap reserves before a question runs

**Type:** Fix
**Fixes:** F-26

## The problem

Ask Lineform's $1/day global spend cap is checked at admission
(`guardrails.spend.exhausted()` in `api/app/routers/ask.py`) but a question's
cost is added only in the stream's `finally`
(`record_question` in `api/app/services/ask/answer_stream.py`). Every question
in flight therefore passes the check, so concurrent questions can overshoot the
cap by one question's cost each, with no bound on how many are in flight.

## The fix

Reserve a worst-case cost per question at admission and settle it to the real
cost when the question ends.

- `app/core/ask_cost.py`: a pure `max_question_cost_usd(prices, max_requests,
  max_tokens)` bound. Output per request is capped by `ask_max_tokens`; input
  is not capped in code, so it assumes a fixed `RESERVE_INPUT_TOKENS_PER_REQUEST`
  (20,000, several times the ~3,600 a typical round uses). Requests per
  question are `ask_max_tool_iterations + 1`. At defaults this is about $0.018.
- `DailySpend` gains `reserve(today, amount, cap) -> Reservation | None` (refuses
  when spent + reserved + amount would pass the cap) and a `Reservation` whose
  `settle(cost)` releases the hold and records the real cost once; later calls
  are no-ops. A reservation from an earlier UTC day only releases.
- The router reserves after the per-client check passes (a 429 holds nothing)
  and releases if the client cannot be built. `ask_frames` settles in its
  `finally` with the estimated cost (zero when no request reached Claude).
- A `StreamingResponse` subclass releases the reservation after the response
  ends, so a disconnect before the stream body starts (the generator never
  runs, so its `finally` never does) cannot leak a hold for the rest of the day.

**Why not a semaphore:** a concurrency cap does not tie admission to the money
left. N streams at once still overshoot by N worst cases, and it refuses
visitors when the app is busy even with budget to spare. The reservation makes
the admission check count what is already committed, which is the actual bug.

Must not break: a refused question still costs nothing and uses none of the
visitor's 20; the logged `ask question` line and `spent_today_usd` keep their
meaning. A real cost above the reservation (an input far past the assumption)
can still overshoot by that excess; the Console monthly limit stays the hard
stop.

## Build steps

- [x] **1. Reserve and settle.** `max_question_cost_usd`, `DailySpend.reserve`
  and `Reservation`, the router and `ask_frames` wiring, the response subclass,
  tests with no network, and the Ask note in `docs/commands.md`.
  Done when: tests show a second concurrent question is refused once the
  reservations fill the cap, settlement records the real cost and frees the
  rest, a failed client build or an unstarted stream releases the hold, and
  Verify passes.

## Verify

- `cd api && python -m pytest tests/test_ask_guardrails.py tests/test_ask_cost.py tests/test_ask_route.py tests/test_ask_stream.py`
- The Verify command from `AGENTS.md`.
- No real Ask or Claude call, and no paid eval run.

## Findings

### ask-spend-reservation/F-26 [P2] closed - Ask's daily spend cap is checked before and recorded after, so concurrent questions overshoot it

**File:** api/app/routers/ask.py:34; api/app/services/ask/answer_stream.py:121
**Found:** 2026-11-06 by /audit (scope: full; lens: security)
**Why it matters:** `spend.exhausted()` runs at admission and cost is added in the stream's `finally`, so every question in flight passes the check. With prizepicks-rerun-snapshots/F-19, concurrency is unbounded per client. Overshoot is bounded by the Console monthly limit; the per-question worst case (about $0.01) is an estimate.
**Suggested fix:** reserve a worst-case cost at admission and settle on completion, or cap concurrent streams with a semaphore.
**Resolution:** Fixed on `claude/fix-f26-ask-spend-cap-ae1ff5`: `DailySpend.reserve` holds a worst-case cost per admitted question (`max_question_cost_usd`, about $0.021 at defaults) and refuses when spend plus holds would pass the cap; `ask_frames` settles the hold to the real cost before any await in its `finally`, and `ReservedStreamingResponse` closes the body and releases what it did not settle. Chosen over a semaphore, which would not tie admission to the money left. Closed 2026-11-06 by /audit (scope: current; all lenses): re-reviewed `guardrails.py`, `answer_stream.py`, `routers/ask.py`, `client.py` and `ask_cost.py`. Admission now counts spend plus holds with no await between check and hold; every exit path (finish, error, disconnect mid-stream, disconnect before the body starts, 429, missing key) settles or releases exactly once, each covered by a no-network test. Residual: a question whose input passes the 20,000-token assumption can overshoot by that excess; see F-39 in the live ledger for a cap set below one hold.

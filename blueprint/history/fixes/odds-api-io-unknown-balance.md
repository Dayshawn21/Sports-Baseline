# Fix: One Odds-API.io quota rule, and an unknown balance stops every script

**Type:** Fix
**Fixes:** F-55
**Branch:** `fix/odds-api-io-unknown-balance`

**Completed:** 2026-11-18. Re-reviewed by an independent reviewer (confirmed: every odds request in the three scripts is behind the shared gate, floor arithmetic unchanged except as listed, tests fail on the old tennis gate); finding set `closed`; left for the user to merge.

### The problem

Tennis (`ingest/odds_api.py`), NFL (`ingest/nfl_odds_io.py`) and NHL
(`ingest/nhl_odds_io.py`) spend one Odds-API.io allowance of 100 requests an
hour (45a, 48b), but each parsed `x-ratelimit-remaining` and gated requests on
its own:

| Script | Unknown balance | Header outside 0-100 | Floor |
|---|---|---|---|
| Tennis `_quota_too_low` | **keeps spending** | taken as read | `remaining > max(0, floor)` |
| NFL `can_request` | stops | taken as read | `remaining - 1 >= floor` |
| NHL `can_request` | stops | unknown, stops | `remaining - 1 >= floor` |

So a tennis run with a missing or garbled header could spend the hour NFL and
NHL were holding back for.

### The decision (option A)

Unknown means stop, for all three, through one pure helper,
`api/app/core/odds_api_io_quota.py`:

- `remaining_requests(headers) -> int | None`: the header as an integer, or
  `None` when it is missing, malformed, or outside `0..HOURLY_ALLOWANCE`.
- `can_request(balance, floor) -> bool`: `False` for `None`, otherwise
  `balance - 1 >= max(0, floor)` (one more request still leaves the floor).

**The 0-100 range, on purpose.** NHL's range is the plan allowance: a balance
above 100 cannot come from the plan the three scripts share, so it means the
plan or the header changed. It is now the named `HOURLY_ALLOWANCE = 100`, and
an out-of-range value reads as unknown and stops every script until someone
updates the constant deliberately. Negative values are unknown too.

### Behaviour changes

- **Tennis (visible):** a run whose balance header is missing, unreadable or
  outside 0-100 now sends no odds batch and logs `Stopping odds batch fetch:
  Odds-API.io request balance unknown (x-ratelimit-remaining missing or
  unreadable).` It previously kept spending. The market inventory writes the
  same reason into its report. The floor message wording changed to `Odds-API.io
  quota at the floor: N request(s) remaining, floor F`. Live risk is low: NFL
  and NHL already stop on an unknown balance and store odds on their schedules,
  so `/events` and `/odds/multi` do send the header.
- **NFL:** a header above 100 now stops the run (was taken as read), and a
  negative `--min-requests-remaining` counts as 0, so a balance of 0 never
  requests. The stop log says `unknown` instead of `None`.
- **NHL:** none (its floor is already validated to 0-99).

### Build steps

- [x] **Step 1 - shared helper.** `app/core/odds_api_io_quota.py`, with
  `tests/test_odds_api_io_quota.py`: missing, malformed, out-of-range, the
  allowance edges, at/below/above the floor, unknown, a negative floor.
- [x] **Step 2 - all three scripts use it.** Tennis `_rate_limit_state` reads
  `remaining` through the helper, and `_quota_stop_reason` replaces
  `_quota_too_low` at both gates (batch loop and inventory). NFL and NHL drop
  their own `_remaining` and `can_request`. Tests: tennis unknown balance sends
  no batch and logs why, an unreadable header after a batch stops the next,
  out-of-range reads as unknown, inventory with an unknown balance sends no odds
  request; existing fakes that sent no header now send a known balance.
- [x] **Step 3 - docs.** `docs/commands.md` and `docs/tennis-actions.md` name
  the unknown-balance stop.

### Evidence

- Focused: `test_odds_api_io_quota`, `test_odds_api_quota`,
  `test_odds_market_inventory`, `test_nfl_odds_io_ingest`,
  `test_nhl_odds_io_ingest`: 98 passed. The new tennis unknown-balance tests
  fail on the old `_quota_too_low`.
- Verify: web verify passed (1,861 tests, build clean); API `pytest` 6,572 passed.
- No real ingest was run; every test mocks headers.

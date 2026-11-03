# Stop tennis ingest retries when the daily quota is exhausted

**Type:** Fix

**Completed:** 2026-10-21. Implementation approved by the user's `$complete` request.

## The problem

`api/app/ingest/livetennis.py` retries every HTTP 429, including a response
explicitly saying the BASIC daily allowance is spent. After three attempts,
the H2H loop swallows the failure and starts the same retry sequence for the
next pairing. The daily batch can spend minutes per pairing on requests that
cannot succeed until the provider resets the quota. Its warning also cites
free-tier limits even when the response identifies BASIC.

## The fix

Recognize an explicitly exhausted daily allowance before sleeping or retrying.
Keep exhaustion state for the whole ingest run so later pairings and date
windows make no more quota-consuming provider requests. Finish saving match
records already fetched, including records after the affected H2H pairing;
do not abort their transaction. Log one clear quota-exhaustion warning with
the provider's reset information when available. Report the run as incomplete
when quota prevents fetching the requested window. Preserve bounded retries
for temporary rate limits and transient network/server errors, and preserve
existing tier-blocked behavior. Remove misleading free-tier numbers from the
generic 429 warning. No plan upgrade, quota increase, or live paid API calls.

## Build steps

- [x] Implement daily-quota handling and run-wide request suppression, with
  mocked regression tests. **Done when:** an explicit daily-quota 429 causes
  no retry sleep or further paid requests in that run; already-fetched matches
  still save; later windows do not restart requests; temporary 429s still
  retry and can succeed; malformed/unrecognized responses retain bounded
  handling; the log gives an accurate reason for stopping.

## Verify

- Use mocked HTTP responses and database writes to cover exhaustion during
  match fetching and H2H enrichment, persistence of remaining fetched records,
  multiple windows, temporary 429 recovery, and existing 403 behavior.
- Run the focused livetennis tests, then the documented Verify gate using
  the API venv: web verify followed by the full API test suite.
- Do not rerun live ingest just to reproduce the spent quota.

## Implementation review

- Implemented on `fix/tennis-daily-quota`; approved for completion.
  No live provider call performed. Merge and push require separate approval.
- `LiveTennisClient` remembers explicit daily exhaustion across the run.
  Match pagination preserves earlier pages, remaining fetched matches commit,
  and the run logs an incomplete summary before skipping later windows.
  Incomplete history pagination cannot overwrite stored H2H totals.
- Added ten mocked regression cases in `api/tests/test_livetennis_quota.py`.
  Focused livetennis suite: 115 passed.
- Web gate: `npm.cmd --prefix web run verify` passed (644 tests, typecheck,
  production build). Used the Windows command shim because PowerShell blocks
  `npm.ps1`; esbuild required execution outside the filesystem sandbox.
- API gate: `.venv\Scripts\python.exe -m pytest` from `api/`: 3,465 passed.
- Existing ledger: F-09 (P3) and F-12 (P2) remain unverified and unchanged;
  no P0/P1 blockers. The employer guide needs no change for this small fix.
- Final invariants review: clean; changes are confined to ingest HTTP quota
  handling and its mocked tests. No model, query, UI, secret, or deployment
  changes. `git diff --check` passed.
- Manual try: stop the old batch with Ctrl+C, then restart the usual tennis
  batch. A daily-exhaustion response should log its reset detail once and an
  incomplete summary, with no 59/60-second retry sequence. While quota is
  exhausted, match/H2H enrichment remains incomplete until a later run.

# Correct NFL anytime-touchdown baselines

**Type:** Fix

**Fixes:** F-01

## The problem

`api/app/ingest/nflverse.py` stored a single `touchdowns` value that summed
passing, rushing, and receiving touchdowns. `ANYTIME_TOUCHDOWN` converts that
average into a probability, but a passer did not score the touchdowns they threw.
This inflated quarterback anytime-touchdown projections and any displayed edge.

## The fix

The NFLverse parser now persists player scoring touchdowns only. For the current
NFLverse fields, that is rushing plus receiving touchdowns. Passing production
remains available through the existing passing metrics and does not affect this
market.

No schema, API response, or UI change was required. The normal NFLverse ingest
refreshes existing rows with the corrected derived value.

## Build steps

### Step 1 - store scoring touchdowns for the anytime-TD baseline [x] DONE

Updated the NFLverse parser so its touchdown field excludes `passing_tds` and
includes only player scoring touchdowns. Replaced the test that expected passing
touchdowns in this value with focused parser coverage proving a passing-only
quarterback produces zero and a rushing or receiving scorer remains counted.

**Done when:** a quarterback with only passing touchdowns cannot increase an
anytime-touchdown probability, while rushing and receiving touchdowns still do.

## Verify

- Focused parser and projection tests: 52 passed.
- Full backend suite: 704 passed.
- Web build: passed.
- Web tests: 52 passed.
- Re-audit: F-01 closed with no regression found.

## Findings

### nfl-anytime-touchdown-baselines/F-01 [P1] closed - Passing touchdowns inflate anytime-touchdown projections

**File:** api/app/ingest/nflverse.py:103
**Found:** 2026-09-16 by /audit (scope: NFL area; lens: quality, security, performance, tests)
**Why it matters:** `_total_touchdowns` added `passing_tds` to rushing and receiving touchdowns, then `baseline_projection` turned that average into the probability shown for the `anytime_touchdown` prop. Passing touchdowns credit a quarterback with a throw, not a touchdown scored, so quarterback baselines and any comparable edge were materially overstated.
**Suggested fix:** Store scoring touchdowns separately from passing touchdowns, use that value for `ANYTIME_TOUCHDOWN`, and cover a passing-only quarterback.
**Resolution:** 2026-09-16 - Re-audited the repaired parser, its persistence path, and the anytime-touchdown projection consumer. Passing touchdowns no longer enter the signal; focused tests passed. No regression found.

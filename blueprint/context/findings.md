# Findings

> **Generated file.** The findings ledger: review findings raised by `/audit`
> against the work in progress, each with a durable ID, severity (P0-P3), and
> status. `/implement` marks repaired findings `fixed`, a later `/audit` pass
> moves them to `closed`, and `/complete` refuses to merge while any P0 or P1
> finding is `open` or `fixed`, then archives resolved findings with the work
> and resets this file.

### F-02 [P2] unverified - Usage adjustment skews receiving projections downward

**File:** api/app/core/nfl_projection.py:58
**Found:** 2026-09-17 by /audit (scope: current; lens: all) during 19h
**Why it matters:** On the 2026 week 2 slate the median adjustment across 1,830
adjusted receiving props is -1.05%, and 223 still sit at the cap. Players who
get props are mostly starters whose yards and catches per target beat the
position-wide rate, so pulling toward that rate may systematically favor unders
rather than correcting noise. `USAGE_EFFICIENCY_REGRESSION = 0.35` is reasoned,
not fitted.
**Suggested fix:** Validate before trusting usage-adjusted edges: compare
adjusted versus unadjusted projections against settled 2025 results, or compute
the position efficiency baseline from players with a minimum target volume.
Missing validation: a held-out backtest, which 19h scopes out.
**Resolution:**

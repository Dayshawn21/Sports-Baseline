# Fix: Rank stale-baseline NFL edges below current-season edges

**Type:** Fix
**Status:** complete (2026-09-17), squash-merged from `fix/rank-stale-nfl-edges`

## Outcome

Each game's lines now rank in three tiers (current-season edge, stale-baseline
edge, no edge) through the pure `slate_line_rank` helper, and the slate banner
reports current-season and stale edge counts separately.

Verified on 2026 week 2: no row breaks the tier order across 16 games and 2,749
lines; the banner reads `424 with an edge (0 current season, 424 stale)`. Every
edge on that slate is stale because 2026 baselines are still below the 4-game
minimum, so the ordering change has no visible effect until roughly week 5. Tier
order is proven by unit tests, not by live data. Checks: API tests 768 passed,
web tests 56 passed, web build passed.

## The problem

The NFL slate ranks each game's lines by absolute edge, whatever season the
baseline came from. Early in a season most baselines fall back to the previous
season (week 2 of 2026: 2,565 of 2,749 lines), so stale edges crowd the top of
every game and the banner's "with an edge" count mixes both kinds.

Example: Keon Coleman (BUF) receiving yards, a real PrizePicks standard
full-game line of 14.5. His 2025 average of 33.7 yards, times the +10% opponent
and +6% usage adjustments, gives 39.3 and a +24.8 edge that ranks first in
DET @ BUF. But in 2026 week 1 he caught 1 pass for 1 yard on 1 target. The 2026
sample is below the 4-game minimum, so the baseline ignores it, and the market
is pricing a role change the 2025 baseline cannot see.

Affected code:

- `api/app/routers/nfl.py` - `get_slate` sorts each game's lines by `abs(edge)`
  only.
- `web/src/pages/NflIntelligencePage.tsx` - the banner counts every non-null
  edge as one bucket.

## The fix

Keep stale edges visible, but rank and count them separately:

- Order each game's lines in three tiers: current-season edges first (largest
  absolute edge first), then edges flagged `stale_baseline_season` (largest
  first), then rows with no edge. Put the ordering in a small pure helper so it
  is unit-testable.
- In the banner, report current-season edges and stale edges as separate
  counts, for example `N with an edge (X current season, Y stale)`. Use the
  row's `stale_baseline_season` flag as the source of truth, as
  `summarizeBaselineMix` already does.

Must not change:

- projection, edge values, and edge gating (standard, full-game, minimum sample)
- quality flags and the stale-season banner
- the API response shape; ordering is the only backend change

Out of scope:

- withholding stale edges
- blending current-season games into the baseline (a model change for a later
  feature)

## Build steps

- [x] **Step 1 - Rank stale edges below current-season edges.** Extract the
  per-game sort into a pure helper used by `get_slate`, and add a helper in
  `web/src/utils/nflBaseline.ts` that splits priced lines into current and stale
  counts for the banner.
  *Done when:* a pytest proves a current-season edge of +2 ranks above a stale
  edge of +24.8, stale edges rank above rows with no edge, and ties within a
  tier keep largest absolute edge first. A Vitest test proves the banner counts
  split current and stale edges by the flag. API tests, web tests, and the web
  build pass.

## Verify

- `pytest` from `api/`, `npm run test` and `npm run build` from `web/`.
- Open `/nfl` for 2026, week 2. The banner shows current and stale edge counts
  that add up to the total.

> Verified on 2026 week 2: no row breaks the tier order across 16 games and
> 2,749 lines, and the banner reads `424 with an edge (0 current season, 424
> stale)`. Every edge on the slate is stale today, because 2026 baselines are
> still below the 4-game minimum, so the ordering change has no visible effect
> until roughly week 5. Tier order is proven by unit tests, not by live data.

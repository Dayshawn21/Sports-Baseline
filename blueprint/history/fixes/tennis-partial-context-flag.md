# Partial context chip only for missing recent form

**Type:** Fix
**Completed:** 2026-10-01
**Branch:** `fix/partial-context-chip`

## The problem

The tennis "Partial context" chip showed on every match, so it carried no
information. `getDisplayFlags` in `web/src/components/tennis/qualityFlags.ts`
collapsed three backend flags into it:

- `ctx_last90_missing` - either player has fewer than 3 matches in 90 days
- `ctx_top20_missing` - either player has fewer than 3 matches vs top-20 opponents in 52 weeks
- `ctx_top50_missing` - same, vs top-50

Two causes, found in that order:

1. **Display.** The top-20 and top-50 splits are missing for almost any player
   outside the top 50, so the merged chip fired whenever either player was lower
   ranked.
2. **Backend (the real cause).** All three flags fired on all 74 matches,
   Sabalenka included, because `get_contextual_rolling_stats_batch`
   (`app/repositories/players.py`) failed on every call. With `surface` None,
   `(:surf IS NULL OR surface = :surf)` raised psycopg `AmbiguousParameter`, and
   `_missing_split_columns` swallowed it because it searched `str(exc)`, which
   embeds the SQL and so always contains `split_type`. The loader returned `{}`
   and every context split read as missing.

None of the three flags affects picks, tiers, EV or bettability
(`app/core/bettable_criteria.py` does not list them), and the served v6
LightGBM models do not read these features (only v5 lists them), so no
probability changed.

## The fix

- `getDisplayFlags` shows `partial_context` only when `ctx_last90_missing` is
  present; `ctx_top20_missing` and `ctx_top50_missing` are never displayed (no
  chip, no raw flag, no "+N" count). Other flags pass through in order. Callers
  (`tennisSlate.ts`, `UnifiedMatchCard.tsx`, `TennisCommandCenter.tsx`,
  `MatchComponents.tsx`) were unchanged.
- The batch query casts `:surf` to text.
- `_missing_split_columns` now matches only SQLSTATE `42703` (undefined column)
  whose driver primary message names `split_type` or `split_value`. It guards
  five other queries in the same file, which now raise genuine SQL errors
  instead of silently returning nothing.

## Build steps

- [x] **Step 1 - narrow the chip.** `getDisplayFlags` plus
  `web/src/components/tennis/qualityFlags.test.ts` (last90 alone -> chip;
  top20/top50 alone -> none; all three -> one chip; other flags kept in order).
- [x] **Step 2 - load the context splits.** The cast and the stricter
  `_missing_split_columns`, plus
  `api/tests/test_players_repository_split_columns.py` (real split-column error
  swallowed; `AmbiguousParameter` and other undefined columns are not).

## Evidence

- `npm run test`: 446 passed. `npm run build`: passed.
- `pytest`: 2,109 passed.
- Loader for Sabalenka (player 2011): `last90d` returned `{}` before, 13 matches after.
- `/tennis/predictions/today`, 74 matches:

| Flag | Before | After |
|---|---|---|
| `ctx_last90_missing` (shown) | 74 | 3 |
| `ctx_top20_missing` (hidden) | 74 | 66 |
| `ctx_top50_missing` (hidden) | 74 | 65 |

## Follow-up

Sabalenka has no `last_52w` / `opp_rank` / `top20` row at all, which is
implausible, and 66 of 74 matches still lack a top-20 split. The opponent-rank
parsing in `app/ingest/player_stats.py` (`_opp_rank`, `I_ORANK`) is the likely
cause. Hidden by this fix; worth its own `/fix`.

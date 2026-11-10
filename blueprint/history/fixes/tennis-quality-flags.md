# Current Feature

## Tennis quality-flag cleanup

**Type:** Fix
**Fixes:** F-43, F-44, F-45, F-46, F-47
**Branch:** `fix/tennis-quality-flags`

## The problem

The 2026-11-10 tennis flag audit (`blueprint/context/findings.md`) found four P3 issues. None of them changes a live probability or pick today:

| ID | Where | Problem |
|---|---|---|
| F-46 | `routers/props.py:413`, `services/tennis/prop_sim.py:106`, `core/tennis_prop_check.py:37`, `web/src/utils/tennisPropBoard.ts:57` | The PrizePicks prop blocking-flag list is copied by hand. The web copy blocks `market_stale` and `missing_projection`, which no tennis prop code emits, and leaves out `bo5_unsupported_stat`. |
| F-44 | `routers/admin.py:116`, `web/src/components/tennis/qualityFlags.ts:7` | `ml_features_partial` fires when either the 52-week or the surface rolling stats are missing, but the admin queue clears it for anyone who has a 52-week row. A player missing only surface stats never shows up. The hardcoded Shelton/Zhang clay label works around this one case by name. |
| F-45 | `services/tennis/ensemble.py:155`, `core/bettable_criteria.py:15` | `_market_anchored`'s docstring says overround lowers a pick's confidence, but `high_overround` is not in `_DOWNGRADE_FLAGS`. |
| F-43 | `services/tennis/predictor.py:189` and `:308`, `ensemble.py:94` | `elo_fallback="elo_missing" in feat_flags` is true only when `elo_prob` is already `None`, so `elo_fallback_used` and its 0.7 weight can never fire in served predictions. The two predictor paths also duplicate the `EnsembleInput` and flag assembly. |

## The fix

- **F-46:** add one `PRIZEPICKS_HARD_BLOCKS` frozenset to `app/core/prop_projection.py`, which both `routers/props.py` and `prop_sim.py` already import. `_enrich` and `prop_sim._sim_values` import it instead of their own copies. `EXCLUDED_FLAGS` keeps its own meaning (it also excludes `ungraded_stat` and omits `missing_stats`), but builds from the shared set plus its extras so the overlap can't drift. In the web, drop `market_stale` and `missing_projection` from `BLOCKING_FLAGS` and add `bo5_unsupported_stat`.
- **F-44:** the flagged-players route also fetches each flagged player's rolling stats for that match's surface (`get_rolling_stats_batch_all_surfaces`, which already exists). It keeps `ml_features_partial` when either the 52-week row or the surface row is missing. Pure logic moves into a small helper the test can call without a database. Then delete the Shelton/Zhang branch so `getQualityFlagLabel` returns the flag name.
- **F-45:** correct the docstring to say only stale odds lower confidence, keeping current tier behavior. Adding `high_overround` to `_DOWNGRADE_FLAGS` was considered and declined by the user on 2026-11-10.
- **F-43:** extract one helper in `predictor.py` that builds the `EnsembleInput` and the merged flag list, and call it from both `predict_match` and `_build_prediction`. Pass `elo_fallback=False` in served predictions, with a short comment saying no median ELO is served. `EnsembleInput.elo_fallback` and the hand-set multiplier stay, so the reproducible v2 blend (26c/26d) is untouched.

**Must not break:** `ENSEMBLE_VERSION` and served probabilities (F-43 and F-45 as defaulted change no output); the `hard_blocks` behavior for PrizePicks rows; `elo_comparison.py`'s flag handling; the existing `test_bettable_criteria.py` emit-name checks.

## Build steps

- [x] **Step 1 - Shared prop blocking flags (F-46).** Add `PRIZEPICKS_HARD_BLOCKS` and use it in `_enrich`, `prop_sim.py` and `EXCLUDED_FLAGS`. Fix the web `BLOCKING_FLAGS`. Tests: a pytest that `prop_sim` and `_enrich` use the same set and that every name in it is emitted by `routers/props.py`; a `tennisPropBoard.test.ts` case that a `bo5_unsupported_stat` line is not rateable.
  **Done when:** one Python definition of the hard-block set exists, the web set lists only names the API emits, and the new tests pass.
- [x] **Step 2 - Admin queue keeps surface-stat gaps (F-44).** Add the surface-stats lookup and the pure refinement helper, then remove the Shelton/Zhang special case. Tests: a pytest that the helper keeps `ml_features_partial` for a player with a 52-week row but no surface row, and drops it when both exist.
  **Done when:** a player missing only surface stats appears in `/admin/players/flagged`, and `qualityFlags.ts` contains no player names.
- [x] **Step 3 - Ensemble docstring and fallback wiring (F-45, F-43).** Correct the docstring, extract the shared predictor helper, and pass `elo_fallback=False`. Tests: a pytest that the helper emits `elo_missing` (not `elo_fallback_used`) when either player has no ELO, and that its flag list matches the old assembly for a fixed input.
  **Done when:** both predictor paths call one helper, no served path can set `elo_fallback=True`, and the docstring matches `_DOWNGRADE_FLAGS`.

- [x] **Step 4 - Repair F-47: show which surface is missing.** Add `missing_surfaces` to the flagged-player response, computed in `tennis_flag_queue.py` from the sets `refine_player_flags` already compares, and show it on the Admin page so a surface gap does not read as something Fix Stats can always fill. Tests: pytest cases for the helper.
  **Done when:** a player with a 52-week row but no row for a flagging match surface comes back with that surface named, and the Admin page says so next to the flag.

## Verify

- `npm --prefix web run verify && cd api && python -m pytest` passes (API venv active).
- With the local API running and an admin key, `GET /admin/players/flagged` lists a player who has 52-week stats but none on that match's surface, if today's slate has one. Otherwise the helper test is the evidence.
- The tennis slate and a tennis props page look the same as before (no probability or tier change).
- After `/implement`, run `/audit` on these files to move F-43 to F-46 from `fixed` to `closed`.

## Findings

**Scope:** path - every tennis quality flag from emitter to consumer: `feature_builder.py`, `ensemble.py`, `predictor.py`, `core/bettable_criteria.py`, `best_picks.py`, `routers/admin.py` (flag queue), `routers/props.py` (`_enrich` flags), `prop_sim.py`, `core/tennis_prop_check.py`, and the web `qualityFlags.ts`, `tennisSlate.ts`, `tennisMatch.ts`, `tennisPropBoard.ts`, `tennisPropCards.ts`, `TennisSlateTable.tsx`, `TennisPropTable.tsx`, `TennisMarketPanel.tsx`, `MatchComponents.tsx`. All four lenses, on `master` at `39ba0d70`.
**Signals:** 82 API tests (ensemble, bettable criteria, best-of props, best picks) and 147 web tests (five tennis flag test files) passed. No skipped or focused tests in those files.
**Ledger:** added tennis-quality-flags/F-43 to tennis-quality-flags/F-46.

### tennis-quality-flags/F-43 [P3] closed - The elo_fallback_used flag and its 0.7 ELO weight can never fire in served predictions

**File:** api/app/services/tennis/predictor.py:189; api/app/services/tennis/predictor.py:308; api/app/services/tennis/ensemble.py:94
**Found:** 2026-11-10 by /audit (scope: tennis quality flags; lenses: all)
**Why it matters:** both predictor paths pass `elo_fallback="elo_missing" in feat_flags`, but `feature_builder` emits `elo_missing` only when neither player has an ELO row, and then `elo_prob` is `None`, so the ensemble always takes its `elo_missing` branch first. `elo_fallback_used`, the hand-set 0.7 multiplier, and `elo_comparison.py:223`'s exclusion of it are dead in production; only `test_ensemble.py` reaches them by setting the input directly. The two predictor paths also duplicate this flag assembly line for line.
**Suggested fix:** decide what "fallback" was meant to mean. If nothing serves a median ELO any more, pass `elo_fallback=False` (or drop the input from the served call) and say so, keeping the field only for the reproducible v2 blend; otherwise wire it to the real fallback condition. Either way, have both predictor paths share one helper that builds the `EnsembleInput` and flag list.
**Resolution:** Repaired 2026-11-10 on `fix/tennis-quality-flags` step 3: `predictor._score` is the one place both predictor paths build the `EnsembleInput` and merged flags, and it passes `elo_fallback=False` (the v2 fallback weight stays for reproducibility). Covered by `tests/test_predictor_score.py`. Awaiting /audit. Closed 2026-11-10 by /audit (scope: current): `_score` is the only served `EnsembleInput` builder and passes `elo_fallback=False`; flag output is unchanged for every input (the old flag was only set when `elo_prob` was already `None`). `elo_comparison.py:223` still subtracts the now-dead name, harmless in frozen experiment code.

### tennis-quality-flags/F-44 [P3] closed - The admin stats queue drops a player missing only surface stats, and a hardcoded player-name label covers one case

**File:** api/app/routers/admin.py:116; web/src/components/tennis/qualityFlags.ts:7
**Found:** 2026-11-10 by /audit (scope: tennis quality flags; lenses: all)
**Why it matters:** `feature_builder` sets `ml_features_partial` when either the 52-week **or** the surface rolling stats are missing for either player. The flagged-players route removes the flag from any player who has a 52-week row, so a player missing only clay (or grass) stats never appears in the queue, and the match keeps the flag with no one to fix. `getQualityFlagLabel` works around exactly this for Ben Shelton vs Zhizhen Zhang on clay by name, which helps no other match and will go stale.
**Suggested fix:** in the admin route, also fetch the match surface's rolling stats and keep the flag when that row is missing (report which window is missing). Then delete the Shelton/Zhang special case so the label falls back to the flag name.
**Resolution:** Repaired 2026-11-10 on `fix/tennis-quality-flags` step 2: `app/core/tennis_flag_queue.refine_player_flags` keeps `ml_features_partial` unless the player has the all-surface row and a row for every flagging match surface; the route reads `get_rolling_stats_batch_all_surfaces`; the Shelton/Zhang label is deleted. Covered by `tests/test_tennis_flag_queue.py`; the live endpoint was not called. Awaiting /audit. Re-reviewed 2026-11-10 by /audit (scope: current): the original drop is gone, but the repair surfaces rows the admin cannot act on (tennis-quality-flags/F-47), so it stays `fixed` until tennis-quality-flags/F-47 is resolved or accepted. Closed 2026-11-10 by /audit (scope: current): the queue keeps the flag for an uncovered match surface, the name-specific label is gone, and match and stats surfaces share the canonical Hard, Clay and Grass values, so no false gaps appear. The follow-on gap was repaired as tennis-quality-flags/F-47.

### tennis-quality-flags/F-45 [P3] closed - The ensemble says overround lowers a pick's confidence, but high_overround is not a downgrade flag

**File:** api/app/services/tennis/ensemble.py:155; api/app/core/bettable_criteria.py:15
**Found:** 2026-11-10 by /audit (scope: tennis quality flags; lenses: all)
**Why it matters:** `_market_anchored`'s docstring says "Stale and overround flags still lower a pick's confidence". `stale_odds` is in `_DOWNGRADE_FLAGS`, `high_overround` is not, and no archived spec records dropping it. Since 26d moved the served probability off the overround penalty, the docstring is the only place the behavior is promised, so a reader (or Ask Lineform's tooling) gets the wrong rule. Low live impact while tennis moneyline picks are off.
**Suggested fix:** either add `high_overround` to `_DOWNGRADE_FLAGS` with a `test_bettable_criteria.py` case, or correct the docstring to say only stale odds downgrade. Pick deliberately; it changes which tier shows.
**Resolution:** Repaired 2026-11-10 on `fix/tennis-quality-flags` step 3: the `_market_anchored` docstring now says only stale odds lower confidence. Adding `high_overround` to `_DOWNGRADE_FLAGS` was declined by the user on 2026-11-10. Awaiting /audit. Closed 2026-11-10 by /audit (scope: current): docstring matches `_DOWNGRADE_FLAGS`; tier behavior unchanged.

### tennis-quality-flags/F-46 [P3] closed - The prop blocking-flag list is copied in four places and the web copy has drifted

**File:** web/src/utils/tennisPropBoard.ts:57; api/app/routers/props.py:413; api/app/services/tennis/prop_sim.py:106; api/app/core/tennis_prop_check.py:37
**Found:** 2026-11-10 by /audit (scope: tennis quality flags; lenses: all)
**Why it matters:** `_enrich`'s inline `hard_blocks`, `prop_sim._BLOCKING_FLAGS` (a hand copy, per its comment), `EXCLUDED_FLAGS` and the web `BLOCKING_FLAGS` each list overlapping flag names. The web set includes `market_stale` and `missing_projection`, which no tennis prop code emits, and omits `bo5_unsupported_stat`. That is harmless today only because every tennis prop is PrizePicks, so `_enrich` already nulls the recommendation. A new flag or a second source would have to be added in four places to behave consistently.
**Suggested fix:** export one `PRIZEPICKS_HARD_BLOCKS` frozenset from `routers/props.py`'s pure helper module (or `app/core`) and import it in `prop_sim.py`; drop the two dead names from the web set, add `bo5_unsupported_stat`, and add a pytest like `test_every_tier_flag_is_emitted_somewhere` that checks each listed name is emitted.
**Resolution:** Repaired 2026-11-10 on `fix/tennis-quality-flags` step 1: `PRIZEPICKS_HARD_BLOCKS` in `app/core/prop_projection.py` is imported by `_enrich`, `prop_sim.py` and `EXCLUDED_FLAGS` (unchanged set); the web list dropped `market_stale` and `missing_projection` and added `bo5_unsupported_stat`; `tests/test_prizepicks_hard_blocks.py` checks emit names. Awaiting /audit. Closed 2026-11-10 by /audit (scope: current): one Python definition; `EXCLUDED_FLAGS` is the same seven names; the web set lists only emitted names; the emit test guards drift.

### tennis-quality-flags/F-47 [P3] closed - The admin queue now lists surface-only gaps with a green Stats dot and a Fix Stats button that cannot fill them

**File:** api/app/routers/admin.py:133; web/src/pages/AdminPage.tsx:251; api/app/ingest/player_stats.py:577
**Found:** 2026-11-10 by /audit (scope: current; lenses: all)
**Why it matters:** after tennis-quality-flags/F-44's repair, a player with a 52-week row but no row for the match surface is listed with `has_stats=true` (green dot) beside an `ml_features_partial` chip, and nothing says which surface is missing. `_upsert_baseline_rows` writes a surface row only when that surface has 3 or more matches in 52 weeks, so for a player like Zhang on clay, Fix Stats re-fetches and the row stays. The queue gains entries that look fixable but are not.
**Suggested fix:** add `missing_surfaces: list[str]` to `FlaggedPlayer` (from the same surface sets `refine_player_flags` already compares) and show it on the Admin page, for example "No clay row (under 3 clay matches)", instead of implying Fix Stats will help.
**Resolution:** Repaired 2026-11-10 on `fix/tennis-quality-flags` step 4: `FlaggedPlayer.missing_surfaces` comes from `tennis_flag_queue.missing_surfaces`, and the Admin page shows `surfaceGapNote` under the flags on desktop and mobile. Covered by helper tests and a browser check with mocked API responses; the live endpoint was not called. Awaiting /audit. Closed 2026-11-10 by /audit (scope: current): the note and the flag derive from the same `missing_surfaces` helper, so they cannot disagree; a note appears only when a surface is actually uncovered. The real endpoint remains uncalled; the page was checked against mocked responses.

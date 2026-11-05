# Feature: NHL over-probability served

**From build-plan:** feature 56c3 (third of 56c's four parts; 56c1 served the projection, 56c2 froze the fit, 56c4 freezes predictions)
**Status:** complete (2026-11-05)
**Branch (for /implement):** `feature/nhl-over-probability-served` (exists on origin, no commits beyond `master` `fe29dc30`)

## Goal

Show P(over) beside the gray `nhl-reference-v1` projection on the NHL board, game page and player page, for the four markets that passed the 56c2 holdout check: Shots on Goal, Time On Ice, Goals Allowed, Faceoffs Won. The numbers come from the frozen, generated `app/core/nhl_over_probability_fit.py`; **no new fit, no new rule, no outcome read**. It stays gray reference with no pick wording, no edge, no ranking and no green or red; 56c4 freezes it and 56d grades it.

**Honest strength of what is shown.** Time On Ice and Goals Allowed only *tied* the constant-sigma normal baseline on the holdout (Brier 0.0698 vs 0.0698, 0.1909 vs 0.1909); Shots on Goal and Faceoffs Won beat it by 0.0031 and 0.0026. The page says so in plain words (see Design). Goalie Saves missed by 0.0002 and the seven development-hidden markets never touched the holdout, so all eight show nothing until a new version is pre-registered.

## Design reference

None needed. It adds one column and one sentence to three existing gray tables; no new layout. Existing 56c1 conventions hold (caption "not a pick", `nhlProjectionNote`, gray text).

## Sizing

Medium, one reviewable feature, no split: one pure core change, one schema and service change, one web utility change and one component change. No migration, no workflow, no new endpoint. Four build steps plus verify.

## In scope

- **Core (pure).** Extend `project_line` in `app/core/nhl_projection.py`: after 56c1's gate has produced a number, read P(over) from the generated fit. `NhlLineProjection` gains `p_over`, `p_under`, `over_probability_version` (all `None` by default). A `_fit_serves(market)` mirrors NBA's: the market is in `SHOWN_MARKETS` **and** `FIT_PROJECTION_MODEL_VERSION == NHL_PROJECTION_REFERENCE_VERSION`; a mismatch serves nothing. Parameters are built from the module (`FAMILY_BY_MARKET`, `NEGBIN_R`, `SCALED_NORMAL`, `RATIO_QUANTILES`) and read with 56c2's own `read_family`, imported not rewritten, so the served number cannot drift from what was scored.
- **Gate inheritance (load-bearing).** A probability exists only where `projection is not None`: a gated line (injured out, goalie not confirmed or expected, stale context, few games, low TOI, not a center) gets no probability, because the 56c2 cases exist only for players who played. `injury_listed` and `injury_context_stale` still show a number, so they show its probability too, under the same note.
- **Whole-number lines** read `None` for every family (`read_family` already does). Flag `integer_line` on a line whose projection is shown in a covered market. P(under) is `1 - p_over` on a non-integer line (no push is modelled), `None` otherwise.
- **Hidden markets** carry `p_over = p_under = over_probability_version = None` and **no flag** (8 of 12 markets would otherwise repeat a flag on every row). `no_over_probability` is kept for a covered market whose read returns `None` unexpectedly (for example a zero projection), so a missing number is never silent.
- **API.** Null-valued, never absent, on `NhlProjectionSchema`: `p_over` only (camelCase on the wire). P(under) is `1 - pOver` (no push is modelled) and the fit version is named once per response (`overProbabilityVersion` on the board, game-props and player responses), not on every line, because Step 2's measurement showed three per-line fields cost +9.8 KB gzipped against the 5 KB budget. `NhlProjectionFlag` gains `integer_line` and `no_over_probability` in Python and TypeScript. The core still carries `p_under` and `over_probability_version` per line for 56c4 to freeze. The web shows the P(over) column for a market group when some line has a `pOver` or an `integer_line` flag, so a hidden market shows nothing.
- **Player endpoint.** The projection is one per market with `gap`/`p_over`/`p_under` null (as 56c1 does with `gap`). Each `NhlPlayerLineSchema` rung gains `p_over`, `p_under`, `flags` (only `integer_line` or `no_over_probability`) because the probability depends on the line. The market-level projection keeps `over_probability_version` so the page can say which markets have a probability.
- **Web.** One P(over) column after Gap on the board and game page, for the **standard** rung only (alternates keep their gap, no probability); the player page's PrizePicks lines table gets a P(over) column per rung. The column renders for a market group only when some line in it has a non-null `overProbabilityVersion`; hidden markets look exactly as they do today. Text is a whole percent (`54%`), `<1%` and `>99%` at the ends, `--` when null. `integer_line` shows the note "Whole-number line: no P(over)" through `nhlProjectionNote`. Caption: "P(over): model estimate, not a pick" plus, where Time On Ice or Goals Allowed is shown, "no better than a plain average-based estimate on 2025-26".
- **Response size (F-14).** Measure, do not guess: Step 2 records raw and gzipped bytes of the stored 2026-10-24 board JSON (the F-14 baseline, 1,119 KB raw / 46 KB gzipped) before and after, in-process and read-only. **Budget: gzipped growth at most 5 KB and raw growth at most 20 percent.** If exceeded, move `over_probability_version` out of each line to the response level and re-measure; do not add caching in this feature (F-14 stays open and separate).
- **Tests** (gate is on): core, schema, service and web utility tests as listed in the steps.

## Out of scope

- Any new fit, family, market, threshold or version; a hidden market stays hidden until a new version is pre-registered. `nhl_over_probability_fit.py` is never edited by hand.
- Reading, scoring or fitting on 2025-26 or 2026-27 **outcomes**. Serving reads only the inputs 56c1 already reads (prior games before the board date); no step compares a served probability with a realized result. Grading is 56d.
- Edge, break-even, ranking, "best bets", sorting or filtering by probability, any green or red, any pick wording.
- `NhlPropSource`, `PROP_SOURCES`, freezing, `sport_prop_predictions`, `nhl-prop-lines.yml` (56c4); `/nhl/model` and the ranking check (56d).
- Push handling for whole-number lines (a separately pre-registered later item).
- Caching or de-duplicating the board payload (F-14). F-12 (NBA/NFL calibration by odds type) is not touched.
- Home page record card, injury or goalie logic changes.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

There is no pre-registration commit here (no new rule), so `/complete` follows the normal squash path. The cited commit `512fe51e` is already on `master` and is untouched.

## Build steps

- [x] **Step 1 - Core: P(over) in `project_line` (pure)** - extend `NhlLineProjection` and `project_line` as above, with `_fit_serves`, a params builder from the generated module, and the flags. *Done when* `tests/test_nhl_projection.py` (or a new `tests/test_nhl_projection_probability.py`) shows: a Shots on Goal line returns exactly `read_family(NegBinParams(NEGBIN_R[...]), projection, line)` and a Time On Ice line the scaled-normal read; `p_over + p_under == 1` and `p_over` falls as the line rises across x.5 rungs; a whole-number line gives `p_over is None`, `over_probability_version` set and flag `integer_line`; a hidden market (Goalie Saves, Hits, Points) gives all three `None` and no new flag; a gated line (goalie `starter_unconfirmed`, skater `injured_out`, `few_prior_games`) gives `projection is None` and no probability; a monkeypatched `FIT_PROJECTION_MODEL_VERSION` mismatch gives no probability anywhere; an unknown family or missing params gives `no_over_probability`; a zero or negative projection does not raise; 56c1's existing projection tests pass unchanged.
- [x] **Step 2 - API: schema, board/game/player wiring, size check** - add the null-valued fields and flags to `NhlProjectionSchema`, `NhlPlayerLineSchema`; `line_projection` copies the core result; the player `_market` computes each rung's probability from the market's one projection value (a small pure helper in core so the board, game and player paths share one reading, not three). *Done when* service tests cover: board and game lines carry the fields (JSON keys present, null when none); the player endpoint's market projection has `pOver`/`pUnder` null and each rung has its own, falling with the line; a hidden market's lines are all null with no flag; a stored-board in-process measurement is pasted under Results and meets the budget; one served line is checked by hand outside the service from the generated module's constants. No endpoint reads any outcome.
- [x] **Step 3 - Web: types and pure helpers** - `NhlProjection`, `NhlPlayerLine` and `NhlProjectionFlag` types; `nhlPercentLabel` (whole percent, `<1%`, `>99%`, `--`), flag text for `integer_line` and `no_over_probability`, a helper deciding whether a group shows the column, and the rung/row builders in `nhlLineOnly.ts` / `nhlPropBoard.ts` carrying `pOver`. *Done when* Vitest covers: percent rounding and both clamps and null; the column helper true only when a line has a non-null version; the standard rung's probability reaches the row and an alternate's does not; `integer_line` note text; existing NHL web tests pass.
- [x] **Step 4 - Web: board, game page and player page** - the P(over) column and caption sentence in `NhlPropBoardMarket.tsx`, `NhlGameProps.tsx`, `NhlPlayerMarketSection.tsx`; update the player section's "No probability or pick" doc comment. *Done when* in the running app (API against the stored 2026-10-24 board, web dev server) a Shots on Goal row shows a percent beside Proj and Gap, a Goalie Saves or Hits row shows no column, an unconfirmed-goalie Goals Allowed row shows `--` with the 56c1 note, and the player page's rung table shows a percent per rung; no green, red or pick wording appears; screenshots of the board, game and player page and a clean console.
- [x] **Step 5 - Verify, guide and archive handoff** - run `npm --prefix web run verify && cd api && python -m pytest`; update the local, untracked `docs/SportApp-Employer-Interview-Guide.md` if present (P(over) now visible, gray, four markets, two only tie the baseline, still not graded, frozen or deployed). *Done when* the Verify command passes and the summary names the guide update or that the file is absent.

## Files / areas

- Edit: `api/app/core/nhl_projection.py`, `api/app/schemas/nhl.py`, `api/app/services/nhl/projections.py`, `api/app/services/nhl/player_props.py`, `web/src/types/nhl.ts`, `web/src/utils/nhlProjection.ts`, `web/src/utils/nhlLineOnly.ts`, `web/src/utils/nhlPropBoard.ts`, `web/src/components/nhl/NhlPropBoardMarket.tsx`, `NhlGameProps.tsx`, `NhlPlayerMarketSection.tsx`
- Tests: `api/tests/test_nhl_projection.py` (or a new `test_nhl_projection_probability.py`), `test_nhl_line_projections.py`, `test_nhl_player_props.py`, `test_nhl_display_schemas.py`, `web/src/utils/nhlProjection.test.ts`, `nhlLineOnly.test.ts`, `nhlPropBoard.test.ts`
- Read only: `api/app/core/nhl_over_probability_fit.py` (generated), `nhl_over_probability_crossfit.py` (`read_family`), `count_over_probability.py`, `nba_projection.py` (pattern), `blueprint/history/features/20g2-nba-game-projection.md`, `56c1-nhl-projection-served.md`, `56c2-nhl-over-probability-fit.md`

## Data / contracts

**Load-bearing for 56c4 and 56d** (freeze and grade read the same core function, so these shapes are locked now):

- `NhlLineProjection(model_version, projection, games_in_sample, prior_toi_minutes, gap, p_over, p_under, over_probability_version, flags)`; `p_over` is `None` unless a number is shown, the market is in `SHOWN_MARKETS`, the fit's projection version equals the served one, and the line is not a whole number.
- Wire keys (camelCase, always present): `pOver` on the projection; `pOver`, `pUnder`, `flags` on each player rung; `overProbabilityVersion` on the board, game-props and player responses (null when the fit does not match the served projection).
- Flags added: `integer_line`, `no_over_probability`. A hidden market gets neither.
- `over_probability_version` equals `OVER_PROBABILITY_VERSION` (`nhl-pover-v1`) whenever set.
- Probabilities are rounded to 4 decimals at the schema boundary (player rungs: `p_under = round(1 - p_over, 4)`); the core keeps full precision (56c4 freezes the core value).

## Testing

Test gate on. Pure logic gets tests in Steps 1 to 3; Step 4 rides on browser and build evidence per `coding-standards.md`. API tests need `DATABASE_URL=postgresql://localhost/ci` and the main checkout's venv `C:/dev/SportAppV2/api/.venv/Scripts/python.exe`; web needs `npm ci` in a fresh worktree. Never print the database URL.

**What the tests cannot show, stated up front (F-12).** F-12 found the NFL P(over) running below observed over rates, most on goblin lines. The NHL fit was calibrated on synthetic x.5 lines around each projection, not on PrizePicks standard/demon/goblin lines, and no posted-line outcome may be read here. So tests assert structure (exact agreement with `read_family`, monotone in the line, sums to 1, bounded, gated and hidden cases empty) and **not** calibration by odds type. That check belongs to 56d's forward ranking read, and the board therefore shows a probability on the standard rung only; the player page does show every rung but under the caption.

## Notes for the AI

- **Holdout discipline.** No read, score or fit on 2025-26 or 2026-27 outcomes. Do not run any backtest or `--confirm` CLI. Tests use small fixtures; the size measurement and browser check use stored lines and prior-game inputs only, as 56c1's did.
- `core/` stays pure; the generated module is imported, never edited. Routers stay thin; no SQL outside repositories.
- Gray everywhere: no color tokens beyond what the existing NHL tables use, no "pick", "edge", "value", "best", "lock", or ranking words, no sorting by probability.
- Keep 56c1's caption, `nhlProjectionNote` and gating untouched; this feature adds, it does not change what 56c1 shows.
- No em dashes. Ask before committing; no AI attribution beyond the repo's commit attribution lines.

## Decisions for the owner

1. **Probability on alternates.** Recommended: board and game page show it for the standard rung only; the player page shows every rung. Alternative: standard rung only everywhere (safer under F-12, less to read on the player page).
2. **Weak markets.** Recommended: show Time On Ice and Goals Allowed with the "ties a plain estimate" sentence. Alternative: hide them in the UI only (the fit module still lists them), which needs a separately written reason because the pre-registered rule says they show.
3. **Whole-number Goals Allowed lines.** They show `--` with the note until a push model is pre-registered; that may blank most of the standard Goals Allowed rows. Accepted as the cost of not guessing at pushes.

## Red-team record (this draft)

- Coverage added: version-mismatch refusal, unknown family or missing params, zero projection, gated cases, hidden-market quietness, integer lines.
- Size: web work split into helpers (Step 3) and components (Step 4) so the visual diff reads alone.
- Contracts: freeze/grade shapes locked above and flagged load-bearing.
- Scope: edge, ranking, caching and any posted-line calibration cut to 56d, 56c4 and F-14.

## Results

- **Step 1:** core `over_read` and `project_line`; full API suite 5736 passed.
- **Step 2, size check** (in-process, read-only, stored 2026-10-24 board, 3,416 lines, 826 with a probability): as first specced (`pOver`, `pUnder`, version on every line) raw +18.4% and gzip +9.8 KB (46,057 to 55,873), over the 5 KB budget; version moved out only: +8.5% / +7.1 KB. Owner chose to drop `pUnder` from board and game lines and name the version once per response: raw +4.1% (1,120,849 to 1,166,862), gzip +3.8 KB (46,057 to 49,833), within budget. Hand check: Shots on Goal, projection 1.45, line 2.5 -> negative binomial (r 13.719) P(X>=3) = 0.1851, equal to the served `pOver`. Full API suite 5744 passed.
- **Steps 3 to 5:** web types and helpers, components (checked in the running app against the stored 2026-10-24 board: Shots on Goal, Time On Ice, Goals Allowed and Faceoffs Won show a gray P(over) column, Goalie Saves and Hits show none, a whole-number Faceoffs Won line shows `--` with its note, the player page shows a percent per rung, console clean). Verify: `npm --prefix web run verify` (1233 web tests, build clean) and API pytest 5744 passed. The local, untracked interview guide was updated (P(over) shown gray for four markets, two only tie the baseline, not graded, frozen or deployed).

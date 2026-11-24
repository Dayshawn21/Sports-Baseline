# Feature: NHL reference projection served

**From build-plan:** feature 56c1 (first of 56c's four parts; 56c2 fit, 56c3 P(over) served, 56c4 frozen predictions)
**Status:** complete (2026-11-04)
**Branch (for /implement):** `feature/nhl-projection-served`

## Goal

Show the pre-registered `nhl-reference-v1` projection (the mean of a player's last 20 prior played games in a market, defined in `app/core/nhl_projection_backtest.py` and pre-registered in commit `237c2bcc`) and its gap to the line (projection minus line) beside each stored PrizePicks line on `/nhl/board`, the game page and the player page. Everything is gray reference, never a pick.

**Why:** 56a shows lines only. 56c4 must freeze exactly what the page served, so the served projection comes first, as NBA's 20g2 did before 20g3. Nothing is frozen or graded here.

**The new problem NHL has:** who dresses or starts is known only after the game, and the backtest scores only players who did play. A served number must therefore be gated on what is knowable before puck drop, using the stored ESPN injury and probable-goalie snapshots (45f, display only until now). A goalie line shows a number only for a confirmed or expected starter.

## Design reference

None to capture. Reuse the existing gray reference styling of the NHL board and player page (`web/src/components/nhl/`); add two plain columns, no new visual language.

## In scope

- **Pure projection module `app/core/nhl_projection.py`:** `project_line(prior, market, line, availability) -> NhlLineProjection`. Value is `window_mean(REFERENCE_GAMES)` from 56b's `ARMS["reference"]` (imported, not re-implemented, so the served number cannot drift from what was backtested). Eligibility is 56b's: skaters need `MIN_PRIOR_GAMES` prior games and `MIN_PRIOR_TOI_MINUTES` mean TOI over the last `TOI_WINDOW`; goalies need `MIN_PRIOR_GOALIE_STARTS` prior starts, counting starts only. Faceoffs Won only for position `C`.
- **Availability gate (pure, same module), decided here:**
  - *Goalie lines* (Goalie Saves, Goals Allowed): a number only when the game's goalie context for the player's team has status `confirmed` or `expected`, that goalie's `player_id` is the line's player, and the goalie report's freshness is `fresh`. Otherwise value is null with one flag: `no_goalie_report` (unavailable or not reported), `starter_unconfirmed` (unknown status), `other_starter_expected` (a different goalie is listed), or `context_stale`.
  - *Skater lines:* served unless the player has an entry in the game's stored injury snapshot whose status is out-type (Out, Injured Reserve and their ESPN spellings), then null with `injured_out`. Any other listed status is served with the flag `injury_listed`. A stale injury snapshot still serves the number, with the flag `injury_context_stale`; a missing snapshot serves it with no flag. Absence of an entry is not evidence that a player will play, so the skater gate only ever removes a number for an explicit out-type entry. The exact ESPN status vocabulary is read from stored rows in Step 2 and pinned as a constant with a test before the gate is trusted.
  - Ineligible history gives null with `few_prior_games` or `low_toi`; Faceoffs Won for a non-center gives null with `not_center`.
- **Repository read** `get_prior_history(db, player_ids, before)` in `app/repositories/nhl.py`: the last 20 served-type (`REG`, `PST`) played rows per player strictly before the date, from season `NHL_FIRST_HISTORY_SEASON` (a named lower bound, per the history-floor rule), skater rows as stored and goalie rows only where `started`. Returns `NhlHistoryRow` so 56b's types are reused.
- **Wire into the three line-only endpoints** (board `GET /nhl/props`, the game props endpoint, the player props endpoint): each line carries `projection: {modelVersion, value, gamesInSample, flags, gap}`; the board and game builders load the date's contexts through the existing context service.
- **Web:** Proj and Gap columns on the board market table and the game props table, a per-market "20-game average" projection and per-rung gap on the player page, flags shown as short gray reason text where the value is null ("Starter not confirmed", "Injured: out", "Fewer than 10 games"), a one-line caption "Reference projection: 20-game average, not a pick".

## Out of scope

- P(over), probabilities, edges, any ranking or "best" ordering (56c2, 56c3). The board stays ordered by puck drop then player.
- Freezing, `NhlPropSource`'s full protocol, `PROP_SOURCES`, workflows, `sport_prop_predictions` writes (56c4).
- Any read of 2025-26 outcomes: this feature compares no projection to any actual. 2025-26 rows may appear only as prior-game inputs to a live projection, which has no fitted parameter. The holdout stays unread until 56c2.
- A shorter window or other arm for Time On Ice, Faceoffs Won or Power Play Points (the 56b development read hinted at it; a later pre-registered candidate).
- Changes to ingest, models, migrations, ESPN context fetching or `docs/commands.md`.
- Home page cards (56d).

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Projection arithmetic (pure)** - `app/core/nhl_projection.py` with `NhlLineProjection` (model version, value or None, games in sample, prior TOI minutes, gap, flags), the flag type, and `project_line` with eligibility only (availability passed as "assume available" for now). *Done when:* unit tests show (a) the value equals `ARMS["reference"]` on the same prior rows for every market, skater and goalie, including a NULL stat game skipped; (b) 9 vs 10 prior games and 11.99 vs 12.0 TOI minutes flip eligibility; (c) a goalie counts starts only (4 vs 5); (d) Faceoffs Won returns `not_center` for position W and D and None; (e) gap is `round(value - line, 2)` and None when value is None; (f) the version equals `NHL_PROJECTION_REFERENCE_VERSION`.
- [x] **Step 2 - Availability gate (pure)** - First a read-only query of the distinct stored injury `status` strings (no write, no migration), recorded under Results. Then the gate in the same module: goalie rules and skater rules above, taking the existing `NhlGameContextSchema` fields (not the schema itself, to keep `core/` free of schema imports; a small dataclass carries status, freshness, goalie player id, injury status). *Done when:* tests cover every goalie branch (confirmed, expected, unknown, not_reported, unavailable, stale, other goalie listed, no context), every skater branch (no entry, out, each non-out status found, stale snapshot), a constants test pinning the out-type status set to the stored vocabulary, and that a null-gated line still reports `games_in_sample`.
- [x] **Step 3 - Prior-history read** - `get_prior_history` and `NHL_FIRST_HISTORY_SEASON` reuse; a read-only run for a handful of stored players on 2026-10-24 compares the value `project_line` gives to a hand SQL mean over the same rows. *Done when:* three players (a high-TOI skater, a center for Faceoffs Won, a goalie) match the SQL mean exactly; the query's row count per player is at most 20; the SQL has the explicit season floor; measured time for a full board date is noted (target well under a second).
- [x] **Step 4 - Board and game endpoints** - `NhlProjectionSchema` and `projection` on `NhlLineOnlyLineSchema`; pure builders attach projections; the board and game props services load prior history in one batched call per request and contexts through `load_contexts`. A failed or empty context read degrades to `no_goalie_report` for goalies and ungated skaters, never a 500 for a board that rendered before. *Done when:* builder tests with fixed rows (no DB) check one skater line, one confirmed goalie, one unconfirmed goalie, one ineligible player; existing 56a tests still pass; a `curl` of `/nhl/props?date=2026-10-24` shows values, gaps and flags with the expected gating on a real goalie line; `pytest` passes.
- [x] **Step 5 - Player endpoint** - market-level `projection` on `NhlPlayerMarketSchema` and a `gap` on each `NhlPlayerLineSchema` rung, from the same `project_line` and the context `build_player_props` already assembles. *Done when:* a builder test checks a market with two rungs (standard and demon) giving one value and two gaps; `curl` for a skater and a goalie on 2026-10-24 matches the board's value for the same line; `pytest` passes.
- [x] **Step 6 - Web types and formatting helpers** - `web/src/types/nhl.ts` additions and a pure `web/src/utils/nhlProjection.ts` (format value to one decimal, signed gap, flag to reason text, never a pick word). *Done when:* Vitest tests cover each flag's text, a null value, a negative and a zero gap, and that no output string contains "pick", "bet", "edge" or "value"; `npm run test` passes.
- [x] **Step 7 - Pages** - Proj and Gap in `NhlPropBoardMarket.tsx`, the game props table (`NhlGameProps.tsx`) and the player market section, with the caption; null-value rows show the reason text in gray. *Done when:* in the browser, `/nhl/board?date=2026-10-24` shows the columns for Shots on Goal and Goalie Saves, a goalie row without a confirmed or expected starter shows the reason and no number, a game page and a player page show the same value as the board for the same line, the page is gray with no green or red edge colouring, phone and desktop widths have no horizontal page scroll, and `npm run build` passes.
- [x] **Step 8 - Verify and interview guide** - Run the Verify command; update `docs/SportApp-Employer-Interview-Guide.md` if present (served-but-gated reference projection; planned vs implemented kept distinct, nothing frozen or graded yet). *Done when:* `npm --prefix web run verify && cd api && python -m pytest` passes and the summary names the guide update or that the file is absent.

## Files / areas

- New: `api/app/core/nhl_projection.py`, `api/tests/test_nhl_projection.py`, `web/src/utils/nhlProjection.ts`, `web/src/utils/nhlProjection.test.ts`
- Changed: `api/app/repositories/nhl.py`, `api/app/schemas/nhl.py`, `api/app/services/nhl/{prop_board,line_only_props,player_props,game_detail or its props path}.py`, `api/app/routers/nhl.py` (only if a dependency changes), `web/src/types/nhl.ts`, `web/src/components/nhl/{NhlPropBoardMarket,NhlGameProps,NhlPlayerMarketSection}.tsx`, `web/src/utils/nhlLineOnly.ts` if a row type grows
- Read only: `api/app/core/nhl_projection_backtest.py` (imported, never edited, so 56b's pre-registered rule stays untouched), `api/app/core/nhl_player_values.py`, `api/app/services/nhl/context.py`, `docs/nhl-context.md`

## Data / contracts

No migration, no new table, no new endpoint.

**Load-bearing for 56c2 to 56c4:**
- `NhlLineProjection` and its flag vocabulary: 56c3 adds P(over) fields to it; 56c4 freezes exactly this object (flags and gate inputs go into `feature_snapshot`).
- The gate rules above are the only gate: freezing must call the same function, never a copy.
- `NHL_PROJECTION_REFERENCE_VERSION = "nhl-reference-v1"` is both served and frozen; it changes only if the arm or eligibility changes.
- `projection` sits on every line-only line and market, null-valued rather than absent, so the web never infers "no projection" from a missing key.

## Testing

Test gate on. Pure logic gets tests in the same diff: Steps 1, 2, 4 (builders) and 5 are tested; Steps 3 and 6 ride on read-only SQL comparison, `curl`, browser and build evidence. API tests need `DATABASE_URL=postgresql://localhost/ci` and the main checkout's venv `C:/dev/SportAppV2/api/.venv/Scripts/python.exe`; web needs `npm ci` in `web/` first (never print the database URL).

## Notes for the AI

- `core/` stays pure: no DB, no I/O, no schema imports. Routers thin, SQL only in the repository.
- Import 56b's `ARMS` and constants; do not copy them. A change to NBA or NFL constants must never move NHL's.
- A goalie's history is starts only, matching 56b's replay and how the market settles.
- Prior games are strictly before the game's Eastern date; a same-day earlier game is not an input.
- Do not read, score or print 2025-26 outcomes. Do not compare any projection to an actual in this feature.
- Gray only; no pick, bet, edge or "value" wording; no green or red on gap. No em dashes. No AI attribution in commits; ask before committing.
- Memory: a board date is a few hundred players at 20 rows each, small enough to build per request; if Step 3 shows otherwise, stop and say so instead of adding a cache.

## Results

- **Step 2, stored injury statuses** (read-only `SELECT status, COUNT(*) FROM nhl_player_injuries GROUP BY status`, 2026-11-04): `Injured Reserve` 4867, `Out` 678, `Day-To-Day` 504, `Suspension` 10. Out-type set pinned as `Out`, `Injured Reserve`, `Suspension` (a suspended player does not dress); `Day-To-Day` is served with the `injury_listed` flag.
- **Step 3, prior-history read** (read-only transaction, board date 2026-10-24): 404 players with lines, all 404 with history, at most 20 rows each, earliest season 2023, latest game 2026-10-23. Served value equals a hand SQL mean over the same rows for Alex Bump Shots On Goal (1.45), Christian Dvorak Faceoffs Won (7.05) and Jeremy Swayman Goalie Saves (24.8, starts only). Timing for the whole date: 1.07 s on the first call (cold connection), 0.27 s warm. No 2025-26 outcome was compared to a projection; 2025-26 rows are prior-game inputs only.
- **Step 4, board and game endpoints** (read-only, `build_prop_board` for 2026-10-24 with `as_of` 21:00 UTC, after the stored context batches of 20:41 UTC; 12 games, 3,416 lines, 1.05 s cold): skater lines 3,047 with a number and 251 without (`low_toi` 184, `few_prior_games` 33, `injured_out` 33, `not_center` 1; 9 more served with `injury_listed`); goalie lines 97 with a number and 21 without (`other_starter_expected` 16, `starter_unconfirmed` 5). The game endpoint's lines equal the board's lines for the same game (57031, 171 lines). With `as_of` before the first context fetch every goalie line read `no_goalie_report`, as designed.
- **Step 5, player endpoint** (same read-only setup, 2026-10-24): the player page's market value and every rung's gap equal the board's for Alex Bump Shots On Goal (1.45; gaps -0.05, -1.05), Jeremy Swayman Goalie Saves (24.8; gaps 5.3, 3.3, 1.8, -0.7, ...) and Evgeni Malkin Shots On Goal (no number, `injured_out`, rung gaps null).
- **Step 7, pages** (API on 127.0.0.1:8000 over HTTP and the Vite dev server on 3001, both stopped afterwards; the app uses a hash router, so pages are `/#/nhl/board`): the board for 2026-10-24 shows Proj and Gap beside Standard for every market (Goalie Saves: Arturs Silovs 22.5, Proj 22.9, +0.5); the game page for 57033 shows Jeremy Swayman 23, 24.8, +1.8 with alternates carrying their own gaps ("Goblin 19.5 (+5.3)"), and a skater under the TOI floor shows "-" with "Under 12 min a game"; the player page shows "Projection 24.8" with a Gap column per rung; the board showed "Injured: out" notes. No green or red on any gap. At 375 px wide the page has no horizontal scroll on the board or the game page (the board table scrolls inside its card). Added beyond the spec: a gap in brackets on each alternate line, so a goblin-only player still shows a gap, and the board legend now describes the projection instead of saying there is none.
- [x] Repair F-13 - test `get_prior_history`'s filters (closed by re-audit)
- [x] Repair F-15 - one-date guard in `load_projection_inputs` (closed by re-audit)

- **Step 8, Verify:** `npm --prefix web run verify` (typecheck, 1224 tests, build) and the API suite (5628 passed) both green. The interview guide (`docs/SportApp-Employer-Interview-Guide.md`, local and ignored, in the main checkout) had no NHL passage; one paragraph was added describing the gated reference projection as locally checked only, and the shipped-versus-in-progress reminder now names NHL.

## Findings

### 56c1/F-13 [P2] closed - get_prior_history's load-bearing filters have no test

**File:** api/app/repositories/nhl.py:509
**Found:** 2026-11-04 by /audit (scope: current; lenses: all)
**Why it matters:** The served projection's inputs hang on five filters in one
SQL string: the `NHL_FIRST_HISTORY_SEASON` floor, `REG`/`PST` only, goalies
`started` only, strictly before the date, and the 20-row window. The history
rule in coding-standards names the floor as the guard against a later backfill
changing a model's output, yet nothing would fail if it were dropped. The
behavior was only compared by hand against SQL for three players.
`tests/test_nhl_projection_history.py` already has a recording-session pattern
for the sibling `get_projection_history`.
**Suggested fix:** Add a test beside it that records the two statements and
params from `get_prior_history`: skater query has no `s.started`, goalie query
has it, both carry the floor, `before` and limit params, and rows come back
grouped per player oldest first.
**Resolution:** Added `test_prior_history_scopes_the_window_to_the_floor_and_the_date` and `test_prior_history_for_no_players_reads_nothing` in `api/tests/test_nhl_projection_history.py`; they pin the floor, game types, starts-only goalie filter, date cutoff, limit and per-player ordering. Closed 2026-11-04 by /audit (scope: current; lens: all): re-read `_prior_rows` and `get_prior_history` and the new tests; the tests would fail if any filter or parameter were dropped, and the repair added no code.

### 56c1/F-15 [P3] closed - Single-date assumption is a type ignore plus a docstring

**File:** api/app/services/nhl/projections.py:73
**Found:** 2026-11-04 by /audit (scope: current; lenses: all)
**Why it matters:** `load_projection_inputs` takes `games[0]["game_date"]` as the
cutoff for every game, with a `# type: ignore[arg-type]`. It is correct for the
board and game page today, but 56c4 freezes a whole week of games across
several dates and could reuse this function, which would let a later date's
same-day games into an earlier date's window. The context read also swallows
`HTTPException` after the history read; that is safe only while no query follows
it, since a failed statement can abort the transaction.
**Suggested fix:** Raise if the games span more than one date and replace the
ignore with a real `dt.date` cast; group by date in 56c4 as NBA's freeze does.
**Resolution:**

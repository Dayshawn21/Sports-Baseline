# Feature: NFL recent form window (51)

**From build-plan:** feature 51 (added 2026-11-02, after 50)
**Status:** complete (2026-11-02)
**Branch:** `feature/nfl-recent-form-window`

## Goal

The recent form chart in each prop section of the NFL player page gets a
**Last 5 / Last 10 / vs Opponent** switch. Last 5 is today's chart and stays the
default. Display only: no projection, edge, rank, sort, pick, model version or
signal color changes, and nothing the board, game page or Ask reads changes.
The choice lives in the URL so a link or a reload shows the same window.

## Design reference

None. This extends the section 50a built; the chart is `DetailGameLog` in
`NflPropDetailSections.tsx`, using the existing `nfl-prop-detail__chart` CSS.

## What reading the code and data settled

| Question | Answer | Consequence |
|---|---|---|
| Does `player.gameLog` hold 10 games? | Only sometimes. It is this season plus the last 5 of the previous (`game_log_rows`), so Last 10 is short before week 6 (week 1 = 5 games). Week 8 2026 shows 12. | Not the source for Last 10. |
| Does it carry the chart's per-game value? | No. Slate history uses `fantasy_points`, the game log carries `prizepicksFantasyPoints` (different scale); anytime TD and receiving targets would need a second derivation on the web. | A web-side derivation could disagree with today's Last 5 bars. |
| What does vs Opponent need? | Prior meetings since 2024. The slate's `opponentHistory` already has them (`PROJECTION_FIRST_HISTORY_SEASON`); the game log covers about one season. Live week 8 2026: 0 meetings on 1,584 of 5,914 full-game lines, 1 on 1,917, up to 5. | Use `opponentHistory`. "No meetings" is a normal state (27%), not an edge case. |
| Where is the per-game value computed today? | Server, `_history_value` (and `targets.py` for receiving targets), once, for every market including anytime TD (0 or 1). | Keep one derivation. Add a longer sample from the same code path. |

**Decision:** an additive slate-line field `recentFormLong` (newest first, up to
10 games, same `_history_value`, same ordering and opponent codes as
`recentForm`). `recentForm`, `opponentHistory` and every existing field are
untouched, so Last 5 is byte-for-byte today's chart and `recentForm.average`
keeps its meaning. A test pins `recentFormLong[:5] == recentForm`.

## In scope

- API: `recent_form_long` on `NflSlateLineSchema`, filled in `slate.py`
  (`_history_sample(..., limit=10)`) and `targets.py` (`observations[:10]`).
- Web: `recentFormLong?: NflHistorySample` on `NflSlateLine` (optional because a
  stored slate snapshot written before this ships lacks it).
- A pure module `utils/nflFormWindow.ts`: the window type (`5 | 10 | opp`), URL
  parse, which sample a window reads, per-window availability and labels, and the
  bars builder shared with `recentBars`.
- The switch in `DetailGameLog` and the URL param, kept when the prop tab or the
  lines card changes `?market=`.
- Empty and thin states below.

## Out of scope

- The page's **Game log table** (`NflPlayerGameLog`) is not switched; it is the
  full season log, a different job. Revisit only if asked.
- Kickers and punters: their markets are line-only and have no prop section
  (they live in "Other markets"), so no switch there.
- Receiving-targets, anytime TD, and every other section market all get the
  switch. TD keeps its text list (a game is 0 or 1) and the switch changes
  which games the text lists.
- NBA, tennis, the prop board mini bars, the game page and `DetailContext`'s
  existing "Vs opponent" text (left as is; it repeats the H2H window, accepted).
- Refreshing production `report_snapshots` for `/nfl/slate`. After deploy a
  release note: until `nfl_slate_snapshot` runs, Last 10 shows as unavailable.
- An H2H cap beyond what history holds, season filters, a Last 15 or any other
  window.

## Behavior

**URL.** Param `form` with values `10` and `opp`. Absent means Last 5; an
unknown value means Last 5; choosing Last 5 removes the param. The switch uses
`replace` (no history entries). It coexists with `?market=`: the prop tabs and
the lines card rows write `market` while keeping `form` (today they build
`?market=...` strings that would drop it), and the window applies to whichever
prop is shown, so it persists across tabs.

**Windows (a sample is up to N games, newest on the right as today).**

| Window | Source | Games |
|---|---|---|
| Last 5 | `recentForm` | up to 5 |
| Last 10 | `recentFormLong` | up to 10, across seasons back to 2024 like Last 5 |
| vs Opponent | `opponentHistory` | all prior meetings since 2024, oldest to newest |

**States.**

- Last 10 with `recentFormLong` absent (stale snapshot): button disabled,
  title "Not in this slate snapshot yet", chart stays on Last 5 content.
- Fewer games than the window (a rookie): chart shows what exists; the header
  reads "7 of 10 games" not "10".
- Same number of games as another window (a rookie has 5 for both): the buttons
  stay enabled; no hiding.
- vs Opponent with `opponentTeam` null: disabled, "No opponent this week".
- vs Opponent with no prior meetings: the chart area reads "No earlier games
  against {OPP} since 2024."; the line mark and projection are unaffected.
- Anytime TD: no bars (as today); the text row lists the window's games as
  "TD / No TD vs OPP" and the header keeps the existing `history()` wording
  (percentage average and game count) for the chosen sample.
- Header (`detail.recentForm`) changes with the window: title ("Recent form",
  "Last 10", "Vs {OPP}"), average and game count, all from the chosen sample.
  Bars scale and color against the line exactly as `recentBars` does (a
  partial-segment line is not drawn).

**Style.** Gray signal colors only; the above/below bar colors keep their
current classes, no new green. Switch is a small segmented control with
`aria-pressed`, labels at 11px or larger, tap target at least 24px, usable at
phone width. Colors via theme variables.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

## Build steps

- [x] **Step 1 - Longer form sample from the API** - add `recent_form_long`
  (schema, `slate.py`, `targets.py`) and `recentFormLong?` to `NflSlateLine`.
  Python test: for a history longer than 10 the field has 10 values newest
  first; `[:5]` equals `recent_form` (values and opponents); a TD market gives
  0/1 values; targets path gives the same. *Done when:* `pytest` passes, a live
  `/nfl/slate` line returns both fields and every existing field is unchanged
  (diff of one line's JSON before and after, minus the new key).
- [x] **Step 2 - Window logic, pure** - `utils/nflFormWindow.ts`: `FormWindow`,
  `parseFormWindow(params)`, `formSample(row, window)` (sample or null when
  unavailable), `formWindowOptions(row)` (label, disabled, reason),
  `formBars(sample, row)` extracted from `recentBars` so `recentBars(row)` is
  `formBars(row.recentForm, row)` and the board's mini bars stay identical.
  Vitest: parse (absent, `10`, `opp`, junk), each window's sample and
  availability (stale snapshot, null opponent, no meetings), thin sample count
  text, partial-segment line suppression, `recentBars` regression for an
  existing fixture. *Done when:* `npm.cmd run test` passes; no component
  touched.
- [x] **Step 3 - Switch and URL** - segmented control in `DetailGameLog`
  (window and setter passed from the page level via `useSearchParams`, `replace`);
  header, chart, empty and TD text follow the window; `NflPlayerProps` tabs and
  `NflPlayerLines` rows keep `form` when writing `market` (a small
  `withSearchParam` helper with a test). *Done when:* in the running app
  (player with a line, e.g. one at week 8) Last 5 matches the pre-change chart,
  Last 10 shows up to 10 bars, vs Opponent shows the meetings or the empty
  message; reload and Back keep the window; switching prop tabs and clicking a
  lines card row keep `?form=`; TD prop shows text for the window; a K or P
  page and a player with no line are unchanged; no console errors; phone width
  (375) has no horizontal scroll; every text is 11px or more.
- [x] **Step 4 - Verify** - run the repo Verify command; note the snapshot
  release step. *Done when:* Verify passes and the invariants review finds no
  change to projections, ranks, edges, versions or signal colors.

## Files / areas

- `api/app/schemas/nfl.py`, `api/app/services/nfl/slate.py`,
  `api/app/services/nfl/targets.py`, `api/tests/test_nfl_prop_predictions.py`
  (or a new `test_nfl_form_window.py`)
- `web/src/types/nfl.ts`
- `web/src/utils/nflFormWindow.ts` (+ test), `web/src/utils/nflPropCards.ts`
  (`recentBars` delegates), `web/src/utils/nflPropDetail.ts` (history text for a
  chosen sample), `web/src/utils/nflPlayer.ts` (`withSearchParam` or similar)
- `web/src/components/nfl/NflPropDetailSections.tsx`,
  `NflPlayerPropSection.tsx`, `NflPlayerProps.tsx`, `NflPlayerLines.tsx`,
  `nfl-prop-detail.css`

## Data / contracts

- **Load-bearing:** `recentFormLong` is additive and optional; `recentForm`
  (5), `opponentHistory` and their `average` semantics are frozen. The URL
  contract is `?form=10|opp` beside `?market=`.
- No migration, no new table, no model version, no change to any stored or
  graded value.

## Testing

- Python (`pytest`): the sample helper and both builders (Step 1).
- Vitest: `nflFormWindow` and the search-param helper (Steps 2-3). Components
  are verified in the running app, not unit-tested, per the project gate.
- Verify: `npm --prefix web run verify && cd api && python -m pytest`.

## Notes for the AI

- Display only. Do not touch `model_projection`, edges, `edgeShare`, ranks,
  sort, `qualityFlags`, `projection_model_version` or signal classes. Green is
  reserved for a validated positive signal; nothing here earns it.
- HashRouter: no `#` anchors; use `useSearchParams`. Components call hooks,
  not axios; no new request.
- No em dashes in code, comments or docs. Comment only the why (e.g. why the
  field is optional).
- The 27d/PROJECTION_FIRST_HISTORY_SEASON bound already limits the history;
  do not add a new lower bound or unbounded read.
- Keep Last 5 identical to the pre-change chart; capture a before screenshot
  of one prop in Step 3 to compare.

## Added during the build

- A player opened from the NFL prop board shows "← Props" and returns with the browser Back, so the board filters, scroll and focused row return (user request after Step 3). Board rows set router state (`FROM_BOARD`); the game page and direct links keep their crumbs. Not a spec step.

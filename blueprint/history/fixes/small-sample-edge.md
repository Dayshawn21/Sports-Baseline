# Fix: No edge on a small-sample baseline

**Type:** Fix
**Status:** complete (2026-09-15), squash-merged from `fix/small-sample-edge`

## Outcome

- 2026 week 2: 73 priced edges, down from 77; none carry `small_sample`. The four one-game rows keep their baseline and flags with `edge: null`.
- Comparability now lives in `edge_is_comparable` in `core/`, tested across games, segment, and odds type.
- The web mirrors `MIN_BASELINE_GAMES` for tooltip wording only; the API enforces it. Keep the two in sync.
- Noticed, not fixed: the Sample column renders "1 games".

## The problem

The NFL slate computes an edge for any standard full-game line whose player has
at least one game. A baseline under `MIN_BASELINE_GAMES` (4) is flagged
`small_sample`, but its edge is still shown as a colored, rankable number.

On the 2026 week-2 slate, 4 of 77 priced edges rest on a single game. MarShawn
Lloyd's receiving-yards baseline is one game with zero catches, so it reads as a
-6.5 edge against a 6.5 line: a confident-looking under that measures one game,
not a mispricing. This grows through weeks 3 and 4 as rookies accumulate one to
three games.

The rule deciding comparability also lives inline in `_slate_line` in
`api/app/routers/nfl.py`, which is business logic in a router and untested.

## The fix

- Move the comparability rule into a pure function in
  `api/app/core/nfl_projection.py`, and add the sample gate: an edge is
  comparable only when the baseline has at least `MIN_BASELINE_GAMES` games, the
  segment is `full_game`, and the odds type is standard.
- `_slate_line` calls it instead of building the condition inline.
- The web "Not comparable" tooltip names the thin sample, checked in the same
  order the backend refuses.

**Must not break:**

- The baseline number still shows on small-sample rows. Only the edge is withheld.
- `small_sample` and every other flag are unchanged.
- One threshold: reuse `MIN_BASELINE_GAMES`, no new literal.
- Existing segment and odds-type refusals behave exactly as before.

## Build steps

- [x] **Step 1 - Pure comparability rule with the sample gate.** Add the function
  to `nfl_projection.py`, call it from `_slate_line`. *Done when:* table-driven
  tests cover 0, 3, and 4 games, a non-full-game segment, a goblin line, and a
  missing odds type; `pytest` passes; the live `/nfl/slate?season=2026&week=2`
  returns `edge: null` for all 4 one-game rows and 73 priced edges.
- [x] **Step 2 - Explain it on the slate.** In `notComparableReason`
  (`web/src/pages/NflIntelligencePage.tsx`), a row with games but fewer than 4
  says so. *Done when:* hovering MarShawn Lloyd's receiving-yards "Not
  comparable" shows the small-sample reason with his game count; `npm run build`
  and `npm run test` pass.

## Verify

- `cd api && pytest`, `cd web && npm run test && npm run build`.
- Open NFL, 2026, Week 2. The info banner reads 73 with an edge. MarShawn Lloyd's
  receiving-yards row still shows a 0.0 baseline and Small sample, but its edge
  is "Not comparable" with the game-count tooltip. A 17-game row such as DJ Moore
  still shows its edge.

## Out of scope

- **Scheduling NFL ingest.** Drafted separately as the next fix.
- **Changing how the baseline season is chosen.** The largest-sample fallback
  still supplies a thin baseline; this fix only stops pricing it.

# Current Feature

## Restore the evidence blocks dropped by the NFL page redesign

**Type:** Fix

## The problem

The NFL page redesign (`b303204`, 2026-09-19) rewrote `EvidencePanel` in
[web/src/pages/NflIntelligencePage.tsx](../../web/src/pages/NflIntelligencePage.tsx)
and silently dropped four evidence blocks that shipped with earlier features. The
API still serves every field and the helpers still exist with passing tests; only
the rendering is gone, so nothing failed.

| Missing block | Shipped in | State now |
|---|---|---|
| Sportsbook anytime-TD consensus | 19i | `nflBookOddsEvidence` in [web/src/utils/nflBookOdds.ts](../../web/src/utils/nflBookOdds.ts) has no importer |
| Snap share (RB/TE anytime TD) | 19m | `snapShareLabel` in [web/src/utils/nflSnapShare.ts](../../web/src/utils/nflSnapShare.ts) has no importer |
| Opponent history ("Vs OPP") | 19g | `opponentHistory` is read nowhere |
| Opponent allowed average and sample size | 19g | The Matchup block shows only `opponentAdjustmentPct`, not `opponentPositionAverage` or `opponentSampleGames` |

All four are listed as shipped `/nfl` behavior in
[project-overview.md](project-overview.md) under Web routes, so the page currently
does less than the overview says it does. The sportsbook block is the one that
prompted this: the anytime-TD board has few rateable lines, and the book price is
the context that explains why, but there is nowhere on the slate to see it.

The tests kept passing because `nflBookOdds.test.ts` and `nflSnapShare.test.ts`
call the helpers directly, and the project does not test React components.

## The fix

Render the four blocks again inside the existing `.nfl-evidence-grid`, reusing the
current `.nfl-evidence-block` markup (`span` label, `strong` value, optional
`small` detail). No CSS change: that class already supports all three slots.

Do not resurrect the pre-redesign class names (`nfl-evidence__books`) or the
pre-redesign panel layout. The redesign's structure stays; this only puts the
missing content back into it.

Constraints:

- Blocks that do not apply must not render at all, rather than showing an empty
  or "--" block. `nflBookOddsEvidence` and `snapShareLabel` already return `null`
  for that case; honor it.
- A null book price means no book priced the line, never 0%.
- `snapShareGames === 0` means no snap history and the position average was used;
  that is different from `null` (not applicable). The helper already says this.
- Display only. This changes nothing about edge, ranking, projections, or the
  `/nfl/board` page.

## Build steps

- [x] **Step 1 - restore the four blocks in `EvidencePanel`**

  Import `nflBookOddsEvidence` and `snapShareLabel`. Add to the evidence grid:
  a Sportsbooks block (summary plus the model-vs-books comparison as `small`),
  a Snap share block, a `History` block for `opponentHistory` titled
  `Vs {opponentTeam}`, and the allowed average and sample count as `small`
  detail on the existing Matchup block. Both helper-backed blocks render only
  when the helper returns a value.

  **Done when:** on `/nfl` for 2026 week 2, selecting a CAR or ATL anytime-TD
  line shows a Sportsbooks block with a consensus percentage, book count, and
  fetch age; selecting an RB or TE anytime-TD line shows a Snap share block;
  a line with opponent history shows a "Vs OPP" block; and the Matchup block
  shows the allowed average and games. Selecting a line with none of these
  (for example a passing-yards line in an unpriced game) shows no empty blocks.

## Verify

- `cd web && npm run build` (runs `tsc -b`, so this typechecks too)
- `cd web && npm run test`
- Browser: `/nfl`, season 2026, week 2. CAR @ ATL is the only game with
  sportsbook anytime-TD prices loaded right now (fetched 2026-09-18), so check
  the Sportsbooks block there. Other games should show the block absent, not
  blank.

No new test ships with this step: it is display wiring over helpers that
`nflBookOdds.test.ts` and `nflSnapShare.test.ts` already cover, and the project
does not test React components (see Testing in
[coding-standards.md](coding-standards.md)). Build and browser evidence carry it.

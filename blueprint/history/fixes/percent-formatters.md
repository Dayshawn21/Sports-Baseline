# Fix: Whole percents through `fmtPct`, no pass-through wrappers

**Type:** Fix
**Fixes:** F-77
**Branch:** `claude/fix-percent-formatters-93ec2a`

**Completed:** 2026-11-18. Opened as a pull request against master; the user merges it.

### The problem

The 2026-11-18 re-review of the F-60 fix found whole-percent text still
hand-rolled as `${Math.round(x * 100)}%` beside `fmtPct` (`utils/odds.ts`):

- Local `percent()` helpers in `utils/nbaProps.ts`, `utils/nflSignal.ts` and
  `utils/nflVolume.ts`.
- Inline copies in `utils/nbaPlayer.ts` (`nbaPercentText`),
  `utils/nflGameNotes.ts` (`statValue`), `utils/nflPlayer.ts` (`usageBars`),
  `utils/nflSnapShare.ts`, `utils/tennisPlayer.ts` (`metricText`),
  `utils/nflMatchupContext.ts` (`contextCoverage`, same pattern, not in the
  ledger list), `components/nfl/NflPlayerGameLog.tsx`,
  `components/nfl/NflPlayerRecord.tsx`, `components/nfl/NflPlayerUsage.tsx`
  and `pages/NflPlayerPage.tsx`.
- `utils/boardRecord.ts` `percent` and `components/tennis/TennisSlateTable.tsx`
  `pct` only forward to `fmtPct`.
- `utils/homeSources.ts:188` writes the moneyline gap as
  `+${(diff * 100).toFixed(1)} pp`, a hard-coded sign.

### Why the output stays the same

`fmtPct(x, 0)` is `${(x * 100).toFixed(0)}%`, or the dash glyph for null.
Both forms compute the same double `x * 100`. For a non-negative finite value,
`Math.round` and `toFixed(0)` pick the same integer, ties included (both round
a tie up). They differ only on negatives (`Math.round(-12.5)` is `-12`,
`toFixed` gives `-13`; `Math.round(-0.4)` prints `0`, `toFixed` prints `-0`)
and on null (`0%` versus the dash). Every site here:

- receives a probability, share or rate in `[0, 1]` (P(over/under/push), snap
  share, success rate, a tennis serve or return percentage, observed over
  eligible games), so never a negative; and
- already handles null before formatting (its own `--`, `-`, `no data`,
  `MISSING` or dash), or its type is a plain `number`.

So no placeholder changes and no text changes. NaN and Infinity print the same
in both forms.

The gap: the row names the side with the larger model-minus-market gap, and
the two sides mirror once de-vigged, so `diff >= 0`. `fmtSigned(diff * 100, 1,
' pp')` prints the same `+x.x pp` for every gap that rounds above zero.

**Visible change (F-60 zero rule):** a gap that rounds to zero shows `0.0 pp`
where it showed `+0.0 pp`, as every other signed value has since F-60.

### Left alone

- `utils/homeSources.ts:152` and `:197`: owned by the F-76 session.
- `utils/nbaSlate.ts:118` (`winBar`) and `utils/nhlProjection.ts:53`
  (`nhlPercentLabel`): they use the rounded integer as a number (the bar
  split, the `<1%` and `>99%` clamps), not as text.
- `utils/trackRecord.ts:63`: a `40-50%` range whose first bound has no `%`.
- `NflRankingSlices.tsx:60`, `NflVolumeRecord.tsx:58`, `ModelClv.tsx:11`:
  margins printed as `points`/`pts`, not percentages.

### Build steps

- [x] **Step 1 - replace and delete.** Route every site above through
  `fmtPct(x, 0)` (or `fmtPct(x)` for the two wrappers), the gap through
  `fmtSigned`, and delete the three `percent()` helpers and both wrappers.
  Add or adjust tests for the utils whose output path changes (whole-percent
  ties, the zero gap). Done when: grep for `Math.round(... * 100)}%` finds only
  the sites left alone, no local percent wrapper remains, and Verify passes.

### Verify

- `npm --prefix web run verify` and the API tests.

# Tennis gray-signal cleanup after 48f

**Type:** Fix

**Base:** stacked on `feature/48f-retire-tennis-tiers` (not yet on `master` as of
2026-10-29), built on `claude/magical-hamilton-wzw0xo`.

## The problem

An invariants review of 48f found two tennis elements that still use a signal
color for a signal no tennis tier has earned (none has passed the 32b tier
rule). Both predate 48f and were kept out of its scope.

1. `web/src/components/tennis/TennisSlateSummary.tsx` colors the Locks and
   Strong+ chips `var(--positive)`. After 48f they count priced match-market
   best bets only, so green implies a validated signal that does not exist.
2. Win a Set rows on the tennis prop board (`winASetBoardRows` in
   `web/src/utils/tennisPropBoard.ts`, source `model`, null `payoutTier`) show
   `pickLabel` LOCK or STRONG. The row's tone is decided inline in
   `TennisPropTable.tsx` and `TennisPropEvidencePanel.tsx`, and with no
   payout tier and no recommendation it falls through to the default green
   `.tennis-prop-table__pick` / `.tennis-prop-evidence__pick` color.

## The fix

Owner decisions (2026-10-29): keep both chips and keep the LOCK/STRONG label,
render both in neutral colors.

- Slate summary: drop the `color` prop from the Locks and Strong+ chips so they
  use the default chip color, like Matches and Player props.
- Prop card tone: replace `isUnder` on `TennisPropCardModel` with a
  `pickTone: 'positive' | 'negative' | 'none'` computed in `propCard`, and have
  both components read it instead of duplicating the rule. `none` for Win a
  Set rows, PrizePicks rows (any payout tier) and a `--` label. Priced book
  rows keep `positive` / `negative` by recommendation, as 48f left them.

Must not break: priced book row colors, EV tones, NFL prop cards (separate
model, untouched), the `winASetStrength` thresholds.

## Build steps

- [x] **Step 1 - Neutral slate chips and Win a Set tone.** Slate chips lose
  `var(--positive)`; `propCard` gains `pickTone`, `isUnder` goes, both tennis
  components use `pickTone`; `tennisPropCards.test.ts` covers the tone for a
  Win a Set row, a PrizePicks row, a priced UNDER row, a priced OVER row and a
  `--` row. **Done when:** neither element uses a positive or negative signal
  color, and Verify passes.

## Verify

- `npm --prefix web run verify && cd api && python -m pytest`
- Manual: the tennis page summary strip shows Locks and Strong+ in the default
  chip color; on the tennis prop board, a Win a Set row reads LOCK or STRONG
  in muted gray, in the table and in the evidence drawer.

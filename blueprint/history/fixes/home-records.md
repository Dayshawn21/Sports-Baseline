# Fix: Home model record labels say what the record says

**Type:** Fix
**Follows:** feature 55 and fix `home-cards` (both on `master`)
**Status:** complete (2026-11-04)
**Branch:** `fix/home-records` (worktree `.claude/worktrees/fix-home-records`, cut from `master`)

## The problem

The home's model record cards read the wrong thing:

- **NFL showed "Accruing" while two of its four slices were already rejected.**
  `rankingRecord` returned "Accruing" whenever no slice had adopted, so a final
  `reject` verdict looked like a sample still filling. Real API verdicts on
  2026-11-04: `insufficient, reject, insufficient, reject`.
- **Tennis showed "Not ahead" for a statistical tie.** On the model page the
  market's log loss is 0.6045 and the ensemble's 0.6043 over 382 matches, about
  0.1 standard errors apart. `ensembleVerdictText` collapses `neutral` and
  `negative` into "Not ahead", which reads as a failure.

## The fix

Say what the record says, from the data already loaded; no new request, no
model or rule change, gray stays gray.

- **NFL and NBA label:** `N of M adopted` always (including `0 of 4 adopted`),
  with the card's detail line carrying the rest of the verdicts, for example
  `V4 forward ranking check · 2 rejected · 2 accruing`. Zero counts are left
  out of the detail. `insufficient` and `accruing` both count as accruing, as
  the model pages' `verdictLabel` does.
- **Tennis label:** `Ahead of market` for a positive signal, `Level with
  market` for neutral, `Behind market` for negative, `No data` as today.
  Mapped in the home's own helper; `ensembleVerdictText` and the tennis model
  page are untouched.

## Build steps

- [x] **Step 1 - Honest record labels (pure helper, one component line).**
  Change `web/src/utils/homeRecords.ts` and its test; `HomeRecords.tsx` already
  prints `record.label` and `record.detail`.
  *Done when:* tests prove: all four slices accruing reads `0 of 4 adopted`
  with detail `... · 4 accruing`; the real NFL mix reads `0 of 4 adopted` with
  `2 rejected · 2 accruing`; adopted slices count (`1 of 4 adopted`);
  `pass` is not adopted and is named in the detail; tennis positive, neutral,
  negative and empty read `Ahead of market`, `Level with market`,
  `Behind market` and `No data`; loading and error placeholders are unchanged;
  web Verify passes; on real data the home shows the new text.

## Files / areas

`web/src/utils/homeRecords.ts` and `homeRecords.test.ts` only. The
`home-gaps-tabs` branch does not touch these files.

## Testing

Test gate on: Vitest with fixed fixtures. Final gate:
`npm --prefix web run verify`, and the API half of Verify
(`pytest`) is unaffected (no API change).

## Notes for the AI

- No em dashes in new content; comment the why only.
- Do not change `ensembleVerdictText` or the model pages.

## Results

Verified 2026-11-04: `npm --prefix web run verify` passes (79 files, 1186 tests, build); no API change, so API pytest is unaffected.

- On real local data the home now reads Tennis `Level with market`, NFL props `0 of 4 adopted` with `V4 forward ranking check · 2 rejected · 2 accruing`, and NBA props `0 of 4 adopted` with `Forward ranking check · 4 accruing`.
- Not covered: the cards at phone width (text is longer; the card text wraps, unchecked) and a day where a slice has adopted (unit tests only).

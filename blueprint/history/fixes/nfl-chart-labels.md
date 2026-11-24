# Fix: Bar labels crowd each other on phones

**Type:** Fix
**Follow-up to:** item 51 and `nfl-form-dates`
**Status:** complete (2026-11-02)

## The problem

On a phone, ten bars in the NFL recent form chart carry labels such as `271.0` and
`270.0` that touch and overlap.

## The fix

- `formBarLabel` in `nflFormWindow.ts`: a whole count shows without its `.0`
  (`271`), a fraction keeps one decimal. Only the label above each bar changes;
  the text lines (`231.0 vs CHI`) and the header are unchanged.
- Unused `formatHistoryValue` import removed from `NflPropDetailSections.tsx`.

## Verify

- `npm --prefix web run verify` passed (1,025 tests, build); the API is untouched.
- Hosted API, 375px, Lamar Jackson passing yards, Last 10: ten labels each with
  their own gap. Built directly at the user's request; this note is its record.

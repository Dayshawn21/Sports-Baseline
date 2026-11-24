# Fix: One game per line in the NFL TD list on phones

**Type:** Fix
**Follow-up to:** item 51 and `nfl-form-dates`
**Status:** complete (2026-11-02)

## The problem

On the NFL player page, the Anytime TD recent form list (Last 5, Last 10 or vs
Opponent) is a joined text line. With dates added it wrapped into a dense block
on a phone.

## The fix

- `history()` in `nflPropDetail.ts` also returns `games`, one string per game;
  `detail` is still the joined text.
- `DetailGameLog` renders the games as a list. On screens 600px and narrower each
  game is its own line; wider, the games stay inline with a dot between them
  (the separator is drawn in CSS).
- Only the TD list (the form section without bars) changed. The `vs opponent` and
  `allowed` lines still wrap as text.

## Verify

- `npm --prefix web run verify` passed (1,024 tests, build); the API is untouched.
- Hosted API, 375px: ten lines, no horizontal scroll, 12px text. Desktop: inline
  with dot separators.
- Built directly (no prior spec) at the user's request; this note is its record.

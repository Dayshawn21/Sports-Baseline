# Make model history floors a reviewed invariant

**Type:** Fix
**Completed:** 2026-10-30
**Branch:** `fix/nfl-history-floor-invariant`

## The problem

`fix/nfl-v4-history-floor` (2026-10-30) showed that a versioned model reading
"every stored season before the slate week" changes output when older seasons
are backfilled, with no version bump and no review catching it. The floor now
exists for NFL v4 and Rec Targets (`PROJECTION_FIRST_HISTORY_SEASON`), but no
standard or review check requires one, so the next model or reader can repeat it.

## The fix

- `blueprint/context/coding-standards.md`: a Database rule that model history
  reads carry an explicit lower season bound from the model's validated range.
- `.claude/agents/invariants-reviewer.md`: invariant 11, history floors, the
  single source both `invariants-review` skills read.
- The reviewer and skill descriptions (both adapters) name the new invariant.
- No code changes.

## Build steps

- [x] **Step 1 - add the rule and the invariant.** All four files above.

## Done when

- The reviewer lists invariant 11, and `coding-standards.md` states the rule.
- `.claude` and `.agents` skill copies differ only in the existing link path.
- Verify passes.

## Evidence

- Verify: web 66 test files and 988 tests passed and the build succeeded, then
  5,080 API tests passed.
- `diff` of the two `invariants-review` skill copies shows only the existing
  link-path line.
- Try it: run `/invariants-review` on a branch that adds an NFL history read
  without `PROJECTION_FIRST_HISTORY_SEASON`; it should report invariant 11.

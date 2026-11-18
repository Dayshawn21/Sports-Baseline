# Fix: One shared board crumb for the player pages

**Type:** Fix
**Fixes:** F-79
**Branch:** `claude/fix-board-crumb-f57805`

**Completed:** 2026-11-18. Re-reviewed by an independent reviewer (confirmed fixed, nothing new); left for the user to merge.

### The problem

F-67 copied the NBA board crumb into `NhlPlayerPage`, so `NbaPlayerPage.tsx:33-42`
and `NhlPlayerPage.tsx:34-42` hold the same component. Both call `useLocation()`
inside an `if` condition, which reads like a conditional hook.
`NflPlayerPage.tsx:66` hoists it to a `const`, and builds the same board link
inline.

### The fix

- `components/shared/BoardCrumb.tsx`: `BoardCrumb({ boardPath, label, fallback })`
  calls `useNavigate()` and `useLocation()` at the top. A board arrival
  (`arrivedFromBoard`) renders `← {label}` linking to `boardPath` and going back
  one step on click; anything else renders `fallback`.
- NBA and NHL drop their local `Crumb` for `BoardCrumb`, each passing its own
  fallback (game crumb, then the board for NBA or the slate for NHL).
- NFL's board branch is the same link and click, so it uses `BoardCrumb` too,
  with its game or week-slate crumb as the fallback.

No visible change: the same crumb text (`← NBA props`, `← NHL props`, `← Props`,
or the game or slate crumb otherwise), the same back navigation and the same
fallback paths. No new pure logic, so no new test: `arrivedFromBoard` is
already tested in `utils/playerPage.test.ts`.

Stays inside `web/`.

### Build steps

- [x] **Step 1 - `BoardCrumb`.** Add the component and switch the NBA, NHL and
  NFL player pages to it. Done when: no player page calls `useLocation()` or
  builds the board crumb link itself, and Verify passes.

### Verify

- `npm --prefix web run verify`, then the API tests.

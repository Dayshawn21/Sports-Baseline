# Fix: Load the Ask drawer and slate search rows on demand

**Type:** Fix
**Branch:** `fix/lazy-shell-features` (worktree `.claude/worktrees/sharp-elbakyan-f84efc`, cut from `master` at `4645fff8`)
**Status:** completed 2026-11-23

## The problem

Lighthouse 13.6 (mobile, 2026-11-23) flags 57 KB unused of the 125 KB entry
bundle at startup. Among the app modules in the entry are features no first
paint needs:

- The Ask drawer (`AskDrawer`, `AskAnswer`, `askStream`, `askSession`,
  `askAnswer`, `askError`, `askStarters`, `api/ask`, `useAskSession`):
  `AskLauncher` imports it statically and mounts it closed on every page.
- The per-sport slate search row builders in `utils/slateCommand.ts` (tennis,
  NFL, NBA, NHL, with `nflTeams` and `slateMatchup`): the shell's search field
  imports the module for its placeholder, reducer and matching, so the
  builders ride along, though only the lazy sport pages call them.

The search field itself is visible in the header at first paint, so it stays
eager; only its row builders can leave the entry.

## The fix

- `AskLauncher`: `AskDrawer` becomes `lazy`, mounted from the first click on
  (then kept mounted, so a closed drawer keeps its conversation and draft as
  before); its chunk starts loading on pointer enter or focus of the button.
- `utils/slateCommandRows.ts`: the row builders and their input types
  (`commandGameContext`, `slateCommandRow`, the four `*SlateCommandRows`) move
  out of `slateCommand.ts`, which keeps the placeholder, state, reducer,
  normalizing and matching. The seven sport pages and the test import the
  builders from the new module; no function changes.

**Must not change:** what the drawer or search shows or does, focus return on
close, the search results and their order.

## Build steps

- [x] **Step 1 - Split the search rows.** *Done when:* `tsc -b` is clean and
  `slateCommand.test.ts` passes unchanged in substance (imports only). Done
  2026-11-23: `tsc -b` clean, 25 search tests pass.
- [x] **Step 2 - Lazy Ask drawer.** Done 2026-11-23: Verify passed (1,887 web
  tests and build). Entry `index` 366.3 to 352.3 KB raw, 123.5 to 118.8 KB
  gzip; `AskDrawer` (JS and CSS) and `slateCommandRows` are their own chunks.
  Local production preview: home loads neither at startup; clicking Ask loads
  the drawer chunk and opens the dialog; a typed draft survived Escape and
  reopen, focus returned to the button, only `/ask/status` was called; on
  `#/nfl` (1280 wide) the rows chunk loads with the page and "jefferson" lists
  Justin and Van Jefferson and both games. *Done when:* Verify passes; in a local
  production preview the home page loads neither chunk at startup; Ask opens
  with its chunk, a typed draft survives close and reopen, focus returns to
  the button, and no question is sent; NFL search still finds players and
  games.

## Verify

- Verify: `npm --prefix web run verify && cd api && python -m pytest`.
- Entry bundle size before and after (`build/index.html`'s `index-*.js`).

## Out of scope

- The admin hook in the entry, React render cost, `react-vendor`.

# NFL Props: include the game pages' other markets

**Type:** Fix

## The problem

NFL game pages reached from Slate load `NflLineOnlyProps` separately from
the modelled slate lines. NFL Props loads only the slate, so these additional
stored markets never appear on the weekly board: passing touchdowns,
interceptions, rushing + receiving yards, passing + rushing yards,
passing + rushing + receiving touchdowns, field goals made, kicking points,
and punts. Its Show all lines toggle only reveals additional slate rows.

## The fix

Make the existing line-only markets available on NFL Props across the selected
week's upcoming games, using the established table styling, labels, recent
results, standard lines, and alternate rungs. Preserve the existing game-page
access. Match the board's season, week, position, and game filters, and include
games that have only line-only props. Load these markets independently of the
modelled slate rows, with visible loading, error, retry, and empty states.

Keep these rows explicitly labelled as recent-results-only references. Do not
invent projections, edges, ranks, probabilities, or recommendation colors.
Preserve Rec Targets' separate reference handling and existing comparison
ranking. Reuse the existing line-only service and grouping rules; keep SQL in
repositories and avoid heavy report construction on the production request path.
No model, ingest, grading, migration, or provider request changes.

## Build steps

- [x] Add the existing line-only markets to the weekly NFL Props experience,
  including typed data access and the existing filters. Verify fetching and
  filtering without requiring a modelled line for the game. Reuse the game
  page's rendering where practical without changing its behavior.
  **Done when:** NFL Props shows available other-market lines for upcoming
  games in the chosen week; game and position filters work; alternate rungs
  and recent results remain available; these rows carry no model scores;
  existing modelled rows, Rec Targets references, and game pages still work.

## Verify

- Add pure-helper tests for week/game/position selection, a game with only
  line-only props, grouping/alternate handling, and kickoff exclusion as needed.
- Run the documented Verify gate: `npm.cmd --prefix web run verify` from the
  root, then `.venv\Scripts\python.exe -m pytest` from `api/`.
- In the running app, compare a game's Other markets with NFL Props for the
  same week and game. Check all-game and position filters, another week,
  loading/error/empty states, and desktop/mobile table behavior.

## Implementation evidence (2026-10-22)

**Branch:** `fix/nfl-props-other-markets`.
**Status:** Implementation approved for completion by the owner on 2026-10-22.
Built and verified locally. Merge approval and push approval remain separate;
hosted deployment has not been verified.

- Added `/nfl/line-only-props?season=...&week=...`, using three bounded
  repository reads and the existing game-page response assembly. No modelled
  slate report is built by this endpoint.
- NFL Props includes these markets in its tabs, with separate recent-results
  counts, game/position filtering, game links, and the shared game-page tables.
  Long alternate lists wrap so every rung remains visible.
- `npm.cmd --prefix web run verify`: 52 test files, 706 tests passed;
  typecheck and production build passed. Vite retains its large-bundle warning.
- `.venv\Scripts\python.exe -m pytest` from `api/`: 3,614 tests passed,
  with the existing Starlette/AnyIO deprecation warning.
- Live API parity: all 208 raw line rows across eight Week 7 games exactly
  matched the individual game endpoints, including recent history and alternates.
  The live board showed 56 grouped rows across six available extra markets.
- Browser: passing-TD and kicking tabs, K position filter, NE at CHI game
  filter (two kicking-point rows), and linked game-page tables checked.
  Week 8 requested the correct season/week and showed its empty state.
- Browser fixtures: a game with only line-only props remained accessible;
  an empty position showed the empty state; an injected 503 showed Retry
  and recovered successfully. Expected console errors occurred during the
  injected failure; the final live load had no console errors.
- Desktop and 390px mobile layouts checked; no mobile horizontal overflow.
  Screenshots: `.playwright-mcp/nfl-props-other-desktop.png` and
  `.playwright-mcp/nfl-props-other-mobile.png`.
- Existing Rec Targets exclusion is covered by the new helper test and
  the passing existing reference-path tests. No live Rec Targets lines were
  available in this sample. No open/fixed P0 or P1 ledger findings exist.
- The pre-existing `project-overview.md` changes were preserved. The interview
  guide needs no claim change for this display-access fix.

**Try:** Open `http://127.0.0.1:3001/#/nfl/board`, select Pass TDs or
Kicking points, then choose a position or game. The added markets show
lines, alternates and recent results without model scores.

## Completion review (2026-10-22)

- Final invariants review: clean. NFL sport/regular-season/market filters,
  strict pre-kickoff snapshots, prior-week stats, gray references, repository
  SQL boundaries, and lightweight request assembly are preserved.
- No model, fit, grading, holdout, schema, secret, or workflow changes.
- No blocking P0/P1 findings. The two unverified ledger leads stay unchanged.
- Pre-existing overview edits are excluded from the fix commit.
- Implementation and verification details above are the completion evidence.

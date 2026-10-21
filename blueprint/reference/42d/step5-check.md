# 42d Step 5 opponent evidence check

Date: 2026-10-21. Running Vite app, isolated headless Edge, fixed HTTP fixtures.
No shared database or live provider calls. Values in captures are illustrative.

All 48 cases passed: 12 fixture cases from both board and game entry points,
at 1440px and 390px. `step5-browser.cjs` records the repeatable browser check.

| Cases | Observed result |
|---|---|
| Points, rebounds, assists, made threes, blocks | Correct opposite team, allowed value and rank population; zero remains 0.0 |
| Combined points/rebounds/assists and double-double | Explicit unsupported-market explanation |
| Missing line team | Explanation, without guessing an opponent |
| Missing context | Unavailable message |
| No prior games | Null rate and explicit no-history note |
| Partial assists and missing blocks | Correct counted games and coverage/small-sample notes; missing blocks remain unavailable |

For every case, board/game opponent text matched. Injury evidence remained
visible. Opening/closing drawers made no extra requests and preserved player
row order. Enter opened the drawer; Escape closed it and restored focus to the
same player button. There were no page runtime errors or opponent-section
horizontal overflow.

The game containers needed the board's existing focus-restoration workaround;
the final run verifies the repair for both modelled and line-only rows. Fixture
state changes now use full document navigation to avoid TanStack Query reusing
a previous case's cached response.

- [Board, assists, desktop](step5-board-assists-loaded-1440.png)
- [Game, assists, phone](step5-game-assists-loaded-390.png)
- [Game, partial sample](step5-game-assists-partial-1440.png)
- [Board, missing team](step5-board-assists-unknown-390.png)
- [Board, double-double](step5-board-double_double-loaded-390.png)

To repeat, use an installed `playwright-core` or set `PLAYWRIGHT_MODULE` to an
existing module directory. With Vite running, from the repo root:

```text
node blueprint/reference/42d/step5-browser.cjs
```

Final Verify after the focus repair: 700 web tests, production build and
3,611 API tests passed. Existing Vite bundle-size and Starlette/AnyIO warnings
remain. Mechanical design checks returned no findings. Final real-data and
error/retry checks remain Step 6.

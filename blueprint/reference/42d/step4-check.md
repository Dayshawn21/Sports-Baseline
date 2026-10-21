# 42d Step 4 game-page table check

Date: 2026-10-21. Running Vite app on localhost:3001, separate headless Edge.
Fixed HTTP responses exercised the actual NBA game route and shared shell.
Illustrative values are fixtures, not observed NBA statistics.

| State | 1440px | 390px | Observation |
|---|---|---|---|
| Loaded | Pass | Pass | Two tables, five measures, for/allowed values and ranks; true zero shows 0.0 |
| No prior games | Pass | Pass | Both teams retained; explicit no-history note, null rates and zero samples |
| Partial | Pass | Pass | Missing blocks remain unavailable; assists show 2/10 games, partial coverage and small sample |
| Context unavailable | Pass | Pass | Explicit unavailable message; rest of the game page remains visible |

All eight cases had no page/table horizontal overflow and no page runtime
errors. Measured text within the new table was at least 11px. Tables stack on
phones. The component follows injuries; existing loading/error branches were
unchanged. Final real-data and error/retry checks remain Step 6.

- [Loaded desktop](step4-loaded-1440.png)
- [Loaded phone](step4-loaded-390.png)
- [Partial phone](step4-partial-390.png)
- [Empty phone](step4-empty-390.png)
- [Unavailable phone](step4-missing-390.png)

`step4-browser.cjs` captures the four states at both widths. Reuse an installed
`playwright-core`, or set `PLAYWRIGHT_MODULE` to an existing module directory;
it launches its own headless Edge and does not touch a shared browser profile.
Run from the repo root with Vite already running:

```text
node blueprint/reference/42d/step4-browser.cjs
```

Impeccable detector returned `[]` for the changed UI. Final Verify passed:
679 web tests, production build, 3,611 API tests. Existing Vite bundle-size
and Starlette/AnyIO deprecation warnings remain.

# Feature 43, Step 3 review evidence

Implemented and verified locally on 2026-10-22 on
`feature/nfl-matchup-usage-context`. Steps 1-2 approved; Step 3 awaits owner
review. Drawer integration and the final resource/feature pass remain pending.
No commit, push, deployment, shared writes, provider calls or holdout scoring.

## Changed files

| File | Purpose |
|---|---|
| `web/src/types/nfl.ts` | Typed context metrics, allowed measures, usage windows, players and response; optional additive notes context preserves existing consumers. |
| `web/src/api/nfl.ts` | Typed GET transport for a game's context. |
| `web/src/hooks/useNfl.ts` | One game-ID query key, valid-ID enabling, deliberate five-minute stale time and manual retry. No per-player queries or placeholder data. |
| `web/src/pages/NflGamePage.tsx` | Mounts the context after existing team stats and passes notes context as a fallback; existing market, stats and props remain. |
| `web/src/components/nfl/NflTeamStatsMatchup.tsx` | Adds a separately exported position-allowed table using the existing card/table conventions; original team stats stay intact. |
| `web/src/components/nfl/NflGameContext.tsx` | Game query/state orchestration and native roster disclosure. Full QB/RB/WR/TE roster, player links, historical team changes and season target/carry shares. QB target share is marked not applicable. |
| `web/src/components/nfl/NflContextMetric.tsx` | Shared rendering of value, sample/coverage, observed dates and unavailable reason. |
| `web/src/components/nfl/nfl-matchup-context.css` | Scoped table and disclosure styling from existing tokens, 11px floor, numeric alignment, keyboard focus and 390px wrapping. |
| `web/src/utils/nflMatchupContext.ts` | Pure display formatting, unavailable explanations, fixed UTC date handling and complete roster ordering. |
| `web/src/utils/nflMatchupContext.test.ts` | 18 cases covering missing versus zero, partial coverage, actual rank denominators, UTC/invalid dates, unavailable reasons and stable non-mutating ordering. |
| `blueprint/context/current-feature.md` | Records Step 2 approval and Step 3 evidence; leaves Step 3 unchecked pending review. |

`step-3.diff` is incremental from the approved Step 2 working state and excludes
pre-existing planning edits and Steps 1-2 product changes.

## Running-app check, Step 3 only

Used the existing Vite and API servers. The app uses HashRouter; the tested
route is `http://localhost:3001/#/nfl/game/94`. An isolated headless Edge instance
used the already installed Playwright package. No browser/test dependency was
added. Real game data was read from the local API; controlled cases intercepted
responses only inside isolated browser contexts.

| Done-when | Result and observed evidence |
|---|---|
| Both teams' values and ranks | Pass. All 16 displayed allowed values matched the stored response, including returned ranked-team counts. `step-3-desktop-context.png`, `step-3-mobile-context.png`. |
| Samples and actual dates | Pass. Metric-specific observed/eligible games, percentages and contributing UTC dates are visible with the values; no hover-only evidence. |
| Full deterministic roster and links | Pass. All 39 names matched response order, all hrefs matched player IDs; pure ordering tests pin team/name/ID order without selecting by metric magnitude. `step-3-desktop-usage.png`, `step-3-mobile-usage.png`. |
| Desktop and 390px | Pass. Full-page and focused captures at 1440 and 390 CSS pixels. Expanded mobile document width = viewport = 390px, minimum context text = 11px. |
| Neutral display | Pass. Numeric context values compute to rgb(245,245,247), the existing primary gray/white text token. No signal colors, trend arrows, delta sorting or projection changes. |
| Loading | Pass. Delayed context response shows the shared loading state, announced through role=status; notes-supplied matchup remains available. `step-3-loading.png`. |
| Error and manual retry | Pass. Controlled 503 produces the existing local ErrorState. One failed request until keyboard Retry; second attempt recovers roster content and removes the error. `step-3-error.png`. |
| Empty/unavailable | Pass. Empty roster explanation and all 16 no-history fields are shown; no zero fabrication. `step-3-unavailable-empty.png`. |
| Zero/partial coverage | Pass. Controlled observed 0.0% at 1/2 games (50%) remains distinct from unavailable carry share with a zero team total. `step-3-zero-partial.png`. |
| Existing market/team stats retained | Pass. Existing sections remain in both full-page captures. Data path/legacy calculations were not edited. |
| One context query | Pass. One browser context request for 39 rows; the notes response supplies fallback matchup data. Query key is ready for reuse by Step 4. |

Raw assertions: `step-3-browser.json`. Reproduction driver:
`check-game-context-ui.cjs` (run at repo root, with PLAYWRIGHT_MODULE pointing
to an existing Playwright installation). Captures are in this directory.

The normal page had no JavaScript/application console errors. It did report
the existing `http://localhost:3001/favicon.ico` 404, recorded separately in the
raw report. The controlled 503 is expected fixture behavior, not a live outage.
The first element captures had sticky navigation overlap; final focused captures
use full-document clips and were visually validated before independent review.

## Verify and independent review

Documented Verify run in PowerShell halves:

1. `npm.cmd --prefix web run verify`: typecheck, all 724 web tests and production
   build pass. npm.cmd avoids the execution-policy restriction; esbuild used
   approved filesystem access.
2. From `api/`, `.venv\Scripts\python.exe -m pytest`: all 3,669 API tests pass.
3. `git diff --check`: pass.

Existing warnings remain: Vite's bundle-size advisory and Starlette's anyio
alias deprecation. No configured check was skipped.

Impeccable detector ran once on the changed component/CSS targets: `[]`.
Fresh independent finish review: **ship for the Step 3 addition**, no material
fixes. See `step-3-ui-review.md`. The independent documentation handoff confirms
this ordinary extension preserves the existing visual system; no new design
system files were created.

## How to try

Open `http://localhost:3001/#/nfl/game/94`. Below Team stats, compare NE and CHI
in Position production allowed. Expand Season usage shares to see the full
roster and open any linked player. Repeat at a 390px viewport, or focus the
disclosure and press Enter. The real stored response has partial coverage,
including TE measures, rather than a uniform assumed 32-team sample.

Step 4 will put this same cached context into the shared evidence drawer.
Broader current-data sampling, allocation checks, drawer parity and the ignored
employer-guide update remain in Step 5's final feature pass.

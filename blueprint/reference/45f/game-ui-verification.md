# 45f Step 6: NHL game context

Local acceptance on 2026-10-24 uses the real Vite app, Playwright and controlled
API responses. Migration 0050 remains unapplied by this work. These observations
do not establish real stored-context or deployment acceptance.

## Changes for review

| File | Purpose |
| --- | --- |
| `web/src/components/nhl/NhlGameContext.tsx` | Starting goalies and both team injury lists, with independent source/fetch/freshness labels and explicit empty/unavailable states. |
| `web/src/pages/NhlGamePage.tsx` | Place context after existing market/history in Matchup; pass the same page clock used for game state. Player Props remains the default tab. |
| `web/src/pages/nhl-game.css` | Extend existing gray styles; two team columns on desktop, stacked teams on phone, source metadata at least 11px. |
| `web/src/utils/nhlContext.ts` | Format valid source timestamps without a fetch-time substitute; label unresolved identities and source/roster team disagreement. |
| `web/src/utils/nhlContext.test.ts` | Six additional fixed-input cases for source text, timestamps, unresolved identity and missing optional fields. |

Incremental local diff: `output/45f-step6.diff` (189 lines, five product files).
The slate UI and backend were not changed by this step.

## Observed checks

The initial browser clock was fixed at 2026-10-24 19:00 UTC. An upcoming
TBL/CHI fixture had fresh goalies and stale injuries, with eight away injuries
and one home injury. The source names/statuses/details are controlled examples.

| Criterion | Observed result |
| --- | --- |
| Both teams | Expected away and Confirmed home goalies; eight away and one home injury shown. No list truncation. |
| Source provenance | Each feed has its own ESPN fetch time and freshness; separate source update time. Injury rows retain their source update and reported return-date text. Missing update time says unavailable. |
| Unresolved identities | Long source injury name remains visible with unresolved and team-disagreement labels. Changed unresolved goalie name remains visible too. |
| Status fidelity | Injury Out/Questionable and goalie Unknown status: Questionable remain text; unknown goalie is not upgraded to Expected/Confirmed. |
| Changed goalie | Refreshed fixture replaces both old names with Changed Source Goalie / unknown and a home Not reported. Neither prior goalie name remains. |
| Empty report | Each team shows zero reported and No injuries reported by ESPN. |
| Unavailable report | Known batch times remain visible, but goalie names disappear and each injury team says Injury report unavailable. No zero or empty-report claim. |
| Missing context / TBD | Entirely omitted context falls back to unavailable safely; missing start shows Time TBD and unavailable reports. |
| Historical | Browser clock moved to November 1 for the completed October 24 game. Historical Source Goalie remains visible with Fresh at the exact six-hour pre-start boundary; Final / OT and 3-2 score remain. |
| Desktop / phone | Populated and changed/empty cases captured at 1440px and 390px. Document scroll widths 1425px and 375px; no horizontal page overflow. Minimum computed context font 11px. |
| Default / refresh | Direct game navigation and repeated full refreshes select Player Props. No context request is added; it arrives in game detail. |
| Props parity | Names remain Alex Source, Zach Source, Alex Source across Shots on Goal then Points. Lines remain 2.5, 3.5, 0.5; counts remain total 3 and one Standard, Goblin and Demon. |
| Market parity | Entire rendered market text equals the before-change capture: puck line CHI +1.5 (-180), total 6.5, moneyline CHI +120 / TBL -135, market probabilities 44.0% / 56.0%, book attribution and fetch labels unchanged. |
| Navigation | Keyboard activation selects Matchup. Back link returns to /nhl?date=2026-10-24. |
| Loading / error / retry | Held detail request shows Loading NHL game. Three controlled 503 attempts lead to the existing error/retry state; clicking Retry recovers to the default Player Props tab. |

No page exceptions occurred during the populated/state-change browser check.
The failure check intentionally generated three 503 responses. The initial
keyboard probe used an exact tab name; Ant Design adds a positional accessibility
announcement on focus, so the probe was corrected to match the tab's label.
No app repair was required.

## Artifacts

Local ignored artifacts:

- Before-change capture: `output/45f-step6-before-desktop.png`.
- Populated captures: `output/45f-step6-desktop.png`, `output/45f-step6-phone.png`.
- Changed goalie / empty injuries: `output/45f-step6-empty-1440.png`,
  `output/45f-step6-empty-390.png`.
- Repeatable controlled browser harnesses: `output/45f-step6-browser.cjs` and
  `output/45f-step6-retry.cjs` (the second continues from the first's fixtures).
- Full gate log: `output/45f-step6-verify.log`.

The manual Impeccable detector ran once for the three UI targets and returned
`[]`. Visual inspection found no changes requiring a second polish pass.

## Automated gate and limits

Focused NHL helper/display tests: 65 passed. The exact documented root Verify
command passed with the API venv on PATH:
`npm --prefix web run verify && cd api && python -m pytest`.
Typecheck, 903 web tests, production build and 4,462 API tests passed. Existing
Vite bundle-size and Starlette deprecation warnings remain. Incremental source
whitespace and `git diff --check` pass.

No migration, shared snapshot write, provider fetch, workflow dispatch,
commit, push or deployment occurred in this step. Shared PostgreSQL and deployed
context acceptance remain pending, as in earlier evidence.

## How to try

Review the linked screenshots and incremental diff for fixture states. With
the API and web dev server running, open `/#/nhl/game/<gameId>` and choose
Matchup. Player Props should be selected on direct navigation/refresh. A live
populated context display requires migration 0050 and stored pre-start snapshots;
without the migration, existing nonempty API reads return the explicit 503.

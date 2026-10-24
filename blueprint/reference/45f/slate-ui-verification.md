# 45f Step 5: NHL slate context

Verified locally on 2026-10-24, with the real Vite app and controlled API
responses. This is browser acceptance of the display contract, not live
PostgreSQL or deployed acceptance. Migration 0050 remains unapplied by this work.

## Changes for review

| File | Purpose |
| --- | --- |
| `web/src/types/nhlContext.ts` | Exact injury, goalie, source and link-reason transport types. |
| `web/src/types/nhl.ts` | Require context on slate games and inherited detail responses. |
| `web/src/utils/nhlContext.ts` | Derive independent freshness, CT fetch labels, goalie labels and injury counts; distinguish zero from unavailable. |
| `web/src/utils/nhlContext.test.ts` | Nineteen fixed-clock cases for report age, historical cutoff, missing/invalid/future timestamps, unknown status, unresolved names, independent feeds and empty reports. |
| `web/src/utils/nhlSlate.ts` | Prepare context alongside the existing market cells, without new requests. |
| `web/src/utils/nhlGame.test.ts` | Extend the existing typed fixture with explicit unavailable context. |
| `web/src/components/nhl/NhlSlateContext.tsx` | Compact goalie and injury sections with separate source/fetch/freshness labels. |
| `web/src/components/nhl/NhlSlateTable.tsx` | Add a context row below each game; retain the seven market columns and existing game link. |
| `web/src/pages/nhl-slate.css` | Use existing gray tokens and fonts, two sections on desktop and stacked sections at phone width. |
| `web/src/pages/NhlSlatePage.tsx` | Explain that ESPN reports may miss late changes. |

Incremental diff: local `output/45f-step5.diff` (357 lines, ten product files).
No backend, query-hook, model, market or recommendation changes in this step.

## Browser evidence

The Playwright check uses a fixed browser clock of 2026-10-24 19:00 UTC.
Four controlled games cover these cases together:

| Criterion | Observed result |
| --- | --- |
| Expected / Confirmed | Source names and explicit text labels visible for both teams. |
| Fresh / stale independently | Stale goalie report alongside fresh injuries; fresh goalies alongside stale injuries. Stale values remain visible. |
| Unresolved identity | Long source goalie name retained with `Unresolved identity`; wraps at phone width. |
| Unknown status | `Unknown status: Questionable` remains distinct from Expected and Confirmed. |
| No announcement | `Not reported` appears without an older goalie name. |
| Empty injuries | Team counts are zero and `No injuries reported by ESPN.` appears. |
| Missing / TBD | Both feeds show `Unavailable`, not zero counts or an availability claim. |
| Provenance | Independent ESPN fetch timestamps include date, year and CT. Missing times have explicit text. |
| Desktop | 1440px viewport, document scroll width 1425px, all seven market columns retained. |
| Phone | 390px viewport, document scroll width 375px, no horizontal page overflow. |
| Legibility | Minimum computed context font size 11px. Source text contrast 5.32:1, body text 6.96:1 against the existing card background. |
| Search | Desktop and phone team search filters the slate; unmatched search gives the existing no-results state; Escape clears/closes phone search. |
| Dates | Next/Previous update hash date, displayed calendar date and requested API date. |
| Game navigation | Keyboard Enter opens game 1; keyboard focus has the existing 2px outline. Clicking the context row on phone also opens the game. Player Props remains the default. |
| Loading / empty / failure | Held request shows loading; empty response shows no-games copy; controlled 503 shows the existing retry control. |

Screenshots (local ignored artifacts): `output/45f-step5-desktop.png` and
`output/45f-step5-phone.png`. Browser harnesses:
`output/45f-step5-browser.cjs` and `output/45f-step5-interactions.cjs`.
The latter continues from a populated slate. The desktop keyboard/date checks
were also exercised through the Playwright tool directly.

There were no page exceptions in the populated-slate capture. The initial
browser harness incorrectly intercepted Vite source-module paths; it was
corrected to intercept only URL paths beginning `/api/` before acceptance.
The controlled failure check intentionally generated three 503 responses
through the existing query retry policy.

Impeccable's manual detector ran once against the changed UI targets and
returned `[]`. Existing tokens and the incumbent slate layout were retained.

## Automated checks and limits

Focused helper/existing NHL display tests: 59 passed. Production build passed.
Final gate is the documented root Verify command with API venv on PATH:
`npm --prefix web run verify && cd api && python -m pytest`.
The final result is recorded in the active spec and local
`output/45f-step5-verify.log`.

Shared migration, real stored-context acceptance, workflow activation and
deployment remain pending. Opening a live slate with games before applying
0050 produces the explicit API error established in Step 4. No new shared DB
writes or provider requests were needed for these UI checks.

## How to try

Review the linked screenshots and incremental diff for the controlled states.
For the live app, start the API and `npm run dev` in `web/`, then open
`http://localhost:3001/#/nhl?date=2026-10-24`. Real context needs migration 0050
and snapshots; without them this is not a populated-context demonstration.

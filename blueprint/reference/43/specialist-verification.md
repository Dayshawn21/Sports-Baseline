# Step 4b: kicker and punter game-log repair

Owner-requested amendment implemented locally 2026-10-22; awaiting review.
No commit, model/settlement change, provider call, migration or shared DB write.

| File | Change and reason |
|---|---|
| api/app/core/nfl_player.py | Optional raw specialist counts on PlayerGameRow; old callers retain nullable defaults. |
| api/app/repositories/nfl.py | Select FG/PAT/punts from existing weekly stats; preserve null versus zero. |
| api/app/schemas/nfl.py | Add nullable game-log fields with camelCase aliases. |
| api/app/services/nfl/player_detail.py | Expose counts, compute kickingPoints through existing item 34 line_only_value rule. |
| api/tests/test_nfl_player_detail_service.py | Five cases: counts, 3FG+PAT, zero, either missing input, punter count. |
| api/tests/test_nfl_repository.py | Extend SQL/mapping fixture for count selection and null/zero preservation. |
| web/src/types/nfl.ts | Typed nullable API additions. |
| web/src/utils/nflPlayer.ts | Specialist identity/columns and encoded market URL contract. |
| web/src/utils/nflPlayer.test.ts | Three cases for position boundaries, column/market mapping and link encoding. |
| web/src/components/nfl/NflPlayerGameLog.tsx | K: FG/PAT/Kicking pts; P: Punts. Hide offensive columns/PP fantasy for K/P. Matching specialist query highlights the header and scrolls log into view. |
| web/src/pages/NflPlayerPage.tsx | Hide offensive snap-share tile and usage chart for K/P. |
| web/src/components/nfl/NflLineOnlyProps.tsx | Player link carries selected market and game-log anchor. No new drawer. |
| web/src/pages/nfl-player.css | Neutral underline for selected market header using incumbent tokens. |
| blueprint/context/current-feature.md | Owner-approved scope and implementation evidence, pending review. |

## Proof

`npm.cmd --prefix web run verify`: typecheck, **758 tests**, build pass.
From api, `.venv\Scripts\python.exe -m pytest`: **3,674 passed**.
First API run exposed an old repository fixture lacking new selected columns;
fixture was updated and final full gate passed. Existing Vite bundle-size and
Starlette deprecation advisories remain. Detector on UI targets ran once: `[]`.

`check-specialist-player.cjs` / `specialist-browser.json`: real Andy Borregales
40440, Week 6 **2 FG, 2 PAT, 8 kicking points**, and five other current games.
All kicker log values come from updated read-only API. Clicked Kicking points
Other markets link; query/selected header verified. Captured desktop1440/phone390.
Controlled punter response proves only Punts column, observed 4 and unavailable
missing value. A QB page retains usage and PP fantasy. No horizontal page
overflow or application JavaScript errors at either width. Screenshots:
`specialist-{1440,390}-{kicker,punter}.png` (full page, document top).

Missing specialist stats remain unavailable (`--`) rather than invented zeros.
The empty offensive sections are removed. Existing past-line records and the
main-feed-only This week's lines card are outside this game-log repair; this
step does not add line-only drawers, current-week line-only cards or change
fantasy grading. Optional market emphasis currently matches specialist columns.
No employer-guide claim changed by this small repair; feature-wide guide update
remains Step 5.

Try http://localhost:3001/#/nfl/player/40440?market=kicking_points#game-log
or Player Props > Other markets > Kicking points > Andy Borregales on game94.
Review incremental `specialist.diff`. Final feature verification remains pending.

Independent UI disposition: **ship**, no material fixes. Reviewer inspected all
four captures, source and browser report; verified specialist columns, null
presentation, neutral market emphasis and incumbent composition. Documentation
handoff checked PRODUCT.md, mappings/types and the same evidence: ordinary
extension, no design-system changes required. No deployed claim follows.

# Feature: NHL rows on the shared shape

**From build-plan:** feature 57c (parent 57, One slate shape for every sport)
**Branch:** `feature/57c-nhl-slate-rows` (cut from `master` at `5133dfd6`)
**Status:** complete 2026-11-08 (win label keeps one decimal; tag wording as drafted)

## Goal

The NHL slate (`/nhl`) shows one dense row per game, on the same table as NFL
and NBA. Today each NHL game is a tall block: every market cell repeats its
book and fetch time, and a second "context" row lists both starting goalies,
injury counts and two ESPN source lines. After 57c a row reads like an NBA row:
puck drop, game, puck line, total, moneyline, the market win probability, prop
count, and short gray note tags for goalies and injuries. Full context stays on
the game page, one click away.

## Design reference

No new visual target. The NBA slate table (38c2,
`web/src/components/nba/NbaSlateTable.tsx`) is the shape to match: it already
renders on the NFL table's classes. The 2026-11-08 critique (finding 4: "NHL
repeats source and timestamp in every cell"; fix: "move NHL onto the NFL/NBA
row shape, with provenance once in the legend and goalies as note tags") and
the slate surface brief `.impeccable/surfaces/web-src-pages-nflintelligencepage-tsx.md`
set the direction.

## In scope

- **The NFL/NBA table.** `NhlSlateTable` renders on `nfl-slate-table` classes
  with NBA's columns: `Puck drop` Â· `Game` Â· `Puck line` Â· `Total` Â·
  `Moneyline` Â· `Win` (small "market") Â· `Props` Â· `Notes`. A row opens the game
  page, and the Game link still has its own label, as today.
- **Market cells: value and detail only.** Each cell keeps the line it shows
  today (for example `BOS -1.5 (+180)` over `FLA +1.5 (-222)`) and drops the
  book name and fetch time. A missing market stays `--` with "Not stored".
- **Win column.** The market's de-vigged win probability for the favorite,
  muted, NBA style: `BOS 56.4%`. `--` with no moneyline, and on final,
  postponed or canceled games, as NBA does. The value is
  the same number the page shows today; only the underdog's complement is
  dropped (open question 1).
- **Note tags, gray.** Built by a new pure `nhlNoteTags(context)` from the
  existing `nhlSlateContext` result:

  | Report state | Tags |
  |---|---|
  | Goalie expected or confirmed | `FLA G Markstrom` + `exp.` or `conf.` (one tag per team, e.g. `FLA G Markstrom exp.`) |
  | Goalie not reported | none for that team |
  | Goalie name without a linked player | the name as reported, with `?` (`FLA G Markstrom? exp.`) |
  | Injuries reported | `BOS 3 inj.` per team with at least one |
  | No injuries reported | none |
  | Goalies or injuries report stale | one `reports stale` tag |
  | One report unavailable | `no goalie report` or `no injury report` |
  | Both reports unavailable | one `no ESPN report` tag, not two |
  | Game final, postponed or canceled | no tags (pre-game reports no longer matter) |

  Tags use the shared gray `nfl-slate-card__tag` style. Never green or red.
- **State in the time cell.** As today, the puck-drop cell carries the state
  label under the time (`Scheduled`, `Puck dropped`, `Final / OT`). Final rows
  show the score in the Game cell, as today.
- **The context row and its component go.** `NhlSlateContext.tsx` and the
  `.nhl-slate-context*` and `.nhl-slate-source` styles are deleted; nothing else
  uses them. `nhl-slate.css` shrinks to NHL-only column widths and phone rules,
  like `nba-slate-table.css`.
- **Provenance in the legend.** With no book in the cells, the NHL legend's
  disclosure (57b content) names the book order once: "Prices are stored book
  prices: DraftKings, else the latest of FanDuel and bet365." This is the rule
  the API already applies (`_CHOSEN_ODDS` in `api/app/repositories/nhl.py`).
  The legend line itself is unchanged, so its two-line phone fit holds.

## Out of scope

- **57d:** anything on the tennis slate.
- Grouping NHL games by start window (NBA isn't grouped either; a separate call
  for the whole of 57 if wanted).
- The NHL game, player, props and model pages, including how the game page shows
  goalies, injuries and per-market book and time (it keeps them).
- Any API change, any new field, any change to which book or price is chosen.
- Final-game cell content (the closing lines shown today stay as they are).

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Tags and win label, tested, unused.**
  - In `web/src/utils/nhlSlate.ts`: `nhlNoteTags(context, state)` and
    `nhlWinLabel(game, state)` as pure functions (the state hides tags and the
    win label on final, postponed and canceled games).
  - New `web/src/utils/nhlSlate.test.ts` covering every row of the tag table and
    the win label's favorite, even, and no-moneyline cases.
  - Record the baseline: at 375px and 1440px, the `/nhl` table height and the
    first row's height (screenshots in the step notes).

  *Done when:* the new tests pass, Verify's web half passes, and `/nhl` renders
  exactly as before.
- [x] **Step 2 - The row on the shared table.**
  - `nhlSlateRow` returns a typed `NhlSlateRowModel` (see Data / contracts)
    using the step 1 helpers.
  - `NhlSlateTable` renders it on the NFL table classes with the NBA columns and
    Notes tags.
  - Delete `NhlSlateContext.tsx` and the context and source styles; rewrite
    `nhl-slate.css` to column widths and phone rules.

  *Done when:*
  - each `/nhl` game is one row at 1440px with no book name or fetch time in it
  - a row with a reported goalie shows that goalie's tag; a stale or missing
    report shows its one tag
  - clicking a row or the Game link opens `/nhl/game/:id`
  - search still filters the rows
  - the empty day still names the next slate
- [x] **Step 3 - Legend sentence and check.**
  - Add the book-order sentence to the NHL legend content.
  - Desktop 1440px and phone 375px, compared with the step 1 baseline.

  *Done when:*
  - the NHL disclosure names DraftKings, FanDuel and bet365 once; the legend
    line is still two lines at 375px
  - the `/nhl` table at 375px is at least 40% shorter than the baseline for the
    same date
  - no page scrolls sideways, no text is under 11px, every tag is gray
  - the 57b legend tests still pass (no clock time in legend text)
  - Verify passes

## Files / areas

- **Logic:** `web/src/utils/nhlSlate.ts`; new `web/src/utils/nhlSlate.test.ts`.
- **Table:** `web/src/components/nhl/NhlSlateTable.tsx`; delete
  `web/src/components/nhl/NhlSlateContext.tsx`.
- **Styles:** `web/src/pages/nhl-slate.css` (rewritten small); the table imports
  `nfl-slate-card.css` and `nfl-slate-table.css` as NBA's does.
- **Legend:** `web/src/utils/slateLegend.ts` (one NHL pick sentence).
- **Unchanged:** `NhlSlatePage.tsx` (it already passes rows to the table),
  `nhlContext.ts`, `nhlGame.ts`, and every game-page component.

## Data / contracts

- **No API change.** Every value comes from `NhlSlateGame`, which the page
  already loads.
- **Row model (local to the NHL slate, mirrors `NbaSlateRowModel`):**

  ```ts
  interface NhlSlateRowCell { value: string, detail: string | null }
  interface NhlSlateRowModel {
    gameId: number
    state: NhlGameState
    puckDrop: string
    stateLabel: string
    away: { code: string, name: string, score: number | null }
    home: { code: string, name: string, score: number | null }
    puckLine: NhlSlateRowCell
    total: NhlSlateRowCell
    moneyline: NhlSlateRowCell
    /** Favorite's de-vigged market win probability; null without a moneyline. */
    win: string | null
    props: number
    tags: string[]
  }
  ```

  Not load-bearing beyond the NHL slate; 57d does not read it.

## Testing

- **Unit tests (Vitest, `nhlSlate.test.ts`):**
  - `nhlNoteTags`: expected and confirmed goalies, not reported, an unlinked
    name, injuries on one side and both, no injuries, a stale report, one report
    unavailable, both unavailable (one tag, not two), and a final game (none)
  - `nhlWinLabel`: home favorite, away favorite, a 50/50 game, no moneyline, a
    final game
  - fixed `now` and start times, per the coding standards
- **Not unit-tested:** `NhlSlateTable` and the page. They get browser and
  screenshot evidence in steps 2-3.
- **Gate:** the Verify command (`npm --prefix web run verify && cd api && python -m pytest`).

## Notes for the AI

- **Display only.** No probability, edge, rank, sort or pick changes. The win
  label is the same de-vigged number, shown for the favorite. All tags gray.
  11px floor, `CT` times.
- **Reuse, don't recompute:** `nhlSlateContext` already ages reports (the 6-hour
  stale rule and "fetched after start" rule live in `nhlContextFreshness`);
  `nhlGoalieLabel` already maps statuses. Tags read their output.
- **Copy NBA, not NFL.** NBA's table is the closer model (no model column, a
  muted win column). Reuse its classes and the shared tag style; do not fork
  `nfl-slate-table.css`.
- **Unlinked goalie identity:** the slate shows `?`; the game page keeps the
  full "Unresolved identity" wording.
- **Coordination:** 57d touches the tennis page and `slateLegend.ts`'s tennis
  entry only. Build 57d after 57c merges.

## Open questions for review

1. **Win column format.** The draft shows the favorite only, keeping one
   decimal (`BOS 56.4%`). NBA shows the favorite in whole percent (`BOS 56%`).
   Match NBA exactly, or keep NHL's decimal?
2. **Tag wording.** `FLA G Markstrom exp.`, `BOS 3 inj.`, `reports stale`, `no
   ESPN report` are first drafts. Adjust before step 1 if you want different
   abbreviations.

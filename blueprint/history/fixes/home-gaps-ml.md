# Fix: Home gaps for tennis props and a Moneyline view

**Type:** Fix (one section of one page; no endpoint, model or rule change)
**Follows:** fix `home-gaps-tabs` (merged and pushed as `88566150`)
**Status:** complete (2026-11-04)
**Proposed branch:** `fix/home-gaps-ml` (this worktree `.claude/worktrees/home-gaps-tabs-c899fe`, cut from `master`)

## The problem

After `home-gaps-tabs`, "Largest gaps across sports" shows prop gaps for NFL
and NBA only. Tennis and NHL list next games. The owner wants props and
moneyline (ML) edges across sports wherever a model exists, still gray
reference and never picks.

What the code already holds (read before specing):

| Sport | Prop gap data | Win probability vs market |
|---|---|---|
| NFL | on the home today | `NflSlateGame.model`: `nfl-elo-v1` `homeWinProbability` and `marketHomeWinProbability`, already loaded by the home. Documented as display-only: it did not beat closing lines. |
| NBA | on the home today | none (game odds stored, no win model) |
| NHL | none (line-only props, no projection) | none |
| Tennis | PrizePicks lines carry `statAvg` (projection) and `edgePct` (projection minus line as a share of the line, documented "NOT a betting edge"), served by `/tennis/props/prizepicks` | `MatchPrediction.p1WinProb` (ensemble) and the book price; `moneylineBoardRows` already de-vigs it as reference only |

## Design reference

Existing look and tab strip from `home-gaps-tabs` (`web/src/components/home/home.css`).
No new visual language: the Props/Moneyline switch reuses the tab-strip
styling at a smaller size. If the owner wants a mockup first, say so at
review.

## Decisions fixed here (change them at review, not mid-build)

1. **A two-way switch above the sport tabs: `Props | Moneyline`.** The sport
   tabs (`All`, `NFL`, `NBA`, `NHL`, `Tennis`, with next-start text) stay as
   they are. Both choices live in the URL (`?kind=ml`, `?gaps=nfl`;
   Props and All are the defaults and are omitted). Changing one keeps the
   other. Unknown values read as the default.
2. **Tennis prop gaps join the Props view.** Rows come from the PrizePicks
   lines the tennis board already uses: `isTennisRateable`, standard payout
   only (no goblins or demons), the line's match is still to come, one row
   per player, ranked by `|edgePct|` (the same "share of the line" unit as
   the NFL rows), at most 10. Lines whose data-quality flags include the
   no-book-total flag (`no_market_total`) are left out: their projection ran
   on the model total, which ran low (48a). Columns match the NFL rows:
   Player, Sport, Market, Time, Line, Model (`statAvg`), Gap (`edgePct`).
   The row opens the tennis player page (`propPlayerPath`). Rows stay gray
   even when a slice has adopted: the home never colors or ranks by adoption.
3. **Moneyline view = win probability against the de-vigged market.** One row
   per game or match still to come, showing the side whose model probability
   differs most from the market's. Columns: Game, Sport, Time, Market %
   (that side), Model % (that side), Gap in percentage points. At most 10 per
   sport, ordered by `|gap|` within the sport.
   - **NFL:** from `NflSlateGame.model` (`nfl-elo-v1`). Footer note: "NFL
     win probability did not beat closing lines; reference only."
   - **Tennis:** the ensemble's `p1WinProb`/`p2WinProb` against the market
     probability de-vigged from both prices, as `moneylineBoardRows` does
     (extracted, not duplicated). Footer note: "The tennis ensemble is not
     ahead of the market; reference only." Matches without both prices or
     both probabilities are left out.
   - **NBA and NHL:** no win model, so their Moneyline tabs say so plainly
     ("NBA has no win-probability model, so there is no moneyline gap to
     show. Next games:") and list next games, the same body NHL has today.
4. **`All` stays grouped, never sorted across sports,** in each view: NFL,
   NBA, Tennis (NHL has none), each in its own order. A prop gap is a share
   of a line or points, a moneyline gap is percentage points of a different
   model's probability; they never share a sort.
5. **Gray means gray.** No EV, no tier, no pick label, no green, anywhere in
   either view. The panel note under the table keeps its wording and gains,
   in the Moneyline view, the one-line caveat for the tab's sport.
6. **Tennis tab:** Props view lists the tennis prop gaps (no longer the next
   games, which move to the tab's empty state: "No gap lines yet" plus the
   existing slate link). The NHL Props tab is unchanged (next games, with its
   plain "line-only" note).
7. **Time column** everywhere: a start time per row. NFL and tennis rows use
   `startLabel(start, now)` plus ` CT`; NFL and NBA digest rows keep their
   existing `when`.
8. **Data and cost.** No new endpoint. The only new request on the home is
   the existing `/tennis/props/prizepicks` via `usePrizePicksProps` (same
   query key as the tennis board, 10-minute stale time, so a visit to the
   board warms the home and the reverse). If that request fails, only the
   tennis prop rows are hidden ("Gap lines could not load.") and the games
   still count, as for NBA today. Step 1 measures the payload and the load
   time before the home adds it.
9. **Phone (as built: the Moneyline table hides Game, Market and Model; the Props table hides Market, Line and Model; a Side column leads the Moneyline table):** the switch and the tab strip each stay on one line without
   page-level horizontal scroll (the strip scrolls sideways as today). The
   Moneyline table hides nothing but Market at 640px (Game, Sport, Time,
   Model, Gap stay), checked at 375px.

## In scope

- Home gaps data layer: tennis prop gap rows, NFL and tennis moneyline rows,
  a `kind` switch in the view model and URL, the tab bodies for each
  combination, and the UI and CSS for the switch and the moneyline table.

## Out of scope

- Any new win-probability model (NBA, NHL), any model, rule, adoption or
  ranking change, any EV, tier or color, any new endpoint.
- Moneyline on the sport cards, a cross-sport sort, goblin or demon lines,
  adopted-slice highlighting on the home, pagination.
- Interview-guide edit (no model or validation claim changes).

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real commit at the end.

## Build steps

- [x] **Step 1 - Tennis prop gap rows (data layer)** - read the live
  `/tennis/props/prizepicks` response size and the flag name for "no book
  total"; widen `HomeGap.sport` to include `tennis`; a pure
  `tennisGapRows(props, predictions, now)` in `homeSources.ts` applying
  Decision 2; `tennisSource` fills `gaps`; `useHomeData` adds
  `usePrizePicksProps` and passes its failure to `gapsFailed`. *Done when:*
  tests prove standard-only, rateable-only, upcoming-only, one per player,
  `no_market_total` excluded, ordered by `|edgePct|`, capped at 10, and the
  row path and time; the payload size is recorded in the step summary; the
  existing home still renders; `npm run test` and `npm run build` pass.
- [x] **Step 2 - Moneyline rows (data layer)** - a `HomeMoneyline` row type
  and `moneyline: HomeMoneyline[]` on `HomeSource`; `nflMoneyline` (from
  `game.model`) and `tennisMoneyline` (de-vig extracted from
  `moneylineBoardRows` into one shared helper, behavior unchanged); NBA and
  NHL stay empty. *Done when:* tests prove the side with the larger `|gap|` is
  chosen, finished and started games are dropped, a missing price or
  probability drops the row, at most 10, ordered by `|gap|` per sport, and the
  existing `moneylineBoardRows` tests pass untouched.
- [x] **Step 3 - View model: the kind switch** - `GapKind` (`props | ml`),
  `parseGapKind`, `gapsBody(kind, tab, sports)` returning moneyline bodies, the
  "no win model" bodies for NBA and NHL, and the per-sport caveat text.
  *Done when:* tests prove parsing (absent and junk read as props), `All`
  groups NFL, NBA, Tennis in each view with no cross-sport sort, NBA and NHL
  Moneyline are `games` bodies with the plain sentence, a tennis Props tab with
  no rows says so, and the loading and error bodies still hold.
- [x] **Step 4 - UI** - the Props/Moneyline switch, the moneyline table, the
  caveat line, `hrefFor` building both URL params, CSS. *Done when* (browser,
  desktop): `/` opens on Props and All unchanged plus Tennis rows; the
  Moneyline switch shows NFL and Tennis rows with Time and Gap in points, NBA
  and NHL the plain sentence and next games; `?kind=ml&gaps=tennis` survives a
  reload and a row-open and Back; every row opens its page (NFL `/nfl/game/:id`,
  tennis match page or player page, NBA player page); no color on any gap; no
  console errors; `npm run build` passes.
- [x] **Step 5 - Phone and wrap-up** - 375px: switch and tabs on one line, no
  page-level horizontal scroll, Gap readable in both views. Run Verify.
  *Done when:* 375px and desktop screenshots for Props All, Props Tennis and
  Moneyline NFL; the full Verify command passes.

## Files / areas

- `web/src/utils/homeSources.ts` (+ test), `web/src/utils/home.ts` (+ test),
  `web/src/utils/tennisPropBoard.ts` (extract the de-vig helper only),
  `web/src/hooks/useHomeData.ts`
- `web/src/components/home/HomeGaps.tsx`, `web/src/components/home/home.css`,
  `web/src/pages/HomePage.tsx`
- `blueprint/history/fixes/home-gaps-ml.md` at `/complete`

## Data / contracts

- **Load-bearing:** `HomeGap` and `HomeSource` are home-internal; widening
  `sport` and adding `moneyline` break nothing outside the home. The
  de-vig helper extracted from `moneylineBoardRows` must keep that function's
  output identical (its tests are the guard).
- URL: `?kind=ml` and `?gaps=<sport>`, hash-router query as today.
- No API, schema, model version or rule changes.

## Testing

Gate is on; logic ships tests (Vitest, fixed `NOW`, no clock mocking).

- `homeSources.test.ts`: tennis gap rows, moneyline rows (NFL and tennis).
- `home.test.ts`: `parseGapKind`, bodies per kind and tab, `All` grouping.
- `tennisPropBoard.test.ts`: the extracted helper keeps `moneylineBoardRows`
  unchanged.
- Components and CSS ride on browser evidence at desktop and 375px, console
  clean. Run `npm ci` in `web/` first. Local API recipe: main checkout venv
  with the selector-loop launcher and `DATABASE_URL` from the main `.env`.
- Final gate: `npm --prefix web run verify && cd api && python -m pytest`
  (API tests need `DATABASE_URL=postgresql://localhost/ci`).

## Notes for the AI

- Gaps are gray reference, never picks. No EV, tier, pick wording or green.
- Never sort across sports; never rank tennis rows by adoption.
- No em dashes in code, comments, copy or the archive. Comment the why only.
- Reuse existing helpers (`isTennisRateable`, `propPlayerPath`,
  `enrichTennisPropLines`, `startLabel`); do not duplicate the de-vig math.
- Do not change `slateDigest`, `DIGEST_LIMIT`, the NBA gaps route or any model.
- Ask before committing; the project rule is no AI attribution in commit messages.

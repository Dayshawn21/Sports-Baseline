# Fix: Trim internal stats and model names from page heads

**Type:** Fix

**Completed:** 2026-11-13. Implementation approved by the user's `/complete` request.

## The problem

Page heads and projection cards show numbers a regular user can't use. Most
are counts of loaded data ("Player-market rows", "Scanned") or internal names
(`nba-reference-v1`, "P(over) version"). The rest repeat something the page
already shows: market counts are on the pills and tabs, and the sample size is
in the projection card. The useful facts (minutes, how many games a projection
rests on) end up buried among them.

Survey of every page head (stat strips appear on 11 of 26 pages; slates, game
pages, tennis match and player pages, home, tools and admin have none):

| Page | Head cards / fields | Change |
|---|---|---|
| NBA props, NHL props | Games, Player-market rows | Cut both; game count goes in the meta line |
| NFL props | Games, Rateable, Other markets | Cut all three; game count goes in the meta line |
| Tennis props | Available lines, Rated lines | Cut both (each pill already shows "N rated / N review") |
| Prop boards (all four) | Model version in the record strip | Cut the version; keep the record, slices and Model page link |
| NBA player | Games in sample, Avg minutes, Prop markets | Cut the strip; minutes go in the meta line |
| NHL player | Games in sample, Avg TOI, Prop markets | Cut the strip; TOI goes in the meta line |
| NBA, NHL, NFL, tennis player | "N markets" beside "Props on ..." | Cut (the tabs show them) |
| Projection card (all four sports) | Model, Sample (+ tennis Basis) | Cut Model and Basis; sample becomes a caption |
| NBA, NHL track record | Slices adopted, Last settled week, Projection version, P(over) version | Cut the two version chips |
| NFL track record | V4 slices adopted, Game-line verdicts, V4 last settled week, V4 projection version | Cut the version chip; drop the "V4" prefix from the rest |
| Bankroll Builder | Scanned, Singles, Parlays | Cut Scanned |
| NFL player | Games, focus/volume per game, Snap share | **Keep**: real production and usage |

## The fix

- Page heads become title plus one meta line wherever the strip goes away.
- `PlayerProjectionHero` drops the Model fact and gains a `sample` caption
  shown after the delta: `+3.1 vs 11.5 line · based on last 20 games`
  (tennis: `last N matches`). The tennis "Opp allows" fact stays and the
  priced-market "Source" fact stays.
- Delete what becomes unused: `PlayerHeadChips`, `nbaHeadChips`,
  `nhlHeadChips`, the `PlayerHeadChip` type, `BoardRecord.version`, the
  `projectionVersion` / `overProbabilityVersion` fields of the prop model
  summary if nothing else reads them, and the matching CSS.

**Kept on purpose** (fine print or analysis pages, not the head):

- Player page footers ("Projections from nba-reference-v1.") and projection
  history footnotes, which are where provenance belongs.
- Methodology text in track record page sections, and the tennis track record
  page's model version selector, which is a working control.
- The NFL player strip.

**Must not break:** the gray-signal rule (no new color on any number), empty,
loading and error states of each head, and mobile layout of the head when the
strip is gone.

## Build steps

- [x] **1. Prop boards.** Remove the stat strips on the NBA, NHL, NFL and
  tennis prop boards; put the game count in the meta line for NBA, NHL and
  NFL (for example `Fri, Nov 13 · 9 games`). Stop rendering and building the
  model version in `BoardRecordStrip` / `boardRecord.ts`.
  *Done when* no prop board shows a stat card or a version string above the
  pills, and `boardRecord.test.ts` passes without `version`.
- [x] **2. NBA and NHL player heads.** Remove the chip strip; add average
  minutes (NBA) and average TOI (NHL) to the meta line through a tested
  helper, omitted when unknown. Remove the market count beside "Props on ..."
  in `PlayerMarketTabs` (a page passing its own `note` keeps it). Delete the
  head chip code.
  *Done when* the NBA head reads like `G · IND · vs NY · 2026-11-13 · 25.1 min`
  with no cards, and the helper tests pass.
- [x] **3. Projection card.** Replace the Model and Sample facts with a
  `sample` caption in `nbaProjectionHero`, `nhlProjectionHero`,
  `nflProjectionHero` and `tennisMarketHero` (drop tennis Basis too); render
  it after the delta, or alone when there is no delta.
  *Done when* every sport's card shows the number, the delta and
  "based on last N games", with no model name, and the hero tests pass.
- [x] **4. Track record pages and Bankroll Builder.** Cut the version chips on
  the NBA, NHL and NFL track record heads, drop the "V4" prefix on the NFL
  labels, and cut "Scanned" on Bankroll Builder.
  *Done when* those heads show only adopted slices, verdicts, settled week,
  singles and parlays.

## Verify

- `npm --prefix web run verify` passes (typecheck, tests, build).
- In the running app, open each changed page (NBA, NHL, NFL, tennis props;
  an NBA and an NHL player; an NFL prop detail; a tennis player market; the
  three track record pages; Bankroll Builder) at desktop and phone width:
  no head stat cards except NFL player, no model version string above the
  footer, and the sample reads as a caption under the projection.

## Verification evidence

- `npm --prefix web run verify`: typecheck, 115 test files (1,828 tests) and
  the build pass.
- `python -m pytest` from `api/` with CI's dummy `DATABASE_URL`: 6,433 passed.
- Browser, against this branch's API on port 8001 (the API already on 8000
  predated feature 69 and crashed the NBA player page before any of this
  fix's code ran): NBA, NHL, NFL and tennis prop boards; Aaron Nesmith (NBA),
  Adam Fox (NHL), Drake Maye (NFL) and Aryna Sabalenka (tennis) player pages;
  the NBA and NFL track record pages; Bankroll Builder; and the NBA player
  page at 375px. Each showed the meta line counts and sample captions above,
  with no head stat cards outside the NFL player page and no model version
  above the footer.
- Follow-up found during the browser pass: the NFL track record meta line
  still read "v4 last graded"; it now reads "last graded".

# Feature: Shared legend

**From build-plan:** feature 57b (parent 57, One slate shape for every sport)
**Branch:** `feature/57b-slate-legend` (cut from `master` at `fffac976`)
**Status:** complete (2026-11-08)

## Goal

Every slate (NFL `/nfl`, NBA `/nba`, NHL `/nhl`, tennis `/tennis`) shows the same
legend: one short line naming where the numbers come from and how fresh they
are, then a "What's a pick?" disclosure that says what this sport serves as a
pick and what is reference. Today NFL and NBA carry a three-sentence legend,
NHL a five-sentence one, and tennis none. A visitor learns the pick rule once
and finds it in the same place on every sport.

## Design reference

No new visual target. Follow the incumbent Lineform look, the slate surface
brief `.impeccable/surfaces/web-src-pages-nflintelligencepage-tsx.md`, and the
2026-11-08 critique (P2 finding 5: "collapse the legend to one line plus a
'What's a pick?' disclosure"; finding 4: provenance once in the legend). The
existing `.nfl-slate__legend` look (11px, muted gray, bold labels in the
secondary gray) is the starting point.

## In scope

- **One shared component**, `SlateLegend`, used by all four slates. It renders:
  - **The line:** two or three short parts joined with ` · `, in the existing
    legend style. Each part is a bold label and a few words.
  - **The disclosure:** a `What's a pick?` toggle at the end of the line. Opened,
    it shows two or three plain sentences: what is a pick on this sport, what is
    reference and why it is gray, and a `How it works →` link to
    `/how-it-works`. Closed by default, on every load.
- **Per-sport content** (wording to be tuned at review; meaning fixed):

  | Sport | Line | Disclosure says |
  |---|---|---|
  | NFL | **Market** DraftKings, else latest book · **Model** nfl-elo-v1, context only | No NFL picks. Gaps are reference, gray until the ranking check (27j) adopts a slice. The closing line beat nfl-elo-v1 on the 2022-25 holdout. |
  | NBA | **Market** DraftKings, else latest book, de-vigged · **Scores** the morning after | No NBA picks. Gaps are the reference projection minus the line, gray until the ranking check adopts one. |
  | NHL | **Prices** full-game, incl. OT and shootouts · **Goalies, injuries** ESPN · **Scores** after games (shortened in step 4 to fit two lines at 375px; "stored book prices" and "ESPN reports" moved into the disclosure) | No NHL picks or projections. Win probability is de-vigged per book; props are line-only; late goalie and injury changes may be missing. |
  | Tennis | **Props** PrizePicks (or the admin-chosen source) · **Odds** stored book prices | Total Games and Game Spread picks carry expected value. Moneyline picks are off (the closing line beat them), so moneyline numbers are reference. PrizePicks lines stay gray unless their forward check adopts the slice. |

  Every sentence above already appears in an existing legend or in
  `SPORT_STATUS` (`web/src/pages/howItWorksContent.ts`); nothing new is claimed.
- **Freshness stated once.** The odds time already lives in the period line
  (57a, with its `(stale)` marker). The legend never repeats a timestamp; its
  freshness part is the update cadence ("Scores the morning after"), not a time.
- **Placement:** where the legend sits today, after the digest and before the
  first table. NHL (no digest) puts it right after the page head. Tennis puts it
  after `TennisSlateDigest`. Shown only when the slate has games, as today.
- **Phone:** the line may wrap to two lines at 375px; the disclosure toggle is a
  44px target.

## Out of scope

- **57c:** NHL's per-cell source and timestamps, its expanded context row, and
  goalie and injury note tags. Until 57c lands, NHL states its source in the
  legend and still repeats it in cells; that duplication is 57c's to remove.
- **57d:** tennis's "Best pick", EV column, digest wording, "Show Leans", the six
  filter controls, sort, and moving the prop-source select into the legend. 57b
  states the tennis source as text only; the admin select stays in the filters.
- The digest strips, row shapes, table columns and colors on all four slates.
- How it works page content (`SPORT_STATUS` is read, not edited).
- Game, player, props and model pages. Any API change.

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

## Build steps

- [x] **Step 1 - Shared component and content.**
  - `web/src/components/shared/SlateLegend.tsx`: takes `parts` and `pick` (see
    Data / contracts) and renders the line plus a native `<details>` /
    `<summary>` disclosure (keyboard and screen-reader support for free, no
    state). Styles extend `.nfl-slate__legend` in `nfl-slate.css`; the summary
    gets a 44px phone target and a visible focus ring.
  - `web/src/utils/slateLegend.ts`: the per-sport content as plain strings
    (`SLATE_LEGENDS`, keyed by the sport codes in `~/utils/sportNav`, not by
    importing from `pages/`), with the tennis props part built by
    `tennisLegend(sourceLabel)`.
  - Tests in `slateLegend.test.ts` (see Testing).
  - No page uses them yet.

  *Done when:* the tests pass, Verify's web build passes, and all four slates
  render exactly as before.
- [x] **Step 2 - NFL and NBA.** Replace each page's local `Legend()` with
  `<SlateLegend {...SLATE_LEGENDS.nfl} />` / `.nba`, in the same spot.

  *Done when:*
  - `/nfl` and `/nba` show the one-line legend and a closed `What's a pick?`.
  - Opening it shows the sport's sentences and a working `How it works →` link;
    Enter and Space toggle it from the keyboard.
  - The holdout and 27j sentences are still on the page (inside the disclosure).
  - Neither page defines `Legend()` any more.
- [x] **Step 3 - NHL and tennis.**
  - NHL: the inline five-span paragraph becomes `SlateLegend`, right after the
    page head.
  - Tennis: `SlateLegend` after `TennisSlateDigest`, with the props part naming
    the active source (`PrizePicks`, or `DraftKings` when an admin picks it).

  *Done when:* both pages show the legend and disclosure; switching the admin
  prop source changes the tennis props part; no NHL sentence from the old
  paragraph is lost (each is in the line or the disclosure).
- [x] **Step 4 - Check all four.** Desktop 1440px and phone 375px on all four
  slates, closed and open.

  *Done when:*
  - the closed legend is one line at 1440px and at most two lines at 375px
  - on a 375px phone the first game row sits at or above 57a's result for NFL
    (658), NBA (632) and NHL (451), and at most 60px below it for tennis (620),
    which gains a legend it did not have (two 11px lines plus the 44px toggle)
  - no page scrolls sideways, no text is under 11px, the toggle is 44px on
    phones, and nothing in the legend is green or red
  - Verify passes

## Files / areas

- **New:** `web/src/components/shared/SlateLegend.tsx`,
  `web/src/utils/slateLegend.ts`, `web/src/utils/slateLegend.test.ts`.
- **Styles:** `web/src/pages/nfl-slate.css` (legend and disclosure rules). The
  tennis page must import it or the rules move to a shared stylesheet; decide in
  step 1's plan, preferring the smallest move.
- **Pages:** `web/src/pages/NflIntelligencePage.tsx`,
  `web/src/pages/NbaSlatePage.tsx`, `web/src/pages/NhlSlatePage.tsx`,
  `web/src/pages/TennisIntelligencePage.tsx`.
- **Read only:** `web/src/pages/howItWorksContent.ts` (`SportCode`).

## Data / contracts

- **No API change.** Every value is static text or the tennis source label the
  page already holds.
- **Contract (load-bearing for 57d):**

  ```ts
  // utils/slateLegend.ts - content, strings only, so it is testable
  interface SlateLegendContent { parts: { label: string, text: string }[], pick: string[] }
  // components/shared/SlateLegend.tsx - the component's props
  interface SlateLegendProps { parts: { label: string, text: ReactNode }[], pick: string[] }
  ```

  The component's `text` is a `ReactNode` so 57d can put the tennis prop-source
  select in the props part without changing the component; the content stays
  strings. `pick` is the disclosure's sentences; the component adds the
  `How it works →` link.

## Testing

- **Unit tests (Vitest, `slateLegend.test.ts`):**
  - every sport in `SPORTS` has a legend with at least one part and one pick
    sentence, so a new sport fails loudly instead of rendering an empty legend
  - no legend text contains a clock time (`\d:\d\d`), so freshness stays stated
    once, in the period line
  - for every sport whose `SPORT_STATUS[...].picks` is `'None.'` (NFL, NBA, NHL
    today), the first pick sentence says there are no picks, so the legend and
    How it works cannot drift apart (a test-only import from `pages/`)
  - `tennisLegend('DraftKings')` names DraftKings in the props part
- **Not unit-tested** (per the coding standards): `SlateLegend` and the pages.
  They get browser and screenshot evidence in steps 2-4.
- **Gate:** the Verify command (`npm --prefix web run verify && cd api && python -m pytest`).

## Notes for the AI

- **Display only.** No probability, edge, rank, sort or pick changes. Everything
  in the legend is gray: muted text, secondary-gray labels, no signal colors.
  11px floor.
- **Do not reword claims.** The table's sentences are condensed from the current
  legends and `SPORT_STATUS`. Shortening is fine; a new or stronger claim (for
  example about tennis prop accuracy) is not. If a sentence cannot be shortened
  without changing its meaning, keep it longer.
- **No new timestamps.** The period line owns the odds time and its stale
  marker (57a).
- **Native disclosure.** Use `<details>` / `<summary>`, not Ant `Collapse` or
  component state, so the disclosure resets per load and needs no test.
- **Tennis source label:** reuse the page's existing `sourceLabel`; do not add a
  new lookup.
- **Coordination:** 57c and 57d each touch `NhlSlatePage.tsx` and
  `TennisIntelligencePage.tsx`. Build them after 57b merges, not in parallel.

- **Interview guide:** a cosmetic change; no guide update expected unless the
  pick wording changes a claim there.

## Open questions for review

1. **Legend wording.** The table is a first pass at condensing; adjust any line
   or sentence before step 1.
2. **Tennis odds source.** "Stored book prices" is deliberately generic. If you
   want the books named, say which; the tennis ingest scopes bookmakers through
   `app/core/bookmakers.py`.

## Result

- All four slates share `SlateLegend`: one line of source and cadence parts,
  then a native `<details>` "What's a pick?" disclosure with a How it works link.
  Gray only; the period line keeps the odds time.
- At 375px the closed legend is at most two lines and the toggle is 44px. First
  game row: NFL 629 (57a: 658), NBA 603 (632), NHL 415 (451), tennis 662
  (620, which gained a legend). At 1440px each legend is one line.
- NHL's line was shortened in step 4 to fit two phone lines; "stored book
  prices" and "ESPN reports" moved into its disclosure.
- Additions beyond the spec's file list: `SlateLegend` imports
  `nfl-slate.css` itself so tennis gets the styles (every rule there is scoped
  to slate classes).
- Verify: `npm --prefix web run verify` (86 files, 1285 tests, build) and API
  `pytest` (5937 passed).

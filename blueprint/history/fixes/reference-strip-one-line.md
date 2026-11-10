# Reference strips are one gray line on every page

**Type:** Fix
**Status:** complete 2026-11-10
**Branch:** `fix/reference-strip-one-line`

### The problem

The 2026-11-09 slate fix (PR #22, `cd8cd306`) changed the NFL and NBA slates so
reference-only gaps show as one gray line under a "No picks" headline
(`SlateNoPicks`). Its reasoning was that a box reads as a pick. Every other
page that shows reference items still draws them as boxed `SlateDigest` cards:

| Page | Component | Today |
|---|---|---|
| Tennis slate `/tennis` (no priced best bet) | `TennisSlateDigest` leans | cards |
| NFL game page, Player Props tab | `NflSlateDigest` in `NflGameProps.tsx` | cards |
| NBA game page, props | `NbaSlateDigest` in `NbaProps.tsx` | cards |
| NFL prop board | `NflSlateDigest` in `NflPropBoardPage.tsx` | cards |
| NBA prop board | `NbaSlateDigest` in `NbaPropBoardPage.tsx` | cards |

The result is that the same kind of information looks like a pick on one page
and like reference on the next.

### The fix

**Rule:** cards are only for priced or adopted picks. Reference items (gaps
and leans) are always one gray line.

- **Extract `SlateGaps`** from `SlateNoPicks.tsx`: the label, the order note and
  the `slate-gaps` list, with no headline. `SlateNoPicks` renders its headline
  and then `<SlateGaps>`, so the NFL and NBA slates don't change.
- **Game pages and prop boards** swap `NflSlateDigest` / `NbaSlateDigest` for
  `SlateGaps`, with no "No picks" headline, since those pages don't make
  picks. Keep the current link targets: game pages open the player page
  (`nflPlayerMarketLink`, `nbaPlayerPath`), and prop boards open the game page
  with the NFL opened-row memory. Labels:
  - Game pages: `Largest prop gaps this game`
  - Prop boards: `Largest prop gaps this week` (NFL) / `today` (NBA)
  - Order note: the same sport rule as that sport's slate.
- **Tennis slate:**
  - With a priced best bet, keep the green "Best picks · priced" cards as they are.
  - Without one, show `SlateNoPicks` with a `No tennis picks` headline, a
    remaining line (`N matches left · next <day> <time> CT`), and a
    `Model leans` line covering the same next 4 matches: the lean in bold, then
    the match and start time muted.
  - `SlateNoPicks` gets an optional `title`, because `sport.toUpperCase()`
    would print "TENNIS". `SlateGapLink.gap` becomes optional, since a lean has
    no gap number.
- **Remaining line:** `slateRemainingLine` takes a unit noun (default `game`), so
  tennis reads "matches". Tennis rows carry no state, so a tennis match counts
  as left when its start is in the future or it hasn't finished. Use the
  status the slate already has, and add no new API field.
- **Delete what nothing uses afterwards:** `NflSlateDigest.tsx`,
  `NbaSlateDigest.tsx` and `GapDigestBody.tsx`. `SlateDigest` stays for the
  priced tennis cards. Also drop any `.slate-digest*` CSS that only those
  components used, including `.nfl-game .slate-digest` and
  `.is-game-slate .slate-digest__basis`.

**Must not break:**
- The NFL and NBA slate strips render the same as before.
- The green EV on priced tennis picks stays as it is.
- Gap ordering and the share numbers stay as they are. The digest utils
  (`slateDigest`, `nbaSlateDigest`, `leanDigest`) are untouched.
- Nothing in a reference line is colored.

**Trade-off:** the cards showed `line → model`. The one-line strip shows only the
gap and share, the same as the slates. On game pages and prop boards, the table
right below still shows both numbers.

### Build steps

- [x] **Step 1 - `SlateGaps` + game pages + prop boards.** Extract `SlateGaps`,
  switch the four NFL/NBA call sites, delete `NflSlateDigest`,
  `NbaSlateDigest`, `GapDigestBody` and their dead CSS.
  *As built:* `NflSlateDigest` and `NbaSlateDigest` were kept and became thin
  wrappers around `SlateGaps`, so the four call sites didn't change. They now
  also export `nflGapLink` / `nbaGapLink` and the order notes, which the slates
  reuse instead of their own copies. Only `GapDigestBody` was deleted.
  **Done when:** the NFL and NBA game Player Props tabs and both prop boards
  show one gray "Largest prop gaps" line with working links. The NFL and NBA
  slates look the same as before. `npm run build` passes.
- [x] **Step 2 - Tennis.** *As built:* `slateRemainingLine` is unchanged.
  Tennis rows carry no live or final state, so a new `tennisRemainingLine`
  counts only matches yet to start and reads `N matches to start · next Tue 9:00 AM CT`
  (or `Every match has started`). "Left" would have counted matches still in
  play as done. `leanLink` maps a lean to the line, and both helpers are
  tested in `tennisSlate.test.ts`. Original step: Add the optional `title` to `SlateNoPicks`, make
  `gap` optional, add the unit noun to `slateRemainingLine`, and render the
  no-priced-pick state as `SlateNoPicks` with lean links.
  **Done when:** `/tennis` with no priced pick shows `No tennis picks`, an
  `N matches left` line and one gray `Model leans` line. A slate with a priced
  pick still shows the green cards. `slateHeadline.test.ts` covers the
  `match` unit, and the tennis lean-to-link mapping (a pure helper in
  `utils/`) has a test.

### Verify

- `npm --prefix web run verify && cd api && python -m pytest`
- In the browser at desktop and 390px wide:
  - `/tennis` shows the no-picks line.
  - `/nfl/game/<id>` and the Player Props tab, plus an NBA game, show one gray gaps line.
  - `/nfl/props` and the NBA prop board show the same line.
  - `/nfl` and `/nba` look unchanged.
- On phones, the line scrolls sideways and each item is a 44px tap target
  (inherited from `slate-no-picks.css`).

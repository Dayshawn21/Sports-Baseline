# Fix: Bankroll Builder page split up and on PageHead

**Type:** Fix
**Fixes:** F-70
**Branch:** `fix/web-parlays-page` (cut from `fix/web-admin-panels`, so merge
the seven earlier web branches first)

**Completed:** 2026-11-16. Squash-merged to master at the user's request.

### The problem

`pages/ParlaysPage.tsx` is 802 lines:

- It holds seven subcomponents (`BetTypeBadge`, `ConfidenceBadge`,
  `SinglePickRow`, `ParlayCard`, `StatPill`, `SinglePickCard`,
  `TourSection`) beside the page.
- It builds its own head: a `TENNIS · VALUE ENGINE` eyebrow, a 42px `h1`
  and the Singles/Parlays chips, instead of the shared `PageHead` every
  other page uses. The toolbar also carries a descriptive line ("Top
  singles & 2-leg parlays ranked by edge, EV, and Kelly sizing").
- `SinglePickRow`, `ParlayCard` and `SinglePickCard` change their hover
  look by mutating `style` in `onMouseEnter`/`onMouseLeave`.
- Banner-divider comments (`// ── Sub-components ──`) split the file.

### The fix

User decision (2026-11-16): use `PageHead` and drop the toolbar line.

- The seven subcomponents move to `components/tennis/parlays/`, with the
  constants they use: `ParlayBadges.tsx` (bet-type, confidence and stat
  badges, `TIER_STYLE`), `SinglePickRow.tsx` (with `SINGLES_COLS`),
  `SinglePickCard.tsx`, `ParlayCard.tsx` and `TourSection.tsx`. The banner-divider comments go.
- Hover effects become CSS classes in a new `parlays.css`: the row's hover
  background, and the two cards' hover border and shadow, with the same
  colors as the current inline values.
- The head becomes `<PageHead title="Bankroll Builder" meta={slate date}
  stats={Singles and Parlays chips} />`. The meta shows the response's
  date through `slateDateLabel` (`Mon, Nov 16, 2026`), and nothing while
  loading.
- The toolbar keeps the tour filter, date picker and Refresh, and loses
  the descriptive line. The toolbar right-aligns so the filters stay on the
  right, where the line used to push them.

**Visible change (approved):** no eyebrow, the standard 34px title with the
slate date beside it, the counts in the PageHead stats strip, and no
toolbar description. Everything below the head looks the same.

Stays inside `web/`.

### Build steps

- [x] **Step 1 - move the subcomponents.** The seven components go to
  `components/tennis/parlays/`, and the page imports them. Done when: the
  page holds only `ParlaysPage`, no banner comments remain, Verify passes,
  and the page body renders the same HTML as before.
- [x] **Step 2 - hover classes.** Replace the three `onMouseEnter` /
  `onMouseLeave` pairs with classes in `parlays.css`. Done when: no inline
  hover handlers remain, Verify passes, and a hovered row and card get the
  same computed background, border and shadow as before.
- [x] **Step 3 - PageHead.** Swap the hand-built head for `PageHead` and
  drop the toolbar line. Done when: the page shows the PageHead title, date
  and stats, filters still work, and Verify passes.

### Verify

- `npm --prefix web run verify` after each step.
- In the running app: `#/parlays` at desktop and phone width, before and
  after each step.

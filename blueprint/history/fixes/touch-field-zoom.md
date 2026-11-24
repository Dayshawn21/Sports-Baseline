# Stop phones zooming in on filters and text fields

**Type:** Fix

## The problem

On an iPhone, tapping the player picker, a team or game dropdown, or any other text
field zooms the whole page in, and the user has to pinch out to see the rest of it.

iOS Safari zooms whenever a focused field's text is smaller than 16px. The app's fields
are all smaller:

| Field | Size today | Where it's set |
|---|---|---|
| Ant Design `Select` and `Input` (player and game pickers, team dropdown, NFL season and week, model and admin pages) | 14px | Ant Design's default font size |
| Top-bar search ("Jump to another game") | 13px | `web/src/components/shared/slate-command.css` |
| Ask Lineform question box | 14px | `web/src/components/ask/ask.css` |

## The fix

One rule in `web/src/index.css`, inside `@media (pointer: coarse)`, sets 16px on every
text-entry element on touch screens: `input`, `textarea`, Ant Design's
`.ant-select-selection-search-input` and `.ant-input`, plus the two custom fields above.
Desktop sizes stay exactly as they are.

The field's own text grows by 2 to 3px on touch screens, and nothing else on the page
changes size.

**Must not break**

- Never block zoom with `maximum-scale=1` or `user-scalable=no` in the viewport tag.
  That would fix the jump but stop people from pinch-zooming to read, which is an
  accessibility failure.
- Field heights stay at the 44px touch target the phone styles already set, and the
  filter rows still have no sideways scroll at 375px.

## Build steps

- [x] **1. Touch-screen field size.** The `index.css` rule.
  Done when: in the browser's phone emulation, every listed field's input reports a
  computed `font-size` of 16px, desktop still reports the old sizes, and the filter rows
  have no sideways scroll at 375px.

## Verify

- Run the Verify command: `npm --prefix web run verify && cd api && python -m pytest`.
- Browser phone emulation: check computed font sizes and layout on the NBA props board,
  an NFL game page's Props tab, the top-bar search and the Ask drawer.
- Chrome cannot reproduce the iOS zoom itself, so the final check is on a real iPhone
  after deploy: tap the player picker and confirm the page no longer zooms.

## Implementation notes

- A plain 16px rule did not reach single-choice Ant Design dropdowns: Ant Design sizes
  `.ant-select-selection-search-input` with a four-class selector. The rule sets the
  whole `.ant-select` to 16px, so placeholders and chips match the typed text, and
  uses `!important` only on that Ant Design text box.
- The selected-value text in single-choice dropdowns stays 14px. It is not a text
  field, so it cannot trigger the zoom.
- The multi-select pickers' labels sit about 6px above center on phones. That predates
  this fix (measured with and without the rule) and comes from the pickers' 44px
  phone height.

## Evidence

- Verify, run as its two halves with the API venv and CI's placeholder `DATABASE_URL`:
  1,540 web tests, typecheck and build pass; 6,073 API tests pass.
- Browser phone emulation (375px, `pointer: coarse`) on 2026-11-11, proxied read-only to
  the live API: player and game pickers, team dropdown, NFL game-page picker, top-bar
  search and Ask box all compute 16px; fields stay 44px tall; no sideways scroll.
  Desktop still computes 14px.
- Not verified: the iOS zoom itself, which Chrome cannot reproduce. Confirm on a real
  iPhone after deploy.

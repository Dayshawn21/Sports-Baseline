# NBA prop text wrapping

**Type:** Fix

**Completed:** 2026-10-21. Implementation approved by the user's `$complete`
request. Local merge requires separate approval; push and deployment are pending.

**Branch:** `fix/nba-prop-text-wrapping`

## Problem

NBA prop table sample notes and alternate lines are cut off by shared
single-line table styling. The sample selector loses to `.prop-table td`,
so even its intended wrapping is overridden. Empty recent-history text is
also clipped.

## Scope

Strengthen the NBA sample selector and allow sample notes, modelled alternate
lines, line-only alternate lines, and empty-history messages to wrap inside
their existing cells. Preserve column widths, data, copy, typography, gray
signal rules, sorting, and interactions. No API, model, provider, or workflow
changes. The pre-existing `project-overview.md` edit is outside this fix.

## Build steps

- [x] Correct NBA table wrapping in
  `web/src/components/nba/nba-prop-table.css`. **Done when:** full sample
  notes and alternate lines are available without ellipsis, empty-history
  messages wrap, and game and board rows remain usable on desktop and phone.

## Verification

- Local browser rendering of the actual `NbaPropTable` and `NbaBoardTable`
  components with synthetic data at 1820, 1200, 768, 390, and 320 CSS pixels
  found no horizontal page overflow or clipping in modelled alternate lines
  and sample notes. Desktop and phone screenshots were visually inspected.
- Final desktop and phone confirmation included the empty-history message;
  its computed white-space was normal and no horizontal clipping remained.
- Line-only alternate wrapping is source-reviewed; no separate line-only
  browser fixture was exercised. No live API data was required.
- Impeccable's mechanical detector returned no findings for the CSS; the
  subsequent empty-history refinement was checked in the browser.
- Read-only invariant review of the CSS diff: clean. No model, probability,
  signal-color, font-size, backend, security, or production-memory changes.
- Required final gate: `npm --prefix web run verify && cd api && python -m pytest`
  with the API venv on PATH, passed on 2026-10-21: 51 web test files,
  700 web tests, production build, and 3,611 API tests. Only the existing
  bundle-size and dependency-deprecation warnings were reported.

## Manual try path

Open an NBA game with props and the NBA Props board. Check a market with
alternate lines and a sample note such as `P(over) not fitted for this market`.
Confirm the full text wraps at desktop and phone widths. A player without
recent games should show the full `No earlier games` message.

## Boundaries

CSS-only fix; no new logic tests are needed under project standards. Rows
with long text can become taller. Hosted deployment is unverified. The
employer interview guide needs no update for this cosmetic correction.
Existing unverified findings F-09 and F-12 remain outside scope and unchanged.

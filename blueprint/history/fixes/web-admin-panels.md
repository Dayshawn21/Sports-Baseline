# Fix: Admin repair panels written once

**Type:** Fix
**Fixes:** F-66
**Branch:** `fix/web-admin-panels` (cut from `fix/web-shared-props`, so merge
the six earlier web branches first)

**Completed:** 2026-11-16. Squash-merged to master at the user's request.

### The problem

`pages/AdminPage.tsx` (799 lines) writes each repair panel twice:
`renderMobilePanel` for phones and the table's `expandedRowRender` for
desktop. Fix Stats, Fetch ELO and Set ELO each repeat their submit logic in
both places, twice inside each (Enter and the button), and Set ELO builds its
`SetEloRequest` by hand in both. The Fix Stats / Fetch ELO / Set ELO action
buttons are also written twice (table column and mobile card).

The two layouts really differ: mobile stacks a bare input and button, and
desktop shows a titled card with a label and help text. Both stay.

### The fix

- `utils/adminFlags.ts` gains three tested payload builders:
  - `buildSetEloPayload(inputs): SetEloRequest | null` - null when Overall
    is empty, zero or not a number; blank surfaces become null.
  - `fixStatsPayload(slug): FetchStatsRequest` - an empty slug sends null.
  - `fetchEloPayload(name, playerName): FetchEloRequest` - an unchanged name
    sends null.
- New `components/admin/` components, each taking the player, its input
  value, `onChange`, `onSubmit`, `loading` and a `compact` flag that picks the
  mobile or desktop layout:
  - `FixStatsPanel`, `FetchEloPanel`, `SetEloPanel`.
  - `AdminActions` for the three toggle buttons, with `hasEloFlag` and
    `hasStatsFlag` moved to `utils/adminFlags.ts`.
- `AdminPage.tsx` keeps the state and mutations and renders these
  components in both places. `renderMobilePanel` and the inline
  `expandedRowRender` bodies go.

**Kept on purpose:** the mobile Set ELO grid checks `isMobile` for its column
count, but it only renders on mobile, so it is always one column. The
compact layout keeps one column and drops the dead check.

No visible change. Stays inside `web/`.

### Build steps

- [x] **Step 1 - payload builders.** Add the three builders with tests to
  `utils/adminFlags.ts`, and use them at every submit site in
  `AdminPage.tsx`. Done when: no `SetEloRequest` is built inline and Verify
  passes.
- [x] **Step 2 - panel components.** Add the four `components/admin/`
  components and render them for both layouts. Done when: `renderMobilePanel`
  is gone, each panel's markup exists once, Verify passes, and the Admin page
  renders the same panels at desktop and phone width.

### Verify

- `npm --prefix web run verify` after each step.
- In the running app: local dev asks for the admin key, so the user signs
  in on the Admin page in the browser pane; then open each panel at desktop
  and phone width and compare against the old markup.

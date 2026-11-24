# Fix: remove the tennis slate's unreachable inline drawer

**Type:** Fix
**Fixes:** F-43

## The problem

After f41-tennis-drawer the slate's inline drawer opens only for a prop-only group (no
`matchId`). `composeUnifiedMatches` drops every unlinked prop, because `isTennisRateable`
requires `audit.matchLinked !== false` and both props endpoints set it false for any
unlinked line. So no prop-only row reaches the slate, and the drawer
(`TennisMatchDetail`, its CSS, `DetailRow`), the row toggle button, `expandedKey` and the
digest's `openFromDigest` button fallback (with `revealTab`) are dead code in production.

## The fix

Remove the drawer path (the user's choice over showing unlinked props). Every slate row
and digest box then only links to its match analysis page.

- Delete `TennisMatchDetail.tsx` and `tennis-match-detail.css`.
- `TennisSlateTable`: drop `DetailRow`, `expandedKey`, `onToggle`, the toggle button and
  the `is-open` state. A row without an analysis path renders its players as plain text
  and does nothing on click.
- `TennisIntelligencePage`: drop `expandedKey`, `toggleRow` and `openFromDigest`.
- `TennisSlateDigest`: every box is a link; drop `selectedKey`, `onSelect` and the button.
- `tennisDigest` skips a pick without an analysis path, so `analysisPath` is a `string`.
- Remove the now-unused `revealTab` and the drawer, open-row and digest-selected CSS.

Must not break: analysis links from rows and digest boxes, the prop link in the Best pick
cell, tour tabs, the slate command search, mobile row layout. Not in scope: the
prop-only grouping in `composeUnifiedMatches` (kept so a future linked-props change can
still show a row) and the API.

## Build steps

- [x] Remove the drawer, toggle and digest fallback. Done when: the files above are gone,
  no reference to `TennisMatchDetail`, `expandedKey`, `openFromDigest` or `revealTab`
  remains in `web/src`, `tennisSlate.test.ts` covers the digest skipping a pathless pick,
  and Verify passes.

## Verify

- Verify command passes.
- Browser: `#/tennis` loads with no console errors; clicking a row and a digest box opens
  `#/tennis/match/<id>`; the Best pick prop link still opens its prop page.

## Findings

### f43-tennis-drawer-path/F-43 [P3] closed - The tennis slate's inline drawer cannot open with real props

**File:** web/src/utils/tennisPropBoard.ts:249; web/src/utils/unifiedTennis.ts:559; web/src/components/tennis/TennisSlateTable.tsx:169; api/app/routers/props.py:428
**Found:** 2026-11-06 by a mocked browser check after f41-tennis-drawer (scope: tennis slate drawer; lens: quality)
**Why it matters:** after f41-tennis-drawer the drawer opens only for prop-only groups (no `matchId`). `composeUnifiedMatches` keeps a group only when it has a best pick or a prop passing `isTennisRateable`, and that check requires `audit.matchLinked !== false`, `projectionStatus === 'ok'` and a `recommendation`. The props builder behind both `/tennis/props/prizepicks` and `/tennis/props/dk` always sets `audit.match_linked = prop.match_id is not None`, and an unlinked line also gets `missing_match` (or `missing_player`) as its status. So every unlinked prop is filtered out, no prop-only row ever reaches the slate, and `TennisMatchDetail`, `DetailRow`, the row toggle, `expandedKey` and the digest's `openFromDigest` inline fallback are unreachable in production. Evidence, 2026-11-06 against the local API: 59 of 113 PrizePicks props were unlinked, all 59 had `matchLinked: false` and a `missing_match` or `missing_player` status, and 0 had a recommendation. A mocked unlinked prop with a recommendation, `projectionStatus: "ok"` and no `audit` did render the drawer correctly (props listed, EV gray, only the adopted cell green, no console errors).
**Suggested fix:** a product choice. Either remove the drawer and its toggle path (the slate then only links to analysis pages, and the digest's fallback goes), or decide unlinked props should be shown and let them through the filter as a separate, gray "unlinked" group.
**Resolution:** fixed 2026-11-07 by removing the drawer path (the user's choice): `TennisMatchDetail.tsx` and `tennis-match-detail.css` deleted; `TennisSlateTable` lost `DetailRow`, `expandedKey`, `onToggle`, the toggle button and `is-open`; the page lost `expandedKey`, `toggleRow` and `openFromDigest`; `TennisSlateDigest` boxes are links only; `tennisDigest` skips a pick without an analysis page (tested); `revealTab` and the drawer CSS removed. Closed by /audit (scope: current; all lenses): no reference left in `web/src`, typecheck and Verify pass, and a browser check against the local API showed 24 rows, all analysis links, no drawer markup, and a row click opening `#/tennis/match/98161`. The digest was empty that day, so its link boxes are covered by the unit test only. The prop-only grouping in `composeUnifiedMatches` stays by design.

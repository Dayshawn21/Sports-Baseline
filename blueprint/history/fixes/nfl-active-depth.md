# Current Feature

## NFL depth that skips players ruled out

**Type:** Fix

## The problem

Depth comes straight from the nflverse pre-game depth chart
(`nfl_player_depth_charts.depth_rank`), which lists injured starters in their
usual slot. 2026 week 10: Kenneth Walker III (KC) is Out, but Emmett Johnson
still shows **Depth: RB2** on his player page, and Walker still shows **RB1**.
Since the ESPN injury fix (`8e8eedbb`), the app knows Walker is out; the depth
label just ignores it.

## The fix

Add an **active depth rank**: the player's chart rank, minus the teammates at the
same position ahead of him whose shown injury status (the merged
`injury_reports` status) is `Out`. Johnson becomes RB1. A player who is himself
Out keeps no active rank.

Shown as the depth, with the chart rank kept as context:

| Player | Chart | Shown |
|---|---|---|
| Emmett Johnson | RB2 | `RB1 (RB2 on chart, Walker out)` |
| Kenneth Walker III | RB1 | `RB1 on chart, out` |
| No one ahead is out | WR2 | `WR2` (unchanged) |

Must not break:

- **Display only.** No projection, edge, ranking or frozen model output reads
  depth or injury status, and this fix must not add one. Johnson's projection
  and Walker's 117.1 stay as they are (see Out of scope).
- **Week-over-week moves** (`depth_promoted` / `depth_demoted` and "(was WR1)")
  keep comparing chart rank to chart rank, so an injury fill-in is not reported
  as a promotion.
- Only `Out` moves a teammate up. Doubtful and Questionable players may play.

## Build steps

- [x] **1. Active rank in SQL.** In `app/repositories/nfl.py`, `week_depth` gains
  `active_depth_rank` and `out_ahead` (names of same-team, same-position players
  ranked above who are Out), computed once off `week_depth` joined to
  `injury_reports`. Wire them through `_AVAILABILITY_COLUMNS` / `_AVAILABILITY_FIELDS`,
  `get_player_profile` and `get_week_depth_rows`, then the response schemas and
  services that already pass `depth_rank`.
  *Done when:* a repository test pins the SQL, and a read of 2026 week 10 gives
  Johnson `active_depth_rank = 1`, `out_ahead = ['Kenneth Walker III']`, and
  Walker `active_depth_rank = NULL`.
- [x] **2. Labels (web).** `web/src/utils/nflAvailability.ts`: a pure
  `activeDepthLabel` producing the three forms in the table, used by the player
  page chip, the prop table tag and the game notes depth list. Tests beside it.
  *Done when:* `npm run test` covers all three rows of the table, and the player
  pages for Johnson and Walker read as above.
- [x] **3. Slate snapshot.** The stored slates carry the new fields only after a
  rebuild; the web must treat a missing `activeDepthRank` as "no change" so old
  stored weeks still render.
  *Done when:* a slate fixture without the field renders the old label.

## Verify

- `npm --prefix web run verify && cd api && python -m pytest` passes.
- Local: Johnson's page shows `RB1 (RB2 on chart, Walker out)`; Walker's shows
  `RB1 on chart, out`; a healthy depth chart (any other team) is unchanged.

## Out of scope

- **Projections.** Johnson's projection is still built from his RB2 usage, and
  Walker still shows a projection while Out. Moving usage to the fill-in, or
  withholding an Out player's projection, changes model outputs and needs its own
  versioned, backtested feature.

## Outcome (2026-11-15)

- **Verify:** `npm --prefix web run verify && cd api && python -m pytest` passed
  (web typecheck, tests and build; 6,454 API tests).
- **API, 2026 week 10** (a local API on this branch against Neon):
  Emmett Johnson `depthRank 2`, `activeDepthRank 1`, `outAhead ['Kenneth Walker III']`;
  Walker `depthRank 1`, `activeDepthRank null`, `Out`. 67 depth rows move up and
  58 players are out. Game notes return the fields too (Carson Wentz QB3 reads QB2
  with Kyler Murray out).
- **Not seen in a browser:** the folder's dev-server limit was taken by other
  chats. The labels are unit-tested from those exact values.
- **Field order:** `NflAvailability` gains its two fields at the end; something
  builds it by position, and fields in the middle broke the move flags.
- **Old stored slates** lack `activeDepthRank`; the web reads absent as "no change".

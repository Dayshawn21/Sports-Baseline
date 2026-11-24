# Hide the NFL reference-only forward checks from visitors

**Type:** Fix

**Branch:** `fix/nfl-model-admin-checks`

## The problem

`/nfl/model` is public and shows two forward checks that are still running and
are labeled "reference only":

- **Rec Targets forward check** (`nfl-targets-v1`)
- **Volume model forward check** (`nfl-volume-v1`, receptions)

A visitor can read small, unfinished samples from these checks as claims, or
as failures. The tennis, NBA and NHL model pages show only a track record and
don't need this change.

## Scope decision (confirm in review)

The request named three checks. This spec hides **two of them** and keeps the
**V4 forward ranking check** public:

- V4 is the check that decides which prop slices are adopted (27h), so it is
  the evidence for what the app recommends, not lab work.
- All four summary chips at the top of the page (`V4 prop slices adopted`,
  `V4 last settled week`, `V4 projection version`, game-line verdicts) are
  built from V4 and CLV data. Hiding V4 would leave those chips pointing at a
  section visitors can't see.

To hide V4 as well, move its section into the gated block in Step 1 and drop
the three V4 chips from `Summary` for visitors. Say so before `/implement`.

## The fix

In `web/src/pages/NflModelPage.tsx`:

- Read `useAdminView()` from `~/hooks/useAdmin`, the same owner view that
  already gates the Admin nav and the tennis quality flags.
- Render the Rec Targets and Volume sections only when the admin view is on.
- Pass `season` to the `targets` and `volume` `useNflModelRanking` calls only
  for the admin view, and `null` otherwise. The hook is `enabled: season !== null`,
  so visitors never request those two rankings.

Must not break:

- The V4 check, PrizePicks line grading, kicker correction notes, game-line
  CLV and P(over) calibration render exactly as they do now for everyone.
- `summaryCounts` is unchanged; it already ignores targets and volume rankings.
- The API endpoints stay as they are. This only hides sections in the UI, so
  the data is still public through the API, the same as the tennis quality
  flags.

## Build steps

- [x] **Step 1 - Gate the two reference-only sections.** Add the `useAdminView`
  gate and the `season`-or-`null` arguments in `NflModelPage.tsx`.
  **Done when:** with the admin view off, `/nfl/model` shows no Rec Targets or
  Volume heading and makes no `/nfl/model/ranking` request with a targets or
  volume model version. With it on, both sections render as they do today.

No new pure logic, so no new test. The existing `nflTrackRecord` and
`nflVolumeRecord` tests must still pass.

## Verify

1. Verify command: `npm --prefix web run verify && cd api && python -m pytest`.
2. **Visitor view:** `npm run dev` always turns the admin view on
   (`import.meta.env.DEV`), so check the public page with a production build:
   `npm run build && npm run preview` in `web/`, signed out of admin. Open
   `/nfl/model`. Expected: Track record head and chips, V4 forward ranking
   check, PrizePicks line grading, Game-line CLV, P(over) calibration. In the
   network tab, no ranking request for `nfl-targets-v1` or `nfl-volume-v1`.
3. **Owner view:** `npm run dev`, open `/nfl/model`. Expected: both reference
   checks are back, in their current place between V4 and line grading.
4. Spot check that `/tennis/model`, `/nba/model` and `/nhl/model` are unchanged.

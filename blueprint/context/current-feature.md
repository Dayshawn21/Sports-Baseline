# One game-page frame for NFL, NBA and NHL

**Type:** Fix
**Branch:** `fix/game-page-shell`

## The problem

The 2026-11-10 design critique scored the game pages about 22/40, mostly
because the NFL, NBA and NHL game pages read as three products. Player pages
already share `PlayerPageShell`; game pages have no equivalent.

- **Heroes differ and carry little.** NFL shows code and record with
  "Dome · Indoor" floating beside the home team; NBA shows full names and an
  empty middle before tip-off; NHL shows "Away"/"Home" and no record. At 1440
  the logos sit about 1300px apart; on phone the hero stacks to 143-190px.
- **No shared shell.** The crumb reads "← NBA slate", "← Week 9 slate" or
  "Back to NHL slate"; the meta separator is `·` on NBA and NFL but `/` on NHL;
  the `/` command field is registered only on NFL.
- **NFL status is wrong live.** `NflGamePage.tsx` prints the raw
  `detail.status`, so it says "scheduled" after kickoff. Each sport derives
  state its own way (`nhlGameState`, the NBA card's `cardState`, nothing on NFL).

## The fix

- `web/src/utils/gameState.ts`: one pure `gameState(status, startUtc, now)`
  for all three sports (`upcoming` / `live` / `pending` / `final` / `off`,
  labels Scheduled, In progress, Result pending, Final, Postponed, Canceled)
  plus CT start-time labels. Unit tests with fixed timestamps.
- `web/src/components/shared/GamePageShell.tsx`: crumb (`← NFL slate`
  pattern), the hero as the head (it carries a visually hidden `h1`
  `AWAY @ HOME`, so the title is not printed twice), one meta line joined
  with `·`, an optional notice slot, and the tabs with Player Props default.
  `GamePageState` / `GameNotFound` for loading, error and not-found.
- `web/src/components/shared/GameHero.tsx`: each side logo, code, record.
  The middle is always filled: start time in CT before the game, the live or
  pending state during it, the final score after, plus an optional detail line
  (NFL venue and conditions). Width-capped on desktop, one compact row on phone.
- NFL, NBA and NHL game pages move onto the shell and hero; the old
  `*GameHero` hero components go (their market blocks stay). NFL's best-line
  card shows only while the game is `upcoming`.
- NBA and NHL game pages register the `/` command field from the game date's
  slate (`useNbaSlate` + gaps, `useNhlSlate`), as NFL does from its week.
- Display only: no probability, edge, rank, sort or pick changes. Props tables
  are untouched.

**Known gap:** the NHL API sends no team record, so the NHL hero's record line
stays empty until the API adds one.

## Build steps

- [x] **Step 1 - game-state helper.** `utils/gameState.ts` + tests.
- [x] **Step 2 - shell and hero.** `GamePageShell`, `GameHero`, `game-page.css`.
- [x] **Step 3 - move the three pages.** Pages onto the shell; the old hero
  components go, and their files are renamed `*GameMarket.tsx` since only the
  market blocks remain; hero and crumb CSS removed from the sport files.
  Command field on NBA and NHL (`useNbaSlate` / `useNhlSlate` gained an
  `enabled` flag so the game page waits for its date instead of fetching the
  default slate first).
- [x] **Step 4 - check and Verify.** 1440 and 375 on one game per sport, then
  the Verify command.

## Evidence

Checked 2026-11-09 evening CT on a worktree dev server (:3013) against the
local API, with games in every state:

| Game | State | Hero middle | Meta status |
|---|---|---|---|
| NFL 136 BUF @ MIN | live (stored `scheduled`) | In progress / Started 7:15 PM CT / Dome · Indoor | In progress (was "scheduled") |
| NBA 21167 NO @ GS | live | In progress / Started 9:00 PM CT | In progress |
| NBA 21181 PHI @ CHI | final | 127 121 (loser muted) / Final | Final |
| NHL 57144 PHI @ CGY | final, OT | 3 4 / Final/OT | Final/OT |
| NHL 57149 COL @ TOR | upcoming | 6:00 PM CT / Tue, Nov 10 | Scheduled |

- 375: the hero is one row, 35px tall (was 143-190px); no horizontal
  overflow; smallest text in the head 11px. 1440: the hero is capped at 640px.
- `/` search on the NHL game page finds BOS and FLA @ BOS from that night's
  slate; NBA shows the field after its slate loads.
- No console errors.
- Verify: web typecheck, 1,456 tests and build pass; API 6,043 passed (run
  with CI's dummy `DATABASE_URL`, since this worktree has no `api/app/.env`).

## Done when

- All three game pages share the shell and hero.
- Status is correct pre-game, live and final (unit tests plus the running app).
- Verify passes.

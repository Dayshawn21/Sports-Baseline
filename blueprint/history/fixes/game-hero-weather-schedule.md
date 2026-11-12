# Game hero spans the page; NFL weather runs earlier and before primetime

**Type:** Fix

## The problem

- The shared game hero (`web/src/components/shared/game-page.css`) is capped
  at `max-width: 640px`, so on a desktop the away team, kickoff and home team
  sit squeezed into the left third of the page. The middle column's 220px cap
  also wraps the new rain chance onto a second line.
- `nfl-weather.yml` is scheduled for 14:00 UTC but GitHub has started it 3 to
  9 hours late (17:00 to 23:15 UTC). On 10-25, 11-01 and 11-08 it ran after the
  Sunday early kickoffs, so those games showed Saturday's forecast.

## The fix

- Drop the hero's 640px cap so the teams sit at the page edges with the
  kickoff centered; widen the middle column so the conditions line fits on
  one line at desktop width. The phone layout keeps its own rules. The hero is
  shared by every sport's game page.
- Schedule the weather run at 11:17 UTC daily (off the hour, which GitHub
  delays most, and early enough that a 6-hour delay still lands before the
  18:00 UTC Sunday kickoffs), plus 19:17 UTC on Sunday, Monday and Thursday
  for primetime games. The ingest skips any game with a snapshot from the last
  3 hours, so a late morning run makes the second one cheap. Open-Meteo is
  free. The 11:17 run still follows `nfl-scores` at 07:17, whose statuses its
  slate snapshot picks up.
- Display only: weather never feeds a projection, edge or rank.

## Build steps

- [x] **1. Hero spans the page.** Done when the NFL game page shows WAS at the
  left edge, NYG at the right edge, and the conditions on one line at desktop
  width, with the phone layout unchanged.
- [x] **2. Earlier and primetime weather runs.** Update the cron lines, the
  workflow comment and the project overview's schedule note. Done when the
  workflow parses and reads `17 11 * 1,2,9-12 *` and `17 19 * 1,2,9-12 0,1,4`.

## Verify

- `npm --prefix web run verify && cd api && python -m pytest`
- Open `#/nfl/game/137` at desktop and phone widths.

## Outcome

- Verified 2026-11-12: at 1600px WAS sits at the left edge, NYG at the right,
  and `Outdoor · 48°F · wind 14 mph · 57% rain` fits on one line; the 375px
  phone layout is unchanged. Verify passed (1792 web tests, build, pytest 6422).
- The new cron lines take effect once the push to `master` registers them.

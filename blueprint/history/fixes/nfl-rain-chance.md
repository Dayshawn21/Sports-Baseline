# NFL conditions label shows the rain chance

**Type:** Fix

## The problem

The NFL game page header (and the slate row's conditions) reads
`Outdoor · 48°F · wind 14 mph` even when rain is expected, for example WAS at
NYG on Thu 2026-11-12. `conditionsLabel` in `web/src/utils/nflGame.ts` formats
only temperature and wind, although `NflWeather` already carries
`precipitationProbability` (Open-Meteo `precipitation_probability`, a 0-100
percent) from the snapshot stored by `api/app/ingest/nfl_weather.py`.

## The fix

- Append the rain chance: `48°F · wind 14 mph · 80% rain`. A null value prints
  `-- rain`, matching how temperature and wind show `MISSING`.
- `Indoor` and `Forecast unavailable` stay unchanged.
- Display only: weather never feeds a projection, edge or rank. No API,
  schema or workflow change.
- `NflDataGuide.tsx` mentions weather only in passing ("injuries, weather, the
  spread and total"), so it needs no text change.

## Build steps

- [x] **1. Rain chance in `conditionsLabel`.** Format `precipitationProbability`
  as a rounded percent and extend `web/src/utils/nflGame.test.ts` (a forecast
  with a rain chance, a null rain chance, unchanged Indoor and unavailable).
  Done when the tests pass and the game page header shows the rain chance.

## Verify

- `npm --prefix web run verify && cd api && python -m pytest`
- Open an outdoor NFL game page in the dev server and read the header line.

## Outcome

- Verified 2026-11-12: WAS at NYG (game 137) header reads
  `Outdoor · 48°F · wind 14 mph · 57% rain` on the dev server; Verify passed
  (web verify, pytest 6422 passed).
- The hero's middle column (`max-width: 220px` in `game-page.css`) wraps the
  rain chance onto a second line; left for the 68a CSS work.
- Forecast staleness: the 14:00 UTC `nfl-weather.yml` cron starts 3-9h late,
  after Sunday early kickoffs on 10-25, 11-01 and 11-08. An earlier off-the-hour
  run plus a primetime-day run was recommended; the schedule is unchanged
  pending the owner's yes.

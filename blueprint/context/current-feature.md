# Slate Game cell: each team's record under that team

**Type:** Fix
**Branch:** `fix/slate-team-records`

## The problem

The 2026-11-10 critique: the NFL, NBA and NHL slates read as three products.
The Game cell is one place it shows.

- `NbaSlateTable.tsx` and `NflSlateTable.tsx` print both records as one
  left-aligned string, `<small>{away.record} · {home.record}</small>`, under
  the `SlateMatchupTeams` line, so the home record sits under the away team.
- `NhlSlateTable.tsx` prints the full team names instead (truncated), because
  the NHL API sends no team record: neither `NhlSlateGame` in
  `web/src/types/nhl.ts` nor `NhlSlateGameSchema` has one.

## The fix

- **Shared layout.** `SlateMatchupTeams` renders each side as its own column,
  logo and code on top and an optional record below, with `@` between the
  columns. Records stay gray (`--text-muted`), 11px. The phone rule that
  hides logos under 480px still applies. NBA and NFL pass their records in
  and drop the combined `<small>`.
- **NHL records in the API.** `awayRecord` and `homeRecord` on the NHL slate
  and game responses, computed the way NBA computes `NbaRecord`:
  - SQL in `app/repositories/nhl.py` (`get_completed_results`), counting rule
    in a pure `app/core/nhl_records.py`, schema `NhlRecordSchema` in
    `app/schemas/nhl.py`.
  - Only completed regular-season (`REG`) games of the same season, dated
    before the slate date, count, so a record reads like the standings going
    into the game.
  - Format is the NHL standings' W-L-OT (`8-4-2`): wins of any kind are W, a
    regulation loss is L, and an overtime or shootout loss (`end_period` `OT`
    or `SO`) is the third number. A completed game with no stored
    `end_period` counts its loser as L. The wire carries
    `{ wins, losses, otLosses }`; the web formats it.
- **NHL display.** The NHL slate shows records under each team like NBA and
  NFL, in place of the full names.
- **Game hero (pending).** PR Dayshawn21/Sports-Baseline#38 (shared
  `GameHero`) is not merged, so `NhlGamePage.tsx`'s `record: null` stays
  until it is. The API already sends the records; the follow-up is one line.

Must not change: any probability, edge, rank, sort or pick. No migration
(`end_period` exists since `0049`).

## Build steps

- [x] **1. Shared Game cell.** `SlateMatchupTeams` takes optional records and
  renders two columns; NBA and NFL pass theirs.
  Done when: `/#/nba` and `/#/nfl` show each record under its own team at
  1440 and 375, and the build passes.
- [x] **2. NHL records in the API.** Pure counting rule with pytest coverage,
  repository read, schema fields, slate and game responses.
  Done when: `pytest` passes, including W, L, OT and SO cases, other
  seasons, playoffs and games on or after the date left out.
- [x] **3. NHL slate display.** `NhlSlateGame` gains the records, a formatter
  (with a Vitest test) gives `8-4-2`, and the NHL table passes them in.
  Done when: `/#/nhl` shows records under each team at 1440 and 375.

## Verify

- `/#/nfl`, `/#/nba`, `/#/nhl` at 1440 and 375: each team's record directly
  under that team, gray, nothing clipped.
- `npm --prefix web run verify && cd api && python -m pytest`

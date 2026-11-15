# Current Feature

## NFL game-day injury downgrades from ESPN

**Type:** Fix

## The problem

Every NFL injury status in the app comes from the nflverse `injuries_<season>.csv`
(`app/ingest/nflverse_injuries.py`), which mirrors the team's Friday game-status
report. Later downgrades never reach it, or reach it days late. Week 10 of 2026:
Kenneth Walker III (KC) was ruled out Saturday, ESPN had him `Out` at
2026-11-15 16:21 UTC, and the nflverse file still said `Questionable` at our
16:46 UTC refresh, so the player page, slate tags and game notes all showed
Questionable.

## The fix

Add ESPN's NFL injury feed
(`https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries`, free,
no key, the same API the NBA and NHL ingests already use) as a second source,
and show the **more severe** of the two statuses for the current week.

- **Mapping.** ESPN athlete IDs map to our players (`sport_players.source_player_id`
  = `gsis_id`) through the `espn_id` column of the nflverse weekly roster CSV,
  fetched in the same run. Unmapped athletes are counted and skipped, never guessed
  by name.
- **Week.** Entries are stored against `nfl_repo.get_current_week(now)`. No
  current week (offseason, bye-only gaps) means the run stores nothing.
- **Status normalization.** `Out`, `Injured Reserve` -> `Out`; `Doubtful`;
  `Questionable`; `Active` and anything else -> no status.
- **Merge rule (downgrade only).** Effective status = the more severe of the
  nflverse report and ESPN (Out > Doubtful > Questionable > none). ESPN never
  upgrades a player the official report lists; the injury name and practice status
  stay nflverse's, falling back to ESPN's injury type when nflverse has no row.
- **Replace, never wipe on failure.** A successful fetch replaces the current
  week's ESPN rows; a failed or empty fetch (0 teams) leaves them as they were.

Must not break:

- **Display only.** Every NFL injury reader is display context
  (`core/nfl_availability.py` says so; QB-change is the game-notes panel). No
  projection, edge, ranking or frozen model output reads injury status, and this
  fix must not add one.
- **nflverse rows stay untouched.** The merge happens at read time, so the
  official report is still queryable on its own.
- **Slate snapshot.** Production serves stored slates, so any workflow that runs
  the new ingest must run `nfl_slate_snapshot` after it.

## Build steps

- [x] **1. Parser + merge rule (pure).** `app/core/nfl_espn_injuries.py`: parse the
  feed into `(espn_athlete_id, team_abbr, status, injury, comment, espn_updated_at)`
  entries with the normalization above, and `more_severe(official, espn)`.
  Tests in `api/tests/test_nfl_espn_injuries.py` use a trimmed copy of today's feed
  (Walker `Out`, an `Active`, an `Injured Reserve`, a `Doubtful`).
  *Done when:* tests pass, including Questionable + Out -> Out, Out + Active -> Out,
  none + Injured Reserve -> Out.
- [x] **2. Table.** Migration `0055_nfl_espn_injuries`: `nfl_player_espn_injuries`
  (`player_id` FK `sport_players`, `season`, `week`, `status`, `injury`, `comment`,
  `espn_updated_at`, `fetched_at`; PK `player_id, season, week`). Repository
  `replace_espn_injuries(db, season, week, rows)` in `app/repositories/nfl.py`.
  *Done when:* `alembic upgrade head` applies on a scratch database and
  `alembic downgrade -1` reverses it. Applying it to Neon is a separate,
  manual, one-command step.
- [x] **3. Ingest.** `python -m app.ingest.nfl_espn_injuries [--dry-run]`: fetch
  with `tenacity` retry (as `nba_injuries.py`), build the ESPN->gsis map from the
  roster CSV, store. Prints teams, entries, mapped, unmapped, stored.
  *Done when:* `--dry-run` against the live feed reports Walker mapped to his gsis
  id with status `Out`, and the unmapped count is small (expect under 5%).
- [x] **4. Read-time merge.** The four readers in `app/repositories/nfl.py`
  (`_AVAILABILITY_CTE`, `get_week_game_injuries`, the QB-injury query,
  `get_player_profile`) take the effective status via one shared SQL fragment
  (`CASE` on severity rank), not four copies. `get_week_game_injuries` also lists
  players ESPN has out but nflverse does not.
  *Done when:* a repository test or local run for 2026 week 10 shows Walker's
  `report_status` / `injury_status` as `Out` on the player profile and slate rows.
- [x] **5. Schedule.** Add the ingest to `nfl-prop-odds.yml` (after the nflverse
  injury step, `continue-on-error: true`) and to `nfl-weather.yml` (before its
  slate snapshot), so Sunday's 11:17 and 12:10 UTC runs and the 19:17 UTC Sunday,
  Monday and Thursday runs pick up late downgrades. Add the command to `AGENTS.md`
  and `docs/commands.md`.
  *Done when:* both workflow files show the step before `nfl_slate_snapshot`.

## Verify

- `npm --prefix web run verify && cd api && python -m pytest` passes.
- Local API + web: the Kenneth Walker III player page for 2026 week 10 shows
  **Out · Groin**, not Questionable, and the KC @ ATL game notes list him as Out.
- A player ESPN lists `Active` whom nflverse lists `Questionable` still shows
  Questionable.

## Out of scope

- A new UI label for the source ("per ESPN"). The badge text stays as is.
- Upgrades from ESPN (Questionable -> active), and any use of injury status in
  projections.

## Outcome (2026-11-15)

- **Verify:** `npm --prefix web run verify && cd api && python -m pytest` passed
  (web build and tests, 6,453 API tests).
- **Migration:** `0055` applied to Neon (`0054` -> `0055`). The `downgrade` was not
  exercised: there is no scratch database.
- **First real run (2026 week 10):** 32 teams, 239 statused entries, 197 mapped,
  185 stored (12 mapped players have no `sport_players` row yet).
- **Walker:** nflverse row `Questionable`; player profile and KC game notes read
  `Out`, `Groin`. ESPN downgraded 23 players that week; 69 official statuses with
  no ESPN row stayed as filed.
- **Unmapped:** 42 of 239 (18%), above the spec's 5% target. All are offensive
  linemen or long snappers that nflverse lists without an `espn_id`; none carry
  props. Left unmapped rather than matched by name.
- **Deploy order:** the readers depend on `nfl_player_espn_injuries`, so `0055`
  had to be on Neon before this API deployed (it was, before the merge).

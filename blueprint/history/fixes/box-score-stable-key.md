# Fix: Stop storing box scores twice

**Type:** Fix
**Status:** complete (2026-09-29)
**Branch:** `fix/box-score-stable-key`

## The problem

`player_match_stats` is unique on (`player_id`, `source`, `source_match_key`),
and `source_match_key` is a SHA-256 of the **whole raw TennisAbstract row**
(`app/ingest/player_stats.py`, `_parse_player_match_stats`). TennisAbstract
edits a row as a match progresses, so every edit hashes differently and the
refetch **inserts** a new row instead of updating the old one:

1. a pre-match placeholder (opponent and round, no result, score or stats),
2. then the result and score, stats still blank,
3. then the full box score.

Measured 2026-09-29 over 64,863 rows: **644 duplicate groups (1,308 rows)**,
at most 3 copies each, keyed on player, tournament start, tournament, round
and opponent. Of those, 530 are identical copies and 108 are an empty
placeholder beside the real row, which the 2026-09-29 join fix
(`blueprint/history/fixes/box-score-join-duplicates.md`) already tolerates.
The rest are **score-only rows beside the full row** (for example WTA Adana
125 R32 v Valdmannova: "6-4 6-3" with no stats, then the same with 1 ace, 2
DF), which the join still reads as `ambiguous`. Every duplicate also inflates
row counts for anything reading the table directly.

## The fix

**A stable key.** Key a box score on what identifies the match, not the raw
row: `sha256("v2|<tournament start YYYYMMDD>|<tournament>|<round>|<opponent>")`
with tournament, round and opponent trimmed and lowercased. The opponent is
required: 165 player/event/round groups hold two different opponents (round
robins). A row missing any of the three keeps today's raw-row hash; that is
3,986 legacy rows from before 26e, and no newly fetched row, since ingest has
stored all three since 26e.

**Merge the existing copies, then rekey** in migration `0038`:

1. Snapshot the table to `player_match_stats_pre_0038`, so the downgrade can
   restore it exactly (keys and deleted rows).
2. In each duplicate group keep one row: the most complete (stats, then a
   score), newest `fetched_at`, then highest `id`. Delete the rest.
3. Set `source_match_key` to the v2 key for every row with tournament, round
   and opponent, computed in SQL
   (`encode(sha256(convert_to(..., 'UTF8')), 'hex')`) with the same formula
   as Python.

Ingest then upserts onto the v2 key, so a later edit **updates** the row.

Must not break:

- **The upsert still writes every column.** A later fetch with fewer stats
  must not blank a fuller row: when the incoming row has no stats and the
  stored one does, keep the stored stats (TennisAbstract does not remove stats
  it has published).
- **Round robins.** Two opponents in one round stay two rows.
- **Legacy rows** keep their raw-row key and are never merged.
- **The join fix stays.** It is still the guard for anything that slips
  through.
- **One database, three writers.** GitHub Actions (`tennis-ingest.yml`), the
  local `ingest_daily` task, and manual runs all write this table. Apply
  `0038` and merge in one sitting, outside the `tennis-ingest.yml` run times,
  so old code does not insert raw-hash rows after the rekey. Any that slip in
  are still joined correctly and can be merged by re-running step 2's SQL.

## Build steps

- [x] **Step 1 - Stable key in ingest** - a pure `box_score_key(match_date,
  tournament, round, opponent, raw_row)` in `app/ingest/player_stats.py` (v2
  key when all three are present, else the raw-row hash), used by
  `_parse_player_match_stats`; the upsert keeps stored stats when the incoming
  row has none. Not deployed until step 2's migration runs. *Done when:*
  tests cover the same match fetched as placeholder, score-only and full row
  (one key), two round-robin opponents (two keys), case and spacing (one
  key), a missing field (raw hash), and the exact v2 key string for a known
  row, which step 2's SQL must reproduce.
- [x] **Step 2 - Migration 0038** - snapshot, merge duplicate groups, rekey
  in SQL. *Done when:*
  - a dry run on the live database prints the groups and rows it will merge
    (expect about 644 and 664);
  - after `alembic upgrade head`: zero duplicate groups; the row count down by
    exactly the merged rows; the SQL key equals the Python key for sampled
    rows;
  - re-running `python -m app.ingest.player_stats` for two players with
    duplicates (Hurkacz, a WTA 125 player) inserts **no** new rows;
  - `alembic downgrade -1` then `upgrade head` round-trips on the live
    database, and the snapshot restores the exact pre-0038 row count;
  - pytest passes, and the 30-day join measurement is no worse than after the
    join fix (ATP 87%, WTA 86%, Challenger 73% joined).

## Result

Applied to the live database 2026-09-29 16:3x UTC:

- Dry run: 676 duplicate groups, 696 rows to delete, 0 key collisions (the table
  had grown since the spec's 644/664 count).
- Upgrade: 64,953 to 64,257 rows, 0 duplicate groups; the Python key equals
  the stored key for all 60,271 keyed rows.
- Refetching Hubert Hurkacz and Antonia Ruzic updated rows in place (0 new).
- `alembic downgrade -1` restored 64,953 rows and 676 groups exactly; upgrade
  returned to 64,257 and 0.
- 30-day joined share: ATP 87% to 88%, WTA 86% to 90.5%, Challenger 73% to 74%.

Follow-up: drop `player_match_stats_pre_0038` in a later migration once the fix
has held (about a week).

## Verify

1. `#/tennis/match/82864`: Rublev's recent form still shows Hijikata, 12 aces.
2. A WTA 125 match with a score-only duplicate (Adana R32) now shows its box
   score.
3. `SELECT count(*)` of duplicate groups (query in the migration) returns 0,
   and stays 0 after the next `tennis-ingest.yml` run.

## Notes for the AI

- The migration must not import app code; it holds its own SQL. The Python key
  and the SQL key are held equal by step 1's fixed test vector.
- Migrations are never edited once applied; if 0038 needs a change after it
  runs, write 0039.
- Drop `player_match_stats_pre_0038` in a later migration once the fix has
  held for a week; do not drop it here.
- No em dashes in comments.

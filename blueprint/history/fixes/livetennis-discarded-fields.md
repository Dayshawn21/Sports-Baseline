# Store the livetennisapi fields the ingest discards

**Type:** Fix

## The problem

Every `/matches` response from livetennisapi already carries fields the ingest
throws away. `_player_fields` keeps only id, name, ranking, and birthday, and
`normalize_match` never reads the match-level extras at all.

Measured coverage over 130 upcoming ATP and WTA singles matches:

| Field | Level | Coverage |
|---|---|---|
| `indoor` | match | 130/130 (100%) |
| `tournament_id` | match | 130/130 (100%) |
| `ranking_points` | player | 258/260 (99.2%) |
| `ranking_movement` | player | 258/260 (99.2%) |
| `country` | player | 248/260 (95.4%) |
| `hand` | player | 234/260 (90.0%) |

These cost no extra API calls and no extra quota. They arrive in responses the
ingest already pays for.

`ranking_points` matters most. The model's `d_rank_log` feature uses rank
ordinal, where the gap between #1 and #5 is enormous and the gap between #95 and
#99 is noise. Points make that distance real.

Two constraints learned from the source audit that produced this fix:

- The `stats` block on `/players/{id}` (its `elo`, `computed`, and `season`
  sub-objects) mirrors TennisAbstract's hand-charted subset. It is sparse and
  stale: it reported Sinner with no 2026 season row against 59-1 in our own
  data. Nothing in this fix may read it, and ELO keeps coming from
  `app/ingest/elo.py`.
- The fields here come from the live match feed, which is current. Rankings on
  `/players/{id}` matched our freshly ingested feed ranks on 15 of 15 players.

## The fix

Widen the ingest and schema to keep these fields. No new endpoint calls.

Player-level identity (`hand`, `country`) belongs on `players`, because it does
not change per match. Ranking snapshots (`ranking_points`, `ranking_movement`)
belong on `matches` beside the existing `p1_rank`/`p2_rank`, because they are a
point-in-time value and storing them per match is what keeps future training
data honest.

It must not:

- change existing `p1_rank`/`p2_rank` behavior, or the 1-based ranking guard
  that treats 0 or negative as unranked
- break the `COALESCE` upsert pattern, so a payload missing a field never
  overwrites a stored value with `NULL`
- alter `match_key`, the `p1`/`p2` ordering, or player resolution
- read anything from the `/players/{id}` `stats` block
- change model features or retrain. This fix only stores the data; wiring
  `ranking_points` into `feature_builder` is separate work, once history exists.

## Build steps

- [x] Add the columns.

  Done when migration `0014` adds `indoor` (boolean), `tournament_id` (text) and
  `p1_ranking_points`, `p2_ranking_points` (int), `p1_ranking_movement`,
  `p2_ranking_movement` (text) to `matches`; adds `hand`, `country` (text) to
  `players`; `alembic upgrade head` succeeds; and `alembic downgrade -1` then
  `upgrade head` round-trips cleanly.

- [x] Parse the fields in the ingest.

  Done when `_player_fields` returns `ranking_points`, `ranking_movement`,
  `hand`, and `country`, `normalize_match` carries `indoor` and `tournament_id`,
  and tests in `api/tests/test_livetennis_parsers.py` prove a full payload, a
  payload missing every new field, and the existing unranked-player guard.

- [x] Persist them.

  Done when `upsert_match` accepts and writes the six match-level values and
  `upsert_player` writes `hand` and `country`, both `COALESCE`-guarded so a
  `NULL` never clobbers a stored value, with a test proving the clobber guard.

## Verify

- `cd api && .venv\Scripts\python.exe -m pytest`
- `cd api && alembic upgrade head`
- `cd api && .venv\Scripts\python.exe -m app.ingest.livetennis --days-ahead 1 --no-h2h`
- Query `matches` for today and confirm `indoor`, `tournament_id`, and the
  ranking-point columns are populated at roughly the coverage rates in the table
  above.
- Query `players` and confirm `hand` and `country` are set for players who
  appeared in today's slate, and that no previously stored value became `NULL`.
- Re-run the ingest a second time and confirm no field regresses to `NULL` on
  the repeat upsert.

## Result

Completed 2026-08-29. Verify passed: `pytest` 498 passed (up from 486),
`npm run build` clean, `npm run test` 31 passed. Migration `0014` round-tripped
`upgrade` / `downgrade -1` / `upgrade` cleanly.

Two live ingest runs of `--days-ahead 1 --no-h2h` upserted 53 matches each.
Stored coverage on matches from today onward:

| Field | Populated |
|---|---|
| `indoor` | 53/56 (94.6%) |
| `tournament_id` | 53/56 (94.6%) |
| `p1_ranking_points` | 53/56 (94.6%) |
| `p2_ranking_points` | 51/56 (91.1%) |
| `p1_ranking_movement` | 53/56 (94.6%) |

92 players gained `hand`, 105 gained `country`. The three unpopulated matches
predate the run window rather than failing to parse.

Clobber guard proven against the live database: all 163 affected rows were
snapshotted, the ingest re-run, and the values diffed identical. No field
regressed to `NULL`.

Sample stored row: `('US Open', False, '1218', 'Jessica Pegula', 3, 7265,
'same', 'R', 'USA')`. `Daniil Medvedev` stored with `country` NULL, which is the
partial-coverage path behaving correctly.

### Follow-ups deliberately excluded

- `ranking_points` is stored but not wired into `feature_builder`. That needs
  accumulated per-match history first and should be judged by a training run.
- `indoor` was `False` on all 130 sampled matches because the sample was taken
  in August. It starts carrying signal in the October indoor swing.

### Source audit that produced this fix

Probing the API on the BASIC tier established what is worth pulling and what is
not, and is worth not repeating:

- The `stats` block on `/players/{id}` (`elo`, `computed`, `season`) mirrors
  TennisAbstract's hand-charted subset. It is sparse and stale: it reported
  Sinner with no 2026 season row against 59-1 in our own data, and its `elo`
  matched our May 4 snapshot to the decimal while TennisAbstract had moved on.
  ELO stays with `app/ingest/elo.py`. Do not build features on that block.
- Gated above BASIC: `/matches/{id}/statistics`, `/points`, `/analysis`,
  `/charting/*`, `/rally/*`, WebSocket push, and the as-of Elo leaderboard are
  ULTRA; `/markets/{id}/prices` and the rank-ordered `/rankings` listing are PRO.
- Still unused and genuinely live: `/history/matches/{id}?points=complete`
  returns a point tape carrying `win_probability_p1` from the observed scoring
  feed. That is a calibration benchmark for build-plan item 15, not a feature.

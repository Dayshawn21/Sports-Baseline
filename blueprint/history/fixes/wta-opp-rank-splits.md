# Write opponent-rank splits for WTA players

**Type:** Fix
**Completed:** 2026-10-01
**Branch:** `fix/wta-opp-rank-splits`

## The problem

No WTA player had an opponent-rank split row (`stat_period = 'last_52w'`,
`split_type = 'opp_rank'`, values `top5` to `plus51`). `_persist_player_stats`
in `api/app/ingest/player_stats.py` wrote them only for ATP:

```python
await _upsert_baseline_rows(db, player_id, raw_rows, today)
if (tour or "").upper() == "ATP":
    await _upsert_opp_rank_rows(db, player_id, raw_rows, today)
```

The gate arrived with the contextual splits (commit `66df1d6`, message
"update") with no recorded reason. It was not needed: on 2026-10-01 the WTA
`/jsmatches/` rows carry the opponent's rank at index 12 (`I_ORANK`), the same
as ATP. Sabalenka has 28 top-20 matches in 52 weeks and `_aggregate` computed
her `top20` split, yet she had no row.

So `ctx_top20_missing` and `ctx_top50_missing` fired on every WTA match. The
previous fix's archive (`tennis-partial-context-flag.md`) guessed opponent-rank
parsing; that guess was wrong, and parsing is fine for both tours.

**Impact is data correctness, not picks.** The served v6 LightGBM models do not
read these features, so no probability, tier, EV or pick changed, and the chip
already hides these two flags. The rows feed the stored `quality_flags` and
`feature_snapshot` that a later retrain or grading reads.

## The fix

- `_persist_player_stats` calls `_upsert_opp_rank_rows` for every tour.
- Its `tour` parameter became unused and was removed, along with the argument
  at both callers (`ingest_single_player` and the batch `_write` closure).
- `MIN_MATCHES = 3` and the bucket thresholds are unchanged, so a player with
  under 3 top-20 matches still gets no row and keeps `ctx_top20_missing`.
- Rows populate on the next `player_stats` run (daily `tennis-ingest.yml` and
  the local `ingest_daily` task). No migration or backfill.

## Build steps

- [x] **Step 1 - drop the ATP gate.** Plus
  `test_persist_writes_opp_rank_rows_regardless_of_tour` in
  `api/tests/test_player_stats_contextual.py` (failed for WTA before the change),
  and the seven `_persist` doubles in `test_player_stats_deadlock.py` updated to
  the new signature.

## Evidence

- `pytest`: 2,110 passed.
- `python -m app.ingest.player_stats --today-only` (still running at merge):
  Sabalenka (player 2011) gained `top5` 10, `top10` 17, `top20` 28, `top50` 45,
  `plus51` 19 matches; WTA overall `top20` rows went from 0 to 31 mid-run.
- `/tennis/predictions/today`, 74 matches, mid-ingest:

| Flag | Before | After |
|---|---|---|
| `ctx_top20_missing` | 66 | 48 |
| `ctx_top50_missing` | 65 | 39 |
| `ctx_last90_missing` | 3 | 3 |

Remaining flags are mostly genuine (either player under 3 such matches; 36 of
the 74 are Challenger or WTA 125 matches) or players the run had not reached.

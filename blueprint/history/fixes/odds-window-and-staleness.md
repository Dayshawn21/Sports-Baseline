# Odds arrive too late to price the slate, and stale odds are never flagged

**Type:** Fix

## The problem

Two faults that compound. Together they mean roughly half the daily slate is
predicted with no market signal, and the guard meant to catch that has never
run.

### 1. The odds window is narrower than the slate

`.github/workflows/tennis-ingest.yml` runs the odds job hourly with
`--hours-ahead 4`, while the daily prediction job persists at 13:30 UTC. The
13:10 odds run therefore covers only 13:10 to 17:10.

Tomorrow's US Open slate against that window:

| Start window | Matches | Has odds at 13:30 |
|---|---|---|
| 15:00 to 17:00 | 19 | yes |
| 17:30 to 23:00 | **16** | **no** |

So 16 of 35 matches get predictions persisted carrying `market_missing`, with
the ensemble running on ELO and LightGBM only. Those are the late matches,
including the 23:00 night session.

The same gap hits props: without a match in the odds window there is no
`market_total_games`, so PrizePicks projections fall back to the model total.
Every one of the 1,061 best-of-5 props on tomorrow's slate came back
`projection_source: model_total` for this reason.

### 2. `odds_stale` is dead code

`feature_builder.build_features` takes `odds_stale: bool = False` and reads it
once to append a `stale_odds` flag. **Nothing in the codebase ever passes it as
`True`.** Downstream, `ensemble.py` halves the market weight (`mult = 0.5`) on
that flag, so a documented safety mechanism has never fired.

The data needed is already there and simply unread: `get_latest_odds` and the
bulk odds loaders in `app/repositories/matches.py` all return `fetched_at`.

Today a twenty-hour-old line is weighted identically to one fetched a minute
ago. Widening the window without fixing this would make that worse, because
odds would routinely be fetched much earlier.

## The fix

Widen the odds window so the whole day is priced before predictions persist,
and wire the staleness flag that makes early odds safe to hold.

Widening is safe because `upsert_odds` is an append-only INSERT and every reader
orders `fetched_at DESC`, so a later fetch always supersedes an earlier one. A
frequent refresh must stay: it is what keeps the newest row current.

**Cadence decision, taken during the build.** This spec originally required the
hourly cadence to stay. It was changed to every 2 hours after the odds-api.io
free plan's 500 requests/day cap came to light. A run costs 1 events call plus
one batch per 10 matches, so the busiest observed day (123 matches) is 14 calls
per run: hourly would be 336/day against the cap, leaving only 33% headroom, and
hitting it would drop odds to zero for the rest of the day. Two hours costs
168/day, and still sits well inside the 6h staleness threshold so healthy runs
never flag themselves.

Staleness is measured against the match, not the clock. Odds fetched twelve
hours before a match that is still twelve hours away are current; the same odds
an hour before play are not. Use age since fetch, with a threshold generous
enough that the normal hourly cadence never trips it.

It must not:

- change `upsert_odds` to update in place. Append-only is what makes the newest
  fetch win and preserves line-movement history
- refresh less often than every 2 hours, which is the cadence agreed above
- alter ensemble weights, the `mult = 0.5` downweight, or any other quality flag
- change predictions for a match whose odds are fresh. Existing tests cover the
  fresh path and none of those numbers may move
- introduce I/O into `app/core/`

Out of scope: using stored line movement as a signal. Appending every fetch
means the table already records how a line moved, which is genuinely useful and
is its own feature, not this fix.

## Build steps

- [x] Wire `odds_stale` from the odds row's `fetched_at`.

  Done when both the single-match and cached batch prediction paths in
  `app/services/tennis/predictor.py` derive staleness from `fetched_at` and pass
  it to `build_features`, a shared helper in `app/core/` decides staleness from
  a timestamp and a threshold, and tests prove fresh odds stay unflagged, old
  odds raise `stale_odds`, and a missing `fetched_at` does not raise.

- [x] Confirm the flag reaches the ensemble downweight.

  Done when a test proves a prediction built from stale odds carries
  `stale_odds` in its quality flags and applies the existing `mult = 0.5` market
  weight, while a fresh-odds prediction is unchanged.

- [x] Widen the odds ingest window.

  Done when the scheduled odds job covers the full remaining day rather than
  four hours, the workflow change is the only edit to
  `.github/workflows/tennis-ingest.yml`, and a real run shows matches beyond the
  old four-hour horizon receiving odds.

## Verify

- `cd api && .venv\Scripts\python.exe -m pytest`
- `cd web && npm run build`
- Confirm the pre-existing suite passes unchanged, since it all covers the fresh
  path.
- Run the odds ingest with the widened window and confirm matches starting late
  tomorrow receive odds, where the four-hour window returned none.
- Re-run predictions and confirm the count of matches carrying `market_missing`
  drops sharply against the 16 of 35 measured above.
- Artificially age an odds row, rebuild that match's prediction, and confirm
  `stale_odds` appears in its quality flags and the market component is halved.
- Confirm a match with odds fetched minutes ago carries neither flag.

## Result

Completed 2026-08-29. Verify passed: `pytest` 541 passed (up from 527),
`npm run build` clean, `npm run test` 31 passed. 14 tests added in
`api/tests/test_odds_staleness.py`. No pre-existing test moved.

### Window

Measured back to back on the same slate:

| Window | Matches priced | Odds rows |
|---|---|---|
| 4h (old) | 2 | 6 |
| 14h (new) | 16 | 28 |

Upcoming matches carrying odds went from 15 of 56 to 17 of 56 on a thin evening
slate. The material gain is at the 13:10 run before the 13:30 prediction job,
where it is the difference between pricing 19 of 35 US Open matches and all 35.

### Staleness

`odds_are_stale` in `app/core/odds.py`, threshold `STALE_ODDS_HOURS = 6.0`,
wired into both the single-match and cached batch paths in `predictor.py` from
the `fetched_at` those paths already fetched and discarded.

On live data at completion: **3 of 17** upcoming matches with odds were old
enough to flag, one of them a **28.5-hour-old** line that had been weighted as a
live market. This flag had never fired before.

Three edge cases decided deliberately: a missing `fetched_at` is not stale
(absent odds already report `market_missing`, and flagging both would halve the
weight of a possibly-current market); a naive timestamp is read as UTC; a
future timestamp is not stale, because host clock skew is not staleness.

### The gate that nearly broke it silently

Each job in `tennis-ingest.yml` is selected by matching
`github.event.schedule` against its exact cron string. Changing the cron alone
would have stopped the odds job running on schedule **permanently**, with the
workflow still reporting green. Three edits were required and all three are
load-bearing: the `cron:` entry, the job's `if:` gate, and the `--hours-ahead`
argument.

This is the third silent-failure mode found in one session, after the
inactivity-disabled schedule and the `odds_stale` dead code. Any future change
to a cron string in this workflow must change the matching gate in the same
diff.

### Quota

The odds-api.io free plan caps at 500 requests/day (100/hour burst). A run costs
1 events call plus one batch per 10 matches. Busiest observed day is 123
matches, so 14 calls per run: **168/day** at the 2-hour cadence against 336 if
hourly. Recheck this if match volume grows or another sport is added.

`DEFAULT_BOOKMAKERS` is `DraftKings,Bet365`, both recreational, so the July 2026
move of sharp books and exchanges to paid plans does not affect this ingest.

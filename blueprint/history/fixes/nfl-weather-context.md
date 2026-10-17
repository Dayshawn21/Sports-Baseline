# NFL matchup weather context

**Type:** Fix

## Delivered

- A checked-in 32-team stadium registry with outdoor, dome, and retractable venue types.
- Alembic migration `0022` for append-only NFL game-weather snapshots.
- Manual `app.ingest.nfl_weather` using Open-Meteo, never either odds provider.
- Three-hour snapshot freshness guard, bounded window, and no-network/no-write dry run.
- Weather context on the NFL matchup board: outdoor forecast, dome-neutral state,
  retractable-roof confirmation state, unavailable state, and descriptive wind/rain caution.

Weather remains descriptive only. It does not affect projections, edges, ranks,
or bankroll sizing.

## Verification

- Migration `0022` applied locally.
- Dry run found 11 outdoor and 6 indoor/retractable games without provider calls or writes.
- Live Open-Meteo refresh stored 10 outdoor snapshots; one game remained unavailable.
- Local `/nfl/slate` response confirmed stored forecast data and safe fallback venue states.
- Full API suite: 775 passed.
- Web tests: 66 passed.
- Production web build passed.

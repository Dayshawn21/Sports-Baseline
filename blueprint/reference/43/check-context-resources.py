"""Current-data read-only resource check, run from api/ with its venv."""
import asyncio
import gc
import json
import sys
import tracemalloc
from pathlib import Path
from time import perf_counter
from sqlalchemy import event, text
from app.db.pool import SessionLocal, engine
from app.repositories import nfl
from app.services.nfl.matchup_context import build_game_context, build_week_matchup_context

queries = []
@event.listens_for(engine.sync_engine, 'before_cursor_execute')
def count_sql(conn, cursor, statement, parameters, context, executemany):
    queries.append(statement)

async def measured(db, label, build):
    gc.collect()
    queries.clear()
    tracemalloc.start()
    started = perf_counter()
    result = await build()
    elapsed = perf_counter() - started
    payload = (result.model_dump_json(by_alias=True) if not isinstance(result, dict)
               else json.dumps({str(k): v.model_dump(mode='json', by_alias=True) for k,v in result.items()}))
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return result, {'sample':label,'seconds':round(elapsed,4),'queryCount':len(queries),
                    'responseBytes':len(payload.encode()),'pythonCurrentMiB':round(current/1048576,3),
                    'pythonPeakMiB':round(peak/1048576,3)}

async def main():
    try:
        async with SessionLocal() as db:
            await db.execute(text('SET TRANSACTION READ ONLY'))
            await db.execute(text("SET LOCAL statement_timeout = '15s'"))
            games = await nfl.get_context_games(db, season=2026, week=7)
            assert games
            records=[]
            week, record = await measured(db, 'week-7-matchup-batch', lambda:build_week_matchup_context(db,2026,7))
            record['games']=len(week); records.append(record)
            for target in games:
                result, record = await measured(db, f'game-{target.game_id}', lambda:build_game_context(db,target.game_id))
                assert result.matchup_context == week[target.game_id]
                assert result.cutoff_week == 6
                assert all(m.window_end is None or m.window_end < target.start_utc.date()
                           for p in result.players for window in [p.season_usage,p.recent_usage]
                           for m in [window.targets,window.target_share,window.carries,window.carry_share,window.avg_game_snap_share])
                record['players']=len(result.players);records.append(record)
            report={'season':2026,'week':7,'samples':records,'allMatchupParity':True,
                    'transaction':'read only; rollback','scope':'current regular-season context only; no providers, models, grading or holdout scoring',
                    'limits':'Local sequential tracemalloc includes serialization; excludes total RSS, driver/native allocations and hosted concurrent load.'}
            await db.rollback()
            Path(__file__).with_name('step-5-resources.json').write_text(json.dumps(report,indent=2)+'\n')
            print(json.dumps(report))
    except Exception as exc:
        print('Resource check failed: '+type(exc).__name__)
        raise SystemExit(1)
    finally:
        await engine.dispose()
if __name__=='__main__':
    if sys.platform=='win32':asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())

"""Run from api/ with its venv and PYTHONPATH=.; prints no credentials."""
import asyncio
import json
import sys
from pathlib import Path
from time import perf_counter

from sqlalchemy import text

from app.db.pool import SessionLocal, engine
from app.repositories import nfl
from app.services.nfl.matchup_context import build_game_context, build_week_matchup_context


async def main() -> None:
    try:
        async with SessionLocal() as db:
            await db.execute(text("SET TRANSACTION READ ONLY"))
            await db.execute(text("SET LOCAL statement_timeout = '15s'"))
            games = await nfl.get_context_games(db, season=2026, week=7)
            if not games:
                print("No stored 2026 week 7 NFL games; no further reads.")
                return
            target = games[0]
            started = perf_counter()
            context = await build_game_context(db, target.game_id)
            elapsed = perf_counter() - started
            started = perf_counter()
            week = await build_week_matchup_context(db, 2026, 7)
            week_elapsed = perf_counter() - started
            assert context.matchup_context == week[target.game_id]
            report = {
                "season": 2026, "week": 7, "gameId": target.game_id,
                "players": len(context.players), "weekGames": len(week),
                "gameSeconds": round(elapsed, 4), "weekContextSeconds": round(week_elapsed, 4),
                "gameResponseBytes": len(context.model_dump_json(by_alias=True).encode()),
                "matchupParity": True,
                "availableTargetShares": sum(p.season_usage.target_share.value is not None for p in context.players),
                "availableAllowedMeasures": sum(
                    m.value is not None for t in (context.matchup_context.away, context.matchup_context.home)
                    for m in t.allowed.__dict__.values()
                ),
                "transaction": "read only; rolled back",
                "scope": "one stored game plus week matchup batch; no holdout, model or provider calls",
            }
            Path(__file__).with_name("step-2-stored-read.json").write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps(report))
    except Exception as exc:
        print("Read-only stored-data check failed: " + type(exc).__name__)
        raise SystemExit(1)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())

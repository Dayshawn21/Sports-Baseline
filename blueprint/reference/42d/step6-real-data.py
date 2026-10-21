"""Read-only stored-data and query-plan evidence; run from api/ with its venv."""
from __future__ import annotations

import asyncio
import json
import sys
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import cast

from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import TextClause

from app.core.nba_team_stats import team_stats
from app.db.pool import SessionLocal, engine
from app.repositories import nba as repo
from app.services.nba.game_detail import build_game_detail
from app.services.nba.line_only_props import build_line_only_props
from app.services.nba.prop_board import build_prop_board
from app.services.nba.props import build_props

OUTPUT = Path(__file__).parent


class Capture:
    statement: TextClause
    params: dict[str, object]

    async def execute(self, statement: TextClause, params: dict[str, object]) -> Capture:
        self.statement, self.params = statement, params
        return self

    def mappings(self) -> list[RowMapping]:
        return []


async def main() -> None:
    try:
        async with SessionLocal() as db:
            await db.execute(text('SET TRANSACTION READ ONLY'))
            await db.execute(text("SET LOCAL statement_timeout = '20s'"))
            historical = (await db.execute(text("""
                SELECT g.id, g.game_date FROM sport_games g
                WHERE g.sport = 'nba' AND g.season = 2024 AND g.game_type = 'REG'
                  AND EXISTS (SELECT 1 FROM nba_player_game_stats s WHERE s.game_id = g.id)
                ORDER BY g.game_date DESC, g.id LIMIT 1
            """))).mappings().first()
            current = (await db.execute(text("""
                SELECT g.id, g.game_date FROM sport_games g
                WHERE g.sport = 'nba' AND g.season = 2026 AND g.game_type = 'REG'
                  AND EXISTS (SELECT 1 FROM sport_prop_lines l WHERE l.sport = 'nba'
                      AND l.game_id = g.id AND l.player_id IS NOT NULL AND l.segment = 'full_game')
                ORDER BY g.game_date, g.id LIMIT 1
            """))).mappings().first()
            assert historical is not None and current is not None
            before = historical['game_date']
            capture = Capture()
            await repo.get_team_box_games(cast(AsyncSession, capture), 2024, before)
            plan = (await db.execute(text('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) ' + str(capture.statement)), capture.params)).scalar_one()[0]
            tracemalloc.start()
            start = perf_counter()
            boxes = await repo.get_team_box_games(db, 2024, before)
            league = team_stats(boxes, 2024, before)
            elapsed = perf_counter() - start
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            assert len(league) == 30
            historical_detail = await build_game_detail(db, historical['id'])
            assert historical_detail is not None and historical_detail.team_stats is not None
            sample = historical_detail.team_stats.home
            assert sample.stats['points'].for_.games > 0
            as_of = datetime.now(timezone.utc)
            start = perf_counter()
            detail = await build_game_detail(db, current['id'], as_of)
            props = await build_props(db, current['id'], as_of)
            plain = await build_line_only_props(db, current['id'], as_of)
            board = await build_prop_board(db, current['game_date'], current['game_date'], as_of)
            response_seconds = perf_counter() - start
            assert detail is not None and props is not None and plain is not None
            board_game = next(game for game in board.games if game.game_id == current['id'])
            assert detail.team_stats == props.team_stats == plain.team_stats == board_game.team_stats
            assert props.lines == board_game.lines and plain.lines == board_game.line_only_lines
            assert props.lines or plain.lines
            # Preserve every rung for one assists player and one line-only player.
            player = next(line.player_id for line in props.lines if line.market == 'assists')
            plain_player = plain.lines[0].player_id if plain.lines else None
            sample_props = props.model_copy(update={'lines': [line for line in props.lines if line.player_id == player]})
            sample_plain = plain.model_copy(update={'lines': [line for line in plain.lines if line.player_id == plain_player]})
            fixtures = {
                'capturedAt': as_of.isoformat(),
                'sampledPlayersOnly': True,
                'historical': historical_detail.model_dump(mode='json', by_alias=True),
                'game': detail.model_dump(mode='json', by_alias=True),
                'props': sample_props.model_dump(mode='json', by_alias=True),
                'plain': sample_plain.model_dump(mode='json', by_alias=True),
            }
            (OUTPUT / 'step6-stored-fixtures.json').write_text(json.dumps(fixtures, indent=2), encoding='utf-8')
            evidence = {
                'historicalSeason': 2024, 'beforeDate': str(before), 'historicalGameId': historical['id'],
                'groupedGames': len(boxes), 'groupedSides': sum(len(game.sides) for game in boxes),
                'queryPlanMs': {'planning': plan['Planning Time'], 'execution': plan['Execution Time']},
                'queryPlanRoot': plan['Plan']['Node Type'], 'queryPlanRows': plan['Plan']['Actual Rows'],
                'groupedReadAndMathSeconds': round(elapsed, 3), 'pythonTracedPeakMiB': round(peak / 1024**2, 2),
                'sampleHomeTeam': sample.team, 'sampleCompletedGames': sample.completed_games,
                'samplePointsGames': sample.stats['points'].for_.games,
                'currentGameId': current['id'], 'currentDate': str(current['game_date']),
                'currentModelledLines': len(props.lines), 'currentLineOnlyLines': len(plain.lines),
                'boardGames': len(board.games), 'boardJsonBytes': len(board.model_dump_json(by_alias=True).encode()),
                'fourAssembliesSeconds': round(response_seconds, 3), 'parity': True, 'readOnly': True,
            }
            (OUTPUT / 'step6-data-results.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
            print(json.dumps(evidence, indent=2))
            await db.rollback()
    finally:
        await engine.dispose()


if __name__ == '__main__':
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())

"""Spread, total, and set markets must be read at their newest line per book, with
recency deciding before book preference."""
import asyncio
import sqlite3
from types import SimpleNamespace
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import TextClause

from app.repositories.matches import get_all_market_odds_batch
from app.repositories.props import _BOOK_KEY_SQL, get_today_match_odds_as_props
from app.routers.props import _fetch_market_total_games


class _Rows:
    def fetchall(self) -> list[tuple]:
        return []


class _RecordingSession:
    def __init__(self) -> None:
        self.statement = ""

    async def execute(self, statement: TextClause, params: dict[str, object]) -> _Rows:
        self.statement = " ".join(str(statement).split())
        return _Rows()


def _sql(call) -> str:
    session = _RecordingSession()
    asyncio.run(call(cast(AsyncSession, session)))
    return session.statement


def _book_key(book: str) -> str:
    with sqlite3.connect(":memory:") as conn:
        return conn.execute(f"SELECT {_BOOK_KEY_SQL} FROM (SELECT ? AS book) mo", (book,)).fetchone()[0]


def test_bet365_under_its_old_name_is_the_same_book():
    assert _book_key("betonline.ag") == _book_key("Bet365") == "bet365"
    assert _book_key("DraftKings") == "draftkings"


def test_market_props_keep_only_the_newest_row_per_match_market_and_book():
    sql = _sql(lambda db: get_today_match_odds_as_props(db, ["bet365"]))
    assert "DISTINCT ON (mo.match_id, mo.market, CASE WHEN LOWER(mo.book)" in sql
    inner_order = sql.split("ORDER BY")[1]
    assert inner_order.index("END") < inner_order.index("mo.fetched_at DESC")


def test_all_markets_break_same_run_ties_by_book_after_recency():
    order = _sql(lambda db: get_all_market_odds_batch(db, [1])).split("ORDER BY", 1)[1]
    assert order.index("fetched_at DESC") < order.index("CASE LOWER(book)")


def test_the_total_games_reader_prefers_the_newest_line_over_the_preferred_book():
    order = _sql(lambda db: _fetch_market_total_games(db, [SimpleNamespace(match_id=1)])).split("ORDER BY", 1)[1]
    assert order.index("mo.fetched_at DESC") < order.index("CASE")

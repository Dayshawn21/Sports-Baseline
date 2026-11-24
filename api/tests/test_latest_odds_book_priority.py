"""One odds run stores every book with the same fetched_at, so the latest moneyline
must be chosen by a fixed book priority rather than whichever row DISTINCT ON meets
first."""
import asyncio
import sqlite3
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import TextClause

from app.repositories.matches import (
    _BOOK_PRIORITY_SQL,
    get_latest_odds,
    get_latest_odds_batch,
)


def _rank(book: str) -> int:
    with sqlite3.connect(":memory:") as conn:
        return conn.execute(f"SELECT {_BOOK_PRIORITY_SQL} FROM (SELECT ? AS book)", (book,)).fetchone()[0]


class TestBookPriority:
    def test_draftkings_outranks_bet365_which_outranks_the_exchange(self):
        assert _rank("draftkings") < _rank("bet365") < _rank("betfair exchange") < _rank("pinnacle")

    def test_fanduel_ranks_after_stored_bet365_and_before_the_exchange(self):
        assert _rank("bet365") < _rank("fanduel") < _rank("betfair exchange") < _rank("pinnacle")
        assert _rank("FanDuel") == _rank("fanduel")

    def test_legacy_bet365_rows_rank_with_bet365(self):
        assert _rank("betonline.ag") == _rank("bet365") == _rank("betonline")

    def test_ranking_ignores_case(self):
        assert _rank("DraftKings") == _rank("draftkings")


class _Rows:
    def fetchone(self) -> None:
        return None

    def fetchall(self) -> list[tuple]:
        return []


class _RecordingSession:
    def __init__(self) -> None:
        self.statement = ""

    async def execute(self, statement: TextClause, params: dict[str, object]) -> _Rows:
        self.statement = " ".join(str(statement).split())
        return _Rows()


def _order_by(statement: str) -> str:
    return statement.split("ORDER BY", 1)[1]


class TestQueriesBreakTiesByBook:
    def test_single_match_orders_by_recency_then_book(self):
        session = _RecordingSession()
        asyncio.run(get_latest_odds(cast(AsyncSession, session), 1))
        order_by = _order_by(session.statement)
        assert order_by.index("fetched_at DESC") < order_by.index("CASE LOWER(book)")

    def test_batch_retains_selected_odds_row_identity_for_shadow_provenance(self):
        class Rows:
            def fetchall(self):
                return [(50, "draftkings", -110, -110, None, None, 1234)]

        class Session:
            async def execute(self, statement, params):
                return Rows()

        odds = asyncio.run(get_latest_odds_batch(cast(AsyncSession, Session()), [50]))
        assert odds[50]["row_id"] == 1234 and odds[50]["book"] == "draftkings"
        assert (odds[50]["p1_odds"], odds[50]["p2_odds"]) == (-110, -110)

    def test_batch_orders_by_recency_then_book(self):
        session = _RecordingSession()
        asyncio.run(get_latest_odds_batch(cast(AsyncSession, session), [1, 2]))
        order_by = _order_by(session.statement)
        assert order_by.index("fetched_at DESC") < order_by.index("CASE LOWER(book)")

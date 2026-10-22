import asyncio
from datetime import date, datetime, timedelta, timezone

from app.repositories.tennis_match_context import get_book_freshness, get_workload_matches


class Result:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


class Database:
    def __init__(self, rows):
        self.rows = rows
        self.params = None

    async def execute(self, _sql, params):
        self.params = params
        return Result(self.rows)


def test_workload_read_is_bounded_to_requested_players_and_year():
    on = date(2026, 10, 22)
    db = Database([(1, 123, on - timedelta(days=1), "completed", "6-4 6-3")])
    result = asyncio.run(get_workload_matches(db, [1, 2], on))
    assert db.params == {"ids": [1, 2], "since": on - timedelta(days=365), "on": on}
    assert result[1][0].match_id == 123
    assert result[2] == []


def test_odds_freshness_retains_book_identity_and_aware_prestart_cutoff():
    cutoff = datetime(2026, 10, 22, 3, 15, tzinfo=timezone.utc)
    fetched = cutoff - timedelta(minutes=5)
    db = Database([("draftkings", fetched)])
    result = asyncio.run(get_book_freshness(db, 123, cutoff))
    assert db.params == {"mid": 123, "before": cutoff}
    assert (result[0].book, result[0].fetched_at) == ("draftkings", fetched)

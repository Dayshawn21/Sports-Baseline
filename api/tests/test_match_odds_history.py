import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.pool import get_db
from app.repositories.matches import Match, MatchMeta, OddsHistoryRow, get_odds_history
from app.routers import tennis as tennis_router
from app.services.tennis import match_detail

START = datetime(2026, 9, 28, 10, 30, tzinfo=timezone.utc)
EARLY = datetime(2026, 9, 27, 14, 0, tzinfo=timezone.utc)
LATER = datetime(2026, 9, 28, 9, 0, tzinfo=timezone.utc)


class _Result:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


class _Db:
    def __init__(self, rows):
        self.rows = rows
        self.sql = ""
        self.params = None

    async def execute(self, sql, params):
        self.sql = str(sql)
        self.params = params
        return _Result(self.rows)


def test_history_is_oldest_first_and_capped_at_the_start():
    db = _Db([])

    asyncio.run(get_odds_history(db, 5, "moneyline", START))

    assert db.params == {"mid": 5, "mkt": "moneyline", "before": START}
    assert "fetched_at < :before" in db.sql
    assert "ORDER BY fetched_at ASC" in db.sql


def test_history_rows_map_and_numeric_lines_become_floats():
    db = _Db([
        ("draftkings", None, None, Decimal("22.5"), EARLY),
        ("bet365", 120, -150, None, LATER),
    ])

    rows = asyncio.run(get_odds_history(db, 5, "total_games", None))

    assert rows == [
        OddsHistoryRow(book="draftkings", p1_odds=None, p2_odds=None, line=22.5, fetched_at=EARLY),
        OddsHistoryRow(book="bet365", p1_odds=120, p2_odds=-150, line=None, fetched_at=LATER),
    ]
    assert isinstance(rows[0].line, float)
    assert db.params["before"] is None


def _match(start_utc):
    return Match(
        id=5, match_key="k5", match_date=date(2026, 9, 28), start_utc=start_utc,
        tour="ATP", surface="Hard", tournament="Tokyo", round="R16", best_of=3,
        p1_id=1, p2_id=2, p1_rank=None, p2_rank=None, winner_id=None,
        status="scheduled", sofascore_id=None,
    )


def _patch(monkeypatch, start_utc=START):
    calls = []

    async def get_match(_db, match_id):
        return (_match(start_utc), MatchMeta(indoor=None, score=None)) if match_id == 5 else None

    async def get_odds_history_fake(_db, match_id, market, before):
        calls.append((match_id, market, before))
        return [OddsHistoryRow(book="draftkings", p1_odds=148, p2_odds=-180, line=None, fetched_at=EARLY)]

    monkeypatch.setattr(match_detail.match_repo, "get_match", get_match)
    monkeypatch.setattr(match_detail.match_repo, "get_odds_history", get_odds_history_fake)
    return calls


def test_service_caps_at_the_match_start(monkeypatch):
    calls = _patch(monkeypatch)

    rows = asyncio.run(match_detail.match_odds_history(None, 5, "moneyline"))

    assert len(rows) == 1
    assert calls == [(5, "moneyline", START)]


def test_service_without_a_start_reads_everything(monkeypatch):
    calls = _patch(monkeypatch, start_utc=None)

    asyncio.run(match_detail.match_odds_history(None, 5, "total_games"))

    assert calls == [(5, "total_games", None)]


def test_service_unknown_match_is_none(monkeypatch):
    _patch(monkeypatch)

    assert asyncio.run(match_detail.match_odds_history(None, 404, "moneyline")) is None


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(tennis_router.router, prefix="/tennis")
    app.dependency_overrides[get_db] = lambda: None
    return TestClient(app)


def test_route_returns_rows_in_camel_case(monkeypatch):
    _patch(monkeypatch)

    res = _client().get("/tennis/matches/5/odds-history")

    assert res.status_code == 200
    body = res.json()
    assert body["market"] == "moneyline"
    assert body["rows"][0]["p1Odds"] == 148
    assert body["rows"][0]["fetchedAt"].startswith("2026-09-27T14:00:00")


def test_route_404s_an_unknown_match(monkeypatch):
    _patch(monkeypatch)

    assert _client().get("/tennis/matches/404/odds-history").status_code == 404


def test_route_rejects_a_market_it_does_not_chart(monkeypatch):
    calls = _patch(monkeypatch)

    res = _client().get("/tennis/matches/5/odds-history", params={"market": "set1_winner"})

    assert res.status_code == 422
    assert calls == []

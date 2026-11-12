from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.tennis_prop_reasons import PropReasons, Reason, RecentSummary, RecentValue
from app.db.pool import get_db
from app.repositories.props import Prop
from app.routers import props as props_router
from app.schemas.props import PropLine
from app.services.tennis.prop_reasons import PropReasonsResult

FETCHED = datetime(2026, 11, 10, 12, tzinfo=UTC)


def stored(line: Decimal | None = Decimal("7.5")) -> Prop:
    return Prop(
        id=7, player_id=812, player_name="A. Player", match_id=55, source="prizepicks",
        stat_type="Aces", line=line, odds_type="standard", fetched_at=FETCHED, start_time=FETCHED,
    )


def client(monkeypatch, prop: Prop | None) -> TestClient:
    async def lookup(_db, _prop_id):
        return prop

    async def enrich(_db, props, now):
        return [PropLine(id=p.id, player_id=p.player_id, match_id=p.match_id, source=p.source,
                         stat_type=p.stat_type, odds_type=p.odds_type, fetched_at=p.fetched_at,
                         start_time=p.start_time) for p in props]

    async def build(_db, _prop, _line):
        chart = [RecentValue(date(2026, 10, d), "B. Rival", "Hard", 3, v) for d, v in ((20, 6), (27, 9))]
        reasons = PropReasons(
            over=(Reason("hit_rate", "Cleared the line in 8 of 10 recent matches"),),
            under=(),
            caveats=(Reason("stale_stats", "Rolling stats are out of date"),),
            summary=RecentSummary(10, 8, 2, 0, 9.6, 9.0),
        )
        return PropReasonsResult(reasons, chart)

    monkeypatch.setattr(props_router, "get_prizepicks_prop", lookup)
    monkeypatch.setattr(props_router, "_enrich_props", enrich)
    monkeypatch.setattr(props_router, "build_prop_reasons", build)
    app = FastAPI()
    app.include_router(props_router.router, prefix="/tennis/props")
    app.dependency_overrides[get_db] = lambda: None
    return TestClient(app)


def test_an_unknown_or_non_prizepicks_id_is_404(monkeypatch):
    response = client(monkeypatch, None).get("/tennis/props/prizepicks/7/reasons")
    assert response.status_code == 404


def test_a_line_without_a_number_is_422(monkeypatch):
    response = client(monkeypatch, stored(line=None)).get("/tennis/props/prizepicks/7/reasons")
    assert response.status_code == 422


def test_reasons_come_back_camel_cased_with_the_chart_in_order(monkeypatch):
    body = client(monkeypatch, stored()).get("/tennis/props/prizepicks/7/reasons").json()
    assert (body["propId"], body["playerId"], body["statType"], body["line"]) == (7, 812, "Aces", 7.5)
    assert body["version"] == "reasons-v1"
    assert [(v["matchDate"], v["value"], v["bestOf"]) for v in body["recent"]] == [("2026-10-20", 6, 3), ("2026-10-27", 9, 3)]
    assert body["summary"] == {"matches": 10, "over": 8, "under": 2, "push": 0, "average": 9.6, "median": 9.0}
    assert body["over"] == [{"key": "hit_rate", "text": "Cleared the line in 8 of 10 recent matches"}]
    assert (body["under"], body["caveats"][0]["key"]) == ([], "stale_stats")


def test_a_non_numeric_id_does_not_reach_the_route(monkeypatch):
    assert client(monkeypatch, stored()).get("/tennis/props/prizepicks/audit/reasons").status_code == 404

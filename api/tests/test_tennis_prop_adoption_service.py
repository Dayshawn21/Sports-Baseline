import asyncio
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.prop_ranking_rule import SliceResult
from app.core.tennis_prop_adoption import to_payload
from app.core.tennis_prop_check import CheckFunnel, CheckResult, TennisSlice
from app.db.pool import get_db
from app.main import app
from app.repositories.props import Prop
from app.routers import props as props_router
from app.schemas.props import PropLine
from app.services.tennis import prop_adoption

NOW = datetime(2026, 11, 2, 12, tzinfo=UTC)
START = NOW + timedelta(hours=3)
# Synthetic: no real slice has been graded.
ACES_ATP = TennisSlice("aces", "ATP", "book", "standard", "over")


class _Row:
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.computed_at = NOW


class _Result:
    def __init__(self, row: _Row | None) -> None:
        self.row = row

    def first(self) -> _Row | None:
        return self.row


class _Session:
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.params: dict[str, object] = {}

    async def execute(self, statement: object, params: dict[str, object]) -> _Result:
        self.params = params
        return _Result(_Row(self.payload) if self.payload is not None else None)


def _payload(version: str = "props-v3", adopted: tuple[TennisSlice, ...] = (ACES_ATP,)) -> dict[str, object]:
    result = CheckResult(
        slices={key: SliceResult("adopt", 200, 4, 150, 0.577) for key in adopted},
        exclusions={}, funnel=CheckFunnel(0, 0, 0, 0), finished_weeks=4,
    )
    return to_payload(result, version, date(2026, 11, 1), NOW)


def _load(payload: object) -> frozenset[TennisSlice]:
    return asyncio.run(prop_adoption.load_adopted(cast(AsyncSession, _Session(payload))))


def _pair(line_id: int, stat: str = "Aces", **line_fields: object) -> tuple[Prop, PropLine]:
    prop = Prop(
        id=line_id, player_id=line_id, player_name="A Player", match_id=line_id, source="prizepicks",
        stat_type=stat, line=Decimal("6.5"), odds_type="standard", fetched_at=NOW, start_time=START,
        match_tour="ATP", p1_tour="ATP", p2_tour="ATP",
    )
    fields: dict[str, object] = {
        "id": line_id, "player_id": line_id, "match_id": line_id, "source": "prizepicks", "stat_type": stat,
        "line": Decimal("6.5"), "odds_type": "standard", "fetched_at": NOW, "start_time": START,
        "p_over": 0.7, "p_under": 0.3, "p_push": 0.0, "market_total_games": 22.5, **line_fields,
    }
    return prop, PropLine.model_validate(fields)


def _apply(adopted: frozenset[TennisSlice], *pairs: tuple[Prop, PropLine]) -> list[PropLine]:
    return prop_adoption.apply_adoption([p for p, _ in pairs], [line for _, line in pairs], adopted, NOW)


def test_the_row_read_is_the_board_version() -> None:
    session = _Session(_payload())
    asyncio.run(prop_adoption.load_adopted(cast(AsyncSession, session)))

    assert session.params == {"report": "tennis_prop_adoption:props-v3", "season": 0}


@pytest.mark.parametrize("payload", [
    None,
    _payload(version="props-v4"),
    {**_payload(), "rule": "tennis-props-check-v0"},
    {**_payload(), "adopted": "aces"},
    ["not", "an", "object"],
])
def test_an_unusable_row_adopts_nothing_and_changes_no_line(payload: object) -> None:
    pairs = [_pair(1), _pair(2, "Double Faults")]
    lines = _apply(_load(payload), *pairs)

    assert _load(payload) == frozenset()
    assert lines == [line for _, line in pairs]
    assert all(line.adopted_pick is None for line in lines)


def test_an_adopted_slice_marks_exactly_its_line() -> None:
    aces, faults = _apply(_load(_payload()), _pair(1), _pair(2, "Double Faults"))

    assert faults.adopted_pick is None
    assert aces.adopted_pick is not None
    assert (aces.adopted_pick.side, aces.adopted_pick.probability) == ("over", 0.7)
    assert aces.adopted_pick.margin == round(0.7 - aces.adopted_pick.break_even, 3)
    assert (aces.adopted_pick.rule, aces.adopted_pick.projection_version) == ("tennis-props-check-v1", "props-v3")
    assert aces.model_copy(update={"adopted_pick": None}) == _pair(1)[1]


@pytest.mark.parametrize("missing", ["player_id", "match_id", "start_time"])
def test_a_line_missing_its_identity_is_not_a_pick(missing: str) -> None:
    [line] = _apply(frozenset({ACES_ATP}), _pair(1, **{missing: None}))

    assert line.adopted_pick is None


def test_the_api_field_is_camel_case() -> None:
    [line] = _apply(frozenset({ACES_ATP}), _pair(1))

    assert line.model_dump(by_alias=True)["adoptedPick"]["breakEven"] == pytest.approx(0.577, abs=0.001)


@pytest.fixture
def no_row_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    async def no_props(db: object, source: str | None = None) -> list[Prop]:
        return []

    async def no_lines(db: object, props: list[Prop]) -> list[PropLine]:
        return []

    async def session() -> object:
        return _Session(None)

    monkeypatch.setattr(props_router, "get_today_props", no_props)
    monkeypatch.setattr(props_router, "_enrich_props", no_lines)
    app.dependency_overrides[get_db] = session
    yield TestClient(app)
    app.dependency_overrides.pop(get_db)


def test_the_prizepicks_route_serves_with_no_stored_row(no_row_client: TestClient) -> None:
    response = no_row_client.get("/tennis/props/prizepicks")

    assert response.status_code == 200
    assert response.json() == {"source": "prizepicks", "count": 0, "props": []}

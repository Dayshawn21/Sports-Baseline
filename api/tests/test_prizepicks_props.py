import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import app.db.pool as pool
from app.core.prop_sports import FULL_GAME_SEGMENT, SportPropConfig
from app.ingest import prizepicks_props
from app.services.sport_props import LineLinkage, ProviderLine

TOY = SportPropConfig(
    code="toy", league_prefix="TOY", segment_suffixes={"1H": "first_half"},
    board_segments=frozenset({FULL_GAME_SEGMENT}), market_aliases={"points": "points"}, period_label="round",
)
START = datetime(2026, 10, 21, 23, 0, tzinfo=UTC)


class _ToySource:
    config = TOY
    model_version = "toy-v1"
    over_probability_version = "toy-pover-v1"

    def __init__(self) -> None:
        self.seen: list[ProviderLine] = []

    async def load_resolver(self, db):
        def resolve(line: ProviderLine) -> LineLinkage:
            self.seen.append(line)
            if line.player_name == "Known":
                return LineLinkage(5, 50, "unique_name", True)
            return LineLinkage(None, 50, "not_found", False)
        return resolve


class _Session:
    def __init__(self) -> None:
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True


def _item(name: str, stat: str, prop_id: str) -> dict:
    return {"player_name": name, "player_team": "AAA", "player_position": "G", "start_time": START,
            "stat_type": stat, "line": 21.5, "odds_type": "standard", "raw_json": {"id": prop_id}}


def test_run_stores_only_the_sports_board_lines_under_its_own_code(monkeypatch) -> None:
    requested: list[int] = []
    inserted: list[dict] = []
    session = _Session()

    async def leagues(_client):
        return [{"id": 1, "attributes": {"name": "TOY"}}, {"id": 2, "attributes": {"name": "TOY1H"}},
                {"id": 3, "attributes": {"name": "NFL"}}]

    async def projections(_client, league_id):
        requested.append(league_id)
        return {}

    def parse(_raw, _league_id):
        return [_item("Known", "Points", "p1"), _item("Stranger", "Points", "p2"), _item("Known", "Blocks", "p3")]

    async def insert(db, sport, **fields):
        inserted.append({"sport": sport, **fields})

    monkeypatch.setattr(prizepicks_props, "_fetch_leagues", leagues)
    monkeypatch.setattr(prizepicks_props, "_fetch_projections", projections)
    monkeypatch.setattr(prizepicks_props, "_parse_projections", parse)
    monkeypatch.setattr(prizepicks_props.sport_props, "insert_prop_line", insert)
    monkeypatch.setattr(pool, "SessionLocal", lambda: session)
    source = _ToySource()

    assert asyncio.run(prizepicks_props.run(source)) == 2

    assert requested == [1]
    assert session.committed
    assert [(row["sport"], row["provider_prop_id"], row["market"], row["segment"], row["player_id"], row["game_id"])
            for row in inserted] == [
        ("toy", "p1", "points", "full_game", 5, 50), ("toy", "p2", "points", "full_game", None, 50),
    ]
    assert inserted[0]["line"] == Decimal("21.5") and inserted[0]["raw"]["league_name"] == "TOY"
    assert source.seen[0] == ProviderLine("Known", "AAA", "G", START)


def test_an_empty_board_names_the_sport_in_the_error(monkeypatch) -> None:
    async def leagues(_client):
        return [{"id": 3, "attributes": {"name": "NFL"}}]

    monkeypatch.setattr(prizepicks_props, "_fetch_leagues", leagues)

    try:
        asyncio.run(prizepicks_props.run(_ToySource(), dry_run=True))
    except prizepicks_props.PrizePicksRateLimited as exc:
        assert "no TOY leagues" in str(exc)
    else:
        raise AssertionError("an empty board must raise")

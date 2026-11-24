import asyncio
import json
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import httpx
import pytest

import app.db.pool as pool
from app.ingest import prizepicks_nhl, prizepicks_props
from app.repositories import nhl, sport_props

START = datetime(2026, 10, 24, 1, tzinfo=timezone.utc)


def _payload() -> dict:
    data = []
    for prop_id, player_id, stat, line, odds in [
        ("p1", "1", "Shots On Goal", 2.5, "standard"),
        ("p2", "2", "Goalie Saves", 24.5, "demon"),
        ("p3", "3", "Time On Ice", 20.75, "goblin"),
        ("p4", "1", "Goals (Combo)", 0.5, "demon"),
    ]:
        data.append({
            "type": "projection", "id": prop_id,
            "attributes": {"stat_type": stat, "line_score": line, "odds_type": odds,
                           "start_time": START.isoformat(), "allowed_wager_types": "under_or_over"},
            "relationships": {"new_player": {"data": {"id": player_id}}},
        })
    included = [
        {"type": "new_player", "id": player_id,
         "attributes": {"name": name, "position": position, "team": "TB"}}
        for player_id, name, position in [
            ("1", "Brandon Hagel", "F"), ("2", "Andrei Vasilevskiy", "G"), ("3", "Unknown Rookie", "F"),
        ]
    ]
    return {"data": data, "included": included}


@pytest.fixture
def pipeline(monkeypatch):
    db = AsyncMock()
    db.__aenter__.return_value = db
    session = lambda: db
    monkeypatch.setattr(pool, "SessionLocal", session)
    candidates = AsyncMock(return_value=[(11, "Brandon Hagel", "TBL", "L"), (12, "Andrei Vasilevskiy", "TBL", "G")])
    games = AsyncMock(return_value={("TBL", date(2026, 10, 23)): 100})
    aliases = AsyncMock(return_value={})
    leagues = AsyncMock(return_value=[
        {"id": "8", "attributes": {"name": "NHL"}},
        {"id": "227", "attributes": {"name": "NHL1P"}},
        {"id": "7", "attributes": {"name": "NBA"}},
    ])
    projections = AsyncMock(return_value=_payload())
    monkeypatch.setattr(nhl, "get_player_candidates", candidates)
    monkeypatch.setattr(sport_props, "get_game_index", games)
    monkeypatch.setattr(sport_props, "get_player_aliases", aliases)
    monkeypatch.setattr(prizepicks_props, "_fetch_leagues", leagues)
    monkeypatch.setattr(prizepicks_props, "_fetch_projections", projections)
    return db, candidates, games, aliases, leagues, projections


def test_nhl_pipeline_parses_resolves_and_inserts_supported_lines(pipeline, caplog) -> None:
    db, candidates, games, aliases, _, projections = pipeline
    assert asyncio.run(prizepicks_nhl.run()) == 3
    candidates.assert_awaited_once_with(db)
    games.assert_awaited_once_with(db, "nhl")
    aliases.assert_awaited_once_with(db, "nhl")
    assert projections.await_count == 1 and projections.await_args.args[1] == 8
    writes = [call.args for call in db.execute.await_args_list]
    assert len(writes) == 3
    rows = [params for _, params in writes]
    assert [(row["provider_id"], row["market"], row["player_id"], row["game_id"]) for row in rows] == [
        ("p1", "shots_on_goal", 11, 100), ("p2", "goalie_saves", 12, 100), ("p3", "time_on_ice", None, 100),
    ]
    assert [row["line"] for row in rows] == [Decimal("2.5"), Decimal("24.5"), Decimal("20.75")]
    assert [row["odds_type"] for row in rows] == ["standard", "demon", "goblin"]
    for statement, row in writes:
        assert "INSERT INTO sport_prop_lines" in str(statement)
        assert (row["sport"], row["provider"], row["segment"]) == ("nhl", "prizepicks", "full_game")
        assert row["start_time"] == START
        assert json.loads(row["raw"])["source"] == _payload()["data"][int(row["provider_id"][1:]) - 1]
        assert json.loads(row["raw"])["league_name"] == "NHL"
    assert "Goals (Combo) (1)" in caplog.text
    db.commit.assert_awaited_once()


def test_dry_run_fetches_supported_lines_without_opening_a_session(pipeline, monkeypatch) -> None:
    db, candidates, *_ = pipeline
    def no_session():
        raise AssertionError("dry-run must not open a database session")
    monkeypatch.setattr(pool, "SessionLocal", no_session)
    assert asyncio.run(prizepicks_nhl.run(dry_run=True)) == 3
    candidates.assert_not_awaited()
    db.execute.assert_not_awaited()


def test_successful_empty_board_inserts_no_rows(pipeline) -> None:
    db, _, _, _, _, projections = pipeline
    projections.return_value = {"data": [], "included": []}
    assert asyncio.run(prizepicks_nhl.run()) == 0
    db.execute.assert_not_awaited()


def test_relink_uses_stored_rows_and_updates_only_linkage_fields(pipeline, monkeypatch) -> None:
    db, _, _, _, leagues, projections = pipeline
    stored = AsyncMock(return_value=[{
        "id": 55, "player_name": "Brandon Hagel", "player_team": "TB", "player_position": "F",
        "start_time": START, "player_id": None, "game_id": None,
        "odds_type": None, "provider_odds_type": "goblin",
    }])
    monkeypatch.setattr(sport_props, "get_lines_for_relink", stored)
    assert asyncio.run(prizepicks_nhl.relink()) == 1
    stored.assert_awaited_once_with(db, "nhl")
    leagues.assert_not_awaited()
    projections.assert_not_awaited()
    statement, params = db.execute.await_args.args
    assert str(statement).split("SET", 1)[1].split("WHERE", 1)[0].strip() == (
        "player_id = :player_id, game_id = :game_id, odds_type = :odds_type"
    )
    assert params == {"sport": "nhl", "id": 55, "player_id": 11, "game_id": 100, "odds_type": "goblin"}
    stored.return_value[0].update(player_id=11, game_id=100, odds_type="goblin")
    db.execute.reset_mock()
    assert asyncio.run(prizepicks_nhl.relink()) == 0
    db.execute.assert_not_awaited()


@pytest.mark.parametrize("empty_catalog", [False, True])
def test_exhausted_throttling_or_missing_catalog_exits_75(pipeline, monkeypatch, capsys, empty_catalog) -> None:
    db, _, _, _, leagues, projections = pipeline
    if empty_catalog:
        leagues.return_value = []
    else:
        response = httpx.Response(429, request=httpx.Request("GET", "https://example.test"))
        projections.side_effect = httpx.HTTPStatusError("429", request=response.request, response=response)
    monkeypatch.setattr(sys, "argv", ["prizepicks_nhl", "--dry-run"])
    assert prizepicks_nhl.main() == 75
    assert "No lines were stored" in capsys.readouterr().out
    db.execute.assert_not_awaited()


def test_cli_relink_never_fetches_the_provider(pipeline, monkeypatch, capsys) -> None:
    db, _, _, _, leagues, projections = pipeline
    monkeypatch.setattr(sport_props, "get_lines_for_relink", AsyncMock(return_value=[]))
    monkeypatch.setattr(sys, "argv", ["prizepicks_nhl", "--relink"])
    assert prizepicks_nhl.main() == 0
    assert capsys.readouterr().out.strip() == "0"
    leagues.assert_not_awaited()
    projections.assert_not_awaited()
    db.execute.assert_not_awaited()

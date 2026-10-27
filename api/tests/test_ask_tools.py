"""Executor paths that must answer with a note, not an exception. Services are
stubbed; the real calls are exercised through `app.services.ask.preview`."""
import asyncio
import datetime as dt
import json
from types import SimpleNamespace

from app.schemas.ask import FindInput, GetSlateInput, GetTopPropsInput
from app.services.ask import tools
from app.services.tennis.best_picks_response import PredictionsUnavailable

NOW = dt.datetime(2026, 10, 27, 22, 0, tzinfo=dt.UTC)


def _ctx(registry: object = "registry") -> tools.ToolContext:
    return tools.ToolContext(db=None, registry=registry, now=NOW, production=True)


def _run(executor, inp, ctx=None):
    return asyncio.run(executor(inp, ctx or _ctx()))


def test_nba_day_without_games_says_so(monkeypatch):
    async def empty_slate(_db, _requested, _today):
        return SimpleNamespace(date=dt.date(2026, 10, 27), games=[])

    monkeypatch.setattr(tools, "build_nba_slate", empty_slate)
    result = _run(tools.get_slate, GetSlateInput(sport="nba"))
    assert result.data == [] and "No NBA games on 2026-10-27" in result.note
    assert result.url == "/nba?date=2026-10-27"


def test_nfl_without_a_loaded_season_says_so(monkeypatch):
    async def no_week(_db, _now):
        return None

    monkeypatch.setattr(tools.nfl_repo, "get_current_week", no_week)
    result = _run(tools.get_slate, GetSlateInput(sport="nfl"))
    assert result.note == "No NFL regular-season games are loaded."


def test_nfl_missing_stored_slate_is_a_note_in_production(monkeypatch):
    async def week(_db, _now):
        return 2026, 8

    async def no_snapshot(_db, _season, _week, production):
        assert production is True
        return None

    monkeypatch.setattr(tools.nfl_repo, "get_current_week", week)
    monkeypatch.setattr(tools, "cached_slate_json", no_snapshot)
    result = _run(tools.get_slate, GetSlateInput(sport="nfl", week=9))
    assert "2026 week 9 is not available yet" in result.note
    assert result.url == "/nfl?season=2026&week=9"


def test_nfl_stored_slate_is_parsed(monkeypatch):
    async def week(_db, _now):
        return 2026, 8

    async def snapshot(_db, _season, _week, _production):
        game = {"gameId": 3, "awayTeam": "KC", "homeTeam": "BUF", "startUtc": None, "status": "scheduled", "lines": []}
        return json.dumps({"games": [game]}).encode()

    monkeypatch.setattr(tools.nfl_repo, "get_current_week", week)
    monkeypatch.setattr(tools, "cached_slate_json", snapshot)
    result = _run(tools.get_slate, GetSlateInput(sport="nfl"))
    assert result.note is None and result.data[0]["url"] == "/nfl/game/3"


def test_tennis_unavailable_predictions_are_a_note(monkeypatch):
    async def failing(*_args):
        raise PredictionsUnavailable("down")

    monkeypatch.setattr(tools, "slate_predictions", failing)
    result = _run(tools.get_slate, GetSlateInput(sport="tennis"))
    assert result.note == "Tennis predictions are unavailable right now."
    assert _run(tools.get_slate, GetSlateInput(sport="tennis"), _ctx(registry=None)).data == []


def test_tennis_picks_unavailable_is_a_note(monkeypatch):
    async def failed(*_args):
        return None

    monkeypatch.setattr(tools, "best_picks_for", failed)
    result = _run(tools.get_top_props, GetTopPropsInput(sport="tennis"))
    assert result.note == "Tennis picks are unavailable right now."


def test_find_without_a_match_suggests_another_period(monkeypatch):
    async def predictions(*_args):
        return []

    monkeypatch.setattr(tools, "slate_predictions", predictions)
    result = _run(tools.find, FindInput(sport="tennis", query="Sinner"))
    assert result.data == [] and "Nothing named 'Sinner'" in result.note


def test_find_with_several_matches_asks_to_choose(monkeypatch):
    async def predictions(*_args):
        return [SimpleNamespace(match_id=1, p1_name="Jannik Sinner", p2_name="Jakub Mensik", p1_id=5, p2_id=6,
                                tournament="Paris", start_utc=None)]

    monkeypatch.setattr(tools, "slate_predictions", predictions)
    monkeypatch.setattr(tools, "asdict", lambda p: vars(p))
    result = _run(tools.find, FindInput(sport="tennis", query="ja"))
    players = {row["name"]: row["url"] for row in result.data if row["kind"] == "player"}
    assert players == {"Jakub Mensik": "/tennis/player/6", "Jannik Sinner": "/tennis/player/5"}
    assert "game" in {row["kind"] for row in result.data}
    assert result.note == "Several matches; pick the one the user means, or ask them."


def _none(*_args):
    async def none(*_inner):
        return None
    return none


def test_unknown_ids_are_not_found_notes(monkeypatch):
    from app.schemas.ask import GetGameDetailInput, GetPlayerInput

    monkeypatch.setattr(tools, "build_nba_game", _none())
    monkeypatch.setattr(tools, "build_nfl_player", _none())
    monkeypatch.setattr(tools, "build_match_detail", _none())
    nba = _run(tools.get_game_detail, GetGameDetailInput(sport="nba", game_id=999))
    nfl = _run(tools.get_player, GetPlayerInput(sport="nfl", player_id=999))
    tennis = _run(tools.get_game_detail, GetGameDetailInput(sport="tennis", game_id=999))
    assert nba.note == "not_found: no nba game with that id" and nba.url is None
    assert nfl.note == "not_found: no nfl player with that id"
    assert tennis.note == "not_found: no tennis match with that id"


def test_tennis_track_record_ignores_a_season_and_says_so(monkeypatch):
    from app.schemas.ask import GetModelTrackRecordInput

    async def grading(_db):
        return SimpleNamespace()

    monkeypatch.setattr(tools.tennis_track_record, "get_prediction_grading", grading)
    monkeypatch.setattr(tools.tennis_track_record, "get_tier_grading", grading)
    monkeypatch.setattr(tools, "_plain", lambda _obj: {})
    result = _run(tools.get_model_track_record, GetModelTrackRecordInput(sport="tennis", season=2025))
    assert result.note == "Tennis grading covers every season; the season input is ignored."
    assert result.url == "/tennis/model"


def test_failed_track_record_is_a_note(monkeypatch):
    from app.schemas.ask import GetModelTrackRecordInput

    async def season(_db, _now):
        return 2026

    monkeypatch.setattr(tools.nba_track_record, "nba_season", season)
    monkeypatch.setattr(tools.nba_track_record, "get_ranking_record", _none())
    result = _run(tools.get_model_track_record, GetModelTrackRecordInput(sport="nba"))
    assert result.note == tools.UNAVAILABLE_RECORD and result.data is None

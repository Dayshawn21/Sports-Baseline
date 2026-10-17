import asyncio
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import sport_props
from app.core.prop_predictions import PropPredictionRow


class _Result:
    def __init__(self, rows: list[tuple]) -> None:
        self._rows = rows

    def fetchall(self) -> list[tuple]:
        return self._rows


class _Session:
    def __init__(self, rows: list[tuple] | None = None) -> None:
        self.statement = ""
        self.params: dict[str, object] = {}
        self._rows = rows or []

    async def execute(self, statement, params: dict[str, object] | None = None) -> _Result:
        self.statement = str(statement)
        self.params = params or {}
        return _Result(self._rows)


def _run(coroutine):
    return asyncio.run(coroutine)


def test_prop_line_insert_writes_the_given_sport() -> None:
    session = _Session()

    _run(sport_props.insert_prop_line(
        cast(AsyncSession, session), "nba", provider="prizepicks", provider_prop_id="99", market="points",
        segment="full_game", line=Decimal("24.5"), start_time=datetime(2026, 10, 21, 23, 0, tzinfo=UTC),
        player_id=7, game_id=8, odds_type="standard", raw={"player_name": "A. Player"},
    ))

    assert "INSERT INTO sport_prop_lines (sport, provider, provider_prop_id," in session.statement
    assert "VALUES (:sport, :provider, :provider_id," in session.statement
    assert session.params["sport"] == "nba" and session.params["provider"] == "prizepicks"
    assert json.loads(str(session.params["raw"])) == {"player_name": "A. Player"}


def test_game_index_reads_one_sports_teams_and_games_on_both_sides() -> None:
    session = _Session([("KC", "BUF", date(2026, 10, 4), 12)])

    index = _run(sport_props.get_game_index(cast(AsyncSession, session), "nfl"))

    assert session.params == {"sport": "nfl"}
    assert "home.sport = :sport" in session.statement and "away.sport = :sport" in session.statement
    assert "WHERE g.sport = :sport" in session.statement
    assert index == {("KC", date(2026, 10, 4)): 12, ("BUF", date(2026, 10, 4)): 12}


def test_relink_reads_and_updates_only_the_given_sports_lines() -> None:
    session = _Session()

    assert _run(sport_props.get_lines_for_relink(cast(AsyncSession, session), "nfl")) == []
    assert "WHERE sport = :sport" in session.statement and session.params == {"sport": "nfl"}

    _run(sport_props.set_line_linkage(cast(AsyncSession, session), "nfl", 5, 6, 7, "standard"))

    assert "UPDATE sport_prop_lines" in session.statement
    assert "WHERE sport = :sport AND id = :id" in session.statement
    assert session.params == {"sport": "nfl", "id": 5, "player_id": 6, "game_id": 7, "odds_type": "standard"}


def test_aliases_are_scoped_to_the_sport() -> None:
    session = _Session([("j smith", 4)])

    assert _run(sport_props.get_player_aliases(cast(AsyncSession, session), "nfl")) == {"j smith": 4}
    assert "FROM sport_player_aliases WHERE sport = :sport" in session.statement
    assert session.params == {"sport": "nfl"}


def _prediction_row() -> PropPredictionRow:
    return PropPredictionRow(
        prop_line_id=41, model_version="opponent-dvp-tg-blend-usage-snap-v4", over_probability_version=None,
        projection=None, p_over=None, p_under=None, edge=None, quality_flags=["small_sample"],
        feature_snapshot={"games_in_sample": 2, "odds_type": "goblin"},
        generated_at=datetime(2026, 9, 27, 14, 0, tzinfo=UTC),
    )


def test_frozen_predictions_insert_in_one_statement_and_never_overwrite() -> None:
    session = _Session()

    inserted = _run(sport_props.insert_prop_predictions(cast(AsyncSession, session), "nfl", [_prediction_row()]))

    assert inserted == 0
    assert "INSERT INTO sport_prop_predictions (sport, prop_line_id, model_version, over_probability_version, " \
        "projection, p_over, p_under, edge, quality_flags, feature_snapshot, generated_at)" in session.statement
    assert "SELECT CAST(:sport AS text), prop_line_id," in session.statement
    assert session.params["sport"] == "nfl"
    assert "jsonb_to_recordset(CAST(:rows AS jsonb))" in session.statement
    # The line id carries the sport, so the key stays scoped without naming it.
    assert "ON CONFLICT (prop_line_id, model_version, over_probability_version) DO NOTHING" in session.statement
    rows = json.loads(str(session.params["rows"]))
    assert rows == [{
        "prop_line_id": 41, "model_version": "opponent-dvp-tg-blend-usage-snap-v4", "over_probability_version": None,
        "projection": None, "p_over": None, "p_under": None, "edge": None, "quality_flags": ["small_sample"],
        "feature_snapshot": {"games_in_sample": 2, "odds_type": "goblin"},
        "generated_at": "2026-09-27 14:00:00+00:00",
    }]


def test_no_frozen_predictions_issue_no_sql() -> None:
    session = _Session()

    assert _run(sport_props.insert_prop_predictions(cast(AsyncSession, session), "nfl", [])) == 0
    assert session.statement == ""

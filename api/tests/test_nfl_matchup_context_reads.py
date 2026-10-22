"""Execute the display SQL against isolated fixtures; never connect to Postgres."""
import asyncio
from datetime import UTC, datetime
from typing import cast
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import TextClause

from app.db.pool import get_db
from app.repositories import nfl as repo
from app.routers import nfl as nfl_router
from app.services.nfl import game_notes
from app.services.nfl.matchup_context import build_game_context, build_week_matchup_context


class FixtureResult:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows

    def mappings(self) -> list[dict[str, object]]:
        return self.rows


class FixtureDatabase:
    def __init__(self) -> None:
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
        self.connection = self.engine.connect()
        self.statements: list[str] = []
        definitions = {
            "sport_teams": "id INTEGER, sport TEXT, team_code TEXT",
            "sport_games": "id INTEGER, sport TEXT, season INTEGER, week INTEGER, start_utc TEXT, "
                           "home_team_id INTEGER, away_team_id INTEGER, game_type TEXT, status TEXT",
            "sport_players": "id INTEGER, sport TEXT, name TEXT, position TEXT, team_id INTEGER",
            "nfl_player_weekly_rosters": "player_id INTEGER, season INTEGER, week INTEGER, team_id INTEGER, status TEXT",
            "nfl_player_weekly_stats": "player_id INTEGER, game_id INTEGER, season INTEGER, week INTEGER, "
                                       "team_id INTEGER, targets INTEGER, rushing_attempts INTEGER, "
                                       "rushing_yards INTEGER, receptions INTEGER, receiving_yards INTEGER",
            "nfl_player_snap_counts": "player_id INTEGER, game_id INTEGER, season INTEGER, week INTEGER, "
                                     "team_id INTEGER, offense_snaps INTEGER, offense_pct REAL",
        }
        for table, columns in definitions.items():
            self.connection.execute(text(f"CREATE TABLE {table} ({columns})"))
        for team_id, code in [(1, "A"), (2, "B"), (3, "C"), (4, "D")]:
            self.insert("sport_teams", id=team_id, sport="nfl", team_code=code)
        self.insert("sport_teams", id=99, sport="nba", team_code="A")
        self.game(100, week=4, start=datetime(2026, 10, 4, 17, tzinfo=UTC))

    @property
    def session(self) -> AsyncSession:
        return cast(AsyncSession, self)

    def insert(self, table: str, **fields: object) -> None:
        self.connection.execute(text(
            f"INSERT INTO {table} ({', '.join(fields)}) VALUES ({', '.join(':' + key for key in fields)})",
        ), fields)

    def game(
        self, game_id: int, week: int = 1, *, season: int = 2026, sport: str = "nfl",
        game_type: str = "REG", status: str = "completed", away: int = 1, home: int = 2,
        start: datetime | None = datetime(2026, 9, 1, 17, tzinfo=UTC),
    ) -> None:
        self.insert("sport_games", id=game_id, season=season, week=week, start_utc=start,
                    sport=sport, game_type=game_type, status=status, away_team_id=away, home_team_id=home)

    def player(self, player_id: int, position: str = "WR", team: int = 1, *, name: str = "Player", sport: str = "nfl") -> None:
        self.insert("sport_players", id=player_id, sport=sport, name=name, position=position, team_id=team)

    def roster(self, player_id: int, team: int = 1, week: int = 4, *, status: str = "ACT") -> None:
        self.insert("nfl_player_weekly_rosters", player_id=player_id, season=2026, week=week, team_id=team, status=status)

    def stats(
        self, player_id: int, game_id: int, *, team: int = 1, targets: int | None = 0,
        carries: int = 0, rush_yards: int = 0, receptions: int = 0, rec_yards: int = 0,
    ) -> None:
        season, week = self.connection.execute(text("SELECT season, week FROM sport_games WHERE id = :id"), {"id": game_id}).one()
        self.insert("nfl_player_weekly_stats", player_id=player_id, game_id=game_id, season=season, week=week,
                    team_id=team, targets=targets, rushing_attempts=carries, rushing_yards=rush_yards,
                    receptions=receptions, receiving_yards=rec_yards)

    def snaps(self, player_id: int, game_id: int, *, team: int = 1, snaps: int = 30, pct: float = 0.5) -> None:
        season, week = self.connection.execute(text("SELECT season, week FROM sport_games WHERE id = :id"), {"id": game_id}).one()
        self.insert("nfl_player_snap_counts", player_id=player_id, game_id=game_id, season=season, week=week,
                    team_id=team, offense_snaps=snaps, offense_pct=pct)

    async def execute(self, statement: TextClause, params: dict[str, object]) -> FixtureResult:
        sql = str(statement)
        assert not any(verb in sql.upper().split() for verb in ["INSERT", "DELETE", "UPDATE", "DROP", "CREATE"])
        self.statements.append(sql)
        rows = [dict(row) for row in self.connection.execute(statement, params).mappings()]
        for row in rows:
            if isinstance(row.get("start_utc"), str):
                row["start_utc"] = datetime.fromisoformat(row["start_utc"])
        return FixtureResult(rows)


@pytest.fixture
def database():
    fixture = FixtureDatabase()
    yield fixture
    fixture.connection.close()
    fixture.engine.dispose()


def context(database: FixtureDatabase, game_id: int = 100):
    return asyncio.run(build_game_context(database.session, game_id))


def test_actual_sql_uses_current_week_roster_without_mutable_or_future_team(database):
    database.player(10, team=3)
    database.roster(10, team=1)
    database.roster(10, team=2, week=5)
    database.player(11)
    database.roster(11, week=3)
    database.player(12)
    database.roster(12, status="CUT")
    database.player(13)
    database.roster(13, team=1)
    database.roster(13, team=2)
    database.player(14)
    database.roster(14, status="RET")
    database.player(15, sport="nba")
    database.roster(15)
    database.player(16, position="K")
    database.roster(16)
    result = context(database)
    assert [(player.player_id, player.team) for player in result.players] == [(10, "A")]
    assert result.players[0].season_usage.targets.reason == "no_history"
    assert len(database.statements) == 4


def test_actual_sql_retains_trade_history_and_snap_only_recent_game(database):
    database.player(10, team=3)
    database.player(11, position="QB")
    database.player(12, position="RB")
    database.player(30, team=3)
    database.roster(10)
    database.game(1, away=3)
    database.stats(10, 1, team=3, targets=2)
    database.stats(30, 1, team=3, targets=8)
    database.game(2, week=2, start=datetime(2026, 9, 8, 17, tzinfo=UTC))
    database.stats(10, 2, targets=6)
    database.stats(11, 2, carries=3)
    database.stats(12, 2, targets=14, carries=9)
    database.game(3, week=3, start=datetime(2026, 9, 15, 17, tzinfo=UTC))
    database.snaps(10, 3, pct=0.25)
    database.game(4, week=3, start=datetime(2026, 9, 22, 17, tzinfo=UTC))
    database.stats(10, 4)
    database.snaps(10, 4, snaps=0, pct=0)
    usage = context(database).players[0].season_usage
    assert usage.teams == ["C", "A"]
    assert (usage.targets.value, usage.targets.observed_games, usage.targets.eligible_games) == (4, 2, 3)
    assert usage.target_share.value == pytest.approx(8 / 30)
    assert usage.target_share.observed_games == 2
    assert usage.avg_game_snap_share.value == 0.25
    assert usage.avg_game_snap_share.observed_games == 1
    assert usage.avg_game_snap_share.window_end.isoformat() == "2026-09-15"
    assert usage.carry_share.value == 0
    assert usage.carry_share.observed_games == 1


def test_actual_sql_aggregates_position_team_games_and_keeps_absent_or_partial_groups_null(database):
    database.game(1)
    for player_id, position in [(10, "RB"), (11, "RB"), (12, "TE"), (13, "WR"), (14, "TE")]:
        database.player(player_id, position=position, team=2)
    database.stats(10, 1, team=2, carries=7, rush_yards=30, receptions=2, rec_yards=12)
    database.stats(11, 1, team=2, carries=5, rush_yards=20, receptions=1, rec_yards=8)
    database.stats(12, 1, team=2)
    database.snaps(12, 1, team=2)
    database.game(2, week=2)
    database.stats(10, 2, team=2, carries=20)
    database.snaps(11, 2, team=2)
    database.snaps(14, 2, team=2)
    database.game(3, week=3)
    allowed = context(database).matchup_context.away.allowed
    assert allowed.rb_carries.value == 12
    assert (allowed.rb_carries.observed_games, allowed.rb_carries.eligible_games) == (1, 3)
    assert allowed.rb_rec_yards.value == 20
    assert allowed.te_receptions.value == 0
    assert allowed.te_receptions.observed_games == 1
    assert allowed.wr_receptions.value is None
    assert allowed.wr_receptions.reason == "missing_data"


def test_actual_sql_sums_team_carries_including_qb_and_drops_uncovered_denominators(database):
    database.game(1)
    database.player(10, position="RB")
    database.player(11, position="QB")
    database.roster(10)
    database.stats(10, 1, targets=2, carries=10)
    database.stats(11, 1, targets=0, carries=5)
    usage = context(database).players[0].season_usage
    assert usage.target_share.value == 1
    assert usage.carry_share.value == pytest.approx(10 / 15)
    database.player(12, position="TE")
    database.snaps(12, 1)
    usage = context(database).players[0].season_usage
    assert usage.targets.value == 2
    assert usage.target_share.reason == usage.carry_share.reason == "missing_data"
    assert usage.target_share.observed_games == 0


def test_known_dnp_stat_rows_do_not_establish_position_coverage(database):
    database.game(1)
    database.player(10, position="TE", team=2)
    database.stats(10, 1, team=2)
    database.snaps(10, 1, team=2, snaps=0, pct=0)
    allowed = context(database).matchup_context.away.allowed
    assert allowed.te_receptions.value is None
    assert allowed.te_receptions.observed_games == 0
    assert allowed.te_receptions.eligible_games == 1


def test_missing_target_metric_does_not_drop_covered_carries_and_zero_is_not_missing(database):
    database.game(1)
    database.player(10, position="RB")
    database.player(11, position="QB")
    database.roster(10)
    database.stats(10, 1, targets=0, carries=0)
    database.stats(11, 1, targets=None, carries=20)
    usage = context(database).players[0].season_usage
    assert usage.targets.value == usage.carries.value == 0
    assert usage.target_share.reason == "missing_data"
    assert usage.carry_share.value == 0
    assert usage.carry_share.observed_games == 1


def test_actual_sql_zero_team_total_is_unavailable_for_share_only(database):
    database.game(1)
    database.player(10)
    database.roster(10)
    database.stats(10, 1)
    usage = context(database).players[0].season_usage
    assert usage.targets.value == 0
    assert usage.target_share.reason == "zero_denominator"
    assert usage.target_share.value is None
    assert usage.target_share.observed_games == 0


@pytest.mark.parametrize("fields", [
    {"week": 4}, {"week": 5}, {"season": 2025}, {"sport": "nba"},
    {"game_type": "PRE"}, {"game_type": "POST"}, {"status": "scheduled"},
    {"start": None}, {"start": datetime(2026, 10, 4, 17, tzinfo=UTC)},
    {"start": datetime(2026, 10, 5, 17, tzinfo=UTC)},
])
def test_actual_sql_excludes_ineligible_games_from_usage_and_league_ranks(database, fields):
    database.player(10, position="RB")
    database.roster(10)
    database.game(1, **fields)
    database.stats(10, 1, targets=100, carries=100)
    result = context(database)
    assert result.players[0].season_usage.targets.eligible_games == 0
    assert result.players[0].season_usage.targets.value is None
    assert result.matchup_context.home.allowed.rb_carries.ranked_teams == 0


def test_actual_sql_ignores_foreign_sport_players_and_teams(database):
    database.game(1)
    database.player(10, position="RB", sport="nba")
    database.stats(10, 1, carries=99)
    database.player(11, position="RB")
    database.stats(11, 1, team=99, carries=99)
    database.roster(11)
    database.game(2, home=99)
    database.stats(11, 2, carries=99)
    result = context(database)
    assert result.matchup_context.home.allowed.rb_carries.value is None
    assert result.matchup_context.home.allowed.rb_carries.eligible_games == 1
    assert result.players[0].season_usage.carries.reason == "no_history"


def test_actual_sql_missing_target_kickoff_is_unavailable(database):
    database.game(101, week=4, start=None)
    database.player(10)
    database.roster(10)
    database.game(1)
    database.stats(10, 1, targets=4)
    result = context(database, 101)
    assert result.players[0].season_usage.targets.reason == "unknown_kickoff"
    assert result.matchup_context.away.allowed.rb_carries.reason == "unknown_kickoff"
    assert len(database.statements) == 2


def test_actual_sql_order_is_team_then_name_then_id_and_query_count_does_not_grow(database):
    for player_id, name, team in [(20, "Zed", 1), (30, "Ada", 2), (11, "Ada", 1), (10, "Ada", 1)]:
        database.player(player_id, name=name, team=team)
        database.roster(player_id, team=team)
    first = context(database)
    assert [player.player_id for player in first.players] == [10, 11, 20, 30]
    assert len(database.statements) == 4
    for player_id in range(1000, 1100):
        database.player(player_id)
        database.roster(player_id)
    database.statements.clear()
    assert len(context(database).players) == 104
    assert len(database.statements) == 4
    assert all("sport_prop" not in statement and "sport_game_odds" not in statement for statement in database.statements)


def test_week_matchups_batch_queries_and_use_each_target_kickoff(database):
    database.game(101, week=4, away=3, home=4, start=datetime(2026, 10, 5, 17, tzinfo=UTC))
    database.game(1, week=3, away=2, home=3, start=datetime(2026, 10, 5, 10, tzinfo=UTC))
    database.player(10, position="RB", team=2)
    database.stats(10, 1, team=2, carries=5)
    matchups = asyncio.run(build_week_matchup_context(database.session, 2026, 4))
    assert len(database.statements) == 2
    assert matchups[100].home.allowed.rb_carries.ranked_teams == 0
    assert matchups[101].away.allowed.rb_carries.value == 5
    assert context(database, 100).matchup_context == matchups[100]
    assert context(database, 101).matchup_context == matchups[101]


def client(database: FixtureDatabase) -> TestClient:
    app = FastAPI()
    app.include_router(nfl_router.router, prefix="/nfl")
    app.dependency_overrides[get_db] = lambda: database.session
    return TestClient(app)


@pytest.mark.parametrize("game_id,fields", [
    (999, None), (101, {"sport": "nba"}), (102, {"game_type": "PRE"}), (103, {"home": 99}),
])
def test_route_returns_404_for_unknown_or_non_nfl_regular_season_target(database, game_id, fields):
    if fields is not None:
        database.game(game_id, **fields)
    response = client(database).get(f"/nfl/games/{game_id}/context")
    assert response.status_code == 404
    assert len(database.statements) == 1


def test_route_opening_week_is_structured_unavailable_not_previous_season(database):
    database.game(101, week=1)
    database.game(1, season=2025)
    database.player(10, position="RB")
    database.roster(10, week=1)
    database.stats(10, 1, targets=10, carries=20)
    response = client(database).get("/nfl/games/101/context")
    assert response.status_code == 200
    body = response.json()
    assert body["cutoffWeek"] == 0
    metric = body["players"][0]["seasonUsage"]["targets"]
    assert metric == {"value": None, "observedGames": 0, "eligibleGames": 0,
                      "windowStart": None, "windowEnd": None, "reason": "no_history"}
    assert body["matchupContext"]["away"]["allowed"]["rbCarries"]["rankedTeams"] == 0


def test_notes_and_game_endpoints_serialize_identical_matchup_and_keep_existing_notes(database, monkeypatch):
    database.game(1)
    database.player(10, position="RB")
    database.stats(10, 1, carries=10)
    game = {"away_team_id": 1, "away_team": "A", "away_rest": 7,
            "home_team_id": 2, "home_team": "B", "home_rest": 8,
            "away_score": None, "home_score": None}
    monkeypatch.setattr(repo, "get_week_game_rest", AsyncMock(return_value={100: game}))
    for name in ["get_week_skill_injuries", "get_week_depth_rows", "get_week_line_movement", "get_week_team_games"]:
        monkeypatch.setattr(repo, name, AsyncMock(return_value=[]))
    for name in ["get_week_team_recent_results", "get_week_game_quotes"]:
        monkeypatch.setattr(repo, name, AsyncMock(return_value={}))
    monkeypatch.setattr(game_notes, "_week_qb_changes", AsyncMock(return_value={}))
    api = client(database)
    detail_response = api.get("/nfl/games/100/context")
    notes_response = api.get("/nfl/game-notes?season=2026&week=4")
    assert detail_response.status_code == notes_response.status_code == 200
    notes = notes_response.json()["games"][0]
    assert detail_response.json()["matchupContext"] == notes["matchupContext"]
    assert notes["matchupContext"]["home"]["allowed"]["rbCarries"]["value"] == 10
    assert notes["awayForm"]["restDays"] == 7
    assert notes["homeForm"]["restDays"] == 8
    assert notes["bestLine"] is None
    assert notes["awayStats"]["games"] == 0
    expected = game_notes.game_notes(100, game, [], [], [], {}, {}).model_dump(
        mode="json", by_alias=True, exclude={"matchup_context"},
    )
    assert {key: value for key, value in notes.items() if key != "matchupContext"} == expected


def test_no_target_week_games_skips_all_aggregation(database):
    assert asyncio.run(build_week_matchup_context(database.session, 2026, 18)) == {}
    assert len(database.statements) == 1

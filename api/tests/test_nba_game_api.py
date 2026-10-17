import asyncio
import datetime as dt
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nba_line_only import LINE_ONLY_COLUMNS
from app.core.nba_slate import Record
from app.repositories import nba as nba_repo
from app.services.nba.game_detail import game_detail
from app.services.nba.line_only_props import line_only_props
from app.services.nba.slate import slate_games

UTC = dt.timezone.utc
FETCHED = dt.datetime(2026, 10, 6, 15, 0, tzinfo=UTC)


def _game(game_id: int = 21320, season: int = 2026) -> dict[str, object]:
    return {
        "game_id": game_id, "season": season, "week": 1, "game_type": "REG", "game_date": dt.date(2026, 10, 20),
        "start_utc": dt.datetime(2026, 10, 20, 19, 0, tzinfo=UTC), "status": "scheduled",
        "away_team": "BOS", "home_team": "DET", "away_team_name": "Boston Celtics", "home_team_name": "Detroit Pistons",
        "away_score": None, "home_score": None,
    }


def _row(market: str, first_side: str, first_odds: int, second_odds: int, probability: float,
         line: float | None = None, game_id: int = 21320, book: str = "draftkings") -> dict[str, object]:
    return {"game_id": game_id, "market": market, "book": book, "line": line, "first_side": first_side,
            "first_odds": first_odds, "second_odds": second_odds, "first_market_prob": probability, "fetched_at": FETCHED}


def test_markets_map_home_and_over_sides_and_the_devigged_probability() -> None:
    rows = [
        _row("moneyline", "home", -125, 105, 0.532),
        _row("spread", "home", -105, -115, 0.489, -2.5, book="fanduel"),
        _row("total", "over", -110, -110, 0.5, 221.5),
    ]
    game = slate_games([_game()], rows, {2026: {}})[0]
    assert (game.moneyline.home_odds, game.moneyline.away_odds, game.moneyline.home_win_probability) == (-125, 105, 0.532)
    assert (game.spread.book, game.spread.home_line, game.spread.home_odds, game.spread.away_odds) == ("fanduel", -2.5, -105, -115)
    assert (game.total.line, game.total.over_odds, game.total.under_odds) == (221.5, -110, -110)


def test_a_row_stored_away_side_first_is_turned_home_first() -> None:
    rows = [_row("moneyline", "away", 105, -125, 0.468), _row("spread", "away", -115, -105, 0.511, 2.5)]
    game = slate_games([_game()], rows, {2026: {}})[0]
    assert (game.moneyline.home_odds, game.moneyline.away_odds) == (-125, 105)
    assert abs(game.moneyline.home_win_probability - 0.532) < 1e-9
    assert (game.spread.home_line, game.spread.home_odds, game.spread.away_odds) == (-2.5, -105, -115)


def test_a_market_without_a_row_is_null_and_rows_stay_with_their_game() -> None:
    games = slate_games([_game(), _game(21319)], [_row("total", "over", -110, -110, 0.5, 230.5, game_id=21319)], {2026: {}})
    assert (games[0].moneyline, games[0].spread, games[0].total) == (None, None, None)
    assert games[1].total.line == 230.5 and games[1].moneyline is None


def test_records_come_from_the_games_season_and_default_to_zero() -> None:
    games = slate_games([_game()], [], {2026: {"DET": Record(3, 1)}})
    assert (games[0].home_record.wins, games[0].home_record.losses) == (3, 1)
    assert (games[0].away_record.wins, games[0].away_record.losses) == (0, 0)


def _move(market: str, open_line: float, current_line: float, game_id: int = 21320) -> dict[str, object]:
    return {"game_id": game_id, "market": market, "book": "draftkings", "open_line": open_line, "open_fetched_at": FETCHED,
            "current_line": current_line, "current_fetched_at": FETCHED + dt.timedelta(hours=7)}


def test_line_movement_and_prop_counts_attach_to_their_game() -> None:
    games = slate_games(
        [_game(), _game(21319)], [], {2026: {}},
        [_move("spread", -2.5, -3.5), _move("total", 221.5, 220.0)], {21320: 61},
    )
    moves = {move.market: (move.book, move.open_line, move.current_line) for move in games[0].line_movement}
    assert moves == {"spread": ("draftkings", -2.5, -3.5), "total": ("draftkings", 221.5, 220.0)}
    assert games[0].prop_line_count == 61


def test_a_game_with_no_movement_or_lines_reads_empty_and_zero() -> None:
    games = slate_games([_game(), _game(21319)], [], {2026: {}}, [_move("spread", -2.5, -3.5)], {21320: 61})
    assert (games[1].line_movement, games[1].prop_line_count) == ([], 0)


def test_game_detail_keeps_the_slate_game_and_reduces_history_to_line_changes() -> None:
    game = slate_games([_game()], [_row("moneyline", "home", -125, 105, 0.532)], {2026: {}}, [_move("spread", -2.5, -3.5)], {21320: 61})[0]
    rows = [
        {"market": "spread", "book": "draftkings", "line": -2.5, "fetched_at": FETCHED},
        {"market": "spread", "book": "draftkings", "line": -2.5, "fetched_at": FETCHED + dt.timedelta(hours=7)},
        {"market": "spread", "book": "draftkings", "line": -3.5, "fetched_at": FETCHED + dt.timedelta(days=1)},
        {"market": "total", "book": "fanduel", "line": 221.5, "fetched_at": FETCHED},
    ]
    detail = game_detail(game, rows)
    assert detail.model_dump(exclude={"line_history"}) == game.model_dump()
    histories = {history.market: (history.book, [step.line for step in history.steps]) for history in detail.line_history}
    assert histories == {"spread": ("draftkings", [-2.5, -3.5]), "total": ("fanduel", [221.5])}


def test_game_detail_without_odds_has_no_history() -> None:
    assert game_detail(slate_games([_game()], [], {2026: {}})[0], []).line_history == []


def test_response_serializes_camel_case() -> None:
    payload = slate_games([_game()], [_row("moneyline", "home", -125, 105, 0.532)], {2026: {}})[0].model_dump(by_alias=True)
    assert {"gameId", "awayTeamName", "homeRecord", "propLineCount", "lineMovement"} <= payload.keys()
    assert payload["moneyline"]["homeWinProbability"] == 0.532


def _line(player_id: int, name: str, market: str, line: float, team: str | None = "NYK", odds_type: str = "standard") -> dict[str, object]:
    return {"player_id": player_id, "player_name": name, "position": "G", "team": team, "market": market,
            "odds_type": odds_type, "line": line, "fetched_at": FETCHED}


def _box(player_id: int, day: int, **stats: int | None) -> dict[str, object]:
    base: dict[str, object] = {column: 0 for column in LINE_ONLY_COLUMNS}
    return {**base, **stats, "player_id": player_id, "game_date": dt.date(2026, 4, day), "opponent": "BOS", "did_not_play": False}


def test_line_only_lines_order_by_market_then_player_then_line_and_map_team_codes() -> None:
    lines = [
        _line(2, "Zed", "points", 20.5), _line(1, "Amy", "rebounds", 8.5),
        _line(1, "Amy", "points", 25.5, odds_type="demon"), _line(1, "Amy", "points", 18.5, odds_type="goblin"),
    ]
    response = line_only_props(21320, lines, [])
    assert [(line.market, line.player_name, line.line) for line in response.lines] == [
        ("points", "Amy", 18.5), ("points", "Amy", 25.5), ("points", "Zed", 20.5), ("rebounds", "Amy", 8.5)]
    assert {line.team for line in response.lines} == {"NY"}
    assert response.lines[0].recent == []


def test_recent_values_follow_the_market_rule_with_null_for_a_missing_stat() -> None:
    rows = [_box(1, 12, points=30, rebounds=12), _box(1, 10, points=None, rebounds=9), _box(1, 8, points=8, rebounds=4)]
    response = line_only_props(21320, [_line(1, "Amy", "points_rebounds", 35.5), _line(1, "Amy", "double_double", 0.5)], rows)
    by_market = {line.market: [(str(game.game_date), game.value) for game in line.recent] for line in response.lines}
    assert by_market["points_rebounds"] == [("2026-04-12", 42.0), ("2026-04-10", None), ("2026-04-08", 12.0)]
    assert by_market["double_double"] == [("2026-04-12", 1.0), ("2026-04-10", None), ("2026-04-08", 0.0)]


def test_recent_box_scores_sql_skips_dnp_and_preseason() -> None:
    class Rows:
        def mappings(self) -> list[dict[str, object]]:
            return []

    class Session:
        statement = ""

        async def execute(self, statement: object, params: dict[str, object]) -> Rows:
            Session.statement = str(statement)
            return Rows()

    asyncio.run(nba_repo.get_recent_box_scores(cast(AsyncSession, Session()), [1], dt.date(2026, 10, 20)))
    assert "NOT s.did_not_play" in Session.statement
    assert "g.game_type IN ('REG', 'PIN', 'PST')" in Session.statement
    assert "g.game_date < :before" in Session.statement and "recency <= :limit" in Session.statement

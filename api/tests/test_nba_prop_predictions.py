from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta

from app.core import nba_over_probability_fit as fit
from app.core.nba_line_only import LINE_ONLY_COLUMNS
from app.core.nba_projection import project_line
from app.core.nba_projection_backtest import NBA_PROJECTION_MODEL_VERSION, NbaHistoryRow
from app.core.nba_prop_predictions import NbaFreezeLine, freezable_games, prediction_row, settle_frozen
from app.core.prop_predictions import freeze_rows
from app.nba.markets import NbaPropMarket
from app.services.nba.props import props_response

NOW = datetime(2026, 10, 20, 16, 30, tzinfo=UTC)
FETCHED = datetime(2026, 10, 20, 16, 29, tzinfo=UTC)


def _history(games: int) -> list[NbaHistoryRow]:
    stats: dict[str, int | bool | None] = {column: 1 for column in LINE_ONLY_COLUMNS}
    stats.update({"points": 20, "rebounds": 6, "assists": 5, "did_not_play": False})
    return [
        NbaHistoryRow(
            player_id=7, game_id=100 + day, season=2025, game_date=date(2026, 1, 1) + timedelta(days=day),
            game_type="REG", did_not_play=False, minutes=32.0, stats=stats,
        )
        for day in range(games)
    ]


def _line(market: NbaPropMarket, line: float) -> NbaFreezeLine:
    return NbaFreezeLine(
        line_id=55, game_id=9, game_date=date(2026, 10, 20), start_utc=NOW + timedelta(hours=7), player_id=7,
        market=market.value, odds_type="standard", line=line, fetched_at=FETCHED,
    )


def _frozen(market: NbaPropMarket, line: float, games: int = 20):
    projection = project_line(_history(games), market, line)
    return projection, prediction_row(_line(market, line), projection, NOW)


def test_an_assists_line_freezes_its_over_probability() -> None:
    projection, row = _frozen(NbaPropMarket.ASSISTS, 4.5)

    assert NbaPropMarket.ASSISTS.value in fit.SHOWN_MARKETS
    assert row.over_probability_version == "nba-pover-v1"
    assert row.p_over is not None and row.p_under is not None
    assert (row.p_over, row.p_under) == (projection.p_over, projection.p_under)


def test_a_points_line_freezes_without_over_probability() -> None:
    _, row = _frozen(NbaPropMarket.POINTS, 19.5)

    assert row.projection == 20.0
    assert row.over_probability_version is None
    assert row.p_over is None and row.p_under is None
    assert row.quality_flags == ["no_over_probability"]


def test_an_ineligible_line_is_frozen_with_its_flag() -> None:
    _, row = _frozen(NbaPropMarket.POINTS, 19.5, games=9)

    assert row.projection is None
    assert row.quality_flags == ["few_prior_games"]
    assert row.feature_snapshot["gap"] is None


def test_the_row_is_what_project_line_served() -> None:
    projection, row = _frozen(NbaPropMarket.ASSISTS, 4.5)
    served = asdict(projection)

    assert row.prop_line_id == 55
    assert row.model_version == served["model_version"] == NBA_PROJECTION_MODEL_VERSION
    assert row.projection == served["projection"]
    assert row.edge is None
    assert row.quality_flags == list(served["flags"])
    assert row.generated_at == NOW
    assert row.feature_snapshot == {
        "games_in_sample": served["games_in_sample"], "prior_minutes": served["prior_minutes"],
        "gap": served["gap"], "line": 4.5, "odds_type": "standard", "market": "assists",
        "segment": "full_game", "line_fetched_at": FETCHED.isoformat(),
    }


def _box(**stats: int | bool | None) -> dict[str, int | bool | None]:
    row: dict[str, int | bool | None] = {column: 0 for column in LINE_ONLY_COLUMNS}
    return row | {"did_not_play": False} | stats


def test_a_game_with_no_box_scores_is_not_loaded() -> None:
    assert settle_frozen("points", 19.5, None, game_has_box_scores=False) == "stats_not_loaded"


def test_a_player_missing_from_a_loaded_game_is_void() -> None:
    assert settle_frozen("points", 19.5, None, game_has_box_scores=True) == "void_dnp"


def test_a_dnp_row_is_void() -> None:
    assert settle_frozen("points", 19.5, _box(did_not_play=True, points=None), game_has_box_scores=True) == "void_dnp"


def test_a_played_row_missing_the_stat_is_not_a_call() -> None:
    assert settle_frozen("assists", 4.5, _box(assists=None), game_has_box_scores=True) == "missing_stat"


def test_over_and_under_against_the_line() -> None:
    assert settle_frozen("points", 19.5, _box(points=22), game_has_box_scores=True) == "over"
    assert settle_frozen("points", 19.5, _box(points=17), game_has_box_scores=True) == "under"


def test_a_combo_market_settles_on_the_sum() -> None:
    row = _box(points=20, rebounds=8, assists=5)
    assert settle_frozen("points_rebounds_assists", 32.5, row, game_has_box_scores=True) == "over"
    assert settle_frozen("points_rebounds_assists", 33.5, row, game_has_box_scores=True) == "under"


def test_a_whole_number_line_can_push() -> None:
    assert settle_frozen("rebounds", 8.0, _box(rebounds=8), game_has_box_scores=True) == "push"


def _week_line(
    line_id: int, game_id: int, day: int, start: datetime | None, market: str = "points", line: float = 19.5,
) -> NbaFreezeLine:
    return NbaFreezeLine(
        line_id=line_id, game_id=game_id, game_date=date(2026, 10, day), start_utc=start, player_id=7,
        market=market, odds_type="standard", line=line, fetched_at=FETCHED,
    )


def test_a_started_game_is_skipped_and_an_upcoming_one_frozen() -> None:
    lines = [_week_line(1, 9, 20, NOW - timedelta(minutes=5)), _week_line(2, 10, 22, NOW + timedelta(days=2))]
    prior = {date(2026, 10, 20): {7: _history(20)}, date(2026, 10, 22): {7: _history(20)}}

    rows, counts = freeze_rows(freezable_games(lines, prior, NOW), NOW)

    assert [row.prop_line_id for row in rows] == [2]
    assert counts == {"kicked_off": 1, "frozen": 1}


def test_each_game_reads_the_prior_games_of_its_own_date() -> None:
    lines = [_week_line(1, 9, 20, NOW + timedelta(hours=7)), _week_line(2, 10, 22, NOW + timedelta(days=2))]
    prior = {date(2026, 10, 20): {7: _history(9)}, date(2026, 10, 22): {7: _history(10)}}

    games = freezable_games(lines, prior, NOW)

    assert [[row.quality_flags for row in game.rows] for game in games] == [[["few_prior_games"]], [["no_over_probability"]]]


def test_a_player_with_no_prior_games_is_frozen_unprojected() -> None:
    (game,) = freezable_games([_week_line(1, 9, 20, NOW + timedelta(hours=7))], {}, NOW)

    assert game.rows[0].projection is None and game.rows[0].quality_flags == ["few_prior_games"]


def test_the_frozen_row_matches_what_the_game_page_serves() -> None:
    history = _history(20)
    page_line = {"player_id": 7, "player_name": "Amy", "position": "G", "team": "NYK", "market": "assists",
                 "odds_type": "standard", "line": 4.5, "fetched_at": FETCHED}
    (served,) = props_response(9, [page_line], {7: history}, []).lines
    frozen_line = _week_line(1, 9, 20, NOW + timedelta(hours=7), "assists", 4.5)
    (game,) = freezable_games([frozen_line], {date(2026, 10, 20): {7: history}}, NOW)
    (row,) = game.rows

    assert (row.projection, row.p_over, row.p_under, row.over_probability_version) == (
        served.projection, served.p_over, served.p_under, served.over_probability_version)
    assert row.feature_snapshot["gap"] == served.gap
    assert row.quality_flags == list(served.flags)

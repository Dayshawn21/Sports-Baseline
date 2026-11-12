import datetime as dt
from dataclasses import replace

from app.core.nhl_projection_backtest import HOLDOUT_SEASON
from app.core.nhl_projection_history import NhlProjectionHistoryLine, NhlProjectionHistoryPoint, nhl_history_point
from app.core.projection_history import latest_line_per_match
from app.repositories.nhl import NHL_PROJECTION_HISTORY_FIRST_SEASON

FETCHED = dt.datetime(2026, 11, 7, 23, 0, tzinfo=dt.UTC)
SKATER = {
    "shots": 5, "points": 1, "assists": 1, "goals": 0, "power_play_points": 0, "blocked_shots": 1,
    "plus_minus": 1, "hits": 2, "faceoffs_won": 0, "time_on_ice_seconds": 1305,
}
GOALIE = {"saves": 28, "goals_against": 2, "started": True, "time_on_ice_seconds": 3600}


def _line(market: str = "shots_on_goal", **changes: object) -> NhlProjectionHistoryLine:
    line = NhlProjectionHistoryLine(
        line_id=10, game_id=500, season=2026, game_date=dt.date(2026, 11, 7), market=market, line=3.0,
        fetched_at=FETCHED, projection=2.9, opponent_id=14, opponent_code="TBL",
        skater_row=SKATER, goalie_row=None, game_has_box_scores=True,
    )
    return replace(line, **changes)


def _point(line: NhlProjectionHistoryLine) -> NhlProjectionHistoryPoint:
    point = nhl_history_point(line)
    assert isinstance(point, NhlProjectionHistoryPoint)
    return point


def test_a_settled_skater_line_keeps_line_projection_result_and_opponent() -> None:
    point = _point(_line())
    assert (point.stat, point.line, point.projection, point.actual) == ("shots_on_goal", 3.0, 2.9, 5)
    assert (point.opponent_id, point.opponent_name, point.season, point.snapshot_at) == (14, "TBL", 2026, FETCHED)


def test_a_settled_goalie_line_reads_the_goalie_row() -> None:
    point = _point(_line("goalie_saves", line=26.5, skater_row=None, goalie_row=GOALIE))
    assert point.actual == 28


def test_time_on_ice_is_charted_in_minutes() -> None:
    assert _point(_line("time_on_ice", line=21.5)).actual == 21.75


def test_a_skater_who_did_not_dress_is_void() -> None:
    assert nhl_history_point(_line(skater_row=None, opponent_id=None, opponent_code=None)) == "void"


def test_a_goalie_who_did_not_start_is_void() -> None:
    benched = {**GOALIE, "started": False}
    assert nhl_history_point(_line("goalie_saves", skater_row=None, goalie_row=benched)) == "void"


def test_an_unloaded_game_is_unsettled_not_void() -> None:
    line = _line(skater_row=None, game_has_box_scores=False, opponent_id=None, opponent_code=None)
    assert nhl_history_point(line) == "unsettled"


def test_a_missing_stat_is_unsettled_never_zero() -> None:
    assert nhl_history_point(_line("hits", skater_row={**SKATER, "hits": None})) == "unsettled"


def test_a_gated_line_keeps_its_null_projection_and_still_charts_the_result() -> None:
    point = _point(_line(projection=None))
    assert point.projection is None and point.actual == 5


def test_a_reissued_line_keeps_the_later_fetch() -> None:
    early = _line(line_id=10, line=3.5, fetched_at=FETCHED - dt.timedelta(days=1))
    late = _line(line_id=11, line=3.0)
    other_stat = _line("points", line_id=12, line=0.5)
    kept = latest_line_per_match([late, early, other_stat])
    assert sorted((row.market, row.line) for row in kept) == [("points", 0.5), ("shots_on_goal", 3.0)]


def test_a_reissue_tie_on_fetch_time_goes_to_the_higher_line_id() -> None:
    kept = latest_line_per_match([_line(line_id=21, line=2.5), _line(line_id=20, line=3.5)])
    assert [row.line_id for row in kept] == [21]


def test_the_history_floor_stays_above_the_holdout_season() -> None:
    assert NHL_PROJECTION_HISTORY_FIRST_SEASON > HOLDOUT_SEASON

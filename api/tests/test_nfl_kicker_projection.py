import pytest

from app.core.nfl_kicker_projection import (
    KICKER_PRIOR_GAMES, KICKER_PROJECTED, KICKER_PROJECTION_SERVED, KICKER_REPLAY_MARKETS, NFL_KICKER_MODEL_VERSION,
    kicker_reference, kicker_row, shrunk_average,
)
from app.core.nfl_projection import NFL_PROJECTION_MODEL_VERSION
from app.services.nfl.slate import _slate_line
from tests.helpers.nfl_kicker_rows import kicker_averages as _averages
from tests.helpers.nfl_kicker_rows import kicker_line_row as _kicker_row
from tests.helpers.nfl_kicker_rows import kicker_season as _season

TWO_SEASONS = {2025: _season(6, 10.0), 2024: _season(17, 8.0)}
BLENDED_PLAYER = (6 * 10.0 + 0.6 * 17 * 8.0) / (6 + 0.6 * 17)
EFFECTIVE_GAMES = 6 + 0.6 * 17


def test_the_pre_registered_constants() -> None:
    assert (NFL_KICKER_MODEL_VERSION, KICKER_PRIOR_GAMES, KICKER_PROJECTION_SERVED) == ("nfl-kicker-v1", 10.0, False)
    assert KICKER_REPLAY_MARKETS == {"K": ("fantasy_points",)}


@pytest.mark.parametrize(
    ("games", "expected"), [(0, 8.0), (4, (4 * 10 + 10 * 8) / 14), (30, (30 * 10 + 10 * 8) / 40)],
)
def test_the_shrink_weighs_the_position_mean_as_ten_games(games: float, expected: float) -> None:
    assert shrunk_average(10.0, 8.0, games) == pytest.approx(expected)


def test_two_seasons_blend_then_shrink_toward_the_position() -> None:
    prepared = kicker_row(_kicker_row(TWO_SEASONS), 2025)

    expected = (EFFECTIVE_GAMES * BLENDED_PLAYER + 10 * 8.5) / (EFFECTIVE_GAMES + 10)
    assert prepared["averages"]["fantasy_points"] == pytest.approx(expected)
    assert prepared["averages"]["games"] == 23
    assert prepared[KICKER_PROJECTED] is True


def test_one_season_shrinks_its_own_average_by_its_own_games() -> None:
    prepared = kicker_row(_kicker_row({2025: _season(6, 10.0)}), 2025)

    assert prepared["averages"]["fantasy_points"] == pytest.approx((6 * 10.0 + 10 * 8.5) / 16)


def test_a_last_season_only_kicker_uses_that_season() -> None:
    prepared = kicker_row(_kicker_row({2024: _season(17, 8.0, 9.0)}, chosen=2024), 2025)

    assert prepared["averages"]["fantasy_points"] == pytest.approx((17 * 8.0 + 10 * 9.0) / 27)


@pytest.mark.parametrize(("position", "market"), [("WR", "fantasy_points"), ("K", "receiving_yards"), ("P", "fantasy_points")])
def test_any_other_row_is_left_alone(position: str, market: str) -> None:
    row = _kicker_row(TWO_SEASONS, position=position, market=market)

    assert kicker_row(row, 2025) is row
    assert kicker_reference(row, 2025) is None


def test_a_kicker_without_prizepicks_points_is_never_projected_from_zero() -> None:
    row = _kicker_row({2025: _season(6, None)})

    assert KICKER_PROJECTED not in kicker_row(row, 2025)
    assert _slate_line(kicker_row(row, 2025), 2025, None).projection is None


def test_the_reference_is_the_blended_position_mean() -> None:
    seasons = {2025: _season(6, 10.0, 9.0), 2024: _season(17, 8.0, 8.0)}

    assert kicker_reference(_kicker_row(seasons), 2025) == round((6 * 9.0 + 0.6 * 17 * 8.0) / (6 + 0.6 * 17), 2)


def test_a_prepared_kicker_line_is_projected_under_its_own_version_without_p_over() -> None:
    line = _slate_line(kicker_row(_kicker_row(TWO_SEASONS), 2025), 2025, None)

    expected = round((EFFECTIVE_GAMES * BLENDED_PLAYER + 10 * 8.5) / (EFFECTIVE_GAMES + 10), 2)
    assert line.projection == expected
    assert line.edge == round(expected - 8.5, 2)
    assert line.projection_model_version == NFL_KICKER_MODEL_VERSION
    assert (line.p_over, line.over_probability_version) == (None, None)
    assert "position_not_scored" not in line.quality_flags


def test_the_moneyline_bump_applies_to_a_kicker_as_to_any_fantasy_line() -> None:
    plain = _slate_line(kicker_row(_kicker_row(TWO_SEASONS), 2025), 2025, None)
    favored = _slate_line(kicker_row(_kicker_row(TWO_SEASONS), 2025), 2025, 0.60)

    assert plain.projection is not None
    assert favored.projection == pytest.approx(plain.projection * 1.08, abs=0.01)


def test_an_unprepared_kicker_line_stays_hidden() -> None:
    line = _slate_line(_kicker_row(TWO_SEASONS), 2025, None)

    assert (line.projection, line.edge, line.p_over) == (None, None, None)
    assert "position_not_scored" in line.quality_flags
    assert line.projection_model_version == NFL_PROJECTION_MODEL_VERSION


def test_a_receiver_fantasy_line_is_identical_through_kicker_row() -> None:
    seasons = {2025: _season(6, 12.0) | {"averages": _averages(6, 11.0, 12.0)}}
    row = _kicker_row(seasons, position="WR")

    assert _slate_line(kicker_row(row, 2025), 2025, 0.55) == _slate_line(row, 2025, 0.55)

from datetime import date, timedelta

import pytest

from app.core import nba_over_probability_fit as fit
from app.core.nba_line_only import LINE_ONLY_COLUMNS
from app.core.nba_projection import project_line
from app.core.nba_projection_backtest import ARMS, REFERENCE_ARM, NbaHistoryRow
from app.core.nfl_over_probability import over_probability
from app.nba.markets import NbaPropMarket

START = date(2025, 10, 21)


def row(day: int, *, minutes: float | None = 30.0, **stats: int | None) -> NbaHistoryRow:
    values: dict[str, int | bool | None] = {column: 1 for column in LINE_ONLY_COLUMNS}
    values.update({"points": 10, "rebounds": 5, "assists": 3, "did_not_play": False})
    values.update(stats)
    return NbaHistoryRow(
        player_id=1, game_id=1000 + day, season=2025, game_date=START + timedelta(days=day), game_type="REG",
        did_not_play=False, minutes=minutes, stats=values,
    )


def history(games: int, **overrides: int | float | None) -> list[NbaHistoryRow]:
    return [row(day, **overrides) for day in range(games)]


def test_nine_prior_games_is_not_eligible() -> None:
    result = project_line(history(9), NbaPropMarket.POINTS, 9.5)
    assert result.projection is None
    assert result.gap is None and result.p_over is None
    assert result.flags == ("few_prior_games",)


def test_ten_prior_games_is_eligible() -> None:
    result = project_line(history(10), NbaPropMarket.POINTS, 9.5)
    assert result.projection == 10.0
    assert result.games_in_sample == 10
    assert result.prior_minutes == 30.0


def test_under_twenty_minutes_is_not_eligible() -> None:
    result = project_line(history(12, minutes=19.9), NbaPropMarket.POINTS, 9.5)
    assert result.projection is None
    assert result.prior_minutes == pytest.approx(19.9)
    assert result.flags == ("low_minutes",)


def test_twenty_minutes_is_eligible() -> None:
    result = project_line(history(12, minutes=20.0), NbaPropMarket.POINTS, 9.5)
    assert result.projection == 10.0
    assert "low_minutes" not in result.flags


def test_no_stored_minutes_is_not_eligible() -> None:
    result = project_line(history(12, minutes=None), NbaPropMarket.POINTS, 9.5)
    assert result.prior_minutes is None
    assert result.flags == ("low_minutes",)


def test_the_window_is_the_last_twenty_of_twenty_five() -> None:
    prior = [row(day, points=0) for day in range(5)] + [row(day, points=20) for day in range(5, 25)]
    result = project_line(prior, NbaPropMarket.POINTS, 15.5)
    assert result.projection == 20.0
    assert result.games_in_sample == 20


def test_the_projection_is_the_harness_reference_arm() -> None:
    prior = [row(day, points=day, rebounds=day % 7, assists=day % 4) for day in range(25)]
    for market in NbaPropMarket:
        assert project_line(prior, market, 0.5).projection == ARMS[REFERENCE_ARM](prior, market)


def test_the_gap_is_projection_minus_line_rounded() -> None:
    prior = [row(day, points=10 + (day % 3)) for day in range(11)]
    result = project_line(prior, NbaPropMarket.POINTS, 12.5)
    assert result.projection == pytest.approx(120 / 11)
    assert result.gap == -1.59
    assert project_line(history(12), NbaPropMarket.POINTS, 8.5).gap == 1.5


def test_assists_carry_p_over_from_the_fit() -> None:
    result = project_line(history(12), NbaPropMarket.ASSISTS, 2.5)
    expected = over_probability(fit.QUANTILES_BY_MARKET["assists"], 3.0, 2.5)
    assert expected is not None
    assert result.p_over == expected.p_over
    assert result.p_under == pytest.approx(1 - expected.p_over)
    assert result.over_probability_version == "nba-pover-v1"
    assert result.flags == ()


def test_points_have_no_fitted_p_over() -> None:
    result = project_line(history(12), NbaPropMarket.POINTS, 9.5)
    assert result.projection == 10.0
    assert (result.p_over, result.p_under, result.over_probability_version) == (None, None, None)
    assert result.flags == ("no_over_probability",)


def test_an_integer_line_has_no_p_over() -> None:
    result = project_line(history(12), NbaPropMarket.ASSISTS, 3.0)
    assert result.projection == 3.0
    assert result.p_over is None and result.over_probability_version is None
    assert result.flags == ("integer_line",)


def test_a_stale_fit_hides_p_over(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fit, "FIT_PROJECTION_MODEL_VERSION", "nba-reference-v0")
    result = project_line(history(12), NbaPropMarket.ASSISTS, 2.5)
    assert result.projection == 3.0
    assert result.p_over is None
    assert result.flags == ("no_over_probability",)


def test_an_empty_fit_means_no_p_over(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fit, "SHOWN_MARKETS", frozenset())
    assert project_line(history(12), NbaPropMarket.ASSISTS, 2.5).flags == ("no_over_probability",)


def test_a_zero_projection_has_no_p_over() -> None:
    result = project_line(history(12, assists=0), NbaPropMarket.ASSISTS, 0.5)
    assert result.projection == 0.0
    assert result.p_over is None
    assert result.flags == ("no_over_probability",)


@pytest.mark.parametrize("prior", [history(3), history(12), history(12, minutes=5.0)])
def test_the_model_version_is_always_the_reference(prior: list[NbaHistoryRow]) -> None:
    assert project_line(prior, NbaPropMarket.ASSISTS, 2.5).model_version == "nba-reference-v1"

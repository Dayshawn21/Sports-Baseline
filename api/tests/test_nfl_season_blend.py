import pytest

from app.core.nfl_season_blend import (
    PREVIOUS_SEASON_WEIGHT, apply_season_blend, blend_averages, blend_usage, blended_row, season_blend_inputs,
)


def _averages(games: int, receiving_yards: float, fantasy_points: float | None = 10.0) -> dict:
    return {
        "games": games, "passing_yards": 0.0, "passing_attempts": 0.0, "passing_completions": 0.0,
        "rushing_yards": 0.0, "rushing_attempts": 0.0, "receiving_yards": receiving_yards,
        "receptions": receiving_yards / 10, "touchdowns": 0.5, "fantasy_points": fantasy_points,
    }


def _season(games: int, receiving_yards: float, usage_games: int | None = None, target_share: float = 0.2) -> dict:
    usage_games = games if usage_games is None else usage_games
    return {
        "averages": _averages(games, receiving_yards),
        "position_averages": _averages(games * 30, receiving_yards / 2),
        "usage": {"games": usage_games, "targets": 7.0, "target_share": target_share} if usage_games else None,
        "position_usage": {"games": games * 30, "targets": 4.0, "target_share": 0.1},
    }


def test_week_five_gives_the_current_season_28_percent() -> None:
    blended = blend_averages(_averages(4, 100.0), _averages(17, 0.0))

    # 4 / (4 + 0.6 * 17) = 0.2817
    assert blended["receiving_yards"] == pytest.approx(100.0 * 4 / (4 + PREVIOUS_SEASON_WEIGHT * 17))
    assert blended["receiving_yards"] == pytest.approx(28.17, abs=0.01)


def test_blended_games_are_the_raw_sum_not_the_weighted_one() -> None:
    assert blend_averages(_averages(4, 100.0), _averages(17, 0.0))["games"] == 21


def test_fantasy_blends_only_the_seasons_that_have_it() -> None:
    one_missing = blend_averages(_averages(4, 0.0, fantasy_points=20.0), _averages(17, 0.0, fantasy_points=None))
    both_missing = blend_averages(_averages(4, 0.0, fantasy_points=None), _averages(17, 0.0, fantasy_points=None))

    assert one_missing["fantasy_points"] == 20.0
    assert both_missing["fantasy_points"] is None


def test_usage_weights_by_usage_games_and_passes_a_lone_season_through() -> None:
    current = {"games": 3, "targets": 9.0, "target_share": 0.3}
    previous = {"games": 10, "targets": 3.0, "target_share": 0.1}

    blended = blend_usage(current, previous)

    assert blended is not None
    assert blended["games"] == 13
    assert blended["targets"] == pytest.approx((9.0 * 3 + 3.0 * 6) / 9)
    assert blend_usage(current, None) == current
    assert blend_usage(None, previous) == previous
    assert blend_usage(None, None) is None


def test_a_rookie_and_a_week_one_line_leave_the_choice_to_the_chooser() -> None:
    # One season means nothing to blend; choose_baseline_season already picks it,
    # and knows to prefer a full season two years back over a thin last one.
    assert season_blend_inputs({2026: _season(3, 50.0)}, 2026) is None
    assert season_blend_inputs({2025: _season(2, 80.0), 2024: _season(17, 60.0)}, 2026) is None


def test_no_played_season_returns_none() -> None:
    assert season_blend_inputs({}, 2026) is None
    assert season_blend_inputs({2026: _season(0, 0.0)}, 2026) is None


def test_a_later_season_is_ignored_and_a_gap_year_blends_the_last_season_played() -> None:
    inputs = season_blend_inputs({2024: _season(17, 0.0), 2026: _season(4, 100.0), 2027: _season(5, 999.0)}, 2026)

    assert inputs is not None
    assert inputs["averages"]["games"] == 21
    assert inputs["averages"]["receiving_yards"] == pytest.approx(100.0 * 4 / (4 + 0.6 * 17))


def test_position_inputs_use_the_players_season_weights() -> None:
    inputs = season_blend_inputs({2025: _season(17, 0.0), 2026: _season(4, 100.0)}, 2026)

    assert inputs is not None
    # Position rows have 30x the games, but the mix follows the player's 4 and 17.
    assert inputs["position_averages"]["receiving_yards"] == pytest.approx(50.0 * 4 / (4 + 0.6 * 17))
    assert inputs["position_averages"]["games"] == 21 * 30
    assert inputs["usage"] is not None and inputs["usage"]["games"] == 21


def test_blended_row_skips_anytime_td_and_apply_skips_unadopted_markets() -> None:
    seasons = {2025: _season(17, 0.0), 2026: _season(4, 100.0)}
    receiving = {"market": "receiving_yards", "averages": _averages(4, 100.0), "baseline_seasons": seasons}
    touchdown = {**receiving, "market": "anytime_touchdown"}

    assert blended_row(receiving, 2026)["averages"]["games"] == 21
    assert blended_row(touchdown, 2026) is touchdown
    assert apply_season_blend(receiving, 2026) is receiving


def test_an_adopted_market_reports_the_blend_and_its_own_season_games() -> None:
    seasons = {2025: _season(17, 0.0), 2026: _season(4, 100.0)}
    passing = {"market": "passing_yards", "baseline_reason": "current_season", "baseline_seasons": seasons}

    blended = apply_season_blend(passing, 2026)

    assert blended["averages"]["games"] == 21
    assert blended["baseline_reason"] == "current_previous_blend"
    assert blended["current_season_games"] == 4
    assert apply_season_blend({**passing, "baseline_seasons": {2026: _season(4, 100.0)}}, 2026)["baseline_reason"] == "current_season"


def _environment(games: int, team_total: float, team_margin: float) -> dict:
    return {"games": games, "team_total": team_total, "team_margin": team_margin}


def test_environment_blends_by_games_with_lines_and_sums_them() -> None:
    current = {**_season(4, 100.0), "environment": _environment(4, 20.0, -3.0)}
    previous = {**_season(17, 0.0), "environment": _environment(16, 26.0, 5.0)}

    inputs = season_blend_inputs({2025: previous, 2026: current}, 2026)

    assert inputs is not None
    share = 4 / (4 + 0.6 * 16)
    assert inputs["environment"]["team_total"] == pytest.approx(20.0 * share + 26.0 * (1 - share))
    assert inputs["environment"]["team_margin"] == pytest.approx(-3.0 * share + 5.0 * (1 - share))
    assert inputs["environment"]["games"] == 20


def test_environment_uses_the_one_season_that_has_it() -> None:
    lined = _environment(4, 20.0, -3.0)
    current = {**_season(4, 100.0), "environment": lined}
    previous = {**_season(17, 0.0), "environment": None}

    only_current = season_blend_inputs({2025: previous, 2026: current}, 2026)
    neither = season_blend_inputs({2025: previous, 2026: {**current, "environment": None}}, 2026)

    assert only_current is not None and only_current["environment"] == lined
    assert neither is not None and neither["environment"] is None

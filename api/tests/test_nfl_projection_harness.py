from datetime import UTC, datetime

import pytest

from app.backtest.nfl_projections import ARMS, report
from app.core.nfl_game_environment import NflEnvironmentSlopes, apply_game_environment
from app.core.nfl_projection_backtest import ReplayCase
from app.nfl.markets import NflPropMarket
from app.services.nfl.slate import _slate_line


def _case(player_id: int, projection: float, actual: float) -> ReplayCase:
    return ReplayCase(
        player_id=player_id, game_id=1, week=5, position="WR", market="receptions",
        projection=projection, actual=actual,
    )


def _arms() -> dict[str, list[ReplayCase]]:
    actuals = [7.0 if player_id % 2 else 3.0 for player_id in range(300)]
    production = [_case(player_id, 5.0, actual) for player_id, actual in enumerate(actuals)]
    # Closer on every over, unchanged on every under: 12.5% lower MAE.
    usage_off = [
        _case(player_id, 5.5 if actual == 7.0 else 5.0, actual) for player_id, actual in enumerate(actuals)
    ]
    return {"production": production, "usage_off": usage_off}


def test_report_prints_metrics_a_paired_row_and_a_verdict() -> None:
    text = report(2025, _arms())

    assert "receptions / all                  300     2.00     2.00    +0.00    50.0%" in text
    assert "receptions / WR                   300     2.00     2.00    +0.00    50.0%" in text
    assert "receptions                300     2.000     1.750  -12.50%   -0.250   0.014  adopt" in text
    assert "pre-registered 2026-09-26" in text


def test_usage_off_drops_only_the_usage_input() -> None:
    row = {"usage": {"games": 4}, "position_usage": {"games": 40}, "market": "receptions"}

    assert ARMS["usage_off"](row, 2025) == {"usage": None, "position_usage": {"games": 40}, "market": "receptions"}
    assert ARMS["production"](row, 2025) is row


def _averages(games: int, receiving_yards: float) -> dict:
    return {
        "games": games, "passing_yards": 0.0, "passing_attempts": 0.0, "passing_completions": 0.0,
        "rushing_yards": 0.0, "rushing_attempts": 0.0, "receiving_yards": receiving_yards,
        "receptions": 0.0, "touchdowns": 0.0, "fantasy_points": None,
    }


def _replay_row(**overrides: object) -> dict:
    return {
        "id": 1, "game_id": 2, "player_id": 3, "player_name": "Receiver", "position": "WR",
        "player_team_id": 4, "home_team_id": 4, "market": "receiving_yards", "segment": "full_game",
        "opponent_team": "BUF", "opponent_team_id": 5,
        "odds_type": "standard", "line": 0.0, "provider": "replay", "fetched_at": datetime(2025, 11, 9, tzinfo=UTC),
        "baseline_season": 2025, "baseline_reason": "current_season",
        "averages": _averages(8, 60.0), "position_averages": _averages(200, 40.0), "baseline_seasons": {},
        # Per player row: 51 "games" from about 17 real ones, 5% above the league.
        "opponent_averages": _averages(51, 42.0), "league_position_averages": _averages(3000, 40.0),
        # Per team-game: 17 real games, 8% above the league.
        "team_game_opponent_averages": _averages(17, 162.0), "team_game_league_averages": _averages(540, 150.0),
    } | overrides


def test_dvp_team_game_arm_swaps_in_the_team_game_ratio_and_real_game_count() -> None:
    row = _replay_row()

    production = _slate_line(ARMS["production"](row, 2025), 2025, None)
    team_game = _slate_line(ARMS["dvp_team_game"](row, 2025), 2025, None)

    assert (production.opponent_adjustment_pct, production.opponent_sample_games) == (5.0, 51)
    assert (team_game.opponent_adjustment_pct, team_game.opponent_sample_games) == (8.0, 17)
    assert team_game.projection == 64.8
    assert row["opponent_averages"]["games"] == 51


def test_unknown_opponent_is_missing_in_both_arms() -> None:
    row = _replay_row(
        opponent_team=None, opponent_team_id=None, opponent_averages=None, team_game_opponent_averages=None,
    )

    for arm in ("production", "dvp_team_game"):
        line = _slate_line(ARMS[arm](row, 2025), 2025, None)
        assert line.opponent_adjustment_pct is None
        assert "opponent_data_missing" in line.quality_flags


def test_production_arm_serves_team_game_dvp_for_adopted_markets_only() -> None:
    completions = _replay_row(position="QB", market="passing_completions")
    receiving = _replay_row()

    assert _slate_line(ARMS["production"](completions, 2025), 2025, None).opponent_sample_games == 17
    assert _slate_line(ARMS["production"](receiving, 2025), 2025, None).opponent_sample_games == 51


def _season(games: int, receiving_yards: float) -> dict:
    return {
        "averages": _averages(games, receiving_yards), "position_averages": _averages(games * 30, 40.0),
        "usage": None, "position_usage": None,
    }


def _two_season_row(**overrides: object) -> dict:
    # Production picks 2025 (4 games) alone; the blend adds 2024's 17 at 0.6.
    return _replay_row(
        averages=_averages(4, 100.0), baseline_seasons={2025: _season(4, 100.0), 2024: _season(17, 0.0)},
        **overrides,
    )


def test_season_blend_arm_projects_from_the_blend_with_the_raw_game_count() -> None:
    row = _two_season_row()

    production = _slate_line(ARMS["production"](row, 2025), 2025, None)
    blended = _slate_line(ARMS["season_blend"](row, 2025), 2025, None)

    # Both carry the 5% per-player DVP; only the baseline differs.
    assert (production.projection, production.games_in_sample) == (105.0, 4)
    assert blended.projection == round(100.0 * 4 / (4 + 0.6 * 17) * 1.05, 2)
    assert blended.games_in_sample == 21


def test_season_blend_keeps_team_game_dvp_on_passing_completions() -> None:
    row = _two_season_row(position="QB", market="passing_completions")

    for arm in ("production", "season_blend"):
        assert _slate_line(ARMS[arm](row, 2025), 2025, None).opponent_sample_games == 17


def _rushing_row(**overrides: object) -> dict:
    averages = _averages(8, 0.0) | {"rushing_attempts": 15.0}
    return _replay_row(**{
        "position": "RB", "market": "rushing_attempts", "averages": averages,
        # A usual game: 22-point team total, even margin.
        "environment": {"games": 8, "team_total": 22.0, "team_margin": 0.0},
        # Home and favored by a touchdown, one more than usual.
        "game_lines": {"home_spread_margin": 7.0, "total": 44.0},
    } | overrides)


def test_game_environment_arm_swaps_the_moneyline_bump_for_the_margin_slope() -> None:
    row = _rushing_row()

    production = _slate_line(ARMS["production"](row, 2025), 2025, 0.75)
    environment = _slate_line(ARMS["game_environment"](row, 2025), 2025, 0.75)

    # Production: a 75% favorite gets the capped +8% moneyline bump.
    assert production.projection == 16.2
    # The arm: no moneyline bump, one touchdown of margin times the +0.120 slope.
    assert environment.projection == 16.8


def test_game_environment_arm_removes_the_bump_on_a_zero_slope_market() -> None:
    row = _replay_row()

    production = _slate_line(ARMS["production"](row, 2025), 2025, 0.75)
    environment = _slate_line(ARMS["game_environment"](row, 2025), 2025, 0.75)

    # Both keep the 5% DVP on 60 yards; only production adds the 8% moneyline bump.
    assert production.projection == round(60.0 * 1.05 * 1.08, 2)
    assert environment.projection == 63.0


def test_game_environment_arm_without_lines_gets_neither_adjustment() -> None:
    row = _rushing_row(game_lines=None)

    assert _slate_line(ARMS["game_environment"](row, 2025), 2025, 0.75).projection == 15.0


def test_game_environment_arm_leaves_anytime_td_alone() -> None:
    row = _replay_row(market="anytime_touchdown")

    assert ARMS["game_environment"](row, 2025) is row


def test_a_blended_row_is_compared_against_its_blended_environment() -> None:
    seasons = {
        2025: _season(4, 100.0) | {"environment": {"games": 4, "team_total": 22.0, "team_margin": 7.0}},
        2024: _season(17, 0.0) | {"environment": {"games": 17, "team_total": 22.0, "team_margin": 0.0}},
    }
    row = _replay_row(
        position="QB", market="passing_yards", baseline_seasons=seasons,
        environment=seasons[2025]["environment"], game_lines={"home_spread_margin": 7.0, "total": 44.0},
    )
    slopes = {NflPropMarket.PASSING_YARDS: NflEnvironmentSlopes(total=0.0, margin=0.1)}

    switched = apply_game_environment(ARMS["production"](row, 2025), frozenset(slopes), slopes)

    blended_margin = 7.0 * 4 / (4 + 0.6 * 17)
    assert switched["environment"]["team_margin"] == pytest.approx(blended_margin)
    assert switched["environment_adjustment_pct"] == round((7.0 - blended_margin) / 7 * 0.1 * 100, 2)


def _fantasy_averages(games: int, ppr: float, prizepicks: float) -> dict:
    return _averages(games, 0.0) | {"fantasy_points": ppr, "prizepicks_fantasy_points": prizepicks}


def _qb_fantasy_row() -> dict:
    # A QB whose interceptions cost him a point a game more under PPR than under PrizePicks.
    return _replay_row(
        position="QB", market="fantasy_points",
        averages=_fantasy_averages(8, 18.0, 19.0), position_averages=_fantasy_averages(200, 16.0, 16.8),
        opponent_averages=_fantasy_averages(51, 16.0, 16.8), league_position_averages=_fantasy_averages(3000, 16.0, 16.8),
        baseline_seasons={2025: {
            "averages": _fantasy_averages(8, 18.0, 19.0), "position_averages": _fantasy_averages(200, 16.0, 16.8),
            "usage": None, "position_usage": None,
        }},
    )


def test_prizepicks_fantasy_arm_projects_a_qb_from_prizepicks_points() -> None:
    row = _qb_fantasy_row()

    production = _slate_line(ARMS["production"](row, 2025), 2025, None)
    prizepicks = _slate_line(ARMS["prizepicks_fantasy"](row, 2025), 2025, None)

    assert production.projection == 18.0
    assert prizepicks.projection == 19.0
    assert row["averages"]["fantasy_points"] == 18.0


def test_prizepicks_fantasy_arm_swaps_every_fantasy_average_and_season() -> None:
    swapped = ARMS["prizepicks_fantasy"](_qb_fantasy_row(), 2025)

    for key in ("averages", "position_averages", "opponent_averages", "league_position_averages"):
        assert swapped[key]["fantasy_points"] == swapped[key]["prizepicks_fantasy_points"]
    assert swapped["baseline_seasons"][2025]["averages"]["fantasy_points"] == 19.0
    assert swapped["team_game_opponent_averages"] == _qb_fantasy_row()["team_game_opponent_averages"]


def test_prizepicks_fantasy_arm_leaves_other_markets_unchanged() -> None:
    row = _replay_row()

    production = _slate_line(ARMS["production"](row, 2025), 2025, None)
    prizepicks = _slate_line(ARMS["prizepicks_fantasy"](row, 2025), 2025, None)

    assert prizepicks == production


def _passing_row(**overrides: object) -> dict:
    averages = _averages(8, 0.0) | {"passing_yards": 240.0}
    return _replay_row(**{
        "position": "QB", "market": "passing_yards", "averages": averages,
        "game_weather": {"roof": "outdoors", "wind": 15},
    } | overrides)


def test_wind_arm_cuts_passing_yards_by_the_frozen_slope() -> None:
    row = _passing_row()

    production = _slate_line(ARMS["production"](row, 2025), 2025, 0.75)
    windy = _slate_line(ARMS["wind"](row, 2025), 2025, 0.75)

    # 15 mph is 0.5 above the threshold, times the -0.245 slope: -12.25%.
    assert windy.projection == pytest.approx(production.projection * (1 - 0.1225), abs=0.01)


def test_wind_arm_caps_a_gale_at_fifteen_percent() -> None:
    row = _passing_row(game_weather={"roof": "outdoors", "wind": 30})

    production = _slate_line(ARMS["production"](row, 2025), 2025, 0.75)
    windy = _slate_line(ARMS["wind"](row, 2025), 2025, 0.75)

    assert windy.projection == pytest.approx(production.projection * 0.85, abs=0.01)


@pytest.mark.parametrize("overrides", [
    {"game_weather": {"roof": "dome", "wind": None}},
    {"game_weather": {"roof": "outdoors", "wind": None}},
    {"game_weather": None},
    {"market": "passing_attempts"},
    {"position": "WR", "market": "receiving_yards", "averages": _averages(8, 60.0)},
])
def test_wind_arm_leaves_indoor_unknown_zero_slope_and_other_markets_unchanged(overrides: dict) -> None:
    row = _passing_row(**overrides)

    production = _slate_line(ARMS["production"](row, 2025), 2025, 0.75)
    windy = _slate_line(ARMS["wind"](row, 2025), 2025, 0.75)

    assert windy.projection == production.projection


def test_wind_arm_leaves_anytime_td_alone() -> None:
    row = _passing_row(market="anytime_touchdown")

    assert ARMS["wind"](row, 2025) == ARMS["production"](row, 2025)

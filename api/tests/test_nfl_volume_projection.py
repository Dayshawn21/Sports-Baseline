import copy

import pytest

from app.core.nfl_volume_projection import (
    MARKET_SPECS,
    NO_FIT,
    NO_HISTORY,
    NO_OPPORTUNITIES,
    GameContext,
    PlayerGame,
    TeamVolumeFit,
    VolumeParameters,
    game_context,
    prior_games,
    project_player,
    shrunk_rate,
    shrunk_share,
)
from app.core.outcome_distribution import CompoundYards, NegativeBinomial

GAME = GameContext(season=2024, week=6, implied_team_total=24.0, implied_margin=3.0)
POSITIONS = ("QB", "RB", "WR", "TE")


def _params(**overrides) -> VolumeParameters:
    markets = list(MARKET_SPECS)
    values = dict(
        pass_volume=TeamVolumeFit(intercept=20.0, total_slope=0.5, margin_slope=-0.4),
        rush_volume=TeamVolumeFit(intercept=15.0, total_slope=0.2, margin_slope=0.6),
        previous_season_weight=0.6,
        k_share=4.0,
        k_rate={market: 50.0 for market in markets},
        position_share={(p, s): 0.1 for p in POSITIONS for s in ("targets", "rushing_attempts", "passing_attempts")},
        position_rate={(p, r): 0.6 for p in POSITIONS for r in ("receptions", "passing_completions")}
        | {(p, r): 7.0 for p in POSITIONS for r in ("receiving_yards", "rushing_yards", "passing_yards")},
        dispersion={(m, p): 5.0 for m in markets for p in POSITIONS},
        yards_sd={(m, p): 8.0 for m in markets for p in POSITIONS},
    )
    return VolumeParameters(**(values | overrides))


def _game(season: int, week: int, team_pass: float = 35.0, team_rush: float = 25.0, **stats: float | None) -> PlayerGame:
    return PlayerGame(season, week, stats, team_pass, team_rush)


def test_only_games_before_this_week_this_season_and_last_season_count() -> None:
    history = [
        _game(2024, 5), _game(2024, 6), _game(2024, 7), _game(2023, 17), _game(2022, 10), _game(2025, 1),
    ]

    assert [(g.season, g.week) for g in prior_games(history, GAME)] == [(2024, 5), (2023, 17)]


def test_a_same_week_game_never_moves_the_projection() -> None:
    history = [_game(2024, 5, targets=6, receptions=4, receiving_yards=50)]
    with_same_week = history + [_game(2024, 6, targets=15, receptions=12, receiving_yards=200)]

    before = project_player("WR", history, GAME, _params()).distributions["receptions"]
    after = project_player("WR", with_same_week, GAME, _params()).distributions["receptions"]
    assert after == before


def test_last_season_is_weighted_by_games_at_the_previous_season_weight() -> None:
    games = [_game(2024, 1, team_pass=40, targets=10), _game(2023, 3, team_pass=40, targets=4)]
    share = shrunk_share(games, GAME, MARKET_SPECS["receptions"], prior=0.0, k=0.0, previous_weight=0.6)

    assert share == pytest.approx((0.25 * 1 + 0.10 * 0.6) / 1.6)


def test_share_shrinkage_runs_from_the_position_prior_to_the_player() -> None:
    spec = MARKET_SPECS["receptions"]
    one = [_game(2024, 1, team_pass=40, targets=10)]
    many = [_game(2024, week, team_pass=40, targets=10) for week in range(1, 6)] + [
        _game(2023, week, team_pass=40, targets=10) for week in range(1, 18)
    ]

    assert shrunk_share(one, GAME, spec, prior=0.1, k=1e9, previous_weight=0.6) == pytest.approx(0.1)
    assert shrunk_share(one, GAME, spec, prior=0.1, k=0.0, previous_weight=0.6) == pytest.approx(0.25)
    assert shrunk_share(one, GAME, spec, prior=0.1, k=4.0, previous_weight=0.6) == pytest.approx((0.25 + 0.4) / 5)
    # 5 games this season plus 17 at 0.6 last season outweigh the 4 prior games.
    assert shrunk_share(many, GAME, spec, prior=0.1, k=4.0, previous_weight=0.6) == pytest.approx(
        (15.2 * 0.25 + 4.0 * 0.1) / 19.2
    )


def test_rate_shrinkage_with_no_opportunities_is_the_position_prior() -> None:
    spec = MARKET_SPECS["receiving_yards"]
    no_targets = [_game(2024, 1, targets=0, receiving_yards=0)]
    busy = [_game(2024, week, targets=10, receiving_yards=120) for week in range(1, 6)]

    assert shrunk_rate(no_targets, GAME, spec, prior=7.0, k=50.0, previous_weight=0.6) == pytest.approx(7.0)
    assert shrunk_rate(busy, GAME, spec, prior=7.0, k=50.0, previous_weight=0.6) == pytest.approx((600 + 350) / 100)


def test_the_margin_flips_sign_between_home_and_away() -> None:
    home = game_context(2024, 6, home_spread_margin=7.0, total=45.0, is_home=True)
    away = game_context(2024, 6, home_spread_margin=7.0, total=45.0, is_home=False)

    assert (home.implied_team_total, home.implied_margin) == (26.0, 7.0)
    assert (away.implied_team_total, away.implied_margin) == (19.0, -7.0)
    rush = _params().rush_volume
    assert rush.expected(home) > rush.expected(away)


def test_team_volume_is_floored_at_zero() -> None:
    fit = TeamVolumeFit(intercept=-50.0, total_slope=0.1, margin_slope=0.0)

    assert fit.expected(GAME) == 0.0


def test_a_zero_counts_as_a_game_but_a_missing_value_does_not() -> None:
    spec = MARKET_SPECS["receptions"]
    base = [_game(2024, 1, team_pass=40, targets=10)]
    with_zero = base + [_game(2024, 2, team_pass=40, targets=0)]
    with_missing = base + [_game(2024, 2, team_pass=40, targets=None)]

    assert shrunk_share(with_zero, GAME, spec, 0.0, 0.0, 0.6) == pytest.approx(0.125)
    assert shrunk_share(with_missing, GAME, spec, 0.0, 0.0, 0.6) == pytest.approx(0.25)


def test_only_missing_opportunities_skip_the_market_with_a_reason() -> None:
    result = project_player("WR", [_game(2024, 1, targets=None, receptions=None, receiving_yards=None)], GAME, _params())

    assert result.distributions == {}
    assert result.skipped == {"receptions": NO_OPPORTUNITIES, "receiving_yards": NO_OPPORTUNITIES}


def test_a_rookie_with_no_history_gets_no_projection_and_a_reason() -> None:
    result = project_player("RB", [], GAME, _params())

    assert result.distributions == {}
    assert result.skipped == {m: NO_HISTORY for m in ("rushing_yards", "rushing_attempts", "receiving_yards", "receptions")}


def test_a_qb_never_gets_receiving_markets() -> None:
    history = [_game(2024, 1, passing_attempts=30, passing_completions=20, passing_yards=240, rushing_attempts=4,
                     rushing_yards=20, targets=1, receptions=1, receiving_yards=5)]
    result = project_player("QB", history, GAME, _params())

    assert set(result.distributions) == {
        "passing_yards", "passing_attempts", "passing_completions", "rushing_yards",
    }
    assert "receptions" not in result.skipped and "receiving_yards" not in result.skipped


def test_a_market_without_fitted_constants_is_skipped_not_defaulted() -> None:
    params = _params(yards_sd={})
    result = project_player("WR", [_game(2024, 1, targets=8, receptions=5, receiving_yards=60)], GAME, params)

    assert set(result.distributions) == {"receptions"}
    assert result.skipped == {"receiving_yards": NO_FIT}


def test_counts_and_yards_assemble_volume_share_and_rate() -> None:
    params = _params()
    history = [_game(2024, 1, team_pass=40, targets=10, receptions=7, receiving_yards=90)]
    result = project_player("WR", history, GAME, params)
    volume = params.pass_volume.expected(GAME)
    share = (0.25 + 4.0 * 0.1) / 5.0

    receptions = result.distributions["receptions"]
    assert isinstance(receptions, NegativeBinomial)
    assert receptions.mean == pytest.approx(volume * share * (7 + 50 * 0.6) / 60)

    yards = result.distributions["receiving_yards"]
    assert isinstance(yards, CompoundYards)
    assert yards.opportunities.mean == pytest.approx(volume * share)
    assert yards.yards_mean == pytest.approx((90 + 50 * 7.0) / 60)
    assert yards.yards_sd == 8.0


def test_the_history_is_not_mutated() -> None:
    history = [_game(2024, 1, targets=8, receptions=5, receiving_yards=60), _game(2023, 9, targets=3)]
    snapshot = copy.deepcopy(history)

    project_player("WR", history, GAME, _params())

    assert history == snapshot

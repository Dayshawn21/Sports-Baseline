from types import SimpleNamespace
from typing import cast

import pytest

from app.core.prop_projection import (
    _FIRST_SET_UNDERDOG_HOLD_SHIFT,
    _LEAGUE_ACE_RATE_BY_TOUR,
    _LEAGUE_DF_RATE_BY_TOUR,
    ace_matchup_factor,
    compute_stat_avg,
    double_fault_matchup_factor,
    first_set_for_matchup,
)
from app.core.tennis_first_set import shift_underdog_hold
from app.repositories.players import PlayerRollingStats


def _opponent(allowed_ace: float | None = None, allowed_df: float | None = None) -> PlayerRollingStats:
    return cast(PlayerRollingStats, SimpleNamespace(
        allowed_aces_per_sp=allowed_ace, allowed_df_per_sp=allowed_df, ret_pts_won=None,
    ))


def _player(hold: float, df_rate: float = 0.05) -> PlayerRollingStats:
    return cast(PlayerRollingStats, SimpleNamespace(
        first_in_pct=None, first_won_pct=None, second_won_pct=None, hold_pct=hold,
        df_per_game=df_rate, aces_per_game=0.05, win_rate=0.5,
        allowed_aces_per_sp=None, allowed_df_per_sp=0.052, ret_pts_won=0.4,
        break_points_created_per_return_game=None, allowed_break_points_per_service_game=None,
    ))


@pytest.mark.parametrize("tour", ["ATP", "CHALLENGER", "WTA"])
def test_a_tour_average_opponent_is_neutral(tour):
    assert ace_matchup_factor(_opponent(allowed_ace=_LEAGUE_ACE_RATE_BY_TOUR[tour]), tour) == pytest.approx(1.0)
    assert double_fault_matchup_factor(_opponent(allowed_df=_LEAGUE_DF_RATE_BY_TOUR[tour]), tour) == pytest.approx(1.0)


def test_tour_is_case_insensitive_and_unknown_falls_back_to_pooled():
    opponent = _opponent(allowed_df=0.05)
    assert double_fault_matchup_factor(opponent, "wta") == double_fault_matchup_factor(opponent, "WTA")
    assert double_fault_matchup_factor(opponent, None) == double_fault_matchup_factor(opponent, "ITF")


def test_typical_wta_opponent_no_longer_inflates_double_faults():
    # A WTA opponent allowing 0.052 read as 1.16x against the old 0.045 constant.
    assert 0.052 / 0.045 > 1.15
    assert double_fault_matchup_factor(_opponent(allowed_df=0.052), "WTA") < 1.0


def test_wta_double_fault_projection_falls():
    player, opponent = _player(0.70), _player(0.65)
    pooled = compute_stat_avg("double_faults", player, opponent, 0.5, "Hard", 21.5)
    wta = compute_stat_avg("double_faults", player, opponent, 0.5, "Hard", 21.5, tour="WTA")
    assert wta < pooled


def test_shift_lowers_only_the_weaker_server():
    assert shift_underdog_hold(0.80, 0.65, 0.05) == (0.80, pytest.approx(0.60))
    assert shift_underdog_hold(0.65, 0.80, 0.05) == (pytest.approx(0.60), 0.80)
    assert shift_underdog_hold(0.70, 0.70, 0.05) == (0.70, 0.70)


def test_wta_underdog_first_set_games_drop_and_favorite_rises():
    favorite, underdog = _player(0.70), _player(0.60)
    shifted = first_set_for_matchup(underdog, favorite, "WTA").mean_player_games
    unshifted = first_set_for_matchup(underdog, favorite).mean_player_games
    assert shifted < unshifted
    assert first_set_for_matchup(favorite, underdog, "WTA").mean_player_games > \
        first_set_for_matchup(favorite, underdog).mean_player_games
    assert _FIRST_SET_UNDERDOG_HOLD_SHIFT == {"WTA": 0.0522}


def test_atp_first_set_is_unchanged():
    favorite, underdog = _player(0.85), _player(0.75)
    assert first_set_for_matchup(underdog, favorite, "ATP") == first_set_for_matchup(underdog, favorite)

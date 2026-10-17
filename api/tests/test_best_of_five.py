"""Best-of-5 was treated as best-of-3 everywhere, which matters at the slams.

Two defects, both live going into a grand slam: the total-games projection had no
best_of parameter at all, and bankroll_builder passed win_prob into the opponent_stats
slot, so any match with both a total-games market and rolling stats raised AttributeError
out of the endpoint.
"""

import pytest

from app.core.prop_probs import total_games_probs
from app.core.prop_projection import compute_stat_avg
from app.core.tennis_props import expected_total_games_from_matchup
from app.repositories.players import PlayerRollingStats

# Measured over completed matches.
BO3_MEAN = 22.29
BO5_MEAN = 30.45


def _stats() -> PlayerRollingStats:
    return PlayerRollingStats(
        player_id=1, surface=None, stat_period="last_52w", split_type=None, split_value=None,
        win_rate=0.6, svc_pts_won=0.65, ret_pts_won=0.40, aces_per_game=0.5, df_per_game=0.2,
        hold_pct=0.80, break_pct=0.25, matches_count=30,
        first_in_pct=0.62, first_won_pct=0.72, second_won_pct=0.50,
    )


class TestProjectionLevel:
    def test_best_of_three_lands_near_its_empirical_mean(self):
        assert compute_stat_avg("total_games", _stats(), win_prob=0.65) == pytest.approx(BO3_MEAN, abs=2.0)

    def test_best_of_five_lands_near_its_empirical_mean(self):
        got = compute_stat_avg("total_games", _stats(), win_prob=0.65, best_of=5)
        assert got == pytest.approx(BO5_MEAN, abs=2.0)

    def test_best_of_five_projects_materially_more_games(self):
        bo3 = compute_stat_avg("total_games", _stats(), win_prob=0.65)
        bo5 = compute_stat_avg("total_games", _stats(), win_prob=0.65, best_of=5)
        assert bo5 - bo3 > 6.0

    def test_matchup_sensitivity_survives_the_scaling(self):
        close = expected_total_games_from_matchup(0.80, 0.80, 0.50, 5)
        lopsided = expected_total_games_from_matchup(0.80, 0.80, 0.90, 5)
        assert close > lopsided

    def test_the_market_line_still_wins_when_present(self):
        got = compute_stat_avg("total_games", _stats(), win_prob=0.65,
                               market_total_games=38.5, best_of=5)
        assert got == pytest.approx(38.5)


class TestWinProbMustBeKeyword:
    def test_passing_win_prob_positionally_is_the_bug_that_crashed(self):
        # Third positional parameter is opponent_stats; a float there reaches serve_hold.
        with pytest.raises(AttributeError):
            compute_stat_avg("total_games", _stats(), 0.65)

    def test_keyword_form_works(self):
        assert compute_stat_avg("total_games", _stats(), win_prob=0.65) > 0


class TestBestOfFiveSpread:
    def test_spread_is_much_wider_than_best_of_three(self):
        # Same distance from the projection, best-of-5 must be less certain.
        bo3 = total_games_probs(BO3_MEAN + 8, BO3_MEAN, 0.35).p_over
        bo5 = total_games_probs(BO5_MEAN + 8, BO5_MEAN, 0.35, best_of=5).p_over
        assert bo5 > bo3

    def test_probabilities_still_partition(self):
        p = total_games_probs(30.5, BO5_MEAN, 0.35, best_of=5)
        assert p.p_over + p.p_under + p.p_push == pytest.approx(1.0)

    def test_the_projection_sits_near_even_money(self):
        assert total_games_probs(BO5_MEAN, BO5_MEAN, 0.35, best_of=5).p_over == pytest.approx(0.5, abs=0.12)

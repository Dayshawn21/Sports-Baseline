"""Computed ELO must be as-of-date by construction.

The scraped `player_elo` table only reaches back to 2026, leaving two thirds of
backfilled matches with no rating. These ratings are rebuilt from results instead, which
means the ordering guarantee matters: a match must never be rated using itself.
"""

import datetime as dt

import pytest

from app.ml.elo_history import BASE_RATING, EloIndex, expected_score, k_factor

D = dt.date

ROWS = [
    (D(2024, 1, 1), 1, 2, 1, "hard"),
    (D(2024, 2, 1), 1, 2, 1, "hard"),
    (D(2024, 3, 1), 1, 2, 1, "clay"),
    (D(2024, 4, 1), 2, 3, 2, "hard"),
]


class TestExpectedScore:
    def test_equal_ratings_are_a_coin_flip(self):
        assert expected_score(1500, 1500) == pytest.approx(0.5)

    def test_a_400_point_lead_is_ten_to_one(self):
        assert expected_score(1900, 1500) == pytest.approx(10 / 11, abs=1e-6)

    def test_expectations_of_both_sides_sum_to_one(self):
        assert expected_score(1650, 1480) + expected_score(1480, 1650) == pytest.approx(1.0)


class TestKFactor:
    def test_new_players_move_faster_than_established_ones(self):
        assert k_factor(0) > k_factor(50) > k_factor(500)

    def test_k_stays_positive_deep_into_a_career(self):
        assert k_factor(2000) > 0


class TestRatings:
    def test_a_player_has_no_rating_before_their_first_match(self):
        assert EloIndex(ROWS).rating(1, D(2024, 1, 1)) is None

    def test_winning_raises_the_rating_above_base(self):
        assert EloIndex(ROWS).rating(1, D(2024, 2, 1)) > BASE_RATING

    def test_losing_lowers_the_rating_below_base(self):
        assert EloIndex(ROWS).rating(2, D(2024, 2, 1)) < BASE_RATING

    def test_repeated_wins_keep_raising_the_rating(self):
        idx = EloIndex(ROWS)
        assert idx.rating(1, D(2024, 3, 1)) > idx.rating(1, D(2024, 2, 1))

    def test_rating_is_unknown_for_an_unseen_player(self):
        assert EloIndex(ROWS).rating(999, D(2025, 1, 1)) is None

    def test_points_lost_by_one_side_are_gained_by_the_other_early_on(self):
        # Equal K only while both have the same number of matches played.
        idx = EloIndex([(D(2024, 1, 1), 1, 2, 1, "hard")])
        gain = idx.rating(1, D(2024, 2, 1)) - BASE_RATING
        loss = BASE_RATING - idx.rating(2, D(2024, 2, 1))
        assert gain == pytest.approx(loss)


class TestSurfaceRatings:
    def test_surface_rating_tracks_only_that_surface(self):
        idx = EloIndex(ROWS)
        # p1 won two hard matches before 2024-03-01 and no clay ones.
        assert idx.surface_rating(1, "hard", D(2024, 3, 1)) > BASE_RATING
        assert idx.surface_rating(1, "clay", D(2024, 3, 1)) is None

    def test_an_unknown_surface_has_no_rating(self):
        assert EloIndex(ROWS).surface_rating(1, "carpet", D(2025, 1, 1)) is None

    def test_a_missing_surface_is_handled(self):
        idx = EloIndex([(D(2024, 1, 1), 1, 2, 1, None)])
        assert idx.surface_rating(1, None, D(2025, 1, 1)) is None
        assert idx.rating(1, D(2025, 1, 1)) is not None


class TestNoLookahead:
    def test_the_match_being_rated_never_affects_its_own_rating(self):
        idx = EloIndex(ROWS)
        # Before the very first match both players are unrated, despite p1 winning it.
        assert idx.rating(1, D(2024, 1, 1)) is None
        assert idx.rating(2, D(2024, 1, 1)) is None

    def test_later_matches_do_not_change_an_earlier_rating(self):
        early = EloIndex(ROWS[:2])
        full = EloIndex(ROWS)
        assert early.rating(1, D(2024, 3, 1)) == pytest.approx(full.rating(1, D(2024, 3, 1)))

    def test_input_order_does_not_matter(self):
        assert EloIndex(list(reversed(ROWS))).rating(1, D(2024, 4, 1)) == pytest.approx(
            EloIndex(ROWS).rating(1, D(2024, 4, 1))
        )

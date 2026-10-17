"""Grand slam qualifying is best-of-3, including the qualifying final.

Two ways this went wrong. The round pattern required a trailing digit, so
"Qualification Final" was not recognised and an ATP slam qualifying final inferred
best-of-5. And nothing looked at the tournament name, which providers often mark
"... Qualifying" while leaving the round empty.

The opposite error matters just as much: a pattern loose enough to catch "QF" would make
main-draw quarterfinals best-of-3.
"""

import pytest

from app.core.tennis_format import (
    infer_best_of,
    is_qualifying_event,
    is_qualifying_round,
)

SLAM = "US Open"
SLAM_QUALIFYING = "US Open, New York, USA, Qualifying"


class TestQualifyingRounds:
    @pytest.mark.parametrize("round_name", [
        "Q", "Q1", "Q2", "Q3", "QR1", "QR 2", "Qual", "Qualifying", "Qualification",
        "Qualification Round 1", "Qualification Round 2",
        "Qualification Final", "Qualifying Final",
    ])
    def test_qualifying_forms_are_recognised(self, round_name):
        assert is_qualifying_round(round_name)

    @pytest.mark.parametrize("round_name", [
        "QF", "Quarterfinal", "Quarterfinals", "SF", "Semifinal", "Semifinals",
        "F", "Final", "R128", "R64", "R32", "R16", "Round of 32", "Round of 16", "RR",
    ])
    def test_main_draw_rounds_are_not_qualifying(self, round_name):
        assert not is_qualifying_round(round_name)

    def test_quarterfinal_is_not_swallowed_by_the_q_prefix(self):
        # A pattern of "Q followed by anything" would break every slam quarterfinal.
        assert not is_qualifying_round("QF")
        assert infer_best_of("ATP", SLAM, "QF", 3) == 5

    def test_an_empty_round_is_not_qualifying_on_its_own(self):
        assert not is_qualifying_round(None)
        assert not is_qualifying_round("")


class TestQualifyingEvents:
    def test_the_tournament_name_marks_qualifying(self):
        assert is_qualifying_event(SLAM_QUALIFYING)

    def test_a_main_draw_name_does_not(self):
        assert not is_qualifying_event(SLAM)
        assert not is_qualifying_event("Winston-Salem")

    def test_it_is_case_insensitive(self):
        assert is_qualifying_event("US OPEN QUALIFYING")


class TestBestOfInference:
    @pytest.mark.parametrize("round_name", ["R128", "R64", "R32", "R16", "QF", "SF", "F"])
    def test_atp_slam_main_draw_is_best_of_five(self, round_name):
        assert infer_best_of("ATP", SLAM, round_name, 3) == 5

    @pytest.mark.parametrize("round_name", ["Q1", "Q2", "Q3", "Qualification Final", None])
    def test_atp_slam_qualifying_stays_best_of_three(self, round_name):
        assert infer_best_of("ATP", SLAM_QUALIFYING, round_name, 3) == 3

    def test_qualifying_event_name_wins_even_with_a_main_draw_round(self):
        # Providers sometimes label qualifying rounds R32/R16 inside a qualifying event.
        assert infer_best_of("ATP", SLAM_QUALIFYING, "R32", 3) == 3

    @pytest.mark.parametrize("round_name", ["R32", "QF", "F", "Q1"])
    def test_wta_is_always_best_of_three(self, round_name):
        assert infer_best_of("WTA", SLAM, round_name, 3) == 3

    def test_non_slam_atp_is_best_of_three(self):
        assert infer_best_of("ATP", "Winston-Salem", "QF", 3) == 3

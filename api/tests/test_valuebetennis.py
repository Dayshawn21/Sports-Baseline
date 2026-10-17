"""Valuebetennis rows parse into typed matches; unusable rows parse to None."""
from datetime import date

import pytest

from app.core.valuebetennis import is_truncated_finish, parse_row, row_problem


def _row(**overrides: str) -> dict[str, str]:
    row = {
        "match_id": "500001",
        "date": "2022-05-03 11:00:00",
        "tournoi": "Mutua Madrid Open - Madrid",
        "tournoi_id": "100",
        "categorie": "Masters",
        "genre": "wta",
        "surface": "terre battue",
        "tour": "5",
        "joueur1": "Player One",
        "joueur1_id": "11",
        "joueur2": "Player Two",
        "joueur2_id": "22",
        "cote1_ouverture": "1.800",
        "cote2_ouverture": "2.050",
        "cote1_cloture": "1.700",
        "cote2_cloture": "2.200",
        "vainqueur_id": "22",
        "score": "4-6 6-3 3-6",
        "duree_min": "130",
    }
    row.update(overrides)
    return row


def test_completed_wta_row():
    match = parse_row(_row())
    assert match is not None
    assert (match.match_id, match.tour, match.category, match.round_code) == (500001, "WTA", "Masters", 5)
    assert (match.match_date, match.season) == (date(2022, 5, 3), 2022)
    assert (match.p1_id, match.p2_id, match.winner_id) == (11, 22, 22)
    assert (match.surface, match.best_of, match.completed, match.truncated) == ("clay", 3, True, False)
    assert (match.p1_open, match.p2_open, match.p1_close, match.p2_close) == (1.8, 2.05, 1.7, 2.2)


def test_atp_grand_slam_main_draw_is_best_of_five():
    match = parse_row(_row(genre="atp", categorie="Grand Chelem", tour="4", score="6-4 3-6 6-3 6-2"))
    assert match is not None
    assert (match.category, match.best_of, match.completed) == ("Grand Slam", 5, True)


def test_atp_grand_slam_qualifying_is_best_of_three():
    match = parse_row(_row(genre="atp", categorie="Grand Chelem", tour="2", score="6-4 6-3"))
    assert match is not None
    assert (match.round_code, match.best_of, match.completed) == (2, 3, True)


def test_wta_grand_slam_main_draw_stays_best_of_three():
    match = parse_row(_row(categorie="Grand Chelem", tour="7", score="6-4 6-3"))
    assert match is not None and match.best_of == 3 and match.completed


def test_tie_break_notation_completes():
    match = parse_row(_row(score="7-6(3) 6-7(5) 7-5"))
    assert match is not None and match.completed and not match.truncated


def test_truncated_five_setter_counts_as_completed():
    score = "7-6(3) 6-7(3) 3-6 7-"
    assert len(score) == 20
    match = parse_row(_row(genre="atp", categorie="Grand Chelem", tour="6", score=score))
    assert match is not None and match.completed and match.truncated


def test_truncated_score_with_unfinished_set_before_cut_is_not_completed():
    assert not is_truncated_finish("6-3 4-2 6-7(3) 6-4 6")
    assert not is_truncated_finish("1-6 ret. (Govortsova")


def test_short_score_is_never_truncated():
    assert not is_truncated_finish("6-4 3-6 6-3 2-")


def test_naturally_complete_twenty_character_score_is_not_flagged_truncated():
    score = "7-6(5) 6-7(5) 7-6(5)"
    assert len(score) == 20 and is_truncated_finish(score)
    match = parse_row(_row(score=score))
    assert match is not None and match.completed and not match.truncated


@pytest.mark.parametrize("score", ["6-3 3-1", "4-6 4-5", "5-0 ret.", ""])
def test_retirement_and_walkover_are_not_completed(score):
    match = parse_row(_row(score=score))
    assert match is not None and not match.completed and not match.truncated


def test_walkover_score_is_none():
    match = parse_row(_row(score=""))
    assert match is not None and match.score is None


@pytest.mark.parametrize("value", ["", "abc", "1.0", "0.95", "-2"])
def test_unusable_odds_become_none(value):
    match = parse_row(_row(cote1_cloture=value, cote2_ouverture=value))
    assert match is not None
    assert match.p1_close is None and match.p2_open is None
    assert match.p2_close == 2.2 and match.p1_open == 1.8


@pytest.mark.parametrize(
    "surface, expected",
    [("dur", "hard"), ("dur intérieur", "hard"), ("terre battue", "clay"), ("gazon", "grass"),
     ("moquette intérieur", None), ("", None)],
)
def test_surface_mapping(surface, expected):
    match = parse_row(_row(surface=surface))
    assert match is not None and match.surface == expected


def test_unreadable_round_code_counts_as_qualifying():
    match = parse_row(_row(genre="atp", categorie="Grand Chelem", tour="", score="6-4 6-3"))
    assert match is not None and match.round_code == 0 and match.best_of == 3


@pytest.mark.parametrize(
    "overrides, reason",
    [
        ({"joueur1_id": ""}, "no_players"),
        ({"joueur2_id": "x"}, "no_players"),
        ({"vainqueur_id": ""}, "winner_not_a_player"),
        ({"vainqueur_id": "33"}, "winner_not_a_player"),
        ({"date": ""}, "no_date"),
        ({"date": "not a date"}, "no_date"),
        ({"match_id": ""}, "no_match_id"),
        ({"genre": "mixed"}, "unknown_tour"),
    ],
)
def test_unusable_rows_parse_to_none_with_a_reason(overrides, reason):
    row = _row(**overrides)
    assert parse_row(row) is None
    assert row_problem(row) == reason


def test_usable_row_has_no_problem():
    assert row_problem(_row()) is None

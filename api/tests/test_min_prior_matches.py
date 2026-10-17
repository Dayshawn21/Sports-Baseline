"""The ELO reliability rule reads the thinner of the two players' histories."""

import datetime as dt
from types import SimpleNamespace

from app.ml.asof_features import HistoryIndex
from app.services.tennis.history_cache import min_prior_matches

D = dt.date

# Columns: (match_date, p1_id, p2_id, winner_id, surface)
ROWS = [
    (D(2024, 1, 1), 1, 2, 1, "hard"),
    (D(2024, 2, 1), 1, 3, 1, "hard"),
    (D(2024, 3, 1), 1, 3, 3, "clay"),
]


def _match(p1_id: int, p2_id: int, on: dt.date) -> SimpleNamespace:
    return SimpleNamespace(p1_id=p1_id, p2_id=p2_id, match_date=on)


def test_the_player_with_fewer_matches_sets_the_count():
    assert min_prior_matches(HistoryIndex(ROWS), _match(1, 2, D(2024, 6, 1))) == 1


def test_order_of_the_players_does_not_matter():
    idx = HistoryIndex(ROWS)
    assert min_prior_matches(idx, _match(2, 1, D(2024, 6, 1))) == 1


def test_only_matches_before_the_match_date_count():
    assert min_prior_matches(HistoryIndex(ROWS), _match(1, 3, D(2024, 3, 1))) == 1


def test_a_player_with_no_history_counts_zero():
    assert min_prior_matches(HistoryIndex(ROWS), _match(1, 99, D(2024, 6, 1))) == 0

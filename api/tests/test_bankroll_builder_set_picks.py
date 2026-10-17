from datetime import datetime

import pytest

from app.core.tennis_sets import set_outcomes
from app.services.tennis.bankroll_builder import _generate_set_picks
from app.services.tennis.predictor import PredictionOutput


def _prediction(
    best_of: int,
    p1_win_prob: float = 0.22,
    p1_odds_american: int = 190,
    p2_odds_american: int = -238,
) -> PredictionOutput:
    return PredictionOutput(
        match_id=99,
        start_utc=datetime(2026, 8, 30, 19, 30, 0),
        p1_name="Jeffrey Wolf",
        p2_name="Alexander Bublik",
        tour="ATP",
        surface="Hard",
        tournament="US Open",
        round="R128",
        p1_win_prob=p1_win_prob,
        p2_win_prob=1 - p1_win_prob,
        p1_elo_prob=0.24,
        p1_ml_prob=0.25,
        p1_market_prob=0.33,
        ensemble_weights={"elo": 0.35, "ml": 0.40, "market": 0.25},
        quality_flags=[],
        p1_odds_american=p1_odds_american,
        p2_odds_american=p2_odds_american,
        h2h_p1_wins=0,
        h2h_p2_wins=0,
        best_of=best_of,
    )


def test_best_of_five_uses_three_nil_straight_sets() -> None:
    picks = _generate_set_picks(_prediction(best_of=5, p1_win_prob=0.15), {})

    straight = next(p for p in picks if p.bet_type == "3-0")
    assert straight.pick_label.startswith("Bublik 3-0")
    assert straight.our_prob == pytest.approx(0.85 ** 3, abs=0.0001)
    assert all(p.bet_type != "2-0" for p in picks)


def test_best_of_three_still_uses_two_nil_straight_sets() -> None:
    picks = _generate_set_picks(_prediction(best_of=3), {})

    straight = next(p for p in picks if p.bet_type == "2-0")
    assert straight.pick_label.startswith("Bublik 2-0")
    # Fitted set outcomes, not 0.78 ** 2: sets are correlated (see app/core/tennis_sets.py).
    assert straight.our_prob == pytest.approx(set_outcomes(0.78).favorite_straight, abs=0.0001)
    assert all(p.bet_type != "3-0" for p in picks)


def test_best_of_five_underdog_set_cover_uses_two_and_a_half_sets() -> None:
    picks = _generate_set_picks(
        _prediction(
            best_of=5,
            p1_win_prob=0.30,
            p1_odds_american=400,
            p2_odds_american=-700,
        ),
        {},
    )

    dog_cover = next(p for p in picks if p.bet_type == "underdog_set")
    assert dog_cover.pick_label.startswith("Wolf +2.5 Sets")
    assert dog_cover.our_prob == pytest.approx(1 - 0.70 ** 3, abs=0.0001)

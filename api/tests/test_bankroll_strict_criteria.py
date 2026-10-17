from types import SimpleNamespace

from app.services.tennis.bankroll_builder import _generate_ml_picks


def _pred(**overrides):
    data = {
        "match_id": 1,
        "start_utc": None,
        "p1_name": "Player One",
        "p2_name": "Player Two",
        "tour": "ATP",
        "surface": "Hard",
        "tournament": "Test",
        "round": "R32",
        "best_of": 3,
        "p1_win_prob": 0.61,
        "p2_win_prob": 0.39,
        "p1_odds_american": 110,
        "p2_odds_american": -130,
        "quality_flags": [],
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_bankroll_ml_hides_below_five_percent_ev():
    picks = _generate_ml_picks(
        _pred(
            p1_win_prob=0.55,
            p2_win_prob=0.45,
            p1_odds_american=-130,
            p2_odds_american=110,
        )
    )

    assert picks == []


def test_bankroll_ml_does_not_strong_from_probability_bump():
    picks = _generate_ml_picks(
        _pred(
            p1_win_prob=0.58,
            p2_win_prob=0.42,
            p1_odds_american=120,
            p2_odds_american=-145,
        )
    )

    assert picks
    assert picks[0].confidence == "LEAN"

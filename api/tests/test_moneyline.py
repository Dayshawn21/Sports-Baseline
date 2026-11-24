from types import SimpleNamespace

import pytest

from app.services.tennis.moneyline import MoneylineSide, moneyline_sides, odds_str


def _pred(**overrides) -> SimpleNamespace:
    data = {
        "p1_name": "Jannik Sinner",
        "p2_name": "Carlos Alcaraz",
        "p1_win_prob": 0.60,
        "p2_win_prob": 0.40,
        "p1_odds_american": -150,
        "p2_odds_american": 150,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_sides_carry_model_and_devigged_market_numbers() -> None:
    p1, p2 = moneyline_sides(_pred())
    # -150 is 0.6 raw and +150 is 0.4 raw, so the pair is already vig-free.
    assert p1 == MoneylineSide(
        side="p1", name="Jannik Sinner", our_prob=0.60, market_prob=pytest.approx(0.6),
        odds=-150, ev=pytest.approx(0.0), kelly=0.0,
    )
    assert p2.side == "p2"
    assert p2.name == "Carlos Alcaraz"
    assert p2.market_prob == pytest.approx(0.4)
    assert p2.odds == 150


def test_market_probs_are_devigged_to_sum_to_one() -> None:
    p1, p2 = moneyline_sides(_pred(p1_odds_american=-110, p2_odds_american=-110))
    assert p1.market_prob == pytest.approx(0.5)
    assert p1.market_prob + p2.market_prob == pytest.approx(1.0)


def test_positive_ev_side_has_kelly_stake() -> None:
    p1, _ = moneyline_sides(_pred(p1_win_prob=0.62, p2_win_prob=0.38, p1_odds_american=120, p2_odds_american=-145))
    assert p1.ev == pytest.approx(0.364)
    assert p1.kelly > 0


@pytest.mark.parametrize(
    "missing",
    [{"p1_win_prob": None}, {"p1_odds_american": None}, {"p2_odds_american": None}],
)
def test_missing_probability_or_price_returns_none(missing: dict) -> None:
    assert moneyline_sides(_pred(**missing)) is None


@pytest.mark.parametrize(("odds", "text"), [(120, "+120"), (-130, "-130"), (0, "0"), (None, "N/A")])
def test_odds_str(odds: int | None, text: str) -> None:
    assert odds_str(odds) == text

"""The per-side moneyline numbers that best picks and the bankroll builder both start from."""
from __future__ import annotations

from dataclasses import dataclass

from app.core.kelly import expected_value, kelly_fraction
from app.core.odds import american_to_prob, devig_two_way
from app.services.tennis.predictor import PredictionOutput


@dataclass(frozen=True)
class MoneylineSide:
    side: str
    name: str
    our_prob: float
    market_prob: float
    odds: int
    ev: float
    kelly: float


def moneyline_sides(pred: PredictionOutput) -> tuple[MoneylineSide, MoneylineSide] | None:
    """Both sides' model and de-vigged market probability, EV and Kelly, or None without a price."""
    if pred.p1_win_prob is None or pred.p1_odds_american is None or pred.p2_odds_american is None:
        return None

    market_p1, market_p2 = devig_two_way(
        american_to_prob(pred.p1_odds_american),
        american_to_prob(pred.p2_odds_american),
    )
    p1, p2 = (
        MoneylineSide(
            side=side,
            name=name,
            our_prob=prob,
            market_prob=market,
            odds=odds,
            ev=expected_value(prob, odds),
            kelly=kelly_fraction(prob, odds),
        )
        for side, name, prob, market, odds in (
            ("p1", pred.p1_name, pred.p1_win_prob, market_p1, pred.p1_odds_american),
            ("p2", pred.p2_name, pred.p2_win_prob, market_p2, pred.p2_odds_american),
        )
    )
    return p1, p2


def odds_str(odds: int | None) -> str:
    if odds is None:
        return "N/A"
    return f"+{odds}" if odds > 0 else str(odds)

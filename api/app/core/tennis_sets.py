"""Best-of-3 set-count probabilities from a match win probability.

Fitted on 2026-09-25 against de-vigged pre-start moneylines: 3,276 completed
best-of-3 matches (2026-03-12..05-18) for the fit, 1,404 later ones (05-18..09-25)
held out. The textbook 2p(1-p) for a deciding set scored worse on the holdout
than a constant base rate, and treating sets as independent (p = s^2(3-2s))
doubled that error, because a set winner is more likely to win the next set.

Holdout log loss, fitted vs current: 3 sets 0.638 vs 0.651, favorite 2-0
0.664 vs 0.666. Best-of-5 has no fit and keeps its callers' existing inputs.

Total games still weights its set-count mixture with 2p(1-p): the stored book
total lines it would be validated against were found unreliable on 2026-09-25.
"""
from __future__ import annotations

from dataclasses import dataclass

_THREE_SET_INTERCEPT = 0.1168
_THREE_SET_SLOPE = 0.5813
# The favorite's share of the matches that go three sets.
_FAV_THREE_SET_SHARE_INTERCEPT = 0.0461
_FAV_THREE_SET_SHARE_SLOPE = 0.8580


@dataclass(frozen=True)
class SetOutcomes:
    """Best-of-3 outcomes for the favorite (the side with win prob >= 0.5)."""

    favorite_straight: float
    underdog_straight: float
    three_sets: float


def _clamped(win_prob: float) -> float:
    return min(max(float(win_prob), 0.01), 0.99)


def three_set_probability(win_prob: float) -> float:
    """Chance a best-of-3 match goes the distance. Symmetric in which side is p1."""
    p = _clamped(win_prob)
    return _THREE_SET_INTERCEPT + _THREE_SET_SLOPE * 2.0 * p * (1.0 - p)


def set_outcomes(win_prob: float) -> SetOutcomes:
    """Favorite 2-0, underdog 2-0, and 3 sets, summing to 1.

    Each straight-sets outcome is its side's win probability less its share of
    the three-setters, so the three can never disagree with the match odds. Near
    certainty the underdog's share would dip a hair below zero; that mass moves
    to the favorite rather than being dropped.
    """
    fav = max(_clamped(win_prob), 1.0 - _clamped(win_prob))
    three = three_set_probability(fav)
    share = min(max(_FAV_THREE_SET_SHARE_INTERCEPT + _FAV_THREE_SET_SHARE_SLOPE * fav, 0.0), 1.0)
    underdog_straight = max((1.0 - fav) - (1.0 - share) * three, 0.0)
    favorite_straight = 1.0 - three - underdog_straight
    return SetOutcomes(favorite_straight, underdog_straight, three)


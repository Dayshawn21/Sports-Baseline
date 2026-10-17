"""Kelly Criterion bet sizing."""


DEFAULT_KELLY_MULTIPLIER = 0.25


def kelly_fraction(
    prob: float,
    odds_american: int,
    max_fraction: float = 0.25,
    multiplier: float = DEFAULT_KELLY_MULTIPLIER,
) -> float:
    """
    Calculate fractional Kelly bet size.

    Full Kelly assumes `prob` is the true probability. Ours is a model estimate, and
    overestimating edge compounds into ruin far faster than underestimating it costs,
    so the raw stake is scaled by `multiplier` (quarter Kelly) before the cap applies.

    Args:
        prob: Our estimated win probability (0-1).
        odds_american: American odds for the bet (e.g. -110, +150).
        max_fraction: Hard ceiling on the returned fraction (default 25%).
        multiplier: Fraction of full Kelly to stake (default 0.25).

    Returns:
        Fraction of bankroll to bet (0 = no bet).
    """
    if odds_american >= 0:
        b = odds_american / 100.0
    else:
        b = 100.0 / abs(odds_american)

    q = 1.0 - prob
    k = (b * prob - q) / b
    return max(0.0, min(k * multiplier, max_fraction))


def expected_value(prob: float, odds_american: int) -> float:
    """
    Calculate edge as a fraction of stake.

    Returns:
        EV per unit staked (e.g. 0.05 = 5% edge).
    """
    if odds_american >= 0:
        payout = odds_american / 100.0
    else:
        payout = 100.0 / abs(odds_american)

    return prob * payout - (1.0 - prob)

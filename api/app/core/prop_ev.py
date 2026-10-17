"""Expected-value model for props.

The confidence tier used to be a pure probability threshold, which measured how
*likely* a pick was and ignored how much it *paid*. On PrizePicks that is close
to backwards: goblins shade the line down so they hit almost always and pay
little, demons shade it up so they rarely hit and pay a lot. Tiering on raw
probability graded 36.7% of goblins as LOCK and 0.6% of demons, i.e. it was
effectively ranking picks by how little they returned.

Everything here works in expected value instead: a pick is good when the model's
hit probability clears the break-even probability its price implies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# ── Payout model ──────────────────────────────────────────────────────────────
# PrizePicks does not publish per-leg multipliers in its payload (only
# `odds_type` and an `adjusted_odds` flag), so the structure is encoded here.
# These are per-leg decimal payouts on a 2-pick power play basis: two standard
# legs at 1.732 compound to the familiar 3x. Retune these three numbers and the
# tiers, EV and ranking all follow — no other code needs to change.
STANDARD_LEG_DECIMAL = 1.732
GOBLIN_LEG_DECIMAL = 1.32
DEMON_LEG_DECIMAL = 2.42

# Sportsbook props carry real American odds, so they never need the table above.
_TIER_DECIMALS: dict[str, float] = {
    "standard": STANDARD_LEG_DECIMAL,
    "goblin": GOBLIN_LEG_DECIMAL,
    "demon": DEMON_LEG_DECIMAL,
}

# EV thresholds for the confidence tiers. EV is a return fraction: +0.15 means
# the pick returns 15% of the stake on average.
LOCK_EV = 0.15
STRONG_EV = 0.10
LEAN_EV = 0.05

# A pick with a big EV but a coin-flip hit rate is a different animal from a
# reliable one. Require a floor on raw probability before awarding the top tier
# so a single high-variance demon cannot outrank a solid standard pick.
LOCK_MIN_PROBABILITY = 0.68
STRONG_MIN_PROBABILITY = 0.60
LEAN_MIN_PROBABILITY = 0.55


@dataclass(frozen=True)
class PropEV:
    """EV assessment of one prop at one price."""

    decimal_odds: float
    break_even_probability: float
    probability: float
    ev: float
    """Expected return per unit staked: probability * decimal_odds - 1."""
    confidence: Optional[str]

    @property
    def ev_pct(self) -> float:
        return round(self.ev * 100.0, 1)

    @property
    def edge_over_break_even(self) -> float:
        """Percentage points of probability above what the price requires."""
        return round((self.probability - self.break_even_probability) * 100.0, 1)


def american_to_decimal(odds: float) -> float:
    """Convert American odds to decimal (total return per unit staked)."""
    if odds >= 0:
        return 1.0 + odds / 100.0
    return 1.0 + 100.0 / abs(odds)


def leg_decimal_odds(
    odds_type: Optional[str],
    american_odds: Optional[float] = None,
    source: Optional[str] = None,
) -> Optional[float]:
    """Decimal payout for one prop leg.

    Real American odds win when present. Otherwise the PrizePicks tier table
    applies — but only for PrizePicks, since assuming a 1.73x leg for a
    sportsbook line would invent a price we were never given. Returns None when
    the price is unknown so callers decline to grade rather than guess.
    """
    if american_odds is not None:
        return american_to_decimal(float(american_odds))

    key = (odds_type or "").strip().lower()
    if key in _TIER_DECIMALS:
        return _TIER_DECIMALS[key]
    # An unmarked PrizePicks projection is a standard one; an unpriced prop from
    # anywhere else is simply unknown.
    if key in ("", "none", "null") and (source or "").strip().lower() == "prizepicks":
        return STANDARD_LEG_DECIMAL
    return None


def break_even_probability(decimal_odds: float) -> float:
    """Hit rate at which a price is exactly break-even."""
    if decimal_odds <= 0:
        return 1.0
    return 1.0 / decimal_odds


def ev_confidence_tier(ev: float, probability: float) -> str:
    """Grade a pick on expected value, gated by a minimum hit probability."""
    if ev >= LOCK_EV and probability >= LOCK_MIN_PROBABILITY:
        return "LOCK"
    if ev >= STRONG_EV and probability >= STRONG_MIN_PROBABILITY:
        return "STRONG"
    if ev >= LEAN_EV and probability >= LEAN_MIN_PROBABILITY:
        return "LEAN"
    return "PASS"


def assess_prop(
    probability: float,
    odds_type: Optional[str] = None,
    american_odds: Optional[float] = None,
    source: Optional[str] = None,
) -> Optional[PropEV]:
    """Grade one prop. Returns None when the price is unknown."""
    decimal = leg_decimal_odds(odds_type, american_odds, source)
    if decimal is None:
        return None

    p = max(0.0, min(1.0, float(probability)))
    ev = p * decimal - 1.0
    return PropEV(
        decimal_odds=decimal,
        break_even_probability=break_even_probability(decimal),
        probability=p,
        ev=ev,
        confidence=ev_confidence_tier(ev, p),
    )

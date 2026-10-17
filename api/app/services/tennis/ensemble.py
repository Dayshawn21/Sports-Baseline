"""
Pure ensemble blending: ELO + LightGBM + Market → final probability.
No DB calls, no model loading — pure math.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.core.tennis_market_blend import market_anchored_prob
from app.core.tennis_market_blend_fit import FIT_COEFFICIENTS

# v3 serves the 26d market-anchored blend; regenerating its coefficients is a new version.
ENSEMBLE_VERSION = "ensemble-v3"


@dataclass
class EnsembleInput:
    tour: str
    elo_prob: Optional[float] = None          # from TennisAbstract ELO
    ml_prob: Optional[float] = None           # from LightGBM
    market_prob: Optional[float] = None       # no-vig implied probability
    elo_fallback: bool = False                # True = ELO used median fallback
    ml_features_partial: bool = False         # True = key feature groups missing
    market_stale: bool = False                # True = odds older than threshold
    market_high_overround: bool = False       # True = overround > 8%
    elo_unreliable: bool = False              # True = ELO present but not trusted


@dataclass
class EnsembleResult:
    p1_win_prob: float
    p2_win_prob: float
    elo_prob: Optional[float]
    ml_prob: Optional[float]
    market_prob: Optional[float]
    weights: dict[str, float]
    quality_flags: list[str] = field(default_factory=list)


# Tour-specific base weights: ATP market is tighter/more efficient; WTA has more model signal
_TOUR_BASE_WEIGHTS: dict[str, dict[str, float]] = {
    "ATP": {"elo": 0.35, "ml": 0.40, "market": 0.25},
    "WTA": {"elo": 0.40, "ml": 0.45, "market": 0.15},
}
_BASE_WEIGHTS = {"elo": 0.40, "ml": 0.40, "market": 0.20}  # fallback for non-ATP/WTA

# Fixed from graded ensemble-v1 predictions (2026-09-28): ELO scored about 3x worse
# against the market when either player had under 10 prior matches, and at a 15+ point
# disagreement the market's side won as often as the market said.
ELO_MAX_MARKET_GAP = 0.15
ELO_MIN_PRIOR_MATCHES = 10


def elo_is_unreliable(
    elo_prob: Optional[float],
    market_prob: Optional[float],
    min_prior_matches: Optional[int],
) -> bool:
    if elo_prob is None:
        return False
    if min_prior_matches is not None and min_prior_matches < ELO_MIN_PRIOR_MATCHES:
        return True
    return market_prob is not None and abs(elo_prob - market_prob) >= ELO_MAX_MARKET_GAP


def blend(inp: EnsembleInput) -> Optional[EnsembleResult]:
    """The served ensemble: the 26d fitted blend when a market price exists, else hand-set."""
    if inp.market_prob is not None:
        return _market_anchored(inp)
    return hand_set_blend(inp)


def hand_set_blend(inp: EnsembleInput) -> Optional[EnsembleResult]:
    """
    Blend ELO, ML, and market probabilities with quality-aware weights.
    Returns None if no probability sources are available. ensemble-v2's whole model,
    kept so 26c and 26d stay reproducible against it.
    """
    base = _TOUR_BASE_WEIGHTS.get((inp.tour or "").upper(), _BASE_WEIGHTS)
    flags: list[str] = []
    components: dict[str, float] = {}

    # ── ELO ──────────────────────────────────────────────────────────────────
    # Without a usable ELO its weight goes to the market rather than being spread onto
    # ML, which grades weaker than the market (26a).
    elo_to_market = 0.0
    if inp.elo_prob is None:
        flags.append("elo_missing")
        elo_to_market = base["elo"]
    elif inp.elo_unreliable:
        flags.append("elo_unreliable")
        elo_to_market = base["elo"]
    else:
        mult = 0.7 if inp.elo_fallback else 1.0
        if inp.elo_fallback:
            flags.append("elo_fallback_used")
        components["elo"] = base["elo"] * mult

    # ── ML (LightGBM) ─────────────────────────────────────────────────────────
    if inp.ml_prob is not None:
        # Flagged for the admin stats queue, but no weight penalty: it tracks missing
        # TennisAbstract rolling stats, and the served v6 model uses none of them.
        if inp.ml_features_partial:
            flags.append("ml_features_partial")
        components["ml"] = base["ml"]
    else:
        flags.append("ml_missing")

    # ── Market ────────────────────────────────────────────────────────────────
    if inp.market_prob is not None:
        if inp.market_stale:
            mult = 0.5
            flags.append("stale_odds")
        elif inp.market_high_overround:
            mult = 0.75
            flags.append("high_overround")
        else:
            mult = 1.0
        components["market"] = (base["market"] + elo_to_market) * mult
    else:
        flags.append("market_missing")

    if not components:
        return None

    # ── Normalize weights ─────────────────────────────────────────────────────
    total_weight = sum(components.values())
    norm_weights = {k: v / total_weight for k, v in components.items()}

    # ── Weighted blend ────────────────────────────────────────────────────────
    probs = {"elo": inp.elo_prob, "ml": inp.ml_prob, "market": inp.market_prob}
    p1 = sum(norm_weights[k] * probs[k] for k in norm_weights)  # type: ignore[operator]
    p1 = float(max(0.01, min(0.99, p1)))

    return EnsembleResult(
        p1_win_prob=p1,
        p2_win_prob=round(1.0 - p1, 4),
        elo_prob=inp.elo_prob,
        ml_prob=inp.ml_prob,
        market_prob=inp.market_prob,
        weights=norm_weights,
        quality_flags=flags,
    )


def fitted_group(tour: str) -> str:
    """The 26d fit group: Challenger and WTA 125 matches arrive as neither ATP nor WTA."""
    key = (tour or "").upper()
    return key if key in ("ATP", "WTA") else "CHALLENGER"


def _market_anchored(inp: EnsembleInput) -> EnsembleResult:
    """26d: the close-anchored log-odds blend. v6 gets no weight (26d D1); a missing,
    gated or median-fallback ELO leaves the market alone. Stale and overround flags
    still lower a pick's confidence, but no longer move the probability."""
    flags: list[str] = []
    elo: Optional[float] = None
    if inp.elo_prob is None:
        flags.append("elo_missing")
    elif inp.elo_unreliable:
        flags.append("elo_unreliable")
    elif inp.elo_fallback:
        flags.append("elo_fallback_used")
    else:
        elo = inp.elo_prob
    if inp.ml_prob is None:
        flags.append("ml_missing")
    elif inp.ml_features_partial:
        flags.append("ml_features_partial")
    if inp.market_stale:
        flags.append("stale_odds")
    elif inp.market_high_overround:
        flags.append("high_overround")

    coefs = FIT_COEFFICIENTS[fitted_group(inp.tour)]
    p1 = market_anchored_prob(coefs, inp.market_prob, elo)  # type: ignore[arg-type]
    p1 = float(max(0.01, min(0.99, p1)))
    return EnsembleResult(
        p1_win_prob=p1,
        p2_win_prob=round(1.0 - p1, 4),
        elo_prob=inp.elo_prob,
        ml_prob=inp.ml_prob,
        market_prob=inp.market_prob,
        weights={"market": coefs.market, "elo": coefs.elo} if elo is not None else {"market": 1.0},
        quality_flags=flags,
    )

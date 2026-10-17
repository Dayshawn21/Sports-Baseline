from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional


MIN_EV = 0.05
MIN_IMPUTED_EV = 0.10
MIN_IMPUTED_KELLY = 0.02

_RANKS = {"LEAN": 1, "STRONG": 2, "LOCK": 3}
_CONF_BY_RANK = {value: key for key, value in _RANKS.items()}
# Names must match what the ensemble and feature builder emit; a name nothing emits
# silently disables its downgrade.
_DOWNGRADE_FLAGS = {
    "small_sample",
    "stale_stats",
    "stale_odds",
    "market_stale",
    "fallback_stats",
    "market_missing",
    "ml_missing",
    "ml_not_trained_for_tour",
    "elo_missing",
    "p1_elo_missing",
    "p2_elo_missing",
}
# The ensemble has already dropped the input these name, but its disagreement with the
# market marks the whole prediction as untrustworthy, so no tier is safe to show.
_BLOCKING_FLAGS = {"elo_unreliable"}


@dataclass(frozen=True)
class BettableAssessment:
    confidence: str
    data_quality_flags: tuple[str, ...]
    odds_source: str
    downgraded: bool = False


def _base_confidence(model_prob: float, ev: float, kelly_fraction: float) -> Optional[str]:
    if model_prob >= 0.68 and ev >= 0.15 and kelly_fraction >= 0.03:
        return "LOCK"
    if model_prob >= 0.60 and ev >= 0.10 and kelly_fraction >= 0.02:
        return "STRONG"
    if model_prob >= 0.55 and ev >= MIN_EV:
        return "LEAN"
    return None


def _downgrade(confidence: str) -> str:
    return _CONF_BY_RANK[max(_RANKS[confidence] - 1, 1)]


def assess_bettable_pick(
    model_prob: float | None,
    ev: float | None,
    kelly_fraction: float | None,
    data_quality_flags: Iterable[str] = (),
    odds_source: str = "posted",
) -> BettableAssessment | None:
    if model_prob is None or ev is None or kelly_fraction is None:
        return None
    if ev < MIN_EV:
        return None
    if _BLOCKING_FLAGS.intersection(data_quality_flags):
        return None

    normalized_odds_source = odds_source if odds_source in {"posted", "imputed"} else "posted"
    if (
        normalized_odds_source == "imputed"
        and (ev < MIN_IMPUTED_EV or kelly_fraction < MIN_IMPUTED_KELLY)
    ):
        return None

    confidence = _base_confidence(model_prob, ev, kelly_fraction)
    if confidence is None:
        return None

    flags = set(data_quality_flags)
    if normalized_odds_source == "imputed":
        flags.add("imputed_odds")

    downgraded = False
    if normalized_odds_source == "imputed" and confidence == "LOCK":
        confidence = "STRONG"
        downgraded = True

    if flags.intersection(_DOWNGRADE_FLAGS) and confidence != "LEAN":
        confidence = _downgrade(confidence)
        downgraded = True

    return BettableAssessment(
        confidence=confidence,
        data_quality_flags=tuple(sorted(flags)),
        odds_source=normalized_odds_source,
        downgraded=downgraded,
    )

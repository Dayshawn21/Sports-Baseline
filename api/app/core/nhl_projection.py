"""The served NHL prop projection (item 56c1): one line from a player's prior games.

The board and game pages serve it and 56c4 freezes it, so both read one function.
The value is 56b's pre-registered reference arm, imported rather than rewritten so
the served number cannot drift from what was backtested. Pure: no DB, no I/O, no
clock; the caller passes the prior games.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Literal

from app.core import nhl_over_probability_fit as fit
from app.core.count_over_probability import NegBinParams, ScaledNormalParams
from app.core.nhl_context_snapshots import Freshness
from app.core.nhl_over_probability_crossfit import FamilyParams, RatioParams, read_family
from app.core.nhl_player_values import GOALIE_MARKETS, nhl_stat_value
from app.core.nhl_projection_backtest import (
    ARMS, CENTER_ONLY_MARKETS, CENTER_POSITION, MIN_PRIOR_GAMES, MIN_PRIOR_GOALIE_STARTS, MIN_PRIOR_TOI_MINUTES,
    NHL_PROJECTION_REFERENCE_VERSION, REFERENCE_ARM, REFERENCE_GAMES, NhlHistoryRow, prior_toi_minutes,
)
from app.nhl.markets import NhlLineOnlyMarket

NhlProjectionFlag = Literal[
    "few_prior_games", "low_toi", "not_center",
    "no_goalie_report", "starter_unconfirmed", "other_starter_expected", "context_stale", "injured_out",
    "injury_listed", "injury_context_stale", "integer_line", "no_over_probability",
]

# The statuses ESPN stored in nhl_player_injuries on 2026-11-04. Each means the player will not dress.
OUT_INJURY_STATUSES = frozenset({"Out", "Injured Reserve", "Suspension"})
SERVED_GOALIE_STATUSES = frozenset({"confirmed", "expected"})


@dataclass(frozen=True)
class GoalieAvailability:
    """The game's ESPN probable-goalie report for the line player's team."""

    status: str
    freshness: Freshness
    # The goalie ESPN lists for the team; None when unlisted or not linked to a stored player.
    listed_player_id: int | None


@dataclass(frozen=True)
class Availability:
    """What the stored pre-game context says about whether the line player plays; absent context is the default."""

    goalie: GoalieAvailability | None = None
    # The player's own stored injury entry status, None when the snapshot lists no entry for him.
    injury_status: str | None = None
    injury_freshness: Freshness = "unavailable"


@dataclass(frozen=True)
class NhlLineProjection:
    model_version: str
    # None when no number is served; never zero for "unknown".
    projection: float | None
    games_in_sample: int
    prior_toi_minutes: float | None
    gap: float | None
    flags: tuple[NhlProjectionFlag, ...]
    # Set only where a number is shown, the market is in the served fit and the line is not a whole number.
    p_over: float | None = None
    p_under: float | None = None
    # Names the fit that covers this market whenever a number is shown, even when this line reads no probability.
    over_probability_version: str | None = None


@dataclass(frozen=True)
class OverRead:
    p_over: float | None = None
    p_under: float | None = None
    over_probability_version: str | None = None
    flags: tuple[NhlProjectionFlag, ...] = ()


def _fit_serves(market: NhlLineOnlyMarket) -> bool:
    # A fit made for another projection version would misread this projection's values.
    return market.value in fit.SHOWN_MARKETS and fit.FIT_PROJECTION_MODEL_VERSION == NHL_PROJECTION_REFERENCE_VERSION


def served_over_probability_version() -> str | None:
    """The fit's version when it matches the served projection; None when nothing is served from it."""
    return fit.OVER_PROBABILITY_VERSION if fit.FIT_PROJECTION_MODEL_VERSION == NHL_PROJECTION_REFERENCE_VERSION else None


def _fit_params(market: NhlLineOnlyMarket) -> FamilyParams | None:
    family = fit.FAMILY_BY_MARKET.get(market.value)
    if family == "negbin" and market.value in fit.NEGBIN_R:
        return NegBinParams(fit.NEGBIN_R[market.value])
    if family == "scaled_normal" and market.value in fit.SCALED_NORMAL:
        return ScaledNormalParams(*fit.SCALED_NORMAL[market.value])
    if family == "ratio" and market.value in fit.RATIO_QUANTILES:
        return RatioParams(fit.RATIO_QUANTILES[market.value])
    return None


def over_read(market: NhlLineOnlyMarket, projection: float, line: float) -> OverRead:
    """P(over) for a shown projection at one line, read by 56c2's own reader from the frozen fit.

    A hidden market reads nothing and says nothing. No push is modelled, so a whole-number line
    reads no probability and P(under) is the complement on every other line.
    """
    if not _fit_serves(market):
        return OverRead()
    version = fit.OVER_PROBABILITY_VERSION
    if float(line).is_integer():
        return OverRead(over_probability_version=version, flags=("integer_line",))
    params = _fit_params(market)
    probability = None if params is None else read_family(params, projection, line)
    if probability is None:
        return OverRead(over_probability_version=version, flags=("no_over_probability",))
    return OverRead(probability, 1.0 - probability, version)


def _not_served(sample: int, minutes: float | None, flag: NhlProjectionFlag) -> NhlLineProjection:
    return NhlLineProjection(
        model_version=NHL_PROJECTION_REFERENCE_VERSION, projection=None, games_in_sample=sample,
        prior_toi_minutes=minutes, gap=None, flags=(flag,),
    )


def _goalie_block(availability: GoalieAvailability | None, player_id: int) -> NhlProjectionFlag | None:
    if (
        availability is None or availability.freshness == "unavailable"
        or availability.status in {"unavailable", "not_reported"}
    ):
        return "no_goalie_report"
    if availability.freshness == "stale":
        return "context_stale"
    if availability.status not in SERVED_GOALIE_STATUSES or availability.listed_player_id is None:
        return "starter_unconfirmed"
    return None if availability.listed_player_id == player_id else "other_starter_expected"


def _skater_flags(availability: Availability) -> tuple[NhlProjectionFlag, ...]:
    flags: list[NhlProjectionFlag] = []
    if availability.injury_status is not None:
        flags.append("injury_listed")
    if availability.injury_freshness == "stale":
        flags.append("injury_context_stale")
    return tuple(flags)


def project_line(
    prior: Sequence[NhlHistoryRow], market: NhlLineOnlyMarket, line: float, position: str | None,
    player_id: int, availability: Availability,
) -> NhlLineProjection:
    """The gated reference projection for one line, with P(over) wherever a number is shown."""
    gated = _gated_projection(prior, market, line, position, player_id, availability)
    if gated.projection is None:
        return gated
    read = over_read(market, gated.projection, line)
    return replace(
        gated, p_over=read.p_over, p_under=read.p_under, over_probability_version=read.over_probability_version,
        flags=(*gated.flags, *read.flags),
    )


def _gated_projection(
    prior: Sequence[NhlHistoryRow], market: NhlLineOnlyMarket, line: float, position: str | None,
    player_id: int, availability: Availability,
) -> NhlLineProjection:
    """56b's reference projection for one line, gated on what is knowable before puck drop.

    Who dresses or starts is known only after the game, so the stored context decides whether a
    number is shown: a goalie needs a fresh confirmed or expected report naming him, and a skater
    loses it only to an explicit out-type injury entry (no entry is not evidence he will play).
    """
    served = _eligible_projection(prior, market, line, position)
    if served.projection is None:
        return served
    if market in GOALIE_MARKETS:
        block = _goalie_block(availability.goalie, player_id)
        return served if block is None else replace(served, projection=None, gap=None, flags=(block,))
    if availability.injury_status in OUT_INJURY_STATUSES:
        return replace(served, projection=None, gap=None, flags=("injured_out",))
    return replace(served, flags=_skater_flags(availability))


def _eligible_projection(
    prior: Sequence[NhlHistoryRow], market: NhlLineOnlyMarket, line: float, position: str | None,
) -> NhlLineProjection:
    """56b's reference projection from prior played games, oldest first, on its eligibility rules.

    A goalie's inputs are his starts only, matching how the market settles.
    """
    goalie = market in GOALIE_MARKETS
    played = [row for row in prior if row.started]
    sample = sum(
        nhl_stat_value(market, row.stats) is not None for row in played[-REFERENCE_GAMES:]
    )
    minutes = None if goalie else prior_toi_minutes(played)
    if market in CENTER_ONLY_MARKETS and position != CENTER_POSITION:
        return _not_served(sample, minutes, "not_center")
    if len(played) < (MIN_PRIOR_GOALIE_STARTS if goalie else MIN_PRIOR_GAMES):
        return _not_served(sample, minutes, "few_prior_games")
    if not goalie and (minutes is None or minutes < MIN_PRIOR_TOI_MINUTES):
        return _not_served(sample, minutes, "low_toi")
    value = ARMS[REFERENCE_ARM](played, market)
    if value is None:
        return _not_served(sample, minutes, "few_prior_games")
    return NhlLineProjection(
        model_version=NHL_PROJECTION_REFERENCE_VERSION, projection=value, games_in_sample=sample,
        prior_toi_minutes=minutes, gap=round(value - line, 2), flags=(),
    )

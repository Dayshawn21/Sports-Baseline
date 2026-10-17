"""The served NBA prop projection (item 20g2): one line from a player's prior games.

The game page serves it and 20g3 freezes it, so both read one function. Pure: no
DB, no I/O, no clock; the caller passes the prior games.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from statistics import fmean
from typing import Literal

from app.core import nba_over_probability_fit as fit
from app.core.nba_line_only import line_only_value
from app.core.nba_projection_backtest import (
    MIN_PRIOR_GAMES, MIN_PRIOR_MINUTES, NBA_PROJECTION_MODEL_VERSION, REFERENCE_GAMES, NbaHistoryRow, prior_minutes,
)
from app.core.nfl_over_probability import over_probability
from app.nba.markets import NbaPropMarket

NbaProjectionFlag = Literal["few_prior_games", "low_minutes", "no_over_probability", "integer_line"]


@dataclass(frozen=True)
class NbaLineProjection:
    model_version: str
    # None when the player is not eligible; never zero for "unknown".
    projection: float | None
    games_in_sample: int
    prior_minutes: float | None
    gap: float | None
    p_over: float | None
    p_under: float | None
    over_probability_version: str | None
    flags: tuple[NbaProjectionFlag, ...]


def _not_served(sample: int, minutes: float | None, flag: NbaProjectionFlag) -> NbaLineProjection:
    return NbaLineProjection(
        model_version=NBA_PROJECTION_MODEL_VERSION, projection=None, games_in_sample=sample, prior_minutes=minutes,
        gap=None, p_over=None, p_under=None, over_probability_version=None, flags=(flag,),
    )


def _fit_serves(market: NbaPropMarket) -> bool:
    # A fit made for another projection version would misread this projection's ratios.
    return market.value in fit.SHOWN_MARKETS and fit.FIT_PROJECTION_MODEL_VERSION == NBA_PROJECTION_MODEL_VERSION


def project_line(prior: Sequence[NbaHistoryRow], market: NbaPropMarket, line: float) -> NbaLineProjection:
    """20f's reference projection for one line, from prior played games, oldest first.

    Eligibility is 20f's: 10 or more prior played games and 20 or more mean minutes
    over the last 10 with minutes stored.
    """
    values = [value for row in prior[-REFERENCE_GAMES:] if (value := line_only_value(market, row.stats)) is not None]
    minutes = prior_minutes(prior)
    if len(prior) < MIN_PRIOR_GAMES or not values:
        return _not_served(len(values), minutes, "few_prior_games")
    if minutes is None or minutes < MIN_PRIOR_MINUTES:
        return _not_served(len(values), minutes, "low_minutes")

    projection = fmean(values)
    flags: tuple[NbaProjectionFlag, ...] = ()
    probability = None
    if not _fit_serves(market):
        flags = ("no_over_probability",)
    elif float(line).is_integer():
        flags = ("integer_line",)
    else:
        probability = over_probability(fit.QUANTILES_BY_MARKET[market.value], projection, line)
        if probability is None:
            flags = ("no_over_probability",)
    return NbaLineProjection(
        model_version=NBA_PROJECTION_MODEL_VERSION, projection=projection, games_in_sample=len(values),
        prior_minutes=minutes, gap=round(projection - line, 2),
        p_over=probability.p_over if probability else None, p_under=probability.p_under if probability else None,
        over_probability_version=fit.OVER_PROBABILITY_VERSION if probability else None, flags=flags,
    )

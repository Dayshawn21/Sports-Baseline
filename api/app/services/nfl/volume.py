"""The `nfl-volume-v1` receptions reference, isolated from v4's projection and adjustments (49c)."""
from __future__ import annotations

from math import isfinite

from app.core.nfl_baseline import MIN_BASELINE_GAMES
from app.core.nfl_volume_anchor import (
    ANCHOR_MARKET,
    NFL_VOLUME_ANCHOR_PARAMETERS,
    NFL_VOLUME_ANCHOR_VERSION,
    anchored_probability,
    conditional_over,
    require_anchorable,
)
from app.core.nfl_volume_projection import (
    NFL_VOLUME_MODEL_VERSION,
    NFL_VOLUME_V1_PARAMETERS,
    NO_FIT,
    game_context,
    prior_games,
    project_player,
)
from app.repositories.nfl_volume_serving import VOLUME_SERVING_ODDS_TYPES, VOLUME_SERVING_POSITIONS, VolumeServingLine
from app.schemas.nfl import NflVolumeReferenceSchema

NO_GAME_LINES = "no spread or total for the game"
NO_TEAM_SIDE = "player's team is not in the game"
NO_LINE = "no usable line"
NO_PROBABILITY = "the line has no probability mass"
FLAGS = ["volume_reference", "anchor_unvalidated"]
THIN_HISTORY_FLAG = "thin_history"


def _require_eligible(row: VolumeServingLine) -> None:
    require_anchorable(row.market, NFL_VOLUME_MODEL_VERSION)
    if row.position not in VOLUME_SERVING_POSITIONS:
        raise ValueError(f"{row.position} is not a position nfl-volume-v1 fits")
    if row.segment != "full_game" or row.odds_type not in VOLUME_SERVING_ODDS_TYPES or not 1 <= row.week <= 18:
        raise ValueError("the volume reference requires a full-game standard, goblin or demon line in REG weeks 1-18")


def _assess(row: VolumeServingLine) -> NflVolumeReferenceSchema | str:
    """The reference, or the reason there is none. A wrong market, position or payout is a caller bug and raises."""
    _require_eligible(row)
    if row.line is None or not isfinite(row.line) or row.line < 0:
        return NO_LINE
    if row.home_spread_margin is None or row.total is None:
        return NO_GAME_LINES
    if row.is_home is None:
        return NO_TEAM_SIDE
    game = game_context(row.season, row.week, row.home_spread_margin, row.total, row.is_home)
    projection = project_player(row.position, row.history, game, NFL_VOLUME_V1_PARAMETERS)
    distribution = projection.distributions.get(ANCHOR_MARKET)
    if distribution is None:
        return projection.skipped.get(ANCHOR_MARKET, NO_FIT)
    at_line = distribution.p_over(row.line)
    if at_line.over + at_line.under <= 0 or not isfinite(distribution.mean):
        return NO_PROBABILITY
    q_vol = conditional_over(at_line.over, at_line.under)
    anchor = NFL_VOLUME_ANCHOR_PARAMETERS
    over, under = anchored_probability(q_vol, at_line.push, anchor.a, anchor.b)
    games = len(prior_games(row.history, game))
    mean = round(distribution.mean, 2)
    return NflVolumeReferenceSchema(
        projection=mean, median=distribution.median(), line=row.line, gap=round(mean - row.line, 2),
        games_in_sample=games, q_vol=q_vol, p_over=over, p_under=under, p_push=at_line.push,
        model_version=NFL_VOLUME_MODEL_VERSION, over_probability_version=NFL_VOLUME_ANCHOR_VERSION,
        quality_flags=[*FLAGS, *([THIN_HISTORY_FLAG] if games < MIN_BASELINE_GAMES else [])],
    )


def volume_reference(row: VolumeServingLine) -> NflVolumeReferenceSchema | None:
    result = _assess(row)
    return result if isinstance(result, NflVolumeReferenceSchema) else None


def volume_unavailable_reason(row: VolumeServingLine) -> str | None:
    result = _assess(row)
    return result if isinstance(result, str) else None

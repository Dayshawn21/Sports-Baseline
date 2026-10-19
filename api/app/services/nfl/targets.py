"""Rec Targets reference rows, isolated from v4's projection and adjustments."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import isfinite

from app.core.nfl_availability import availability_flags
from app.core.nfl_baseline import MIN_BASELINE_GAMES
from app.core.nfl_over_probability import OverProbability, over_probability
from app.core.nfl_projection import edge
from app.core.nfl_targets_over_probability import NFL_TARGETS_OVER_PROBABILITY_VERSION, TARGETS_MARKET, TARGETS_POSITIONS
from app.core.nfl_targets_over_probability_fit import FIT_PROJECTION_MODEL_VERSION, QUANTILES_BY_POSITION, SHOWN
from app.core.nfl_targets_projection import (
    NFL_TARGETS_MODEL_VERSION, TargetsObservation, TargetsProjection, prior_targets, project_targets,
)
from app.repositories.nfl_targets import TargetsHistoryGame, TargetsServingLine
from app.schemas.nfl import NflHistoryResultSchema, NflHistorySampleSchema, NflSlateLineSchema


def _eligible_line(row: TargetsServingLine) -> bool:
    return (
        row.market == TARGETS_MARKET and row.position in TARGETS_POSITIONS
        and row.segment == "full_game" and row.odds_type == "standard" and 1 <= row.input.week <= 18
    )


def targets_over_probability(
    row: TargetsServingLine, projection: TargetsProjection, *,
    shown: bool = SHOWN, fit_version: str = FIT_PROJECTION_MODEL_VERSION,
    tables: Mapping[str, Sequence[float]] = QUANTILES_BY_POSITION,
) -> OverProbability | None:
    """Read only a shown, compatible targets fit; a hidden fit supplies no probability."""
    quantiles = tables.get(row.position)
    if (
        not shown or fit_version != NFL_TARGETS_MODEL_VERSION or not quantiles or not _eligible_line(row)
        or projection.games_in_sample < MIN_BASELINE_GAMES or projection.projection is None or row.line is None
        or not isfinite(projection.projection) or not isfinite(row.line) or row.line < 0
    ):
        return None
    return over_probability(quantiles, projection.projection, row.line)


def _history_sample(
    observations: Sequence[TargetsObservation], history: Mapping[int, TargetsHistoryGame],
) -> NflHistorySampleSchema:
    values = [
        NflHistoryResultSchema(
            value=observation.targets,
            opponent_team=history[observation.game_id].opponent_team if observation.game_id in history else None,
        )
        for observation in observations if observation.targets is not None
    ]
    return NflHistorySampleSchema(
        average=round(sum(item.value for item in values) / len(values), 2) if values else None,
        values=values,
    )


def targets_slate_line(row: TargetsServingLine) -> NflSlateLineSchema:
    """Assemble the fixed season-average reference and its descriptive evidence."""
    if not _eligible_line(row):
        raise ValueError("Rec Targets requires RB/WR/TE, REG weeks 1-18, full-game standard lines")
    projection = project_targets(row.input)
    observations = prior_targets(row.input)
    history = {game.observation.game_id: game for game in row.history}
    opponent_games = {
        game_id for game_id, game in history.items()
        if row.opponent_team_id is not None and game.opponent_team_id == row.opponent_team_id
    }
    over = targets_over_probability(row, projection)
    flags = ["historical_baseline", *projection.quality_flags, *availability_flags(row.availability)]
    if row.opponent_team_id is None:
        flags.append("team_not_in_game")
    return NflSlateLineSchema(
        line_id=row.line_id, player_id=row.player_id, player_name=row.player_name, position=row.position,
        opponent_team=row.opponent_team, opponent_position_average=None,
        recent_form=_history_sample(observations[:5], history),
        opponent_history=_history_sample([item for item in observations if item.game_id in opponent_games], history),
        opponent_allowed_history=NflHistorySampleSchema(average=None, values=[]),
        market=row.market, segment=row.segment, odds_type=row.odds_type,
        projection=projection.projection, line=row.line, edge=edge(projection.projection, row.line),
        games_in_sample=projection.games_in_sample, baseline_season=projection.baseline_season,
        baseline_reason=projection.baseline_reason, projection_model_version=NFL_TARGETS_MODEL_VERSION,
        opponent_adjustment_pct=None, opponent_sample_games=None, usage_adjustment_pct=None, usage_sample_games=None,
        provider=row.provider, fetched_at=row.fetched_at, quality_flags=flags,
        injury_status=row.availability.injury_status, practice_status=row.practice_status, injury=row.injury,
        depth_position=row.availability.depth_position, depth_rank=row.availability.depth_rank,
        previous_depth_position=row.availability.previous_depth_position,
        previous_depth_rank=row.availability.previous_depth_rank,
        p_over=over.p_over if over is not None else None, p_under=over.p_under if over is not None else None,
        over_probability_version=NFL_TARGETS_OVER_PROBABILITY_VERSION if over is not None else None,
    )

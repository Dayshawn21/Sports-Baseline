"""Freeze what the NFL slate served for each line before kickoff (build-plan item 27i).

27a replays today's code on past weeks, so a model change re-grades history.
These rows are the record of what was actually shown, graded by 27j against
the pre-registered rule in `app/core/prop_ranking_rule.py`.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime

from app.schemas.nfl import NflSlateLineSchema, NflSlateResponse
from app.core.prop_predictions import FreezableGame, PropPredictionRow
from app.core.prop_predictions import freeze_rows as freeze_games


def prediction_row(line: NflSlateLineSchema, now: datetime) -> PropPredictionRow:
    return PropPredictionRow(
        prop_line_id=line.line_id,
        model_version=line.projection_model_version,
        over_probability_version=line.over_probability_version,
        projection=line.projection, p_over=line.p_over, p_under=line.p_under, edge=line.edge,
        quality_flags=list(line.quality_flags),
        feature_snapshot={
            "games_in_sample": line.games_in_sample, "baseline_season": line.baseline_season,
            "baseline_reason": line.baseline_reason, "opponent_adjustment_pct": line.opponent_adjustment_pct,
            "usage_adjustment_pct": line.usage_adjustment_pct, "line": line.line, "odds_type": line.odds_type,
            "market": line.market, "segment": line.segment, "line_fetched_at": line.fetched_at.isoformat(),
        },
        generated_at=now,
    )


def freezable_games(slate: NflSlateResponse, now: datetime) -> list[FreezableGame]:
    return [FreezableGame(game.start_utc, [prediction_row(line, now) for line in game.lines]) for game in slate.games]


def freeze_rows(slate: NflSlateResponse, now: datetime) -> tuple[list[PropPredictionRow], Counter[str]]:
    """Rows for every slate line whose game has not kicked off at `now`, and why the others were skipped."""
    return freeze_games(freezable_games(slate, now), now)

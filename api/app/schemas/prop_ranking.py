"""The forward ranking check's response, shared by every sport's model page (33d, 20g4)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

Signal = Literal["positive", "neutral", "negative"]


class _RankingModel(BaseModel):
    """Built straight from `app.services.prop_ranking`'s dataclasses."""
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class PropRankingRuleSchema(_RankingModel):
    min_picks: int
    min_weeks: int
    min_pick_margin: float


class PropCoverageWeekSchema(_RankingModel):
    week: int
    lines: int
    frozen: int


class PropPickFunnelSchema(_RankingModel):
    calls: int
    with_p_over: int
    picks: int
    bets: int


class PropRankingSliceSchema(_RankingModel):
    odds_type: str
    side: Literal["over", "under"]
    verdict: Literal["insufficient", "adopt", "reject"]
    n: int
    weeks: int
    hits: int
    hit_rate: float | None
    standard_error: float | None
    break_even: float
    signal: Signal


class PropRankingResponse(_RankingModel):
    graded_at: datetime
    season: int
    model_version: str
    over_probability_version: str
    rule: PropRankingRuleSchema
    finished_weeks: list[int]
    last_settled_week: int | None
    frozen_rows: int
    excluded: dict[str, int]
    coverage: list[PropCoverageWeekSchema]
    funnel: PropPickFunnelSchema
    slices: list[PropRankingSliceSchema]

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class PropAudit(_CamelModel):
    player_resolved: bool
    match_linked: bool
    stats_fresh: Optional[bool] = None
    sample_size: Optional[int] = None
    opponent_stats_found: bool
    prediction_found: bool
    projection_found: bool
    match_link_method: Optional[str] = None


class PropsAuditSummary(_CamelModel):
    total_props: int
    unresolved_player_count: int
    unlinked_match_count: int
    missing_stats_count: int
    stale_stats_count: int
    unsupported_stat_count: int
    missing_prediction_count: int
    small_sample_count: int
    top_flagged_examples: list[str]


class AdoptedPick(_CamelModel):
    """A line whose slice 48e's forward check adopted, so it may be ranked (48g)."""

    side: str                  # "over" | "under"
    probability: float         # push-excluded P(side)
    break_even: float
    margin: float              # probability - break_even, the ranking key
    rule: str
    projection_version: str


class PropLine(_CamelModel):
    id: int
    player_id: Optional[int]
    player_name: Optional[str] = None
    match_id: Optional[int]
    source: str
    stat_type: str
    line: Optional[Decimal] = None
    odds_type: Optional[str]
    fetched_at: datetime
    start_time: Optional[datetime]
    match_status: Optional[str] = None
    match_finished: bool = False
    match_link_invalid: bool = False
    p1_odds: Optional[int] = None
    p2_odds: Optional[int] = None
    p_over: Optional[float] = None
    p_under: Optional[float] = None
    p_push: Optional[float] = None
    confidence: Optional[str] = None
    recommendation: Optional[str] = None   # "OVER" | "UNDER"
    stat_avg: Optional[float] = None       # projected per-match average from rolling stats
    edge_pct: Optional[float] = None       # (stat_avg - line) / line * 100 — projection delta, NOT a betting edge
    ev_pct: Optional[float] = None         # expected return %: hit_probability * decimal_odds - 1
    hit_probability: Optional[float] = None  # model probability for the playable side
    break_even_pct: Optional[float] = None   # hit rate this price needs to break even
    matches_count: Optional[int] = None    # rolling stats sample size
    surface: Optional[str] = None          # match surface (Hard / Clay / Grass)
    market_total_games: Optional[float] = None      # market total used for match-length context
    expected_service_points: Optional[float] = None # service-point volume used for serve props
    projection_source: Optional[str] = None         # market_total | model_total
    projection_inputs: dict[str, float | str] = Field(default_factory=dict)
    opponent_stat_avg: Optional[float] = None       # derived per-match figure opponent typically gives up
    opponent_matches_count: Optional[int] = None    # opponent rolling stats sample size
    stats_computed_at: Optional[datetime] = None    # when rolling stats were last refreshed
    stats_stale: Optional[bool] = None              # True if stats older than freshness threshold
    data_quality_flags: list[str] = Field(default_factory=list)
    projection_status: str = "ok"
    audit: Optional[PropAudit] = None
    adopted_pick: Optional[AdoptedPick] = None  # null unless 48e adopted the line's slice; never snapshotted


class PropsResponse(_CamelModel):
    source: Optional[str]
    count: int
    props: list[PropLine]


class PropsAuditResponse(PropsResponse):
    summary: PropsAuditSummary

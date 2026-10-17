from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class MatchPrediction(_CamelModel):
    match_id: int
    start_utc: Optional[datetime]
    p1_name: str
    p2_name: str
    tour: str
    # Display label for `tour` — WTA 125 draws arrive labelled CHALLENGER.
    # Defaulted so older clients and any caller building this by hand still work.
    tour_label: str = ""
    surface: Optional[str]
    tournament: Optional[str]
    round: Optional[str]
    p1_win_prob: Optional[float]
    p2_win_prob: Optional[float]
    p1_elo_prob: Optional[float]
    p1_ml_prob: Optional[float]
    p1_market_prob: Optional[float]
    ensemble_weights: dict
    quality_flags: list[str]
    p1_odds_american: Optional[int]
    p2_odds_american: Optional[int]
    # to_camel capitalizes the letter after a digit, which would serialize these
    # as `h2HP1Wins` and leave the client's `h2hP1Wins` undefined. The only two
    # fields in the API with a digit inside a word, so they are pinned by hand.
    h2h_p1_wins: int = Field(alias="h2hP1Wins")
    h2h_p2_wins: int = Field(alias="h2hP2Wins")
    p1_id: Optional[int] = None
    p2_id: Optional[int] = None


class PredictionsResponse(_CamelModel):
    date: date
    count: int
    matches: list[MatchPrediction]


class PlayerStatsResponse(_CamelModel):
    player_id: int
    surface: Optional[str]
    stat_period: str
    win_rate: Optional[float]
    svc_pts_won: Optional[float]
    ret_pts_won: Optional[float]
    aces_per_game: Optional[float]
    df_per_game: Optional[float]
    hold_pct: Optional[float]
    break_pct: Optional[float]
    matches_count: Optional[int]
    first_in_pct: Optional[float] = None
    first_won_pct: Optional[float] = None
    second_won_pct: Optional[float] = None
    dominance_ratio: Optional[float] = None
    break_points_created_per_return_game: Optional[float] = None
    allowed_break_points_per_service_game: Optional[float] = None
    # ELO ratings (all surfaces + per surface)
    elo: Optional[float] = None
    elo_hard: Optional[float] = None
    elo_clay: Optional[float] = None
    elo_grass: Optional[float] = None


class RecentMatchResult(_CamelModel):
    match_date: date
    opponent_name: str
    score: Optional[str]
    result: str
    aces: Optional[int] = None
    double_faults: Optional[int] = None
    break_chances_created: Optional[int] = None
    break_points_converted: Optional[int] = None


class PlayerFormStats(_CamelModel):
    svc_pts_won: Optional[float]
    ret_pts_won: Optional[float]
    aces_per_game: Optional[float]
    df_per_game: Optional[float]
    hold_pct: Optional[float]
    break_pct: Optional[float]
    win_rate: Optional[float]


class PlayerRecentForm(_CamelModel):
    player_id: int
    player_name: str
    matches: list[RecentMatchResult]
    last_52_w: Optional[PlayerFormStats]


class MatchRecentFormResponse(_CamelModel):
    match_id: int
    players: list[PlayerRecentForm]


class BestPickSchema(_CamelModel):
    pick_type: str           # "moneyline" | "prop" | "derived"
    label: str               # e.g. "Moneyline", "Aces", "Set Score 2-0"
    pick: str                # e.g. "Sinner ML (-150)", "OVER 5.5"
    player_name: Optional[str]
    edge_pct: float          # NOT comparable across pick types — see BestPick.ev_pct
    confidence: str          # LOCK / STRONG / LEAN / PASS
    reasoning: str
    odds_american: Optional[int] = None
    ev_pct: Optional[float] = None  # expected return %; null when the pick is unpriced
    model_prob: Optional[float] = None
    market_prob: Optional[float] = None
    kelly_fraction: Optional[float] = None
    data_quality_flags: list[str] = Field(default_factory=list)
    odds_source: str = "posted"


class MatchPlayerDetail(_CamelModel):
    player_id: int
    name: str
    rank: Optional[int]
    hand: Optional[str]
    country: Optional[str]
    elo: Optional[float]
    elo_surface: Optional[float]


class MatchH2H(_CamelModel):
    p1_wins: int
    p2_wins: int
    surface_p1_wins: Optional[int]
    surface_p2_wins: Optional[int]


class MatchMeetingSchema(_CamelModel):
    match_date: date
    tournament: Optional[str]
    round: Optional[str]
    surface: Optional[str]
    score: Optional[str]
    winner_side: Optional[str]


class MatchDetailResponse(_CamelModel):
    """Load-bearing (32a): the player page links from it, and later match-level
    features extend it rather than adding another endpoint."""
    match_id: int
    status: str
    start_utc: Optional[datetime]
    tour: str
    tour_label: str
    surface: Optional[str]
    indoor: Optional[bool]
    tournament: Optional[str]
    round: Optional[str]
    best_of: int
    score: Optional[str]
    winner_side: Optional[str]
    p1: MatchPlayerDetail
    p2: MatchPlayerDetail
    h2h: MatchH2H = Field(alias="h2h")
    meetings: list[MatchMeetingSchema]
    prediction: Optional[MatchPrediction]
    prediction_source: Optional[str]
    prediction_generated_at: Optional[datetime]
    model_version: Optional[str]
    ml_pick: Optional[BestPickSchema]


class MatchOddsRow(_CamelModel):
    book: str
    p1_odds: Optional[int]
    p2_odds: Optional[int]
    line: Optional[float]
    fetched_at: datetime


class MatchOddsHistoryResponse(_CamelModel):
    match_id: int
    market: str
    rows: list[MatchOddsRow]


class MatchBestPicksSchema(_CamelModel):
    match_id: int
    start_utc: Optional[str]
    p1_name: str
    p2_name: str
    tour: str
    tour_label: str = ""
    surface: Optional[str]
    tournament: Optional[str]
    round: Optional[str]
    p1_win_prob: Optional[float]
    p2_win_prob: Optional[float]
    p1_odds_american: Optional[int]
    p2_odds_american: Optional[int]
    h2h_p1_wins: int = Field(alias="h2hP1Wins")
    h2h_p2_wins: int = Field(alias="h2hP2Wins")
    picks: list[BestPickSchema]


class BestPicksResponse(_CamelModel):
    date: date
    count: int
    matches: list[MatchBestPicksSchema]


# ── Bankroll Builder schemas ─────────────────────────────────────────────────

class BankrollPickSchema(_CamelModel):
    match_id: int
    p1_name: str
    p2_name: str
    tour: str
    surface: Optional[str]
    tournament: Optional[str]
    round: Optional[str]
    start_utc: Optional[datetime]
    bet_type: str
    pick_label: str
    pick_side: str
    our_prob: float
    market_prob: Optional[float]
    odds_american: Optional[int]
    edge_pct: float
    ev: float
    kelly_fraction: float
    confidence: str
    reasoning: str


class ParlayLegSchema(_CamelModel):
    match_id: int
    p1_name: str
    p2_name: str
    tour: str
    bet_type: str
    pick_label: str
    our_prob: float
    odds_american: Optional[int]
    confidence: str


class SuggestedParlaySchema(_CamelModel):
    legs: list[ParlayLegSchema]
    combined_prob: float
    combined_odds_american: int
    combined_ev: float
    combined_kelly: float
    combined_edge_pct: float = 0.0
    confidence: str


class BankrollBuilderResponse(_CamelModel):
    date: date
    total_matches_scanned: int
    singles_count: int
    parlays_count: int
    singles: list[BankrollPickSchema]
    parlays: list[SuggestedParlaySchema]


class _TrackRecordModel(_CamelModel):
    """Built straight from the track-record service's dataclasses."""
    model_config = ConfigDict(from_attributes=True)


class LossComparisonSchema(_TrackRecordModel):
    mean: float
    standard_error: Optional[float]
    signal: str


class ComponentRowSchema(_TrackRecordModel):
    name: str
    log_loss: float
    brier: float
    vs_market: Optional[LossComparisonSchema]


class GroupScoresSchema(_TrackRecordModel):
    group: str
    n: int
    components: list[ComponentRowSchema]


class CalibrationBinSchema(_TrackRecordModel):
    low: float
    high: float
    n: int
    mean_predicted: float
    actual_rate: float


class CalibrationSeriesSchema(_TrackRecordModel):
    source: str
    bins: list[CalibrationBinSchema]


class ClvLineSchema(_TrackRecordModel):
    group: str
    min_gap: float
    eligible: int
    moved: int
    toward: int
    away: int
    mean_move_toward: float


class GradingCountsSchema(_TrackRecordModel):
    settled: int
    other_versions: int
    incomplete: int
    graded: int
    with_market: int
    with_close: int


class VersionCountSchema(_TrackRecordModel):
    model_version: str
    settled: int
    served: bool


class ModelPredictionsResponse(_TrackRecordModel):
    graded_at: datetime
    model_version: str
    counts: GradingCountsSchema
    groups: list[GroupScoresSchema]
    calibration: list[CalibrationSeriesSchema]
    clv: list[ClvLineSchema]
    versions: list[VersionCountSchema]


class LineExclusionsSchema(_TrackRecordModel):
    live: int
    promo: int
    incomplete_score: int
    unjoined: int
    not_settleable: int


class LineSettlementRowSchema(_TrackRecordModel):
    stat: str
    odds_type: str
    settled: int
    over_share: float
    under_share: float
    push_share: float
    over_rate: Optional[float]
    standard_error: Optional[float]
    break_even: Optional[float]
    signal: str


class ModelPrizePicksLinesResponse(_TrackRecordModel):
    graded_at: datetime
    excluded: LineExclusionsSchema
    rows: list[LineSettlementRowSchema]


class TierExclusionsSchema(_TrackRecordModel):
    non_standard: int
    awaiting: int


class TierRowSchema(_TrackRecordModel):
    tier: str
    decided: int
    hits: int
    pushes: int
    hit_rate: Optional[float]
    standard_error: Optional[float]
    verdict: str
    verdict_sample_size: int
    verdict_hit_rate: Optional[float]
    signal: str


class ModelPropTiersResponse(_TrackRecordModel):
    graded_at: datetime
    projection_version: str
    verdict_sample: int
    break_even: float
    excluded: TierExclusionsSchema
    tiers: list[TierRowSchema]
    pass_snapshotted: int


class PlayerEloPointSchema(_CamelModel):
    as_of: date
    overall: Optional[float]
    hard: Optional[float]
    clay: Optional[float]
    grass: Optional[float]


class PlayerEloSchema(_CamelModel):
    overall: Optional[float]
    hard: Optional[float]
    clay: Optional[float]
    grass: Optional[float]
    as_of: Optional[date]
    change: Optional[float]
    tour_rank: Optional[int]
    tour_rank_of: Optional[int]
    history: list[PlayerEloPointSchema]


class PlayerNextMatchSchema(_CamelModel):
    match_id: int
    start_utc: Optional[datetime]
    match_date: date
    tournament: Optional[str]
    round: Optional[str]
    surface: Optional[str]
    opponent_id: int
    opponent_name: str


class PlayerDetailResponse(_CamelModel):
    """Load-bearing (32c): later player-level features extend this or add a sibling endpoint."""
    player_id: int
    name: str
    tour: str
    hand: Optional[str]
    country: Optional[str]
    birth_date: Optional[date]
    rank: Optional[int]
    elo: PlayerEloSchema
    next_match: Optional[PlayerNextMatchSchema]
    aliases: list[str]
    stats_computed_at: Optional[datetime]


class _ServeReturnMetrics(_CamelModel):
    """Stored names kept; break_pct is BP converted and the two "per game" rates are per serve point."""
    hold_pct: Optional[float]
    break_pct: Optional[float]
    first_in_pct: Optional[float]
    first_won_pct: Optional[float]
    second_won_pct: Optional[float]
    ret_pts_won: Optional[float]
    aces_per_game: Optional[float]
    df_per_game: Optional[float]


class PlayerSurfaceStatsSchema(_ServeReturnMetrics):
    matches: int


class TourAverageStatsSchema(_ServeReturnMetrics):
    players: int


class PlayerSurfaceComparisonSchema(_CamelModel):
    surface: str
    player: Optional[PlayerSurfaceStatsSchema]
    tour_average: TourAverageStatsSchema


class PlayerServeReturnResponse(_CamelModel):
    tour: str
    surfaces: list[PlayerSurfaceComparisonSchema]


class PlayerMatchLogSchema(_CamelModel):
    match_id: int
    match_date: date
    tournament: Optional[str]
    round: Optional[str]
    surface: Optional[str]
    best_of: int
    opponent_id: int
    opponent_name: str
    opponent_rank: Optional[int]
    result: str
    score: Optional[str]
    aces: Optional[int]
    double_faults: Optional[int]
    bp_saved: Optional[int]
    bp_faced: Optional[int]
    bp_won: Optional[int]
    bp_created: Optional[int]


class WinLossSchema(_CamelModel):
    model_config = ConfigDict(from_attributes=True)
    wins: int
    losses: int


class PlayerRecordSchema(_CamelModel):
    """52-week splits; tie_breaks counts sets, and set splits skip retirements."""
    model_config = ConfigDict(from_attributes=True)
    window_start: date
    all: WinLossSchema
    hard: WinLossSchema
    clay: WinLossSchema
    grass: WinLossSchema
    vs_top20: WinLossSchema
    deciding_sets: WinLossSchema
    tie_breaks: WinLossSchema


class PlayerMatchesResponse(_CamelModel):
    log: list[PlayerMatchLogSchema]
    record: PlayerRecordSchema


class PastPropSchema(_CamelModel):
    model_config = ConfigDict(from_attributes=True)
    snapshot_date: date
    stat: str
    odds_type: str
    line: float
    actual: Optional[int]
    recommendation: Optional[str]
    confidence: Optional[str]
    outcome: str
    """hit | miss | push | pass (no recommendation) | void (retired or walkover) | awaiting (box score
    not joined yet) | ungradable (no settlement source, such as fantasy score)."""


class PastPropSummarySchema(_CamelModel):
    hits: int
    misses: int


class PlayerPropsResponse(_CamelModel):
    projection_version: str
    rows: list[PastPropSchema]
    summary: PastPropSummarySchema

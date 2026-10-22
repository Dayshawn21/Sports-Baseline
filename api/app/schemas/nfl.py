from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app.core.nfl_matchup_context import UnavailableReason
from app.schemas.prop_ranking import PropRankingResponse


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class NflGameSchema(_CamelModel):
    game_id: int
    season: int
    week: int
    game_date: date
    start_utc: datetime | None
    away_team: str
    home_team: str
    status: str


class NflLineStepSchema(_CamelModel):
    fetched_at: datetime
    line: float


class NflLineHistorySchema(_CamelModel):
    market: Literal["spread", "total"]
    book: str
    # A spread line is the home spread in book sign, as `NflGameOddsSchema.home_spread`.
    steps: list[NflLineStepSchema]


class NflGameDetailResponse(NflGameSchema):
    """The game page's anchor; later game-level display context extends it."""
    line_history: list[NflLineHistorySchema]


class NflLineOnlyRecentSchema(_CamelModel):
    season: int
    week: int
    opponent: str | None
    # NULL when a stat the market needs was not loaded for that game, never zero.
    value: float | None


class NflLineOnlyLineSchema(_CamelModel):
    player_id: int
    player_name: str
    position: str | None
    team: str | None
    market: str
    odds_type: str | None
    line: float
    fetched_at: datetime
    recent: list[NflLineOnlyRecentSchema]


class NflLineOnlyPropsResponse(_CamelModel):
    """Item 35: line-only markets with recent results; never a projection, edge or rank."""
    game_id: int
    lines: list[NflLineOnlyLineSchema]


class NflLineOnlyBoardGame(NflGameSchema):
    lines: list[NflLineOnlyLineSchema]


class NflLineOnlyBoardResponse(_CamelModel):
    season: int
    week: int
    games: list[NflLineOnlyBoardGame]


class NflSeasonWeekSchema(_CamelModel):
    season: int
    week: int


class NflPlayerSummarySchema(_CamelModel):
    """Per-game means this season; a mean is null when no game has the stat."""
    games: int
    focus_per_game: float | None
    volume_per_game: float | None
    snap_share: float | None


class NflPlayerSplitSchema(NflPlayerSummarySchema):
    label: str


class NflPlayerUsageSchema(_CamelModel):
    """One game's usage; the page shows the stats named in `usage_stats`."""
    season: int
    week: int
    previous_season: bool
    passing_attempts: int
    rushing_attempts: int
    targets: int | None
    receptions: int
    snap_pct: float | None


class NflPastLineCountSchema(_CamelModel):
    """Over hits out of decided standard full-game lines this season; anecdote, never a verdict."""
    market: str
    overs: int
    decided: int


class NflPlayerGameSchema(_CamelModel):
    game_id: int
    season: int
    week: int
    opponent: str
    is_home: bool
    team_score: int | None
    opponent_score: int | None
    snap_pct: float | None       # 0 to 1; null when no snap row was loaded
    passing_completions: int
    passing_attempts: int
    passing_yards: int
    rushing_attempts: int
    rushing_yards: int
    targets: int | None
    receptions: int
    receiving_yards: int
    touchdowns: int
    fg_made: int | None = None
    pat_made: int | None = None
    kicking_points: float | None = None
    punts: int | None = None
    prizepicks_fantasy_points: float | None
    # The last pre-kickoff standard full-game line in the focus market, as 27a grades it.
    focus_line: float | None
    focus_outcome: str | None    # "over" | "under" | "push"; voids and unloaded weeks carry no line


class NflPlayerDetailResponse(_CamelModel):
    """The one NFL player page; later player-level features extend it or add a sibling under /nfl/players/{id}/."""
    player_id: int
    name: str
    position: str | None
    team: str | None             # as of the week; null when cut or retired
    season: int
    week: int
    depth_position: str | None
    depth_rank: int | None
    injury_status: str | None
    practice_status: str | None
    injury: str | None
    aliases: list[str]
    stats_through: NflSeasonWeekSchema | None
    focus_market: str | None
    summary: NflPlayerSummarySchema
    game_log: list[NflPlayerGameSchema]
    usage_stats: list[str]                    # which usage fields to show, by position
    usage: list[NflPlayerUsageSchema]         # last 8 games, oldest first
    past_lines: list[NflPastLineCountSchema]  # market order
    break_even: float                         # per-leg standard break-even, the tick the past lines are read against
    splits: list[NflPlayerSplitSchema]        # empty for a position without a focus


class NflProjectionSchema(_CamelModel):
    game_id: int
    player_id: int
    player_name: str
    position: str | None
    market: str
    projection: float
    games_in_sample: int
    probability_over: float | None = None
    probability_under: float | None = None
    edge: float | None = None
    confidence: str
    quality_flags: list[str]
    live_line_status: str = "unavailable"


class NflCurrentWeekResponse(_CamelModel):
    season: int
    week: int


class NflGamesResponse(_CamelModel):
    season: int
    week: int
    count: int
    games: list[NflGameSchema]


class NflProjectionsResponse(_CamelModel):
    season: int
    week: int
    count: int
    live_lines_connected: bool = False
    projections: list[NflProjectionSchema]


class NflPropLineSchema(_CamelModel):
    id: int
    provider: str
    provider_prop_id: str | None
    player_name: str
    position: str | None
    market: str
    segment: str = "full_game"
    league_name: str | None = None
    line: float
    start_time: datetime | None
    fetched_at: datetime


class NflProspectsResponse(_CamelModel):
    count: int
    provider: str = "prizepicks"
    refresh_interval_minutes: int = 120
    lines: list[NflPropLineSchema]


class NflSlateLineSchema(_CamelModel):
    """One market for one player: our baseline beside the market's line."""

    line_id: int
    player_id: int
    player_name: str
    position: str | None
    opponent_team: str | None = None
    opponent_position_average: float | None = None
    recent_form: "NflHistorySampleSchema"
    opponent_history: "NflHistorySampleSchema"
    opponent_allowed_history: "NflHistorySampleSchema"
    market: str
    segment: str
    odds_type: str | None
    # Nullable so "no baseline" and "no line" stay distinguishable from zero.
    projection: float | None
    line: float | None
    edge: float | None
    games_in_sample: int
    # The season this baseline was computed from, not merely the newest season
    # with any data. `baseline_reason` says how it was chosen, because 19e's
    # model will need to report something a bare season number cannot carry.
    baseline_season: int | None
    baseline_reason: str
    opponent_adjustment_pct: float | None
    opponent_sample_games: int | None
    # Both null for markets usage does not adjust, so "not applicable" never
    # reads as "no usage data".
    usage_adjustment_pct: float | None
    usage_sample_games: int | None
    provider: str
    fetched_at: datetime
    projection_model_version: str
    quality_flags: list[str]
    # Sportsbook consensus for anytime-TD full-game lines; all null means no book price.
    book_probability: float | None = None
    book_count: int | None = None
    book_includes_margin: bool | None = None
    book_fetched_at: datetime | None = None
    # The consensus with the book's margin removed, normalized across the game
    # (build-plan item 25a). Null means not normalized, never "no margin": a
    # price that was already de-vigged needs no correction, and a game with no
    # market total has nothing to normalize against. Never replaces
    # `book_probability`; both travel together so the correction stays auditable.
    book_probability_devigged: float | None = None
    # This week's injury report and depth chart, display only. Null injury fields
    # mean "not on the report" (or not published yet), never "healthy".
    injury_status: str | None = None
    practice_status: str | None = None
    injury: str | None = None
    depth_position: str | None = None
    depth_rank: int | None = None
    previous_depth_position: str | None = None
    previous_depth_rank: int | None = None
    # Only RB and TE anytime-TD lines: the pre-week season-weighted share (0 to 1)
    # the model used, and the player's snap games behind it. A null share with
    # 0 games means no snap history (the model fell back to the position share).
    snap_share: float | None = None
    snap_share_games: int | None = None
    # Display only (build-plan item 27g): the fitted chance the result lands over
    # the line. Null means not shown for this market, line or sample, never 0.5.
    p_over: float | None = None
    p_under: float | None = None
    over_probability_version: str | None = None


class NflHistorySampleSchema(_CamelModel):
    average: float | None
    values: list["NflHistoryResultSchema"]


class NflHistoryResultSchema(_CamelModel):
    value: float
    opponent_team: str | None


class NflUnmatchedLineSchema(_CamelModel):
    """A line placed in a game but not resolved to a player."""

    line_id: int
    player_name: str
    provider_team: str | None
    provider_position: str | None
    market: str
    segment: str
    odds_type: str | None
    line: float
    provider: str
    fetched_at: datetime


class NflSlateGameSchema(_CamelModel):
    game_id: int
    game_date: date
    start_utc: datetime | None
    away_team: str
    home_team: str
    status: str
    lines: list[NflSlateLineSchema]
    odds: "NflGameOddsSchema | None" = None
    away_context: "NflTeamContextSchema | None" = None
    home_context: "NflTeamContextSchema | None" = None
    weather: "NflWeatherSchema"
    model: "NflGameModelSchema | None" = None


class NflGameModelSchema(_CamelModel):
    """Display-only team-strength line; it did not beat closing lines (24b), so never an edge."""

    model_version: str
    home_elo: float
    away_elo: float
    home_win_probability: float
    # Book sign, like `NflGameOddsSchema.home_spread`: negative when home is favored.
    home_spread: float
    total: float
    # De-vigged from the displayed book's moneylines, so both numbers share a source.
    market_home_win_probability: float | None


class NflWeatherSchema(_CamelModel):
    venue_type: str
    forecast_for: datetime | None = None
    temperature_f: float | None = None
    wind_mph: float | None = None
    wind_gust_mph: float | None = None
    precipitation_probability: float | None = None
    fetched_at: datetime | None = None


class NflGameOddsSchema(_CamelModel):
    book: str
    home_moneyline: int | None
    away_moneyline: int | None
    home_spread: float | None
    total: float | None


class NflTeamContextSchema(_CamelModel):
    games: int
    wins: int
    losses: int
    points_for_per_game: float
    points_allowed_per_game: float


class NflSlateResponse(_CamelModel):
    season: int
    week: int
    game_count: int
    line_count: int
    unmatched_count: int
    games: list[NflSlateGameSchema]
    unmatched: list[NflUnmatchedLineSchema]


class NflNoteInjurySchema(_CamelModel):
    player_id: int
    player_name: str
    team: str
    position: str
    injury_status: str | None
    practice_status: str | None
    injury: str | None
    updated_at: datetime | None = None


class NflNoteDepthChangeSchema(_CamelModel):
    player_id: int
    player_name: str
    team: str
    depth_position: str
    depth_rank: int
    previous_depth_position: str | None
    previous_depth_rank: int | None
    change: Literal["promoted", "demoted", "new"]


class NflLineMoveSchema(_CamelModel):
    market: Literal["spread", "total"]
    book: str
    # Spread is the home line in book sign: negative when home is favored.
    open_line: float
    open_fetched_at: datetime
    current_line: float
    current_fetched_at: datetime
    # Null when only one pre-kickoff line is stored, so "no history" never reads as "no movement".
    move: float | None


class NflRecentResultSchema(_CamelModel):
    week: int
    opponent: str
    is_home: bool
    points_for: int
    points_against: int
    result: Literal["W", "L", "T"]


class NflTeamFormSchema(_CamelModel):
    team: str
    rest_days: int | None
    short_week: bool
    recent: list[NflRecentResultSchema]


class NflTeamStatSchema(_CamelModel):
    value: float | None
    rank: int | None
    observed_games: int = 0


class NflTeamStatsSchema(_CamelModel):
    """Season to date before the slate week; ranks are league-wide, 1 = best."""

    team: str
    games: int
    efficiency_games: int
    points: NflTeamStatSchema
    pass_yards: NflTeamStatSchema
    rush_yards: NflTeamStatSchema
    pass_attempts: NflTeamStatSchema = NflTeamStatSchema(value=None, rank=None)
    rush_attempts: NflTeamStatSchema = NflTeamStatSchema(value=None, rank=None)
    plays: NflTeamStatSchema
    epa_per_play: NflTeamStatSchema
    success_rate: NflTeamStatSchema
    points_allowed: NflTeamStatSchema
    pass_yards_allowed: NflTeamStatSchema
    rush_yards_allowed: NflTeamStatSchema
    pass_attempts_allowed: NflTeamStatSchema = NflTeamStatSchema(value=None, rank=None)
    rush_attempts_allowed: NflTeamStatSchema = NflTeamStatSchema(value=None, rank=None)
    plays_allowed: NflTeamStatSchema
    epa_per_play_allowed: NflTeamStatSchema
    success_rate_allowed: NflTeamStatSchema


class NflQbChangeSchema(_CamelModel):
    """A team's QB differs from the one its recent games, and so the game model, were built on."""

    team: str
    usual_starter: str      # latest depth-chart QB1; most attempts only when no chart is stored
    reasons: list[Literal["injured", "backup_started", "depth_chart"]]
    # Each pair is set only with its reason; weeks are the latest stored, not always the slate week.
    injury_status: str | None
    injury_week: int | None
    last_game_qb: str | None
    last_game_week: int | None
    previous_qb1: str | None


class NflFairPriceSchema(_CamelModel):
    source: Literal["pinnacle", "consensus"]
    line: float | None
    first_probability: float     # de-vigged, home or over side
    fetched_at: datetime


class NflBestSideSchema(_CamelModel):
    side: Literal["home", "away", "over", "under"]
    line: float | None           # book sign: negative home spread = home favored
    odds: int
    book: str
    provider: str
    fetched_at: datetime
    # Exactly one is set when there is a fair price: EV at the fair line, else points off it.
    ev_pct: float | None
    points_vs_fair: float | None


class NflBestMarketSchema(_CamelModel):
    market: Literal["moneyline", "spread", "total"]
    fair: NflFairPriceSchema | None
    sides: list[NflBestSideSchema]


class NflBestLineSchema(_CamelModel):
    """Each side's best price across books beside a fair price; a reference, never a pick."""

    max_age_hours: int
    markets: list[NflBestMarketSchema]


class NflGameNotesSchema(_CamelModel):
    """Display-only pre-bet context; never feeds an edge, rank, or projection."""

    game_id: int
    away_team: str
    home_team: str
    injuries: list[NflNoteInjurySchema]
    depth_changes: list[NflNoteDepthChangeSchema]
    line_movement: list[NflLineMoveSchema]
    away_form: NflTeamFormSchema
    home_form: NflTeamFormSchema
    away_stats: NflTeamStatsSchema
    home_stats: NflTeamStatsSchema
    away_recent_stats: NflTeamStatsSchema | None = None
    home_recent_stats: NflTeamStatsSchema | None = None
    away_score: int | None      # null until the game is final in sport_games
    home_score: int | None
    away_qb_change: NflQbChangeSchema | None
    home_qb_change: NflQbChangeSchema | None
    best_line: NflBestLineSchema | None     # null once kicked off or with no fresh book
    matchup_context: NflMatchupContextSchema | None = None


class NflGameNotesResponse(_CamelModel):
    season: int
    week: int
    games: list[NflGameNotesSchema]


class NflContextMetricSchema(_CamelModel):
    model_config = ConfigDict(from_attributes=True)

    value: float | None
    observed_games: int
    eligible_games: int
    window_start: date | None
    window_end: date | None
    reason: UnavailableReason | None


class NflAllowedMetricSchema(NflContextMetricSchema):
    rank: int | None
    ranked_teams: int


class NflPositionAllowedSchema(_CamelModel):
    rb_carries: NflAllowedMetricSchema
    rb_rush_yards: NflAllowedMetricSchema
    rb_receptions: NflAllowedMetricSchema
    rb_rec_yards: NflAllowedMetricSchema
    wr_receptions: NflAllowedMetricSchema
    wr_rec_yards: NflAllowedMetricSchema
    te_receptions: NflAllowedMetricSchema
    te_rec_yards: NflAllowedMetricSchema


class NflMatchupTeamSchema(_CamelModel):
    team_id: int
    team: str
    allowed: NflPositionAllowedSchema


class NflMatchupContextSchema(_CamelModel):
    away: NflMatchupTeamSchema
    home: NflMatchupTeamSchema


class NflUsageWindowSchema(_CamelModel):
    model_config = ConfigDict(from_attributes=True)

    targets: NflContextMetricSchema
    carries: NflContextMetricSchema
    target_share: NflContextMetricSchema
    carry_share: NflContextMetricSchema
    avg_game_snap_share: NflContextMetricSchema
    teams: list[str]


class NflContextPlayerSchema(_CamelModel):
    player_id: int
    name: str
    position: Literal["QB", "RB", "WR", "TE"]
    team: str
    season_usage: NflUsageWindowSchema
    recent_usage: NflUsageWindowSchema


class NflGameContextResponse(_CamelModel):
    game_id: int
    season: int
    week: int
    cutoff_week: int
    matchup_context: NflMatchupContextSchema
    players: list[NflContextPlayerSchema]


class _NflTrackRecordModel(_CamelModel):
    """Built straight from the NFL track-record service's dataclasses."""
    model_config = ConfigDict(from_attributes=True)


Signal = Literal["positive", "neutral", "negative"]
NflRankingModelVersion = Literal["opponent-dvp-tg-blend-usage-snap-v4", "nfl-targets-v1"]


class NflModelRankingResponse(PropRankingResponse):
    """27j's record, in the shape every sport's ranking check shares (20g4)."""

    over_probability_version: str | None


class NflClvRuleSchema(_NflTrackRecordModel):
    pick_threshold: float
    verdict_picks: int


class NflClvRowSchema(_NflTrackRecordModel):
    n: int
    mean_clv: float | None
    standard_error: float | None
    toward: int
    away: int
    flat: int
    wins: int
    losses: int
    pushes: int


class NflClvMarketSchema(_NflTrackRecordModel):
    market: Literal["spread", "total"]
    model_version: str
    graded: int
    excluded: dict[str, int]
    median_lead_hours: float | None
    min_lead_hours: float | None
    verdict: Literal["accruing", "pass", "reject"]
    verdict_weeks: list[int]
    headline: NflClvRowSchema
    all: NflClvRowSchema
    early: NflClvRowSchema
    late: NflClvRowSchema
    signal: Signal


class NflModelClvResponse(_NflTrackRecordModel):
    graded_at: datetime
    season: int
    rule: NflClvRuleSchema
    markets: list[NflClvMarketSchema]


class NflLineCoverageSchema(_NflTrackRecordModel):
    loaded: int
    settled: int
    void_dnp: int
    unsettleable_segment: int
    week_not_loaded: int


class NflHitRowSchema(_NflTrackRecordModel):
    calls: int
    hits: int
    pushes: int
    hit_rate: float | None
    standard_error: float | None
    signal: Signal


class NflEdgeHitRowSchema(NflHitRowSchema):
    bucket: Literal["small", "medium", "large"]
    label: str


class NflMarketHitRowSchema(NflHitRowSchema):
    market: str


class NflWeekHitRowSchema(NflHitRowSchema):
    week: int


class NflOverProbabilityReadSchema(_NflTrackRecordModel):
    odds_type: str
    scored: int
    unscored: int
    mean_predicted: float | None
    over_rate: float | None
    brier: float | None


class NflReliabilityBinSchema(_NflTrackRecordModel):
    n: int
    mean_predicted: float
    observed: float


class NflModelPropLinesResponse(_NflTrackRecordModel):
    graded_at: datetime
    season: int
    model_version: str
    break_even: float
    coverage: NflLineCoverageSchema
    calls: NflHitRowSchema
    by_edge: list[NflEdgeHitRowSchema]
    by_market: list[NflMarketHitRowSchema]
    by_week: list[NflWeekHitRowSchema]
    over_probability: list[NflOverProbabilityReadSchema]
    reliability: list[NflReliabilityBinSchema]


class NflFitRuleSchema(_NflTrackRecordModel):
    min_cases: int
    max_ece: float
    max_bin_gap: float
    min_bin_pairs: int


class NflFitMarketSchema(_NflTrackRecordModel):
    market: str
    cases: int
    pairs: int
    ece: float
    worst_gap: float | None
    brier: float
    normal_brier: float
    verdict: Literal["show", "hide"]
    at_projection_predicted: float
    at_projection_observed: float


class NflModelFitResponse(_NflTrackRecordModel):
    fit_season: int
    projection_version: str
    served: bool
    rule: NflFitRuleSchema
    markets: list[NflFitMarketSchema]

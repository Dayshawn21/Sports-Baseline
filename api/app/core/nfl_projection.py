"""Transparent historical baseline projections for the first NFL MVP."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import exp

from app.core.nfl_baseline import FULL_SEASON_GAMES, MIN_BASELINE_GAMES
from app.core.odds import odds_are_stale
from app.nfl.markets import STANDARD_ODDS_TYPE, NflPropMarket

NFL_PROJECTION_MODEL_VERSION = "opponent-dvp-tg-blend-usage-snap-v4"
MARKET_ADJUSTMENT_MAX = 0.08
OPPONENT_MIN_SAMPLE_GAMES = 4
OPPONENT_FULL_WEIGHT_GAMES = 12
OPPONENT_ADJUSTMENT_MAX = 0.10
USAGE_MIN_SAMPLE_GAMES = 4
USAGE_FULL_WEIGHT_GAMES = 12
USAGE_ADJUSTMENT_MAX = 0.08
# Efficiency is partly a persistent skill and role (deep threat versus slot), so
# only part of the gap to position-typical efficiency is expected to close. A
# full pull let the cap, not the evidence, decide most adjustments.
USAGE_EFFICIENCY_REGRESSION = 0.35
STALE_BASELINE_SEASON_FLAG = "stale_baseline_season"
# Game odds are fetched weekly (Tuesday), so eight days catches a stopped job
# without flagging a healthy week. Tennis's six hours assumes an hourly job.
NFL_STALE_ODDS_HOURS = 192.0
# Touchdowns are rare and noisy, so a single season (or four games of one) is not
# enough evidence. Older seasons still count, less, and the position's TD rate
# acts as PRIOR_GAMES games of evidence the player has to outweigh.
TD_SEASON_WEIGHTS = (1.0, 0.6, 0.35)
TD_PRIOR_GAMES = 10.0
USAGE_ADJUSTED_MARKETS = frozenset({NflPropMarket.RECEIVING_YARDS, NflPropMarket.RECEPTIONS})
# Markets whose DVP reads per-game position totals (27c) instead of per-player
# rows: only those that passed the 2025 projection backtest. Never anytime TD,
# which has its own backtest.
TEAM_GAME_DVP_MARKETS = frozenset({NflPropMarket.PASSING_COMPLETIONS})
# Markets whose baseline blends the current and previous season (27d) instead of
# switching seasons at four games: only those that pass the 2025 projection
# backtest. Never anytime TD, which blends its own seasons.
SEASON_BLEND_MARKETS = frozenset({
    NflPropMarket.PASSING_ATTEMPTS, NflPropMarket.PASSING_COMPLETIONS, NflPropMarket.PASSING_YARDS,
})
# Markets that take no moneyline bump (27e): raising a favorite's passing volume
# is the wrong sign, and dropping it passed the 2025 projection backtest. The
# game-environment slopes fitted for them on 2024 were all zero, so nothing
# replaces it.
MONEYLINE_UNSCALED_MARKETS = frozenset({
    NflPropMarket.PASSING_ATTEMPTS, NflPropMarket.PASSING_COMPLETIONS, NflPropMarket.PASSING_YARDS,
})


@dataclass(frozen=True)
class NflUsageInput:
    games: int
    targets: float
    target_share: float
    position_targets: float
    position_target_share: float


@dataclass(frozen=True)
class NflProjectionInput:
    recent_average: float
    position_average: float
    games: int
    home_market_prob: float | None = None
    player_is_home: bool = True
    market_is_stale: bool = False
    opponent_average: float | None = None
    league_position_average: float | None = None
    opponent_games: int = 0
    usage_applicable: bool = False
    usage: NflUsageInput | None = None
    # Game environment replaces moneyline scaling for these rows, even when its
    # adjustment is None (no lines, or no baseline environment to compare with).
    uses_game_environment: bool = False
    environment_adjustment_pct: float | None = None
    moneyline_scaled: bool = True
    wind_adjustment_pct: float | None = None


def _usage_is_valid(input: NflProjectionInput, usage: NflUsageInput) -> bool:
    return (
        input.recent_average > 0
        and input.position_average > 0
        and usage.position_targets > 0
        and usage.position_target_share > 0
    )


def usage_adjustment_pct(input: NflProjectionInput) -> float | None:
    """Return the bounded, sample-shrunk receiving-usage adjustment in percentage points.

    The player's own average already reflects their targets, so scaling it by
    relative usage would count volume twice. Instead, targets and target share
    are converted into the production a typical player at the position gets from
    that usage, and part of the gap to the player's actual average is applied,
    because efficiency is less stable week to week than volume.
    """
    usage = input.usage
    if not input.usage_applicable or usage is None:
        return None
    if usage.games < USAGE_MIN_SAMPLE_GAMES or not _usage_is_valid(input, usage):
        return None
    volume_expected = usage.targets * input.position_average / usage.position_targets
    share_expected = input.position_average * usage.target_share / usage.position_target_share
    expected = (volume_expected + share_expected) / 2
    sample_weight = min(1.0, usage.games / USAGE_FULL_WEIGHT_GAMES)
    raw_adjustment = (expected / input.recent_average - 1) * USAGE_EFFICIENCY_REGRESSION * sample_weight
    bounded_adjustment = max(-USAGE_ADJUSTMENT_MAX, min(USAGE_ADJUSTMENT_MAX, raw_adjustment))
    return round(bounded_adjustment * 100, 2)


def opponent_adjustment_pct(input: NflProjectionInput) -> float | None:
    """Return the bounded, sample-shrunk DVP adjustment in percentage points."""
    if input.opponent_average is None or input.league_position_average is None:
        return None
    if input.opponent_games < OPPONENT_MIN_SAMPLE_GAMES:
        return None
    if input.league_position_average <= 0:
        return None
    sample_weight = min(1.0, input.opponent_games / OPPONENT_FULL_WEIGHT_GAMES)
    raw_adjustment = (input.opponent_average / input.league_position_average - 1) * sample_weight
    bounded_adjustment = max(-OPPONENT_ADJUSTMENT_MAX, min(OPPONENT_ADJUSTMENT_MAX, raw_adjustment))
    return round(bounded_adjustment * 100, 2)


def moneyline_is_stale(fetched_at: datetime | None, kickoff: datetime | None, now: datetime) -> bool:
    """Whether a game's moneyline is too old to adjust a projection with.

    Age is measured at kickoff once the game has started, so revisiting a past
    week reproduces the projection it had before the game.
    """
    reference = min(now, kickoff) if kickoff is not None else now
    return odds_are_stale(fetched_at, reference, NFL_STALE_ODDS_HOURS)


def model_projection(input: NflProjectionInput) -> float:
    """Regress a recent average, then apply a bounded fresh-market adjustment."""
    weight = min(1.0, max(0.0, input.games / MIN_BASELINE_GAMES))
    projection = input.recent_average * weight + input.position_average * (1 - weight)
    if input.uses_game_environment:
        if input.environment_adjustment_pct is not None:
            projection *= 1 + input.environment_adjustment_pct / 100
    elif input.moneyline_scaled and input.home_market_prob is not None and not input.market_is_stale:
        team_probability = input.home_market_prob if input.player_is_home else 1 - input.home_market_prob
        projection *= 1 + max(-MARKET_ADJUSTMENT_MAX, min(MARKET_ADJUSTMENT_MAX, team_probability - 0.5))
    opponent_adjustment = opponent_adjustment_pct(input)
    if opponent_adjustment is not None:
        projection *= 1 + opponent_adjustment / 100
    usage_adjustment = usage_adjustment_pct(input)
    if usage_adjustment is not None:
        projection *= 1 + usage_adjustment / 100
    if input.wind_adjustment_pct is not None:
        projection *= 1 + input.wind_adjustment_pct / 100
    return round(projection, 2)


def model_quality_flags(input: NflProjectionInput) -> list[str]:
    flags = ["recent_market_model"]
    if input.games < MIN_BASELINE_GAMES:
        flags.append("small_sample")
    if input.moneyline_scaled:
        if input.home_market_prob is None:
            flags.append("market_missing")
        elif input.market_is_stale:
            flags.append("market_stale")
    if input.opponent_average is None or input.league_position_average is None:
        flags.append("opponent_data_missing")
    elif input.opponent_games < OPPONENT_MIN_SAMPLE_GAMES:
        flags.append("opponent_small_sample")
    elif input.league_position_average <= 0:
        flags.append("opponent_data_invalid")
    else:
        flags.append("opponent_adjusted")
    if input.usage_applicable:
        flags.append(_usage_flag(input))
    return flags


def _usage_flag(input: NflProjectionInput) -> str:
    if input.usage is None:
        return "usage_data_missing"
    if input.usage.games < USAGE_MIN_SAMPLE_GAMES:
        return "usage_small_sample"
    if not _usage_is_valid(input, input.usage):
        return "usage_data_invalid"
    return "usage_adjusted"


@dataclass(frozen=True)
class NflHistoricalAverages:
    games: int
    passing_yards: float
    passing_attempts: float
    passing_completions: float
    rushing_yards: float
    rushing_attempts: float
    receiving_yards: float
    receptions: float
    touchdowns: float
    fantasy_points: float | None
    # Carried beside NFLverse PPR for the 27f arm; the projection never reads it.
    prizepicks_fantasy_points: float | None = None


def baseline_projection(market: NflPropMarket, averages: NflHistoricalAverages) -> float:
    values = {
        NflPropMarket.PASSING_YARDS: averages.passing_yards,
        NflPropMarket.PASSING_ATTEMPTS: averages.passing_attempts,
        NflPropMarket.PASSING_COMPLETIONS: averages.passing_completions,
        NflPropMarket.RUSHING_YARDS: averages.rushing_yards,
        NflPropMarket.RUSHING_ATTEMPTS: averages.rushing_attempts,
        NflPropMarket.RECEIVING_YARDS: averages.receiving_yards,
        NflPropMarket.RECEPTIONS: averages.receptions,
        NflPropMarket.FANTASY_POINTS: averages.fantasy_points or 0.0,
        # This is a probability, not a count. A Poisson event model makes the
        # baseline explicit until target-share and red-zone features are added.
        NflPropMarket.ANYTIME_TOUCHDOWN: 1 - exp(-max(averages.touchdowns, 0.0)),
    }
    return round(values[market], 2)


@dataclass(frozen=True)
class NflSeasonTouchdowns:
    season: int
    games: int
    touchdowns_per_game: float


def td_seasons_used(seasons: list[NflSeasonTouchdowns], line_season: int) -> list[NflSeasonTouchdowns]:
    """Seasons with games that fall inside the recency weights for this line."""
    return [
        entry for entry in seasons
        if entry.games > 0 and 0 <= line_season - entry.season < len(TD_SEASON_WEIGHTS)
    ]


def anytime_td_rate(
    seasons: list[NflSeasonTouchdowns], line_season: int, position_rate: float,
) -> tuple[float, float]:
    """Unrounded TDs per game behind `anytime_td_probability`, as (rate, weighted games)."""
    weighted_tds = TD_PRIOR_GAMES * max(position_rate, 0.0)
    weighted_games = 0.0
    for entry in td_seasons_used(seasons, line_season):
        weight = TD_SEASON_WEIGHTS[line_season - entry.season]
        weighted_tds += weight * entry.games * max(entry.touchdowns_per_game, 0.0)
        weighted_games += weight * entry.games
    return weighted_tds / (weighted_games + TD_PRIOR_GAMES), weighted_games


def anytime_td_probability(
    seasons: list[NflSeasonTouchdowns], line_season: int, position_rate: float,
) -> tuple[float, float]:
    """Recency-weighted TD rate shrunk toward the position, as (probability, weighted games)."""
    rate, weighted_games = anytime_td_rate(seasons, line_season, position_rate)
    return round(1 - exp(-rate), 2), round(weighted_games, 2)


def quality_flags(averages: NflHistoricalAverages) -> list[str]:
    flags = ["historical_baseline", "live_line_unavailable"]
    if averages.games < MIN_BASELINE_GAMES:
        flags.append("small_sample")
    return flags


def edge_is_comparable(market: NflPropMarket, games: int, segment: str, odds_type: str | None) -> bool:
    """Whether baseline minus line measures a mispricing worth ranking.

    A thin sample still gets a baseline and the `small_sample` flag, but not an
    edge: one game with no catches would otherwise rank as a confident under.
    Goblin and demon lines and non-full-game segments are refused for the
    reasons given in `line_quality_flags`. Anytime TD is refused until build-plan
    item 25c: the model sits well below the de-vigged book, so probability minus
    the 0.5 line would label nearly every scorer an under.
    """
    return (
        market is not NflPropMarket.ANYTIME_TOUCHDOWN
        and games >= MIN_BASELINE_GAMES
        and segment == "full_game"
        and odds_type == STANDARD_ODDS_TYPE
    )


def edge(projection: float | None, line: float | None) -> float | None:
    """How far the baseline sits above (positive) or below (negative) the line.

    None when either side is missing, because an unlinked line and a line we
    happen to agree with are different facts and must not both read as 0.0.
    """
    if projection is None or line is None:
        return None
    return round(projection - line, 2)


def slate_line_rank(edge_value: float | None, quality_flags: list[str]) -> tuple[int, float]:
    """Sort key placing current-season edges above stale ones, then unpriced rows.

    Early in a season most baselines fall back to the previous one, so ranking
    by edge size alone floats a stale baseline's disagreement above every edge
    measured against the season being played.
    """
    if edge_value is None:
        return (2, 0.0)
    tier = 1 if STALE_BASELINE_SEASON_FLAG in quality_flags else 0
    return (tier, -abs(edge_value))


def line_quality_flags(
    averages: NflHistoricalAverages,
    baseline_season: int | None = None,
    line_season: int | None = None,
    segment: str | None = None,
    odds_type: str | None = None,
    current_season_games: int | None = None,
) -> list[str]:
    """Quality flags for a baseline priced against a real market line.

    `current_season_games` is the line season's own count when the baseline
    blends in last season, so a blend of 22 games still reads as a season in
    progress.
    """
    flags = ["historical_baseline"]
    if averages.games < MIN_BASELINE_GAMES:
        flags.append("small_sample")
    # Goblin and demon lines are moved off the market price on purpose, with the
    # payout adjusted, so the gap measures the ladder rather than a mispricing.
    if odds_type is not None and odds_type != STANDARD_ODDS_TYPE:
        flags.append("non_standard_line")
    if baseline_season is not None and line_season is not None:
        if baseline_season != line_season:
            # A 2024 baseline against a 2026 line is not a disagreement with the
            # market, it is a comparison across two different things.
            flags.append(STALE_BASELINE_SEASON_FLAG)
        elif (averages.games if current_season_games is None else current_season_games) < FULL_SEASON_GAMES:
            # Right season, but one still being played, so the average will move.
            # Distinct from small_sample: 12 games is plenty to bet on and still
            # not a finished season.
            flags.append("partial_season_baseline")
    # Baselines are whole-game averages, so any other segment is not comparable.
    if segment is not None and segment != "full_game":
        flags.append("segment_mismatch")
    return flags

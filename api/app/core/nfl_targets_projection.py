"""Pure Rec Targets baseline and development candidates for item 39a."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from math import isfinite

from app.core.nfl_baseline import MIN_BASELINE_GAMES, SeasonGames, choose_baseline_season

NFL_TARGETS_MODEL_VERSION = "nfl-targets-v1"
TARGETS_RECENT_GAMES = 5
TARGETS_RECENT_WEIGHT = 0.5
TARGETS_MONEYLINE_CAP = 0.08
# Frozen by 39a's 2024 run, which rejected both candidates; changing either needs a new version.
SELECTED_MONEYLINE_SCALING = False
SELECTED_RECENT_FORM = False


@dataclass(frozen=True)
class TargetsObservation:
    game_id: int
    season: int
    week: int
    start_utc: datetime | None
    targets: float | None


@dataclass(frozen=True)
class TargetsProjectionInput:
    season: int
    week: int
    observations: tuple[TargetsObservation, ...]
    home_market_prob: float | None = None
    player_is_home: bool | None = None


@dataclass(frozen=True)
class TargetsProjection:
    projection: float | None
    baseline_season: int | None
    baseline_reason: str
    games_in_sample: int
    recent_games: int
    quality_flags: tuple[str, ...]


@dataclass(frozen=True)
class TargetsReplayRow:
    player_id: int
    game_id: int
    week: int
    position: str
    input: TargetsProjectionInput
    actual: float | None


def valid_target_count(value: float | None) -> bool:
    return value is not None and isfinite(value) and value >= 0


def prior_targets(input: TargetsProjectionInput) -> tuple[TargetsObservation, ...]:
    """Known counts strictly before the target week, newest first."""
    return tuple(sorted(
        (
            observation for observation in input.observations
            if (observation.season, observation.week) < (input.season, input.week)
            and valid_target_count(observation.targets)
        ),
        key=lambda observation: (
            observation.season, observation.week, observation.start_utc is not None,
            observation.start_utc or datetime.min.replace(tzinfo=UTC), observation.game_id,
        ),
        reverse=True,
    ))


def _mean(observations: tuple[TargetsObservation, ...]) -> float:
    return sum(item.targets for item in observations if item.targets is not None) / len(observations)


def _moneyline_factor(input: TargetsProjectionInput) -> tuple[float, tuple[str, ...]]:
    probability = input.home_market_prob
    flags = []
    if probability is None or not isfinite(probability) or not 0 < probability < 1:
        flags.append("market_missing")
    if input.player_is_home is None:
        flags.append("team_not_in_game")
    if flags:
        return 1.0, tuple(flags)
    assert probability is not None
    team_probability = probability if input.player_is_home else 1 - probability
    adjustment = max(-TARGETS_MONEYLINE_CAP, min(TARGETS_MONEYLINE_CAP, team_probability - 0.5))
    return 1 + adjustment, ()


def project_targets(
    input: TargetsProjectionInput,
    *,
    moneyline_scaled: bool = SELECTED_MONEYLINE_SCALING,
    recent_form: bool = SELECTED_RECENT_FORM,
) -> TargetsProjection:
    history = prior_targets(input)
    seasons = sorted({item.season for item in history})
    choice = choose_baseline_season(input.season, [
        SeasonGames(season, sum(item.season == season for item in history)) for season in seasons
    ])
    recent = history[:TARGETS_RECENT_GAMES]
    if choice.games < MIN_BASELINE_GAMES:
        flag = "no_baseline" if choice.season is None else "small_sample"
        return TargetsProjection(None, choice.season, choice.reason, choice.games, len(recent), (flag,))

    baseline = _mean(tuple(item for item in history if item.season == choice.season))
    projection = (
        (1 - TARGETS_RECENT_WEIGHT) * baseline + TARGETS_RECENT_WEIGHT * _mean(recent)
        if recent_form else baseline
    )
    flags = ("stale_baseline_season",) if choice.season != input.season else ()
    if moneyline_scaled:
        factor, market_flags = _moneyline_factor(input)
        projection *= factor
        flags += market_flags
    return TargetsProjection(
        round(projection, 2), choice.season, choice.reason, choice.games, len(recent), flags,
    )

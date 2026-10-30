"""NFL prop distributions as team volume x player share x per-opportunity efficiency.

Team volume comes from the game's implied team total and margin, so a big
favourite runs more and an underdog throws more. The player's share of that
volume and their efficiency per opportunity are shrunk toward their position,
so a thin history leans on the position rather than on a few games. The result
is a whole distribution per market (item 49a), not a mean.

Pure: no DB, no I/O. Every constant arrives in `VolumeParameters`; the fitted
values are chosen by the 49a rolling-origin backtest.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from app.core.nfl_game_environment import team_lines
from app.core.nfl_projection_backtest import REPLAY_MARKETS_BY_POSITION
from app.core.outcome_distribution import CompoundYards, NegativeBinomial

# 49a's own history floor (invariant 11): the backfill reaches 2018, and the
# rolling origins fit on 2018 through the season before each scored one.
VOLUME_FIRST_HISTORY_SEASON = 2018

NO_HISTORY = "no games this season or last"
NO_FIT = "no fitted constants for this market and position"
NO_OPPORTUNITIES = "no recorded opportunities this season or last"

Volume = Literal["pass", "rush"]


@dataclass(frozen=True)
class MarketSpec:
    opportunity: str
    volume: Volume
    rate: str | None
    yards: bool


# The opportunity stat is also the share's name: a target share is targets over
# team pass attempts, a carry share is carries over team rush attempts.
MARKET_SPECS: dict[str, MarketSpec] = {
    "receptions": MarketSpec("targets", "pass", "receptions", yards=False),
    "receiving_yards": MarketSpec("targets", "pass", "receiving_yards", yards=True),
    "rushing_attempts": MarketSpec("rushing_attempts", "rush", None, yards=False),
    "rushing_yards": MarketSpec("rushing_attempts", "rush", "rushing_yards", yards=True),
    "passing_attempts": MarketSpec("passing_attempts", "pass", None, yards=False),
    "passing_completions": MarketSpec("passing_attempts", "pass", "passing_completions", yards=False),
    "passing_yards": MarketSpec("passing_attempts", "pass", "passing_yards", yards=True),
}


@dataclass(frozen=True)
class PlayerGame:
    """One completed regular-season game: the player's stats and their team's attempts."""

    season: int
    week: int
    stats: Mapping[str, float | None]
    team_pass_attempts: float
    team_rush_attempts: float


@dataclass(frozen=True)
class GameContext:
    season: int
    week: int
    implied_team_total: float
    implied_margin: float


@dataclass(frozen=True)
class TeamVolumeFit:
    intercept: float
    total_slope: float
    margin_slope: float

    def expected(self, game: GameContext) -> float:
        # A linear fit can dip below zero far outside its data; no team runs
        # negative plays, so the floor is zero rather than an error.
        value = self.intercept + self.total_slope * game.implied_team_total + self.margin_slope * game.implied_margin
        return max(0.0, value)


@dataclass(frozen=True)
class VolumeParameters:
    pass_volume: TeamVolumeFit
    rush_volume: TeamVolumeFit
    previous_season_weight: float
    k_share: float
    k_rate: Mapping[str, float]
    position_share: Mapping[tuple[str, str], float]
    position_rate: Mapping[tuple[str, str], float]
    dispersion: Mapping[tuple[str, str], float]
    yards_sd: Mapping[tuple[str, str], float]


Distribution = NegativeBinomial | CompoundYards


@dataclass(frozen=True)
class PlayerProjection:
    distributions: Mapping[str, Distribution]
    skipped: Mapping[str, str]


def game_context(season: int, week: int, home_spread_margin: float, total: float, is_home: bool) -> GameContext:
    team_total, margin = team_lines(home_spread_margin, total, is_home)
    return GameContext(season, week, team_total, margin)


def prior_games(history: Sequence[PlayerGame], game: GameContext) -> list[PlayerGame]:
    """Games before this one, from this season and last only."""
    return [
        past for past in history
        if (past.season == game.season and past.week < game.week) or past.season == game.season - 1
    ]


def _season_weight(past: PlayerGame, game: GameContext, previous_weight: float) -> float:
    return 1.0 if past.season == game.season else previous_weight


def _team_attempts(past: PlayerGame, volume: Volume) -> float:
    return past.team_pass_attempts if volume == "pass" else past.team_rush_attempts


def shrunk_share(
    games: Sequence[PlayerGame], game: GameContext, spec: MarketSpec, prior: float, k: float, previous_weight: float,
) -> float | None:
    """Share of team volume, each season pooled, weighted by games, shrunk with `k` prior games."""
    weighted_games = weighted_share = 0.0
    for season in (game.season, game.season - 1):
        rows = [
            past for past in games
            if past.season == season and past.stats.get(spec.opportunity) is not None
            and _team_attempts(past, spec.volume) > 0
        ]
        if not rows:
            continue
        share = sum(past.stats[spec.opportunity] for past in rows) / sum(_team_attempts(past, spec.volume) for past in rows)
        weight = len(rows) * _season_weight(rows[0], game, previous_weight)
        weighted_games += weight
        weighted_share += weight * share
    if weighted_games == 0:
        return None
    return (weighted_share + k * prior) / (weighted_games + k)


def shrunk_rate(
    games: Sequence[PlayerGame], game: GameContext, spec: MarketSpec, prior: float, k: float, previous_weight: float,
) -> float:
    """Rate per opportunity, last season's games discounted, shrunk with `k` prior opportunities."""
    numerator = denominator = 0.0
    for past in games:
        made, opportunities = past.stats.get(spec.rate or ""), past.stats.get(spec.opportunity)
        if made is None or opportunities is None:
            continue
        weight = _season_weight(past, game, previous_weight)
        numerator += weight * made
        denominator += weight * opportunities
    return (numerator + k * prior) / (denominator + k)


def _market_distribution(
    position: str, market: str, games: Sequence[PlayerGame], game: GameContext, params: VolumeParameters,
) -> Distribution | str:
    spec = MARKET_SPECS[market]
    key = (market, position)
    share_prior = params.position_share.get((position, spec.opportunity))
    rate_prior = params.position_rate.get((position, spec.rate)) if spec.rate else None
    needs = [share_prior, params.dispersion.get(key)]
    if spec.rate:
        needs += [rate_prior, params.k_rate.get(market)]
    if spec.yards:
        needs.append(params.yards_sd.get(key))
    if any(value is None for value in needs):
        return NO_FIT

    share = shrunk_share(games, game, spec, share_prior, params.k_share, params.previous_season_weight)
    if share is None:
        return NO_OPPORTUNITIES
    volume = params.pass_volume if spec.volume == "pass" else params.rush_volume
    opportunities = volume.expected(game) * share
    if spec.rate is None:
        return NegativeBinomial(opportunities, params.dispersion[key])
    rate = shrunk_rate(games, game, spec, rate_prior, params.k_rate[market], params.previous_season_weight)
    if spec.yards:
        return CompoundYards(NegativeBinomial(opportunities, params.dispersion[key]), rate, params.yards_sd[key])
    return NegativeBinomial(opportunities * rate, params.dispersion[key])


def project_player(
    position: str, history: Sequence[PlayerGame], game: GameContext, params: VolumeParameters,
) -> PlayerProjection:
    """One distribution per modelled market for this position, from games before `game` only."""
    markets = [market for market in REPLAY_MARKETS_BY_POSITION.get(position, ()) if market in MARKET_SPECS]
    games = prior_games(history, game)
    if not games:
        return PlayerProjection({}, {market: NO_HISTORY for market in markets})
    distributions: dict[str, Distribution] = {}
    skipped: dict[str, str] = {}
    for market in markets:
        result = _market_distribution(position, market, games, game, params)
        if isinstance(result, str):
            skipped[market] = result
        else:
            distributions[market] = result
    return PlayerProjection(distributions, skipped)

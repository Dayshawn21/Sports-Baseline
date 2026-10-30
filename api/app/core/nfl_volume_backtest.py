"""Rolling-origin fitting and scoring for the 49a volume x efficiency projection.

Two arms are fitted on the same fit seasons and scored on the season after:
the volume arm (`nfl_volume_projection`) and a reference arm, v4's core
baseline with 27g's ratio quantiles, which is the distribution v4 would give
without its matchup, usage and weather adjustments.

Pure: no DB, no I/O.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from math import floor
from typing import Literal

import numpy as np

from app.core.nfl_baseline import MIN_BASELINE_GAMES
from app.core.nfl_over_probability import ratio_cdf, ratio_quantiles
from app.core.nfl_over_probability_calibration import (
    MAX_BIN_GAP,
    MAX_ECE,
    CalibrationPair,
    calibrate,
    synthetic_lines,
)
from app.core.nfl_projection_backtest import REPLAY_MARKETS_BY_POSITION
from app.core.nfl_season_blend import PREVIOUS_SEASON_WEIGHT
from app.core.nfl_volume_projection import (
    MARKET_SPECS,
    VOLUME_FIRST_HISTORY_SEASON,
    GameContext,
    MarketSpec,
    PlayerGame,
    TeamVolumeFit,
    VolumeParameters,
    game_context,
    prior_games,
    project_player,
    shrunk_rate,
    shrunk_share,
)
from app.core.outcome_distribution import count_crps, yards_crps, yards_grid

# A fit needs at least two cases in a (market, position) group, so a spread or
# a dispersion can be estimated at all; smaller groups leave the cohort.
MIN_GROUP_CASES = 2

VOLUME_STATS = (
    "passing_attempts", "passing_completions", "passing_yards", "rushing_attempts", "rushing_yards",
    "targets", "receptions", "receiving_yards",
)


@dataclass(frozen=True)
class VolumePlayerGame:
    player_id: int
    game_id: int
    season: int
    week: int
    position: str
    team_id: int
    is_home: bool
    stats: dict[str, float | None]
    target_share: float | None
    offense_snaps: int | None


@dataclass(frozen=True)
class VolumeTeamGame:
    game_id: int
    team_id: int
    season: int
    week: int
    is_home: bool
    pass_attempts: float | None
    rush_attempts: float | None
    plays: int | None
    home_spread_margin: float | None
    total: float | None


@dataclass(frozen=True)
class VolumeHistory:
    player_games: list[VolumePlayerGame]
    team_games: list[VolumeTeamGame]


@dataclass(frozen=True)
class VolumeCase:
    """One player-game: what was known before kickoff, and what happened."""

    player_id: int
    game_id: int
    season: int
    position: str
    game: GameContext
    history: tuple[PlayerGame, ...]
    actuals: Mapping[str, float]
    # The game itself, team attempts included, for fitting volume, priors and spread.
    result: PlayerGame


def modelled_markets(position: str) -> tuple[str, ...]:
    return tuple(market for market in REPLAY_MARKETS_BY_POSITION.get(position, ()) if market in MARKET_SPECS)


def build_cases(history: VolumeHistory) -> list[VolumeCase]:
    """A case per player-game whose game has closing lines and team attempts."""
    teams = {(team.game_id, team.team_id): team for team in history.team_games}
    by_player: dict[int, list[PlayerGame]] = defaultdict(list)
    cases: list[VolumeCase] = []
    for row in sorted(history.player_games, key=lambda g: (g.player_id, g.season, g.week)):
        team = teams.get((row.game_id, row.team_id))
        if team is None or team.pass_attempts is None or team.rush_attempts is None:
            continue
        past = by_player[row.player_id]
        result = PlayerGame(row.season, row.week, row.stats, team.pass_attempts, team.rush_attempts)
        if team.home_spread_margin is not None and team.total is not None:
            game = game_context(row.season, row.week, team.home_spread_margin, team.total, row.is_home)
            actuals = {
                market: row.stats[market] for market in modelled_markets(row.position)
                if row.stats.get(market) is not None
            }
            if actuals:
                cases.append(VolumeCase(
                    row.player_id, row.game_id, row.season, row.position, game,
                    tuple(prior_games(past, game)), actuals, result,
                ))
        past.append(result)
    return cases


def in_seasons(cases: Iterable[VolumeCase], seasons: Iterable[int]) -> list[VolumeCase]:
    wanted = set(seasons)
    return [case for case in cases if case.season in wanted]


def reference_projection(case: VolumeCase, market: str, position_average: float) -> float | None:
    """v4's core baseline: the season blend, regressed to the position over `MIN_BASELINE_GAMES`.

    The same arithmetic as `blend_averages` then `model_projection` with every
    adjustment off: per-game averages weighted by games, last season at
    `PREVIOUS_SEASON_WEIGHT`, mixed linearly toward the position until four games.
    """
    totals = {case.game.season: [0.0, 0], case.game.season - 1: [0.0, 0]}
    for past in case.history:
        value = past.stats.get(market)
        if value is not None:
            totals[past.season][0] += value
            totals[past.season][1] += 1
    (current_sum, current_games), (previous_sum, previous_games) = totals[case.game.season], totals[case.game.season - 1]
    games = current_games + previous_games
    if games == 0:
        return None
    current_weight, previous_weight = current_games, PREVIOUS_SEASON_WEIGHT * previous_games
    blended = (
        (current_sum / current_games if current_games else 0.0) * current_weight
        + (previous_sum / previous_games if previous_games else 0.0) * previous_weight
    ) / (current_weight + previous_weight)
    weight = min(1.0, games / MIN_BASELINE_GAMES)
    return blended * weight + position_average * (1.0 - weight)


@dataclass(frozen=True)
class ReferenceFit:
    position_average: Mapping[tuple[str, str], float]
    quantiles: Mapping[tuple[str, str], tuple[float, ...]]


def fit_reference(cases: Sequence[VolumeCase], fit_seasons: Iterable[int]) -> ReferenceFit:
    """Position averages and ratio quantiles per (market, position), from fit seasons only."""
    fit_cases = in_seasons(cases, fit_seasons)
    actuals: dict[tuple[str, str], list[float]] = defaultdict(list)
    for case in fit_cases:
        for market, actual in case.actuals.items():
            actuals[(market, case.position)].append(actual)
    position_average = {
        key: sum(values) / len(values) for key, values in actuals.items() if len(values) >= MIN_GROUP_CASES
    }
    pairs: dict[tuple[str, str], list[tuple[float, float]]] = defaultdict(list)
    for case in fit_cases:
        for market, actual in case.actuals.items():
            key = (market, case.position)
            if key not in position_average:
                continue
            projection = reference_projection(case, market, position_average[key])
            if projection is not None and projection > 0:
                pairs[key].append((projection, actual))
    quantiles = {key: ratio_quantiles(values) for key, values in pairs.items() if len(values) >= MIN_GROUP_CASES}
    return ReferenceFit(
        position_average={key: value for key, value in position_average.items() if key in quantiles},
        quantiles=quantiles,
    )


@dataclass(frozen=True)
class ReferenceDistribution:
    """The reference arm's forecast: ratio quantiles scaled by the projection."""

    quantiles: tuple[float, ...]
    projection: float
    is_count: bool

    def cdf(self, x: float) -> float:
        return ratio_cdf(self.quantiles, self.projection, x)

    def crps(self, actual: float) -> float:
        if self.is_count:
            top = floor(self.projection * self.quantiles[-1]) + 1
            return count_crps(np.array([self.cdf(k) for k in range(top + 1)]), actual)
        points = yards_grid(actual)
        return yards_crps(points, np.array([self.cdf(y) for y in points]), actual)


def reference_distribution(case: VolumeCase, market: str, fit: ReferenceFit) -> ReferenceDistribution | None:
    key = (market, case.position)
    if key not in fit.quantiles:
        return None
    projection = reference_projection(case, market, fit.position_average[key])
    if projection is None or projection <= 0:
        return None
    return ReferenceDistribution(fit.quantiles[key], projection, is_count=not MARKET_SPECS[market].yards)


# Fixed before any scored season was read (49a spec). Extended downward on
# 2026-10-30 after a fit on 2018-2020 chose the smallest K for the share and
# two rates. The search runs share first, then each rate on its own market, so
# it is 7 + 7 x rate markets fits, not a product.
K_SHARE_GRID = (0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0)
K_RATE_GRID = (2.0, 5.0, 10.0, 25.0, 50.0, 100.0, 200.0)
# Rates sit at the grid's middle while the share is searched.
SEARCH_START_K_RATE = K_RATE_GRID[len(K_RATE_GRID) // 2]
# A group whose counts vary no more than a Poisson's gets this nearly Poisson
# dispersion instead of an infinite or negative one.
MAX_DISPERSION = 1000.0
TIE_RELATIVE_TOLERANCE = 1e-9
RATE_MARKETS = tuple(market for market, spec in MARKET_SPECS.items() if spec.rate)


@dataclass(frozen=True)
class VolumeFit:
    params: VolumeParameters
    share_crps: Mapping[float, float]
    rate_crps: Mapping[str, Mapping[float, float]]


def _team_attempts(game: PlayerGame, volume: str) -> float:
    return game.team_pass_attempts if volume == "pass" else game.team_rush_attempts


def _team_volume_fit(cases: Sequence[VolumeCase], volume: str) -> TeamVolumeFit:
    """OLS of team attempts on implied team total and margin, one row per team-game."""
    rows: dict[tuple[int, float], tuple[float, float, float]] = {}
    for case in cases:
        rows[(case.game_id, case.game.implied_margin)] = (
            case.game.implied_team_total, case.game.implied_margin, _team_attempts(case.result, volume),
        )
    if len(rows) < 3:
        raise ValueError(f"a team volume fit needs at least 3 team-games, got {len(rows)}")
    data = np.array(list(rows.values()))
    design = np.column_stack([np.ones(len(data)), data[:, 0], data[:, 1]])
    (intercept, total_slope, margin_slope), *_ = np.linalg.lstsq(design, data[:, 2], rcond=None)
    return TeamVolumeFit(float(intercept), float(total_slope), float(margin_slope))


def _position_priors(cases: Sequence[VolumeCase]) -> tuple[dict[tuple[str, str], float], dict[tuple[str, str], float]]:
    """Mean per-game share and pooled rate per (position, stat), from the cases' own games."""
    shares: dict[tuple[str, str], list[float]] = defaultdict(list)
    rates: dict[tuple[str, str], list[float]] = defaultdict(lambda: [0.0, 0.0])
    for case in cases:
        specs = [MARKET_SPECS[market] for market in modelled_markets(case.position)]
        for opportunity, volume in {(spec.opportunity, spec.volume) for spec in specs}:
            opportunities = case.result.stats.get(opportunity)
            attempts = _team_attempts(case.result, volume)
            if opportunities is not None and attempts > 0:
                shares[(case.position, opportunity)].append(opportunities / attempts)
        for opportunity, rate in {(spec.opportunity, spec.rate) for spec in specs if spec.rate}:
            opportunities, made = case.result.stats.get(opportunity), case.result.stats.get(rate)
            if opportunities is not None and made is not None:
                rates[(case.position, rate)][0] += made
                rates[(case.position, rate)][1] += opportunities
    share_priors = {key: sum(values) / len(values) for key, values in shares.items()}
    rate_priors = {key: made / opportunities for key, (made, opportunities) in rates.items() if opportunities > 0}
    return share_priors, rate_priors


@dataclass(frozen=True)
class _Mean:
    position: str
    market: str
    opportunities: float
    rate: float | None
    result: PlayerGame


def _means(cases: Sequence[VolumeCase], params: VolumeParameters) -> list[_Mean]:
    """Each (case, market)'s expected opportunities and rate under `params`' K values."""
    means = []
    for case in cases:
        if not case.history:
            continue
        for market in case.actuals:
            spec = MARKET_SPECS[market]
            share_prior = params.position_share.get((case.position, spec.opportunity))
            rate_prior = params.position_rate.get((case.position, spec.rate)) if spec.rate else None
            if share_prior is None or (spec.rate and rate_prior is None):
                continue
            share = shrunk_share(case.history, case.game, spec, share_prior, params.k_share, params.previous_season_weight)
            if share is None:
                continue
            rate = None
            if spec.rate and rate_prior is not None:
                rate = shrunk_rate(
                    case.history, case.game, spec, rate_prior, params.k_rate[market], params.previous_season_weight,
                )
            volume = params.pass_volume if spec.volume == "pass" else params.rush_volume
            means.append(_Mean(case.position, market, volume.expected(case.game) * share, rate, case.result))
    return means


def _dispersion(pairs: Sequence[tuple[float, float]]) -> float:
    """Method of moments for r in variance = mean + mean**2 / r, from (observed, expected)."""
    excess = sum((observed - expected) ** 2 - expected for observed, expected in pairs)
    squared = sum(expected**2 for _, expected in pairs)
    if excess <= 0 or squared <= 0:
        return MAX_DISPERSION
    return min(MAX_DISPERSION, squared / excess)


def _yards_sd(group: Sequence[_Mean], spec: MarketSpec, market: str) -> float | None:
    """Per-opportunity sd: var(yards | N) = N * sd**2, pooled over games with N > 0."""
    residual = opportunities_total = 0.0
    for mean in group:
        n, yards = mean.result.stats.get(spec.opportunity), mean.result.stats.get(market)
        if n is None or yards is None or n <= 0 or mean.rate is None:
            continue
        residual += (yards - n * mean.rate) ** 2
        opportunities_total += n
    if opportunities_total <= 0 or residual <= 0:
        return None
    return (residual / opportunities_total) ** 0.5


def _spreads(means: Sequence[_Mean]) -> tuple[dict[tuple[str, str], float], dict[tuple[str, str], float]]:
    groups: dict[tuple[str, str], list[_Mean]] = defaultdict(list)
    for mean in means:
        groups[(mean.market, mean.position)].append(mean)
    dispersion: dict[tuple[str, str], float] = {}
    yards_sd: dict[tuple[str, str], float] = {}
    for (market, position), group in groups.items():
        if len(group) < MIN_GROUP_CASES:
            continue
        spec = MARKET_SPECS[market]
        # A yards market's dispersion belongs to its opportunity count N.
        observed_stat = spec.opportunity if spec.yards else market
        pairs = [
            (mean.result.stats[observed_stat], mean.opportunities * (mean.rate if spec.rate and not spec.yards else 1.0))
            for mean in group if mean.result.stats.get(observed_stat) is not None
        ]
        dispersion[(market, position)] = _dispersion(pairs)
        if spec.yards:
            sd = _yards_sd(group, spec, market)
            if sd is not None:
                yards_sd[(market, position)] = sd
    return dispersion, yards_sd


def _complete(cases: Sequence[VolumeCase], params: VolumeParameters) -> VolumeParameters:
    dispersion, yards_sd = _spreads(_means(cases, params))
    return replace(params, dispersion=dispersion, yards_sd=yards_sd)


def total_crps(cases: Sequence[VolumeCase], params: VolumeParameters, markets: Iterable[str] | None = None) -> float:
    wanted = set(markets) if markets is not None else None
    total = 0.0
    for case in cases:
        scored = [m for m in case.actuals if wanted is None or m in wanted]
        if not scored:
            continue
        distributions = project_player(case.position, case.history, case.game, params).distributions
        total += sum(distributions[m].crps(case.actuals[m]) for m in scored if m in distributions)
    return total


def best_k(scores: Mapping[float, float]) -> float:
    """The K with the lowest score; a tie keeps the smaller K.

    Grids are ascending and only a clearly lower score moves the choice, so when
    the data cannot tell two K apart the choice is the one that shrinks more.
    Scores within `TIE_RELATIVE_TOLERANCE` are a tie: rounding, not evidence.
    """
    best = next(iter(scores))
    for k, score in scores.items():
        if score < scores[best] * (1.0 - TIE_RELATIVE_TOLERANCE):
            best = k
    return best


def fit_volume(cases: Sequence[VolumeCase], fit_seasons: Iterable[int]) -> VolumeFit:
    """Every volume-arm constant, fitted on fit-season cases only."""
    fit_cases = in_seasons(cases, fit_seasons)
    share_priors, rate_priors = _position_priors(fit_cases)
    base = VolumeParameters(
        pass_volume=_team_volume_fit(fit_cases, "pass"),
        rush_volume=_team_volume_fit(fit_cases, "rush"),
        previous_season_weight=PREVIOUS_SEASON_WEIGHT,
        k_share=K_SHARE_GRID[0],
        k_rate={market: SEARCH_START_K_RATE for market in RATE_MARKETS},
        position_share=share_priors,
        position_rate=rate_priors,
        dispersion={},
        yards_sd={},
    )
    share_crps = {k: total_crps(fit_cases, _complete(fit_cases, replace(base, k_share=k))) for k in K_SHARE_GRID}
    base = replace(base, k_share=best_k(share_crps))
    chosen = dict(base.k_rate)
    rate_crps: dict[str, dict[float, float]] = {}
    for market in RATE_MARKETS:
        rate_crps[market] = {
            k: total_crps(fit_cases, _complete(fit_cases, replace(base, k_rate=chosen | {market: k})), [market])
            for k in K_RATE_GRID
        }
        chosen[market] = best_k(rate_crps[market])
    return VolumeFit(_complete(fit_cases, replace(base, k_rate=chosen)), share_crps, rate_crps)


# The adoption rule, pre-registered before any scored season is read (49a).
SCORED_SEASONS = (2021, 2022, 2023, 2024, 2025)
MIN_SEASON_CASES = 300
SE_MULTIPLE = 2.0
MIN_SEASONS_WON = 4
SHARE_BELOW_RANGE = (0.47, 0.53)
# ECE and the worst-bin gap use 27g's thresholds and its 200-pair bin floor.
CALIBRATION_MAX_ECE = MAX_ECE
CALIBRATION_MAX_BIN_GAP = MAX_BIN_GAP

Verdict = Literal["adopt", "reject", "insufficient"]


@dataclass(frozen=True)
class ScoredPair:
    """One (player, game, market) both arms forecast, scored against what happened."""

    player_id: int
    game_id: int
    market: str
    position: str
    season: int
    volume_crps: float
    reference_crps: float
    # Volume P(over) at the reference arm's synthetic lines, one pair per line.
    over_pairs: tuple[CalibrationPair, ...]
    # 1 below the volume median, 0 above, 0.5 on it: a count often lands on its
    # median, and counting those as half keeps a calibrated median at 0.5.
    below_median: float

    @property
    def key(self) -> tuple[int, int, str]:
        return (self.player_id, self.game_id, self.market)

    @property
    def difference(self) -> float:
        return self.volume_crps - self.reference_crps


@dataclass(frozen=True)
class OriginScore:
    season: int
    pairs: tuple[ScoredPair, ...]
    # (market, reason) -> (case, market) forecasts left out of the common cohort.
    excluded: Mapping[tuple[str, str], int]
    volume_fit: VolumeFit
    reference_fit: ReferenceFit


def _below_median(actual: float, median: float) -> float:
    if actual < median:
        return 1.0
    return 0.5 if actual == median else 0.0


def score_origin(cases: Sequence[VolumeCase], season: int) -> OriginScore:
    """Fit both arms on the floor season to `season - 1`, then score `season`'s common cohort."""
    scored_cases = in_seasons(cases, [season])
    if not scored_cases:
        raise ValueError(f"no cases in season {season}")
    fit_seasons = range(VOLUME_FIRST_HISTORY_SEASON, season)
    volume_fit = fit_volume(cases, fit_seasons)
    reference_fit = fit_reference(cases, fit_seasons)
    pairs: list[ScoredPair] = []
    excluded: dict[tuple[str, str], int] = defaultdict(int)
    for case in scored_cases:
        volume = project_player(case.position, case.history, case.game, volume_fit.params).distributions
        for market, actual in case.actuals.items():
            reference = reference_distribution(case, market, reference_fit)
            if market not in volume or reference is None:
                reason = "no volume forecast" if market not in volume else "no reference forecast"
                excluded[(market, reason)] += 1
                continue
            forecast = volume[market]
            pairs.append(ScoredPair(
                case.player_id, case.game_id, market, case.position, season,
                volume_crps=forecast.crps(actual), reference_crps=reference.crps(actual),
                over_pairs=tuple(
                    CalibrationPair(forecast.p_over(line).over, actual > line)
                    for line in synthetic_lines(reference.projection)
                ),
                below_median=_below_median(actual, forecast.median()),
            ))
    return OriginScore(season, tuple(pairs), dict(excluded), volume_fit, reference_fit)


def clustered_se(values: Sequence[float], clusters: Sequence[int]) -> float:
    """Standard error of the mean of `values`, clustered by `clusters` (here, games)."""
    n = len(values)
    groups = len(set(clusters))
    if n == 0 or groups < 2:
        raise ValueError("a clustered standard error needs at least two clusters")
    mean = sum(values) / n
    sums: dict[int, float] = defaultdict(float)
    for value, cluster in zip(values, clusters, strict=True):
        sums[cluster] += value - mean
    variance = sum(total**2 for total in sums.values()) / n**2 * groups / (groups - 1)
    return variance**0.5


@dataclass(frozen=True)
class MarketVerdict:
    market: str
    cases_by_season: Mapping[int, int]
    mean_difference: float | None
    standard_error: float | None
    seasons_won: int
    ece: float | None
    worst_gap: float | None
    share_below: float | None
    failed: tuple[str, ...]
    verdict: Verdict


def verdict(market: str, pairs: Sequence[ScoredPair]) -> MarketVerdict:
    """Apply the pre-registered rule to one market's pairs, pooled over the scored seasons."""
    own = [pair for pair in pairs if pair.market == market]
    by_season = {season: [pair for pair in own if pair.season == season] for season in SCORED_SEASONS}
    counts = {season: len(rows) for season, rows in by_season.items()}
    if any(count < MIN_SEASON_CASES for count in counts.values()):
        return MarketVerdict(market, counts, None, None, 0, None, None, None, ("cases",), "insufficient")

    differences = [pair.difference for pair in own]
    mean_difference = sum(differences) / len(differences)
    standard_error = clustered_se(differences, [pair.game_id for pair in own])
    seasons_won = sum(
        1 for rows in by_season.values()
        if sum(p.volume_crps for p in rows) < sum(p.reference_crps for p in rows)
    )
    report = calibrate([over for pair in own for over in pair.over_pairs])
    share_below = sum(pair.below_median for pair in own) / len(own)

    failed = []
    if not mean_difference < -SE_MULTIPLE * standard_error:
        failed.append("crps")
    if seasons_won < MIN_SEASONS_WON:
        failed.append("seasons")
    if report.ece > CALIBRATION_MAX_ECE or (report.worst_gap is not None and report.worst_gap > CALIBRATION_MAX_BIN_GAP):
        failed.append("calibration")
    if not SHARE_BELOW_RANGE[0] <= share_below <= SHARE_BELOW_RANGE[1]:
        failed.append("median")
    return MarketVerdict(
        market, counts, mean_difference, standard_error, seasons_won, report.ece, report.worst_gap, share_below,
        tuple(failed), "reject" if failed else "adopt",
    )

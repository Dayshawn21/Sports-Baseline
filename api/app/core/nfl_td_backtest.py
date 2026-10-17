"""Replay anytime-TD predictions week by week and score them against outcomes.

Every input a case carries is built only from rows strictly before its week, with
the same regular-season cutoff and position-rate choice the live slate uses, so a
backtest score describes what the model would have said at the time.

Pure: no DB, no I/O. Later role signals extend `NflTdBacktestCase` (as snap share
did in 19m) rather than building a second harness.
"""
from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from itertools import groupby
from math import exp, log, log1p
from typing import Literal

from app.core.nfl_baseline import MIN_BASELINE_GAMES, SeasonGames, choose_baseline_season
from app.core.nfl_game_script import scoring_environment_probability
from app.core.nfl_end_zone import NflEndZoneCoefficients, NflEndZoneSeason, end_zone_target_rate, end_zone_td_probability
from app.core.odds import implied_prob_from_american
from app.core.nfl_projection import NflSeasonTouchdowns, anytime_td_rate, td_seasons_used
from app.core.nfl_red_zone import (
    NflRedZoneCoefficients,
    NflRedZoneRates,
    NflRedZoneSeason,
    red_zone_rates,
    red_zone_td_probability,
)
from app.core.nfl_snap_share import (
    RECENT_SNAP_WINDOW,
    SNAP_SHARE_BLEND_WEIGHT,
    SNAP_SHARE_COEFFICIENTS,
    NflSnapCoefficients,
    NflSnapSeason,
    recent_snap_share,
    season_snap_share,
    snap_td_probability,
)

EVALUATED_POSITIONS = frozenset({"QB", "RB", "WR", "TE"})
# Fixed before the 2025 holdout was scored; QB and WR stay on the baseline in both arms.
SNAP_SHARE_POSITIONS = frozenset({"RB", "TE"})
END_ZONE_POSITIONS = frozenset({"WR", "TE"})
PROBABILITY_FLOOR = 1e-6
ZERO_RATES = NflRedZoneRates(0.0, 0.0, 0.0, 0.0)

SnapForm = Literal["season", "recent"]


@dataclass(frozen=True)
class NflWeeklyTdRow:
    player_id: int
    position: str | None
    season: int
    week: int
    touchdowns: int
    # NULL when play-by-play was not loaded for the game.
    rz20_carries: int | None
    rz20_targets: int | None
    rz5_carries: int | None
    rz5_targets: int | None
    # NULL when play-by-play was not loaded for the game.
    end_zone_targets: int | None
    total_line: float | None = None
    spread_line: float | None = None
    home_moneyline: int | None = None
    away_moneyline: int | None = None
    is_home: bool = False

    @property
    def red_zone(self) -> NflRedZoneRates | None:
        counts = (self.rz20_carries, self.rz20_targets, self.rz5_carries, self.rz5_targets)
        if any(value is None for value in counts):
            return None
        return NflRedZoneRates(*(float(value) for value in counts))


@dataclass(frozen=True)
class NflSnapRow:
    """One stored snap row, including games with no weekly-stat row (e.g. blocking TEs)."""

    player_id: int
    position: str | None
    season: int
    week: int
    # NULL when the source left it blank; such rows are not evidence.
    offense_pct: float | None


@dataclass(frozen=True)
class NflTdBacktestCase:
    player_id: int
    position: str
    season: int
    week: int
    scored: bool
    td_seasons: list[NflSeasonTouchdowns]
    position_td_rate: float
    red_zone_seasons: list[NflRedZoneSeason]
    position_red_zone: NflRedZoneRates
    end_zone_seasons: list[NflEndZoneSeason]
    position_end_zone_targets: float
    snap_seasons: list[NflSnapSeason]
    # The latest pre-week shares, oldest first, across season boundaries.
    recent_snap_shares: tuple[float, ...]
    position_snap_share: float
    total_line: float | None
    spread_line: float | None
    home_moneyline: int | None
    away_moneyline: int | None
    is_home: bool


class _SnapTally:
    """Running per-season snap-share sums for one player or one position."""

    def __init__(self) -> None:
        self.games = 0
        self.share_total = 0.0

    def add(self, share: float) -> None:
        self.games += 1
        self.share_total += share

    def share(self) -> float:
        return self.share_total / self.games if self.games else 0.0


@dataclass
class _PlayerHistory:
    td: defaultdict[int, _Tally]
    snaps: defaultdict[int, _SnapTally]
    recent: deque[float]


def _player_history() -> _PlayerHistory:
    return _PlayerHistory(defaultdict(_Tally), defaultdict(_SnapTally), deque(maxlen=RECENT_SNAP_WINDOW))


@dataclass
class _PositionHistory:
    td: defaultdict[int, _Tally]
    snaps: defaultdict[int, _SnapTally]


def _position_history() -> _PositionHistory:
    return _PositionHistory(defaultdict(_Tally), defaultdict(_SnapTally))


class _Tally:
    """Running per-season sums for one player or one position."""

    def __init__(self) -> None:
        self.games = 0
        self.touchdowns = 0
        self.rz_games = 0
        self.rz_totals = [0.0, 0.0, 0.0, 0.0]
        self.end_zone_games = 0
        self.end_zone_targets = 0.0

    def add(self, row: NflWeeklyTdRow) -> None:
        self.games += 1
        self.touchdowns += row.touchdowns
        rates = row.red_zone
        if rates is not None:
            self.rz_games += 1
            values = (rates.rz20_carries, rates.rz20_targets, rates.rz5_carries, rates.rz5_targets)
            self.rz_totals = [total + value for total, value in zip(self.rz_totals, values)]
        if row.end_zone_targets is not None:
            self.end_zone_games += 1
            self.end_zone_targets += row.end_zone_targets

    def td_rate(self) -> float:
        return self.touchdowns / self.games if self.games else 0.0

    def red_zone(self) -> NflRedZoneRates:
        if not self.rz_games:
            return ZERO_RATES
        return NflRedZoneRates(*(total / self.rz_games for total in self.rz_totals))

    def end_zone(self) -> float:
        return self.end_zone_targets / self.end_zone_games if self.end_zone_games else 0.0


def _case(row: NflWeeklyTdRow, player: _PlayerHistory, position: _PositionHistory) -> NflTdBacktestCase | None:
    td_seasons = [
        NflSeasonTouchdowns(season, tally.games, tally.td_rate()) for season, tally in sorted(player.td.items())
    ]
    used_games = sum(entry.games for entry in td_seasons_used(td_seasons, row.season))
    if row.position not in EVALUATED_POSITIONS or used_games < MIN_BASELINE_GAMES:
        return None
    # The slate takes the position rate from the player's chosen baseline season.
    choice = choose_baseline_season(row.season, [SeasonGames(entry.season, entry.games) for entry in td_seasons])
    position_tally = position.td.get(choice.season) if choice.season is not None else None
    position_snaps = position.snaps.get(choice.season) if choice.season is not None else None
    return NflTdBacktestCase(
        player_id=row.player_id, position=row.position, season=row.season, week=row.week,
        scored=row.touchdowns > 0, td_seasons=td_seasons,
        position_td_rate=position_tally.td_rate() if position_tally else 0.0,
        red_zone_seasons=[
            NflRedZoneSeason(season, tally.rz_games, tally.red_zone()) for season, tally in sorted(player.td.items())
        ],
        position_red_zone=position_tally.red_zone() if position_tally else ZERO_RATES,
        end_zone_seasons=[
            NflEndZoneSeason(season, tally.end_zone_games, tally.end_zone())
            for season, tally in sorted(player.td.items())
        ],
        position_end_zone_targets=position_tally.end_zone() if position_tally else 0.0,
        snap_seasons=[NflSnapSeason(season, tally.games, tally.share()) for season, tally in sorted(player.snaps.items())],
        recent_snap_shares=tuple(player.recent),
        position_snap_share=position_snaps.share() if position_snaps else 0.0,
        total_line=row.total_line, spread_line=row.spread_line,
        home_moneyline=row.home_moneyline, away_moneyline=row.away_moneyline,
        is_home=row.is_home,
    )


def _week_key(row: NflWeeklyTdRow | NflSnapRow) -> tuple[int, int]:
    return row.season, row.week


def build_cases(
    rows: Iterable[NflWeeklyTdRow], seasons: frozenset[int], snap_rows: Iterable[NflSnapRow] = (),
) -> list[NflTdBacktestCase]:
    """One case per evaluated player-game in `seasons`, from strictly earlier weeks only.

    Rows are replayed a week at a time: every case in a week is built before any
    of that week's rows enter the running tallies, so no case sees its own game
    or a same-week game. Snap rows feed snap evidence only; a snap-only game
    (no weekly-stat row) adds no case and no TD history, so the baseline arm
    matches production.
    """
    players: defaultdict[int, _PlayerHistory] = defaultdict(_player_history)
    positions: defaultdict[str | None, _PositionHistory] = defaultdict(_position_history)
    ordered = sorted(rows, key=lambda row: (row.season, row.week, row.player_id))
    weekly = {key: list(group) for key, group in groupby(ordered, key=_week_key)}
    snaps = {key: list(group) for key, group in groupby(sorted(snap_rows, key=_week_key), key=_week_key)}
    cases: list[NflTdBacktestCase] = []
    for key in sorted(weekly.keys() | snaps.keys()):
        week = weekly.get(key, [])
        if key[0] in seasons:
            for row in week:
                case = _case(row, players[row.player_id], positions[row.position])
                if case is not None:
                    cases.append(case)
        for row in week:
            players[row.player_id].td[row.season].add(row)
            positions[row.position].td[row.season].add(row)
        for snap in snaps.get(key, []):
            if snap.offense_pct is None:
                continue
            players[snap.player_id].snaps[snap.season].add(snap.offense_pct)
            players[snap.player_id].recent.append(snap.offense_pct)
            positions[snap.position].snaps[snap.season].add(snap.offense_pct)
    return cases


def baseline_probability(case: NflTdBacktestCase) -> float:
    """The production anytime-TD probability, unrounded."""
    rate, _ = anytime_td_rate(case.td_seasons, case.season, case.position_td_rate)
    return 1 - exp(-rate)


def production_baseline_probability(case: NflTdBacktestCase) -> float:
    """Production's adopted snap-share baseline before historical moneyline adjustment."""
    return snap_share_probability(case, SNAP_SHARE_COEFFICIENTS, "season", SNAP_SHARE_BLEND_WEIGHT)


def historical_home_market_probability(case: NflTdBacktestCase) -> float | None:
    """De-vig historical NFLverse moneylines for the production market adjustment."""
    if case.home_moneyline is None or case.away_moneyline is None:
        return None
    try:
        home_probability, _ = implied_prob_from_american(case.home_moneyline, case.away_moneyline)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    return home_probability


def moneyline_adjusted_probability(probability: float, case: NflTdBacktestCase) -> float:
    """Apply the slate's bounded team-win adjustment without introducing rounding."""
    home_probability = historical_home_market_probability(case)
    if home_probability is None:
        return probability
    team_probability = home_probability if case.is_home else 1 - home_probability
    adjustment = min(max(team_probability - 0.5, -0.08), 0.08)
    return min(max(probability * (1 + adjustment), 0.0), 1.0)


def production_probability(case: NflTdBacktestCase) -> float:
    """Production baseline scored by the implied-total backtest arm."""
    return moneyline_adjusted_probability(production_baseline_probability(case), case)


def implied_total_probability(
    case: NflTdBacktestCase, league_average_implied_points: float, exponent: float, blend_weight: float,
) -> float:
    """Apply implied total over the adopted baseline, then the shared moneyline adjustment."""
    baseline = production_baseline_probability(case)
    rate = -log1p(-baseline) if 0 <= baseline < 1 else 0.0
    probability = scoring_environment_probability(
        rate, case.total_line, case.spread_line, case.is_home,
        league_average_implied_points, exponent, blend_weight,
    )
    return moneyline_adjusted_probability(probability, case)


def end_zone_probability(
    case: NflTdBacktestCase, coefficients: NflEndZoneCoefficients, blend_weight: float,
) -> float:
    """Apply end-zone targets over the production baseline, then the shared moneyline adjustment."""
    baseline = production_baseline_probability(case)
    historical_rate = -log1p(-baseline) if 0 <= baseline < 1 else 0.0
    targets, _ = end_zone_target_rate(case.end_zone_seasons, case.season, case.position_end_zone_targets)
    probability = end_zone_td_probability(historical_rate, targets, coefficients, blend_weight)
    return moneyline_adjusted_probability(probability, case)


def red_zone_probability(
    case: NflTdBacktestCase, coefficients: NflRedZoneCoefficients, blend_weight: float,
) -> float:
    historical_rate, _ = anytime_td_rate(case.td_seasons, case.season, case.position_td_rate)
    rates, _ = red_zone_rates(case.red_zone_seasons, case.season, case.position_red_zone)
    return red_zone_td_probability(historical_rate, rates, coefficients, blend_weight)


def case_snap_share(case: NflTdBacktestCase, form: SnapForm) -> float:
    if form == "recent":
        return recent_snap_share(list(case.recent_snap_shares), case.position_snap_share)[0]
    return season_snap_share(case.snap_seasons, case.season, case.position_snap_share)[0]


def snap_share_probability(
    case: NflTdBacktestCase,
    coefficients_by_position: dict[str, NflSnapCoefficients],
    form: SnapForm,
    blend_weight: float,
) -> float:
    """RB and TE blend in snap share; every other position gets the baseline unchanged."""
    coefficients = coefficients_by_position.get(case.position)
    if case.position not in SNAP_SHARE_POSITIONS or coefficients is None:
        return baseline_probability(case)
    historical_rate, _ = anytime_td_rate(case.td_seasons, case.season, case.position_td_rate)
    return snap_td_probability(historical_rate, case_snap_share(case, form), coefficients, blend_weight)


def _clip(probability: float) -> float:
    return min(max(probability, PROBABILITY_FLOOR), 1 - PROBABILITY_FLOOR)


def log_loss(probabilities: list[float], outcomes: list[bool]) -> float:
    if not probabilities or len(probabilities) != len(outcomes):
        raise ValueError("log_loss needs one outcome per probability and at least one of each")
    return -sum(
        log(_clip(p)) if scored else log(1 - _clip(p)) for p, scored in zip(probabilities, outcomes)
    ) / len(probabilities)


def brier(probabilities: list[float], outcomes: list[bool]) -> float:
    if not probabilities or len(probabilities) != len(outcomes):
        raise ValueError("brier needs one outcome per probability and at least one of each")
    return sum((p - float(scored)) ** 2 for p, scored in zip(probabilities, outcomes)) / len(probabilities)


@dataclass(frozen=True)
class NflTdScore:
    games: int
    log_loss: float
    brier: float
    mean_predicted: float
    actual_rate: float


def score(cases: list[NflTdBacktestCase], predict: Callable[[NflTdBacktestCase], float]) -> NflTdScore:
    probabilities = [predict(case) for case in cases]
    outcomes = [case.scored for case in cases]
    return NflTdScore(
        games=len(cases), log_loss=log_loss(probabilities, outcomes), brier=brier(probabilities, outcomes),
        mean_predicted=sum(probabilities) / len(probabilities),
        actual_rate=sum(outcomes) / len(outcomes),
    )


def score_by_position(
    cases: list[NflTdBacktestCase], predict: Callable[[NflTdBacktestCase], float],
) -> dict[str, NflTdScore]:
    by_position: dict[str, list[NflTdBacktestCase]] = defaultdict(list)
    for case in cases:
        by_position[case.position].append(case)
    return {position: score(group, predict) for position, group in sorted(by_position.items())}

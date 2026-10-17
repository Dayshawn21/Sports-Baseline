"""Pure pre-game NFL team efficiency ratings for any per-team-game metric.

Each team carries an offense offset (value above league average produced) and a
defense offset (value above league average allowed). The same replay serves EPA
per play, success rate, and plays, so each metric is one call with its own map.
"""
from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from app.core.nfl_elo import NflEloGame

# About one season of team-games, so the league average follows league trends.
LEAGUE_WINDOW_TEAM_GAMES = 544

# (game_key, is_home) -> that offense's value in that game.
TeamGameMetric = Mapping[tuple[str, bool], float]


@dataclass(frozen=True)
class NflEfficiencyConfig:
    learning_rate: float
    season_regression: float = 1 / 3


@dataclass(frozen=True)
class NflEfficiencyRow:
    game_key: str
    season: int
    week: int
    # None until a first week of values exists; ratings do not move before then.
    league: float | None
    home_offset: float
    away_offset: float

    @property
    def expected_home(self) -> float | None:
        return None if self.league is None else self.league + self.home_offset

    @property
    def expected_away(self) -> float | None:
        return None if self.league is None else self.league + self.away_offset


SPREAD_FEATURE_NAMES = ("epa_edge", "success_edge")
TOTAL_FEATURE_NAMES = ("epa_sum", "success_sum", "pace")


@dataclass(frozen=True)
class NflEfficiencyFeatures:
    """Pre-game offsets only, so two league-average teams give all zeros."""

    epa_edge: float
    success_edge: float
    epa_sum: float
    success_sum: float
    pace: float

    def spread_vector(self) -> list[float]:
        return [self.epa_edge, self.success_edge]

    def total_vector(self) -> list[float]:
        return [self.epa_sum, self.success_sum, self.pace]


def efficiency_features(epa: NflEfficiencyRow, success: NflEfficiencyRow, plays: NflEfficiencyRow) -> NflEfficiencyFeatures:
    """One game's features from its three metric rows; edges are home minus away."""
    return NflEfficiencyFeatures(
        epa_edge=epa.home_offset - epa.away_offset,
        success_edge=success.home_offset - success.away_offset,
        epa_sum=epa.home_offset + epa.away_offset,
        success_sum=success.home_offset + success.away_offset,
        pace=plays.home_offset + plays.away_offset,
    )


def replay(games: Iterable[NflEloGame], metric: TeamGameMetric, config: NflEfficiencyConfig) -> list[NflEfficiencyRow]:
    """One row per game, in the order given, which must be the order games were played.

    Offsets only read earlier games; the league average only reads earlier weeks.
    A game missing either side's value (unplayed or not loaded) still gets a row
    but updates nothing. Every team-game counts once in the league average.
    """
    offense: dict[str, float] = {}
    defense: dict[str, float] = {}
    window: deque[float] = deque(maxlen=LEAGUE_WINDOW_TEAM_GAMES)
    pending: list[float] = []
    current: tuple[int, int] | None = None
    rows: list[NflEfficiencyRow] = []
    for game in games:
        if (game.season, game.week) != current:
            window.extend(pending)
            pending = []
            if current is not None and game.season > current[0]:
                keep = 1 - config.season_regression
                offense = {team: value * keep for team, value in offense.items()}
                defense = {team: value * keep for team, value in defense.items()}
            current = (game.season, game.week)
        league = sum(window) / len(window) if window else None
        home_offset = offense.get(game.home_team, 0.0) + defense.get(game.away_team, 0.0)
        away_offset = offense.get(game.away_team, 0.0) + defense.get(game.home_team, 0.0)
        rows.append(NflEfficiencyRow(game.game_key, game.season, game.week, league, home_offset, away_offset))
        home_value = metric.get((game.game_key, True))
        away_value = metric.get((game.game_key, False))
        if home_value is None or away_value is None:
            continue
        pending.extend((home_value, away_value))
        if league is None:
            continue
        home_error = (home_value - league - home_offset) * config.learning_rate
        away_error = (away_value - league - away_offset) * config.learning_rate
        offense[game.home_team] = offense.get(game.home_team, 0.0) + home_error
        defense[game.away_team] = defense.get(game.away_team, 0.0) + home_error
        offense[game.away_team] = offense.get(game.away_team, 0.0) + away_error
        defense[game.home_team] = defense.get(game.home_team, 0.0) + away_error
    return rows

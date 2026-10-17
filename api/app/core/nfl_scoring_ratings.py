"""Pure pre-game NFL scoring ratings, the total-points counterpart to team ELO.

ELO measures who is better, not how many points a game will have, so totals
need their own input. Each team carries an offense rating (points scored above
league average) and a defense rating (points allowed above league average).
Home field is left out: it shifts points between the two sides of a game, not
the total this exists to predict.
"""
from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass

from app.core.nfl_elo import NflEloGame

# Only used until the first week of results exists (2012 week 1).
INITIAL_LEAGUE_POINTS = 22.0
# About one season of games, so the league average follows scoring trends.
LEAGUE_WINDOW_GAMES = 272


@dataclass(frozen=True)
class NflScoringConfig:
    learning_rate: float
    season_regression: float = 1 / 3


# The 24b fit on 2014-2021. Rejected against closing totals, so it is shown only
# as display context on the slate, never as an edge.
NFL_SCORING_V1 = NflScoringConfig(learning_rate=0.05)


@dataclass(frozen=True)
class NflScoringRow:
    game_key: str
    season: int
    week: int
    expected_home_points: float
    expected_away_points: float

    @property
    def expected_total(self) -> float:
        return self.expected_home_points + self.expected_away_points


def replay(games: Iterable[NflEloGame], config: NflScoringConfig) -> list[NflScoringRow]:
    """One row per game, in the order given, which must be the order games were played.

    Team ratings only read earlier games. The league average only reads earlier
    weeks, because games sharing a kickoff time would otherwise see each other.
    """
    offense: dict[str, float] = {}
    defense: dict[str, float] = {}
    window: deque[int] = deque(maxlen=LEAGUE_WINDOW_GAMES * 2)
    pending: list[int] = []
    current: tuple[int, int] | None = None
    rows: list[NflScoringRow] = []
    for game in games:
        if (game.season, game.week) != current:
            window.extend(pending)
            pending = []
            if current is not None and game.season > current[0]:
                keep = 1 - config.season_regression
                offense = {team: value * keep for team, value in offense.items()}
                defense = {team: value * keep for team, value in defense.items()}
            current = (game.season, game.week)
        league = sum(window) / len(window) if window else INITIAL_LEAGUE_POINTS
        expected_home = league + offense.get(game.home_team, 0.0) + defense.get(game.away_team, 0.0)
        expected_away = league + offense.get(game.away_team, 0.0) + defense.get(game.home_team, 0.0)
        rows.append(NflScoringRow(game.game_key, game.season, game.week, expected_home, expected_away))
        if game.home_score is None or game.away_score is None:
            continue
        home_error = (game.home_score - expected_home) * config.learning_rate
        away_error = (game.away_score - expected_away) * config.learning_rate
        offense[game.home_team] = offense.get(game.home_team, 0.0) + home_error
        defense[game.away_team] = defense.get(game.away_team, 0.0) + home_error
        offense[game.away_team] = offense.get(game.away_team, 0.0) + away_error
        defense[game.home_team] = defense.get(game.home_team, 0.0) + away_error
        pending.extend((game.home_score, game.away_score))
    return rows

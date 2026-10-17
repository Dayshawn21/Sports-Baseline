"""Pure NFL team ELO: pre-game ratings from final regular-season scores only.

`NFL_ELO_V1` follows the FiveThirtyEight NFL form and is reasoned, not fitted.
The 24b backtest fits alternatives on fit seasons only.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import log

NFL_ELO_MODEL_VERSION = "nfl-elo-v1"
INITIAL_ELO = 1500.0


@dataclass(frozen=True)
class NflEloConfig:
    k: float
    home_field: float
    # Rosters turn over between seasons, so a rating only partly carries forward.
    season_regression: float


NFL_ELO_V1 = NflEloConfig(k=20.0, home_field=48.0, season_regression=1 / 3)


@dataclass(frozen=True)
class NflEloGame:
    game_key: str
    season: int
    week: int
    home_team: str
    away_team: str
    home_score: int | None
    away_score: int | None


@dataclass(frozen=True)
class NflTeamEloRow:
    team_code: str
    game_key: str
    season: int
    week: int
    is_home: bool
    elo_pre: float
    elo_post: float | None


def expected_home_win_probability(home_elo: float, away_elo: float, home_field: float = NFL_ELO_V1.home_field) -> float:
    return 1 / (1 + 10 ** (-(home_elo + home_field - away_elo) / 400))


def margin_multiplier(margin: int, winner_elo_diff: float) -> float:
    """Scale an update by margin, damped when the winner was already favored.

    Without the damping, favorites win by more on average, so their ratings
    would inflate from the correlation alone. A tie counts as a one-point margin
    so it still moves both ratings toward a half result.
    """
    return log(max(abs(margin), 1) + 1) * 2.2 / (winner_elo_diff * 0.001 + 2.2)


def update(
    home_elo: float, away_elo: float, home_score: int, away_score: int, config: NflEloConfig = NFL_ELO_V1,
) -> tuple[float, float]:
    """Post-game ratings; the home gain always equals the away loss."""
    expected = expected_home_win_probability(home_elo, away_elo, config.home_field)
    actual = 1.0 if home_score > away_score else 0.0 if home_score < away_score else 0.5
    home_diff = home_elo + config.home_field - away_elo
    winner_diff = -home_diff if home_score < away_score else home_diff
    shift = config.k * margin_multiplier(home_score - away_score, winner_diff) * (actual - expected)
    return home_elo + shift, away_elo - shift


def regress_to_mean(elo: float, config: NflEloConfig = NFL_ELO_V1) -> float:
    return elo + (INITIAL_ELO - elo) * config.season_regression


def current_ratings(rows: Iterable[NflTeamEloRow]) -> dict[str, float]:
    """Each team's rating entering its next game: its last post, or last pre if unplayed."""
    ratings: dict[str, float] = {}
    for row in rows:
        ratings[row.team_code] = row.elo_post if row.elo_post is not None else row.elo_pre
    return ratings


def season_end_ratings(rows: Iterable[NflTeamEloRow], season: int) -> dict[str, float]:
    """Each team's last post rating in a season, before any between-season regression."""
    return {
        row.team_code: row.elo_post for row in rows
        if row.season == season and row.elo_post is not None
    }


def point_differentials(games: Iterable[NflEloGame], season: int) -> dict[str, int]:
    differentials: dict[str, int] = {}
    for game in games:
        if game.season != season or game.home_score is None or game.away_score is None:
            continue
        margin = game.home_score - game.away_score
        differentials[game.home_team] = differentials.get(game.home_team, 0) + margin
        differentials[game.away_team] = differentials.get(game.away_team, 0) - margin
    return differentials


def replay(games: Iterable[NflEloGame], config: NflEloConfig = NFL_ELO_V1) -> list[NflTeamEloRow]:
    """Two rows per game, in the order given, which must be the order games were played.

    A game's pre rating reads only games earlier in the sequence, so later
    results can never leak into it. Unfinished games get a pre rating and no
    post rating, and leave both teams' ratings unchanged.
    """
    ratings: dict[str, float] = {}
    season: int | None = None
    rows: list[NflTeamEloRow] = []
    for game in games:
        if season is not None and game.season > season:
            ratings = {team: regress_to_mean(elo, config) for team, elo in ratings.items()}
        season = game.season if season is None else max(season, game.season)
        home_pre = ratings.get(game.home_team, INITIAL_ELO)
        away_pre = ratings.get(game.away_team, INITIAL_ELO)
        home_post: float | None = None
        away_post: float | None = None
        if game.home_score is not None and game.away_score is not None:
            home_post, away_post = update(home_pre, away_pre, game.home_score, game.away_score, config)
            ratings[game.home_team], ratings[game.away_team] = home_post, away_post
        rows.append(NflTeamEloRow(game.home_team, game.game_key, game.season, game.week, True, home_pre, home_post))
        rows.append(NflTeamEloRow(game.away_team, game.game_key, game.season, game.week, False, away_pre, away_post))
    return rows

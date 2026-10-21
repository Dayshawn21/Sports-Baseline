"""Display-only NBA team rates from paired, score-checked player-box totals."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Literal

from app.core.nba_season import NBA_TEAM_CODES

TeamStat = Literal["points", "rebounds", "assists", "threes_made", "blocks"]
TEAM_STATS: tuple[TeamStat, ...] = ("points", "rebounds", "assists", "threes_made", "blocks")


@dataclass(frozen=True)
class TeamBoxSide:
    """SQL groups by team, opponent and DNP; invalid/missing stat totals are null."""

    team: str
    opponent: str
    player_rows: int
    totals: Mapping[TeamStat, int | None]
    did_not_play: bool = False


@dataclass(frozen=True)
class TeamBoxGame:
    season: int
    game_date: date
    home_team: str
    away_team: str
    home_score: int | None
    away_score: int | None
    sides: tuple[TeamBoxSide, ...]
    sport: str = "nba"
    game_type: str = "REG"
    status: str = "completed"


@dataclass(frozen=True)
class TeamStatRate:
    per_game: float | None
    rank: int | None
    games: int
    ranked_teams: int


@dataclass(frozen=True)
class TeamStatPair:
    for_: TeamStatRate
    allowed: TeamStatRate


@dataclass(frozen=True)
class TeamSeasonStats:
    team: str
    completed_games: int
    stats: Mapping[TeamStat, TeamStatPair]


def team_stats(games: Iterable[TeamBoxGame], season: int, before: date) -> dict[str, TeamSeasonStats]:
    """Rank all NBA teams using only the requested season's prior completed REG games."""
    completed = dict.fromkeys(NBA_TEAM_CODES, 0)
    samples: dict[str, dict[TeamStat, list[tuple[int, int]]]] = {
        team: {stat: [] for stat in TEAM_STATS} for team in NBA_TEAM_CODES
    }
    for game in games:
        if not _eligible(game, season, before):
            continue
        for team in (game.home_team, game.away_team):
            completed[team] += 1
        sides = _played_sides(game)
        if sides is None:
            continue
        home, away = sides
        for stat in TEAM_STATS:
            home_value, away_value = home.totals.get(stat), away.totals.get(stat)
            if home_value is None or away_value is None or min(home_value, away_value) < 0:
                continue
            samples[home.team][stat].append((home_value, away_value))
            samples[away.team][stat].append((away_value, home_value))
    rates: dict[str, dict[TeamStat, TeamStatPair]] = {team: {} for team in NBA_TEAM_CODES}
    for stat in TEAM_STATS:
        offense = _rates({team: [pair[0] for pair in rows[stat]] for team, rows in samples.items()}, higher=True)
        allowed = _rates({team: [pair[1] for pair in rows[stat]] for team, rows in samples.items()}, higher=False)
        for team in NBA_TEAM_CODES:
            rates[team][stat] = TeamStatPair(offense[team], allowed[team])
    return {team: TeamSeasonStats(team, completed[team], rates[team]) for team in sorted(NBA_TEAM_CODES)}


def _eligible(game: TeamBoxGame, season: int, before: date) -> bool:
    return (
        game.sport == "nba" and game.season == season and game.game_date < before
        and game.game_type == "REG" and game.status == "completed"
        and game.home_team in NBA_TEAM_CODES and game.away_team in NBA_TEAM_CODES
        and game.home_team != game.away_team
    )


def _played_sides(game: TeamBoxGame) -> tuple[TeamBoxSide, TeamBoxSide] | None:
    opponents = {game.home_team: game.away_team, game.away_team: game.home_team}
    if any(side.team not in opponents or side.opponent != opponents[side.team] for side in game.sides):
        return None
    played = [side for side in game.sides if not side.did_not_play]
    if len(played) != 2 or {side.team for side in played} != set(opponents):
        return None
    by_team = {side.team: side for side in played}
    home, away = by_team[game.home_team], by_team[game.away_team]
    for side, score in ((home, game.home_score), (away, game.away_score)):
        points = side.totals.get("points")
        if side.player_rows <= 0 or points is None or points < 0 or points != score:
            return None
    return home, away


def _rates(samples: Mapping[str, list[int]], *, higher: bool) -> dict[str, TeamStatRate]:
    # Rank displayed precision so equal visible values cannot have different ranks.
    values = {team: round(sum(rows) / len(rows), 1) for team, rows in samples.items() if rows}
    ordered = sorted(values, key=lambda team: values[team], reverse=higher)
    ranks: dict[float, int] = {}
    for position, team in enumerate(ordered, start=1):
        ranks.setdefault(values[team], position)
    return {
        team: TeamStatRate(values.get(team), ranks.get(values[team]) if team in values else None,
                           len(rows), len(values))
        for team, rows in samples.items()
    }

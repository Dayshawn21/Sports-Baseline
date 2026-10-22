"""Season-to-date team offense and defense per game, with league ranks.

Display only, for the game notes panel: nothing here feeds a projection, an
edge, or the slate's ranking. Pure: no DB, no I/O.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date

# Values are rounded to the precision the panel shows before ranking, so two
# teams that read the same share a rank.
_PRECISION = {"per_game": 1, "epa_per_play": 2, "success_rate": 2}


@dataclass(frozen=True)
class TeamGame:
    """One team's side of a completed game; None means not loaded, never zero."""

    team_id: int
    points_for: int
    points_against: int
    pass_yards_for: float | None = None
    pass_yards_against: float | None = None
    rush_yards_for: float | None = None
    rush_yards_against: float | None = None
    plays_for: int | None = None
    plays_against: int | None = None
    epa_for: float | None = None
    epa_against: float | None = None
    successes_for: int | None = None
    successes_against: int | None = None
    pass_attempts_for: int | None = None
    pass_attempts_against: int | None = None
    rush_attempts_for: int | None = None
    rush_attempts_against: int | None = None
    played_on: date = date.min
    game_id: int = 0


@dataclass(frozen=True)
class StatLine:
    value: float | None
    rank: int | None
    observed_games: int = 0


@dataclass(frozen=True)
class TeamStats:
    games: int
    efficiency_games: int
    stats: dict[str, StatLine]


# Stat key -> higher is better. Defense ranks 1 for the fewest allowed.
STAT_KEYS: dict[str, bool] = {
    "points": True, "pass_yards": True, "rush_yards": True,
    "plays": True, "epa_per_play": True, "success_rate": True,
    "points_allowed": False, "pass_yards_allowed": False, "rush_yards_allowed": False,
    "plays_allowed": False, "epa_per_play_allowed": False, "success_rate_allowed": False,
    "pass_attempts": True, "rush_attempts": True,
    "pass_attempts_allowed": False, "rush_attempts_allowed": False,
}

EMPTY_TEAM_STATS = TeamStats(games=0, efficiency_games=0, stats={key: StatLine(None, None) for key in STAT_KEYS})


def team_stats(games: Iterable[TeamGame], *, last_n: int | None = None) -> dict[int, TeamStats]:
    """League ranks within the season or each team's latest completed games."""
    if last_n is not None and last_n < 1:
        raise ValueError("last_n must be positive")
    by_team: dict[int, list[TeamGame]] = {}
    for game in games:
        by_team.setdefault(game.team_id, []).append(game)
    if last_n is not None:
        by_team = {team: sorted(rows, key=lambda row: (row.played_on, row.game_id))[-last_n:]
                   for team, rows in by_team.items()}
    values = {team_id: _values(rows) for team_id, rows in by_team.items()}
    ranks = {key: _ranks({team_id: row[key] for team_id, row in values.items()}, higher) for key, higher in STAT_KEYS.items()}
    return {
        team_id: TeamStats(
            games=len(rows),
            efficiency_games=sum(1 for row in rows if row.plays_for),
            stats={key: StatLine(values[team_id][key], ranks[key].get(team_id), _observed_games(rows, key))
                   for key in STAT_KEYS},
        )
        for team_id, rows in by_team.items()
    }


def _values(rows: list[TeamGame]) -> dict[str, float | None]:
    return {
        "points": _per_game(rows, lambda row: row.points_for),
        "pass_yards": _per_game(rows, lambda row: row.pass_yards_for),
        "rush_yards": _per_game(rows, lambda row: row.rush_yards_for),
        "pass_attempts": _per_game(rows, lambda row: row.pass_attempts_for),
        "rush_attempts": _per_game(rows, lambda row: row.rush_attempts_for),
        "plays": _per_game(rows, lambda row: row.plays_for),
        "epa_per_play": _per_play(rows, lambda row: (row.epa_for, row.plays_for), "epa_per_play"),
        "success_rate": _per_play(rows, lambda row: (row.successes_for, row.plays_for), "success_rate"),
        "points_allowed": _per_game(rows, lambda row: row.points_against),
        "pass_yards_allowed": _per_game(rows, lambda row: row.pass_yards_against),
        "rush_yards_allowed": _per_game(rows, lambda row: row.rush_yards_against),
        "pass_attempts_allowed": _per_game(rows, lambda row: row.pass_attempts_against),
        "rush_attempts_allowed": _per_game(rows, lambda row: row.rush_attempts_against),
        "plays_allowed": _per_game(rows, lambda row: row.plays_against),
        "epa_per_play_allowed": _per_play(rows, lambda row: (row.epa_against, row.plays_against), "epa_per_play"),
        "success_rate_allowed": _per_play(rows, lambda row: (row.successes_against, row.plays_against), "success_rate"),
    }


def _observed_games(rows: list[TeamGame], key: str) -> int:
    allowed = key.endswith("_allowed")
    metric = key.removesuffix("_allowed")
    field = {"epa_per_play": "epa", "success_rate": "successes"}.get(metric, metric)
    side = "against" if allowed else "for"
    return sum(
        getattr(row, f"{field}_{side}") is not None
        and (metric not in {"epa_per_play", "success_rate"} or bool(getattr(row, f"plays_{side}")))
        for row in rows
    )


def _per_game(rows: list[TeamGame], pick: Callable[[TeamGame], float | None]) -> float | None:
    """Mean over the games where the value was loaded."""
    loaded = [value for value in map(pick, rows) if value is not None]
    if not loaded:
        return None
    return round(sum(loaded) / len(loaded), _PRECISION["per_game"])


def _per_play(
    rows: list[TeamGame], pick: Callable[[TeamGame], tuple[float | None, int | None]], precision: str,
) -> float | None:
    """Season total over season plays, so a long game weighs by its plays, not as one game."""
    pairs = [(amount, plays) for amount, plays in map(pick, rows) if amount is not None and plays]
    plays = sum(plays for _, plays in pairs)
    if not plays:
        return None
    return round(sum(amount for amount, _ in pairs) / plays, _PRECISION[precision])


def _ranks(values: dict[int, float | None], higher_is_better: bool) -> dict[int, int]:
    """Competition ranks (1, 2, 2, 4) over teams with a value."""
    ordered = sorted(
        ((team_id, value) for team_id, value in values.items() if value is not None),
        key=lambda item: -item[1] if higher_is_better else item[1],
    )
    ranks: dict[int, int] = {}
    for position, (team_id, value) in enumerate(ordered, start=1):
        previous = ordered[position - 2] if position > 1 else None
        ranks[team_id] = ranks[previous[0]] if previous and previous[1] == value else position
    return ranks

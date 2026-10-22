"""Pure, pre-week NFL display context, independent of projection/model inputs."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from math import isfinite
from typing import Literal

UnavailableReason = Literal["no_history", "missing_data", "zero_denominator", "unknown_kickoff"]
AllowedMeasure = Literal[
    "rb_carries", "rb_rush_yards", "rb_receptions", "rb_rec_yards",
    "wr_receptions", "wr_rec_yards", "te_receptions", "te_rec_yards",
]
ALLOWED_MEASURES: tuple[AllowedMeasure, ...] = (
    "rb_carries", "rb_rush_yards", "rb_receptions", "rb_rec_yards",
    "wr_receptions", "wr_rec_yards", "te_receptions", "te_rec_yards",
)


@dataclass(frozen=True)
class ContextCutoff:
    season: int
    week: int
    kickoff: datetime | None


@dataclass(frozen=True)
class HistoryGame:
    game_id: int
    season: int
    week: int
    start_utc: datetime | None
    completed: bool = True
    game_type: str = "REG"
    sport: str = "nfl"


@dataclass(frozen=True)
class ContextMetric:
    value: float | None
    observed_games: int
    eligible_games: int
    window_start: date | None
    window_end: date | None
    reason: UnavailableReason | None


@dataclass(frozen=True)
class AllowedMetric(ContextMetric):
    rank: int | None
    ranked_teams: int


@dataclass(frozen=True)
class PlayerUsageGame:
    """One played game, with actual historical team and covered team totals.

    A denominator is None unless every relevant teammate row is covered.
    Snap share is the stored fraction, not a percentage from 0 to 100.
    """

    game: HistoryGame
    team: str
    targets: float | None = None
    carries: float | None = None
    team_targets: float | None = None
    team_carries: float | None = None
    offense_pct: float | None = None
    played: bool = True


@dataclass(frozen=True)
class UsageWindow:
    targets: ContextMetric
    carries: ContextMetric
    target_share: ContextMetric
    carry_share: ContextMetric
    avg_game_snap_share: ContextMetric
    teams: tuple[str, ...]


@dataclass(frozen=True)
class PlayerUsage:
    season_usage: UsageWindow
    recent_usage: UsageWindow


@dataclass(frozen=True)
class TeamAllowedGame:
    """One defense game; each value is a position sum, never a player average.

    Missing/partially covered position sums stay None. An explicit zero needs
    source completeness established by the loader, not an absent SQL group.
    """

    game: HistoryGame
    team_id: int
    rb_carries: float | None = None
    rb_rush_yards: float | None = None
    rb_receptions: float | None = None
    rb_rec_yards: float | None = None
    wr_receptions: float | None = None
    wr_rec_yards: float | None = None
    te_receptions: float | None = None
    te_rec_yards: float | None = None


def _aware(value: datetime | None) -> bool:
    return value is not None and value.utcoffset() is not None


def eligible_game(game: HistoryGame, cutoff: ContextCutoff) -> bool:
    return (
        game.sport == "nfl" and game.game_type == "REG" and game.completed
        and game.season == cutoff.season and 1 <= game.week < cutoff.week
        and _aware(game.start_utc) and _aware(cutoff.kickoff)
        and game.start_utc < cutoff.kickoff
    )


def _number(value: float | None, *, nonnegative: bool = True) -> bool:
    return value is not None and isfinite(value) and (not nonnegative or value >= 0)


def _metric(
    values: list[tuple[HistoryGame, float]], eligible: int, cutoff: ContextCutoff,
    reason: UnavailableReason | None = None,
) -> ContextMetric:
    dates = [game.start_utc.astimezone(UTC).date() for game, _ in values]
    return ContextMetric(
        value=sum(value for _, value in values) / len(values) if values else None,
        observed_games=len(values), eligible_games=eligible,
        window_start=min(dates) if dates else None, window_end=max(dates) if dates else None,
        reason=None if values else (
            "unknown_kickoff" if not _aware(cutoff.kickoff)
            else "no_history" if not eligible else reason or "missing_data"
        ),
    )


def _usage_mean(
    rows: list[PlayerUsageGame], cutoff: ContextCutoff,
    pick: Callable[[PlayerUsageGame], float | None], *, fraction: bool = False,
) -> ContextMetric:
    values = [
        (row.game, value) for row in rows
        if _number(value := pick(row)) and (not fraction or value <= 1)
    ]
    return _metric(values, len(rows), cutoff)


def _usage_share(
    rows: list[PlayerUsageGame], cutoff: ContextCutoff,
    pick: Callable[[PlayerUsageGame], tuple[float | None, float | None]],
) -> ContextMetric:
    pairs: list[tuple[HistoryGame, float, float]] = []
    zero_denominators = 0
    for row in rows:
        numerator, denominator = pick(row)
        if not _number(numerator) or not _number(denominator) or numerator > denominator:
            continue
        if denominator == 0:
            zero_denominators += 1
            continue
        pairs.append((row.game, numerator, denominator))
    metric = _metric(
        [(game, numerator) for game, numerator, _ in pairs], len(rows), cutoff,
        "zero_denominator" if zero_denominators == len(rows) else "missing_data",
    )
    if not pairs:
        return metric
    return replace(metric, value=sum(n for _, n, _ in pairs) / sum(d for _, _, d in pairs))


def _usage_window(rows: list[PlayerUsageGame], cutoff: ContextCutoff) -> UsageWindow:
    return UsageWindow(
        targets=_usage_mean(rows, cutoff, lambda row: row.targets),
        carries=_usage_mean(rows, cutoff, lambda row: row.carries),
        target_share=_usage_share(rows, cutoff, lambda row: (row.targets, row.team_targets)),
        carry_share=_usage_share(rows, cutoff, lambda row: (row.carries, row.team_carries)),
        avg_game_snap_share=_usage_mean(rows, cutoff, lambda row: row.offense_pct, fraction=True),
        teams=tuple(dict.fromkeys(row.team for row in rows)),
    )


def player_usage(rows: Iterable[PlayerUsageGame], cutoff: ContextCutoff) -> PlayerUsage:
    """Choose the last three played games before filtering any metric."""
    history = sorted(
        (row for row in rows if row.played and eligible_game(row.game, cutoff)),
        key=lambda row: (row.game.start_utc, row.game.game_id),
    )
    if len({row.game.game_id for row in history}) != len(history):
        raise ValueError("Player usage requires one row per played game")
    return PlayerUsage(_usage_window(history, cutoff), _usage_window(history[-3:], cutoff))


def position_allowed(
    rows: Iterable[TeamAllowedGame], team_ids: Iterable[int], cutoff: ContextCutoff,
) -> dict[int, dict[AllowedMeasure, AllowedMetric]]:
    """League position means, coverage and competition ranks, 1 = fewest."""
    by_team: dict[int, list[TeamAllowedGame]] = {team_id: [] for team_id in team_ids}
    seen: set[tuple[int, int]] = set()
    for row in rows:
        if row.team_id not in by_team or not eligible_game(row.game, cutoff):
            continue
        identity = (row.team_id, row.game.game_id)
        if identity in seen:
            raise ValueError("Position allowed requires one row per defense game")
        seen.add(identity)
        by_team[row.team_id].append(row)
    result: dict[int, dict[AllowedMeasure, AllowedMetric]] = {team: {} for team in by_team}
    for measure in ALLOWED_MEASURES:
        metrics = {
            team: _metric([
                (row.game, value) for row in games
                if _number(value := getattr(row, measure), nonnegative=False)
            ], len(games), cutoff)
            for team, games in by_team.items()
        }
        rounded = {team: round(metric.value, 1) for team, metric in metrics.items() if metric.value is not None}
        for team, metric in metrics.items():
            rank = 1 + sum(value < rounded[team] for value in rounded.values()) if team in rounded else None
            result[team][measure] = AllowedMetric(
                value=round(metric.value, 1) if metric.value is not None else None,
                observed_games=metric.observed_games, eligible_games=metric.eligible_games,
                window_start=metric.window_start, window_end=metric.window_end, reason=metric.reason,
                rank=rank, ranked_teams=len(rounded),
            )
    return result

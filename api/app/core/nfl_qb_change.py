"""Whether a team's quarterback differs from the one its recent games were played with.

The game model (`nfl-elo-v1`, `NFL_SCORING_V1`) is built from final scores only,
so a QB change is invisible to it. This flags the change for display beside the
model; it never feeds a projection, edge, rank, or the model itself. Pure: no DB.

Every input is the latest one stored, not this week's: depth charts, injury
reports and box scores all land days apart, so each reason names its week.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

QbReason = Literal["injured", "backup_started", "depth_chart"]

USUAL_STARTER_GAMES = 8
_UNAVAILABLE = {"Out", "Doubtful"}


@dataclass(frozen=True)
class Qb:
    player_id: int
    name: str


@dataclass(frozen=True)
class QbGame:
    """One QB's passing attempts in one team game; recency 1 is the team's latest completed game."""

    season: int
    week: int
    recency: int
    qb: Qb
    attempts: int


@dataclass(frozen=True)
class QbInjury:
    """A QB's status in the team's latest stored injury report this season."""

    week: int
    status: str | None


@dataclass(frozen=True)
class QbChange:
    usual_starter: str
    reasons: list[QbReason]
    injury_status: str | None = None
    injury_week: int | None = None
    last_game_qb: str | None = None
    last_game_week: int | None = None
    previous_qb1: str | None = None


def attempts_leader(games: list[QbGame]) -> Qb | None:
    """Most attempts in the latest season's games; a tie goes to the QB who played more recently.

    Only the latest season counts, so last year's starter never outvotes this year's.
    """
    latest_season = max((game.season for game in games), default=None)
    totals: dict[Qb, int] = {}
    latest: dict[Qb, int] = {}
    for game in games:
        if game.season != latest_season:
            continue
        totals[game.qb] = totals.get(game.qb, 0) + game.attempts
        latest[game.qb] = min(latest.get(game.qb, game.recency), game.recency)
    if not totals:
        return None
    return min(totals, key=lambda qb: (-totals[qb], latest[qb], qb.name))


def last_game_leader(games: list[QbGame], starter: Qb) -> QbGame | None:
    """The attempts leader in the latest game with stats loaded; a tie keeps the usual starter."""
    if not games:
        return None
    latest = min(game.recency for game in games)
    played = [game for game in games if game.recency == latest]
    return min(played, key=lambda game: (-game.attempts, game.qb != starter, game.qb.name))


def qb_change(
    games: list[QbGame],
    injuries: dict[int, QbInjury],
    latest_qb1: Qb | None,
    previous_qb1: Qb | None,
) -> QbChange | None:
    """The team's QB change, or None when its usual starter is expected to play.

    The usual starter is the latest depth-chart QB1, because teams keep an
    injured starter there; attempts decide only when no chart is stored.
    `injuries` holds the team's latest report by player id.
    """
    starter = latest_qb1 or attempts_leader(games)
    if starter is None:
        return None
    reasons: list[QbReason] = []
    injury = injuries.get(starter.player_id)
    injured = injury is not None and injury.status in _UNAVAILABLE
    if injured:
        reasons.append("injured")
    leader = last_game_leader(games, starter)
    backup = leader if leader is not None and leader.qb != starter else None
    if backup is not None:
        reasons.append("backup_started")
    replaced = previous_qb1 if previous_qb1 is not None and previous_qb1 != starter else None
    if replaced is not None:
        reasons.append("depth_chart")
    if not reasons:
        return None
    return QbChange(
        usual_starter=starter.name,
        reasons=reasons,
        injury_status=injury.status if injured and injury else None,
        injury_week=injury.week if injured and injury else None,
        last_game_qb=backup.qb.name if backup else None,
        last_game_week=backup.week if backup else None,
        previous_qb1=replaced.name if replaced else None,
    )

"""Role-change flags from a player's injury report and depth-chart movement.

Display only: these flags warn the reader; they never change a projection, an
edge, or the slate's ranking. Pure: no DB, no I/O.
"""
from __future__ import annotations

from dataclasses import dataclass

INJURY_FLAGS = {"Out": "injury_out", "Doubtful": "injury_doubtful", "Questionable": "injury_questionable"}
DEPTH_PROMOTED = "depth_promoted"
DEPTH_DEMOTED = "depth_demoted"
DEPTH_NEW = "depth_new"


@dataclass(frozen=True)
class NflAvailability:
    injury_status: str | None = None
    depth_team_id: int | None = None
    depth_position: str | None = None
    depth_rank: int | None = None
    previous_depth_team_id: int | None = None
    previous_depth_position: str | None = None
    previous_depth_rank: int | None = None


def availability_flags(availability: NflAvailability) -> list[str]:
    """Injury status flag, then a depth move against the player's previous chart.

    A different team or position than before counts as a new role, not a
    promotion or demotion, since the ranks are not comparable. No chart this
    week says nothing: absence is not a demotion.
    """
    flags = []
    if availability.injury_status in INJURY_FLAGS:
        flags.append(INJURY_FLAGS[availability.injury_status])
    if availability.depth_rank is None:
        return flags
    same_role = (
        availability.previous_depth_rank is not None
        and availability.previous_depth_position == availability.depth_position
        and availability.previous_depth_team_id == availability.depth_team_id
    )
    if not same_role:
        flags.append(DEPTH_NEW)
    elif availability.depth_rank < availability.previous_depth_rank:
        flags.append(DEPTH_PROMOTED)
    elif availability.depth_rank > availability.previous_depth_rank:
        flags.append(DEPTH_DEMOTED)
    return flags

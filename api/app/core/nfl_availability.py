"""Role-change flags from a player's injury report and depth-chart movement.

Display and selection only: these flags warn the reader, and `role_changed`
keeps a line from being called or ranked as a pick, but no flag changes a
projection, an edge or the API's slate order. Pure: no DB, no I/O.
"""
from __future__ import annotations

from dataclasses import dataclass

INJURY_FLAGS = {"Out": "injury_out", "Doubtful": "injury_doubtful", "Questionable": "injury_questionable"}
DEPTH_PROMOTED = "depth_promoted"
DEPTH_DEMOTED = "depth_demoted"
DEPTH_NEW = "depth_new"
# The projection is a role average that cannot know this week's role: the
# player is Out, or a teammate ahead of him is Out and he moves up (70a).
ROLE_CHANGED = "role_changed"


@dataclass(frozen=True)
class NflAvailability:
    injury_status: str | None = None
    depth_team_id: int | None = None
    depth_position: str | None = None
    depth_rank: int | None = None
    previous_depth_team_id: int | None = None
    previous_depth_position: str | None = None
    previous_depth_rank: int | None = None
    # The chart rank once teammates ahead who are Out step aside; None when this
    # player is Out. Never used for the week-over-week move flags.
    active_depth_rank: int | None = None
    out_ahead: tuple[str, ...] = ()


def availability_flags(availability: NflAvailability) -> list[str]:
    """Injury status flag, then a depth move against the player's previous chart.

    A different team or position than before counts as a new role, not a
    promotion or demotion, since the ranks are not comparable. No chart this
    week says nothing: absence is not a demotion.
    """
    flags = []
    if availability.injury_status in INJURY_FLAGS:
        flags.append(INJURY_FLAGS[availability.injury_status])
    if role_changed(availability):
        flags.append(ROLE_CHANGED)
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


def role_changed(availability: NflAvailability) -> bool:
    """Out, or an active depth that differs from the chart rank because a teammate ahead is Out."""
    if availability.injury_status == "Out":
        return True
    return (
        availability.depth_rank is not None
        and availability.active_depth_rank is not None
        and availability.active_depth_rank != availability.depth_rank
    )

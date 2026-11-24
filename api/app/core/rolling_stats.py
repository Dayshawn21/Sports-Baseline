"""Which rolling-stats row a tennis projection reads for a player."""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.repositories.players import PlayerRollingStats

# Below this many matches a surface split is too noisy to project from, so the
# all-surface row is used instead, and a prop line built on it is flagged.
SMALL_SAMPLE_MATCHES = 10


def pick_stats_for_player(
    player_id: Optional[int],
    surface: Optional[str],
    all_stats: dict[tuple[int, Optional[str]], "PlayerRollingStats"],
) -> Optional["PlayerRollingStats"]:
    """The surface row when it has SMALL_SAMPLE_MATCHES or more, else all-surface."""
    if player_id is None:
        return None
    surface_stats = all_stats.get((player_id, surface))
    if surface_stats is not None and (surface_stats.matches_count or 0) >= SMALL_SAMPLE_MATCHES:
        return surface_stats
    return all_stats.get((player_id, None))

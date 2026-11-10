"""Which of a match's data-quality flags a player in the admin stats queue still causes."""
from __future__ import annotations

from collections.abc import Collection, Iterable

ELO_FLAGS = frozenset({"elo_missing", "p1_elo_missing", "p2_elo_missing"})
STATS_FLAG = "ml_features_partial"


def missing_surfaces(
    stat_surfaces: Collection[str | None],
    match_surfaces: Iterable[str | None],
) -> list[str]:
    """The flagging match surfaces this player has no 52-week row for, sorted."""
    return sorted({s for s in match_surfaces if s is not None and s not in stat_surfaces})


def refine_player_flags(
    flags: Iterable[str],
    *,
    has_elo: bool,
    stat_surfaces: Collection[str | None],
    match_surfaces: Iterable[str | None],
) -> set[str]:
    """Drop the flags this player's data no longer explains.

    `stat_surfaces` holds the surfaces the player has 52-week rows for (None is the
    all-surface row). The feature builder flags a match when either the all-surface
    or the match-surface row is missing, so both must exist to clear the flag. A
    match with no surface can never get a surface row, so it does not hold the flag.
    """
    refined = set(flags)
    if has_elo:
        refined -= ELO_FLAGS
    if None in stat_surfaces and not missing_surfaces(stat_surfaces, match_surfaces):
        refined.discard(STATS_FLAG)
    return refined

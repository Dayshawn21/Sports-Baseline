"""Rank live tennis PrizePicks lines only in the slices 48e's forward check adopted (48g).

The grade itself is too heavy for the hosted API, so `tennis_prop_adoption`
stores the adopted slices and this reads that one small row. Anything it
cannot trust serves as "nothing adopted": the board stays gray, never 503s.
"""
from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tennis_prop_adoption import (
    ADOPTION_SEASON, UNSETTLED, adopted_from_payload, adopted_picks, adoption_report,
)
from app.core.tennis_prop_check import TENNIS_PROP_CHECK_RULE, TennisFrozenLine, TennisSlice
from app.repositories import report_snapshots
from app.repositories.props import Prop
from app.schemas.props import AdoptedPick, PropLine
from app.services.tennis.prop_snapshots import PROJECTION_VERSION

logger = logging.getLogger(__name__)


async def load_adopted(db: AsyncSession, version: str = PROJECTION_VERSION) -> frozenset[TennisSlice]:
    """The slices adopted for the version the board shows, or none."""
    snapshot = await report_snapshots.get_snapshot(db, adoption_report(version), ADOPTION_SEASON)
    if snapshot is None:
        logger.warning("No %s row: every tennis prop line stays gray", adoption_report(version))
        return frozenset()
    payload = snapshot.payload
    adopted = adopted_from_payload(payload, version) if isinstance(payload, dict) else None
    if adopted is None:
        logger.warning("Untrusted %s row (rule or version mismatch, or malformed): nothing adopted",
                       adoption_report(version))
        return frozenset()
    return adopted


def _live_line(prop: Prop, line: PropLine) -> TennisFrozenLine | None:
    if line.player_id is None or line.match_id is None or line.start_time is None:
        return None
    return TennisFrozenLine(
        line_id=line.id, player_id=line.player_id, match_id=line.match_id, stat_type=line.stat_type,
        match_tour=prop.match_tour, p1_tour=prop.p1_tour, p2_tour=prop.p2_tour, odds_type=line.odds_type,
        start_time=line.start_time, p_over=line.p_over, p_under=line.p_under, p_push=line.p_push,
        market_total_games=line.market_total_games, data_quality_flags=tuple(line.data_quality_flags),
        outcome=UNSETTLED,
    )


def apply_adoption(
    props: Sequence[Prop], lines: Sequence[PropLine], adopted: frozenset[TennisSlice], now: datetime,
    version: str = PROJECTION_VERSION,
) -> list[PropLine]:
    """`lines` (built from `props`, in order) with `adopted_pick` set on the lines that are picks."""
    live = [frozen for prop, line in zip(props, lines, strict=True) if (frozen := _live_line(prop, line)) is not None]
    picks = adopted_picks(live, adopted, now)
    return [
        line.model_copy(update={"adopted_pick": AdoptedPick(
            side=pick.side, probability=round(pick.probability, 3), break_even=round(pick.break_even, 3),
            margin=round(pick.margin, 3), rule=TENNIS_PROP_CHECK_RULE, projection_version=version,
        )}) if (pick := picks.get(line.id)) is not None else line
        for line in lines
    ]

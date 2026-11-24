"""Snapshot eligibility must use the timing of the match actually resolved."""
import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import TextClause

from app.repositories.props import get_today_props, get_today_match_odds_as_props
from app.schemas.props import PropLine
from app.services.tennis.prop_snapshots import skip_reason

NOW = datetime(2026, 10, 18, 12, tzinfo=timezone.utc)
SOURCE_START = NOW + timedelta(hours=2)


class _Result:
    def __init__(self, row: tuple) -> None:
        self.row = row

    def fetchall(self) -> list[tuple]:
        return [self.row]


class _Session:
    def __init__(self, row: tuple) -> None:
        self.row = row
        self.sql = ""

    async def execute(self, statement: TextClause, params: dict) -> _Result:
        self.sql = " ".join(str(statement).split())
        return _Result(self.row)


def _row() -> tuple:
    return (
        7, 11, "A Player", 99, "prizepicks", "Total Games", Decimal("21.5"), "standard",
        NOW - timedelta(hours=1), SOURCE_START, None, None, "Hard", None, "scheduled", False, 3,
    )


@pytest.mark.parametrize(
    ("resolved_start", "reason"),
    [(NOW - timedelta(minutes=1), "started"), (SOURCE_START + timedelta(hours=1), None), (None, None)],
)
def test_resolved_match_timing_reaches_eligibility_without_changing_the_display(resolved_start, reason):
    session = _Session((*_row(), SOURCE_START, resolved_start))
    [prop] = asyncio.run(get_today_props(cast(AsyncSession, session), source="prizepicks"))

    assert "COALESCE(relinked.id, p.match_id) AS match_id" in session.sql
    assert "COALESCE(relinked.status, m.status) AS match_status" in session.sql
    assert "p.start_time AS source_start_time" in session.sql
    # CASE preserves an unknown resolved start instead of falling back to the old match.
    assert "CASE WHEN relinked.id IS NOT NULL THEN relinked.start_utc ELSE m.start_utc END AS match_start_time" in session.sql
    assert "COALESCE(p.start_time, m.start_utc, relinked.start_utc) AS start_time" in session.sql
    assert (prop.match_id, prop.match_status, prop.best_of) == (99, "scheduled", 3)
    assert prop.source_start_time == SOURCE_START and prop.match_start_time == resolved_start
    assert prop.start_time == SOURCE_START
    line = PropLine(
        id=prop.id, player_id=prop.player_id, player_name=prop.player_name, match_id=prop.match_id,
        source=prop.source, stat_type=prop.stat_type, line=prop.line, odds_type=prop.odds_type,
        fetched_at=prop.fetched_at, start_time=prop.start_time,
    )
    assert skip_reason(prop, line, NOW) == reason


def test_match_odds_rows_keep_their_existing_positional_mapping():
    session = _Session(_row())
    [prop] = asyncio.run(get_today_match_odds_as_props(cast(AsyncSession, session), ["draftkings"]))

    assert prop.best_of == 3
    assert prop.source_start_time is None and prop.match_start_time is None


def test_live_props_carry_the_resolved_match_tours():
    # 17 base columns, the two timing columns, then player, match and both players' tours.
    session = _Session((*_row(), SOURCE_START, None, "WTA", "CHALLENGER", "WTA", "WTA"))
    [prop] = asyncio.run(get_today_props(cast(AsyncSession, session), source="prizepicks"))

    # Like match_start_time, a relinked match never borrows the stale link's tours.
    resolved = "CASE WHEN relinked.id IS NOT NULL THEN relinked.{0} ELSE m.{0} END"
    assert f"{resolved.format('tour')} AS match_tour" in session.sql
    assert "mm.tour, mm.p1_id, mm.p2_id" in session.sql
    assert f"LEFT JOIN players mp1 ON mp1.id = {resolved.format('p1_id')}" in session.sql
    assert f"LEFT JOIN players mp2 ON mp2.id = {resolved.format('p2_id')}" in session.sql
    assert (prop.player_tour, prop.match_tour, prop.p1_tour, prop.p2_tour) == ("WTA", "CHALLENGER", "WTA", "WTA")


def test_props_without_the_tour_columns_still_map():
    [prop] = asyncio.run(get_today_props(cast(AsyncSession, _Session(_row())), source="prizepicks"))

    assert (prop.match_tour, prop.p1_tour, prop.p2_tour) == (None, None, None)

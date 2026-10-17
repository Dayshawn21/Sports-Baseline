import asyncio
from datetime import UTC, date, datetime

import httpx
import pytest

from app.ingest.nflverse import SeasonNotPublished
from app.ingest.nflverse_depth_charts import NflverseDepthWeek, fetch_depth_charts, reduce_depth_charts

# The published 2026 header, verbatim.
HEADER = "dt,team,player_name,espn_id,gsis_id,pos_grp_id,pos_grp,pos_id,pos_name,pos_abb,pos_slot,pos_rank"
# CIN plays Sunday 9/13 (week 1) and Sunday 9/20 (week 2), bye in week 3, then 10/4 (week 4).
SCHEDULE = {"CIN": [(1, date(2026, 9, 13)), (2, date(2026, 9, 20)), (4, date(2026, 10, 4))]}
CHASE, HIGGINS = "00-0036900", "00-0035646"


def _row(dt: str, gsis_id: str, pos_abb: str = "WR", rank: str = "1", team: str = "CIN") -> str:
    return f"{dt},{team},Player,1,{gsis_id},1,3WR 1TE,1,Wide Receiver,{pos_abb},1,{rank}"


def _reduce(*rows: str) -> list[NflverseDepthWeek]:
    return reduce_depth_charts([HEADER, *rows], 2026, SCHEDULE)


def _weeks(parsed: list[NflverseDepthWeek]) -> list[tuple[int, str, int]]:
    return [(item.week, item.player_id, item.depth_rank) for item in parsed]


def test_a_game_day_snapshot_belongs_to_that_week_and_the_next_day_to_the_next() -> None:
    parsed = _reduce(
        _row("2026-09-13T12:10:00Z", CHASE, rank="1"),
        _row("2026-09-14T12:10:00Z", CHASE, rank="2"),
    )

    assert _weeks(parsed) == [(1, CHASE, 1), (2, CHASE, 2)]
    assert parsed[0].snapshot_at == datetime(2026, 9, 13, 12, 10, tzinfo=UTC)


def test_the_latest_snapshot_for_a_team_week_replaces_earlier_ones_whatever_the_file_order() -> None:
    parsed = _reduce(
        _row("2026-09-18T12:00:00Z", HIGGINS, rank="1"),
        _row("2026-09-17T12:00:00Z", CHASE, rank="1"),
        _row("2026-09-18T12:00:00Z", CHASE, rank="2"),
        _row("2026-09-18T06:00:00Z", CHASE, rank="1"),
    )

    # Only the 12:00 snapshot on 9/18 counts for week 2, so the 9/17 order is gone.
    assert sorted(_weeks(parsed)) == sorted([(2, CHASE, 2), (2, HIGGINS, 1)])
    assert {item.snapshot_at for item in parsed} == {datetime(2026, 9, 18, 12, 0, tzinfo=UTC)}


def test_a_bye_week_snapshot_maps_to_the_following_game() -> None:
    parsed = _reduce(_row("2026-09-27T12:00:00Z", CHASE))

    assert _weeks(parsed) == [(4, CHASE, 1)]


def test_a_player_listed_twice_keeps_the_better_rank() -> None:
    parsed = _reduce(
        _row("2026-09-18T12:00:00Z", CHASE, pos_abb="WR", rank="3"),
        _row("2026-09-18T12:00:00Z", CHASE, pos_abb="RB", rank="2"),
    )

    assert [(item.position, item.depth_rank) for item in parsed] == [("RB", 2)]


def test_snapshots_after_the_last_game_and_unscheduled_teams_are_dropped() -> None:
    parsed = _reduce(
        _row("2026-10-05T12:00:00Z", CHASE),
        _row("2026-09-18T12:00:00Z", CHASE, team="XYZ"),
    )

    assert parsed == []


def _fetch(status: int, body: str = "") -> list[NflverseDepthWeek]:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/depth_charts/depth_charts_2026.csv")
        return httpx.Response(status, content=body.encode())

    async def go() -> list[NflverseDepthWeek]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await fetch_depth_charts(client, 2026, SCHEDULE)

    return asyncio.run(go())


def test_fetch_streams_the_file_and_reduces_it() -> None:
    parsed = _fetch(200, "\n".join([HEADER, _row("2026-09-18T12:00:00Z", CHASE)]))

    assert _weeks(parsed) == [(2, CHASE, 1)]


def test_an_unpublished_depth_season_names_the_season_and_asset() -> None:
    with pytest.raises(SeasonNotPublished) as caught:
        _fetch(404)

    assert "depth charts" in str(caught.value)
    assert "2026" in str(caught.value)


class _BrokenStream(httpx.AsyncByteStream):
    """A body that spools a full row, then drops the connection."""

    async def __aiter__(self):
        yield "\n".join([HEADER, _row("2026-09-18T12:00:00Z", HIGGINS)]).encode() + b"\n"
        raise httpx.ReadError("connection reset")


def test_a_retried_download_parses_only_the_body_that_completed() -> None:
    complete = "\n".join([HEADER, _row("2026-09-18T12:00:00Z", CHASE)]).encode()
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) == 1:
            return httpx.Response(200, stream=_BrokenStream())
        return httpx.Response(200, content=complete)

    async def go() -> list[NflverseDepthWeek]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await fetch_depth_charts(client, 2026, SCHEDULE)

    parsed = asyncio.run(go())

    assert len(attempts) == 2
    assert _weeks(parsed) == [(2, CHASE, 1)]


def test_non_skill_positions_and_incomplete_rows_are_dropped() -> None:
    parsed = _reduce(
        _row("2026-09-18T12:00:00Z", CHASE, pos_abb="LT"),
        _row("2026-09-18T12:00:00Z", CHASE, pos_abb="PK"),
        _row("2026-09-18T12:00:00Z", ""),
        _row("2026-09-18T12:00:00Z", CHASE, rank=""),
        _row("not-a-time", CHASE),
    )

    assert parsed == []

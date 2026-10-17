import asyncio

import httpx
import pytest

from app.ingest.nflverse import SeasonNotPublished
from app.ingest.nflverse_injuries import NflverseInjuryWeek, fetch_injuries, parse_injuries

# The published 2026 header, verbatim.
HEADER = (
    "season,season_type,game_type,team,week,gsis_id,position,full_name,first_name,last_name,"
    "report_primary_injury,report_secondary_injury,report_status,practice_primary_injury,"
    "practice_secondary_injury,practice_status"
)
# 2024 files have no season_type column.
HEADER_2024 = HEADER.replace("season_type,", "")


def _row(gsis_id: str = "00-0000001", team: str = "CIN", week: str = "2", *, report_status: str = "",
         report_injury: str = "", practice_injury: str = "", practice_status: str = "",
         season: str = "2026", game_type: str = "REG", header: str = HEADER) -> str:
    values = {name: "" for name in header.split(",")}
    values.update(
        season=season, game_type=game_type, team=team, week=week, gsis_id=gsis_id,
        report_status=report_status, report_primary_injury=report_injury,
        practice_primary_injury=practice_injury, practice_status=practice_status,
    )
    if "season_type" in values:
        values["season_type"] = game_type
    return ",".join(values[name] for name in header.split(","))


def test_injury_rows_keep_game_status_practice_and_injury() -> None:
    parsed = parse_injuries([
        HEADER,
        _row(report_status="Questionable", report_injury="Hamstring", practice_injury="Hamstring",
             practice_status="Limited Participation in Practice"),
    ], 2026)

    assert parsed == [NflverseInjuryWeek(
        "00-0000001", 2026, 2, "CIN", "Questionable", "Limited Participation in Practice", "Hamstring",
    )]


def test_a_practice_only_row_has_no_game_status_and_keeps_the_practice_reason() -> None:
    parsed = parse_injuries([
        HEADER,
        _row(practice_injury="Not injury related - resting player", practice_status="Did Not Participate In Practice"),
    ], 2026)

    assert parsed[0].report_status is None
    assert parsed[0].primary_injury == "Not injury related - resting player"


def test_blank_and_na_values_become_none() -> None:
    parsed = parse_injuries([HEADER, _row(report_status="NA", practice_status=" ")], 2026)

    assert (parsed[0].report_status, parsed[0].practice_status, parsed[0].primary_injury) == (None, None, None)


def test_files_without_season_type_still_parse() -> None:
    parsed = parse_injuries([HEADER_2024, _row(season="2024", report_status="Out", header=HEADER_2024)], 2024)

    assert [(item.season, item.report_status) for item in parsed] == [(2024, "Out")]


def test_other_seasons_postseason_and_incomplete_rows_are_skipped() -> None:
    parsed = parse_injuries([
        HEADER,
        _row(season="2025"),
        _row(game_type="POST", week="19"),
        _row(gsis_id=""),
        _row(team=""),
        _row(week="NA"),
    ], 2026)

    assert parsed == []


def test_a_player_listed_twice_in_one_week_keeps_the_later_row() -> None:
    parsed = parse_injuries([HEADER, _row(report_status="Questionable"), _row(report_status="Out")], 2026)

    assert [item.report_status for item in parsed] == ["Out"]


def _fetch(status: int, body: str = "") -> list[NflverseInjuryWeek]:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/injuries/injuries_2026.csv")
        return httpx.Response(status, text=body)

    async def go() -> list[NflverseInjuryWeek]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await fetch_injuries(client, 2026)

    return asyncio.run(go())


def test_fetch_parses_the_season_file() -> None:
    parsed = _fetch(200, "\n".join([HEADER, _row(report_status="Out", report_injury="Knee")]))

    assert [(item.player_id, item.report_status, item.primary_injury) for item in parsed] == [("00-0000001", "Out", "Knee")]


def test_an_unpublished_injury_season_names_the_season_and_asset() -> None:
    with pytest.raises(SeasonNotPublished) as caught:
        _fetch(404)

    assert "injury reports" in str(caught.value)
    assert "2026" in str(caught.value)

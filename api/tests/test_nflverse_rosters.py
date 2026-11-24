import asyncio

import httpx
import pytest

from app.ingest.nflverse import SeasonNotPublished
from app.ingest.nflverse_rosters import NflverseRosterWeek, fetch_weekly_rosters, parse_weekly_rosters

# The published header, verbatim; DictReader ignores the columns the parser does not read.
HEADER = (
    "season,team,position,depth_chart_position,jersey_number,status,full_name,first_name,"
    "last_name,birth_date,height,weight,college,gsis_id,espn_id,sportradar_id,yahoo_id,"
    "rotowire_id,pff_id,pfr_id,fantasy_data_id,sleeper_id,years_exp,headshot_url,ngs_position,"
    "week,game_type,status_description_abbr,football_name,esb_id,gsis_it_id,smart_id,"
    "entry_year,rookie_year,draft_club,draft_number"
)


def _row(gsis_id: str, team: str, week: str, status: str = "ACT", *,
         season: str = "2026", game_type: str = "REG") -> str:
    values = {name: "" for name in HEADER.split(",")}
    values.update(season=season, team=team, status=status, gsis_id=gsis_id, week=week, game_type=game_type)
    return ",".join(values[name] for name in HEADER.split(","))


def test_roster_rows_keep_player_week_team_and_status() -> None:
    parsed = parse_weekly_rosters([HEADER, _row("00-0000001", "PIT", "1"), _row("00-0000001", "PIT", "2", "RES")], 2026)

    assert parsed == [
        NflverseRosterWeek("00-0000001", 2026, 1, "PIT", "ACT"),
        NflverseRosterWeek("00-0000001", 2026, 2, "PIT", "RES"),
    ]


def test_other_seasons_and_postseason_rows_are_dropped() -> None:
    parsed = parse_weekly_rosters([
        HEADER,
        _row("00-0000001", "PIT", "1", season="2025"),
        _row("00-0000001", "PIT", "19", game_type="POST"),
    ], 2026)

    assert parsed == []


def test_rows_without_an_id_team_or_week_are_skipped() -> None:
    parsed = parse_weekly_rosters([
        HEADER,
        _row("", "PIT", "1"),
        _row("00-0000001", "", "1"),
        _row("00-0000001", "PIT", ""),
        _row("00-0000001", "PIT", "NA"),
    ], 2026)

    assert parsed == []


def test_a_player_listed_twice_in_one_week_keeps_the_later_row() -> None:
    parsed = parse_weekly_rosters([
        HEADER,
        _row("00-0000001", "NYJ", "2", "CUT"),
        _row("00-0000001", "MIA", "2", "ACT"),
    ], 2026)

    assert parsed == [NflverseRosterWeek("00-0000001", 2026, 2, "MIA", "ACT")]


def _fetch(status: int, body: str = "") -> list[NflverseRosterWeek]:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/weekly_rosters/roster_weekly_2026.csv")
        return httpx.Response(status, text=body)

    async def go() -> list[NflverseRosterWeek]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await fetch_weekly_rosters(client, 2026)

    return asyncio.run(go())


def test_fetch_parses_the_season_file() -> None:
    parsed = _fetch(200, "\n".join([HEADER, _row("00-0000001", "PIT", "1")]))

    assert parsed == [NflverseRosterWeek("00-0000001", 2026, 1, "PIT", "ACT")]


def test_an_unpublished_roster_season_names_the_season_and_asset() -> None:
    with pytest.raises(SeasonNotPublished) as caught:
        _fetch(404)

    assert "weekly rosters" in str(caught.value)
    assert "2026" in str(caught.value)


def test_a_relocated_franchise_is_stored_under_its_current_code() -> None:
    parsed = parse_weekly_rosters([HEADER, _row("00-0000001", "OAK", "1", season="2019")], 2019)

    assert [item.team for item in parsed] == ["LV"]

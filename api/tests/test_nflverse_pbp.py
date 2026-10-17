import asyncio
import gzip

import httpx
import pytest

from app.ingest.nflverse import SeasonNotPublished
from app.ingest.nflverse_pbp import (
    NflverseRedZoneGame,
    NflverseRedZoneSeason,
    fetch_red_zone_usage,
    parse_red_zone_usage,
)

# Published column names, in a subset: the real file has ~370 columns and DictReader
# ignores the rest.
HEADER = (
    "play_id,game_id,season_type,week,yardline_100,play_type,qb_scramble,rush_attempt,"
    "pass_attempt,sack,two_point_attempt,receiver_player_id,rusher_player_id,air_yards,season,"
    "punt_attempt,punter_player_id"
)
GAME = "2024_01_ARI_BUF"
RB, WR, QB, P = "00-0000001", "00-0000002", "00-0000003", "00-0000004"


def _play(yardline: str, play_type: str, *, rush: str = "0", pass_: str = "0", sack: str = "0",
          two_point: str = "0", scramble: str = "0", receiver: str = "", rusher: str = "", air_yards: str = "",
          season_type: str = "REG", season: str = "2024", game: str = GAME, punt: str = "0",
          punter: str = "") -> str:
    return (
        f"1,{game},{season_type},1,{yardline},{play_type},{scramble},{rush},"
        f"{pass_},{sack},{two_point},{receiver},{rusher},{air_yards},{season},{punt},{punter}"
    )


def _parse(*plays: str) -> dict[str, NflverseRedZoneGame]:
    parsed = parse_red_zone_usage([HEADER, *plays], 2024)
    return {item.player_id: item for item in parsed.games}


def test_punts_count_for_the_punter_per_game_and_nothing_else() -> None:
    punter = _parse(
        _play("60", "punt", punt="1", punter=P),
        _play("45", "punt", punt="1", punter=P),
        _play("70", "no_play", punter=P),
    )[P]

    assert punter.punts == 2
    assert (punter.rz20_carries, punter.rz20_targets, punter.end_zone_targets) == (0, 0, 0)


def test_a_preseason_punt_or_one_without_a_punter_is_not_counted() -> None:
    assert _parse(
        _play("60", "punt", punt="1", punter=P, season_type="PRE"),
        _play("60", "punt", punt="1"),
    ) == {}


def test_red_zone_players_carry_zero_punts() -> None:
    assert _parse(_play("5", "run", rush="1", rusher=RB))[RB].punts == 0


def test_a_carry_at_the_five_counts_inside_both_the_five_and_the_twenty() -> None:
    rb = _parse(_play("5", "run", rush="1", rusher=RB))[RB]

    assert (rb.rz20_carries, rb.rz5_carries, rb.rz20_targets, rb.rz5_targets) == (1, 1, 0, 0)
    assert rb.game_id == GAME


def test_a_carry_at_the_six_counts_inside_the_twenty_only() -> None:
    rb = _parse(_play("6", "run", rush="1", rusher=RB))[RB]

    assert (rb.rz20_carries, rb.rz5_carries) == (1, 0)


def test_a_carry_at_the_twenty_one_is_not_red_zone() -> None:
    assert _parse(_play("21", "run", rush="1", rusher=RB)) == {}


def test_a_target_counts_for_the_receiver_and_counts_accumulate_per_game() -> None:
    parsed = parse_red_zone_usage([
        HEADER,
        _play("3", "pass", pass_="1", receiver=WR),
        _play("18", "pass", pass_="1", receiver=WR),
        _play("18", "pass", pass_="1", receiver=WR, game="2024_02_BUF_MIA"),
    ], 2024)
    by_game = {item.game_id: item for item in parsed.games}

    week_one = by_game[GAME]
    assert (week_one.rz20_targets, week_one.rz5_targets, week_one.rz20_carries) == (2, 1, 0)
    assert by_game["2024_02_BUF_MIA"].rz20_targets == 1


def test_end_zone_target_requires_a_non_sack_pass_to_a_receiver_that_reaches_the_end_zone() -> None:
    parsed = _parse(
        _play("12", "pass", pass_="1", receiver=WR, air_yards="12"),
        _play("12", "pass", pass_="1", receiver=WR, air_yards="11"),
        _play("12", "pass", pass_="1", sack="1", receiver=WR, air_yards="12"),
        _play("12", "pass", pass_="1", air_yards="12"),
        _play("12", "pass", pass_="1", receiver=WR, air_yards=""),
    )

    assert parsed[WR].end_zone_targets == 1


def test_a_qb_scramble_is_a_carry() -> None:
    qb = _parse(_play("4", "run", rush="1", scramble="1", rusher=QB))[QB]

    assert qb.rz5_carries == 1


def test_non_opportunities_are_excluded() -> None:
    excluded = _parse(
        _play("8", "pass", pass_="1", sack="1", rusher=""),
        _play("2", "pass", pass_="1", two_point="1", receiver=WR),
        _play("2", "run", rush="1", two_point="1", rusher=RB),
        _play("10", "no_play", receiver=WR),
        # Kneels carry rush_attempt=1 in the real file.
        _play("3", "qb_kneel", rush="1", rusher=QB),
        _play("3", "qb_spike", pass_="1"),
        _play("5", "run", rush="1", rusher=RB, season_type="POST"),
        _play("5", "run", rush="1", rusher=RB, season="2023"),
        _play("5", "run", rush="1", rusher=""),
        _play("5", "pass", pass_="1", receiver=""),
        _play("", "run", rush="1", rusher=RB),
        _play("NA", "run", rush="1", rusher=RB),
    )

    assert excluded == {}


def test_a_game_with_no_red_zone_plays_is_still_listed_so_it_can_be_zeroed() -> None:
    parsed = parse_red_zone_usage([
        HEADER,
        _play("40", "run", rush="1", rusher=RB),
        _play("5", "run", rush="1", rusher=RB, game="2024_02_BUF_MIA"),
        _play("5", "run", rush="1", rusher=RB, game="2024_20_BUF_KC", season_type="POST"),
    ], 2024)

    assert parsed.game_ids == {GAME, "2024_02_BUF_MIA"}
    assert [item.game_id for item in parsed.games] == ["2024_02_BUF_MIA"]


def _fetch(status: int, body: bytes = b"") -> NflverseRedZoneSeason:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=body)

    async def go() -> NflverseRedZoneSeason:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await fetch_red_zone_usage(client, 2024)

    return asyncio.run(go())


def test_fetch_decompresses_and_parses_the_season_archive() -> None:
    body = gzip.compress("\n".join([HEADER, _play("2", "run", rush="1", rusher=RB)]).encode())

    parsed = _fetch(200, body)

    assert [(item.player_id, item.rz5_carries) for item in parsed.games] == [(RB, 1)]


def test_an_unpublished_play_by_play_season_names_the_season_and_asset() -> None:
    with pytest.raises(SeasonNotPublished) as caught:
        _fetch(404)

    assert "play-by-play" in str(caught.value)
    assert "2024" in str(caught.value)

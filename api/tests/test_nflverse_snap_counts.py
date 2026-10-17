import asyncio

import httpx
import pytest

from app.ingest.nflverse import SeasonNotPublished
from app.ingest.nflverse_snap_counts import (
    NflverseSnapGame,
    NflverseSnapSeason,
    fetch_snap_counts,
    parse_pfr_gsis_map,
    parse_snap_counts,
    resolve_gsis_ids,
)

# The published headers, verbatim (players.csv trimmed to the columns before and including pfr_id).
SNAP_HEADER = (
    "game_id,pfr_game_id,season,game_type,week,player,pfr_player_id,position,team,opponent,"
    "offense_snaps,offense_pct,defense_snaps,defense_pct,st_snaps,st_pct"
)
PLAYERS_HEADER = "gsis_id,display_name,common_first_name,first_name,last_name,short_name,football_name,suffix,esb_id,nfl_id,pfr_id"


def _snap(pfr_id: str = "KamaAl00", game_id: str = "2025_01_ARI_NO", position: str = "RB", *,
          offense_snaps: str = "59", offense_pct: str = "0.79", season: str = "2025",
          game_type: str = "REG", week: str = "1", team: str = "NO") -> str:
    return (
        f"{game_id},202509070nor,{season},{game_type},{week},Alvin Kamara,{pfr_id},{position},{team},ARI,"
        f"{offense_snaps},{offense_pct},0,0,0,0"
    )


def _player(gsis_id: str, pfr_id: str) -> str:
    return f"{gsis_id},Name,,,,,,,,,{pfr_id}"


def test_snap_rows_keep_ids_week_team_and_share_as_a_fraction() -> None:
    parsed = parse_snap_counts([SNAP_HEADER, _snap()], 2025)

    assert parsed.games == [NflverseSnapGame("KamaAl00", "2025_01_ARI_NO", 2025, 1, "NO", 59, 0.79)]
    assert parsed.game_ids == frozenset({"2025_01_ARI_NO"})


def test_blank_snaps_are_none_and_zero_stays_zero() -> None:
    parsed = parse_snap_counts([
        SNAP_HEADER,
        _snap("BlankA00", offense_snaps="", offense_pct="NA"),
        _snap("ZeroAa00", offense_snaps="0", offense_pct="0"),
    ], 2025)

    by_id = {item.pfr_player_id: (item.offense_snaps, item.offense_pct) for item in parsed.games}
    assert by_id == {"BlankA00": (None, None), "ZeroAa00": (0, 0.0)}


def test_other_seasons_postseason_and_non_skill_positions_are_skipped() -> None:
    parsed = parse_snap_counts([
        SNAP_HEADER,
        _snap(season="2024"),
        _snap(game_type="WC", game_id="2025_19_ARI_NO", week="19"),
        _snap("ReidJu00", position="S"),
        _snap("StraCo01", position="G"),
        _snap("HalfBa00", position="HB"),
        _snap("FullBa00", position="FB"),
    ], 2025)

    assert sorted(item.pfr_player_id for item in parsed.games) == ["FullBa00", "HalfBa00"]
    assert parsed.game_ids == frozenset({"2025_01_ARI_NO"})


def test_a_game_with_only_skipped_rows_is_still_listed() -> None:
    parsed = parse_snap_counts([SNAP_HEADER, _snap("ReidJu00", position="S")], 2025)

    assert parsed.games == []
    assert parsed.game_ids == frozenset({"2025_01_ARI_NO"})


def test_rows_missing_a_player_game_week_or_team_are_skipped() -> None:
    parsed = parse_snap_counts([
        SNAP_HEADER,
        _snap(pfr_id=""),
        _snap(game_id=""),
        _snap(week="NA"),
        _snap(team=""),
    ], 2025)

    assert parsed.games == []


def test_a_player_listed_twice_in_one_game_keeps_the_later_row() -> None:
    parsed = parse_snap_counts([SNAP_HEADER, _snap(offense_snaps="40"), _snap(offense_snaps="59")], 2025)

    assert [item.offense_snaps for item in parsed.games] == [59]


def test_pfr_map_keeps_one_to_one_ids_and_drops_ambiguous_and_incomplete_ones() -> None:
    mapping = parse_pfr_gsis_map([
        PLAYERS_HEADER,
        _player("00-0033906", "KamaAl00"),
        _player("00-0000001", "TwinAa00"),
        _player("00-0000002", "TwinAa00"),
        _player("00-0000003", ""),
        _player("", "NoGsis00"),
        _player("00-0000004", "NA"),
    ])

    assert mapping == {"KamaAl00": "00-0033906"}


def test_a_repeated_identical_mapping_is_not_ambiguous() -> None:
    mapping = parse_pfr_gsis_map([PLAYERS_HEADER, _player("00-0033906", "KamaAl00"), _player("00-0033906", "KamaAl00")])

    assert mapping == {"KamaAl00": "00-0033906"}


def _game(pfr_id: str, game_id: str = "2025_01_ARI_NO", snaps: int = 59) -> NflverseSnapGame:
    return NflverseSnapGame(pfr_id, game_id, 2025, 1, "NO", snaps, 0.79)


def test_resolve_attaches_gsis_ids_and_counts_unmapped_rows() -> None:
    snaps = NflverseSnapSeason(frozenset({"2025_01_ARI_NO"}), [_game("KamaAl00"), _game("UnknAa00")])

    resolved = resolve_gsis_ids(snaps, {"KamaAl00": "00-0033906"})

    assert resolved.rows == [("00-0033906", _game("KamaAl00"))]
    assert resolved.unmapped == 1


def test_two_pfr_ids_for_one_player_in_one_game_keep_the_later_row() -> None:
    snaps = NflverseSnapSeason(
        frozenset({"2025_01_ARI_NO", "2025_02_NO_SF"}),
        [_game("OldIdA00", snaps=40), _game("NewIdA00", snaps=59), _game("NewIdA00", "2025_02_NO_SF", 61)],
    )

    resolved = resolve_gsis_ids(snaps, {"OldIdA00": "00-0000001", "NewIdA00": "00-0000001"})

    assert [(gsis_id, game.game_id, game.offense_snaps) for gsis_id, game in resolved.rows] == [
        ("00-0000001", "2025_01_ARI_NO", 59), ("00-0000001", "2025_02_NO_SF", 61),
    ]


def _fetch(status: int, body: str = "") -> NflverseSnapSeason:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/snap_counts/snap_counts_2025.csv")
        return httpx.Response(status, text=body)

    async def go() -> NflverseSnapSeason:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await fetch_snap_counts(client, 2025)

    return asyncio.run(go())


def test_fetch_parses_the_season_file() -> None:
    parsed = _fetch(200, "\n".join([SNAP_HEADER, _snap()]))

    assert [(item.pfr_player_id, item.offense_pct) for item in parsed.games] == [("KamaAl00", 0.79)]


def test_an_unpublished_snap_season_names_the_season_and_asset() -> None:
    with pytest.raises(SeasonNotPublished) as caught:
        _fetch(404)

    assert "snap counts" in str(caught.value)
    assert "2025" in str(caught.value)

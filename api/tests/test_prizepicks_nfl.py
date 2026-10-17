import asyncio

import httpx
import pytest

from app.ingest.prizepicks import (
    RATE_LIMIT_MAX_WAIT_S, _parse_projections, retry_after_seconds,
)
from app.ingest.prizepicks_nfl import (
    PrizePicksRateLimited, board_nfl_leagues, is_full_game_nfl_league, market_for_prizepicks_stat, run,
    unmapped_stat_counts,
)
from app.core.prop_sports import market_for_stat
from app.nfl.markets import NFL_PROPS, NflLineOnlyMarket, NflPropMarket, NflPropSegment, segment_for_league_name


def _response(headers: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(429, headers=headers or {})


def test_prizepicks_nfl_mapping_excludes_noisy_markets() -> None:
    assert market_for_prizepicks_stat("Passing Yards") == NflPropMarket.PASSING_YARDS
    assert market_for_prizepicks_stat("Pass Yards") == NflPropMarket.PASSING_YARDS
    assert market_for_prizepicks_stat("First TD") is None


def test_current_prizepicks_spellings_map_to_supported_markets() -> None:
    assert market_for_prizepicks_stat("Rush Yards") == NflPropMarket.RUSHING_YARDS
    assert market_for_prizepicks_stat("Anytime TDs") == NflPropMarket.ANYTIME_TOUCHDOWN
    assert market_for_prizepicks_stat("Rushing Yards") == NflPropMarket.RUSHING_YARDS
    assert market_for_prizepicks_stat("Anytime Touchdowns") == NflPropMarket.ANYTIME_TOUCHDOWN


def test_unmapped_stat_counts_reports_only_skipped_names() -> None:
    items = [
        {"stat_type": "Rush Yards"},
        {"stat_type": "Longest Reception"},
        {"stat_type": "Longest Reception"},
        {"stat_type": "Sacks"},
        {"stat_type": "Pass TDs"},
    ]
    assert unmapped_stat_counts(items) == {"Longest Reception": 2, "Sacks": 1}


LINE_ONLY_NAMES = {
    "Rec Targets": NflLineOnlyMarket.RECEIVING_TARGETS,
    "Pass TDs": NflLineOnlyMarket.PASSING_TOUCHDOWNS,
    "INT": NflLineOnlyMarket.INTERCEPTIONS,
    "Rush+Rec Yds": NflLineOnlyMarket.RUSHING_RECEIVING_YARDS,
    "Pass+Rush Yds": NflLineOnlyMarket.PASSING_RUSHING_YARDS,
    "Pass+Rush+Rec TDs": NflLineOnlyMarket.PASSING_RUSHING_RECEIVING_TOUCHDOWNS,
    "FG Made": NflLineOnlyMarket.FIELD_GOALS_MADE,
    "Kicking Points": NflLineOnlyMarket.KICKING_POINTS,
    "Punts": NflLineOnlyMarket.PUNTS,
}


@pytest.mark.parametrize(("stat_type", "market"), LINE_ONLY_NAMES.items())
def test_line_only_stats_are_stored_but_never_read_as_modelled(stat_type: str, market: NflLineOnlyMarket) -> None:
    assert market_for_stat(stat_type, NFL_PROPS) == market
    assert market_for_prizepicks_stat(stat_type) is None


@pytest.mark.parametrize("stat_type", [
    "Receiving Yards (Combo)", "Rush Yards (Combo)", "Pass Yards (Combo)", "FG Made (Combo)", "Rush TDs", "Sacks",
    "Kicking Points (Combo)", "Punts (Combo)", "Punts Inside 20", "PAT Made (Combo)",
])
def test_combo_and_unsettleable_stats_stay_unmapped(stat_type: str) -> None:
    assert market_for_stat(stat_type, NFL_PROPS) is None


def test_every_alias_lands_in_exactly_one_market_set() -> None:
    modelled, line_only = set(NflPropMarket), set(NflLineOnlyMarket)
    assert not {str(m) for m in modelled} & {str(m) for m in line_only}
    for market in NFL_PROPS.market_aliases.values():
        assert (market in modelled) != (market in line_only), market
    assert set(NFL_PROPS.market_aliases.values()) >= line_only


def _projection_payload(player_attributes: dict[str, str]) -> dict:
    """One projection plus its new_player include, in PrizePicks JSON:API shape."""
    return {
        "data": [{
            "type": "projection",
            "id": "10433855",
            "attributes": {
                "stat_type": "Receiving Yards",
                "line_score": 58.5,
                "start_time": "2026-09-17T20:15:00.000-04:00",
            },
            "relationships": {"new_player": {"data": {"type": "new_player", "id": "42"}}},
        }],
        "included": [{"type": "new_player", "id": "42", "attributes": player_attributes}],
    }


def test_parser_keeps_the_team_and_position_needed_to_disambiguate() -> None:
    raw = _projection_payload({"name": "Jaylen Waddle", "position": "WR", "team": "MIA"})

    [line] = _parse_projections(raw, league_id=9)

    assert line["player_name"] == "Jaylen Waddle"
    assert line["player_team"] == "MIA"
    assert line["player_position"] == "WR"


def test_parser_reports_missing_team_and_position_as_none() -> None:
    raw = _projection_payload({"name": "Jaylen Waddle"})

    [line] = _parse_projections(raw, league_id=9)

    # None, not "", so resolution can tell "provider said nothing" from a real value.
    assert line["player_team"] is None
    assert line["player_position"] is None


def test_full_game_league_is_identified() -> None:
    assert is_full_game_nfl_league("NFL")
    assert is_full_game_nfl_league(" nfl ")
    for other in ("NFLSZN", "NFL1H", "NFL2H", "NFL1Q", "NFL4Q"):
        assert not is_full_game_nfl_league(other), other


def test_every_nfl_league_maps_to_a_distinct_segment() -> None:
    assert segment_for_league_name("NFL") is NflPropSegment.FULL_GAME
    assert segment_for_league_name("NFLSZN") is NflPropSegment.SEASON
    assert segment_for_league_name("NFL1H") is NflPropSegment.FIRST_HALF
    assert segment_for_league_name("NFL2H") is NflPropSegment.SECOND_HALF
    assert segment_for_league_name("NFL1Q") is NflPropSegment.Q1
    assert segment_for_league_name("NFL4Q") is NflPropSegment.Q4


def test_board_leagues_exclude_unused_nfl_periods() -> None:
    leagues = [{"id": str(index), "attributes": {"name": name}} for index, name in enumerate(
        ("NFL", "NFL1H", "NFL1Q", "NFL2H", "NFL2Q", "NFL3Q", "NFL4Q", "NFLSZN"), start=1,
    )]

    assert [(league_id, segment) for league_id, _, segment in board_nfl_leagues(leagues)] == [
        (1, NflPropSegment.FULL_GAME), (2, NflPropSegment.FIRST_HALF), (3, NflPropSegment.Q1),
    ]


def test_segment_mapping_normalizes_provider_spelling() -> None:
    assert segment_for_league_name("nfl 1h") is NflPropSegment.FIRST_HALF
    assert segment_for_league_name("NFL-1Q") is NflPropSegment.Q1


def test_non_nfl_and_unknown_nfl_leagues_are_not_ingested() -> None:
    for name in ("NBA", "MLB", "NCAAF", ""):
        assert segment_for_league_name(name) is None, name
    # An unrecognized NFL suffix must not silently fall through as full game.
    assert segment_for_league_name("NFLDRAFT") is None


def test_retry_after_header_wins_over_exponential_backoff() -> None:
    assert retry_after_seconds(_response({"Retry-After": "30"}), attempt=1) == 30.0


def test_retry_after_falls_back_to_exponential_backoff() -> None:
    assert retry_after_seconds(_response(), attempt=1) == 5.0
    assert retry_after_seconds(_response(), attempt=3) == 20.0


def test_retry_after_zero_still_waits_instead_of_busy_looping() -> None:
    assert retry_after_seconds(_response({"Retry-After": "0"}), attempt=1) == 1.0


def test_retry_after_is_capped_and_survives_a_garbage_header() -> None:
    assert retry_after_seconds(_response({"Retry-After": "99999"}), attempt=1) == RATE_LIMIT_MAX_WAIT_S
    assert retry_after_seconds(_response({"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}), attempt=2) == 10.0


def test_run_raises_a_clear_error_when_every_league_is_throttled(monkeypatch) -> None:
    async def fake_leagues(_client):
        return [{"id": "163", "attributes": {"name": "NFL"}}]

    async def fake_projections(_client, league_id):
        raise httpx.HTTPStatusError("429", request=httpx.Request("GET", "http://t"), response=_response())

    monkeypatch.setattr("app.ingest.prizepicks_props._fetch_leagues", fake_leagues)
    monkeypatch.setattr("app.ingest.prizepicks_props._fetch_projections", fake_projections)

    with pytest.raises(PrizePicksRateLimited):
        asyncio.run(run(dry_run=True))


def test_run_rejects_an_empty_league_catalog_instead_of_reporting_zero(monkeypatch) -> None:
    async def no_leagues(_client):
        return []

    monkeypatch.setattr("app.ingest.prizepicks_props._fetch_leagues", no_leagues)

    with pytest.raises(PrizePicksRateLimited):
        asyncio.run(run(dry_run=True))

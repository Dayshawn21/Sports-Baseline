import pytest

from app.core.prop_sports import FULL_GAME_SEGMENT, board_leagues, market_for_stat, segment_for_league_name
from app.ingest.prizepicks import _parse_projections
from app.ingest.prizepicks_props import unmapped_stat_counts
from app.nhl.markets import NHL_PROPS, NhlLineOnlyMarket


@pytest.mark.parametrize(("stat", "market"), [
    ("Shots On Goal", "shots_on_goal"),
    ("Points", "points"),
    ("Assists", "assists"),
    ("Goals", "goals"),
    ("Power Play Points", "power_play_points"),
    ("Blocked Shots", "blocked_shots"),
    ("Plus/Minus", "plus_minus"),
    ("Goalie Saves", "goalie_saves"),
    ("Hits", "hits"),
    ("Time On Ice", "time_on_ice"),
    ("Goals Allowed", "goals_allowed"),
    ("Faceoffs Won", "faceoffs_won"),
])
def test_observed_stat_names_keep_their_stored_market(stat: str, market: str) -> None:
    assert market_for_stat(stat, NHL_PROPS) == market
    assert market_for_stat(f" {stat.upper()} ", NHL_PROPS) == market


def test_only_full_game_nhl_is_selected_without_hardcoding_its_id() -> None:
    names = ["NHL", "NHL1P", "NHL2P", "NHL3P", "NHLSZN", "NHLP", "NHL SERIES", "NBA", "NFL"]
    leagues = [{"id": str(i), "attributes": {"name": name}} for i, name in enumerate(names, 900)]
    assert board_leagues(leagues, NHL_PROPS) == [(900, "NHL", FULL_GAME_SEGMENT)]


@pytest.mark.parametrize(("name", "segment"), [
    (" NHL ", FULL_GAME_SEGMENT), ("NHL1P", "p1"), ("NHLSZN", "season"),
    ("NHL2P", None), ("NHL3P", None), ("NHLP", None), ("NHL SERIES", None),
])
def test_recognized_and_unknown_suffixes(name: str, segment: str | None) -> None:
    assert segment_for_league_name(name, NHL_PROPS) == segment


@pytest.mark.parametrize("stat", [
    "Shots On Goal (Combo)", "Goals (Combo)", "Goalie Saves (Combo)",
    "Fantasy Score", "Goalie Fantasy Score", "Shots", "Unknown Stat",
])
def test_unsupported_names_are_skipped_and_counted_for_logging(stat: str) -> None:
    assert market_for_stat(stat, NHL_PROPS) is None
    assert unmapped_stat_counts([{"stat_type": stat}, {"stat_type": "Points"}], NHL_PROPS) == {stat: 1}


def test_all_configured_markets_are_line_only() -> None:
    assert set(NHL_PROPS.market_aliases.values()) == set(NhlLineOnlyMarket)
    assert all(isinstance(market, NhlLineOnlyMarket) for market in NHL_PROPS.market_aliases.values())
    assert NHL_PROPS.code == "nhl"
    assert NHL_PROPS.period_label == "week"


@pytest.mark.parametrize("position", ["F", "D", "G"])
def test_time_on_ice_preserves_provider_minutes_for_skaters_and_goalies(position: str) -> None:
    raw = {
        "data": [{
            "type": "projection", "id": "16126764",
            "attributes": {
                "stat_type": "Time On Ice", "stat_display_name": "Minutes",
                "line_score": 59.25, "odds_type": "standard",
                "start_time": "2026-10-23T20:00:00.000-04:00",
            },
            "relationships": {"new_player": {"data": {"id": "230115"}}},
        }],
        "included": [{
            "type": "new_player", "id": "230115",
            "attributes": {"name": "Example Player", "team": "CHI", "position": position},
        }],
    }
    item, = _parse_projections(raw, 8)
    assert market_for_stat(item["stat_type"], NHL_PROPS) == "time_on_ice"
    assert item["line"] == 59.25
    assert item["player_position"] == position
    assert item["raw_json"]["attributes"]["stat_display_name"] == "Minutes"

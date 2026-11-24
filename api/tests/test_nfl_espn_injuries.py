from datetime import datetime, timezone

import pytest

from app.core.nfl_espn_injuries import more_severe, parse_injury_feed
from app.ingest.nfl_espn_injuries import link_entries, parse_espn_gsis_map


def _entry(athlete_id: str, name: str, status: str, injury: str | None = "Groin", date: str = "2026-11-15T16:21Z") -> dict:
    return {
        "status": status,
        "date": date,
        "shortComment": f"{name} update.",
        "details": {"type": injury} if injury else {},
        "athlete": {
            "displayName": name,
            "links": [{"href": f"https://www.espn.com/nfl/player/_/id/{athlete_id}/{name.lower().replace(' ', '-')}"}],
        },
    }


FEED = {
    "injuries": [
        {"id": "12", "displayName": "Kansas City Chiefs", "injuries": [
            _entry("4567048", "Kenneth Walker III", "Out"),
            _entry("100", "Healthy Again", "Active"),
        ]},
        {"id": "1", "displayName": "Atlanta Falcons", "injuries": [
            _entry("200", "Season Over", "Injured Reserve", injury="Knee"),
            _entry("300", "Maybe Not", "Doubtful", injury=None, date="not a date"),
            {"status": "Out", "athlete": {"displayName": "No Link", "links": []}},
            "garbage",
        ]},
    ],
}


def test_parse_keeps_statused_entries_and_normalizes_injured_reserve():
    teams, entries = parse_injury_feed(FEED)
    by_id = {entry.espn_athlete_id: entry for entry in entries}

    assert teams == 2
    assert set(by_id) == {"4567048", "200", "300"}
    walker = by_id["4567048"]
    assert (walker.status, walker.injury, walker.player_name) == ("Out", "Groin", "Kenneth Walker III")
    assert walker.espn_updated_at == datetime(2026, 11, 15, 16, 21, tzinfo=timezone.utc)
    assert by_id["200"].status == "Out"
    assert by_id["300"].status == "Doubtful"
    assert by_id["300"].injury is None
    assert by_id["300"].espn_updated_at is None


def test_athlete_listed_twice_keeps_the_more_severe_status():
    feed = {"injuries": [{"injuries": [_entry("1", "Two Rows", "Questionable"), _entry("1", "Two Rows", "Out")]}]}

    _, entries = parse_injury_feed(feed)

    assert [entry.status for entry in entries] == ["Out"]


def test_feed_without_injuries_list_is_rejected():
    with pytest.raises(ValueError):
        parse_injury_feed({"status": "error"})


@pytest.mark.parametrize(("official", "espn", "shown"), [
    ("Questionable", "Out", "Out"),
    ("Doubtful", "Out", "Out"),
    (None, "Out", "Out"),
    ("Out", None, "Out"),
    ("Out", "Questionable", "Out"),
    ("Questionable", None, "Questionable"),
    (None, None, None),
])
def test_more_severe_only_downgrades(official, espn, shown):
    assert more_severe(official, espn) == shown


ROSTER = [
    "season,team,full_name,gsis_id,espn_id,week",
    "2026,SEA,Kenneth Walker III,00-0038134,4567048,1",
    "2026,KC,Kenneth Walker III,00-0038134,4567048,10",
    "2026,ATL,No Espn,00-0000001,NA,10",
    "2026,ATL,Float Id,00-0000002,200.0,10",
    "2026,ATL,No Gsis,,300,10",
]


def test_gsis_map_skips_missing_ids_and_strips_float_suffix():
    assert parse_espn_gsis_map(ROSTER) == {"4567048": "00-0038134", "200": "00-0000002"}


def test_link_entries_drops_unmapped_athletes():
    _, entries = parse_injury_feed(FEED)

    linked = link_entries(entries, parse_espn_gsis_map(ROSTER))

    assert sorted((gsis, entry.status) for gsis, entry in linked) == [("00-0000002", "Out"), ("00-0038134", "Out")]

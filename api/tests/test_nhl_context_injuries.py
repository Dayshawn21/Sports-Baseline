from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

import pytest

from app.core.nhl_context import ESPN_NHL_TEAMS, espn_nhl_team_code, parse_injury_feed

FIXTURES = Path(__file__).parent / "fixtures"


def feed() -> dict[str, object]:
    return json.loads((FIXTURES / "espn_nhl_injuries.json").read_text(encoding="utf-8"))


def groups(payload: dict[str, object]) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], payload["injuries"])


def entries(payload: dict[str, object]) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], groups(payload)[0]["injuries"])


def athlete(payload: dict[str, object]) -> dict[str, object]:
    return cast(dict[str, object], entries(payload)[0]["athlete"])


def test_verified_directory_maps_all_32_teams_without_changing_shared_aliases() -> None:
    directory = json.loads((FIXTURES / "espn_nhl_teams.json").read_text())
    assert {team_id: espn_nhl_team_code(code) for team_id, code in directory.items()} == ESPN_NHL_TEAMS
    assert len(set(ESPN_NHL_TEAMS.values())) == 32
    from app.core.nhl_names import nhl_team_code

    assert nhl_team_code("LA") == "LA"


@pytest.mark.parametrize(("source", "canonical"), [
    ("LA", "LAK"), ("NJ", "NJD"), ("SJ", "SJS"), ("TB", "TBL"),
    ("UTAH", "UTA"), (" tb ", "TBL"), ("LAK", "LAK"), ("UNKNOWN", "UNKNOWN"),
    (None, None), ("", None), ("  ", None),
])
def test_espn_aliases_are_explicit(source: str | None, canonical: str | None) -> None:
    assert espn_nhl_team_code(source) == canonical


def test_live_fixture_preserves_source_identity_and_statuses() -> None:
    parsed = parse_injury_feed(feed())
    assert parsed.source_timestamp == datetime(2026, 10, 24, 16, 18, 22, tzinfo=timezone.utc)
    assert {row.status for row in parsed.injuries} == {"Injured Reserve", "Day-To-Day", "Out"}
    row = parsed.injuries[0]
    assert (row.espn_team_id, row.team_code, row.espn_athlete_id) == ("25", "ANA", "5080154")
    assert row.player_name == "Pavel Mintyukov"
    assert row.source_updated_at == datetime(2026, 10, 23, 21, 8, tzinfo=timezone.utc)
    assert not row.team_mismatch


def test_detail_and_return_date_are_source_context() -> None:
    payload = feed()
    entries(payload)[0].update(details={
        "side": "Left", "type": "Knee", "detail": "Not Specified", "returnDate": "2026-11-01",
    }, shortComment="Fixture comment.")
    row = parse_injury_feed(payload).injuries[0]
    assert row.detail == "Left Knee. Fixture comment."
    assert row.return_date == "2026-11-01"


@pytest.mark.parametrize("explicit_null", [False, True])
def test_optional_fields_do_not_invent_times_or_status(explicit_null: bool) -> None:
    payload = feed()
    for field in ("date", "details", "shortComment"):
        if explicit_null:
            entries(payload)[0][field] = None
        else:
            entries(payload)[0].pop(field, None)
    athlete(payload).pop("team")
    entries(payload)[0]["status"] = "New source label"
    row = parse_injury_feed(payload).injuries[0]
    assert (row.detail, row.return_date, row.source_updated_at, row.athlete_team_id) == (None,) * 4
    assert row.status == "New source label"


def test_empty_success_is_distinct_from_error_or_missing_collection() -> None:
    payload = feed()
    payload["injuries"] = []
    assert parse_injury_feed(payload).injuries == ()
    payload["injuries"] = [{"id": "25", "injuries": []}]
    assert parse_injury_feed(payload).injuries == ()


@pytest.mark.parametrize("payload", [None, [], {}, {"status": "success"}, {1: "bad key"}])
def test_incomplete_feed_fails(payload: object) -> None:
    with pytest.raises(ValueError):
        parse_injury_feed(payload)


@pytest.mark.parametrize(("field", "value"), [
    ("status", "error"), ("status", None), ("injuries", None), ("injuries", {}),
    ("timestamp", None), ("timestamp", ""), ("timestamp", "2026-10-24T16:18:22"),
    ("timestamp", "bad"), ("timestamp", 123),
])
def test_invalid_root_cannot_clear_previous_report(field: str, value: object) -> None:
    payload = feed()
    payload[field] = value
    with pytest.raises(ValueError):
        parse_injury_feed(payload)


@pytest.mark.parametrize(("field", "value"), [
    ("id", "999"), ("id", True), ("id", "0"), ("id", ""),
    ("injuries", None), ("injuries", {}),
])
def test_invalid_group_rejects_batch(field: str, value: object) -> None:
    payload = feed()
    groups(payload)[0][field] = value
    with pytest.raises(ValueError):
        parse_injury_feed(payload)


@pytest.mark.parametrize(("field", "value"), [
    ("status", ""), ("status", None), ("status", 3), ("date", "yesterday"),
    ("date", "2026-10-24"), ("details", []), ("shortComment", []), ("athlete", None),
])
def test_invalid_entry_rejects_whole_batch(field: str, value: object) -> None:
    payload = feed()
    entries(payload)[0][field] = value
    with pytest.raises(ValueError):
        parse_injury_feed(payload)


@pytest.mark.parametrize("href", [
    "https://evil.test/nhl/player/_/id/5080154",
    "https://www.espn.com.evil.test/nhl/player/_/id/5080154",
    "https://www.espn.com/nba/player/_/id/5080154",
    "https://www.espn.com/nhl/player/_/id/0",
    "https://www.espn.com/nhl/player/_/id/5080154bad",
    "sportscenter://nhl/player/_/id/5080154", "",
])
def test_untrusted_or_wrong_sport_links_do_not_resolve_athlete(href: str) -> None:
    payload = feed()
    athlete(payload)["links"] = [{"href": href}]
    with pytest.raises(ValueError, match="unambiguous"):
        parse_injury_feed(payload)


def test_explicit_id_and_consistent_links_must_agree() -> None:
    payload = feed()
    athlete(payload)["id"] = 5080154
    assert parse_injury_feed(payload).injuries[0].espn_athlete_id == "5080154"
    athlete(payload)["id"] = "1111"
    with pytest.raises(ValueError, match="unambiguous"):
        parse_injury_feed(payload)


@pytest.mark.parametrize("value", [True, 0, -1, "1.5", "", " 123 "])
def test_invalid_explicit_athlete_id_rejects_batch(value: object) -> None:
    payload = feed()
    athlete(payload)["id"] = value
    with pytest.raises(ValueError):
        parse_injury_feed(payload)


def test_duplicate_entries_and_groups_deduplicate_but_conflicts_fail() -> None:
    payload = feed()
    expected = parse_injury_feed(payload)
    entries(payload).append(deepcopy(entries(payload)[0]))
    groups(payload).append(deepcopy(groups(payload)[0]))
    assert parse_injury_feed(payload) == expected
    entries(payload)[1]["status"] = "Contradictory status"
    with pytest.raises(ValueError, match="conflicting duplicate"):
        parse_injury_feed(payload)


def test_nested_team_disagreement_is_retained_under_reporting_team() -> None:
    payload = feed()
    athlete(payload)["team"] = {"id": "20", "abbreviation": "TB"}
    row = parse_injury_feed(payload).injuries[0]
    assert (row.team_code, row.athlete_team_id, row.team_mismatch) == ("ANA", "20", True)


@pytest.mark.parametrize("team", [
    {"id": "20", "abbreviation": "ANA"}, {"id": "999"}, {"id": True},
    {"id": "25", "abbreviation": None}, [],
])
def test_unknown_or_internally_inconsistent_nested_team_fails(team: object) -> None:
    payload = feed()
    athlete(payload)["team"] = team
    with pytest.raises(ValueError):
        parse_injury_feed(payload)


def test_id_only_nested_team_and_offset_timestamp_are_supported() -> None:
    payload = feed()
    athlete(payload)["team"] = {"id": "25"}
    entries(payload)[0]["date"] = "2026-10-23T16:08:00-05:00"
    assert parse_injury_feed(payload).injuries[0].source_updated_at == datetime(
        2026, 10, 23, 21, 8, tzinfo=timezone.utc,
    )

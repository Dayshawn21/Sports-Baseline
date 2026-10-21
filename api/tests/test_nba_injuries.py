from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

import pytest

from app.core.nba_injuries import ESPN_NBA_TEAMS, parse_injury_feed
from app.core.nba_season import NBA_TEAM_CODES


def feed() -> dict[str, object]:
    path = Path(__file__).parent / "fixtures" / "espn_nba_injuries.json"
    return cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))


def groups(payload: dict[str, object]) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], payload["injuries"])


def entry(payload: dict[str, object]) -> dict[str, object]:
    return cast(list[dict[str, object]], groups(payload)[0]["injuries"])[0]


def athlete(payload: dict[str, object]) -> dict[str, object]:
    return cast(dict[str, object], entry(payload)["athlete"])


def test_verified_feed_fields_and_team_identity() -> None:
    result = parse_injury_feed(feed())
    out, day_to_day, mismatch = result.injuries
    assert result.source_timestamp == datetime(2026, 10, 21, 17, 52, 32, tzinfo=timezone.utc)
    assert (out.espn_team_id, out.team_code, out.espn_athlete_id) == ("1", "ATL", "4712863")
    assert out.player_name == "Mouhamed Gueye"
    assert out.status == "Out"
    assert out.source_updated_at == datetime(2026, 10, 19, 19, 38, tzinfo=timezone.utc)
    assert out.return_date == "2026-11-20"
    assert out.detail == "Left Foot Fracture. Edited fixture comment."
    assert not out.team_mismatch
    assert day_to_day.status == "Day-To-Day"
    assert day_to_day.team_code == "CHI"
    assert (mismatch.team_code, mismatch.athlete_team_id, mismatch.team_mismatch) == ("LAC", "28", True)
    assert set(ESPN_NBA_TEAMS.values()) == NBA_TEAM_CODES
    assert len(ESPN_NBA_TEAMS) == 30


def test_missing_optional_data_is_null_and_unknown_status_is_preserved() -> None:
    payload = feed()
    row = entry(payload)
    for key in ("date", "details", "shortComment"):
        row.pop(key)
    athlete(payload).pop("team")
    row["status"] = "Questionable"
    parsed = parse_injury_feed(payload).injuries[0]
    assert parsed.status == "Questionable"
    assert parsed.detail is None
    assert parsed.source_updated_at is None
    assert parsed.return_date is None
    assert parsed.athlete_team_id is None


def test_explicit_null_optional_data_and_blank_text() -> None:
    payload = feed()
    row = entry(payload)
    row.update(date=None, details=None, shortComment="  ")
    parsed = parse_injury_feed(payload).injuries[0]
    assert parsed.detail is None
    assert parsed.source_updated_at is None


def test_successful_empty_feed_and_empty_team_are_distinct_from_malformed() -> None:
    payload = feed()
    payload["injuries"] = []
    assert parse_injury_feed(payload).injuries == ()
    payload["injuries"] = [{"id": "1", "injuries": []}]
    assert parse_injury_feed(payload).injuries == ()


@pytest.mark.parametrize("payload", [None, [], {}, {"status": "success"}])
def test_incomplete_feed_cannot_clear_reports(payload: object) -> None:
    with pytest.raises(ValueError):
        parse_injury_feed(payload)


@pytest.mark.parametrize(("field", "value"), [
    ("status", "error"), ("status", None), ("injuries", None), ("injuries", {}),
    ("timestamp", None), ("timestamp", ""), ("timestamp", "2026-10-21T17:52:32"),
    ("timestamp", "bad"), ("timestamp", 123),
])
def test_invalid_root_fields(field: str, value: object) -> None:
    payload = feed()
    payload[field] = value
    with pytest.raises(ValueError):
        parse_injury_feed(payload)


@pytest.mark.parametrize(("field", "value"), [
    ("id", "99"), ("id", True), ("id", ""), ("injuries", None), ("injuries", {}),
])
def test_invalid_team_group(field: str, value: object) -> None:
    payload = feed()
    groups(payload)[0][field] = value
    with pytest.raises(ValueError):
        parse_injury_feed(payload)


@pytest.mark.parametrize(("field", "value"), [
    ("status", ""), ("status", None), ("status", 3), ("date", "yesterday"),
    ("date", "2026-10-21"), ("details", []), ("details", ""), ("athlete", None),
    ("shortComment", []),
])
def test_invalid_entry_fails_entire_batch(field: str, value: object) -> None:
    payload = feed()
    entry(payload)[field] = value
    with pytest.raises(ValueError):
        parse_injury_feed(payload)


@pytest.mark.parametrize("href", [
    "https://evil.test/nba/player/_/id/4712863/name",
    "https://www.espn.com.evil.test/nba/player/_/id/4712863/name",
    "https://www.espn.com/nfl/player/_/id/4712863/name",
    "https://www.espn.com/nba/player/_/id/0/name",
    "https://www.espn.com/nba/player/_/id/4712863bad/name",
    "sportscenter://nba/player/_/id/4712863/name", "",
])
def test_invalid_athlete_link_is_not_a_name_match(href: str) -> None:
    payload = feed()
    athlete(payload)["links"] = [{"href": href}]
    with pytest.raises(ValueError, match="unambiguous"):
        parse_injury_feed(payload)


def test_explicit_athlete_id_and_multiple_consistent_links() -> None:
    payload = feed()
    player = athlete(payload)
    player["id"] = 4712863
    player["links"] = [
        {"href": "https://www.espn.com/nba/player/stats/_/id/4712863/name"},
        {"href": "https://www.espn.com/nba/player/gamelog/_/id/4712863/name"},
    ]
    assert parse_injury_feed(payload).injuries[0].espn_athlete_id == "4712863"
    player.pop("links")
    assert parse_injury_feed(payload).injuries[0].espn_athlete_id == "4712863"


@pytest.mark.parametrize("value", [True, -1, "", "bad", "123"])
def test_bad_or_conflicting_explicit_athlete_id(value: object) -> None:
    payload = feed()
    athlete(payload)["id"] = value
    with pytest.raises(ValueError):
        parse_injury_feed(payload)


def test_conflicting_athlete_links_fail_the_batch() -> None:
    payload = feed()
    athlete(payload)["links"] = [
        {"href": "https://www.espn.com/nba/player/_/id/4712863/name"},
        {"href": "https://www.espn.com/nba/player/_/id/123/other"},
    ]
    with pytest.raises(ValueError, match="unambiguous"):
        parse_injury_feed(payload)


def test_identical_duplicate_collapses_but_conflicting_duplicate_fails() -> None:
    payload = feed()
    rows = cast(list[dict[str, object]], groups(payload)[0]["injuries"])
    duplicate = copy.deepcopy(rows[0])
    rows.append(duplicate)
    assert len(parse_injury_feed(payload).injuries) == 3
    duplicate["status"] = "Day-To-Day"
    with pytest.raises(ValueError, match="conflicting duplicate"):
        parse_injury_feed(payload)


def test_repeated_team_group_is_not_silently_merged() -> None:
    payload = feed()
    groups(payload).append(copy.deepcopy(groups(payload)[0]))
    with pytest.raises(ValueError, match="repeated"):
        parse_injury_feed(payload)


@pytest.mark.parametrize("team", [{"id": "1", "abbreviation": "TOR"}, {"id": "99", "abbreviation": "ATL"}])
def test_conflicting_or_unknown_athlete_team_mapping(team: dict[str, str]) -> None:
    payload = feed()
    athlete(payload)["team"] = team
    with pytest.raises(ValueError, match="verified NBA team"):
        parse_injury_feed(payload)

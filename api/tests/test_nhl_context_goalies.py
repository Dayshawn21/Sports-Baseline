from __future__ import annotations

import json
from copy import deepcopy
from datetime import date, datetime, timezone
from pathlib import Path
from typing import cast

import pytest

from app.core.nhl_context import parse_goalie_feed

DAY = date(2026, 10, 24)


def feed() -> dict[str, object]:
    path = Path(__file__).parent / "fixtures" / "espn_nhl_goalies.json"
    return json.loads(path.read_text(encoding="utf-8"))


def events(payload: dict[str, object]) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], payload["events"])


def competition(payload: dict[str, object]) -> dict[str, object]:
    return cast(list[dict[str, object]], events(payload)[0]["competitions"])[0]


def sides(payload: dict[str, object]) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], competition(payload)["competitors"])


def probable(payload: dict[str, object]) -> dict[str, object]:
    return cast(list[dict[str, object]], sides(payload)[0]["probables"])[0]


def test_live_fixture_preserves_event_team_and_goalie_identity() -> None:
    parsed = parse_goalie_feed(feed(), DAY)
    assert parsed.scope_date == DAY
    assert parsed.source_timestamp is None
    assert len(parsed.observations) == 4
    home, away, second_home, second_away = parsed.observations
    assert (home.espn_event_id, home.team_code, home.home_team, home.away_team) == (
        "401892566", "PHI", "PHI", "ANA",
    )
    assert (home.espn_athlete_id, home.player_name, home.status, home.raw_status) == (
        "4271575", "Joseph Woll", "confirmed", "Confirmed",
    )
    assert home.start_utc == datetime(2026, 10, 24, 17, tzinfo=timezone.utc)
    assert home.time_valid and not home.team_mismatch
    assert away.status == "expected"
    assert (second_home.team_code, second_away.team_code) == ("NJD", "LAK")


@pytest.mark.parametrize("remove", [False, True])
def test_absent_probables_create_explicit_not_reported_competitor(remove: bool) -> None:
    payload = feed()
    if remove:
        sides(payload)[0].pop("probables")
    else:
        sides(payload)[0]["probables"] = []
    row = parse_goalie_feed(payload, DAY).observations[0]
    assert row.status == "not_reported"
    assert (row.espn_athlete_id, row.player_name, row.raw_status, row.source_position) == (None,) * 4
    assert row.team_code == "PHI"


def test_unrelated_probables_are_not_starting_goalies() -> None:
    payload = feed()
    sides(payload)[0]["probables"] = [{"name": "anotherRole"}]
    assert parse_goalie_feed(payload, DAY).observations[0].status == "not_reported"


@pytest.mark.parametrize(("name", "kind"), [
    ("Projected", "projected"), ("Confirmed", "expected"),
    ("Expected", "confirmed"), ("confirmed", "confirmed"), ("Confirmed", "newType"),
])
def test_unknown_or_conflicting_status_never_promotes_confirmation(name: str, kind: str) -> None:
    payload = feed()
    probable(payload)["status"] = {"name": name, "type": kind}
    row = parse_goalie_feed(payload, DAY).observations[0]
    assert (row.status, row.raw_status) == ("unknown", name)


def test_status_name_without_optional_type_is_preserved() -> None:
    payload = feed()
    probable(payload)["status"] = {"name": "Confirmed"}
    assert parse_goalie_feed(payload, DAY).observations[0].status == "confirmed"


def test_explicit_empty_response_and_missing_events_are_distinct() -> None:
    payload = feed()
    payload["events"] = []
    assert parse_goalie_feed(payload, DAY).observations == ()
    payload.pop("events")
    with pytest.raises(ValueError):
        parse_goalie_feed(payload, DAY)


@pytest.mark.parametrize("payload", [None, [], {}, {"events": []}, {"leagues": [], "events": []}])
def test_malformed_roots_cannot_be_success_markers(payload: object) -> None:
    with pytest.raises(ValueError):
        parse_goalie_feed(payload, DAY)


@pytest.mark.parametrize("league", [
    {"id": "90", "slug": "nba"}, {"id": "46", "slug": "nhl"},
    {"id": True, "slug": "nhl"}, {},
])
def test_wrong_or_incomplete_league_is_rejected(league: object) -> None:
    payload = feed()
    payload["leagues"] = [league]
    with pytest.raises(ValueError):
        parse_goalie_feed(payload, DAY)


def test_wrong_date_and_request_limit_cannot_silently_shrink_coverage() -> None:
    with pytest.raises(ValueError, match="requested Eastern date"):
        parse_goalie_feed(feed(), date(2026, 10, 25))
    with pytest.raises(ValueError, match="truncated"):
        parse_goalie_feed(feed(), DAY, request_limit=2)


@pytest.mark.parametrize("limit", [True, 0, -1, 1.5])
def test_invalid_request_limit_fails(limit: int) -> None:
    with pytest.raises(ValueError):
        parse_goalie_feed(feed(), DAY, request_limit=limit)


@pytest.mark.parametrize("value", [None, "", "bad", "2026-10-24T17:00", 123])
def test_malformed_source_start_fails(value: object) -> None:
    payload = feed()
    events(payload)[0]["date"] = value
    with pytest.raises(ValueError):
        parse_goalie_feed(payload, DAY)


@pytest.mark.parametrize("field,value", [
    ("id", "111"), ("date", "2026-10-24T18:00Z"), ("timeValid", None),
    ("timeValid", 1), ("competitors", []), ("competitors", None),
])
def test_inconsistent_or_partial_competition_fails(field: str, value: object) -> None:
    payload = feed()
    competition(payload)[field] = value
    with pytest.raises(ValueError):
        parse_goalie_feed(payload, DAY)


@pytest.mark.parametrize("field,value", [
    ("id", "999"), ("homeAway", "neutral"), ("team", {"id": "999"}),
    ("team", {"id": "15", "abbreviation": "ANA"}), ("probables", None),
])
def test_bad_competitor_fails_whole_date(field: str, value: object) -> None:
    payload = feed()
    sides(payload)[0][field] = value
    with pytest.raises(ValueError):
        parse_goalie_feed(payload, DAY)


def test_repeated_side_or_same_team_on_both_sides_fails() -> None:
    payload = feed()
    sides(payload)[1]["homeAway"] = "home"
    with pytest.raises(ValueError):
        parse_goalie_feed(payload, DAY)
    sides(payload)[1].update(homeAway="away", id=15, team={"id": "15", "abbreviation": "PHI"})
    with pytest.raises(ValueError, match="same team"):
        parse_goalie_feed(payload, DAY)


@pytest.mark.parametrize("field,value", [
    ("playerId", 123), ("athlete", None), ("status", "Confirmed"),
    ("status", {"name": ""}), ("status", {"name": "Confirmed", "type": []}),
])
def test_bad_goalie_identity_or_status_fails(field: str, value: object) -> None:
    payload = feed()
    probable(payload)[field] = value
    with pytest.raises(ValueError):
        parse_goalie_feed(payload, DAY)


def test_nested_team_disagreement_and_position_are_retained() -> None:
    payload = feed()
    player = cast(dict[str, object], probable(payload)["athlete"])
    player.update(team={"id": "25"}, position="C")
    row = parse_goalie_feed(payload, DAY).observations[0]
    assert (row.team_code, row.athlete_team_id, row.source_position, row.team_mismatch) == (
        "PHI", "25", "C", True,
    )


def test_invalid_time_flag_preserves_schedule_without_claiming_known_start() -> None:
    payload = feed()
    competition(payload)["timeValid"] = False
    row = parse_goalie_feed(payload, DAY).observations[0]
    assert not row.time_valid
    assert row.start_utc == datetime(2026, 10, 24, 17, tzinfo=timezone.utc)


def test_identical_goalies_and_events_deduplicate_but_conflicts_fail() -> None:
    payload = feed()
    expected = parse_goalie_feed(payload, DAY)
    cast(list[object], sides(payload)[0]["probables"]).append(deepcopy(probable(payload)))
    events(payload).append(deepcopy(events(payload)[0]))
    assert parse_goalie_feed(payload, DAY) == expected
    duplicate = cast(list[dict[str, object]], sides(payload)[0]["probables"])[1]
    duplicate["status"] = {"name": "Expected", "type": "expected"}
    with pytest.raises(ValueError, match="conflicting duplicate starting goalie"):
        parse_goalie_feed(payload, DAY)


def test_conflicting_duplicate_event_does_not_replace_earlier_observation() -> None:
    payload = feed()
    duplicate = deepcopy(payload)
    sides(duplicate)[0]["probables"] = []
    events(payload).append(events(duplicate)[0])
    with pytest.raises(ValueError, match="conflicting duplicate scoreboard event"):
        parse_goalie_feed(payload, DAY)


@pytest.mark.parametrize("kind", [True, 2.0, 0, 4, "2", None])
def test_unknown_or_malformed_season_type_fails(kind: object) -> None:
    payload = feed()
    events(payload)[0]["season"] = {"type": kind}
    with pytest.raises(ValueError):
        parse_goalie_feed(payload, DAY)


def test_preseason_is_excluded_but_playoffs_are_eligible() -> None:
    payload = feed()
    events(payload)[0]["season"] = {"type": 1}
    assert len(parse_goalie_feed(payload, DAY).observations) == 2
    events(payload)[0]["season"] = {"type": 3}
    assert len(parse_goalie_feed(payload, DAY).observations) == 4


def test_utc_next_day_is_same_eastern_scope_and_does_not_mutate_input() -> None:
    payload = feed()
    original = deepcopy(payload)
    events(payload)[0]["date"] = "2026-10-25T01:00Z"
    competition(payload)["date"] = "2026-10-25T01:00Z"
    payload["timestamp"] = "2026-10-24T12:00:00-05:00"
    expected = deepcopy(payload)
    parsed = parse_goalie_feed(payload, DAY)
    assert parsed.observations[0].event_date == DAY
    assert parsed.source_timestamp == datetime(2026, 10, 24, 17, tzinfo=timezone.utc)
    assert payload == expected and original != payload

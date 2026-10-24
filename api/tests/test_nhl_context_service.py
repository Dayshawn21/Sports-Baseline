from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from typing import cast
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nhl_context import NhlGoalieObservation, NhlInjuryEntry
from app.core.nhl_context_resolution import EventLink, PlayerLink
from app.core.nhl_context_snapshots import GoalieSnapshot, InjurySnapshot, StoredGoalie, StoredInjury, context_freshness
from app.repositories import nhl, nhl_context as repo
from app.schemas.nhl import NhlSlateGameSchema
from app.services.nhl.context import goalie_context, injury_context, load_contexts
from app.services.nhl.game_detail import build_game_detail
from app.services.nhl.slate import build_slate, slate_games

START = datetime(2026, 10, 24, 20, tzinfo=timezone.utc)
NOW, FETCH = START - timedelta(hours=1), START - timedelta(hours=2)
DAY = date(2026, 10, 24)
DB = cast(AsyncSession, object())


def game(**changes: object) -> NhlSlateGameSchema:
    row = {"game_id": 1, "season": 2026, "week": 3, "game_type": "REG", "game_date": DAY,
           "start_utc": START, "status": "scheduled", "away_team": "TBL", "home_team": "CHI",
           "away_team_name": "Tampa Bay", "home_team_name": "Chicago", "away_score": None,
           "home_score": None, "end_period": None, **changes}
    return slate_games([row], [], [], {})[0]


def injuries(fetched: datetime = FETCH) -> InjurySnapshot:
    entry = NhlInjuryEntry("20", "TBL", "123", "Unresolved source name", "Out", "Ankle", FETCH, None, "4")
    return InjurySnapshot(fetched, fetched, (StoredInjury(entry, PlayerLink(None, "team_mismatch")),))


def goalies(fetched: datetime = FETCH) -> GoalieSnapshot:
    rows = []
    for team_id, code in [("20", "TBL"), ("4", "CHI")]:
        observation = NhlGoalieObservation("555", DAY, START, True, "CHI", "TBL", team_id, code,
                                           team_id + "123", code + " source name", "confirmed", "Confirmed", team_id, "G")
        rows.append(StoredGoalie(observation, PlayerLink(None, "no_candidate"), EventLink(1, "matched")))
    return GoalieSnapshot(fetched, None, tuple(rows))


@pytest.mark.parametrize("fetched,start,as_of,expected", [
    (FETCH, START, NOW, "fresh"), (NOW - timedelta(hours=6), START, NOW, "fresh"),
    (NOW - timedelta(hours=6, microseconds=1), START, NOW, "stale"),
    (NOW, START, NOW, "fresh"), (NOW + timedelta(microseconds=1), START, NOW, "unavailable"),
    (START, START, START, "unavailable"), (START + timedelta(seconds=1), START, START, "unavailable"),
    (None, START, NOW, "unavailable"), (FETCH, None, NOW, "unavailable"),
    (FETCH, START, NOW + timedelta(days=100), "fresh"),
    (START - timedelta(hours=6), START, START + timedelta(days=100), "fresh"),
    (START - timedelta(hours=6, microseconds=1), START, START + timedelta(days=100), "stale"),
])
def test_freshness_has_strict_pre_game_and_six_hour_boundaries(
    fetched: datetime | None, start: datetime | None, as_of: datetime, expected: str,
) -> None:
    assert context_freshness(fetched, start, as_of) == expected


@pytest.mark.parametrize("field", ["fetched", "start", "as_of"])
def test_naive_clocks_are_not_accepted(field: str) -> None:
    values = {"fetched": FETCH, "start": START, "as_of": NOW}
    values[field] = values[field].replace(tzinfo=None)
    with pytest.raises(ValueError, match="timezone-aware"):
        context_freshness(**values)


def test_injury_unresolved_name_stays_on_source_team_without_inventing_player_link() -> None:
    report = injury_context(game(), injuries(), NOW)
    assert len(report.away) == 1 and report.home == []
    assert report.away[0].player_id is None and report.away[0].team_mismatch
    assert report.away[0].team == "TBL" and report.away[0].status == "Out"
    assert report.source_timestamp == FETCH and report.away[0].source_updated_at == FETCH


def test_empty_report_stale_report_and_no_report_have_distinct_metadata() -> None:
    empty = injury_context(game(), replace(injuries(), injuries=()), NOW)
    assert empty.away == empty.home == [] and empty.freshness == "fresh" and empty.fetched_at == FETCH
    assert injury_context(game(), injuries(NOW - timedelta(hours=7)), NOW).freshness == "stale"
    assert injury_context(game(), None, NOW).fetched_at is None
    assert injury_context(game(start_utc=None), injuries(), NOW).fetched_at is None


def test_unrelated_injuries_are_ignored_and_frozen_internal_links_survive() -> None:
    snapshot = injuries()
    stored = snapshot.injuries[0]
    valid = replace(stored, entry=replace(stored.entry, athlete_team_id="20"), player=PlayerLink(777, "matched"))
    unrelated = replace(stored, entry=replace(stored.entry, team_code="BOS", espn_athlete_id="999"))
    report = injury_context(game(), replace(snapshot, injuries=(valid, unrelated)), NOW)
    assert len(report.away) == 1 and report.away[0].player_id == 777


def test_goalie_names_and_unknown_status_survive_null_internal_player_ids() -> None:
    snapshot = goalies()
    first, second = snapshot.observations
    first = replace(first, observation=replace(first.observation, status="unknown", raw_status="Projected"))
    report = goalie_context(game(), replace(snapshot, observations=(first, second)), NOW)
    assert report.away.status == "unknown" and report.away.raw_status == "Projected"
    assert report.away.player_name == "TBL source name" and report.away.player_id is None
    assert report.home.status == "confirmed" and report.freshness == "fresh"


def test_missing_event_is_unavailable_with_batch_time_and_no_prior_starter() -> None:
    report = goalie_context(game(), replace(goalies(), observations=()), NOW)
    assert report.freshness == "unavailable" and report.fetched_at == FETCH
    assert report.away.status == report.home.status == "unavailable"
    assert report.away.player_name is None
    assert goalie_context(game(), None, NOW).fetched_at is None


def test_not_reported_is_distinct_from_unavailable_and_stale_report_remains_visible() -> None:
    snapshot = goalies(NOW - timedelta(hours=7))
    first, second = snapshot.observations
    first = replace(first, observation=replace(first.observation, espn_athlete_id=None, player_name=None,
                    raw_status=None, status="not_reported", athlete_team_id=None, source_position=None),
                    player=PlayerLink(None, "not_reported"))
    report = goalie_context(game(), replace(snapshot, observations=(first, second)), NOW)
    assert report.away.status == "not_reported" and report.home.status == "confirmed"
    assert report.freshness == "stale" and report.fetched_at == snapshot.fetched_at


@pytest.mark.parametrize("changed", [
    {"start_utc": START + timedelta(minutes=61)}, {"start_utc": None},
    {"game_date": DAY + timedelta(days=1)}, {"away_team": "BOS"},
])
def test_rescheduled_tbd_changed_date_or_teams_never_reuse_invalid_event(changed: dict[str, object]) -> None:
    report = goalie_context(game(**changed), goalies(), NOW)
    assert report.freshness == "unavailable" and report.away.player_name is None
    assert report.fetched_at == (None if changed.get("start_utc", START) is None else FETCH)


@pytest.mark.parametrize("minutes", [-60, 60])
def test_reschedule_within_declared_tolerance_still_matches(minutes: int) -> None:
    report = goalie_context(game(start_utc=START + timedelta(minutes=minutes)), goalies(), FETCH)
    assert report.away.status == "confirmed"


def test_duplicate_source_events_partial_pairs_and_invalid_time_are_not_guessed() -> None:
    snapshot = goalies()
    first, second = snapshot.observations
    cases = [(first,), (first, first), (first, replace(second, observation=replace(second.observation, time_valid=False))),
             (first, replace(second, observation=replace(second.observation, espn_event_id="556"))),
             (*snapshot.observations, *snapshot.observations)]
    for rows in cases:
        report = goalie_context(game(), replace(snapshot, observations=rows), NOW)
        assert report.freshness == "unavailable" and report.fetched_at == FETCH


def test_completed_game_keeps_the_same_pre_start_context_as_time_passes() -> None:
    current = goalie_context(game(), goalies(), NOW)
    historical = goalie_context(game(status="completed"), goalies(), START + timedelta(days=100))
    assert historical == current


def test_batched_loader_uses_one_response_clock_and_preserves_independent_feed_times(monkeypatch: pytest.MonkeyPatch) -> None:
    injury_reader = AsyncMock(return_value={1: injuries()})
    goalie_reader = AsyncMock(return_value={1: goalies(FETCH + timedelta(minutes=30))})
    monkeypatch.setattr(repo, "get_injury_snapshots", injury_reader)
    monkeypatch.setattr(repo, "get_goalie_snapshots", goalie_reader)
    reports = asyncio.run(load_contexts(DB, [game(), game(game_id=2)], NOW))
    assert reports[1].injuries.fetched_at == FETCH
    assert reports[1].goalies.fetched_at == FETCH + timedelta(minutes=30)
    assert reports[2].injuries.freshness == "unavailable"
    injury_reader.assert_awaited_once_with(DB, [1, 2], NOW)
    goalie_reader.assert_awaited_once_with(DB, [1, 2], NOW)
    assert asyncio.run(load_contexts(DB, [], NOW)) == {}
    assert injury_reader.await_count == goalie_reader.await_count == 1


@pytest.mark.parametrize("state", ["42P01", "42501"])
def test_missing_migration_is_explicit_503_and_other_database_errors_are_not_hidden(
    state: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DatabaseError(Exception):
        sqlstate = state

    error = ProgrammingError("private SQL", {}, DatabaseError("private connection"))
    monkeypatch.setattr(repo, "get_injury_snapshots", AsyncMock(side_effect=error))
    with pytest.raises(HTTPException if state == "42P01" else ProgrammingError) as exc:
        asyncio.run(load_contexts(DB, [game()], NOW))
    if state == "42P01":
        assert exc.value.status_code == 503 and "0050" in exc.value.detail
        assert "private" not in exc.value.detail


def test_slate_and_detail_share_context_with_identical_fixed_clock_and_existing_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    row = game().model_dump(exclude={"context", "moneyline", "spread", "total", "line_movement", "prop_line_count"})
    for name, value in {"get_game_dates": [DAY], "get_games_on": [row], "get_game": row,
                        "get_latest_market_rows": [], "get_line_movement": [], "get_prop_line_counts": {1: 7},
                        "get_game_line_history": []}.items():
        monkeypatch.setattr(nhl, name, AsyncMock(return_value=value))
    monkeypatch.setattr(repo, "get_injury_snapshots", AsyncMock(return_value={1: injuries()}))
    monkeypatch.setattr(repo, "get_goalie_snapshots", AsyncMock(return_value={1: goalies()}))
    slate = asyncio.run(build_slate(DB, DAY, DAY, as_of=NOW))
    detail = asyncio.run(build_game_detail(DB, 1, as_of=NOW))
    assert detail is not None and slate.games[0].model_dump() == detail.model_dump(exclude={"line_history"})
    assert detail.prop_line_count == 7 and detail.context.goalies.away.status == "confirmed"
    wire = detail.model_dump(mode="json", by_alias=True)
    assert wire["context"]["injuries"]["away"][0]["teamMismatch"] is True
    assert wire["context"]["goalies"]["fetchedAt"] == "2026-10-24T18:00:00Z"

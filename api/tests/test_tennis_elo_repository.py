import asyncio
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from typing import cast

import pytest
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import TextClause

from app.core.tennis_elo import TennisEloRating
from app.repositories.tennis_elo import (
    SOURCE, TennisEloSnapshot, get_daily_snapshots, insert_daily_snapshots,
)

DAY = date(2026, 10, 20)
NOW = datetime(2026, 10, 20, 11, tzinfo=timezone.utc)


def snapshot(player_id: int = 1) -> TennisEloSnapshot:
    return TennisEloSnapshot(
        player_id=player_id, source=SOURCE, as_of_date=DAY,
        rating=TennisEloRating(1565.0, 1565.0, None, None, 1, 1, 0, 0),
        provider_namespace="ATP", provider_player_id=f"A{player_id}",
        computed_at=NOW, source_downloaded_at=NOW - timedelta(minutes=5),
        replay_cutoff=DAY, method_version=SOURCE, manifest_sha256="a" * 64,
    )


def stored_row(value: TennisEloSnapshot) -> RowMapping:
    return cast(RowMapping, {
        "player_id": value.player_id, "source": value.source, "as_of_date": value.as_of_date,
        "overall": value.rating.overall, "hard": value.rating.hard, "clay": value.rating.clay,
        "grass": value.rating.grass, "overall_matches": value.rating.overall_matches,
        "hard_matches": value.rating.hard_matches, "clay_matches": value.rating.clay_matches,
        "grass_matches": value.rating.grass_matches, "provider_namespace": value.provider_namespace,
        "provider_player_id": value.provider_player_id, "computed_at": value.computed_at,
        "source_downloaded_at": value.source_downloaded_at, "replay_cutoff": value.replay_cutoff,
        "method_version": value.method_version, "manifest_sha256": value.manifest_sha256,
    })


class Rows:
    def __init__(self, values: list[RowMapping]) -> None:
        self.values = values

    def mappings(self) -> "Rows":
        return self

    def all(self) -> list[RowMapping]:
        return self.values


class Savepoint:
    def __init__(self) -> None:
        self.failed = False

    async def __aenter__(self) -> "Savepoint":
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        self.failed = exc_type is not None


class Session:
    def __init__(self, stored: list[TennisEloSnapshot] = (), fail_insert: bool = False) -> None:
        self.rows = [stored_row(s) for s in stored]
        self.calls: list[tuple[str, dict[str, object] | list[dict[str, object]]]] = []
        self.savepoint = Savepoint()
        self.fail_insert = fail_insert

    def begin_nested(self) -> Savepoint:
        return self.savepoint

    async def execute(self, query: TextClause, params: dict[str, object] | list[dict[str, object]]) -> Rows:
        sql = " ".join(str(query).split())
        self.calls.append((sql, params))
        if self.fail_insert and sql.startswith("INSERT"):
            raise RuntimeError("batch insert failed")
        return Rows(self.rows)


def insert(session: Session, values: list[TennisEloSnapshot]) -> int:
    return asyncio.run(insert_daily_snapshots(cast(AsyncSession, session), values))


def test_batch_is_locked_then_checked_then_inserted_once_with_native_values():
    session = Session()
    assert insert(session, [snapshot(1), snapshot(2)]) == 2
    assert len(session.calls) == 3
    lock, read, write = session.calls
    assert lock[0] == "SELECT pg_advisory_xact_lock(:lock_id)"
    assert "WHERE source = :source AND as_of_date = :as_of_date" in read[0]
    assert read[1] == {"source": SOURCE, "as_of_date": DAY}
    assert write[0].startswith("INSERT INTO tennis_elo_snapshots")
    assert "UPDATE" not in write[0] and "player_elo" not in write[0]
    assert write[1] == [stored_row(snapshot(1)), stored_row(snapshot(2))]
    assert session.savepoint.failed is False


def test_identical_retry_in_any_roster_order_does_not_write():
    session = Session([snapshot(1), snapshot(2)])
    assert insert(session, [snapshot(2), snapshot(1)]) == 0
    assert len(session.calls) == 2


@pytest.mark.parametrize("changes", [
    {"manifest_sha256": "b" * 64}, {"computed_at": NOW + timedelta(minutes=1)},
    {"rating": TennisEloRating(1600.0, 1565.0, None, None, 1, 1, 0, 0)},
    {"provider_player_id": "B1"},
])
def test_changed_facts_or_provenance_fail_before_any_write(changes):
    session = Session([snapshot()])
    with pytest.raises(ValueError, match="already frozen"):
        insert(session, [replace(snapshot(), **changes)])
    assert len(session.calls) == 2 and session.savepoint.failed


@pytest.mark.parametrize("stored, incoming", [([1], [1, 2]), ([1, 2], [1])])
def test_a_frozen_daily_roster_cannot_be_extended_or_partially_replaced(stored, incoming):
    session = Session([snapshot(i) for i in stored])
    with pytest.raises(ValueError, match="already frozen"):
        insert(session, [snapshot(i) for i in incoming])
    assert len(session.calls) == 2


@pytest.mark.parametrize("other", [
    snapshot(), replace(snapshot(2), provider_player_id="A1"),
    replace(snapshot(2), manifest_sha256="b" * 64),
    replace(snapshot(2), computed_at=NOW + timedelta(minutes=1)),
])
def test_invalid_batch_roster_or_mixed_provenance_never_reaches_the_database(other):
    session = Session()
    with pytest.raises(ValueError, match="one provenance"):
        insert(session, [snapshot(), other])
    assert session.calls == []


def test_insert_failure_leaves_the_savepoint_via_its_error_path():
    session = Session(fail_insert=True)
    with pytest.raises(RuntimeError, match="batch insert failed"):
        insert(session, [snapshot(1), snapshot(2)])
    assert session.savepoint.failed


def test_empty_batch_has_no_database_side_effect():
    session = Session()
    assert insert(session, []) == 0 and session.calls == []


def test_explicit_daily_read_round_trips_all_rating_and_provenance_fields():
    value = replace(snapshot(), rating=TennisEloRating(1600.0, 1580.0, 1501.0, 1490.0, 8, 4, 2, 1))
    session = Session([value])
    result = asyncio.run(get_daily_snapshots(cast(AsyncSession, session), source=SOURCE, as_of_date=DAY))
    assert result == [value]
    assert len(session.calls) == 1
    assert "FROM tennis_elo_snapshots" in session.calls[0][0]
    assert "ORDER BY player_id" in session.calls[0][0]


def test_a_legacy_or_unspecified_source_cannot_enter_the_candidate_read_path():
    session = Session()
    with pytest.raises(ValueError, match="Explicit candidate"):
        asyncio.run(get_daily_snapshots(cast(AsyncSession, session), source="tennisabstract", as_of_date=DAY))
    assert session.calls == []


@pytest.mark.parametrize("changes", [
    {"player_id": 0}, {"source": "tennisabstract"}, {"method_version": "other"},
    {"provider_namespace": "NBA"}, {"provider_player_id": "bad id"},
    {"manifest_sha256": "invalid"}, {"computed_at": NOW.replace(tzinfo=None)},
    {"source_downloaded_at": NOW.replace(tzinfo=None)},
    {"source_downloaded_at": NOW + timedelta(minutes=1)},
    {"as_of_date": DAY + timedelta(days=1)}, {"replay_cutoff": DAY - timedelta(days=1)},
])
def test_invalid_snapshot_identity_or_time_provenance_is_rejected(changes):
    with pytest.raises(ValueError):
        replace(snapshot(), **changes)


@pytest.mark.parametrize("rating", [
    TennisEloRating(float("nan"), None, None, None, 1, 0, 0, 0),
    TennisEloRating(float("inf"), None, None, None, 1, 0, 0, 0),
    TennisEloRating(1500, None, None, None, 0, 0, 0, 0),
    TennisEloRating(1500, 1500, None, None, 1, 2, 0, 0),
    TennisEloRating(1500, None, None, None, 1, 1, 0, 0),
    TennisEloRating(1500, 1500, None, None, 1, 0, 0, 0),
    TennisEloRating(1500, float("-inf"), None, None, 1, 1, 0, 0),
    TennisEloRating(1500, None, None, None, 1, -1, 0, 0),
    TennisEloRating(1500, None, None, None, 1.5, 0, 0, 0),
])
def test_missing_or_nonfinite_ratings_and_inconsistent_counts_are_rejected(rating):
    with pytest.raises(ValueError):
        replace(snapshot(), rating=rating)


def test_utc_day_is_independent_of_timestamp_display_timezone():
    offset_time = NOW.astimezone(timezone(timedelta(hours=-12)))
    assert offset_time.date() != DAY
    assert replace(snapshot(), computed_at=offset_time).as_of_date == DAY

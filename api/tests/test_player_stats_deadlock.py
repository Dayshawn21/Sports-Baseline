"""A deadlock on one player must not cost the rest of the slate, or a second fetch.

The daily run held one transaction across every player and committed every 50, so a
concurrent ingest deadlocked against it on `players` and killed the process partway
through. Each player now writes in its own short transaction, retried on 40P01.

The retry replays only the write. Re-fetching would spend another TennisAbstract
request on a source that already rate limits us, which is what these tests pin down.
"""

import asyncio

import pytest
from sqlalchemy.exc import DBAPIError, OperationalError

from app.db import retry as retry_mod
from app.ingest import player_stats


class _Orig(Exception):
    def __init__(self, sqlstate):
        self.sqlstate = sqlstate


def _db_error(sqlstate) -> DBAPIError:
    return OperationalError("stmt", {}, _Orig(sqlstate))


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _SelectionSession:
    """Stands in for the one session that picks which players to refresh."""

    def __init__(self, rows):
        self._rows = rows

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, *args, **kwargs):
        return _Result(self._rows)


class _WriteSession:
    def __init__(self, commits):
        self._commits = commits

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def commit(self):
        self._commits.append(1)


PLAYERS = [
    (1, "Player One", "ATP", None),
    (2, "Player Two", "WTA", "PlayerTwoOfficial"),
    (3, "Player Three", "ATP", None),
]


@pytest.fixture
def harness(monkeypatch):
    """Wire run() to fake sessions so only the loop's own logic is under test."""

    async def _instant(_seconds):
        return None

    monkeypatch.setattr(retry_mod.asyncio, "sleep", _instant)
    monkeypatch.setattr("app.db.pool.SessionLocal", lambda: _SelectionSession(PLAYERS))

    commits: list = []
    write_sessions: list = []

    def _write_session():
        s = _WriteSession(commits)
        write_sessions.append(s)
        return s

    monkeypatch.setattr(retry_mod, "SessionLocal", _write_session)

    async def _no_fresh(db, player_ids, skip_computed_today=False):
        return set()

    monkeypatch.setattr(player_stats, "_get_fresh_player_ids", _no_fresh)

    fetches: list = []
    fetch_details: list = []

    def _fetch(name, tour="", slug_override=None):
        fetches.append(name)
        fetch_details.append((name, tour, slug_override))
        return [["row"]]

    monkeypatch.setattr(player_stats, "_fetch_matches", _fetch)
    monkeypatch.setattr(player_stats, "_aggregate", lambda *a, **k: {"win_rate": 1.0})

    return {
        "fetches": fetches,
        "fetch_details": fetch_details,
        "commits": commits,
        "write_sessions": write_sessions,
    }


def _run():
    asyncio.run(player_stats.run(sleep=0))


class TestPerPlayerTransaction:
    def test_saved_tennisabstract_slug_is_used_for_the_daily_fetch(self, harness, monkeypatch):
        async def _persist(*args, **kwargs):
            return None

        monkeypatch.setattr(player_stats, "_persist_player_stats", _persist)

        _run()

        assert harness["fetch_details"] == [
            ("Player One", "ATP", None),
            ("Player Two", "WTA", "PlayerTwoOfficial"),
            ("Player Three", "ATP", None),
        ]

    def test_each_player_commits_its_own_transaction(self, harness, monkeypatch):
        persisted = []

        async def _persist(db, player_id, rows, today):
            persisted.append(player_id)

        monkeypatch.setattr(player_stats, "_persist_player_stats", _persist)

        _run()

        assert persisted == [1, 2, 3]
        # One session and one commit each, rather than one transaction spanning the slate.
        assert len(harness["write_sessions"]) == 3
        assert len(harness["commits"]) == 3


class TestDeadlockRecovery:
    def test_a_deadlock_is_retried_and_the_player_is_persisted(self, harness, monkeypatch):
        attempts = []

        async def _persist(db, player_id, rows, today):
            attempts.append(player_id)
            if player_id == 2 and attempts.count(2) == 1:
                raise _db_error("40P01")

        monkeypatch.setattr(player_stats, "_persist_player_stats", _persist)

        _run()

        assert attempts == [1, 2, 2, 3]

    def test_a_retry_does_not_refetch_from_tennisabstract(self, harness, monkeypatch):
        attempts = []

        async def _persist(db, player_id, rows, today):
            attempts.append(player_id)
            if player_id == 2 and attempts.count(2) == 1:
                raise _db_error("40P01")

        monkeypatch.setattr(player_stats, "_persist_player_stats", _persist)

        _run()

        assert attempts.count(2) == 2
        assert harness["fetches"] == ["Player One", "Player Two", "Player Three"]

    def test_a_player_that_never_writes_does_not_abort_the_slate(self, harness, monkeypatch):
        persisted = []

        async def _persist(db, player_id, rows, today):
            if player_id == 2:
                raise _db_error("40P01")
            persisted.append(player_id)

        monkeypatch.setattr(player_stats, "_persist_player_stats", _persist)

        _run()

        # Player 2 exhausts its retries, players 1 and 3 still land.
        assert persisted == [1, 3]

    def test_a_non_conflict_error_still_stops_the_run(self, harness, monkeypatch):
        async def _persist(db, player_id, rows, today):
            raise _db_error("23505")

        monkeypatch.setattr(player_stats, "_persist_player_stats", _persist)

        with pytest.raises(DBAPIError):
            _run()


class TestSkips:
    def test_a_player_missing_from_tennisabstract_is_skipped_without_a_write(
        self, harness, monkeypatch
    ):
        monkeypatch.setattr(player_stats, "_fetch_matches", lambda *a, **k: None)
        persisted = []

        async def _persist(db, player_id, rows, today):
            persisted.append(player_id)

        monkeypatch.setattr(player_stats, "_persist_player_stats", _persist)

        _run()

        assert persisted == []
        assert harness["commits"] == []

    def test_a_player_with_too_little_data_is_skipped_without_a_write(
        self, harness, monkeypatch
    ):
        monkeypatch.setattr(player_stats, "_aggregate", lambda *a, **k: None)
        persisted = []

        async def _persist(db, player_id, rows, today):
            persisted.append(player_id)

        monkeypatch.setattr(player_stats, "_persist_player_stats", _persist)

        _run()

        assert persisted == []
        assert harness["commits"] == []

"""Concurrent ingest runs deadlock on `players`, and the loser must retry, not die.

Two jobs upserting players take row locks in whatever order the provider returned them,
so Postgres kills one with 40P01. That is not a data problem: the transaction simply has
to run again. It happens in practice, since the hourly cron overlaps any manual run.
"""

import asyncio

import pytest
from sqlalchemy.exc import DBAPIError, OperationalError

from app.db import retry as retry_mod
from app.db.retry import is_retryable_conflict, run_in_session_with_retry


class _Orig(Exception):
    def __init__(self, sqlstate):
        self.sqlstate = sqlstate


def _db_error(sqlstate) -> DBAPIError:
    return OperationalError("stmt", {}, _Orig(sqlstate))


class _FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


@pytest.fixture
def no_sleep(monkeypatch):
    async def _instant(_seconds):
        return None

    monkeypatch.setattr(retry_mod.asyncio, "sleep", _instant)


@pytest.fixture
def fake_sessions(monkeypatch):
    monkeypatch.setattr(retry_mod, "SessionLocal", lambda: _FakeSession())


class TestClassification:
    def test_deadlock_is_retryable(self):
        assert is_retryable_conflict(_db_error("40P01"))

    def test_serialization_failure_is_retryable(self):
        assert is_retryable_conflict(_db_error("40001"))

    @pytest.mark.parametrize("state", ["23505", "42P01", "08006", None])
    def test_other_errors_are_not_retryable(self, state):
        assert not is_retryable_conflict(_db_error(state))

    def test_a_plain_exception_is_not_retryable(self):
        assert not is_retryable_conflict(ValueError("nope"))


class TestRetryLoop:
    def test_work_that_succeeds_runs_once(self, fake_sessions, no_sleep):
        calls = []

        async def work(db):
            calls.append(1)
            return "ok"

        assert asyncio.run(run_in_session_with_retry(work)) == "ok"
        assert len(calls) == 1

    def test_a_deadlock_is_retried_and_can_succeed(self, fake_sessions, no_sleep):
        calls = []

        async def work(db):
            calls.append(1)
            if len(calls) < 3:
                raise _db_error("40P01")
            return "recovered"

        assert asyncio.run(run_in_session_with_retry(work)) == "recovered"
        assert len(calls) == 3

    def test_it_gives_up_after_the_attempt_limit(self, fake_sessions, no_sleep):
        calls = []

        async def work(db):
            calls.append(1)
            raise _db_error("40P01")

        with pytest.raises(DBAPIError):
            asyncio.run(run_in_session_with_retry(work, attempts=3))
        assert len(calls) == 3

    def test_a_non_conflict_error_is_not_retried(self, fake_sessions, no_sleep):
        calls = []

        async def work(db):
            calls.append(1)
            raise _db_error("23505")

        with pytest.raises(DBAPIError):
            asyncio.run(run_in_session_with_retry(work))
        assert len(calls) == 1

    def test_every_attempt_gets_a_fresh_session(self, monkeypatch, no_sleep):
        made = []

        def session_factory():
            s = _FakeSession()
            made.append(s)
            return s

        monkeypatch.setattr(retry_mod, "SessionLocal", session_factory)
        seen = []

        async def work(db):
            seen.append(db)
            if len(seen) < 2:
                raise _db_error("40P01")
            return "ok"

        asyncio.run(run_in_session_with_retry(work))
        assert len(made) == 2
        assert seen[0] is not seen[1]

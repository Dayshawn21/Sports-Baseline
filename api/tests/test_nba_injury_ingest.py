from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

import httpx
import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import TextClause
from tenacity import wait_none

from app.core.nba_injuries import NbaInjuryFeed, parse_injury_feed
from app.ingest import nba_injuries as ingest
from app.repositories import nba_injuries as repo

FETCHED = datetime(2026, 10, 21, 18, tzinfo=timezone.utc)


def payload() -> dict[str, object]:
    path = Path(__file__).parent / "fixtures/espn_nba_injuries.json"
    return cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))


@dataclass
class Mappings:
    rows: list[dict[str, object]]

    def one(self) -> dict[str, object]:
        assert len(self.rows) == 1
        return self.rows[0]

    def all(self) -> list[dict[str, object]]:
        return self.rows


@dataclass
class Scalars:
    values: list[str]

    def all(self) -> list[str]:
        return self.values


@dataclass
class Result:
    scalar: int | None = None
    rows: list[dict[str, object]] = field(default_factory=list)
    values: list[str] = field(default_factory=list)

    def scalar_one_or_none(self) -> int | None:
        return self.scalar

    def mappings(self) -> Mappings:
        return Mappings(self.rows)

    def scalars(self) -> Scalars:
        return Scalars(self.values)


@dataclass
class Session:
    results: list[Result]
    fail_on: int | None = None
    calls: list[tuple[str, object]] = field(default_factory=list)
    commits: int = 0
    rollbacks: int = 0

    async def execute(self, statement: TextClause, params: object = None) -> Result:
        self.calls.append((str(statement), params))
        if len(self.calls) == self.fail_on:
            raise SQLAlchemyError("injected write failure")
        return self.results.pop(0) if self.results else Result()

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


def db(session: Session) -> AsyncSession:
    return cast(AsyncSession, session)


def test_unresolved_linkage_is_nba_scoped_and_does_not_discard_entries() -> None:
    feed = parse_injury_feed(payload())
    session = Session([Result(values=["4712863"]), Result(scalar=7)])
    summary = asyncio.run(ingest.ingest_feed(db(session), feed, FETCHED))
    assert summary.unresolved_ids == ("3913176", "5044385")
    assert (summary.teams, summary.entries, summary.team_mismatches, summary.snapshot_id) == (3, 3, 1, 7)
    assert (session.commits, session.rollbacks) == (1, 0)
    assert "sport = 'nba'" in session.calls[0][0]
    rows = cast(list[dict[str, object]], session.calls[-1][1])
    assert len(rows) == 3
    mismatch = next(row for row in rows if row["espn_athlete_id"] == "3913176")
    assert (mismatch["espn_team_id"], mismatch["athlete_team_id"]) == ("12", "28")


def test_dry_run_reads_linkage_but_never_inserts_or_commits() -> None:
    session = Session([Result(values=["4712863"])])
    summary = asyncio.run(ingest.ingest_feed(db(session), parse_injury_feed(payload()), FETCHED, True))
    assert summary.dry_run and summary.snapshot_id is None
    assert len(session.calls) == 1 and session.calls[0][0].strip().startswith("SELECT")
    assert (session.commits, session.rollbacks) == (0, 0)
    assert "dry run" in str(summary) and "2 unresolved athlete IDs" in str(summary)


def test_valid_empty_report_stores_a_marker_and_does_not_read_player_ids() -> None:
    feed = replace(parse_injury_feed(payload()), injuries=())
    session = Session([Result(scalar=8)])
    summary = asyncio.run(ingest.ingest_feed(db(session), feed, FETCHED))
    assert (summary.entries, summary.unresolved_ids, summary.snapshot_id) == (0, (), 8)
    assert len(session.calls) == 1
    assert cast(dict[str, object], session.calls[0][1])["entry_count"] == 0
    assert session.commits == 1


def test_entry_write_failure_rolls_back_the_header_with_no_commit() -> None:
    session = Session([Result(), Result(scalar=9)], fail_on=3)
    with pytest.raises(SQLAlchemyError, match="injected"):
        asyncio.run(ingest.ingest_feed(db(session), parse_injury_feed(payload()), FETCHED))
    assert "INSERT INTO nba_injury_snapshots" in session.calls[1][0]
    assert "INSERT INTO nba_player_injuries" in session.calls[2][0]
    assert (session.commits, session.rollbacks) == (0, 1)


def existing_results(feed: NbaInjuryFeed) -> list[Result]:
    return [
        Result(), Result(rows=[{"id": 7, "source_timestamp": feed.source_timestamp, "entry_count": len(feed.injuries)}]),
        Result(rows=[asdict(row) for row in reversed(feed.injuries)]),
    ]


@pytest.mark.parametrize("empty", [False, True])
def test_same_timestamp_and_contents_reuse_immutable_snapshot(empty: bool) -> None:
    feed = parse_injury_feed(payload())
    if empty:
        feed = replace(feed, injuries=())
    session = Session(existing_results(feed))
    assert asyncio.run(repo.store_snapshot(db(session), feed, FETCHED)) == 7
    assert len(session.calls) == 3
    assert all(sql.strip().startswith("SELECT") for sql, _ in session.calls[1:])


@pytest.mark.parametrize("change", ["status", "count", "source_time", "missing_row"])
def test_timestamp_collision_cannot_overwrite_or_hide_different_contents(change: str) -> None:
    feed = parse_injury_feed(payload())
    results = existing_results(feed)
    if change == "status":
        results[2].rows[0]["status"] = "Different"
    elif change == "count":
        results[1].rows[0]["entry_count"] = 1
    elif change == "source_time":
        results[1].rows[0]["source_timestamp"] = FETCHED
    else:
        results[2].rows.pop()
    session = Session(results)
    with pytest.raises(ValueError, match="different contents"):
        asyncio.run(repo.store_snapshot(db(session), feed, FETCHED))
    assert len(session.calls) == 3


def test_naive_batch_time_and_duplicate_identity_are_rejected_before_sql() -> None:
    feed = parse_injury_feed(payload())
    session = Session([])
    with pytest.raises(ValueError, match="timezone-aware"):
        asyncio.run(repo.store_snapshot(db(session), feed, FETCHED.replace(tzinfo=None)))
    duplicate = replace(feed, injuries=(*feed.injuries, feed.injuries[0]))
    with pytest.raises(ValueError, match="duplicate"):
        asyncio.run(repo.store_snapshot(db(session), duplicate, FETCHED))
    assert not session.calls


@pytest.fixture
def no_retry_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ingest, "wait_exponential", lambda **kwargs: wait_none())


@pytest.mark.parametrize("failure", [429, 503, "transport"])
def test_transient_fetch_failure_is_retried_then_parsed(failure: int | str, no_retry_wait: None) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            if failure == "transport":
                raise httpx.ConnectError("temporary failure", request=request)
            return httpx.Response(cast(int, failure))
        return httpx.Response(200, json=payload())

    async def fetch() -> NbaInjuryFeed:
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            return await ingest.fetch_injuries(client)

    assert len(asyncio.run(fetch()).injuries) == 3
    assert len(requests) == 2
    assert requests[0].extensions["timeout"] == {"connect": 30, "read": 30, "write": 30, "pool": 30}


@pytest.mark.parametrize(("status", "body", "attempts"), [
    (403, "{}", 1), (503, "{}", 3), (200, "not-json", 1),
    (200, '{"status":"error"}', 1),
])
def test_permanent_or_exhausted_fetch_failure_cannot_become_an_empty_report(
    status: int, body: str, attempts: int, no_retry_wait: None,
) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(status, text=body)

    async def fetch() -> NbaInjuryFeed:
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            return await ingest.fetch_injuries(client)

    with pytest.raises((httpx.HTTPStatusError, ValueError)):
        asyncio.run(fetch())
    assert len(requests) == attempts

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nhl_context_resolution import ContextGameCandidate, ContextPlayerCandidate
from app.ingest import nhl_context as ingest

NOW = datetime(2026, 10, 24, 16, 30, tzinfo=timezone.utc)
DAY = NOW.date()
FIXTURES = Path(__file__).parent / "fixtures"


def payload(kind: str) -> dict[str, object]:
    return json.loads((FIXTURES / f"espn_nhl_{kind}.json").read_text())


@dataclass
class Session:
    commits: int = 0
    rollbacks: int = 0
    closed: bool = False

    async def __aenter__(self) -> Session:
        return self

    async def __aexit__(self, *args: object) -> None:
        self.closed = True

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


@pytest.fixture
def repositories(monkeypatch: pytest.MonkeyPatch) -> None:
    players = [ContextPlayerCandidate(1, "nhl", "Pavel Mintyukov", "ANA", "D"),
               ContextPlayerCandidate(2, "nhl", "Joseph Woll", "PHI", "G")]
    games = [ContextGameCandidate(10, "nhl", "REG", "ANA", "PHI", NOW.replace(hour=17))]
    for name, value in [("prepare_dry_run", None), ("get_context_players", players),
                        ("get_context_games", games), ("store_injury_snapshot", 50), ("store_goalie_snapshot", 51)]:
        monkeypatch.setattr(ingest.repo, name, AsyncMock(return_value=value))


def run_components(
    respond: Callable[[httpx.Request], httpx.Response], dry_run: bool = True, dates: tuple[date, ...] = (DAY,),
) -> tuple[tuple[ingest.ComponentSummary, ...], list[Session]]:
    sessions: list[Session] = []

    def factory() -> AsyncSession:
        session = Session()
        sessions.append(session)
        return cast(AsyncSession, session)

    async def run() -> tuple[ingest.ComponentSummary, ...]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            return await ingest.run_components(ingest.EspnContextFetcher(client), factory, dates, dry_run)

    return asyncio.run(run()), sessions


def success(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith("/injuries"):
        return httpx.Response(200, json=payload("injuries"))
    if request.url.params["dates"] != "20261024":
        return httpx.Response(200, json={"leagues": [{"id": "90", "slug": "nhl"}], "events": []})
    return httpx.Response(200, json=payload("goalies"))


def test_dry_run_resolves_and_reports_without_any_snapshot_access_or_commit(repositories: None) -> None:
    summaries, sessions = run_components(success)
    injury, goalies = summaries
    assert (injury.entries, injury.linked_players, len(injury.unresolved_ids)) == (3, 1, 2)
    assert (goalies.entries, goalies.linked_players, len(goalies.unresolved_ids)) == (4, 1, 3)
    assert goalies.unmatched_events == ("401892567",)
    assert all(row.snapshot_id is None and row.error is None for row in summaries)
    assert all(session.commits == session.rollbacks == 0 and session.closed for session in sessions)
    assert cast(AsyncMock, ingest.repo.prepare_dry_run).await_count == 2
    cast(AsyncMock, ingest.repo.store_injury_snapshot).assert_not_awaited()
    cast(AsyncMock, ingest.repo.store_goalie_snapshot).assert_not_awaited()


def test_write_components_commit_independently_including_empty_goalie_date(repositories: None) -> None:
    summaries, sessions = run_components(success, False, (DAY, date(2026, 10, 25)))
    assert [row.snapshot_id for row in summaries] == [50, 51, 51]
    assert summaries[-1].entries == 0
    assert all(session.commits == 1 and session.rollbacks == 0 and session.closed for session in sessions)
    cast(AsyncMock, ingest.repo.prepare_dry_run).assert_not_awaited()
    stored = cast(AsyncMock, ingest.repo.store_goalie_snapshot).await_args_list[0].args
    links, games = stored[3], stored[4]
    assert links[("401892566", "15")].player_id == 2
    assert games["401892566"].game_id == 10


@pytest.mark.parametrize("failure", ["http", "parse", "write", "commit"])
def test_injury_failure_does_not_prevent_other_components_or_leak_error_details(
    failure: str, repositories: None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    if failure == "write":
        cast(AsyncMock, ingest.repo.store_injury_snapshot).side_effect = SQLAlchemyError("secret database URL")
    if failure == "commit":
        original = Session.commit
        fail_next = True

        async def commit(session: Session) -> None:
            nonlocal fail_next
            if fail_next:
                fail_next = False
                raise SQLAlchemyError("secret database URL")
            await original(session)

        monkeypatch.setattr(Session, "commit", commit)

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/injuries") and failure in ("http", "parse"):
            return httpx.Response(403, text="secret upstream body") if failure == "http" else httpx.Response(200, json={})
        return success(request)

    summaries, sessions = run_components(respond, False, (DAY, date(2026, 10, 25)))
    assert summaries[0].error in {"http_403", "invalid_feed_or_links", "database_error"}
    assert all(summary.error is None for summary in summaries[1:])
    assert [row.commits for row in sessions[-2:]] == [1, 1]
    if failure in ("write", "commit"):
        assert sessions[0].rollbacks == 1
    assert "secret" not in " ".join(map(str, summaries))


def test_goalie_write_failure_rolls_back_only_that_component(repositories: None) -> None:
    cast(AsyncMock, ingest.repo.store_goalie_snapshot).side_effect = [SQLAlchemyError("private"), 52]
    summaries, sessions = run_components(success, False, (DAY, date(2026, 10, 25)))
    assert [row.error for row in summaries] == [None, "database_error", None]
    assert [(row.commits, row.rollbacks) for row in sessions] == [(1, 0), (0, 1), (1, 0)]


@pytest.mark.parametrize("failure", [429, 503, "transport", "timeout"])
def test_transient_fetch_is_retried_then_timestamped_after_response(
    failure: int | str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []
    monkeypatch.setattr(ingest.asyncio, "sleep", AsyncMock())
    monkeypatch.setattr(ingest, "_now", lambda: NOW)

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            if failure == "transport":
                raise httpx.ConnectError("private", request=request)
            if failure == "timeout":
                raise TimeoutError("private")
            return httpx.Response(cast(int, failure))
        return httpx.Response(200, json=payload("injuries"))

    async def fetch() -> tuple[object, datetime]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            return await ingest.EspnContextFetcher(client).get("injuries")

    _, fetched = asyncio.run(fetch())
    assert fetched == NOW and len(requests) == 2
    assert requests[0].extensions["timeout"] == {"connect": 30, "read": 30, "write": 30, "pool": 30}


@pytest.mark.parametrize("status,body,attempts,error", [
    (403, "private", 1, "http_403"), (503, "private", 3, "http_503"),
    (200, "not JSON", 1, None),
])
def test_fetch_exhaustion_permanent_http_and_bad_json_do_not_turn_into_empty_success(
    status: int, body: str, attempts: int, error: str | None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []
    monkeypatch.setattr(ingest.asyncio, "sleep", AsyncMock())

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(status, text=body)

    async def fetch() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            await ingest.EspnContextFetcher(client).get("injuries")

    with pytest.raises(ingest.FetchFailure if error else ValueError) as exc:
        asyncio.run(fetch())
    assert len(requests) == attempts
    if error:
        assert str(exc.value) == error


@pytest.mark.parametrize("header,delay", [("5", 5), ("Sat, 24 Oct 2026 16:30:05 GMT", 5),
                                         ("Sat, 24 Oct 2026 16:29:00 GMT", 0)])
def test_retry_after_supports_seconds_and_aware_http_dates(header: str, delay: float) -> None:
    assert ingest.retry_after_seconds(header, NOW) == delay


def test_retry_after_cooldown_is_honored_before_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ingest, "monotonic", lambda: 0.0)
    sleep = AsyncMock()
    monkeypatch.setattr(ingest.asyncio, "sleep", sleep)
    requests = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(429, headers={"Retry-After": "5"}) if requests == 1 else httpx.Response(200, json={})

    async def fetch() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            await ingest.EspnContextFetcher(client).get("injuries")

    asyncio.run(fetch())
    sleep.assert_awaited_once_with(5.0)


def test_last_retry_cooldown_also_applies_to_the_next_component(
    repositories: None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ingest, "monotonic", lambda: 0.0)
    sleep = AsyncMock()
    monkeypatch.setattr(ingest.asyncio, "sleep", sleep)
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/injuries"):
            return httpx.Response(429, headers={"Retry-After": "5"})
        return success(request)

    summaries, _ = run_components(respond)
    assert summaries[0].error == "http_429" and summaries[1].error is None
    assert len(requests) == 4 and sleep.await_count == 3
    assert all(call.args == (5.0,) for call in sleep.await_args_list)


def test_explicit_goalie_date_does_not_date_or_replace_current_injury_request(repositories: None) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return success(request)

    summaries, _ = run_components(respond, dates=(date(2026, 10, 25),))
    assert summaries[0].kind == "injuries" and summaries[0].scope_date is None
    assert requests[0].url.path.endswith("/injuries") and not requests[0].url.params
    assert dict(requests[1].url.params) == {"dates": "20261025", "limit": "100"}


@pytest.mark.parametrize("header", ["60", "bad header"])
def test_long_or_invalid_retry_after_blocks_later_provider_calls_in_this_run(header: str, repositories: None) -> None:
    requests = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(429, headers={"Retry-After": header})

    summaries, sessions = run_components(respond, dates=(DAY, date(2026, 10, 25)))
    assert requests == 1 and not sessions
    assert summaries[0].error in {"retry_after_exceeds_bound", "invalid_retry_after"}
    assert [row.error for row in summaries[1:]] == ["provider_cooldown", "provider_cooldown"]


def test_slow_response_has_a_wall_clock_fetch_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ingest, "FETCH_DEADLINE", 0.01)

    async def respond(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(1)
        return httpx.Response(200, json={})

    async def fetch() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            await ingest.EspnContextFetcher(client).get("injuries")

    with pytest.raises(ingest.FetchFailure, match="fetch_deadline"):
        asyncio.run(fetch())


def test_default_scope_is_eastern_today_and_tomorrow_and_explicit_date_is_one_day() -> None:
    now = datetime(2026, 10, 24, 3, tzinfo=timezone.utc)
    assert ingest.selected_dates(now) == (date(2026, 10, 23), DAY)
    assert ingest.selected_dates(now, DAY) == (DAY,)
    with pytest.raises(ValueError, match="timezone-aware"):
        ingest.selected_dates(now.replace(tzinfo=None))


@pytest.mark.parametrize("value", ["20261024", "10/24/2026", "2026-02-30", "not a date"])
def test_cli_dates_require_canonical_format(value: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        ingest._date_argument(value)


def test_cli_reports_all_components_before_failing_and_passes_options(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    summaries = (ingest.ComponentSummary("injuries", None, error="database_error"),
                 ingest.ComponentSummary("goalies", DAY, NOW))
    run = AsyncMock(return_value=summaries)
    monkeypatch.setattr(ingest, "run", run)
    monkeypatch.setattr(ingest.sys, "argv", ["nhl_context", "--dry-run", "--date", "2026-10-24"])
    with pytest.raises(SystemExit) as exc:
        asyncio.run(ingest._main())
    assert exc.value.code == 1
    run.assert_awaited_once_with(True, DAY)
    output = capsys.readouterr()
    assert "database_error" in output.err and "goalies 2026-10-24 dry run" in output.out

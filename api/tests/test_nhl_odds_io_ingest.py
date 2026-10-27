import asyncio
import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

from app.core.nhl_odds import parse_nhl_game_markets, provider_team_code
from app.ingest import nhl_odds_io as ingest

NOW = datetime(2026, 10, 23, 20, tzinfo=UTC)
EVENT = json.loads((Path(__file__).parent / "fixtures" / "odds_api_io_nhl_event.json").read_text())
GAME = {"game_id": 7, "start_utc": NOW + timedelta(hours=4), "home_team": "MTL", "away_team": "CHI"}


class _Session:
    def __init__(self) -> None:
        self.commit = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_: object) -> None:
        pass


class Harness:
    def __init__(self, monkeypatch: pytest.MonkeyPatch, events=None, games=None, responses=None) -> None:
        self.session = _Session()
        self.requests: list[httpx.Request] = []
        self.events = events if events is not None else [EVENT]
        self.responses = list(responses) if responses is not None else [([EVENT], "98")]
        self.remaining = "99"
        self.insert = AsyncMock(return_value=501)
        self.read = AsyncMock(return_value=games if games is not None else [GAME])
        client_factory = httpx.AsyncClient
        monkeypatch.setattr(ingest, "SessionLocal", lambda: self.session)
        monkeypatch.setattr(ingest.nhl_repo, "get_upcoming_games", self.read)
        monkeypatch.setattr(ingest.nhl_repo, "insert_game_odds_snapshot", self.insert)
        monkeypatch.setattr(ingest, "_now", lambda: NOW)
        monkeypatch.setattr(ingest.settings, "odds_api_key", "test-secret")
        monkeypatch.setattr(ingest.httpx, "AsyncClient", lambda: client_factory(transport=httpx.MockTransport(self.handle)))

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.path.endswith("/events"):
            return httpx.Response(200, json=self.events, headers={"x-ratelimit-remaining": self.remaining})
        reply = self.responses.pop(0)
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, httpx.Response):
            return reply
        payload, remaining = reply
        return httpx.Response(200, json=payload, headers={"x-ratelimit-remaining": remaining})


def _slate(size: int) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    names = ["Montreal Canadiens", "Boston Bruins", "Buffalo Sabres", "Calgary Flames",
             "Carolina Hurricanes", "Colorado Avalanche", "Columbus Blue Jackets",
             "Dallas Stars", "Detroit Red Wings", "Edmonton Oilers", "Florida Panthers"]
    games, events = [], []
    for index, name in enumerate(names[:size]):
        games.append({**GAME, "game_id": index + 1, "home_team": provider_team_code(name)})
        events.append({**EVENT, "id": index + 1, "home": name})
    return games, events


def test_dry_run_parses_both_books_without_inserting_or_committing(monkeypatch) -> None:
    harness = Harness(monkeypatch)
    counts = asyncio.run(ingest.run(dry_run=True))
    assert (counts["requests"], counts["matched"], counts["candidates"], counts["written"]) == (2, 1, 6, 0)
    for book in ("draftkings", "fanduel"):
        for market in ("moneyline", "spread", "total"):
            assert counts[f"candidate_{book}_{market}"] == 1
    assert counts["unsupported_or_malformed_book"] == 1  # Bet365, paid-only since 2026-10-26
    harness.insert.assert_not_awaited()
    harness.session.commit.assert_not_awaited()
    assert harness.requests[0].url.params["sport"] == "ice-hockey"
    assert harness.requests[1].url.params["bookmakers"] == "DraftKings,FanDuel"
    assert all(request.url.host == "api.odds-api.io" for request in harness.requests)


def test_write_mode_passes_oriented_rows_and_event_provenance(monkeypatch) -> None:
    flipped = {**GAME, "home_team": "CHI", "away_team": "MTL"}
    harness = Harness(monkeypatch, games=[flipped])
    counts = asyncio.run(ingest.run())
    assert counts["written"] == 6
    args, kwargs = harness.insert.await_args_list[0]
    assert args[:3] == (harness.session, 7, "draftkings")
    assert (args[3].first_odds, args[3].second_odds) == (130, -154)
    assert kwargs == {"event_id": 1001}
    harness.session.commit.assert_awaited_once()


def test_no_games_makes_no_http_requests_and_needs_no_key(monkeypatch) -> None:
    harness = Harness(monkeypatch, games=[])
    monkeypatch.setattr(ingest.settings, "odds_api_key", "")
    counts = asyncio.run(ingest.run())
    assert counts == {"requests": 0, "matched": 0, "candidates": 0, "written": 0}
    assert harness.requests == []
    harness.session.commit.assert_not_awaited()


@pytest.mark.parametrize("size, batches", [(10, [10]), (11, [10, 1])])
def test_only_matched_events_are_requested_in_batches_of_ten(monkeypatch, size, batches) -> None:
    games, events = _slate(size)
    harness = Harness(monkeypatch, events=events, games=games, responses=[([], "98"), ([], "97")])
    counts = asyncio.run(ingest.run(dry_run=True))
    assert counts["matched"] == size
    assert [len(request.url.params["eventIds"].split(",")) for request in harness.requests[1:]] == batches


@pytest.mark.parametrize("balance", ["20", "0", "-1", "bad", "", "101"])
def test_low_or_unknown_quota_stops_after_discovery(monkeypatch, balance) -> None:
    harness = Harness(monkeypatch)
    harness.remaining = balance
    counts = asyncio.run(ingest.run(dry_run=True))
    assert counts["stopped_at_floor"] == 1
    assert len(harness.requests) == 1


def test_exact_floor_boundary_allows_one_request_then_stops(monkeypatch) -> None:
    games, events = _slate(11)
    harness = Harness(monkeypatch, events=events, games=games, responses=[([], "20")])
    harness.remaining = "21"
    counts = asyncio.run(ingest.run(dry_run=True))
    assert counts["requests"] == 2 and counts["stopped_at_floor"] == 1


@pytest.mark.parametrize("failure", [
    httpx.Response(429, headers={"Retry-After": "3600"}), httpx.Response(403),
    httpx.ReadTimeout("timeout test-secret"), httpx.ConnectError("failed test-secret"),
    httpx.Response(200, content="invalid json"), httpx.Response(200, json={"error": "bad"}),
])
def test_http_and_payload_failures_stop_without_retry_or_secret_output(monkeypatch, caplog, failure) -> None:
    games, events = _slate(11)
    harness = Harness(monkeypatch, events=events, games=games, responses=[failure])
    counts = asyncio.run(ingest.run(dry_run=True))
    assert counts["failed"] == 1 and counts["requests_remaining"] == -1
    assert len(harness.requests) == 2
    assert "test-secret" not in caplog.text and "apiKey" not in caplog.text


def test_good_batch_is_committed_when_later_batch_fails(monkeypatch) -> None:
    games, events = _slate(11)
    harness = Harness(monkeypatch, events=events, games=games, responses=[([events[0]], "98"), httpx.ReadTimeout("stop")])
    counts = asyncio.run(ingest.run())
    assert counts["written"] == 6 and counts["failed"] == 1 and counts["requests"] == 3
    harness.session.commit.assert_awaited_once()


def test_unrequested_ids_bad_records_and_unconfigured_books_do_not_hide_valid_siblings(monkeypatch) -> None:
    event = copy.deepcopy(EVENT)
    event["bookmakers"]["Pinnacle"] = event["bookmakers"]["Bet365"]
    harness = Harness(monkeypatch, responses=[([None, {"id": "bad"}, {**EVENT, "id": 888}, event], "98")])
    counts = asyncio.run(ingest.run(dry_run=True))
    assert counts["candidates"] == 6
    assert counts["malformed_event"] == 2
    assert counts["unrequested_or_changed_event"] == 1
    assert counts["unsupported_or_malformed_book"] == 2  # Pinnacle and Bet365


@pytest.mark.parametrize("changes", [
    {"home": "Boston Bruins"}, {"date": "2026-10-24T01:00:00Z"},
    {"status": "live"}, {"league": {"slug": "usa-ahl"}},
])
def test_changed_response_identity_is_rejected(monkeypatch, changes) -> None:
    harness = Harness(monkeypatch, responses=[([{**EVENT, **changes}], "98")])
    counts = asyncio.run(ingest.run(dry_run=True))
    assert counts["candidates"] == 0
    assert counts["unrequested_or_changed_event"] == 1


def test_game_that_starts_during_fetch_is_skipped(monkeypatch) -> None:
    harness = Harness(monkeypatch)
    times = iter([NOW, GAME["start_utc"]])
    monkeypatch.setattr(ingest, "_now", lambda: next(times, GAME["start_utc"]))
    counts = asyncio.run(ingest.run())
    assert counts["started_before_write"] == 6 and counts["written"] == 0
    harness.insert.assert_not_awaited()
    harness.session.commit.assert_not_awaited()


def test_repository_rejection_is_counted_without_claiming_a_write(monkeypatch) -> None:
    harness = Harness(monkeypatch)
    harness.insert.return_value = None
    counts = asyncio.run(ingest.run())
    assert counts["ineligible_at_write"] == 6 and counts["written"] == 0
    harness.session.commit.assert_not_awaited()


def test_event_selection_rejects_started_pending_unknown_and_conflicting_events() -> None:
    events = [
        None, {**EVENT, "id": True}, {**EVENT, "id": 2, "status": "live"},
        {**EVENT, "id": 3, "date": NOW.isoformat()},
        {**EVENT, "id": 4, "home": "Unknown"},
        {**EVENT, "id": 5}, {**EVENT, "id": 6},
        {**EVENT, "id": 7}, {**EVENT, "id": 7, "away": "Boston Bruins"},
    ]
    selected, counts = ingest.select_events(events, [GAME], NOW)
    assert selected == {}
    assert counts["malformed_event"] == 2
    assert counts["not_pending"] == 1 and counts["started"] == 1
    assert counts["conflicting_event"] == 1 and counts["conflicting_game"] == 2


def test_identical_duplicate_events_are_deduplicated() -> None:
    selected, _ = ingest.select_events([EVENT, copy.deepcopy(EVENT)], [GAME], NOW)
    assert list(selected) == [1001]


def test_conflicting_odds_responses_skip_the_event(monkeypatch) -> None:
    changed = copy.deepcopy(EVENT)
    changed["bookmakers"]["Bet365"][0]["odds"][0]["home"] = "1.80"
    harness = Harness(monkeypatch, responses=[([EVENT, changed], "98")])
    counts = asyncio.run(ingest.run(dry_run=True))
    assert counts["conflicting_event"] == 1 and counts["candidates"] == 0


def test_missing_event_book_and_market_coverage_are_explicit(monkeypatch) -> None:
    games, events = _slate(2)
    event = {**events[0], "bookmakers": {"FanDuel": [EVENT["bookmakers"]["FanDuel"][0]]}}
    harness = Harness(monkeypatch, events=events, games=games, responses=[([event], "98")])
    counts = asyncio.run(ingest.run(dry_run=True))
    assert counts["missing_event"] == 1
    assert counts["missing_book_draftkings"] == 1
    assert counts["missing_fanduel_spread"] == 1 and counts["missing_fanduel_total"] == 1
    assert counts["candidates"] == 1


@pytest.mark.parametrize("payload", [[], [None], [{**EVENT, "bookmakers": None}], [{**EVENT, "bookmakers": {"Bet365": None}}]])
def test_empty_or_malformed_odds_are_not_written(monkeypatch, payload) -> None:
    harness = Harness(monkeypatch, responses=[(payload, "98")])
    counts = asyncio.run(ingest.run())
    assert counts["written"] == counts["candidates"] == 0
    harness.insert.assert_not_awaited()
    harness.session.commit.assert_not_awaited()


def test_invalid_discovery_payload_stops_before_requesting_odds(monkeypatch) -> None:
    harness = Harness(monkeypatch, events={"error": "invalid"})
    counts = asyncio.run(ingest.run(dry_run=True))
    assert counts["failed"] == 1 and len(harness.requests) == 1


def test_empty_discovery_spends_only_the_discovery_request(monkeypatch) -> None:
    harness = Harness(monkeypatch, events=[])
    counts = asyncio.run(ingest.run(dry_run=True))
    assert counts["matched"] == 0 and len(harness.requests) == 1


def test_missing_header_after_a_good_batch_stops_subsequent_requests(monkeypatch) -> None:
    games, events = _slate(11)
    harness = Harness(monkeypatch, events=events, games=games, responses=[([events[0]], "")])
    counts = asyncio.run(ingest.run())
    assert counts["stopped_at_floor"] == 1 and counts["written"] == 6
    assert counts["requests_remaining"] == -1 and len(harness.requests) == 2
    harness.session.commit.assert_awaited_once()


@pytest.mark.parametrize("counts, exit_code", [({"failed": 1}, 1), ({"stopped_at_floor": 1}, 75)])
def test_cli_propagates_failed_or_incomplete_runs(monkeypatch, counts, exit_code) -> None:
    monkeypatch.setattr(ingest.sys, "argv", ["nhl_odds_io", "--dry-run"])
    monkeypatch.setattr(ingest, "run", AsyncMock(return_value=counts))
    with pytest.raises(SystemExit) as result:
        asyncio.run(ingest._main())
    assert result.value.code == exit_code


@pytest.mark.parametrize("kwargs", [
    {"days_ahead": 0}, {"days_ahead": 15}, {"days_ahead": True},
    {"min_requests_remaining": -1}, {"min_requests_remaining": 100}, {"min_requests_remaining": True},
])
def test_invalid_cli_bounds_fail_before_database_or_http(monkeypatch, kwargs) -> None:
    harness = Harness(monkeypatch)
    with pytest.raises(ValueError):
        asyncio.run(ingest.run(**kwargs))
    harness.read.assert_not_awaited()
    assert harness.requests == []


def test_missing_key_fails_before_provider_call(monkeypatch) -> None:
    harness = Harness(monkeypatch)
    monkeypatch.setattr(ingest.settings, "odds_api_key", "")
    with pytest.raises(ValueError, match="ODDS_API_KEY"):
        asyncio.run(ingest.run(dry_run=True))
    assert harness.requests == []


@pytest.mark.parametrize("name, rung", [
    ("ML", {"home": "1e100", "away": "1.91"}),
    ("ML", {"home": "1.00000000001", "away": "1.91"}),
    ("Totals", {"hdp": "1e100", "over": "1.91", "under": "1.91"}),
])
def test_malformed_numbers_cannot_overflow_storage_columns(name, rung) -> None:
    assert parse_nhl_game_markets([{"name": name, "odds": [rung]}], True) == []

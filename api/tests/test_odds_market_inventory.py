import asyncio
from datetime import datetime, timezone

from pathlib import Path

from app.ingest import odds_api
from app.ingest.odds_api import (
    BOOK_CONFIGS,
    _bookmaker_market_rows,
    bookmaker_market_inventory,
    DEFAULT_INVENTORY_OUTPUT,
    event_market_inventory,
    render_market_inventory,
)


def test_inventory_merges_bookmaker_casing_and_sorts_unique_markets() -> None:
    inventory = bookmaker_market_inventory({
        "draftkings": [
            {"name": "Total Games"}, {"name": "Moneyline"}, {"name": "Total Games"},
        ],
        "DraftKings": [{"name": "Set 1 Winner"}],
        "Bet365": [{"name": "Game Handicap"}],
    })

    assert [(entry.bookmaker, entry.markets) for entry in inventory] == [
        ("Bet365", ("Game Handicap",)),
        ("DraftKings", ("Moneyline", "Set 1 Winner", "Total Games")),
    ]


def test_inventory_supports_list_payloads_and_ignores_malformed_entries() -> None:
    inventory = bookmaker_market_inventory([
        {"key": "betfair_exchange", "markets": [{"name": "Match Winner"}, {}, "bad"]},
        {"name": "Bet365", "markets": [{"name": "Game Spread"}]},
        {"name": "Ignored", "markets": "not a list"},
        "not a bookmaker",
    ])

    assert [(entry.bookmaker, entry.markets) for entry in inventory] == [
        ("Bet365", ("Game Spread",)),
        ("betfair_exchange", ("Match Winner",)),
    ]


def test_event_inventory_merges_bookmakers_from_multiple_event_responses() -> None:
    inventory = event_market_inventory([
        {"bookmakers": {"DraftKings": [{"name": "Moneyline"}]}},
        {"bookmakers": [{"key": "DraftKings", "markets": [{"name": "Total Games"}]}]},
    ])

    assert [(entry.bookmaker, entry.markets) for entry in inventory] == [
        ("DraftKings", ("Moneyline", "Total Games")),
    ]


def test_inventory_report_contains_only_capture_metadata_and_market_names() -> None:
    report = render_market_inventory(
        bookmaker_market_inventory({"DraftKings": [{"name": "Moneyline"}]}),
        datetime(2026, 9, 16, 15, 0, tzinfo=timezone.utc),
        "tennis, one odds batch",
    )

    assert report == """# Odds market inventory

- Captured at: 2026-09-16T15:00:00+00:00
- Request scope: tennis, one odds batch

| Bookmaker | Markets |
|---|---|
| DraftKings | Moneyline |
"""


def test_configured_books_preserve_canonical_names_markets_and_player_orientation() -> None:
    markets = [
        {"name": "Moneyline", "odds": [{"home": 1.5, "away": 2.5}]},
        {"name": "Total Games", "odds": [{"hdp": 21.5, "over": 1.91, "under": 1.91}]},
        {"name": "1st Set Winner", "odds": [{"home": 1.8, "away": 2.1}]},
        {"name": "Game Handicap", "odds": [{"hdp": 2.5, "home": 1.91, "away": 1.91}]},
        {"name": "Set Handicap", "odds": [{"hdp": 1.5, "home": 1.91, "away": 1.91}]},
    ]
    rows_by_book = {
        config.canonical_name: _bookmaker_market_rows(config, markets, home_is_p1=False)
        for config in BOOK_CONFIGS
    }

    assert [row.market for row in rows_by_book["draftkings"]] == [
        "moneyline", "total_games", "set1_winner",
    ]
    assert rows_by_book["draftkings"][0].p1_odds == 150
    assert rows_by_book["draftkings"][0].p2_odds == -200
    assert [row.market for row in rows_by_book["betfair exchange"]] == [
        "moneyline", "total_games", "set1_winner", "game_spread",
    ]
    assert rows_by_book["betfair exchange"][-1].line == -2.5
    assert [row.market for row in rows_by_book["bet365"]] == [
        "moneyline", "total_games", "game_spread", "set_handicap",
    ]
    assert rows_by_book["bet365"][1].line == 21.5
    assert rows_by_book["bet365"][-1].line == -1.5


def test_inventory_request_scope_records_the_bounded_request_shape() -> None:
    assert odds_api._inventory_request_scope("DraftKings,Bet365", 2) == (
        "sport=tennis; one /events request; one /odds/multi request for 2 event(s), "
        "up to 10; bookmakers=DraftKings,Bet365"
    )


def test_inventory_output_defaults_to_the_repository_docs_folder() -> None:
    assert DEFAULT_INVENTORY_OUTPUT.name == "odds-market-inventory.md"
    assert DEFAULT_INVENTORY_OUTPUT.parent.name == "docs"


def test_capture_inventory_uses_one_bounded_batch_and_no_database(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, object]] = []

    async def fake_events(client: object, api_key: str) -> tuple[list[dict], odds_api.RateLimitState]:
        calls.append(("events", api_key))
        return [{"id": "12"}, {"id": 13}, {"id": "bad"}, {"id": 12}], odds_api.RateLimitState()

    async def fake_odds_batch(
        client: object, api_key: str, event_ids: list[int], bookmakers: str
    ) -> tuple[list[dict], odds_api.RateLimitState]:
        calls.append(("odds", (api_key, event_ids, bookmakers)))
        return ([{"bookmakers": {"DraftKings": [{"name": "Moneyline"}]}}], odds_api.RateLimitState())

    monkeypatch.setattr(odds_api, "_fetch_events", fake_events)
    monkeypatch.setattr(odds_api, "_fetch_odds_batch", fake_odds_batch)

    output = asyncio.run(odds_api.capture_market_inventory(
        tmp_path / "inventory.md", bookmakers="DraftKings", api_key="test-key"
    ))

    assert calls == [
        ("events", "test-key"),
        ("odds", ("test-key", [12, 13], "DraftKings")),
    ]
    assert output.read_text(encoding="utf-8").endswith("| DraftKings | Moneyline |\n")


def test_capture_inventory_records_no_active_events_without_an_odds_request(monkeypatch, tmp_path: Path) -> None:
    async def fake_events(client: object, api_key: str) -> tuple[list[dict], odds_api.RateLimitState]:
        return [], odds_api.RateLimitState()

    async def unexpected_odds_request(*args: object) -> tuple[list[dict], odds_api.RateLimitState]:
        raise AssertionError("No odds batch should be requested without active events")

    monkeypatch.setattr(odds_api, "_fetch_events", fake_events)
    monkeypatch.setattr(odds_api, "_fetch_odds_batch", unexpected_odds_request)

    output = asyncio.run(odds_api.capture_market_inventory(tmp_path / "inventory.md", api_key="test-key"))

    report = output.read_text(encoding="utf-8")
    assert "- Result: No active tennis events returned." in report
    assert "| Bookmaker | Markets |" in report


def test_capture_inventory_records_an_empty_bookmaker_batch(monkeypatch, tmp_path: Path) -> None:
    async def fake_events(client: object, api_key: str) -> tuple[list[dict], odds_api.RateLimitState]:
        return [{"id": 12}], odds_api.RateLimitState()

    async def fake_odds_batch(
        client: object, api_key: str, event_ids: list[int], bookmakers: str
    ) -> tuple[list[dict], odds_api.RateLimitState]:
        return ([{"bookmakers": {}}], odds_api.RateLimitState())

    monkeypatch.setattr(odds_api, "_fetch_events", fake_events)
    monkeypatch.setattr(odds_api, "_fetch_odds_batch", fake_odds_batch)

    output = asyncio.run(odds_api.capture_market_inventory(tmp_path / "inventory.md", api_key="test-key"))

    assert "- Result: No bookmaker markets returned for the scoped batch." in output.read_text(encoding="utf-8")


NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)

LISTING = [
    {"id": 1, "league": {"name": "ATP - Paris, France"}, "date": "2026-10-29T15:00:00Z"},
    {"id": 2, "league": {"name": "WTA - Riyadh"}, "date": "2026-10-29T12:30:00Z"},
    {"id": 3, "league": {"name": "ATP - Paris, France, Doubles"}, "date": "2026-10-29T13:00:00Z"},
    {"id": 4, "league": {"name": "Challenger - Bari"}, "date": "2026-10-29T13:00:00Z"},
    {"id": 5, "league": {"name": "ATP - Paris, France"}, "date": "2026-10-30T15:00:00Z"},
]


def _fake_listing(monkeypatch, events: list[dict], remaining: int | None, odds_response: list[dict]) -> list:
    calls: list = []

    async def fake_events(client: object, api_key: str) -> tuple[list[dict], odds_api.RateLimitState]:
        calls.append("events")
        return events, odds_api.RateLimitState(remaining=remaining)

    async def fake_odds_batch(
        client: object, api_key: str, event_ids: list[int], bookmakers: str
    ) -> tuple[list[dict], odds_api.RateLimitState]:
        calls.append(event_ids)
        return odds_response, odds_api.RateLimitState()

    monkeypatch.setattr(odds_api, "_fetch_events", fake_events)
    monkeypatch.setattr(odds_api, "_fetch_odds_batch", fake_odds_batch)
    return calls


def _capture(tmp_path: Path, **kwargs: object) -> str:
    output = asyncio.run(odds_api.capture_market_inventory(
        tmp_path / "capture.md", bookmakers="DraftKings,FanDuel", api_key="test-key", now=NOW, **kwargs
    ))
    return output.read_text(encoding="utf-8")


def test_window_capture_sends_the_selected_tour_level_ids_soonest_first(monkeypatch, tmp_path: Path) -> None:
    calls = _fake_listing(monkeypatch, LISTING, 60, [])

    _capture(tmp_path, within_hours=6, min_requests_remaining=20)

    assert calls == ["events", [2, 1]]


def test_window_capture_at_the_floor_sends_no_odds_request(monkeypatch, tmp_path: Path) -> None:
    calls = _fake_listing(monkeypatch, LISTING, 20, [])

    report = _capture(tmp_path, within_hours=6, min_requests_remaining=20)

    assert calls == ["events"]
    assert "- Result: Stopped at the quota floor: 20 request(s) remaining, floor 20; no odds request sent." in report


def test_window_capture_with_no_selected_event_sends_no_odds_request(monkeypatch, tmp_path: Path) -> None:
    calls = _fake_listing(monkeypatch, LISTING[2:], 60, [])

    report = _capture(tmp_path, within_hours=6)

    assert calls == ["events"]
    assert "- Result: No active tennis events returned." in report


def test_window_capture_lists_each_books_markets_per_event(monkeypatch, tmp_path: Path) -> None:
    _fake_listing(monkeypatch, LISTING, 60, [
        {"id": 1, "bookmakers": {"DraftKings": [{"name": "ML"}, {"name": "Player Games"}], "FanDuel": [{"name": "ML"}]}},
        {"id": "2", "bookmakers": {}},
    ])

    report = _capture(tmp_path, within_hours=6)

    assert "| DraftKings | ML, Player Games |" in report
    assert report.endswith(
        "## Per event\n\n"
        "- WTA - Riyadh, starts in 30 min: no bookmakers\n"
        "- ATP - Paris, France, starts in 180 min: DraftKings: ML, Player Games; FanDuel: ML\n"
    )


def test_window_capture_marks_an_event_the_odds_response_left_out(monkeypatch, tmp_path: Path) -> None:
    _fake_listing(monkeypatch, LISTING[:1], 60, [{"id": 99, "bookmakers": {"DraftKings": [{"name": "ML"}]}}])

    report = _capture(tmp_path, within_hours=6)

    assert report.endswith("- ATP - Paris, France, starts in 180 min: not returned\n")


def test_capture_without_the_window_keeps_the_first_listed_ids_and_report(monkeypatch, tmp_path: Path) -> None:
    calls = _fake_listing(monkeypatch, LISTING, 60, [{"id": 1, "bookmakers": {"DraftKings": [{"name": "ML"}]}}])

    report = _capture(tmp_path)

    assert calls == ["events", [1, 2, 3, 4, 5]]
    assert "## Per event" not in report
    assert report.endswith("| DraftKings | ML |\n")

import asyncio
import json
from datetime import date
from typing import cast

from app.core.nfl_odds import match_scheduled_game, parse_game_markets
from app.ingest import nfl_odds
from app.repositories import nfl as nfl_repo
from sqlalchemy.ext.asyncio import AsyncSession


class _ScalarResult:
    def scalar_one(self) -> int:
        return 42


class _CapturingSession:
    def __init__(self) -> None:
        self.statement = ""
        self.params: dict[str, object] = {}

    async def execute(self, statement: object, params: dict[str, object]) -> _ScalarResult:
        self.statement = str(statement)
        self.params = params
        return _ScalarResult()


def _markets() -> list[dict[str, object]]:
    return [
        {"key": "h2h", "outcomes": [{"name": "Dallas Cowboys", "price": -130}, {"name": "Chicago Bears", "price": 110}]},
        {"key": "spreads", "outcomes": [{"name": "Dallas Cowboys", "price": -110, "point": -3.5}, {"name": "Chicago Bears", "price": -110, "point": 3.5}]},
        {"key": "totals", "outcomes": [{"name": "Over", "price": -105, "point": 44.5}, {"name": "Under", "price": -115, "point": 44.5}]},
    ]


def test_the_odds_api_request_scope_uses_only_nfl_model_markets() -> None:
    assert nfl_odds.BASE_URL == "https://api.the-odds-api.com/v4"
    assert nfl_odds.DEFAULT_SPORT == "americanfootball_nfl"
    assert nfl_odds._odds_params("test-key") == {"apiKey": "test-key", "regions": "us", "markets": "h2h,spreads,totals", "oddsFormat": "american", "dateFormat": "iso"}


def test_pinnacle_names_the_book_instead_of_a_region() -> None:
    params = nfl_odds._odds_params("test-key", pinnacle=True)

    assert params["bookmakers"] == "pinnacle" and "regions" not in params
    assert params["markets"] == "h2h,spreads,totals"


def test_the_odds_api_key_never_falls_back_to_tennis_key(monkeypatch) -> None:
    monkeypatch.setattr(nfl_odds.settings, "the_odds_api_key", "")
    monkeypatch.setattr(nfl_odds.settings, "odds_api_key", "tennis-only-key")
    try:
        nfl_odds._provider_key()
    except RuntimeError as error:
        assert "THE_ODDS_API_KEY" in str(error)
    else:
        raise AssertionError("NFL ingest must not fall back to ODDS_API_KEY")


def test_match_scheduled_game_requires_both_the_odds_api_teams_and_nearby_date() -> None:
    games = [{"game_id": 7, "game_date": date(2026, 9, 20), "home_team": "DAL", "away_team": "CHI"}]
    event = {"home_team": "Dallas Cowboys", "away_team": "Chicago Bears", "commence_time": "2026-09-20T18:00:00Z"}
    assert match_scheduled_game(event, games) == (7, True)
    assert match_scheduled_game({**event, "commence_time": "2026-09-23T18:00:00Z"}, games) is None
    assert match_scheduled_game({**event, "away_team": "Unknown"}, games) is None


def test_parse_game_markets_orients_home_side_and_devigs_american_prices() -> None:
    rows = parse_game_markets(_markets(), True, "Dallas Cowboys", "Chicago Bears")
    assert [(row.market, row.line, row.first_side, row.second_side) for row in rows] == [("moneyline", None, "home", "away"), ("spread", -3.5, "home", "away"), ("total", 44.5, "over", "under")]
    assert (rows[0].first_odds, rows[0].second_odds) == (-130, 110)
    assert all(abs(row.first_market_prob + row.second_market_prob - 1) < 1e-9 for row in rows)


def test_parse_game_markets_uses_actual_nfl_home_when_provider_event_is_reversed() -> None:
    rows = parse_game_markets(_markets(), False, "Chicago Bears", "Dallas Cowboys")
    assert rows[0].first_odds == -130
    assert rows[1].line == -3.5


def test_parse_game_markets_skips_malformed_or_incomplete_markets() -> None:
    assert parse_game_markets([{"key": "h2h", "outcomes": [{"name": "Dallas Cowboys", "price": -110}]}], True, "Dallas Cowboys", "Chicago Bears") == []


def test_bookmaker_sets_uses_the_odds_api_book_keys() -> None:
    assert nfl_odds._bookmaker_sets({"bookmakers": [{"key": "draftkings", "markets": _markets()}]}) == [("draftkings", _markets())]


def test_remaining_requests_uses_the_odds_api_credit_header() -> None:
    assert nfl_odds._remaining_requests({"x-requests-remaining": "497"}) == 497
    assert nfl_odds._remaining_requests({}) is None


def test_game_odds_snapshot_serializes_raw_market_as_jsonb() -> None:
    session = _CapturingSession()
    inserted_id = asyncio.run(
        nfl_repo.insert_game_odds_snapshot(
            cast(AsyncSession, session), 7, "draftkings", "moneyline", None,
            "home", "away", -130, 110, 0.55, 0.45, {"key": "h2h"}, provider="the_odds_api_us",
        )
    )
    assert inserted_id == 42
    assert session.params["provider"] == "the_odds_api_us"
    assert "CAST(:raw_json AS jsonb)" in session.statement
    assert session.params["raw_json"] == json.dumps({"key": "h2h"})


def test_run_persists_matched_markets_and_honors_quota_floor(monkeypatch) -> None:
    stored: list[tuple[object, ...]] = []

    class Session:
        async def __aenter__(self): return self
        async def __aexit__(self, *args: object): return None
        async def commit(self): return None

    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args: object): return None

    event = {"home_team": "Dallas Cowboys", "away_team": "Chicago Bears", "commence_time": "2026-09-20T18:00:00Z", "bookmakers": [{"key": "draftkings", "markets": _markets()}]}

    async def games(_: object, __: int) -> list[dict[str, object]]:
        return [{"game_id": 7, "game_date": date(2026, 9, 20), "home_team": "DAL", "away_team": "CHI"}]

    async def odds(*_: object) -> tuple[list[dict[str, object]], int | None]: return [event], 497
    providers: list[str] = []

    async def insert(*args: object, provider: str) -> int:
        providers.append(provider)
        stored.append(args)
        return len(stored)

    monkeypatch.setattr(nfl_odds, "SessionLocal", lambda: Session())
    monkeypatch.setattr(nfl_odds.httpx, "AsyncClient", lambda: Client())
    monkeypatch.setattr(nfl_repo, "get_upcoming_games", games)
    monkeypatch.setattr(nfl_odds, "_fetch_odds", odds)
    monkeypatch.setattr(nfl_repo, "insert_game_odds_snapshot", insert)
    monkeypatch.setattr(nfl_odds.settings, "the_odds_api_key", "test-key")
    assert asyncio.run(nfl_odds.run()) == {"matched": 1, "skipped": 0, "stored": 3}
    assert len(stored) == 3 and set(providers) == {"the_odds_api_us"}
    asyncio.run(nfl_odds.run(pinnacle=True))
    assert providers[3:] == ["the_odds_api_eu"] * 3

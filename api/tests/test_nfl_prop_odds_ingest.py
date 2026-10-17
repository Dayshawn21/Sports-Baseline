import asyncio
from datetime import date, datetime, timezone

import httpx

from app.core.nfl_resolution import PlayerCandidate, Resolution, index_candidates
from app.ingest import nfl_prop_odds
from app.ingest.nfl_prop_odds import can_afford, resolve_book_player, select_events
from app.repositories import nfl as nfl_repo
from app.repositories import sport_props

NOW = datetime(2026, 9, 18, 20, 0, tzinfo=timezone.utc)
GAMES = [
    {"game_id": 1, "game_date": date(2026, 9, 20), "home_team": "ATL", "away_team": "CAR"},
    {"game_id": 2, "game_date": date(2026, 9, 21), "home_team": "LA", "away_team": "NYG"},
]


def _event(event_id: str, home: str, away: str, kickoff: str) -> dict[str, object]:
    return {"id": event_id, "home_team": home, "away_team": away, "commence_time": kickoff}


def test_select_events_keeps_matched_future_games_inside_the_window_soonest_first() -> None:
    events = [
        _event("late", "Los Angeles Rams", "New York Giants", "2026-09-21T00:15:00Z"),
        _event("soon", "Atlanta Falcons", "Carolina Panthers", "2026-09-20T17:00:00Z"),
        _event("started", "Buffalo Bills", "Detroit Lions", "2026-09-18T00:15:00Z"),
        _event("unscheduled", "Dallas Cowboys", "Washington Commanders", "2026-09-20T20:25:00Z"),
        _event("bad-time", "Atlanta Falcons", "Carolina Panthers", "soon"),
    ]

    assert [(event["id"], game_id) for event, game_id in select_events(events, GAMES, NOW, 96)] == [("soon", 1), ("late", 2)]
    assert select_events(events, GAMES, NOW, 36) == []


def test_can_afford_respects_the_floor_and_treats_an_unknown_balance_as_empty() -> None:
    assert can_afford(51, 1, 50) is True
    assert can_afford(50, 1, 50) is False
    assert can_afford(None, 1, 0) is False


def test_book_player_uses_a_team_only_to_break_a_same_name_tie() -> None:
    index = index_candidates([
        PlayerCandidate(10, "Bijan Robinson", "ATL", "RB"),
        PlayerCandidate(20, "Josh Allen", "BUF", "QB"),
        PlayerCandidate(21, "Josh Allen", "JAX", "LB"),
    ])

    assert resolve_book_player("Bijan Robinson", ("ATL", "CAR"), index, {}).player_id == 10
    assert resolve_book_player("Josh Allen", ("BUF", "DET"), index, {}).player_id == 20
    unresolved = resolve_book_player("Josh Allen", ("ATL", "CAR"), index, {})
    assert (unresolved.player_id, unresolved.reason) == (None, Resolution.AMBIGUOUS)


class _Session:
    async def __aenter__(self): return self
    async def __aexit__(self, *args: object): return None
    async def commit(self): return None


class _Client:
    async def __aenter__(self): return self
    async def __aexit__(self, *args: object): return None


def _patch_run(monkeypatch, remaining_after_events: int, odds_calls: list[str], fail: bool = False) -> list[tuple]:
    inserted: list[tuple] = []
    events = [
        _event("e1", "Atlanta Falcons", "Carolina Panthers", "2026-09-20T17:00:00Z"),
        _event("e2", "Los Angeles Rams", "New York Giants", "2026-09-21T00:15:00Z"),
    ]
    balance = {"remaining": remaining_after_events}

    async def get(_client: object, path: str, _params: dict[str, str]):
        if path == "/events":
            return events, balance["remaining"]
        odds_calls.append(path)
        if fail:
            raise httpx.ConnectError("boom")
        balance["remaining"] -= 1
        return {"bookmakers": [{"key": "draftkings", "markets": [{"key": "player_anytime_td", "outcomes": [
            {"name": "Yes", "description": "Bijan Robinson", "price": -195},
        ]}]}]}, balance["remaining"]

    async def games(*_: object): return GAMES
    async def candidates(*_: object): return [(10, "Bijan Robinson", "ATL", "RB")]
    async def aliases(*_: object): return {}
    async def insert(*args: object): inserted.append(args)

    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None): return NOW

    monkeypatch.setattr(nfl_prop_odds, "SessionLocal", lambda: _Session())
    monkeypatch.setattr(nfl_prop_odds.httpx, "AsyncClient", lambda: _Client())
    monkeypatch.setattr(nfl_prop_odds, "_get", get)
    monkeypatch.setattr(nfl_prop_odds, "datetime", _FixedDatetime)
    monkeypatch.setattr(nfl_prop_odds.settings, "the_odds_api_key", "test-key")
    monkeypatch.setattr(nfl_repo, "get_upcoming_games", games)
    monkeypatch.setattr(nfl_repo, "get_player_candidates", candidates)
    monkeypatch.setattr(sport_props, "get_player_aliases", aliases)
    monkeypatch.setattr(nfl_repo, "insert_player_prop_odds_snapshot", insert)
    return inserted


def test_run_spends_nothing_without_confirm_spend(monkeypatch) -> None:
    odds_calls: list[str] = []
    inserted = _patch_run(monkeypatch, 490, odds_calls)

    assert asyncio.run(nfl_prop_odds.run()) == {}
    assert odds_calls == [] and inserted == []


def test_run_stops_at_the_credit_floor(monkeypatch) -> None:
    odds_calls: list[str] = []
    inserted = _patch_run(monkeypatch, 51, odds_calls)

    counts = asyncio.run(nfl_prop_odds.run(min_credits=50, confirm_spend=True))

    assert odds_calls == ["/events/e1/odds"]
    assert counts["events"] == 1 and counts["stopped_at_floor"] == 1
    assert [(args[1], args[2], args[5], args[8]) for args in inserted] == [(1, 10, "anytime_touchdown", -195)]


def test_run_never_retries_a_failed_paid_request(monkeypatch) -> None:
    odds_calls: list[str] = []
    inserted = _patch_run(monkeypatch, 490, odds_calls, fail=True)

    counts = asyncio.run(nfl_prop_odds.run(confirm_spend=True))

    assert odds_calls == ["/events/e1/odds", "/events/e2/odds"]
    assert counts["failed"] == 2 and inserted == []

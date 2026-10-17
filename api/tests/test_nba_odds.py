import asyncio
import datetime as dt
import json
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nba_odds import _TEAM_CODES, match_nba_game, odds_api_team_code
from app.core.nba_season import NBA_TEAM_CODES
from app.ingest import nba_odds
from app.repositories import nba as nba_repo

UTC = dt.timezone.utc
TIP = dt.datetime(2026, 10, 20, 19, 10, tzinfo=UTC)


def _event(home: str = "Detroit Pistons", away: str = "Boston Celtics", commence: str = "2026-10-20T19:00:00Z") -> dict[str, object]:
    return {"home_team": home, "away_team": away, "commence_time": commence}


def _game(game_id: int = 7, home: str = "DET", away: str = "BOS", start: dt.datetime | None = TIP) -> dict[str, object]:
    return {"game_id": game_id, "start_utc": start, "home_team": home, "away_team": away}


def test_team_map_covers_exactly_the_espn_codes() -> None:
    assert len(_TEAM_CODES) == 30
    assert set(_TEAM_CODES.values()) == NBA_TEAM_CODES


def test_team_code_normalizes_case_and_spacing_and_never_guesses() -> None:
    assert odds_api_team_code("  Los Angeles  CLIPPERS ") == "LAC"
    assert odds_api_team_code("Utah Jazz") == "UTAH"
    assert odds_api_team_code("LA Clippers") is None
    assert odds_api_team_code(None) is None


def test_matches_one_game_a_few_minutes_off_the_stored_tip() -> None:
    assert match_nba_game(_event(), [_game()]) == (7, True)


def test_reversed_provider_home_is_reported() -> None:
    assert match_nba_game(_event("Boston Celtics", "Detroit Pistons"), [_game()]) == (7, False)


def test_game_outside_the_window_does_not_match() -> None:
    assert match_nba_game(_event(commence="2026-10-21T02:11:00Z"), [_game()]) is None


def test_same_teams_on_consecutive_nights_each_match_their_own_game() -> None:
    games = [_game(7), _game(8, start=TIP + dt.timedelta(days=1))]
    assert match_nba_game(_event(), games) == (7, True)
    assert match_nba_game(_event(commence="2026-10-21T19:00:00Z"), games) == (8, True)


def test_two_candidates_inside_the_window_give_none() -> None:
    games = [_game(7), _game(8, start=TIP + dt.timedelta(hours=2))]
    assert match_nba_game(_event(), games) is None


def test_unknown_team_missing_start_and_bad_timestamp_give_none() -> None:
    assert match_nba_game(_event(home="Seattle SuperSonics"), [_game()]) is None
    assert match_nba_game(_event(), [_game(start=None)]) is None
    assert match_nba_game(_event(commence="not-a-time"), [_game()]) is None
    assert match_nba_game(_event(commence="2026-10-20T19:00:00"), [_game()]) is None


class _Result:
    def scalar_one(self) -> int:
        return 42

    def fetchall(self) -> list[tuple[object, ...]]:
        return [(7, TIP, "DET", "BOS")]


class _CapturingSession:
    def __init__(self) -> None:
        self.statement = ""
        self.params: dict[str, object] = {}

    async def __aenter__(self) -> "_CapturingSession":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def execute(self, statement: object, params: dict[str, object]) -> _Result:
        self.statement = str(statement)
        self.params = params
        return _Result()


class _Client:
    async def __aenter__(self) -> "_Client":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None


def test_request_scope_is_nba_game_markets_only() -> None:
    assert nba_odds.SPORT_KEY == "basketball_nba"
    assert nba_odds._odds_params("k")["markets"] == "h2h,spreads,totals"
    assert nba_odds._odds_params("k")["regions"] == "us"


def test_credit_gate_never_spends_on_unknown_or_low_balance() -> None:
    assert nba_odds.credit_gate(None, 100) is False
    assert nba_odds.credit_gate(99, 100) is False
    assert nba_odds.credit_gate(100, 100) is True


def test_queries_carry_the_nba_literal_and_skip_preseason() -> None:
    session = _CapturingSession()
    games = asyncio.run(nba_repo.get_upcoming_odds_games(cast(AsyncSession, session), 2))
    assert games == [{"game_id": 7, "start_utc": TIP, "home_team": "DET", "away_team": "BOS"}]
    assert "g.sport = 'nba'" in session.statement and "'PRE'" not in session.statement
    assert asyncio.run(nba_repo.insert_game_odds_snapshot(cast(AsyncSession, session), 7, "draftkings", "moneyline", None, "home", "away", -130, 110, 0.55, 0.45, {"key": "h2h"}, provider="the_odds_api_us")) == 42
    assert session.params["provider"] == "the_odds_api_us"
    assert "'nba', :game_id" in session.statement
    assert session.params["raw_json"] == json.dumps({"key": "h2h"})


def _patch_run(monkeypatch, games: list[dict[str, object]], remaining: int | None) -> list[str]:
    calls: list[str] = []

    async def upcoming(*_: object) -> list[dict[str, object]]:
        return games

    async def free(*_: object) -> int | None:
        calls.append("sports")
        return remaining

    async def paid(*_: object) -> tuple[list[dict[str, object]], int | None]:
        calls.append("odds")
        return [], remaining

    monkeypatch.setattr(nba_odds, "SessionLocal", _CapturingSession)
    monkeypatch.setattr(nba_odds.httpx, "AsyncClient", _Client)
    monkeypatch.setattr(nba_odds.nba_repo, "get_upcoming_odds_games", upcoming)
    monkeypatch.setattr(nba_odds, "_provider_key", lambda: "k")
    monkeypatch.setattr(nba_odds, "_free_remaining", free)
    monkeypatch.setattr(nba_odds, "_fetch_odds", paid)
    return calls


def test_run_makes_no_provider_call_without_games(monkeypatch) -> None:
    calls = _patch_run(monkeypatch, [], 400)
    asyncio.run(nba_odds.run())
    assert calls == []


def test_run_skips_the_paid_call_below_the_floor(monkeypatch) -> None:
    calls = _patch_run(monkeypatch, [_game()], 99)
    asyncio.run(nba_odds.run())
    assert calls == ["sports"]

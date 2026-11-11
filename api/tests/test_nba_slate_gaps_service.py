import asyncio
import datetime as dt
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.core.nba_line_only import LINE_ONLY_COLUMNS
from app.core.nba_projection_backtest import NbaHistoryRow
from app.services.nba.props import props_response
from app.services.nba import slate_gaps
from app.services.nba.slate_gaps import _not_tipped, build_slate_gaps, slate_gaps_response
from app.services.serial_build_cache import SerialBuildCache

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 10, 20, 18, 0, tzinfo=UTC)
DATE = dt.date(2026, 10, 20)
FETCHED = dt.datetime(2026, 10, 20, 15, 0, tzinfo=UTC)


def _game(game_id: int, hours: float = 5, status: str = "scheduled") -> dict[str, object]:
    return {"game_id": game_id, "start_utc": NOW + dt.timedelta(hours=hours), "status": status,
            "away_team": "BOS", "home_team": "NY"}


def _line(player_id: int, name: str, market: str, line: float, odds_type: str = "standard") -> dict[str, object]:
    return {"player_id": player_id, "player_name": name, "position": "G", "team": "NYK", "market": market,
            "odds_type": odds_type, "line": line, "fetched_at": FETCHED}


def _prior(player_id: int, points: int, assists: int = 5) -> list[NbaHistoryRow]:
    values: dict[str, int | bool | None] = {column: 1 for column in LINE_ONLY_COLUMNS}
    values.update({"points": points, "rebounds": 6, "assists": assists, "did_not_play": False})
    return [
        NbaHistoryRow(player_id=player_id, game_id=day, season=2025, game_date=dt.date(2025, 10, 21) + dt.timedelta(days=day),
                      game_type="REG", did_not_play=False, minutes=32.0, stats=values)
        for day in range(20)
    ]


LINES = {
    1: [_line(1, "Amy", "points", 18.5), _line(1, "Amy", "assists", 3.5), _line(2, "Bea", "points", 25.5, "goblin")],
    2: [_line(3, "Cat", "points", 9.5), _line(4, "Dee", "points", 30.5)],
}
PRIOR = {1: _prior(1, 20, assists=6), 2: _prior(2, 30), 3: _prior(3, 12), 4: _prior(4, 26)}


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture(autouse=True)
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    clock = Clock()
    cache = SerialBuildCache(slate_gaps.CACHE_TTL_SECONDS, slate_gaps.FAILURE_TTL_SECONDS, slate_gaps.MAX_ENTRIES, clock)
    monkeypatch.setattr(slate_gaps, "_DATES", cache)
    return clock


def _stub_repo(monkeypatch: pytest.MonkeyPatch, games: list[dict[str, object]]) -> AsyncMock:
    """Stubs the gap reads; returns the date line read so a test can count builds."""
    date_lines = AsyncMock(return_value=LINES)
    monkeypatch.setattr(slate_gaps.nba_repo, "get_games_on", AsyncMock(return_value=games))
    monkeypatch.setattr(slate_gaps.nba_repo, "get_date_modelled_lines", date_lines)
    monkeypatch.setattr(slate_gaps.nba_repo, "get_prior_games", AsyncMock(return_value=PRIOR))
    return date_lines


def test_each_item_matches_the_game_page_props_line() -> None:
    response = slate_gaps_response(DATE, [_game(1), _game(2)], LINES, PRIOR, NOW)
    assert response.items
    for item in response.items:
        page = props_response(item.game_id, LINES[item.game_id], PRIOR, []).lines
        served = next(line for line in page if line.player_id == item.player_id and line.market == item.market)
        assert (item.line, item.projection, item.gap) == (served.line, served.projection, served.gap)


def test_items_rank_by_gap_share_one_per_player_and_skip_goblins() -> None:
    response = slate_gaps_response(DATE, [_game(1), _game(2)], LINES, PRIOR, NOW)
    assert [(item.player_name, item.market) for item in response.items] == [
        ("Amy", "assists"), ("Cat", "points"), ("Dee", "points")]
    assert response.items[0].gap_share == 2.5 / 3.5
    assert (response.items[0].away_team, response.items[0].home_team) == ("BOS", "NY")
    assert response.items[0].start_utc == NOW + dt.timedelta(hours=5)
    assert response.model_version == "nba-reference-v1"


def test_a_tipped_or_unscheduled_game_contributes_nothing() -> None:
    response = slate_gaps_response(DATE, [_game(1, hours=-1), _game(2, status="postponed")], LINES, PRIOR, NOW)
    assert response.items == []
    assert not _not_tipped(_game(1, hours=-1), NOW)
    assert not _not_tipped({**_game(1), "start_utc": None}, NOW)
    assert _not_tipped(_game(1), NOW)


def test_no_games_gives_an_empty_digest_in_camel_case() -> None:
    payload = slate_gaps_response(DATE, [], {}, {}, NOW).model_dump(by_alias=True, mode="json")
    assert payload == {"date": "2026-10-20", "modelVersion": "nba-reference-v1", "items": []}


def test_a_market_filter_runs_before_one_per_player() -> None:
    """Amy's largest gap is in assists; she must still rank in a points-only digest."""
    response = slate_gaps_response(DATE, [_game(1), _game(2)], LINES, PRIOR, NOW, market="points")
    assert [(item.player_name, item.market) for item in response.items] == [
        ("Cat", "points"), ("Dee", "points"), ("Amy", "points")]


def test_defaults_are_the_page_digest_and_a_limit_widens_it() -> None:
    default = slate_gaps_response(DATE, [_game(1), _game(2)], LINES, PRIOR, NOW)
    explicit = slate_gaps_response(DATE, [_game(1), _game(2)], LINES, PRIOR, NOW, None, 4)
    assert default == explicit
    assert len(slate_gaps_response(DATE, [_game(1), _game(2)], LINES, PRIOR, NOW, limit=2).items) == 2


def test_the_build_reads_the_whole_date_once_and_matches_per_game_lines(monkeypatch) -> None:
    date_lines = AsyncMock(return_value={**LINES, 3: [_line(5, "Eve", "points", 20.5)]})
    per_game = AsyncMock(side_effect=AssertionError("one read per game"))
    monkeypatch.setattr(slate_gaps.nba_repo, "get_games_on", AsyncMock(return_value=[_game(1), _game(2), _game(3, hours=-1)]))
    monkeypatch.setattr(slate_gaps.nba_repo, "get_date_modelled_lines", date_lines)
    monkeypatch.setattr(slate_gaps.nba_repo, "get_modelled_lines", per_game)
    prior = AsyncMock(return_value=PRIOR)
    monkeypatch.setattr(slate_gaps.nba_repo, "get_prior_games", prior)

    response = asyncio.run(build_slate_gaps(None, DATE, NOW))

    date_lines.assert_awaited_once_with(None, DATE)
    assert prior.await_args.args[1] == [1, 2, 3, 4]
    assert response == slate_gaps_response(DATE, [_game(1), _game(2)], LINES, PRIOR, NOW)


def test_a_date_with_no_open_games_skips_the_line_read(monkeypatch) -> None:
    date_lines = AsyncMock(return_value={})
    monkeypatch.setattr(slate_gaps.nba_repo, "get_games_on", AsyncMock(return_value=[_game(1, hours=-1)]))
    monkeypatch.setattr(slate_gaps.nba_repo, "get_date_modelled_lines", date_lines)

    assert asyncio.run(build_slate_gaps(None, DATE, NOW)).items == []
    date_lines.assert_not_awaited()


def test_a_repeat_within_the_ttl_reuses_the_build_and_an_expired_one_rebuilds(monkeypatch, clock) -> None:
    date_lines = _stub_repo(monkeypatch, [_game(1), _game(2)])

    first = asyncio.run(build_slate_gaps(None, DATE, NOW))
    clock.now = slate_gaps.CACHE_TTL_SECONDS - 1
    assert asyncio.run(build_slate_gaps(None, DATE, NOW)) == first
    assert date_lines.await_count == 1

    clock.now = slate_gaps.CACHE_TTL_SECONDS + 1
    asyncio.run(build_slate_gaps(None, DATE, NOW))
    assert date_lines.await_count == 2


def test_a_game_that_tips_after_the_build_drops_out_of_the_cached_digest(monkeypatch) -> None:
    date_lines = _stub_repo(monkeypatch, [_game(1, hours=1), _game(2, hours=5)])
    before = asyncio.run(build_slate_gaps(None, DATE, NOW))
    assert {item.game_id for item in before.items} == {1, 2}

    later = asyncio.run(build_slate_gaps(None, DATE, NOW + dt.timedelta(hours=2)))

    assert date_lines.await_count == 1
    assert {item.game_id for item in later.items} == {2}


def test_market_and_limit_apply_to_a_cached_date(monkeypatch) -> None:
    date_lines = _stub_repo(monkeypatch, [_game(1), _game(2)])
    asyncio.run(build_slate_gaps(None, DATE, NOW))

    points = asyncio.run(build_slate_gaps(None, DATE, NOW, market="points"))
    two = asyncio.run(build_slate_gaps(None, DATE, NOW, limit=2))

    assert date_lines.await_count == 1
    assert points == slate_gaps_response(DATE, [_game(1), _game(2)], LINES, PRIOR, NOW, market="points")
    assert len(two.items) == 2


def test_a_failed_build_is_a_503(monkeypatch) -> None:
    monkeypatch.setattr(slate_gaps.nba_repo, "get_games_on", AsyncMock(side_effect=RuntimeError("db down")))

    with pytest.raises(HTTPException) as raised:
        asyncio.run(build_slate_gaps(None, DATE, NOW))
    assert raised.value.status_code == 503

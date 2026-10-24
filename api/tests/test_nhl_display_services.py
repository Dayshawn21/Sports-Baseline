import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import cast
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.slate_dates import adjacent_dates, slate_date
from app.nhl.markets import NhlLineOnlyMarket
from app.repositories import nhl
from app.services.nhl.game_detail import build_game_detail, game_detail
from app.services.nhl.line_only_props import build_line_only_props, line_only_props
from app.services.nhl.slate import assemble_games, build_slate, slate_games

DAY = date(2026, 10, 23)
FETCH = datetime(2026, 10, 23, 12, tzinfo=UTC)


def _game(game_id: int = 1) -> dict[str, object]:
    return {
        "game_id": game_id, "season": 2026, "week": 2, "game_type": "REG", "game_date": DAY,
        "start_utc": FETCH + timedelta(hours=8), "status": "scheduled", "away_team": "TBL",
        "home_team": "CHI", "away_team_name": "Tampa Bay Lightning", "home_team_name": "Chicago Blackhawks",
        "away_score": None, "home_score": None, "end_period": None,
    }


def _market(market: str = "moneyline", **overrides: object) -> dict[str, object]:
    return {
        "game_id": 1, "market": market, "book": "draftkings", "line": None,
        "first_side": "home", "first_odds": -120, "second_odds": 110,
        "first_market_prob": Decimal("0.53"), "fetched_at": FETCH, **overrides,
    }


def _line(**overrides: object) -> dict[str, object]:
    return {
        "provider": "prizepicks", "provider_prop_id": "offer-a", "player_id": 7,
        "player_name": "Player A", "position": "C", "team": "TB", "market": "time_on_ice",
        "odds_type": "standard", "line": Decimal("20.5"), "fetched_at": FETCH, **overrides,
    }


@pytest.mark.parametrize(("requested", "today", "dates", "expected"), [
    (DAY, DAY, [], DAY), (None, DAY, [], DAY),
    (None, DAY, [DAY], DAY), (None, DAY, [DAY + timedelta(days=2)], DAY + timedelta(days=2)),
    (None, DAY, [DAY - timedelta(days=2)], DAY - timedelta(days=2)),
    (DAY, DAY, [DAY - timedelta(days=2), DAY + timedelta(days=2)], DAY),
])
def test_shared_date_selection(requested: date | None, today: date, dates: list[date], expected: date) -> None:
    assert slate_date(requested, today, dates) == expected


def test_shared_adjacent_dates_have_strict_boundaries() -> None:
    earlier, later = DAY - timedelta(days=2), DAY + timedelta(days=2)
    assert adjacent_dates(DAY, []) == (None, None)
    assert adjacent_dates(DAY, [earlier, DAY, later]) == (earlier, later)
    assert adjacent_dates(earlier, [earlier, later]) == (None, later)
    assert adjacent_dates(later, [earlier, later]) == (earlier, None)


@pytest.mark.parametrize("first", ["home", "away"])
def test_prices_and_probabilities_orient_to_home(first: str) -> None:
    row = _market(first_side=first)
    game = slate_games([_game()], [row], [], {})[0]
    assert game.moneyline is not None
    expected = (-120, 110, 0.53) if first == "home" else (110, -120, 0.47)
    assert (game.moneyline.home_odds, game.moneyline.away_odds) == expected[:2]
    assert game.moneyline.home_win_probability == pytest.approx(expected[2])
    assert game.moneyline.book == "draftkings" and game.moneyline.fetched_at == FETCH


@pytest.mark.parametrize(("first", "line", "expected"), [("home", -1.5, -1.5), ("away", 1.5, -1.5)])
def test_puck_line_uses_signed_home_handicap(first: str, line: float, expected: float) -> None:
    game = slate_games([_game()], [_market("spread", first_side=first, line=Decimal(str(line)))], [], {})[0]
    assert game.spread.home_line == expected
    assert game.spread.home_odds == (-120 if first == "home" else 110)


@pytest.mark.parametrize("first", ["over", "under"])
def test_total_orients_over_under_without_negating_goals(first: str) -> None:
    game = slate_games([_game()], [_market("total", first_side=first, line=Decimal("6.5"))], [], {})[0]
    assert game.total.line == 6.5
    assert (game.total.over_odds, game.total.under_odds) == ((-120, 110) if first == "over" else (110, -120))


def test_batch_assembly_keeps_input_order_and_attaches_only_each_games_data() -> None:
    move = {"game_id": 1, "market": "spread", "book": "bet365", "open_line": -1.5, "current_line": 1.5,
            "open_fetched_at": FETCH, "current_fetched_at": FETCH + timedelta(hours=1)}
    games = slate_games([_game(2), _game(1)], [_market()], [move], {1: 3})
    assert [g.game_id for g in games] == [2, 1]
    assert (games[0].moneyline, games[0].spread, games[0].total) == (None, None, None)
    assert (games[0].line_movement, games[0].prop_line_count) == ([], 0)
    assert games[1].moneyline is not None and games[1].prop_line_count == 3
    assert games[1].line_movement[0].current_fetched_at == FETCH + timedelta(hours=1)
    assert games[1].line_movement[0].book == "bet365"


@pytest.mark.parametrize("market", ["spread", "total"])
def test_missing_line_does_not_fabricate_a_market(market: str) -> None:
    game = slate_games([_game()], [_market(market)], [], {})[0]
    assert game.spread is None and game.total is None


def test_detail_preserves_slate_fields_and_reduces_only_consecutive_repeats() -> None:
    game = slate_games([_game()], [_market()], [], {1: 2})[0]
    rows = [{"market": "spread", "book": "draftkings", "line": line, "fetched_at": FETCH + timedelta(hours=i)}
            for i, line in enumerate([-1.5, -1.5, 1.5, -1.5])]
    rows.append({"market": "total", "book": "bet365", "line": 6.5, "fetched_at": FETCH})
    detail = game_detail(game, rows)
    assert detail.model_dump(exclude={"line_history"}) == game.model_dump()
    spread, total = detail.line_history
    assert [s.line for s in spread.steps] == [-1.5, 1.5, -1.5]
    assert [s.fetched_at for s in spread.steps] == [FETCH, FETCH + timedelta(hours=2), FETCH + timedelta(hours=3)]
    assert len(total.steps) == 1 and total.book == "bet365"
    assert game_detail(game, []).line_history == []


@pytest.mark.parametrize(("team", "expected"), [(" tb ", "TBL"), ("CHI", "CHI"), (None, None),
                                                 ("???", None), ("BOS", None), ("", None)])
def test_provider_team_is_normalized_or_left_unknown(team: str | None, expected: str | None) -> None:
    result = line_only_props(_game(), [_line(team=team)])
    assert result.lines[0].team == expected


def test_all_markets_sort_by_enum_order_and_keep_negative_zero_and_minutes() -> None:
    rows = [_line(market=m.value, line=Decimal("-0.5") if m == NhlLineOnlyMarket.PLUS_MINUS else 0)
            for m in reversed(list(NhlLineOnlyMarket))]
    result = line_only_props(_game(), rows)
    assert [line.market for line in result.lines] == list(NhlLineOnlyMarket)
    assert result.lines[6].line == -0.5
    assert result.lines[9].line == 0
    assert line_only_props(_game(), [_line()]).lines[0].line == 20.5
    assert line_only_props(_game(), []).lines == []


def test_offer_sort_keeps_duplicate_prices_and_all_provider_offerings() -> None:
    rows = [
        _line(provider_prop_id="z"), _line(provider_prop_id="b"),
        _line(provider_prop_id="d", odds_type="demon"),
        _line(provider_prop_id="c", player_id=8),
        _line(provider_prop_id="a", player_name="Aaron"),
        _line(provider_prop_id="f", line=19.5),
    ]
    result = line_only_props(_game(), rows)
    assert [line.provider_prop_id for line in result.lines] == ["a", "d", "f", "b", "z", "c"]


def _mock_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, result in {
        "get_game_dates": [DAY], "get_games_on": [_game()], "get_game": _game(),
        "get_latest_market_rows": [_market()], "get_line_movement": [], "get_prop_line_counts": {1: 1},
        "get_game_line_history": [], "get_line_only_lines": [_line()],
    }.items():
        monkeypatch.setattr(nhl, name, AsyncMock(return_value=result))


def test_builders_share_assembly_batch_reads_and_propagate_requested_dates(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_repository(monkeypatch)
    db = cast(AsyncSession, object())
    slate = asyncio.run(build_slate(db, DAY, DAY))
    detail = asyncio.run(build_game_detail(db, 1))
    props = asyncio.run(build_line_only_props(db, 1))
    assert detail.model_dump(exclude={"line_history"}) == slate.games[0].model_dump()
    assert slate.games[0].prop_line_count == len(props.lines) == 1
    nhl.get_games_on.assert_awaited_once_with(db, DAY)
    assert all(call.args == (db, [1]) for call in nhl.get_latest_market_rows.await_args_list)


def test_empty_slate_skips_all_market_and_count_reads(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_repository(monkeypatch)
    nhl.get_games_on.return_value = []
    db = cast(AsyncSession, object())
    assert asyncio.run(build_slate(db, DAY, DAY)).games == []
    assert asyncio.run(assemble_games(db, [])) == []
    nhl.get_latest_market_rows.assert_not_awaited()
    nhl.get_prop_line_counts.assert_not_awaited()
    nhl.get_line_movement.assert_not_awaited()


def test_multiple_games_use_one_read_per_market_movement_and_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_repository(monkeypatch)
    db = cast(AsyncSession, object())
    games = asyncio.run(assemble_games(db, [_game(1), _game(2)]))
    assert [game.game_id for game in games] == [1, 2]
    nhl.get_latest_market_rows.assert_awaited_once_with(db, [1, 2])
    nhl.get_line_movement.assert_awaited_once_with(db, [1, 2])
    nhl.get_prop_line_counts.assert_awaited_once_with(db, [1, 2])


def test_missing_game_short_circuits_detail_and_props(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_repository(monkeypatch)
    nhl.get_game.return_value = None
    db = cast(AsyncSession, object())
    assert asyncio.run(build_game_detail(db, 999)) is None
    assert asyncio.run(build_line_only_props(db, 999)) is None
    nhl.get_latest_market_rows.assert_not_awaited()
    nhl.get_game_line_history.assert_not_awaited()
    nhl.get_line_only_lines.assert_not_awaited()


def test_database_failure_is_not_reported_as_an_empty_slate(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_repository(monkeypatch)
    nhl.get_games_on.side_effect = RuntimeError("database unavailable")
    with pytest.raises(RuntimeError, match="database unavailable"):
        asyncio.run(build_slate(cast(AsyncSession, object()), DAY, DAY))

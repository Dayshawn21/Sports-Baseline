"""Keep independent prop models out of v4's inputs and forward sample."""
from __future__ import annotations

import asyncio
import re
import sqlite3
from collections.abc import Awaitable, Callable
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.backtest.nfl_game_environment_fit import FIT_MARKETS
from app.backtest.nfl_projections import ENVIRONMENT_ARM_MARKETS
from app.core.nfl_projection_backtest import REPLAY_MARKETS_BY_POSITION
from app.nfl.markets import NFL_V4_PROP_MARKETS, NflLineOnlyMarket
from app.repositories import nfl
from tests.test_nfl_repository import _RecordingSession

V4_MARKETS = {
    "passing_yards", "passing_attempts", "passing_completions", "rushing_yards",
    "rushing_attempts", "receiving_yards", "receptions", "anytime_touchdown", "fantasy_points",
}


def test_v4_membership_and_replay_fit_inputs_stay_at_the_original_markets() -> None:
    assert NFL_V4_PROP_MARKETS == V4_MARKETS
    assert set(FIT_MARKETS) == ENVIRONMENT_ARM_MARKETS == V4_MARKETS - {"anytime_touchdown"}
    assert [market.value for market in FIT_MARKETS] == [
        "passing_yards", "passing_attempts", "passing_completions", "rushing_yards",
        "rushing_attempts", "receiving_yards", "receptions", "fantasy_points",
    ]
    assert {market for markets in REPLAY_MARKETS_BY_POSITION.values() for market in markets} <= V4_MARKETS


@pytest.mark.parametrize("loader", [
    nfl.get_slate_lines, nfl.get_unmatched_slate_lines, nfl.get_gradeable_prop_lines,
    nfl.get_frozen_gradeable_lines, nfl.get_frozen_coverage,
])
def test_legacy_queries_filter_mixed_markets_before_latest_selection(
    loader: Callable[..., Awaitable[object]], monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _RecordingSession()
    # Simulate a wider serving universe without promoting or serving targets yet.
    monkeypatch.setattr(nfl, "MODELLED_MARKET_FILTER", "l.market IN ('receiving_targets', 'passing_yards')")
    db = cast(AsyncSession, session)
    if loader in (nfl.get_slate_lines, nfl.get_unmatched_slate_lines):
        asyncio.run(loader(db, 2026, 7))
    else:
        asyncio.run(loader(db, 2026))

    query = session.statement
    predicate = re.search(r"l\.market IN \([^)]+\)", query)
    assert predicate is not None
    assert query.index("WHERE") < predicate.start() < query.index("ORDER BY l.provider")
    candidates = sorted(V4_MARKETS | {market.value for market in NflLineOnlyMarket} | {"receiving_targets"})
    with sqlite3.connect(":memory:") as connection:
        connection.execute("CREATE TABLE sport_prop_lines (market TEXT)")
        connection.executemany("INSERT INTO sport_prop_lines VALUES (?)", [(market,) for market in candidates])
        selected = connection.execute(f"SELECT l.market FROM sport_prop_lines l WHERE {predicate.group()}").fetchall()
    assert {market for (market,) in selected} == V4_MARKETS


def test_coverage_requires_a_frozen_row_of_the_same_market() -> None:
    session = _RecordingSession()
    asyncio.run(nfl.get_frozen_coverage(cast(AsyncSession, session), 2026))

    assert "l.provider_prop_id, l.market, g.week" in session.statement
    assert "fl.market = latest.market" in session.statement

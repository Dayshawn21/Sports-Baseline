"""Mixed-model NFL serving and freezing preserve v4's existing output."""
from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timedelta
from typing import cast
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.nfl.markets import NFL_V4_PROP_MARKETS, NflLineOnlyMarket, NflPropMarket
from app.repositories.nfl import LINE_ONLY_MARKET_FILTER, MODELLED_MARKET_FILTER, V4_MARKET_FILTER
from app.repositories.nfl_targets import TargetsServingLine, TargetsUnmatchedLine
from app.services.nfl import slate
from app.services.nfl.prop_predictions import freeze_rows
from app.services.nfl.prop_source import NflPropSource
from app.services.prop_predictions import freeze_current_period
from tests.test_nfl_projection_harness import _replay_row
from tests.test_nfl_targets_service import FETCHED, KICKOFF, NOW, _source

DB = cast(AsyncSession, object())


def _game(game_id: int = 50) -> dict[str, object]:
    return {"game_id": game_id, "game_date": KICKOFF.date(), "start_utc": KICKOFF,
            "away_team": "BUF", "home_team": "MIA", "status": "scheduled"}


def _inputs(
    monkeypatch: pytest.MonkeyPatch, games: list[dict[str, object]], v4: list[dict[str, object]],
    targets: list[TargetsServingLine], unmatched: list[TargetsUnmatchedLine] | None = None,
) -> None:
    reads = {
        "get_slate_games": games, "get_slate_lines": v4, "get_slate_player_history": {},
        "get_slate_opponent_position_history": {}, "get_team_game_position_totals": {},
        "get_slate_market_probabilities": {}, "get_slate_matchup_context": {}, "get_slate_weather": {},
        "get_unmatched_slate_lines": [], "get_slate_prop_odds": {}, "get_slate_team_elo": {}, "get_elo_games": [],
        "get_current_week": (2026, 7),
    }
    for name, value in reads.items():
        monkeypatch.setattr(slate.nfl_repo, name, AsyncMock(return_value=value))
    monkeypatch.setattr(slate.targets_repo, "get_targets_serving_lines", AsyncMock(return_value=targets))
    monkeypatch.setattr(slate.targets_repo, "get_unmatched_targets_lines", AsyncMock(return_value=unmatched or []))


def test_promotion_widens_serving_and_removes_only_targets_from_line_only() -> None:
    assert NflPropMarket.RECEIVING_TARGETS.value == "receiving_targets"
    assert len(NflPropMarket) == 10 and len(NFL_V4_PROP_MARKETS) == 9
    assert {market.value for market in NflLineOnlyMarket} == {
        "passing_touchdowns", "interceptions", "rushing_receiving_yards", "passing_rushing_yards",
        "passing_rushing_receiving_touchdowns", "field_goals_made", "kicking_points", "punts",
    }
    assert "'receiving_targets'" in MODELLED_MARKET_FILTER
    assert "receiving_targets" not in V4_MARKET_FILTER and "receiving_targets" not in LINE_ONLY_MARKET_FILTER


def test_mixed_slate_preserves_the_entire_v4_payload_after_removing_targets(monkeypatch: pytest.MonkeyPatch) -> None:
    v4 = [_replay_row(game_id=50, fetched_at=FETCHED)]
    _inputs(monkeypatch, [_game()], v4, [])
    before = asyncio.run(slate.build_slate(DB, 2026, 7, NOW))
    monkeypatch.setattr(slate.targets_repo, "get_targets_serving_lines", AsyncMock(return_value=[_source()]))

    mixed = asyncio.run(slate.build_slate(DB, 2026, 7, NOW))

    assert (mixed.game_count, mixed.line_count, mixed.unmatched_count) == (1, 2, 0)
    target, = [line for line in mixed.games[0].lines if line.market == "receiving_targets"]
    assert (target.projection_model_version, target.projection, target.p_over, target.over_probability_version) == (
        "nfl-targets-v1", 3.25, None, None,
    )
    assert [line.model_dump_json() for line in mixed.games[0].lines if line.market != "receiving_targets"] == [
        line.model_dump_json() for line in before.games[0].lines
    ]
    without_targets = mixed.model_copy(deep=True)
    without_targets.games[0].lines = [line for line in without_targets.games[0].lines if line.market != "receiving_targets"]
    without_targets.line_count -= 1
    assert without_targets.model_dump_json() == before.model_dump_json()


def test_no_targets_and_no_lines_leave_the_existing_empty_slate(monkeypatch: pytest.MonkeyPatch) -> None:
    _inputs(monkeypatch, [], [], [])
    result = asyncio.run(slate.build_slate(DB, 2026, 7, NOW))
    assert result.model_dump(by_alias=True) == {
        "season": 2026, "week": 7, "gameCount": 0, "lineCount": 0, "unmatchedCount": 0, "games": [], "unmatched": [],
    }


def test_unmatched_targets_are_counted_without_projecting_them(monkeypatch: pytest.MonkeyPatch) -> None:
    unmatched = TargetsUnmatchedLine(71, 50, "Unresolved", "MIA", "WR", "receiving_targets",
                                     "full_game", "standard", 5.5, "prizepicks", FETCHED)
    _inputs(monkeypatch, [_game()], [], [], [unmatched])

    result = asyncio.run(slate.build_slate(DB, 2026, 7, NOW))

    assert result.line_count == 0 and result.unmatched_count == 1 and result.games[0].lines == []
    assert result.unmatched[0].model_dump(by_alias=True) == {
        "lineId": 71, "playerName": "Unresolved", "providerTeam": "MIA", "providerPosition": "WR",
        "market": "receiving_targets", "segment": "full_game", "oddsType": "standard", "line": 5.5,
        "provider": "prizepicks", "fetchedAt": FETCHED,
    }


def test_nfl_source_freezes_both_versions_without_changing_its_report_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    _inputs(monkeypatch, [_game()], [_replay_row(game_id=50, fetched_at=FETCHED)], [_source()])
    source = NflPropSource()

    run = asyncio.run(freeze_current_period(DB, source, NOW, dry_run=True))

    assert run is not None and run.inserted is None and run.counts == {"frozen": 2}
    by_market = {row.feature_snapshot["market"]: row for row in run.rows}
    target = by_market["receiving_targets"]
    assert target.model_version == "nfl-targets-v1" and target.over_probability_version is None
    assert target.projection == 3.25 and target.p_over is None and target.p_under is None
    assert by_market["receiving_yards"].model_version == source.model_version == "opponent-dvp-tg-blend-usage-snap-v4"
    assert source.over_probability_version == "nfl-pover-v1"


@pytest.mark.parametrize("start", [NOW, NOW - timedelta(seconds=1), None])
def test_started_and_unknown_start_games_freeze_neither_model(
    monkeypatch: pytest.MonkeyPatch, start: datetime | None,
) -> None:
    _inputs(monkeypatch, [_game() | {"start_utc": start}],
            [_replay_row(game_id=50, fetched_at=FETCHED)], [replace(_source(), start_utc=start)])

    result = asyncio.run(slate.build_slate(DB, 2026, 7, NOW))
    rows, counts = freeze_rows(result, NOW)

    assert rows == [] and counts == {"no_start_time" if start is None else "kicked_off": 2, "frozen": 0}


def test_a_missing_targets_baseline_is_still_frozen_with_nulls(monkeypatch: pytest.MonkeyPatch) -> None:
    _inputs(monkeypatch, [_game()], [], [_source(())])
    run = asyncio.run(freeze_current_period(DB, NflPropSource(), NOW, dry_run=True))

    assert run is not None
    row, = run.rows
    assert (row.model_version, row.projection, row.edge, row.p_over, row.over_probability_version) == (
        "nfl-targets-v1", None, None, None, None,
    )

from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import cast
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nba_injuries import (
    LinkedNbaInjury, NbaInjuryEntry, NbaInjurySnapshot, injury_freshness,
)
from app.core.nba_projection_backtest import NbaHistoryRow
from app.repositories import nba as nba_repo
from app.repositories import nba_injuries as repo
from app.services.nba import game_detail, prop_board, props, line_only_props
from app.services.nba.injuries import injury_index, injury_report, load_injury_reports
from app.services.nba.slate import slate_games

NOW = datetime(2026, 10, 21, 18, tzinfo=timezone.utc)
TIP = NOW + timedelta(hours=2)
FETCHED = NOW - timedelta(hours=1)
DB = cast(AsyncSession, object())


def game(game_id: int = 7, tip: datetime | None = TIP) -> dict[str, object]:
    return {
        "game_id": game_id, "away_team": "NY", "home_team": "BOS", "start_utc": tip,
        "status": "scheduled", "game_date": NOW.date(), "game_type": "REG", "season": 2026,
        "week": 1, "away_team_name": "New York Knicks", "home_team_name": "Boston Celtics",
        "away_score": None, "home_score": None,
    }


def entry(player_id: int | None = 1, team: str = "NY", athlete_team: str = "18") -> LinkedNbaInjury:
    row = NbaInjuryEntry(
        espn_team_id="18" if team == "NY" else "2", team_code=team, espn_athlete_id="123",
        player_name="Injured player", status="Out", detail="Ankle", source_updated_at=FETCHED,
        return_date=None, athlete_team_id=athlete_team,
    )
    return LinkedNbaInjury(row, player_id)


def snapshot(time: datetime = FETCHED) -> NbaInjurySnapshot:
    return NbaInjurySnapshot(time, (entry(),))


def line(market: str = "points", value: float = 20.5, team: str | None = "NYK") -> dict[str, object]:
    return {
        "player_id": 1, "player_name": "Injured player", "position": "G", "team": team,
        "market": market, "odds_type": "standard", "line": value, "fetched_at": FETCHED,
    }


@pytest.mark.parametrize(("fetched", "tip", "as_of", "expected"), [
    (FETCHED, TIP, NOW, "fresh"),
    (NOW - timedelta(hours=6), TIP, NOW, "fresh"),
    (NOW - timedelta(hours=6, microseconds=1), TIP, NOW, "stale"),
    (TIP, TIP, TIP, "unavailable"),
    (TIP + timedelta(seconds=1), TIP, TIP, "unavailable"),
    (NOW + timedelta(seconds=1), TIP, NOW, "unavailable"),
    (NOW, TIP, NOW, "fresh"),
    (None, TIP, NOW, "unavailable"),
    (FETCHED, None, NOW, "unavailable"),
    (FETCHED, TIP, NOW + timedelta(days=20), "fresh"),
    (TIP - timedelta(hours=6, microseconds=1), TIP, NOW + timedelta(days=20), "stale"),
])
def test_snapshot_eligibility_and_freshness_are_pre_tip(
    fetched: datetime | None, tip: datetime | None, as_of: datetime, expected: str,
) -> None:
    assert injury_freshness(fetched, tip, as_of) == expected


def test_naive_context_clock_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        injury_freshness(FETCHED, TIP, NOW.replace(tzinfo=None))


def test_empty_stale_and_unavailable_reports_have_distinct_metadata() -> None:
    empty = injury_report(game(), NbaInjurySnapshot(FETCHED, ()), NOW)
    assert empty.injuries == [] and empty.freshness == "fresh" and empty.fetched_at == FETCHED
    stale = injury_report(game(), NbaInjurySnapshot(NOW - timedelta(days=1), ()), NOW)
    assert stale.injuries == [] and stale.freshness == "stale" and stale.fetched_at is not None
    unavailable = injury_report(game(), None, NOW)
    assert unavailable.injuries == [] and unavailable.freshness == "unavailable" and unavailable.fetched_at is None
    assert injury_report(game(tip=None), snapshot(), NOW) == unavailable


def test_reports_retain_unlinked_and_mismatched_players_but_prop_index_does_not() -> None:
    rows = (entry(), entry(None, "BOS", "2"), entry(2, "BOS", "28"), entry(3, "LAC", "12"))
    report = injury_report(game(), NbaInjurySnapshot(FETCHED, rows), NOW)
    assert [(row.player_id, row.team, row.athlete_team) for row in report.injuries] == [
        (1, "NY", "NY"), (None, "BOS", "BOS"), (2, "BOS", "TOR"),
    ]
    assert list(injury_index(report)) == [(1, "NY")]
    assert report.model_dump(by_alias=True)["injuries"][1]["playerId"] is None


@pytest.mark.parametrize("team", ["BOS", None, "LAC"])
def test_same_player_with_wrong_or_missing_prop_team_gets_no_injury_tag(team: str | None) -> None:
    report = injury_report(game(), snapshot(), NOW)
    response = props.props_response(7, [line(team=team)], {}, [], report)
    assert response.lines[0].injury is None


def test_board_game_and_both_prop_kinds_share_context_without_changing_old_values() -> None:
    report = injury_report(game(), snapshot(), NOW)
    modelled = [line(), line(value=25.5), line("assists", 4.5)]
    plain = [line("double_double", 0.5)]
    prior = {1: [
        NbaHistoryRow(player_id=1, game_id=day, season=2025, game_date=NOW.date() - timedelta(days=day),
                      game_type="REG", did_not_play=False, minutes=32.0,
                      stats={"points": 20, "assists": 5, "rebounds": 6})
        for day in range(1, 21)
    ]}
    board = prop_board.prop_board_response(NOW.date(), None, None, [game()], {7: modelled}, {7: plain}, prior, [], {7: report})
    served = props.props_response(7, modelled, prior, [], report)
    other = line_only_props.line_only_props(7, plain, [], report)
    detail = game_detail.game_detail(slate_games([game()], [], {2026: {}})[0], [], report)
    assert board.games[0].lines == served.lines
    assert board.games[0].line_only_lines == other.lines
    assert board.games[0].injury_report == served.injury_report == other.injury_report == detail.injury_report
    assert all(row.injury == report.injuries[0] for row in [*served.lines, *other.lines])
    before = props.props_response(7, modelled, prior, [])
    assert any(row.p_over is not None for row in served.lines)
    assert served.model_dump(exclude={"injury_report", "lines"}) == before.model_dump(exclude={"injury_report", "lines"})
    assert [row.model_dump(exclude={"injury"}) for row in served.lines] == [row.model_dump(exclude={"injury"}) for row in before.lines]
    before_plain = line_only_props.line_only_props(7, plain, [])
    assert [row.model_dump(exclude={"injury"}) for row in other.lines] == [row.model_dump(exclude={"injury"}) for row in before_plain.lines]


def test_empty_replacement_does_not_reuse_the_previous_player_status() -> None:
    old = injury_report(game(), snapshot(), NOW)
    new = injury_report(game(), NbaInjurySnapshot(NOW, ()), NOW)
    assert props.props_response(7, [line()], {}, [], old).lines[0].injury is not None
    assert props.props_response(7, [line()], {}, [], new).lines[0].injury is None


def test_report_defaults_serialize_nulls_and_do_not_share_mutable_lists() -> None:
    first = props.props_response(7, [line()], {}, [])
    second = props.props_response(7, [], {}, [])
    payload = first.model_dump(mode="json", by_alias=True)
    assert payload["injuryReport"] == {"source": "ESPN", "fetchedAt": None, "freshness": "unavailable", "injuries": []}
    assert payload["lines"][0]["injury"] is None
    first.injury_report.injuries.append(injury_report(game(), snapshot(), NOW).injuries[0])
    assert second.injury_report.injuries == []


def test_date_loader_batches_games_once_and_uses_each_games_own_cutoff(monkeypatch: pytest.MonkeyPatch) -> None:
    reader = AsyncMock(return_value={7: snapshot(), 8: snapshot(NOW + timedelta(hours=1))})
    monkeypatch.setattr(repo, "get_game_snapshots", reader)
    reports = asyncio.run(load_injury_reports(DB, [game(), game(8, NOW)], NOW))
    reader.assert_awaited_once_with(DB, [7, 8], NOW)
    assert reports[7].freshness == "fresh"
    assert reports[8].freshness == "unavailable"
    reader.reset_mock()
    assert asyncio.run(load_injury_reports(DB, [], NOW)) == {}
    reader.assert_not_awaited()


def test_actual_service_builders_use_the_same_batch_context_even_with_no_props(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in {
        "get_game": game(), "get_game_dates": [NOW.date()], "get_games_on": [game()],
        "get_modelled_lines": [], "get_line_only_lines": [], "get_date_modelled_lines": {},
        "get_date_line_only_lines": {}, "get_game_line_history": [],
    }.items():
        monkeypatch.setattr(nba_repo, name, AsyncMock(return_value=value))
    reader = AsyncMock(return_value={7: snapshot()})
    monkeypatch.setattr(repo, "get_game_snapshots", reader)
    slate_game = slate_games([game()], [], {2026: {}})[0]
    monkeypatch.setattr(game_detail, "assemble_games", AsyncMock(return_value=[slate_game]))
    responses = [
        asyncio.run(props.build_props(DB, 7, NOW)),
        asyncio.run(line_only_props.build_line_only_props(DB, 7, NOW)),
        asyncio.run(game_detail.build_game_detail(DB, 7, NOW)),
    ]
    board = asyncio.run(prop_board.build_prop_board(DB, NOW.date(), NOW.date(), NOW))
    assert all(response is not None and response.injury_report == board.games[0].injury_report for response in responses)
    assert reader.await_count == 4
    assert all(call.args == (DB, [7], NOW) for call in reader.await_args_list)


def test_missing_game_keeps_existing_not_found_behavior_without_injury_reads(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(nba_repo, "get_game", AsyncMock(return_value=None))
    reader = AsyncMock()
    monkeypatch.setattr(repo, "get_game_snapshots", reader)
    assert asyncio.run(props.build_props(DB, 7, NOW)) is None
    assert asyncio.run(line_only_props.build_line_only_props(DB, 7, NOW)) is None
    assert asyncio.run(game_detail.build_game_detail(DB, 7, NOW)) is None
    reader.assert_not_awaited()


def test_repository_preserves_empty_and_missing_snapshots_in_one_scoped_query() -> None:
    row = asdict(entry().injury)
    null_entry = {key: None for key in row}
    rows = [
        {**row, "game_id": 7, "snapshot_id": 1, "fetched_at": FETCHED, "player_id": 1},
        {**null_entry, "game_id": 8, "snapshot_id": 2, "fetched_at": NOW, "player_id": None},
        {**null_entry, "game_id": 9, "snapshot_id": None, "fetched_at": None, "player_id": None},
    ]
    result = AsyncMock()
    class Rows:
        def mappings(self) -> Rows:
            return self

        def all(self) -> list[dict[str, object]]:
            return rows

    result.execute.return_value = Rows()
    snapshots = asyncio.run(repo.get_game_snapshots(result, [7, 8, 9], NOW))
    assert snapshots[7] == snapshot()
    assert snapshots[8] == NbaInjurySnapshot(NOW, ())
    assert 9 not in snapshots
    result.execute.assert_awaited_once()
    sql = str(result.execute.call_args.args[0])
    for predicate in ("g.sport = 'nba'", "p.sport = 'nba'", "away.sport = 'nba'", "home.sport = 'nba'",
                      "g.game_type IN ('REG', 'PIN', 'PST')", "fetched_at < g.start_utc", "fetched_at <= :as_of",
                      "ORDER BY fetched_at DESC LIMIT 1", "i.team_code IN (away.team_code, home.team_code)"):
        assert predicate in sql
    result.execute.reset_mock()
    assert asyncio.run(repo.get_game_snapshots(result, [], NOW)) == {}
    result.execute.assert_not_awaited()

import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.core.nfl_line_grading import GradeableLine, LineOutcome, LineResult
from app.core.nfl_player import PlayerGameRow
from app.services.nfl.player_detail import build_player_detail, game_log_rows, player_detail

NOW = datetime(2026, 9, 30, 12, tzinfo=UTC)
PROFILE = {
    "id": 3107, "name": "James Cook", "position": "RB", "team_code": "BUF", "depth_position": "RB", "depth_rank": 1,
    "report_status": None, "practice_status": None, "primary_injury": None, "aliases": [],
    "stats_season": 2026, "stats_week": 3,
}
ROW = PlayerGameRow(
    game_id=34, season=2026, week=3, opponent="LAC", is_home=True, team_score=24, opponent_score=16, team_spread=-7.0,
    roof="outdoors", snap_pct=0.67, passing_completions=0, passing_attempts=0, passing_yards=0, rushing_attempts=24,
    rushing_yards=154, targets=1, receptions=0, receiving_yards=0, touchdowns=1, prizepicks_fantasy_points=20.4,
)


def game(**overrides: object) -> PlayerGameRow:
    return replace(ROW, **overrides)


def settled(game_id: int, market: str, line: float, outcome: LineOutcome, hour: int = 15, **overrides: object) -> LineResult:
    gradeable = GradeableLine(
        line_id=game_id * 100 + hour, season=2026, week=3, game_id=game_id, player_id=3107, market=market,
        segment="full_game", odds_type="standard", line=line, fetched_at=datetime(2026, 9, 26, hour, tzinfo=UTC),
        stat_value=154.0, offense_snaps=50, game_has_stats=True,
    )
    return LineResult(replace(gradeable, **overrides), outcome, 154.0)


def test_detail_maps_the_profile_summary_and_log() -> None:
    rows = [ROW, game(game_id=17, week=2, rushing_yards=135, rushing_attempts=21, snap_pct=None)]

    detail = player_detail(PROFILE, rows, [], 2026, 4)

    assert (detail.player_id, detail.team, detail.depth_rank, detail.focus_market) == (3107, "BUF", 1, "rushing_yards")
    assert detail.stats_through is not None and (detail.stats_through.season, detail.stats_through.week) == (2026, 3)
    assert (detail.summary.games, detail.summary.focus_per_game, detail.summary.volume_per_game) == (2, 144.5, 22.5)
    assert detail.summary.snap_share == 0.67
    assert [row.week for row in detail.game_log] == [3, 2]


def test_the_log_keeps_this_season_and_the_latest_five_previous_games() -> None:
    rows = [game(game_id=1, week=1)] + [game(game_id=100 + week, season=2025, week=week) for week in range(18, 10, -1)]

    assert [(row.season, row.week) for row in game_log_rows(rows, 2026)] == [
        (2026, 1), (2025, 18), (2025, 17), (2025, 16), (2025, 15), (2025, 14),
    ]


def test_a_player_with_no_games_this_season_still_shows_last_season() -> None:
    detail = player_detail(PROFILE, [game(season=2025, week=18)], [], 2026, 4)

    assert (detail.summary.games, detail.summary.focus_per_game) == (0, None)
    assert [(row.season, row.week) for row in detail.game_log] == [(2025, 18)]


def test_each_game_carries_its_latest_settled_focus_line_only() -> None:
    rows = [ROW, game(game_id=17, week=2), game(game_id=6, week=1)]
    results = [
        settled(34, "rushing_yards", 79.5, "over", hour=12),
        settled(34, "rushing_yards", 80.5, "over", hour=18),
        settled(34, "receiving_yards", 9.5, "under"),
        settled(34, "rushing_yards", 70.5, "over", hour=20, odds_type="goblin"),
        settled(17, "rushing_yards", 64.5, "void_dnp"),
        settled(6, "rushing_yards", 57.0, "push"),
    ]

    log = player_detail(PROFILE, rows, results, 2026, 4).game_log

    assert [(row.focus_line, row.focus_outcome) for row in log] == [(80.5, "over"), (None, None), (57.0, "push")]


def test_a_position_without_a_focus_has_no_lines_or_focus_market() -> None:
    detail = player_detail(PROFILE | {"position": "K"}, [ROW], [settled(34, "rushing_yards", 80.5, "over")], 2026, 4)

    assert detail.focus_market is None
    assert detail.game_log[0].focus_line is None


def test_the_response_serializes_in_camel_case() -> None:
    body = player_detail(PROFILE, [ROW], [], 2026, 4).model_dump(by_alias=True)

    assert body["gameLog"][0]["prizepicksFantasyPoints"] == 20.4
    assert body["statsThrough"] == {"season": 2026, "week": 3}


def test_an_unknown_player_is_none_and_skips_the_game_queries() -> None:
    with patch("app.services.nfl.player_detail.nfl_repo") as repo:
        repo.get_current_week = AsyncMock(return_value=(2026, 4))
        repo.get_player_profile = AsyncMock(return_value=None)
        repo.get_player_game_rows = AsyncMock()

        assert asyncio.run(build_player_detail(AsyncMock(), 999999, NOW)) is None

        repo.get_player_game_rows.assert_not_called()


def test_no_loaded_games_at_all_is_none() -> None:
    with patch("app.services.nfl.player_detail.nfl_repo") as repo:
        repo.get_current_week = AsyncMock(return_value=None)
        repo.get_player_profile = AsyncMock()

        assert asyncio.run(build_player_detail(AsyncMock(), 3107, NOW)) is None

        repo.get_player_profile.assert_not_called()


def test_a_known_player_reads_this_weeks_profile_and_this_seasons_lines() -> None:
    with patch("app.services.nfl.player_detail.nfl_repo") as repo:
        repo.get_current_week = AsyncMock(return_value=(2026, 4))
        repo.get_player_profile = AsyncMock(return_value=PROFILE)
        repo.get_player_game_rows = AsyncMock(return_value=[ROW])
        repo.get_gradeable_prop_lines = AsyncMock(return_value=[settled(34, "rushing_yards", 80.5, "over").line])

        detail = asyncio.run(build_player_detail(AsyncMock(), 3107, NOW))

        repo.get_player_profile.assert_awaited_once()
        assert repo.get_player_profile.await_args.args[1:] == (3107, 2026, 4)
        assert repo.get_gradeable_prop_lines.await_args.kwargs == {"player_id": 3107}
        assert detail is not None and detail.game_log[0].focus_outcome == "over"


def test_usage_takes_the_latest_eight_games_oldest_first_and_flags_last_season() -> None:
    rows = [game(game_id=week, week=week) for week in (3, 2, 1)] + [
        game(game_id=100 + week, season=2025, week=week) for week in range(18, 10, -1)
    ]

    detail = player_detail(PROFILE, rows, [], 2026, 4)

    assert [(item.season, item.week) for item in detail.usage] == [
        (2025, 14), (2025, 15), (2025, 16), (2025, 17), (2025, 18), (2026, 1), (2026, 2), (2026, 3),
    ]
    assert detail.usage[0].previous_season and not detail.usage[-1].previous_season
    assert detail.usage_stats == ["rushing_attempts", "targets", "snap_pct"]


def test_past_lines_and_splits_come_from_the_core() -> None:
    results = [settled(34, "rushing_yards", 80.5, "over"), settled(17, "rushing_yards", 64.5, "under")]

    detail = player_detail(PROFILE, [ROW, game(game_id=17, week=2, is_home=False)], results, 2026, 4)

    assert [(count.market, count.overs, count.decided) for count in detail.past_lines] == [("rushing_yards", 1, 2)]
    assert detail.break_even == pytest.approx(0.577, abs=0.001)
    assert [(split.label, split.games) for split in detail.splits][:3] == [("All", 2), ("Home", 1), ("Away", 1)]
    assert detail.model_dump(by_alias=True)["splits"][0]["focusPerGame"] == 154.0


def test_a_position_without_a_focus_has_no_splits_and_only_snap_usage() -> None:
    detail = player_detail(PROFILE | {"position": "K"}, [ROW], [], 2026, 4)

    assert detail.splits == []
    assert detail.usage_stats == ["snap_pct"]

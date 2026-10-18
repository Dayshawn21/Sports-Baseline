from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.core.nfl_line_grading import GradeableLine, LineOutcome, LineResult
from app.core.nfl_player import (
    NO_FOCUS,
    SPLIT_WINDOW,
    PastLineCount,
    PlayerGameRow,
    focus_for,
    past_line_counts,
    record_splits,
    season_summary,
)
from app.nfl.markets import NflPropMarket

ROW = PlayerGameRow(
    game_id=1, season=2026, week=1, opponent="NYJ", is_home=True, team_score=27, opponent_score=20,
    team_spread=-3.5, roof="outdoors", snap_pct=0.6, passing_completions=0, passing_attempts=0, passing_yards=0,
    rushing_attempts=15, rushing_yards=60, targets=3, receptions=2, receiving_yards=12, touchdowns=1,
    prizepicks_fantasy_points=14.2,
)
RB = focus_for("RB")


def row(**overrides: object) -> PlayerGameRow:
    return replace(ROW, **overrides)


@pytest.mark.parametrize(("position", "market", "volume"), [
    ("QB", NflPropMarket.PASSING_YARDS, "passing_attempts"),
    ("RB", NflPropMarket.RUSHING_YARDS, "rushing_attempts"),
    ("WR", NflPropMarket.RECEIVING_YARDS, "targets"),
    ("te", NflPropMarket.RECEIVING_YARDS, "targets"),
])
def test_each_skill_position_has_a_focus(position: str, market: NflPropMarket, volume: str) -> None:
    focus = focus_for(position)

    assert (focus.market, focus.volume_stat) == (market, volume)
    assert focus.usage_stats[-1] == "snap_pct"


@pytest.mark.parametrize("position", [None, "", "K", "FB"])
def test_other_positions_have_no_focus_but_keep_snaps(position: str | None) -> None:
    assert focus_for(position) is NO_FOCUS
    assert NO_FOCUS.usage_stats == ("snap_pct",)


def test_season_summary_counts_only_the_season_and_skips_missing_snaps_and_targets() -> None:
    rows = [row(week=3, rushing_yards=90, snap_pct=None, targets=None), row(week=2, rushing_yards=30, snap_pct=0.5), row(season=2025, rushing_yards=200)]

    summary = season_summary(rows, 2026, RB)

    assert (summary.games, summary.focus_per_game, summary.volume_per_game) == (2, 60.0, 15.0)
    assert summary.snap_share == 0.5


def test_a_season_with_no_games_has_empty_means() -> None:
    summary = season_summary([row(season=2025)], 2026, RB)

    assert (summary.games, summary.focus_per_game, summary.snap_share) == (0, None, None)


def test_favored_and_underdog_read_the_players_side_with_a_pickem_in_neither() -> None:
    rows = [
        row(game_id=1, is_home=True, team_spread=-3.5),
        row(game_id=2, is_home=False, team_spread=-1.0),
        row(game_id=3, is_home=True, team_spread=6.5),
        row(game_id=4, is_home=False, team_spread=2.5),
        row(game_id=5, is_home=True, team_spread=0.0),
        row(game_id=6, is_home=False, team_spread=None),
    ]

    games = {split.label: split.games for split in record_splits(rows, RB)}

    assert games == {"All": 6, "Home": 3, "Away": 3, "Team favored": 2, "Team underdog": 2, "Dome": 0, "Outdoor": 6}


def test_dome_and_closed_roofs_are_dome_and_open_is_outdoor() -> None:
    rows = [row(roof="dome"), row(roof="closed"), row(roof="open"), row(roof="outdoors"), row(roof=None)]

    games = {split.label: split.games for split in record_splits(rows, RB)}

    assert (games["Dome"], games["Outdoor"], games["All"]) == (2, 2, 5)


def test_splits_use_the_latest_seventeen_games() -> None:
    rows = [row(game_id=index, rushing_yards=100 if index < SPLIT_WINDOW else 0) for index in range(SPLIT_WINDOW + 3)]

    all_games = record_splits(rows, RB)[0]

    assert (all_games.games, all_games.focus_per_game) == (SPLIT_WINDOW, 100.0)


def test_a_position_without_a_focus_has_no_splits() -> None:
    assert record_splits([ROW], NO_FOCUS) == []


def _result(market: str, outcome: LineOutcome, odds_type: str | None = "standard", segment: str = "full_game") -> LineResult:
    line = GradeableLine(
        line_id=1, season=2026, week=3, game_id=1, player_id=7, market=market, segment=segment, odds_type=odds_type,
        line=60.5, fetched_at=datetime(2026, 9, 27, tzinfo=UTC), stat_value=70.0, offense_snaps=40, game_has_stats=True,
    )
    return LineResult(line, outcome, 70.0)


def test_past_line_counts_keep_decided_standard_full_game_lines_in_market_order() -> None:
    counts = past_line_counts([
        _result("receiving_yards", "over"),
        _result("rushing_yards", "over"),
        _result("rushing_yards", "under"),
        _result("rushing_yards", "push"),
        _result("rushing_yards", "void_dnp"),
        _result("rushing_yards", "over", odds_type="goblin"),
        _result("rushing_yards", "over", odds_type="demon"),
        _result("rushing_yards", "over", segment="first_half"),
    ])

    assert counts == [PastLineCount("rushing_yards", 1, 2), PastLineCount("receiving_yards", 1, 1)]


def test_no_settled_lines_means_no_counts() -> None:
    assert past_line_counts([_result("rushing_yards", "push")]) == []

import sys

import pytest

from app.backtest import nfl_usage_shift_counts
from app.backtest.nfl_usage_shift_counts import count_shifts, report
from app.core.nfl_projection_backtest import ReplayRow
from app.core.nfl_usage_shift import NO_CHART_ROW, NOT_FRESH, UsageShiftPlayer
from app.nfl.markets import NflPropMarket

WALKER, JOHNSON, LOWVOL, HURT, GONE = 1, 2, 3, 4, 5
AVERAGES = {
    "games": 8, "passing_yards": 0.0, "passing_attempts": 0.0, "passing_completions": 0.0,
    "rushing_yards": 40.0, "rushing_attempts": 9.0, "receiving_yards": 20.0, "receptions": 2.0,
    "touchdowns": 0.3, "fantasy_points": 9.0,
}
RB_GROUP = (
    UsageShiftPlayer(WALKER, 1, True, True, 16.0, 2.0, 6),
    UsageShiftPlayer(JOHNSON, 2, False, True, 8.0, 2.0, 6),
    UsageShiftPlayer(LOWVOL, 2, False, True, 0.5, 0.0, 6),
    UsageShiftPlayer(HURT, 3, True, False, 3.0, 1.0, 6),
    UsageShiftPlayer(GONE, None, True, True, 5.0, 1.0, 6),
)


def _replay(player_id: int, market: str, position: str = "RB", players: tuple | None = RB_GROUP) -> ReplayRow:
    row = {"game_id": 30, "player_id": player_id, "position": position, "market": market, "averages": dict(AVERAGES)}
    return ReplayRow(row=row, actual=0.0, home_market_prob=None, usage_shift_players=players)


def test_counts_shifted_rows_below_minimum_rows_givers_and_misses() -> None:
    rows = [
        _replay(JOHNSON, "rushing_yards"),
        _replay(JOHNSON, "receptions"),
        _replay(LOWVOL, "rushing_yards"),
        _replay(LOWVOL, "passing_yards"),  # not a shift market
        _replay(JOHNSON, "rushing_yards", position="QB"),  # not a shift position
        _replay(JOHNSON, "rushing_attempts", players=None),  # no inputs loaded
    ]

    counts = count_shifts(rows, transfer=1.0, min_own_volume=1.0, max_multiplier=3.0)

    rushing = counts.markets[NflPropMarket.RUSHING_YARDS]
    # Walker's 16 carries split between the two RB2s: Johnson (8 + 8) / 8; the 0.5-carry back is below the minimum.
    assert (rushing.rows, rushing.multipliers, rushing.below_min) == (2, [2.0], 1)
    receptions = counts.markets[NflPropMarket.RECEPTIONS]
    assert (receptions.rows, receptions.multipliers) == (1, [1.5])
    assert counts.markets[NflPropMarket.RUSHING_ATTEMPTS].rows == 0
    assert counts.givers == 1
    assert counts.missed == {NOT_FRESH: 1, NO_CHART_ROW: 1}


def test_the_report_prints_parameters_markets_and_misses_but_no_results() -> None:
    counts = count_shifts([_replay(JOHNSON, "rushing_yards")], transfer=1.0, min_own_volume=1.0, max_multiplier=3.0)

    text = report(counts, 1.0, 1.0, 3.0)

    assert "transfer=1 min_own_volume=1 max_multiplier=3" in text
    assert "rushing_yards" in text and "2.00" in text
    assert "Out players missed: no_chart_row 1, not_fresh 1" in text
    assert "actual" not in text.lower() and "mae" not in text.lower()


def test_any_season_but_2024_is_refused(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(sys, "argv", [
        "nfl_usage_shift_counts", "--season", "2025", "--transfer", "1", "--min-own-volume", "1", "--max-multiplier", "3",
    ])

    with pytest.raises(SystemExit):
        nfl_usage_shift_counts.main()

    assert "2025 is the usage-shift holdout" in capsys.readouterr().err

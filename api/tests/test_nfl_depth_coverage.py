from app.core.nfl_depth_coverage import DepthCoverage, DepthRow, OutRow, depth_coverage

WALKER, JOHNSON, RICE, KELCE, MAHOMES = 1, 2, 3, 4, 5


def test_counts_starters_out_rows_and_actionable_out_starters() -> None:
    depth = [
        # KC week 1: a full chart; the RB1 is Out and an RB2 is charted.
        DepthRow("KC", 1, MAHOMES, "QB", 1),
        DepthRow("KC", 1, WALKER, "RB", 1),
        DepthRow("KC", 1, JOHNSON, "RB", 2),
        DepthRow("KC", 1, RICE, "WR", 1),
        DepthRow("KC", 1, KELCE, "TE", 1),
        # KC week 2: no RB1 charted, and the Out WR1 has no WR2 behind him.
        DepthRow("KC", 2, MAHOMES, "QB", 1),
        DepthRow("KC", 2, JOHNSON, "RB", 2),
        DepthRow("KC", 2, RICE, "WR", 1),
    ]
    out = [
        OutRow("KC", 1, WALKER, "RB"),
        OutRow("KC", 2, RICE, "WR"),
        # Out with no chart row that week.
        OutRow("KC", 2, KELCE, "TE"),
        # A kicker is not counted.
        OutRow("KC", 2, 99, "K"),
    ]

    assert depth_coverage(depth, out) == DepthCoverage(
        team_weeks=2,
        starter_team_weeks={"QB": 2, "RB": 1, "WR": 2, "TE": 1},
        out_players=3,
        out_with_depth=2,
        actionable_out_starters=1,
    )


def test_an_out_backup_is_not_actionable() -> None:
    depth = [DepthRow("KC", 1, WALKER, "RB", 1), DepthRow("KC", 1, JOHNSON, "RB", 2)]

    coverage = depth_coverage(depth, [OutRow("KC", 1, JOHNSON, "RB")])

    assert (coverage.out_with_depth, coverage.actionable_out_starters) == (1, 0)


def test_an_empty_season_counts_nothing() -> None:
    assert depth_coverage([], []) == DepthCoverage(0, {"QB": 0, "RB": 0, "WR": 0, "TE": 0}, 0, 0, 0)


def test_the_report_shows_shares_and_leaves_an_empty_season_as_counts() -> None:
    from app.backtest.nfl_depth_coverage import report

    full = DepthCoverage(4, {"QB": 4, "RB": 3, "WR": 4, "TE": 2}, 10, 9, 5)
    empty = depth_coverage([], [])

    text = report({2025: full, 2024: empty})

    assert "Team-weeks with a RB1" in text and "3 (75%)" in text
    assert "9 (90%)" in text
    assert text.splitlines()[2].split() == ["2025", "2024"]

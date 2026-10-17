from dataclasses import replace
from datetime import UTC, datetime

from app.backtest.nfl_prizepicks_lines import MoneylineTiming, one_call_per_player_game, report
from app.core.nfl_line_grading import GradeableLine, settle_line

FETCHED = datetime(2026, 9, 20, 15, 0, tzinfo=UTC)


def _line(line_id: int, **overrides: object) -> GradeableLine:
    base = GradeableLine(
        line_id=line_id, season=2026, week=2, game_id=3, player_id=line_id, market="receptions",
        segment="full_game", odds_type="standard", line=4.5, fetched_at=FETCHED,
        stat_value=6.0, offense_snaps=50, week_has_stats=True,
    )
    return replace(base, **overrides)


def _results() -> list:
    return [settle_line(line) for line in [
        _line(1, stat_value=6.0),                                  # over, model called over: hit
        _line(2, stat_value=3.0),                                  # under, model called over: miss
        _line(3, stat_value=2.0),                                  # under, model called under: hit
        _line(4, stat_value=None, offense_snaps=None),             # did not play
        _line(5, segment="first_half"),                            # unsettleable segment
        _line(6, odds_type="goblin", line=2.5, stat_value=3.0),    # over, but not a model call
    ]]


def test_report_counts_coverage_and_scores_the_models_calls() -> None:
    text = report(2026, _results(), {1: 1.0, 2: 0.5, 3: -1.0}, MoneylineTiming(games=1, fetched_after_kickoff=0))

    assert "lines loaded (pre-kickoff)       6" in text
    assert "settled                          4" in text
    assert "did not play                     1" in text
    assert "half, quarter or season          1" in text
    assert "0 of 1" in text
    # Four receptions settled: standard 1 over of 3, goblin 1 over of 1.
    assert "receptions / standard                  3    33.3%" in text
    assert "receptions / goblin                    1   100.0%" in text
    # Calls: two hits of three. On a 4.5 reference, 1.0 is large (22%), 0.5 medium (11%).
    assert "all                                    3    66.7%" in text
    assert "edge >= 15%                            2   100.0%" in text
    assert "edge 5-15%                             1     0.0%" in text
    assert "57.7% (2-pick Power), 58.5% (3-pick Power)" in text


def test_one_call_per_player_game_keeps_the_newest_standard_line() -> None:
    older = _line(1, player_id=9, line=4.5)
    newer = _line(2, player_id=9, line=5.5, fetched_at=datetime(2026, 9, 20, 16, 0, tzinfo=UTC))
    goblin = _line(3, player_id=9, odds_type="goblin", line=3.5)
    other_market = _line(4, player_id=9, market="receiving_yards", line=40.5)

    calls = one_call_per_player_game([settle_line(line) for line in (older, newer, goblin, other_market)])

    assert [call.line.line_id for call in calls] == [2, 4]


def test_report_scores_p_over_by_odds_type_and_counts_unserved_lines() -> None:
    timing = MoneylineTiming(games=1, fetched_after_kickoff=0)

    text = report(2026, _results(), {}, timing, {1: 0.6, 2: 0.4, 6: 0.9})

    lines = text.splitlines()
    standard = next(line for line in lines if line.startswith("  standard "))
    goblin = next(line for line in lines if line.startswith("  goblin "))
    # Standard: lines 1 and 2 scored, line 3 settled without a P(over); goblin: line 6 alone.
    assert standard.split()[:5] == ["standard", "2", "1", "50.0%", "50.0%"]
    assert goblin.split()[:5] == ["goblin", "1", "0", "90.0%", "100.0%"]
    assert "reliability, all" in text

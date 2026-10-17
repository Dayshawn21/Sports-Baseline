from app.backtest.nba_ranking_check import report
from app.core.prop_ranking_check import slice_results


def test_report_names_nba_its_versions_and_its_own_coverage() -> None:
    text = report(2026, slice_results([]), 190, {"week_not_finished": 190}, {1: (0, 0)})

    assert text.splitlines()[0] == "NBA forward ranking check, 2026 (model nba-reference-v1, P(over) nba-pover-v1)"
    assert "frozen rows on completed games 190; excluded: week_not_finished 190" in text
    assert "coverage, modelled full-game lines with a frozen row: wk 1 0/0" in text
    assert "funnel: calls 0, with P(over) 0, picks 0, one per bet 0" in text
    assert "  standard under       0      0      0         -       -       57.7%   accruing, 0 of 200 picks, 0 of 4 weeks" in text

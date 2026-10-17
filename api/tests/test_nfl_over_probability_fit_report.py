import pytest

from app.core import nfl_over_probability_fit as served_fit
from app.core.nfl_over_probability_calibration import CalibrationReport, display_verdict
from app.core.nfl_over_probability_fit_report import FIT_MARKETS, FIT_PROJECTION_MODEL_VERSION, FIT_SEASON


def test_report_describes_the_fit_the_slate_serves() -> None:
    assert FIT_PROJECTION_MODEL_VERSION == served_fit.FIT_PROJECTION_MODEL_VERSION
    assert FIT_SEASON == served_fit.FIT_SEASON
    assert {row.market for row in FIT_MARKETS if row.verdict == "show"} == served_fit.SHOWN_MARKETS


def test_every_market_is_listed_once() -> None:
    markets = [row.market for row in FIT_MARKETS]

    assert len(markets) == len(set(markets)) == 8


@pytest.mark.parametrize("row", FIT_MARKETS, ids=lambda row: row.market)
def test_recorded_verdict_follows_the_pre_registered_rule(row) -> None:
    report = CalibrationReport(n=row.pairs, brier=row.brier, ece=row.ece, bins=(), worst_gap=row.worst_gap)

    assert display_verdict(row.cases, report, row.normal_brier) == row.verdict

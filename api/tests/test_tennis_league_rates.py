import pytest

from app.backtest.tennis_league_rates import report, summarize
from app.repositories.players import LeagueRateRow


def _row(tour: str, matches: int, allowed_df: float | None, allowed_ace: float | None = 0.07) -> LeagueRateRow:
    return LeagueRateRow(tour, matches, allowed_ace, allowed_df, 0.08, 0.04)


def _field(summary, tour, field):
    return next(s for s in summary[tour] if s.field == field)


def test_summary_is_per_tour_with_plain_and_weighted_means():
    rows = [_row("WTA", 10, 0.05), _row("WTA", 30, 0.06), _row("ATP", 20, 0.03)]
    summary = summarize(rows, min_matches=5)
    wta = _field(summary, "WTA", "allowed_df_per_sp")
    assert wta.n == 2
    assert wta.mean == pytest.approx(0.055)
    assert wta.weighted_mean == pytest.approx((0.05 * 10 + 0.06 * 30) / 40)
    assert _field(summary, "ATP", "allowed_df_per_sp").mean == pytest.approx(0.03)


def test_thin_samples_and_missing_values_are_left_out():
    rows = [_row("WTA", 2, 0.20), _row("WTA", 12, None), _row("WTA", 12, 0.05)]
    wta = _field(summarize(rows, min_matches=5), "WTA", "allowed_df_per_sp")
    assert wta.n == 1
    assert wta.mean == pytest.approx(0.05)


def test_report_format():
    text = report(summarize([_row("ATP", 10, 0.03), _row("WTA", 10, None)], 5), 5)
    lines = text.splitlines()
    assert lines[0] == "Tour league rates per serve point (last_52w, all surfaces, overall split)"
    assert lines[1] == "  players with at least 5 matches"
    assert "  ATP         allowed_df_per_sp          1   0.0300   0.0300" in lines
    assert "  WTA         allowed_df_per_sp          0      n/a      n/a" in lines

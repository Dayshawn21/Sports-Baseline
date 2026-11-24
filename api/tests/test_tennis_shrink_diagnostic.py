import asyncio
from datetime import date, datetime, timedelta, timezone
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.backtest import tennis_shrink_diagnostic as diag
from app.backtest.tennis_closing_lines import ClosingLineCase
from app.core.tennis_market_blend import market_anchored_prob
from app.core.tennis_market_blend_fit import FIT_COEFFICIENTS
from app.repositories.predictions import GradedPrediction, get_match_ids_with_model_prefix

START = datetime(2026, 9, 10, 18, tzinfo=timezone.utc)


def _row(match_id: int, tour: str = "WTA", market: float = 0.60, elo: float = 0.55,
         won: bool = True, version: str = "ensemble-v1+lgbm-v6", close: float | None = 0.61) -> GradedPrediction:
    start = START + timedelta(days=match_id)
    return GradedPrediction(
        match_id=match_id, tour=tour, start_utc=start, generated_at=start - timedelta(hours=5),
        model_version=version, p1_won=won, completed_score=True, elo_prob=elo, ml_prob=None,
        market_prob=market, ensemble_prob=0.6, market_book="draftkings", closing_market_prob=close,
    )


def test_matches_with_any_v3_prediction_are_dropped():
    rows = [_row(1), _row(2), _row(3)]
    kept = diag.outside_motivating_sample(rows, v3_match_ids={2})
    assert [r.match_id for r in kept] == [1, 3]


def test_unscorable_rows_are_dropped_by_the_26d_filter():
    no_elo = _row(4, elo=None)  # type: ignore[arg-type]
    assert diag.outside_motivating_sample([no_elo], set()) == []


def test_live_rows_are_replayed_through_v3_not_the_stored_ensemble():
    [row] = diag.live_diagnostic_rows([_row(1, market=0.60, elo=0.55)])
    assert row.model != 0.6
    assert row.market == 0.60 and row.close == 0.61


def test_shadow_equals_v3_below_the_threshold():
    row = diag.DiagnosticRow("WTA", model=0.62, market=0.60, close=None, p1_won=True)
    assert row.shadow == row.model


def test_shadow_halves_the_gap_at_three_points():
    row = diag.DiagnosticRow("WTA", model=0.66, market=0.60, close=None, p1_won=True)
    assert abs(row.shadow - 0.63) < 1e-12


def _rows_in(lines: list[str], group: str) -> list[str]:
    start = lines.index(next(line for line in lines if line.startswith(f"  {group} (")))
    return lines[start + 1:start + 6]


def test_bucket_assignment_and_shrink_column():
    rows = [
        diag.DiagnosticRow("WTA", 0.600, 0.600, 0.60, True),
        diag.DiagnosticRow("WTA", 0.605, 0.600, 0.60, False),
        diag.DiagnosticRow("WTA", 0.620, 0.600, 0.61, True),
        diag.DiagnosticRow("WTA", 0.620, 0.600, 0.59, False),
        diag.DiagnosticRow("WTA", 0.640, 0.600, 0.62, True),
        diag.DiagnosticRow("WTA", 0.640, 0.600, 0.60, False),
        diag.DiagnosticRow("WTA", 0.700, 0.600, 0.58, True),
        diag.DiagnosticRow("WTA", 0.700, 0.600, 0.61, False),
    ]
    wta = _rows_in(diag.bucket_lines(rows), "WTA")
    labels = [line.split()[0] for line in wta]
    assert labels == ["<1", "1-3", "3-5", "5+", "3+"]
    assert all("n=2" in line for line in wta[:4])
    assert "n=4" in wta[4]
    assert "shrink-v3" not in wta[0] and "shrink-v3" not in wta[1]
    assert all("shrink-v3" in line for line in wta[2:])


def test_groups_never_pool_challenger_with_atp_wta():
    rows = [diag.DiagnosticRow("CHALLENGER", 0.7, 0.6, 0.6, True), diag.DiagnosticRow("ATP", 0.7, 0.6, 0.6, True)]
    lines = diag.bucket_lines(rows)
    assert "  ATP+WTA (n=1)" in lines
    assert "  CHALLENGER (n=1)" in lines


def test_report_header_labels_exploration_and_counts():
    rows = [_row(1), _row(2), _row(3, elo=None)]  # type: ignore[arg-type]
    text = diag.live_report(rows, v3_match_ids={2})
    assert "EXPLORATION, NOT A VERDICT" in text
    assert "Settled graded matches 3; scorable by 26d's live filter 2; dropped for any ensemble-v3 prediction 1; kept 1" in text
    assert "By gap bucket" in text


class _Result:
    def fetchall(self) -> list:
        return [(5,), (9,)]


class _RecordingSession:
    def __init__(self) -> None:
        self.statement = ""
        self.params: dict = {}

    async def execute(self, statement, params=None) -> _Result:
        self.statement = " ".join(str(statement).split())
        self.params = params or {}
        return _Result()


def test_v3_match_ids_query_matches_any_prediction_by_prefix():
    session = _RecordingSession()
    ids = asyncio.run(get_match_ids_with_model_prefix(cast(AsyncSession, session), "ensemble-v3"))
    assert ids == {5, 9}
    assert session.statement == "SELECT DISTINCT match_id FROM predictions WHERE model_version LIKE :pattern"
    assert "generated_at" not in session.statement
    assert session.params == {"pattern": "ensemble-v3%"}


def _case(season: int = 2024, match_date: date | None = None, tour: str = "WTA", category: str = "Main tour",
          open_prob: float | None = 0.60, close: float = 0.62, elo: float | None = 0.50, won: bool = True) -> ClosingLineCase:
    return ClosingLineCase(
        tour=tour, category=category, round_code=10, tournament="Somewhere Open", season=season,
        match_date=match_date or date(season, 5, 1), p1_id=1, p2_id=2, p1_won=won, completed=True,
        truncated=False, elo_prob=elo, market_prob=close, open_prob=open_prob, blend_prob=0.6,
        p1_close_decimal=1.6, p2_close_decimal=2.4, elo_reliable=True,
    )


def test_history_drops_the_fit_season_and_the_motivating_dates():
    kept = diag.history_cases([
        _case(season=2022), _case(season=2023), _case(season=2026, match_date=date(2026, 9, 30)),
        _case(season=2026, match_date=date(2026, 10, 1)),
    ])
    assert [(c.season, c.match_date) for _, c in kept] == [(2023, date(2023, 5, 1)), (2026, date(2026, 9, 30))]


def test_history_needs_an_opening_price_and_a_scored_group():
    kept = diag.history_cases([
        _case(open_prob=None), _case(category="ITF"), _case(tour="ATP"), _case(tour="WTA", category="Challenger"),
    ])
    assert [g for g, _ in kept] == ["ATP", "CHALLENGER"]


def test_history_blends_the_open_not_the_close():
    case = _case(open_prob=0.60, close=0.70, elo=0.55)
    expected = market_anchored_prob(FIT_COEFFICIENTS["WTA"], 0.60, 0.55)
    assert diag.history_v3_prob(case) == expected
    [row] = diag.history_diagnostic_rows([("WTA", case)])
    assert (row.market, row.close) == (0.60, 0.70)


def test_history_gates_elo_against_the_open():
    case = _case(open_prob=0.80, close=0.60, elo=0.62)
    assert diag.history_v3_prob(case) == 0.80


def test_history_uses_the_challenger_coefficients_for_challenger_events():
    case = _case(tour="WTA", category="Challenger", open_prob=0.6, elo=0.55)
    assert diag.history_v3_prob(case) == market_anchored_prob(FIT_COEFFICIENTS["CHALLENGER"], 0.6, 0.55)


def test_history_report_labels_and_reference_section():
    cases = [_case(won=True), _case(won=False), _case(season=2022)]
    text = diag.history_report(cases)
    assert "EXPLORATION, NOT A VERDICT" in text
    assert "Cases 3; kept 2 (seasons 2024)." in text
    assert "By gap bucket" in text
    assert "Reference: v3 on the open minus the Pinnacle close" in text

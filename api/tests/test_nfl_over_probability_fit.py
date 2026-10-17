import pytest

from app.backtest.nfl_over_probability_fit import cross_fit, fit_tables, render_module, report, verdicts
from app.core.nfl_over_probability import QUANTILE_LEVELS
from app.core.nfl_projection_backtest import ReplayCase

# Right-skewed around a projection of 5: mean 5.5, median 5.5, a long upper tail.
SKEWED_ACTUALS = (0.0, 1.0, 2.0, 3.0, 4.0, 7.0, 8.0, 9.0, 11.0, 10.0)


def _cases(market: str, count: int) -> list[ReplayCase]:
    return [
        ReplayCase(
            player_id=i, game_id=i, week=1 + i % 18, position="WR", market=market,
            # i // 2 so both week parities see every actual; i alone would split them by parity.
            projection=5.0, actual=SKEWED_ACTUALS[(i // 2) % len(SKEWED_ACTUALS)],
        )
        for i in range(count)
    ]


def test_cross_fit_scores_every_case_out_of_fold_at_its_synthetic_lines() -> None:
    scored = cross_fit(_cases("receptions", 360))

    assert len(scored) == 360 * 5
    assert {p.line for p in scored} == {2.5, 3.5, 5.5, 6.5, 7.5}
    assert all(p.case.week % 2 in (0, 1) for p in scored)


def test_verdicts_show_a_calibrated_market_and_flag_a_thin_one() -> None:
    scored = cross_fit(_cases("receptions", 360) + _cases("rushing_attempts", 120))

    assert verdicts(scored) == {"receptions": "show", "rushing_attempts": "insufficient"}


def test_report_prints_a_market_row_the_lean_and_the_reliability_table() -> None:
    text = report(2025, cross_fit(_cases("receptions", 360)))

    assert "pre-registered 2026-09-26" in text
    row = next(line for line in text.splitlines() if line.strip().startswith("receptions") and "show" in line)
    assert row.split()[1:3] == ["360", "1800"]
    lean = next(line for line in text.splitlines() if line.strip().startswith("receptions") and len(line.split()) == 5)
    assert lean.split()[1] == "360"
    assert lean.split()[3] == "0.500"
    assert "Reliability, receptions" in text
    assert "position WR" in text


def test_rendered_module_round_trips() -> None:
    tables = {
        ("receptions", "WR"): tuple(level * 2 for level in QUANTILE_LEVELS),
        ("rushing_yards", "QB"): tuple(-0.5 + level * 3 for level in QUANTILE_LEVELS),
    }

    namespace: dict[str, object] = {}
    exec(render_module(2025, "model-v9", ["rushing_yards", "receptions"], tables), namespace)

    assert namespace["FIT_SEASON"] == 2025
    assert namespace["FIT_PROJECTION_MODEL_VERSION"] == "model-v9"
    assert namespace["SHOWN_MARKETS"] == frozenset({"receptions", "rushing_yards"})
    loaded = namespace["QUANTILES_BY_GROUP"]
    assert isinstance(loaded, dict) and set(loaded) == set(tables)
    for group, values in tables.items():
        assert loaded[group] == pytest.approx(values, abs=5e-5)


def test_fit_tables_keep_only_shown_markets() -> None:
    tables = fit_tables(_cases("receptions", 40) + _cases("rushing_attempts", 40), ["receptions"])

    assert list(tables) == [("receptions", "WR")]
    assert len(tables[("receptions", "WR")]) == len(QUANTILE_LEVELS)

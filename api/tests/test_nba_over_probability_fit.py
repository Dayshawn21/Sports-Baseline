from datetime import date

from app.backtest.nba_over_probability_fit import render_module, report, verdicts
from app.core import nba_over_probability_fit as fit
from app.core.nba_over_probability import NBA_OVER_PROBABILITY_VERSION, ScoredLine
from app.core.nba_projection_backtest import BACKTEST_MARKETS, NBA_PROJECTION_MODEL_VERSION, NbaReplayCase
from app.core.nfl_over_probability import QUANTILE_LEVELS


def _case(player_id: int, prior_minutes: float = 30.0) -> NbaReplayCase:
    return NbaReplayCase(
        player_id=player_id, game_id=1, game_date=date(2026, 1, 5), game_type="REG", market="rebounds",
        prior_minutes=prior_minutes, projection=6.0, actual=7.0 if player_id % 2 else 5.0,
    )


def _scored(cases: int) -> list[ScoredLine]:
    # Every case at the line nearest its projection (6.5): half go over, each predicted 0.5.
    return [
        ScoredLine(case=_case(player_id, 24.0 if player_id < 100 else 30.0), line=6.5, p_over=0.5,
                   normal_p_over=0.4, over=bool(player_id % 2))
        for player_id in range(cases)
    ]


def test_report_prints_the_verdict_row_nearest_line_and_minutes() -> None:
    text = report(_scored(300))

    assert "rebounds                      300     300   0.000   0.000  0.2500  0.2600  show" in text
    assert "rebounds                      300      0.500     0.500   0.400" in text
    assert "rebounds / 20-28 min                     100   0.000" in text
    assert "holdout read 2 (no projection verdict)" in text
    assert "nba-reference-v1" in text and "nba-pover-v1" in text


def test_report_names_the_failed_check() -> None:
    worse_than_normal = [
        ScoredLine(case=line.case, line=line.line, p_over=0.5, normal_p_over=float(line.over), over=line.over)
        for line in _scored(300)
    ]
    assert verdicts(worse_than_normal) == {"rebounds": "hide"}
    assert "hide      Brier" in report(worse_than_normal)


def test_too_few_cases_is_insufficient() -> None:
    assert verdicts(_scored(299)) == {"rebounds": "insufficient"}
    assert "insufficient cases" in report(_scored(299))


def test_the_generated_fit_matches_the_served_versions_and_shape() -> None:
    assert fit.FIT_PROJECTION_MODEL_VERSION == NBA_PROJECTION_MODEL_VERSION
    assert fit.OVER_PROBABILITY_VERSION == NBA_OVER_PROBABILITY_VERSION
    assert (fit.FIT_SEASON, fit.SCORED_SEASON) == (2024, 2025)
    assert fit.SHOWN_MARKETS <= {market.value for market in BACKTEST_MARKETS}
    assert set(fit.QUANTILES_BY_MARKET) == fit.SHOWN_MARKETS
    for quantiles in fit.QUANTILES_BY_MARKET.values():
        assert len(quantiles) == len(QUANTILE_LEVELS)
        assert list(quantiles) == sorted(quantiles)
    assert "blocks" not in fit.QUANTILES_BY_MARKET


def test_render_module_writes_shown_markets_only_at_four_decimals() -> None:
    text = render_module(["assists"], {"assists": [i / 3 for i in range(41)]})

    assert "Do not edit." in text
    assert "FIT_SEASON = 2024" in text and "SCORED_SEASON = 2025" in text
    assert 'FIT_PROJECTION_MODEL_VERSION = "nba-reference-v1"' in text
    assert "SHOWN_MARKETS: frozenset[str] = frozenset({'assists'})" in text
    assert "        0.0000, 0.3333, 0.6667, 1.0000, 1.3333, 1.6667, 2.0000, 2.3333," in text
    namespace: dict[str, object] = {}
    exec(compile(text, "generated", "exec"), namespace)
    assert namespace["SHOWN_MARKETS"] == frozenset({"assists"})

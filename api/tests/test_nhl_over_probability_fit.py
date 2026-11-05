from math import inf
from pathlib import Path

import pytest

from app.backtest import nhl_over_probability_fit as cli
from app.core.count_over_probability import NegBinParams, ScaledNormalParams
from app.core.nhl_over_probability import CandidateResult, Family, NhlDisplayVerdict as Verdict
from app.core.nhl_over_probability_crossfit import (
    Confirmation, FamilyDiagnostics, MarketFit, MarketSelection, RatioParams, confirm_markets, select_markets,
)
from app.nhl.markets import NhlLineOnlyMarket
from tests.test_nhl_over_probability_crossfit import weekly_cases


def selection(selected: Family | None = "negbin") -> MarketSelection:
    return MarketSelection(
        results=(
            CandidateResult("negbin", 1200, 0.21, "show"),
            CandidateResult("scaled_normal", 250, 0.22, "insufficient"),
            CandidateResult("ratio", 1200, 0.24, "hide"),
        ),
        diagnostics=(
            FamilyDiagnostics(5000, 0.011, 0.02, 0.23),
            FamilyDiagnostics(900, 0.01, None, 0.23),
            FamilyDiagnostics(5000, 0.031, 0.07, 0.23),
        ),
        selected=selected,
    )


def row(text: str, needle: str) -> str:
    return next(line for line in text.splitlines() if needle in line)


def test_header_names_the_commit_the_rule_the_seasons_and_that_the_holdout_is_unread() -> None:
    text = cli.report([], {})
    assert "512fe51eebd18dd3e7abd3bc15aa82e640831185" in text
    assert "2024-25 (development: select freely)" in text and "Holdout (2025-26): not read." in text
    assert "nhl-reference-v1" in text and "nhl-pover-v1" in text and "negbin, scaled_normal, ratio" in text
    assert "Integer lines" in text


def test_a_confirm_run_that_reads_the_holdout_does_not_claim_it_is_unread() -> None:
    text = cli.report([], {}, holdout_read=True)
    assert "Holdout (2025-26): read once in this run, reported below." in text
    assert "not read" not in text


def test_a_confirm_run_without_write_is_refused_before_any_read() -> None:
    with pytest.raises(ValueError, match="needs --write"):
        cli.check_flags(True, True, False)


def test_a_market_row_shows_cases_pairs_metrics_and_verdict() -> None:
    negbin = row(cli.report([], {NhlLineOnlyMarket.GOALS: selection()}), "goals / negbin")
    for value in ("1200", "5000", "0.0110", "0.0200", "0.2100", "0.2300", "show"):
        assert value in negbin


def test_a_row_names_what_failed_and_dashes_what_could_not_be_computed() -> None:
    text = cli.report([], {NhlLineOnlyMarket.GOALS: selection()})
    assert row(text, "goals / scaled_normal").rstrip().endswith("insufficient (cases<300)")
    assert "--" in row(text, "goals / scaled_normal")
    assert row(text, "goals / ratio").rstrip().endswith("hide (ece,bin,brier)")


def test_the_selection_table_lists_each_selected_family_and_hidden_markets() -> None:
    text = cli.report([], {NhlLineOnlyMarket.GOALS: selection(), NhlLineOnlyMarket.HITS: selection(None)})
    chosen = text.split("Selected on development")[1]
    assert "goals               negbin" in chosen
    assert "hits                hidden (no eligible family)" in chosen


def test_the_report_runs_on_real_selection_output_for_a_stub_history() -> None:
    cases = weekly_cases(2.0, 40)
    text = cli.report(cases, select_markets(cases))
    assert "Cases: 40 reference-arm replay cases" in text
    assert "goals               hidden (no eligible family)" in text


def test_only_the_development_seasons_are_read() -> None:
    assert cli.DEVELOPMENT_SEASONS == (2023, 2024)


@pytest.mark.parametrize(
    ("confirm", "holdout", "write", "ok"),
    [
        (False, False, False, True), (True, True, True, True),
        (True, True, False, False), (True, False, True, False), (True, False, False, False),
        (False, True, False, False), (False, False, True, False), (False, True, True, False),
    ],
)
def test_flags_need_each_other_in_the_registered_way(confirm: bool, holdout: bool, write: bool, ok: bool) -> None:
    if ok:
        cli.check_flags(confirm, holdout, write)
    else:
        with pytest.raises(ValueError, match="--holdout|--confirm"):
            cli.check_flags(confirm, holdout, write)


def test_the_confirm_run_refuses_when_the_generated_module_exists(tmp_path: Path) -> None:
    module = tmp_path / "nhl_over_probability_fit.py"
    cli.check_module_absent(module)
    module.write_text("SHOWN_MARKETS = frozenset()\n")
    with pytest.raises(ValueError, match="already read"):
        cli.check_module_absent(module)


def test_the_generated_module_lives_beside_the_other_core_modules() -> None:
    assert cli.FIT_MODULE_PATH.parent.name == "core" and cli.FIT_MODULE_PATH.name == "nhl_over_probability_fit.py"


def confirmation(
    family: Family, params: NegBinParams | ScaledNormalParams | RatioParams, verdict: Verdict = "show",
) -> Confirmation:
    return Confirmation(
        family=family, fit=MarketFit(params, 1.0), result=CandidateResult(family, 800, 0.2, verdict),
        diagnostics=FamilyDiagnostics(4000, 0.01, 0.02, 0.22),
    )


def test_the_module_renders_only_shown_markets_and_reads_back_exactly() -> None:
    quantiles = tuple(i / 20 for i in range(41))
    text = cli.render_module({
        NhlLineOnlyMarket.SHOTS_ON_GOAL: confirmation("negbin", NegBinParams(r=3.25)),
        NhlLineOnlyMarket.POINTS: confirmation("negbin", NegBinParams(r=1.5), "hide"),
        NhlLineOnlyMarket.HITS: confirmation("negbin", NegBinParams(r=inf)),
        NhlLineOnlyMarket.TIME_ON_ICE: confirmation("scaled_normal", ScaledNormalParams(a=0.1, b=0.9)),
        NhlLineOnlyMarket.GOALIE_SAVES: confirmation("ratio", RatioParams(quantiles)),
        NhlLineOnlyMarket.GOALS_ALLOWED: confirmation("ratio", RatioParams(quantiles), "insufficient"),
    })
    namespace: dict[str, object] = {}
    exec(compile(text, "generated", "exec"), namespace)
    assert namespace["SHOWN_MARKETS"] == {"shots_on_goal", "hits", "time_on_ice", "goalie_saves"}
    assert namespace["FAMILY_BY_MARKET"] == {
        "shots_on_goal": "negbin", "hits": "negbin", "time_on_ice": "scaled_normal", "goalie_saves": "ratio",
    }
    assert namespace["NEGBIN_R"] == {"shots_on_goal": 3.25, "hits": inf}
    assert namespace["SCALED_NORMAL"] == {"time_on_ice": (0.1, 0.9)}
    assert namespace["RATIO_QUANTILES"] == {"goalie_saves": quantiles}
    assert (namespace["FIT_SEASON"], namespace["SCORED_SEASON"]) == (2024, 2025)
    assert namespace["FIT_PROJECTION_MODEL_VERSION"] == "nhl-reference-v1"
    assert namespace["OVER_PROBABILITY_VERSION"] == "nhl-pover-v1"
    assert namespace["PRE_REGISTRATION_COMMIT"] == "512fe51eebd18dd3e7abd3bc15aa82e640831185"
    assert "points" not in text and "goals_allowed" not in text and text.startswith('"""Generated by')


def test_a_run_with_nothing_shown_renders_empty_tables() -> None:
    text = cli.render_module({NhlLineOnlyMarket.POINTS: confirmation("negbin", NegBinParams(r=2.0), "hide")})
    namespace: dict[str, object] = {}
    exec(compile(text, "generated", "exec"), namespace)
    assert namespace["SHOWN_MARKETS"] == frozenset()
    assert namespace["NEGBIN_R"] == namespace["SCALED_NORMAL"] == namespace["RATIO_QUANTILES"] == {}


def test_a_market_that_could_not_be_fitted_is_never_shown() -> None:
    unfitted = Confirmation("negbin", None, CandidateResult("negbin", 0, inf, "insufficient"), FamilyDiagnostics(0, None, None, None))
    assert "Shown: none" in cli.confirmation_report({NhlLineOnlyMarket.GOALS: unfitted})
    assert cli.render_module({NhlLineOnlyMarket.GOALS: unfitted}).count("goals") == 0


def test_the_confirmation_report_says_it_is_the_one_holdout_read_and_lists_shown_markets() -> None:
    text = cli.confirmation_report({
        NhlLineOnlyMarket.HITS: confirmation("negbin", NegBinParams(r=2.0)),
        NhlLineOnlyMarket.POINTS: confirmation("negbin", NegBinParams(r=2.0), "hide"),
    })
    assert "holdout read 1" in text and "2025-26" in text
    assert row(text, "hits / negbin").rstrip().endswith("show")
    assert text.rstrip().endswith("Shown: hits")


def test_a_confirmation_scores_only_the_markets_selected_in_development() -> None:
    fit_cases = weekly_cases(2.0, 400) + weekly_cases(2.0, 400, NhlLineOnlyMarket.HITS)
    holdout_cases = weekly_cases(2.0, 400) + weekly_cases(2.0, 400, NhlLineOnlyMarket.HITS)
    confirmations = confirm_markets({NhlLineOnlyMarket.GOALS: "negbin"}, fit_cases, holdout_cases)
    assert set(confirmations) == {NhlLineOnlyMarket.GOALS}
    goals = confirmations[NhlLineOnlyMarket.GOALS]
    assert goals.family == "negbin" and goals.fit is not None and goals.result.cases == 400


def test_a_selected_market_with_no_holdout_cases_is_insufficient_not_shown() -> None:
    confirmations = confirm_markets({NhlLineOnlyMarket.GOALS: "negbin"}, weekly_cases(2.0, 400), [])
    assert confirmations[NhlLineOnlyMarket.GOALS].result.verdict == "insufficient"


def test_failed_checks_names_each_missed_rule() -> None:
    assert cli.failed_checks(1000, FamilyDiagnostics(5000, 0.01, 0.02, 0.25), 0.2) == ""
    assert cli.failed_checks(299, FamilyDiagnostics(5000, 0.01, 0.02, 0.25), 0.2) == "cases<300"
    assert cli.failed_checks(1000, FamilyDiagnostics(5000, 0.03, 0.06, 0.2), 0.25) == "ece,bin,brier"

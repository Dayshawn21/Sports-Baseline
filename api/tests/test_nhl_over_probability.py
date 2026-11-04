import datetime as dt

import pytest

from app.core import nhl_over_probability as rule
from app.core.nfl_over_probability_calibration import CalibrationBin, CalibrationReport
from app.core.nhl_over_probability import CandidateResult, nhl_display_verdict, select_family
from app.nhl.markets import NhlLineOnlyMarket


def report(ece: float = 0.01, brier: float = 0.2, bins: tuple[CalibrationBin, ...] = ()) -> CalibrationReport:
    return CalibrationReport(n=sum(b.n for b in bins), brier=brier, ece=ece, bins=bins, worst_gap=None)


def bin_off_by(n: int, gap: float) -> CalibrationBin:
    return CalibrationBin(n=n, mean_predicted=0.5, observed=0.5 - gap)


def test_registered_display_rule_constants_are_pinned() -> None:
    assert (rule.MIN_CASES, rule.MAX_ECE, rule.MAX_BIN_GAP, rule.MIN_BIN_PAIRS) == (300, 0.02, 0.05, 200)


def test_registered_versions_and_seasons_are_pinned() -> None:
    assert rule.NHL_PROJECTION_MODEL_VERSION == "nhl-reference-v1"
    assert rule.NHL_OVER_PROBABILITY_VERSION == "nhl-pover-v1"
    assert (rule.FIT_SEASON, rule.CONFIRMATION_SEASON) == (2024, 2025)


def test_registered_candidate_order_is_pinned() -> None:
    assert rule.CANDIDATE_ORDER == ("negbin", "scaled_normal", "ratio")


def test_registered_domain_rules_are_pinned() -> None:
    assert rule.FAMILY_EXCLUDED_MARKETS == {
        "negbin": {NhlLineOnlyMarket.PLUS_MINUS, NhlLineOnlyMarket.TIME_ON_ICE},
        "scaled_normal": set(),
        "ratio": {NhlLineOnlyMarket.PLUS_MINUS},
    }
    assert {family for family in rule.CANDIDATE_ORDER} == set(rule.FAMILY_EXCLUDED_MARKETS)


@pytest.mark.parametrize(("family", "market", "applies"), [
    ("negbin", NhlLineOnlyMarket.GOALS, True),
    ("negbin", NhlLineOnlyMarket.PLUS_MINUS, False),
    ("negbin", NhlLineOnlyMarket.TIME_ON_ICE, False),
    ("scaled_normal", NhlLineOnlyMarket.PLUS_MINUS, True),
    ("ratio", NhlLineOnlyMarket.TIME_ON_ICE, True),
    ("ratio", NhlLineOnlyMarket.PLUS_MINUS, False),
])
def test_a_family_reads_only_the_markets_it_can_represent(family: rule.Family, market: NhlLineOnlyMarket, applies: bool) -> None:
    assert rule.family_applies(family, market) is applies


def test_the_rule_text_states_the_registered_numbers() -> None:
    for text in ("300", "0.02", "200", "0.05", "2024-25", "2025-26"):
        assert text in rule.RULE_TEXT


def test_parity_splits_by_iso_week() -> None:
    assert rule.parity(dt.date(2024, 10, 14)) == rule.parity(dt.date(2024, 10, 20))
    assert rule.parity(dt.date(2024, 10, 14)) != rule.parity(dt.date(2024, 10, 21))


def test_verdict_needs_three_hundred_cases() -> None:
    assert nhl_display_verdict(299, report(), 0.25) == "insufficient"
    assert nhl_display_verdict(300, report(), 0.25) == "show"


def test_ece_of_exactly_two_percent_passes_and_above_fails() -> None:
    assert nhl_display_verdict(300, report(ece=0.02), 0.25) == "show"
    assert nhl_display_verdict(300, report(ece=0.0201), 0.25) == "hide"


def test_a_large_bin_exactly_five_percent_off_passes_and_beyond_fails() -> None:
    assert nhl_display_verdict(300, report(bins=(bin_off_by(200, 0.05),)), 0.25) == "show"
    assert nhl_display_verdict(300, report(bins=(bin_off_by(200, 0.0501),)), 0.25) == "hide"


def test_a_small_bin_far_off_is_ignored() -> None:
    assert nhl_display_verdict(300, report(bins=(bin_off_by(199, 0.4),)), 0.25) == "show"


def test_brier_equal_to_the_normals_passes_and_worse_fails() -> None:
    assert nhl_display_verdict(300, report(brier=0.25), 0.25) == "show"
    assert nhl_display_verdict(300, report(brier=0.2501), 0.25) == "hide"


def result(family: rule.Family, brier: float, verdict: rule.NhlDisplayVerdict = "show") -> CandidateResult:
    return CandidateResult(family=family, cases=1000, brier=brier, verdict=verdict)


def test_selection_takes_the_lowest_brier_among_eligible_families() -> None:
    assert select_family([result("negbin", 0.21), result("scaled_normal", 0.20), result("ratio", 0.22)]) == "scaled_normal"


def test_an_ineligible_family_is_never_selected_however_low_its_brier() -> None:
    results = [result("negbin", 0.10, "hide"), result("scaled_normal", 0.20, "insufficient"), result("ratio", 0.22)]
    assert select_family(results) == "ratio"


def test_an_exact_tie_goes_to_the_earlier_family_in_candidate_order() -> None:
    assert select_family([result("ratio", 0.2), result("scaled_normal", 0.2), result("negbin", 0.2)]) == "negbin"
    assert select_family([result("ratio", 0.2), result("scaled_normal", 0.2)]) == "scaled_normal"


def test_no_eligible_family_hides_the_market() -> None:
    assert select_family([result("negbin", 0.2, "hide"), result("ratio", 0.2, "insufficient")]) is None
    assert select_family([]) is None

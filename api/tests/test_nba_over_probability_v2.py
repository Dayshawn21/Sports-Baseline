import datetime as dt

from app.core.nba_over_probability_v2 import (
    CANDIDATE_ORDER,
    CONFIRMATION_SEASON,
    CONFIRMATION_WEEKS,
    DISPLAY_RULE,
    FIT_SEASON,
    NBA_OVER_PROBABILITY_V2_VERSION,
    TARGET_MARKETS,
    CandidateResult,
    select_family,
    split_by_parity,
)
from app.core.nba_projection_backtest import NbaReplayCase
from app.nba.markets import NbaPropMarket


def _case(day: dt.date) -> NbaReplayCase:
    return NbaReplayCase(
        player_id=1, game_id=day.toordinal(), game_date=day, game_type="REG",
        market="points", prior_minutes=30.0, projection=20.0, actual=18.0,
    )


def _result(family, brier, verdict="show", cases=5000):
    return CandidateResult(family=family, cases=cases, brier=brier, verdict=verdict)


def test_pre_registered_constants_are_pinned():
    assert NBA_OVER_PROBABILITY_V2_VERSION == "nba-pover-v2"
    assert CANDIDATE_ORDER == ("negbin", "scaled_normal")
    assert FIT_SEASON == 2024
    assert CONFIRMATION_SEASON == 2026
    assert CONFIRMATION_WEEKS == (1, 2, 3, 4)


def test_target_markets_are_the_eight_20g1_hid():
    assert set(TARGET_MARKETS) == set(NbaPropMarket) - {NbaPropMarket.ASSISTS}
    assert len(TARGET_MARKETS) == 8


def test_display_rule_is_20g1s_unchanged():
    assert DISPLAY_RULE == (300, 0.02, 0.05, 200)


def test_split_by_iso_week_parity():
    monday_week_44 = dt.date(2024, 10, 28)
    sunday_week_44 = dt.date(2024, 11, 3)
    monday_week_45 = dt.date(2024, 11, 4)
    even, odd = split_by_parity([_case(monday_week_44), _case(sunday_week_44), _case(monday_week_45)])
    assert [c.game_date for c in even] == [monday_week_44, sunday_week_44]
    assert [c.game_date for c in odd] == [monday_week_45]


def test_both_pass_lower_brier_wins():
    assert select_family([_result("negbin", 0.20), _result("scaled_normal", 0.19)]) == "scaled_normal"


def test_only_one_passes():
    assert select_family([_result("negbin", 0.25), _result("scaled_normal", 0.19, "hide")]) == "negbin"


def test_neither_passes_is_not_carried():
    assert select_family([_result("negbin", 0.20, "hide"), _result("scaled_normal", 0.19, "hide")]) is None


def test_exact_tie_goes_to_candidate_order():
    assert select_family([_result("scaled_normal", 0.2), _result("negbin", 0.2)]) == "negbin"


def test_insufficient_cases_are_not_eligible():
    results = [_result("negbin", 0.2, "insufficient", 299), _result("scaled_normal", 0.3, "insufficient", 299)]
    assert select_family(results) is None

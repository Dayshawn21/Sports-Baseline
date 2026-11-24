import datetime as dt

from app.core import nhl_projection_backtest as rule
from app.core.nfl_projection_backtest import PairedDiff
from app.core.nhl_projection_backtest import NhlReplayCase, nhl_adoption_verdict
from app.nhl.markets import NhlLineOnlyMarket


def diff(n: int = 300, change: float = -0.05, mean_diff: float = -0.2, se: float = 0.05) -> PairedDiff:
    return PairedDiff(
        n=n, production_mae=1.0, variant_mae=1.0 + change, mean_diff=mean_diff,
        standard_error=se, relative_mae_change=change,
    )


def test_registered_adoption_rule_constants_are_pinned() -> None:
    assert rule.MIN_PAIRED_CASES == 300
    assert rule.MIN_RELATIVE_MAE_IMPROVEMENT == 0.01
    assert rule.STANDARD_ERRORS_REQUIRED == 2.0


def test_registered_replay_constants_are_pinned() -> None:
    assert (rule.REFERENCE_ARM, rule.REFERENCE_GAMES) == ("reference", 20)
    assert (rule.LAST_10_ARM, rule.LAST_10_GAMES) == ("last_10", 10)
    assert rule.MIN_PRIOR_GAMES == 10
    assert rule.TOI_WINDOW == 10
    assert rule.MIN_PRIOR_TOI_MINUTES == 12.0
    assert rule.MIN_PRIOR_GOALIE_STARTS == 5
    assert rule.SERVED_GAME_TYPES == ("REG", "PST")
    assert rule.NHL_PROJECTION_REFERENCE_VERSION == "nhl-reference-v1"


def test_registered_seasons_are_pinned() -> None:
    assert (rule.PRIOR_SEASON, rule.DEVELOPMENT_SEASON, rule.HOLDOUT_SEASON) == (2023, 2024, 2025)


def test_markets_cover_every_priced_market_and_faceoffs_are_for_centers() -> None:
    assert set(rule.BACKTEST_MARKETS) == set(NhlLineOnlyMarket)
    assert len(rule.BACKTEST_MARKETS) == 12
    assert rule.CENTER_ONLY_MARKETS == {NhlLineOnlyMarket.FACEOFFS_WON}
    assert rule.CENTER_POSITION == "C"


def test_verdict_needs_three_hundred_paired_cases() -> None:
    assert nhl_adoption_verdict(diff(n=299)) == "insufficient"
    assert nhl_adoption_verdict(diff(n=300)) == "adopt"


def test_verdict_adopts_at_exactly_one_percent() -> None:
    assert nhl_adoption_verdict(diff(change=-0.01, mean_diff=-0.21)) == "adopt"
    assert nhl_adoption_verdict(diff(change=-0.0099, mean_diff=-0.21)) == "reject"


def test_verdict_needs_more_than_two_standard_errors() -> None:
    assert nhl_adoption_verdict(diff(mean_diff=-0.2, se=0.1)) == "reject"
    assert nhl_adoption_verdict(diff(mean_diff=-0.2001, se=0.1)) == "adopt"


def test_verdict_rejects_a_worse_variant() -> None:
    assert nhl_adoption_verdict(diff(change=0.02, mean_diff=0.3)) == "reject"


def test_replay_case_error_is_projection_minus_actual_and_keyed_by_market() -> None:
    case = NhlReplayCase(
        player_id=1, game_id=2, game_date=dt.date(2025, 1, 2), game_type="REG", market="shots_on_goal",
        prior_toi_minutes=18.0, projection=2.5, actual=4.0,
    )
    assert case.error == -1.5
    assert case.key == (1, 2, "shots_on_goal")

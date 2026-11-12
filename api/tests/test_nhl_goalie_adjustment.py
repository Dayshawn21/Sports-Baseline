import pytest

from app.core import nhl_goalie_adjustment as adj
from app.core.nhl_goalie_adjustment import GoalieRecord, adjusted_value, goalie_multiplier, shrunk_save_pct
from app.nhl.markets import NhlLineOnlyMarket

LEAGUE = 0.900


def test_preregistered_constants_are_pinned() -> None:
    assert adj.NHL_OPP_GOALIE_VERSION == "nhl-opp-goalie-v1"
    assert adj.GOALIE_QUALITY_STARTS == 20
    assert adj.SHRINK_SHOTS == 1000
    assert (adj.MIN_MULTIPLIER, adj.MAX_MULTIPLIER) == (0.80, 1.25)
    assert adj.DEVELOPMENT_BETAS == (0.5, 1.0)
    assert adj.SELECTION_BETAS == (0.0, 0.5, 1.0)
    assert {market.value for market in adj.ADJUSTED_MARKETS} == {
        "shots_on_goal", "points", "goals", "assists", "power_play_points",
    }


def test_no_prior_shots_reads_the_league_value() -> None:
    assert shrunk_save_pct(GoalieRecord(0, 0), LEAGUE) == pytest.approx(LEAGUE)
    assert goalie_multiplier(GoalieRecord(0, 0), LEAGUE) == pytest.approx(1.0)


def test_missing_record_is_neutral() -> None:
    assert goalie_multiplier(None, LEAGUE) == 1.0


def test_shrinkage_weights_shots_against_the_prior() -> None:
    # 500 shots at .920: (460 + 900) / 1500.
    assert shrunk_save_pct(GoalieRecord(460, 500), LEAGUE) == pytest.approx(1360 / 1500)


def test_hot_goalie_lowers_and_cold_goalie_raises() -> None:
    hot = goalie_multiplier(GoalieRecord(460, 500), LEAGUE)
    cold = goalie_multiplier(GoalieRecord(430, 500), LEAGUE)
    assert hot == pytest.approx((1 - 1360 / 1500) / 0.1)
    assert hot < 1.0 < cold


def test_multiplier_is_clipped_at_both_bounds() -> None:
    assert goalie_multiplier(GoalieRecord(100_000, 100_000), LEAGUE) == adj.MIN_MULTIPLIER
    assert goalie_multiplier(GoalieRecord(0, 100_000), LEAGUE) == adj.MAX_MULTIPLIER


@pytest.mark.parametrize("league", [0.0, 1.0, -0.1, 1.2])
def test_degenerate_league_value_is_rejected(league: float) -> None:
    with pytest.raises(ValueError):
        goalie_multiplier(GoalieRecord(10, 12), league)
    with pytest.raises(ValueError):
        shrunk_save_pct(GoalieRecord(10, 12), league)


def test_beta_zero_returns_the_input() -> None:
    assert adjusted_value(2.4, NhlLineOnlyMarket.POINTS, 1.2, 0.0) == 2.4


def test_beta_scales_by_the_power_of_the_multiplier() -> None:
    assert adjusted_value(2.0, NhlLineOnlyMarket.POINTS, 1.21, 0.5) == pytest.approx(2.2)
    assert adjusted_value(2.0, NhlLineOnlyMarket.SHOTS_ON_GOAL, 0.9, 1.0) == pytest.approx(1.8)


@pytest.mark.parametrize("market", [
    NhlLineOnlyMarket.HITS, NhlLineOnlyMarket.BLOCKED_SHOTS, NhlLineOnlyMarket.TIME_ON_ICE,
    NhlLineOnlyMarket.GOALIE_SAVES, NhlLineOnlyMarket.FACEOFFS_WON, NhlLineOnlyMarket.PLUS_MINUS,
])
def test_markets_outside_the_adjusted_set_are_unchanged(market: NhlLineOnlyMarket) -> None:
    assert adjusted_value(3.0, market, 1.25, 1.0) == 3.0


def test_select_beta_takes_the_lowest_and_breaks_ties_low() -> None:
    assert adj.select_beta({0.0: 1.0, 0.5: 0.9, 1.0: 0.95}) == 0.5
    assert adj.select_beta({0.0: 1.0, 0.5: 0.9, 1.0: 0.9}) == 0.5
    assert adj.select_beta({0.0: 0.9, 0.5: 0.9, 1.0: 0.9}) == 0.0
    with pytest.raises(ValueError):
        adj.select_beta({0.5: 0.9})

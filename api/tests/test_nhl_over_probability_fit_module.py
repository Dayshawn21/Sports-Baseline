import re

from app.backtest.nhl_over_probability_fit import PREREGISTRATION_COMMIT
from app.core import nhl_over_probability as rule
from app.core import nhl_over_probability_fit as generated
from app.nhl.markets import NhlLineOnlyMarket

TABLES = {
    "negbin": generated.NEGBIN_R,
    "scaled_normal": generated.SCALED_NORMAL,
    "ratio": generated.RATIO_QUANTILES,
}
MARKETS = {market.value for market in NhlLineOnlyMarket}


def test_the_generated_module_matches_the_registered_versions_seasons_and_commit() -> None:
    assert generated.FIT_PROJECTION_MODEL_VERSION == rule.NHL_PROJECTION_MODEL_VERSION == "nhl-reference-v1"
    assert generated.OVER_PROBABILITY_VERSION == rule.NHL_OVER_PROBABILITY_VERSION == "nhl-pover-v1"
    assert (generated.FIT_SEASON, generated.SCORED_SEASON) == (rule.FIT_SEASON, rule.CONFIRMATION_SEASON)
    assert generated.PRE_REGISTRATION_COMMIT == PREREGISTRATION_COMMIT
    assert re.fullmatch(r"[0-9a-f]{40}", generated.PRE_REGISTRATION_COMMIT)


def test_shown_markets_are_real_markets_and_each_has_exactly_its_familys_parameters() -> None:
    assert generated.SHOWN_MARKETS <= MARKETS
    assert set(generated.FAMILY_BY_MARKET) == generated.SHOWN_MARKETS
    for market in generated.SHOWN_MARKETS:
        family = generated.FAMILY_BY_MARKET[market]
        assert family in rule.CANDIDATE_ORDER
        assert rule.family_applies(family, NhlLineOnlyMarket(market))
        assert [name for name, table in TABLES.items() if market in table] == [family]


def test_a_hidden_market_has_no_entry_anywhere() -> None:
    for market in MARKETS - generated.SHOWN_MARKETS:
        assert market not in generated.FAMILY_BY_MARKET
        assert all(market not in table for table in TABLES.values())
    assert set().union(*TABLES.values()) == generated.SHOWN_MARKETS


def test_parameters_are_usable() -> None:
    assert all(r > 0 for r in generated.NEGBIN_R.values())
    for a, b in generated.SCALED_NORMAL.values():
        assert a + b * 0.1 > 0
    for quantiles in generated.RATIO_QUANTILES.values():
        assert len(quantiles) == 41 and list(quantiles) == sorted(quantiles)

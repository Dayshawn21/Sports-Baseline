import pytest

from app.config import Settings
from app.core.ask_cost import AskPrices, estimate_cost_usd, max_question_cost_usd
from app.core.ask_messages import AskUsage
from app.services.ask.client import ask_prices, question_reserve_usd

PRICES = AskPrices(input=0.10, output=0.50, cache_read=0.01, cache_write=0.125)


@pytest.mark.parametrize(
    ("usage", "cost"),
    [
        (AskUsage(input_tokens=1_000_000), 0.10),
        (AskUsage(output_tokens=1_000_000), 0.50),
        (AskUsage(cache_read_input_tokens=1_000_000), 0.01),
        (AskUsage(cache_creation_input_tokens=1_000_000), 0.125),
    ],
)
def test_each_token_kind_is_priced_alone(usage, cost):
    assert estimate_cost_usd(usage, PRICES) == pytest.approx(cost)


def test_a_question_sums_every_kind():
    usage = AskUsage(
        requests=2, input_tokens=3_000, output_tokens=400,
        cache_read_input_tokens=5_000, cache_creation_input_tokens=5_000,
    )
    # 0.0003 + 0.0002 + 0.00005 + 0.000625
    assert estimate_cost_usd(usage, PRICES) == pytest.approx(0.001175)


def test_no_usage_costs_nothing():
    assert estimate_cost_usd(AskUsage(), PRICES) == 0.0


def test_prices_come_from_settings():
    settings = Settings(
        database_url="postgresql://localhost/test",
        ask_price_input_per_mtok=1.0, ask_price_output_per_mtok=2.0,
        ask_price_cache_read_per_mtok=3.0, ask_price_cache_write_per_mtok=4.0,
    )
    assert ask_prices(settings) == AskPrices(input=1.0, output=2.0, cache_read=3.0, cache_write=4.0)


def test_the_worst_case_prices_every_request_at_full_output_and_the_assumed_input():
    # Per request: 20,000 input at the $0.125 cache-write rate plus 2,048 output at $0.50.
    assert max_question_cost_usd(PRICES, 6, 2048) == pytest.approx(6 * (0.0025 + 0.001024))


def test_the_reserve_counts_every_tool_round_plus_the_answer():
    settings = Settings(database_url="postgresql://localhost/test", ask_max_tool_iterations=2, ask_max_tokens=1024)
    assert question_reserve_usd(settings) == pytest.approx(max_question_cost_usd(ask_prices(settings), 3, 1024))

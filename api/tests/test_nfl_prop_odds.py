from datetime import datetime, timezone

import pytest

from app.core.nfl_prop_odds import (
    MIN_EXPECTED_SCORERS,
    consensus,
    devigged_book_probabilities,
    expected_distinct_scorers,
    normalize_one_way,
    parse_yes_no_props,
    slate_book_odds,
)

MARKET = "player_anytime_td"


def _book(key: str, outcomes: list[dict[str, object]], market: str = MARKET) -> dict[str, object]:
    return {"key": key, "markets": [{"key": market, "outcomes": outcomes}]}


def test_yes_only_price_keeps_the_raw_implied_probability_and_flags_margin() -> None:
    [price] = parse_yes_no_props([_book("draftkings", [
        {"name": "Yes", "description": "Bijan Robinson", "price": -195},
    ])], [MARKET])

    assert price.player_name == "Bijan Robinson"
    assert price.no_odds is None
    assert price.market_prob == pytest.approx(195 / 295)
    assert price.includes_margin is True


def test_two_sided_price_is_de_vigged() -> None:
    [price] = parse_yes_no_props([_book("fanduel", [
        {"name": "Yes", "description": "Drake London", "price": 175},
        {"name": "No", "description": "Drake London", "price": -250},
    ])], [MARKET])

    yes_raw, no_raw = 100 / 275, 250 / 350
    assert price.no_odds == -250
    assert price.market_prob == pytest.approx(yes_raw / (yes_raw + no_raw))
    assert price.includes_margin is False


def test_malformed_outcomes_and_other_markets_are_skipped() -> None:
    prices = parse_yes_no_props([
        _book("draftkings", [
            {"name": "Yes", "description": "No Price"},
            {"name": "Yes", "description": "Tiny Price", "price": 50},
            {"name": "Yes", "description": "", "price": 150},
            {"name": "No", "description": "No Yes Side", "price": -150},
            "not a mapping",
        ]),
        _book("betmgm", [{"name": "Over", "description": "Chuba Hubbard", "price": -110, "point": 60.5}], "player_rush_yds"),
        {"key": "bovada"},
    ], [MARKET])

    assert prices == []


def test_consensus_of_one_book_is_that_book() -> None:
    result = consensus([(0.4, False)])
    assert result is not None
    assert (result.probability, result.book_count, result.includes_margin) == (0.4, 1, False)


def test_consensus_uses_the_median_and_flags_any_yes_only_book() -> None:
    result = consensus([(0.30, False), (0.36, True), (0.34, False), (0.32, False)])

    assert result is not None
    assert result.probability == pytest.approx(0.33)
    assert result.book_count == 4
    assert result.includes_margin is True


def test_consensus_without_prices_is_unavailable_not_zero() -> None:
    assert consensus([]) is None


EARLY = datetime(2026, 9, 18, 20, 0, tzinfo=timezone.utc)
LATE = datetime(2026, 9, 20, 14, 0, tzinfo=timezone.utc)


def test_slate_book_odds_attaches_consensus_and_newest_fetch_to_full_game_anytime_td() -> None:
    result = slate_book_odds("anytime_touchdown", "full_game", [(0.66, True, EARLY), (0.62, True, LATE), (0.64, True, EARLY)])

    assert result is not None
    assert (result.probability, result.book_count, result.includes_margin, result.fetched_at) == (0.64, 3, True, LATE)


def test_slate_book_odds_is_absent_for_other_markets_segments_and_unpriced_players() -> None:
    rows = [(0.66, True, EARLY)]

    assert slate_book_odds("receiving_yards", "full_game", rows) is None
    assert slate_book_odds("anytime_touchdown", "first_half", rows) is None
    assert slate_book_odds("anytime_touchdown", "full_game", []) is None


def test_normalize_one_way_reduces_the_sum_to_the_target() -> None:
    raw = [0.67, 0.54, 0.41, 0.28, 0.19, 0.12, 0.09]
    normalized = normalize_one_way(raw, 1.8)

    assert sum(normalized) == pytest.approx(1.8, abs=1e-6)
    assert all(new < old for new, old in zip(normalized, raw))


def test_normalize_one_way_preserves_order_and_pulls_long_shots_down_hardest() -> None:
    raw = [0.60, 0.30, 0.10]
    normalized = normalize_one_way(raw, 0.8)

    assert normalized == sorted(normalized, reverse=True)
    # The margin sits disproportionately in the tail, so the long shot loses the
    # largest share of its price even though the favourite loses more absolutely.
    assert (raw[2] - normalized[2]) / raw[2] > (raw[0] - normalized[0]) / raw[0]


def test_normalize_one_way_never_inflates_a_book_already_at_or_under_target() -> None:
    raw = [0.30, 0.20]

    assert normalize_one_way(raw, 0.9) == raw
    assert normalize_one_way(raw, 0.5) == raw


def test_normalize_one_way_passes_through_degenerate_prices() -> None:
    # 0.0 and 1.0 have no exponent that moves them, so they are left alone and
    # excluded from the solve rather than dragging it.
    normalized = normalize_one_way([1.0, 0.5, 0.0, 0.5], 0.6)

    assert normalized[0] == 1.0
    assert normalized[2] == 0.0
    assert sum(normalized[1::2]) == pytest.approx(0.6, abs=1e-6)


def test_normalize_one_way_handles_empty_and_single_inputs() -> None:
    assert normalize_one_way([], 1.0) == []
    assert normalize_one_way([0.5], 0.25) == pytest.approx([0.25], abs=1e-6)


def test_expected_distinct_scorers_tracks_the_fitted_season_means() -> None:
    # The 2024-2025 fit means: 45.92 points gave 4.094 distinct scorers.
    assert expected_distinct_scorers(45.92) == pytest.approx(4.094, abs=0.01)
    assert expected_distinct_scorers(38.5) == pytest.approx(3.37, abs=0.05)
    assert expected_distinct_scorers(52.5) == pytest.approx(4.74, abs=0.05)


def test_expected_distinct_scorers_rises_with_the_total() -> None:
    totals = [34.0, 41.0, 45.0, 48.0, 56.0]
    values = [expected_distinct_scorers(total) for total in totals]

    assert values == sorted(values)
    assert len(set(values)) == len(values)


def test_expected_distinct_scorers_floors_rather_than_going_to_zero() -> None:
    # The fit crosses zero near 4 points, far outside the range it was measured
    # on, and a real game always prices someone to score.
    assert expected_distinct_scorers(3.0) == MIN_EXPECTED_SCORERS
    assert expected_distinct_scorers(0.5) == MIN_EXPECTED_SCORERS


def test_expected_distinct_scorers_is_none_without_a_total() -> None:
    assert expected_distinct_scorers(None) is None
    assert expected_distinct_scorers(0.0) is None


def test_devigged_book_probabilities_normalizes_one_value_per_player() -> None:
    # A realistic board: roughly twenty listed players summing above the target.
    players = {
        11: 0.67, 22: 0.54, 33: 0.45, 44: 0.38, 55: 0.33, 66: 0.30, 77: 0.28,
        88: 0.26, 99: 0.24, 110: 0.22, 121: 0.20, 132: 0.19, 143: 0.17,
        154: 0.15, 165: 0.14, 176: 0.12, 187: 0.11, 198: 0.09, 209: 0.08,
    }
    devigged = devigged_book_probabilities(players, 45.5)

    assert set(devigged) == set(players)
    assert sum(devigged.values()) == pytest.approx(expected_distinct_scorers(45.5), abs=1e-6)
    assert all(devigged[player] < players[player] for player in players)


def test_devigged_book_probabilities_is_empty_without_a_market_total() -> None:
    assert devigged_book_probabilities({11: 0.5, 22: 0.4}, None) == {}


def test_devigged_book_probabilities_leaves_a_sparse_game_alone() -> None:
    # A book listing only a few players can already sum under the target; the
    # no-inflation guard must not invent probability to reach it.
    players = {11: 0.30, 22: 0.20}
    devigged = devigged_book_probabilities(players, 45.5)

    assert devigged == players


def test_devigged_book_probabilities_handles_no_players() -> None:
    assert devigged_book_probabilities({}, 45.5) == {}

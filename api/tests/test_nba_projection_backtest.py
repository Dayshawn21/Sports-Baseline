from datetime import date, timedelta

import pytest

from app.core.nba_line_only import LINE_ONLY_COLUMNS
from app.core import nba_projection_backtest as rule
from app.core.nba_projection_backtest import (
    ARMS, BACKTEST_MARKETS, REFERENCE_ARM, NbaHistoryRow, NbaReplayCase, eligible_minutes, nba_adoption_verdict,
    replay_cases,
)
from app.core.nfl_projection_backtest import PairedDiff, market_metrics, paired
from app.nba.markets import NbaLineOnlyMarket

START = date(2025, 10, 21)


def row(
    day: int, *, player_id: int = 1, game_id: int | None = None, season: int = 2025, did_not_play: bool = False,
    minutes: float | None = 30.0, **stats: int | None,
) -> NbaHistoryRow:
    values: dict[str, int | bool | None] = {column: 1 for column in LINE_ONLY_COLUMNS}
    values.update({"points": 10, "rebounds": 5, "assists": 3})
    values.update(stats)
    if did_not_play:
        values = {column: None for column in LINE_ONLY_COLUMNS}
        minutes = None
    values["did_not_play"] = did_not_play
    return NbaHistoryRow(
        player_id=player_id, game_id=game_id if game_id is not None else 1000 + day * 10 + player_id,
        season=season, game_date=START + timedelta(days=day), game_type="REG",
        did_not_play=did_not_play, minutes=minutes, stats=values,
    )


def history(games: int, **overrides: int | float | None) -> list[NbaHistoryRow]:
    return [row(day, **overrides) for day in range(games)]


def cases_on(history_rows: list[NbaHistoryRow], arm: str = REFERENCE_ARM, season: int = 2025) -> list[NbaReplayCase]:
    return replay_cases(history_rows, season, ARMS[arm])


def points(cases: list[NbaReplayCase], game_id: int) -> NbaReplayCase:
    return next(case for case in cases if case.game_id == game_id and case.market == "points")


def test_backtest_markets_are_the_nine_summed_markets() -> None:
    assert len(BACKTEST_MARKETS) == 9
    assert NbaLineOnlyMarket.DOUBLE_DOUBLE not in BACKTEST_MARKETS


def test_the_eleventh_game_is_the_first_scored() -> None:
    cases = cases_on(history(11))
    assert {case.game_id for case in cases} == {row(10).game_id}
    assert {case.market for case in cases} == {market.value for market in BACKTEST_MARKETS}


def test_a_same_date_game_is_never_an_input() -> None:
    rows = history(10) + [row(10, game_id=1, points=50), row(10, game_id=2, points=10)]
    cases = cases_on(rows)
    # Ten prior games, both scored from them alone: the earlier game that day is not an input.
    assert points(cases, 1).projection == points(cases, 2).projection == 10.0


def test_dnp_games_are_neither_inputs_nor_cases() -> None:
    rows = history(10) + [row(10, did_not_play=True), row(11, points=40)]
    cases = cases_on(rows)
    assert row(10, did_not_play=True).game_id not in {case.game_id for case in cases}
    assert points(cases, row(11).game_id).projection == 10.0


def test_a_window_crosses_into_the_prior_season() -> None:
    rows = [row(day - 30, season=2024, points=20) for day in range(10)] + [row(0, season=2025, points=12)]
    cases = cases_on(rows)
    assert points(cases, row(0).game_id).projection == 20.0
    assert not cases_on(rows, season=2024)


def test_eligibility_needs_ten_prior_games() -> None:
    assert eligible_minutes(row(9), history(9)) is None
    assert eligible_minutes(row(10), history(10)) == 30.0


def test_eligibility_needs_twenty_prior_minutes() -> None:
    assert eligible_minutes(row(10), history(10, minutes=20.0)) == 20.0
    assert eligible_minutes(row(10), history(10, minutes=19.9)) is None


def test_null_minutes_are_ignored_in_the_minutes_mean() -> None:
    prior = history(8, minutes=24.0) + [row(8, minutes=None), row(9, minutes=None)]
    assert eligible_minutes(row(10), prior) == 24.0
    assert eligible_minutes(row(10), history(10, minutes=None)) is None


def test_minutes_use_only_the_last_ten_prior_games() -> None:
    prior = history(5, minutes=10.0) + [row(day, minutes=25.0) for day in range(5, 15)]
    assert eligible_minutes(row(15), prior) == 25.0


def test_a_null_stat_is_skipped_in_the_mean_and_as_an_actual() -> None:
    rows = history(9) + [row(9, points=None), row(10, points=16), row(11, points=None)]
    cases = cases_on(rows)
    assert points(cases, row(10).game_id).projection == 10.0
    assert not [case for case in cases if case.game_id == row(11).game_id and case.market == "points"]
    assert [case for case in cases if case.game_id == row(11).game_id and case.market == "rebounds"]


def test_a_combo_equals_the_sum_of_its_components() -> None:
    rows = [row(day, points=10 + day, rebounds=day % 4, assists=2) for day in range(15)]
    by_market = {case.market: case.projection for case in cases_on(rows) if case.game_id == rows[-1].game_id}
    assert by_market["points_rebounds_assists"] == pytest.approx(
        by_market["points"] + by_market["rebounds"] + by_market["assists"])
    assert by_market["points_rebounds"] == pytest.approx(by_market["points"] + by_market["rebounds"])


def test_reference_averages_the_last_twenty_and_last_10_the_last_ten() -> None:
    rows = [row(day, points=day) for day in range(25)] + [row(25)]
    target = row(25).game_id
    assert points(cases_on(rows), target).projection == pytest.approx(sum(range(5, 25)) / 20)
    assert points(cases_on(rows, "last_10"), target).projection == pytest.approx(sum(range(15, 25)) / 10)


def test_reference_uses_every_prior_game_below_twenty() -> None:
    rows = [row(day, points=day) for day in range(12)] + [row(12)]
    assert points(cases_on(rows), row(12).game_id).projection == pytest.approx(sum(range(12)) / 12)


def test_a_case_carries_its_error_key_and_prior_minutes() -> None:
    case = points(cases_on(history(10) + [row(10, points=14)]), row(10).game_id)
    assert case.key == (1, row(10).game_id, "points")
    assert case.error == -4.0
    assert case.prior_minutes == 30.0


def test_players_are_walked_independently() -> None:
    rows = sorted(history(11) + [row(day, player_id=2, points=20) for day in range(11)], key=lambda r: r.game_date)
    cases = cases_on(rows)
    assert points(cases, row(10).game_id).projection == 10.0
    assert points(cases, row(10, player_id=2).game_id).projection == 20.0


def diff(n: int = 300, change: float = -0.01, mean_diff: float = -0.2, se: float = 0.1) -> PairedDiff:
    return PairedDiff(
        n=n, production_mae=5.0, variant_mae=5.0 * (1 + change),
        mean_diff=mean_diff, standard_error=se, relative_mae_change=change,
    )


def test_the_pre_registered_rule_is_pinned() -> None:
    assert (rule.MIN_PAIRED_CASES, rule.MIN_RELATIVE_MAE_IMPROVEMENT, rule.STANDARD_ERRORS_REQUIRED) == (300, 0.01, 2.0)
    assert (rule.REFERENCE_ARM, rule.HOLDOUT_SEASON, rule.DEVELOPMENT_SEASON) == ("reference", 2025, 2024)
    assert (rule.MIN_PRIOR_GAMES, rule.MIN_PRIOR_MINUTES) == (10, 20.0)


def test_verdict_needs_three_hundred_paired_cases() -> None:
    assert nba_adoption_verdict(diff(n=299)) == "insufficient"
    assert nba_adoption_verdict(diff(n=300, mean_diff=-0.21)) == "adopt"


def test_verdict_adopts_at_exactly_one_percent() -> None:
    assert nba_adoption_verdict(diff(change=-0.01, mean_diff=-0.21)) == "adopt"
    assert nba_adoption_verdict(diff(change=-0.0099, mean_diff=-0.21)) == "reject"


def test_verdict_needs_more_than_two_standard_errors() -> None:
    assert nba_adoption_verdict(diff(change=-0.05, mean_diff=-0.2, se=0.1)) == "reject"
    assert nba_adoption_verdict(diff(change=-0.05, mean_diff=-0.2001, se=0.1)) == "adopt"


def test_verdict_rejects_a_worse_variant() -> None:
    assert nba_adoption_verdict(diff(change=0.02, mean_diff=0.3)) == "reject"


def test_nba_cases_run_through_the_shared_metrics() -> None:
    rows = [row(day, points=day % 5 * 4) for day in range(30)]
    reference = cases_on(rows)
    last_10 = cases_on(rows, "last_10")
    metrics = market_metrics([case for case in reference if case.market == "points"])
    assert metrics.n == 20
    comparison = paired(reference, last_10)
    assert comparison.n == len(reference) == len(last_10)

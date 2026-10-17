import pytest

from app.backtest.nfl_prop_market import report
from app.core.nfl_prop_market import (
    ARMS,
    PropCase,
    PropCoverage,
    PropOutcome,
    SettledPropRow,
    build_prop_cases,
    by_week,
    coverage,
    score_arm,
    settle,
)


def _case(outcome: PropOutcome, book_devig: float | None = 0.3, model: float | None = 0.25) -> PropCase:
    return PropCase(1, 10, 2026, 2, outcome, 0.35, book_devig, model)


def test_a_stat_row_with_a_touchdown_settles_as_scored() -> None:
    assert settle(1, None) is PropOutcome.SCORED
    assert settle(3, 42) is PropOutcome.SCORED


def test_a_stat_row_without_a_touchdown_settles_as_a_miss() -> None:
    assert settle(0, None) is PropOutcome.NOT_SCORED
    assert settle(0, 0) is PropOutcome.NOT_SCORED


def test_snaps_without_a_stat_row_settle_as_a_miss() -> None:
    assert settle(None, 12) is PropOutcome.NOT_SCORED


def test_no_stat_row_and_no_snaps_is_not_a_miss() -> None:
    assert settle(None, None) is PropOutcome.DID_NOT_PLAY


def test_a_snap_row_of_zero_without_a_stat_row_is_not_a_miss() -> None:
    assert settle(None, 0) is PropOutcome.DID_NOT_PLAY


def test_only_a_scored_outcome_counts_as_a_hit() -> None:
    assert _case(PropOutcome.SCORED).scored
    assert not _case(PropOutcome.NOT_SCORED).scored
    assert not _case(PropOutcome.DID_NOT_PLAY).scored


def test_a_voided_case_is_neither_settled_nor_in_the_common_subset() -> None:
    voided = _case(PropOutcome.DID_NOT_PLAY)
    assert not voided.is_settled
    assert not voided.in_common_subset


def test_the_common_subset_needs_every_arm() -> None:
    assert _case(PropOutcome.NOT_SCORED).in_common_subset
    assert not _case(PropOutcome.NOT_SCORED, book_devig=None).in_common_subset
    assert not _case(PropOutcome.SCORED, model=None).in_common_subset


def _row(
    player_id: int | None, probability: float, touchdowns: int | None = 0, *,
    game_id: int = 10, week: int = 2, total_line: float | None = 45.5,
    offense_snaps: int | None = None, includes_margin: bool = True,
) -> SettledPropRow:
    return SettledPropRow(
        game_id=game_id, season=2026, week=week, player_id=player_id,
        provider_player_name=f"Player {player_id}", book_probability=probability,
        book_count=3, includes_margin=includes_margin, total_line=total_line,
        total_source=None if total_line is None else "book",
        touchdowns=touchdowns, offense_snaps=offense_snaps,
    )


def test_unresolved_rows_leave_the_sample_but_stay_in_coverage() -> None:
    rows = [_row(1, 0.5), _row(None, 0.4)]
    cases = build_prop_cases(rows, {})
    assert [case.player_id for case in cases] == [1]
    counts = coverage(rows, cases)
    assert (counts.priced_player_games, counts.unresolved, counts.settled) == (2, 1, 1)


def _priced_game(player_ids: range, probability: float, game_id: int = 10) -> list[SettledPropRow]:
    """A game priced like a real one: enough players that the Yes prices carry a margin."""
    return [_row(player_id, probability, game_id=game_id) for player_id in player_ids]


def test_de_vig_runs_per_game_and_pulls_prices_below_the_raw_price() -> None:
    # 20 players at 0.25 sum to 5.0, over the 4.05 scorers a 45.5 total expects.
    rows = [*_priced_game(range(1, 21), 0.25), _row(99, 0.4, game_id=11)]
    cases = {case.player_id: case for case in build_prop_cases(rows, {})}
    assert all(cases[player_id].book_devig < cases[player_id].book_raw for player_id in range(1, 21))
    # A lone priced player in a game sums under the target, so there is no margin to remove.
    assert cases[99].book_devig == cases[99].book_raw


def test_a_game_without_a_total_gets_no_de_vigged_arm() -> None:
    [case] = build_prop_cases([_row(1, 0.6, total_line=None)], {})
    assert case.book_devig is None
    assert coverage([_row(1, 0.6, total_line=None)], [case]).missing_total == 1


def test_a_case_without_history_keeps_its_book_arms_but_no_model() -> None:
    rows = [_row(1, 0.6), _row(2, 0.5)]
    cases = build_prop_cases(rows, {(1, 2026, 2): 0.42})
    assert [case.model for case in cases] == [0.42, None]
    counts = coverage(rows, cases)
    assert (counts.missing_model, counts.common_subset) == (1, 1)


def test_arms_score_only_the_common_subset() -> None:
    rows = _priced_game(range(1, 21), 0.25)
    rows[0] = _row(1, 0.25, touchdowns=1)
    # Player 20 has no model probability, so no arm may score it.
    model = {(player_id, 2026, 2): 0.2 for player_id in range(1, 20)}
    cases = build_prop_cases(rows, model)
    scores = {arm: score_arm(cases, arm) for arm in ARMS}
    assert {score.games for score in scores.values()} == {19}
    assert scores["model"].mean_predicted == pytest.approx(0.2)
    assert scores["book_raw"].mean_predicted > scores["book_devig"].mean_predicted


def test_a_voided_player_game_is_scored_by_nobody() -> None:
    rows = [_row(1, 0.6, touchdowns=None), _row(2, 0.5, touchdowns=0)]
    cases = build_prop_cases(rows, {(1, 2026, 2): 0.5, (2, 2026, 2): 0.4})
    counts = coverage(rows, cases)
    assert (counts.did_not_play, counts.settled, counts.common_subset) == (1, 1, 1)
    assert score_arm(cases, "book_raw").games == 1


def test_weeks_group_in_order() -> None:
    rows = [_row(1, 0.6, week=3, game_id=12), _row(2, 0.5, week=2)]
    weeks = by_week(build_prop_cases(rows, {}))
    assert [key for key, _ in weeks] == [(2026, 2), (2026, 3)]


def test_an_empty_sample_scores_nothing_instead_of_dividing_by_zero() -> None:
    assert build_prop_cases([], {}) == []
    assert all(score_arm([], arm) is None for arm in ARMS)
    assert coverage([], []) == PropCoverage(0, 0, 0, 0, 0, 0, 0)


def test_the_report_reads_at_zero_and_never_prints_nan() -> None:
    printed = report([], [])
    assert "Sample not yet assessable: 0 of 2000" in printed
    assert "no settled cases" in printed
    assert "nan" not in printed.lower()


def test_the_report_prints_a_row_per_week_once_cases_settle() -> None:
    rows = [_row(1, 0.6, touchdowns=1), _row(2, 0.5, touchdowns=0, week=3, game_id=12)]
    cases = build_prop_cases(rows, {(1, 2026, 2): 0.5, (2, 2026, 3): 0.4})
    printed = report(rows, cases)
    assert "2026 w2" in printed and "2026 w3" in printed
    assert "common subset              2" in printed

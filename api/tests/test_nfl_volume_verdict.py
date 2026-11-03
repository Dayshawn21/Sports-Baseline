import ast
import math
from collections.abc import Sequence
from pathlib import Path

import pytest

from app.core import nfl_volume_anchor as anchor
from app.core import nfl_volume_verdict as verdict
from app.core.nfl_volume_backtest import clustered_se
from app.core.prop_ranking_check import SLICES
from app.core.prop_ranking_rule import FrozenCall, Pick, to_pick

PER_WEEK = 50


def _picks(weeks: Sequence[int], hit_share: float = 0.8, per_week: int = PER_WEEK, offset: int = 0) -> list[Pick]:
    picks: list[Pick] = []
    for week in weeks:
        for index in range(per_week):
            hit = index < hit_share * per_week
            call = FrozenCall(
                line_id=offset + week * 1000 + index, period=week, player_id=offset + week * 1000 + index,
                game_id=offset + week * 1000 + index // 5, market="receptions", odds_type="standard",
                p_over=0.7, p_under=0.3, outcome="over" if hit else "under",
            )
            pick = to_pick(call)
            assert pick is not None
            picks.append(pick)
    return picks


def _rows(
    weeks: Sequence[int], per_week: int = 100, p_over: float = 0.65, over_share: float = 0.65, q_vol: float = 0.9,
    offset: int = 0, rows_per_game: int = 1,
) -> list[verdict.LogLossRow]:
    rows = []
    for week in weeks:
        for index in range(per_week):
            outcome = "over" if (index % 100) < over_share * 100 else "under"
            rows.append(verdict.LogLossRow(
                game_id=offset + week * 1000 + index // rows_per_game, week=week, p_over=p_over,
                p_under=1.0 - p_over, q_vol=q_vol, outcome=outcome,
            ))
    return rows


def _decide(picks: list[Pick], rows: list[verdict.LogLossRow]) -> verdict.VolumeSliceVerdict:
    return verdict.volume_slice_verdict("standard", picks, rows)


def test_both_clauses_passing_adopts_on_the_fixed_sample() -> None:
    result = _decide(_picks([1, 2, 3, 4]), _rows([1, 2, 3, 4]))

    assert result.verdict == "adopt"
    assert result.picks.verdict == "adopt" and result.picks.n == 200
    assert result.log_loss is not None and result.log_loss.passed
    assert result.log_loss.weeks_won == 4 and result.log_loss.weeks_required == 3
    assert result.log_loss.blend < result.log_loss.half < result.log_loss.raw


def test_the_pick_rule_failing_alone_blocks_adopt() -> None:
    result = _decide(_picks([1, 2, 3, 4], hit_share=0.5), _rows([1, 2, 3, 4]))

    assert result.log_loss is not None and result.log_loss.passed
    assert result.picks.verdict == "reject" and result.verdict == "reject"


def test_the_log_loss_failing_alone_blocks_adopt() -> None:
    result = _decide(_picks([1, 2, 3, 4]), _rows([1, 2, 3, 4], p_over=0.5, over_share=0.5, q_vol=0.5))

    assert result.picks.verdict == "adopt"
    assert result.log_loss is not None and not result.log_loss.passed
    assert result.verdict == "reject"


def test_beating_the_raw_probability_but_not_a_coin_flip_is_not_enough() -> None:
    result = _decide(_picks([1, 2, 3, 4]), _rows([1, 2, 3, 4], p_over=0.5, over_share=0.5, q_vol=0.9))

    assert result.log_loss is not None
    assert result.log_loss.raw_difference is not None and result.log_loss.raw_difference < 0
    assert result.log_loss.half_difference == pytest.approx(0.0, abs=1e-9)
    assert not result.log_loss.passed and result.verdict == "reject"


def test_winning_fewer_than_three_of_four_weeks_fails_even_when_the_pool_wins() -> None:
    good = _rows([1, 2], p_over=0.8, over_share=0.8, q_vol=0.5)
    bad = _rows([3, 4], p_over=0.65, over_share=0.45, q_vol=0.5)
    clause = verdict.log_loss_clause(good + bad, [1, 2, 3, 4])

    assert clause.raw_difference is not None and clause.raw_standard_error is not None
    assert clause.raw_difference < -2 * clause.raw_standard_error
    assert clause.weeks_won == 2 and clause.weeks_required == 3 and not clause.passed


def test_the_weeks_required_scale_from_three_of_four() -> None:
    assert [verdict._weeks_required(weeks) for weeks in (4, 5, 8)] == [3, 4, 6]


def test_the_verdict_stays_insufficient_until_the_pick_sample_is_fixed() -> None:
    result = _decide(_picks([1, 2, 3]), _rows([1, 2, 3, 4]))

    assert result.verdict == "insufficient" and result.log_loss is None
    assert result.picks.n == 150 and result.picks.periods == 3


def test_fewer_than_two_hundred_picks_stays_insufficient_over_many_weeks() -> None:
    result = _decide(_picks([1, 2, 3, 4, 5], per_week=30), _rows([1, 2, 3, 4, 5]))
    assert result.verdict == "insufficient" and result.picks.n == 150 and result.picks.periods == 5


def test_later_weeks_never_change_a_fixed_verdict() -> None:
    picks = _picks([1, 2, 3, 4])
    rows = _rows([1, 2, 3, 4])
    fixed = _decide(picks, rows)
    later = _decide(
        picks + _picks([5, 6], hit_share=0.0, offset=100000),
        rows + _rows([5, 6], p_over=0.9, over_share=0.0, offset=100000),
    )

    assert fixed.verdict == "adopt" and later == fixed


def test_pushes_are_left_out_of_the_log_loss() -> None:
    rows = _rows([1, 2, 3, 4])
    pushes = [verdict.LogLossRow(900000 + i, 1, 0.5, 0.5, 0.5, "push") for i in range(50)]

    assert verdict.log_loss_clause(rows + pushes, [1, 2, 3, 4]) == verdict.log_loss_clause(rows, [1, 2, 3, 4])
    assert verdict.log_loss_clause(rows + pushes, [1, 2, 3, 4]).n == 400


def test_rows_from_weeks_outside_the_sample_are_left_out() -> None:
    rows = _rows([1, 2, 3, 4]) + _rows([9], offset=500000)
    assert verdict.log_loss_clause(rows, [1, 2, 3, 4]).n == 400


def test_the_standard_error_is_clustered_by_game() -> None:
    rows = _rows([1, 2, 3, 4], per_week=100, rows_per_game=4)
    clause = verdict.log_loss_clause(rows, [1, 2, 3, 4])
    unclustered = verdict.log_loss_clause(_rows([1, 2, 3, 4]), [1, 2, 3, 4])

    blend = [-math.log(0.65 if row.outcome == "over" else 0.35) for row in rows]
    half = [math.log(2.0)] * len(rows)
    expected = clustered_se([b - h for b, h in zip(blend, half)], [row.game_id for row in rows])
    assert clause.half_standard_error == pytest.approx(expected)
    assert clause.half_standard_error is not None and unclustered.half_standard_error is not None
    assert clause.half_standard_error > unclustered.half_standard_error


def test_an_empty_slice_and_an_empty_clause_are_ordinary() -> None:
    empty = _decide([], [])
    clause = verdict.log_loss_clause([], [])

    assert empty.verdict == "insufficient" and empty.picks.n == 0 and empty.log_loss is None
    assert empty.picks.break_even == pytest.approx(1 / 1.732)
    assert clause.n == 0 and clause.blend is None and not clause.passed


def test_a_single_game_cannot_produce_a_clustered_standard_error() -> None:
    rows = [verdict.LogLossRow(1, 1, 0.65, 0.35, 0.9, "over") for _ in range(20)]
    clause = verdict.log_loss_clause(rows, [1])
    assert clause.raw_standard_error is None and not clause.passed


def test_only_the_standard_slices_are_evaluated_and_the_others_are_not_frozen() -> None:
    assert set(verdict.EVALUATED_SLICES) | set(verdict.NOT_FROZEN_SLICES) == set(SLICES)
    assert not set(verdict.EVALUATED_SLICES) & set(verdict.NOT_FROZEN_SLICES)
    assert verdict.EVALUATED_SLICES == (("standard", "over"), ("standard", "under"))


def test_the_module_adds_no_threshold_of_its_own() -> None:
    tree = ast.parse(Path(verdict.__file__).read_text(encoding="utf-8"))
    literals = [
        node.targets[0].id if isinstance(node, ast.Assign) else node.target.id
        for node in tree.body if isinstance(node, (ast.Assign, ast.AnnAssign))
        and any(isinstance(part, ast.Constant) and isinstance(part.value, (int, float)) for part in ast.walk(node))
    ]
    assert literals == []
    assert verdict.LOG_LOSS_MIN_WEEKS_WON is anchor.LOG_LOSS_MIN_WEEKS_WON
    assert verdict.LOG_LOSS_STANDARD_ERRORS is anchor.LOG_LOSS_STANDARD_ERRORS
    assert (anchor.LOG_LOSS_STANDARD_ERRORS, anchor.LOG_LOSS_MIN_WEEKS_WON) == (2.0, 3)

import asyncio

from app.core.prop_ranking_check import FrozenLine
from app.core.prop_sports import FULL_GAME_SEGMENT, SportPropConfig
from app.services.prop_ranking import load_ranking_calls

TOY = SportPropConfig("toy", "TOY", {}, frozenset({FULL_GAME_SEGMENT}), {}, "round")


def _frozen(line_id: int, period: int, outcome: str = "over", model: str = "toy-v1") -> FrozenLine:
    return FrozenLine(line_id, period, line_id, 100 + line_id, "points", "standard", outcome, 0.7, 0.3, model, None)


class _Source:
    config = TOY
    model_version = "toy-v1"
    over_probability_version = "toy-pover-v1"

    async def frozen_lines(self, db, season):
        return [_frozen(1, 1), _frozen(2, 2), _frozen(3, 1, "void_dnp"), _frozen(4, 1, model="toy-v0")]

    async def finished_periods(self, db, season):
        return {1}

    async def frozen_coverage(self, db, season):
        return {1: (5, 4), 2: (3, 1)}


def test_the_loader_grades_through_the_source_and_names_periods_after_the_sport() -> None:
    loaded = asyncio.run(load_ranking_calls(object(), _Source(), 2026))

    assert [(call.line_id, call.period, call.outcome) for call in loaded.calls] == [(1, 1, "over")]
    assert loaded.exclusions == {"round_not_finished": 1, "void_dnp": 1, "wrong_version": 1}
    assert (loaded.frozen_rows, loaded.finished_periods) == (4, {1})
    assert loaded.coverage == {1: (5, 4), 2: (3, 1)}

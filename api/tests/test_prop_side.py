"""A prop's side must be the likelier outcome, since that is what its confidence grades."""
import math
from dataclasses import replace

from app.core.prop_probs import prop_probabilities, prop_side
from app.routers.props import _enrich
from tests.test_props_audit_projection import _prop, _stats


def test_a_skewed_count_just_over_the_line_is_still_likelier_under():
    probs = prop_probabilities("aces", 5.5, 5.6)
    assert probs.p_under > probs.p_over
    assert prop_side(probs.p_over, probs.p_under) == "UNDER"


def test_ties_go_over():
    assert prop_side(0.5, 0.5) == "OVER"


def _just_over_a_half_line() -> tuple[object, float]:
    """Stats whose aces projection sits a hair above a .5 line."""
    for rate in (x / 1000 for x in range(60, 260)):
        stats = _stats(aces_per_game=rate)
        mean = _enrich(_prop("0.5"), stats, _stats(2)).stat_avg
        line = math.floor(mean - 0.5) + 0.5
        if 0 < mean - line < 0.1 and line > 2:
            return stats, line
    raise AssertionError("no aces rate put the projection just above a half line")


def test_router_recommends_the_likelier_side_not_the_side_of_the_mean():
    stats, line = _just_over_a_half_line()
    row = _enrich(_prop(str(line)), stats, _stats(2))
    assert row.stat_avg > line
    assert row.p_under > row.p_over
    assert row.recommendation == "UNDER"


def test_demon_and_goblin_stay_over():
    stats, line = _just_over_a_half_line()
    for odds_type in ("demon", "goblin"):
        row = _enrich(replace(_prop(str(line)), odds_type=odds_type), stats, _stats(2))
        assert row.recommendation == "OVER"

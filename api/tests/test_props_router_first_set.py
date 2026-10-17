"""First-set lines (16e) are projected from the chain, flagged ungraded, and never above LEAN."""
import pytest

from app.core.tennis_first_set import first_set_distribution, pmf_probabilities
from app.core.prop_projection import serve_hold
from tests.test_props_router_best_of import _enriched, _stats


@pytest.mark.parametrize(("stat", "line"), [("1st Set Total Games", "9.5"), ("1st Set Total Games Won", "4.5")])
def test_first_set_lines_are_projected_flagged_and_capped(stat: str, line: str) -> None:
    enriched = _enriched(stat, line, 3)

    assert enriched.projection_status == "ok"
    assert enriched.stat_avg is not None
    assert "ungraded_stat" in enriched.data_quality_flags
    assert "unsupported_stat" not in enriched.data_quality_flags
    assert enriched.recommendation in ("OVER", "UNDER")
    assert enriched.confidence in (None, "PASS", "LEAN")
    assert set(enriched.projection_inputs) >= {"player_hold", "opponent_hold"}


def test_first_set_probabilities_come_from_the_chain() -> None:
    enriched = _enriched("1st Set Total Games", "9.5", 3)

    dist = first_set_distribution(serve_hold(_stats()), serve_hold(_stats(2)))
    expected = pmf_probabilities(dist.total_games, 9.5)
    assert enriched.p_over == pytest.approx(expected.p_over, abs=0.001)
    assert enriched.p_push == 0.0
    assert enriched.stat_avg == pytest.approx(dist.mean_total_games, abs=0.01)


def test_other_stats_carry_no_ungraded_flag() -> None:
    assert "ungraded_stat" not in _enriched("Total Games", "22.5", 3).data_quality_flags


def test_a_near_certain_first_set_line_is_still_only_lean() -> None:
    enriched = _enriched("1st Set Total Games", "6.5", 3)

    assert enriched.hit_probability is not None and enriched.hit_probability > 0.95
    assert enriched.confidence == "LEAN"
    # The same certainty on a graded stat reaches LOCK, so the cap is what holds it.
    assert _enriched("Total Games", "12.5", 3).confidence == "LOCK"

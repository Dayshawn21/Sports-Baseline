"""props-v3 (45a): no_market_total, the LEAN ceiling and the version pin."""
from dataclasses import replace

import pytest

from app.core.prop_projection import TOTALS_DEPENDENT_STATS
from app.core.track_record import TIER_RULE_VERSION
from app.routers.props import _enrich
from app.services.tennis.best_picks import generate_prop_picks
from app.services.tennis.prop_snapshots import PROJECTION_VERSION
from tests.test_best_picks import _board_and_cards, _parity_prop, _pred
from tests.test_props_audit_projection import _prop, _stats


def _row(stat_type: str, line: str, total: float | None):
    prop = replace(_prop(line), stat_type=stat_type, best_of=3, player_tour="ATP")
    return _enrich(prop, _stats(), _stats(2), 0.6, market_total_games=total)


@pytest.mark.parametrize("stat", ["Total Games", "Total Games Won", "Aces", "Double Faults",
                                  "Break Points Won", "Fantasy Score"])
def test_a_totals_based_prop_without_a_book_total_is_flagged_pass(stat):
    row = _row(stat, "5.5", None)
    assert "no_market_total" in row.data_quality_flags
    assert row.confidence == "PASS"
    assert row.stat_avg is not None


def test_a_book_total_clears_the_flag():
    assert "no_market_total" not in _row("Aces", "5.5", 22.5).data_quality_flags


@pytest.mark.parametrize("stat", ["1st Set Total Games", "1st Set Total Games Won", "Total Sets"])
def test_stats_that_ignore_the_total_are_not_flagged(stat):
    assert "no_market_total" not in _row(stat, "4.5", None).data_quality_flags


def test_the_flagged_stat_list_is_one_constant():
    assert TOTALS_DEPENDENT_STATS >= {"total_games", "total_games_won", "aces", "double_faults",
                                      "break_points_won", "fantasy_score"}


@pytest.mark.parametrize("line", ["0.5", "2.5", "12.5", "30.5"])
def test_no_tennis_prop_reaches_lock_or_strong(line):
    for stat in ("Total Games", "Aces", "Total Games Won"):
        assert _row(stat, line, 22.5).confidence in (None, "PASS", "LEAN")


def test_best_picks_never_take_a_flagged_prop():
    board, cards = _board_and_cards(_parity_prop("Aces", "2.5"), totals={})
    assert "no_market_total" in board.data_quality_flags
    assert cards == []
    assert generate_prop_picks(_pred(), [board]) == []


def test_version_is_props_v3_for_projection_and_tier_rule():
    assert PROJECTION_VERSION == TIER_RULE_VERSION == "props-v3"

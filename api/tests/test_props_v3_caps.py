"""props-v3 (48a): no_market_total and the version pin; no tennis prop carries a tier (48f)."""
from dataclasses import replace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.prop_projection import TOTALS_DEPENDENT_STATS
from app.core.track_record import TIER_RULE_VERSION
from app.db.pool import get_db
from app.routers import props as props_router
from app.routers.props import _enrich
from app.services.tennis.prop_snapshots import PROJECTION_VERSION
from tests.test_props_audit_projection import _prop, _stats


def _row(stat_type: str, line: str, total: float | None, **overrides):
    prop = replace(_prop(line), stat_type=stat_type, best_of=3, player_tour="ATP", **overrides)
    return _enrich(prop, _stats(), _stats(2), 0.6, market_total_games=total)


@pytest.mark.parametrize("stat", ["Total Games", "Total Games Won", "Aces", "Double Faults",
                                  "Break Points Won", "Fantasy Score"])
def test_a_totals_based_prop_without_a_book_total_is_flagged(stat):
    row = _row(stat, "5.5", None)
    assert "no_market_total" in row.data_quality_flags
    assert row.stat_avg is not None


def test_a_book_total_clears_the_flag():
    assert "no_market_total" not in _row("Aces", "5.5", 22.5).data_quality_flags


@pytest.mark.parametrize("stat", ["1st Set Total Games", "1st Set Total Games Won", "Total Sets"])
def test_stats_that_ignore_the_total_are_not_flagged(stat):
    assert "no_market_total" not in _row(stat, "4.5", None).data_quality_flags


def test_the_flagged_stat_list_is_one_constant():
    assert TOTALS_DEPENDENT_STATS >= {"total_games", "total_games_won", "aces", "double_faults",
                                      "break_points_won", "fantasy_score"}


# Pinned from master before 48f removed the tiers, so these prove no math moved.
@pytest.mark.parametrize(
    ("case", "stat", "line", "total", "overrides", "p_over", "hit", "flags", "side"),
    [
        ("complete", "Aces", "5.5", 22.5, {}, 0.988, 0.988, [], "OVER"),
        ("no_market_total", "Aces", "5.5", None, {}, 0.995, 0.995, ["no_market_total"], "OVER"),
        ("ungraded_first_set", "1st Set Total Games", "9.5", None, {}, 0.624, 0.624, ["ungraded_stat"], "OVER"),
        ("hard_blocked", "Aces", "5.5", 22.5, {"match_link_invalid": True}, 0.988, 0.988,
         ["match_link_invalid"], None),
    ],
)
def test_tennis_prop_lines_carry_no_tier(case, stat, line, total, overrides, p_over, hit, flags, side):
    row = _row(stat, line, total, **overrides)

    assert row.confidence is None
    assert (row.p_over, row.hit_probability, row.break_even_pct) == (p_over, hit, 57.7)
    assert row.data_quality_flags == flags
    assert row.recommendation == side


def test_version_is_props_v3_for_projection_and_tier_rule():
    assert PROJECTION_VERSION == TIER_RULE_VERSION == "props-v3"


def test_the_tier_ranked_top_props_route_is_gone():
    app = FastAPI()
    app.include_router(props_router.router, prefix="/tennis/props")
    app.dependency_overrides[get_db] = lambda: None

    assert TestClient(app).get("/tennis/props/top").status_code == 404

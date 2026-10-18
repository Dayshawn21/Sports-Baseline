from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.core.nfl_line_grading import (
    STAT_COLUMN_BY_MARKET, GradeableLine, HitSummary, LineResult, RateSummary, edge_bucket, model_hits,
    over_probability_reads, rate,
    reference_lines, settle_line,
)
from app.nfl.markets import NflPropMarket

FETCHED = datetime(2026, 9, 20, 15, 0, tzinfo=UTC)


def _line(line_id: int = 1, **overrides: object) -> GradeableLine:
    base = GradeableLine(
        line_id=line_id, season=2026, week=2, game_id=3, player_id=9, market="receptions",
        segment="full_game", odds_type="standard", line=4.5, fetched_at=FETCHED,
        stat_value=6.0, offense_snaps=51, game_has_stats=True,
    )
    return replace(base, **overrides)


def test_every_supported_market_settles_on_a_weekly_stat_column() -> None:
    assert set(STAT_COLUMN_BY_MARKET) == set(NflPropMarket)
    assert STAT_COLUMN_BY_MARKET[NflPropMarket.ANYTIME_TOUCHDOWN] == "touchdowns"


@pytest.mark.parametrize("stat, expected", [(6.0, "over"), (3.0, "under"), (4.5, "push")])
def test_a_line_settles_over_under_or_push_on_its_stat(stat: float, expected: str) -> None:
    result = settle_line(_line(stat_value=stat))

    assert (result.outcome, result.actual) == (expected, stat)


def test_anytime_td_scores_over_its_half_line_on_any_touchdown() -> None:
    scored = settle_line(_line(market="anytime_touchdown", line=0.5, stat_value=2.0))
    blanked = settle_line(_line(market="anytime_touchdown", line=0.5, stat_value=0.0))

    assert (scored.outcome, blanked.outcome) == ("over", "under")


def test_snaps_without_a_stat_row_settle_as_zero() -> None:
    result = settle_line(_line(market="receiving_yards", line=12.5, stat_value=None, offense_snaps=38))

    assert (result.outcome, result.actual) == ("under", 0.0)


@pytest.mark.parametrize("snaps", [None, 0])
def test_no_stat_row_and_no_snaps_is_a_void_not_an_under(snaps: int | None) -> None:
    result = settle_line(_line(stat_value=None, offense_snaps=snaps))

    assert (result.outcome, result.actual) == ("void_dnp", None)


def test_a_game_without_loaded_stats_is_not_read_as_everyone_sitting() -> None:
    assert settle_line(_line(stat_value=None, offense_snaps=None, game_has_stats=False)).outcome == "week_not_loaded"


def test_snaps_on_a_game_without_loaded_stats_are_not_read_as_zero() -> None:
    result = settle_line(_line(stat_value=None, offense_snaps=44, game_has_stats=False))

    assert (result.outcome, result.actual) == ("week_not_loaded", None)


def test_a_first_half_line_is_counted_but_not_settled() -> None:
    result = settle_line(_line(segment="first_half"))

    assert (result.outcome, result.actual) == ("unsettleable_segment", None)


def test_rate_counts_outcomes_and_ignores_unsettled_lines() -> None:
    results = [
        LineResult(_line(1), "over", 6.0), LineResult(_line(2), "over", 6.0), LineResult(_line(3), "under", 3.0),
        LineResult(_line(4), "push", 4.5), LineResult(_line(5), "void_dnp", None),
    ]

    summary = rate(results)

    assert summary == RateSummary(over=2, under=1, push=1)
    assert summary.decided == 3
    assert summary.over_rate == pytest.approx(2 / 3)


def test_standard_error_on_a_known_sample() -> None:
    # 60 of 100: sqrt(0.6 * 0.4 / 100) = 0.04899.
    assert HitSummary(hits=60, misses=40, pushes=5).standard_error == pytest.approx(0.04899, abs=1e-5)
    assert HitSummary(0, 0, 3).standard_error is None


@pytest.mark.parametrize("edge, expected", [(0.9, "small"), (1.0, "medium"), (-2.9, "medium"), (3.0, "large")])
def test_edge_buckets_split_at_exactly_five_and_fifteen_percent(edge: float, expected: str) -> None:
    assert edge_bucket(edge, 20.0) == expected


def test_reference_line_is_the_median_standard_full_game_line_per_market() -> None:
    lines = [
        _line(1, line=3.5), _line(2, line=4.5), _line(3, line=6.5),
        _line(4, line=1.5, odds_type="goblin"), _line(5, line=2.5, segment="first_half"),
        _line(6, market="receiving_yards", line=40.5),
    ]

    assert reference_lines(lines) == {"receptions": 4.5, "receiving_yards": 40.5}


def test_model_hits_score_calls_by_bucket_and_exclude_pushes_and_uncalled_lines() -> None:
    results = [
        LineResult(_line(1), "over", 6.0),    # called over by 1.0 on a 5.0 reference: large, hit
        LineResult(_line(2), "over", 6.0),    # called under by 0.1: small, miss
        LineResult(_line(3), "push", 4.5),    # push: neither
        LineResult(_line(4), "under", 3.0),   # no edge: not a call
        LineResult(_line(5), "void_dnp", None),
    ]
    edges = {1: 1.0, 2: -0.1, 3: 0.4, 5: 2.0}

    hits = model_hits(results, edges, {"receptions": 5.0})

    assert hits["all"] == HitSummary(hits=1, misses=1, pushes=1)
    assert hits["large"] == HitSummary(1, 0, 0)
    assert hits["small"] == HitSummary(0, 1, 0)
    assert hits["medium"] == HitSummary(0, 0, 1)


def test_a_market_without_a_reference_line_still_counts_toward_all() -> None:
    hits = model_hits([LineResult(_line(1), "under", 3.0)], {1: -1.0}, {})

    assert hits == {"all": HitSummary(1, 0, 0)}


def test_over_probability_reads_group_by_odds_type_and_count_unserved_lines() -> None:
    results = [
        settle_line(_line(1, stat_value=6.0)),
        settle_line(_line(2, odds_type="goblin", line=2.5, stat_value=6.0)),
        settle_line(_line(3, odds_type="demon", line=7.5, stat_value=6.0)),
        settle_line(_line(4, odds_type="demon", line=6.0, stat_value=6.0)),
        settle_line(_line(5, stat_value=3.0)),
    ]

    reads = over_probability_reads(results, {1: 0.45, 2: 0.8, 3: 0.3, 4: 0.5})

    assert (reads["standard"].scored, reads["standard"].unscored) == (1, 1)
    assert reads["goblin"].over_rate == 1.0 and reads["goblin"].mean_predicted == pytest.approx(0.8)
    # The demon push is not scored at all.
    assert (reads["demon"].scored, reads["demon"].over_rate) == (1, 0.0)
    assert (reads["all"].scored, reads["all"].unscored) == (3, 1)
    assert reads["all"].report is not None and reads["all"].report.brier == pytest.approx((0.55**2 + 0.2**2 + 0.3**2) / 3)


def test_over_probability_read_without_scored_lines_has_no_report() -> None:
    reads = over_probability_reads([settle_line(_line(1, stat_value=6.0))], {})

    assert reads["standard"].report is None and reads["standard"].over_rate is None

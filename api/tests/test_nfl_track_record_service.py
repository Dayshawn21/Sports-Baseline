from dataclasses import fields

import pytest

from app.core.nfl_game_line_clv import VERDICT_PICKS
from app.core.prop_ranking_rule import MIN_PICKS
from app.services.nfl.track_record import OverProbabilityRow, build_clv_record, build_line_record, build_ranking_record
from tests.helpers.nfl_track_record_service import GRADED_AT, _call, _clv_pick, _grade, _inputs, _line, _line_inputs


def _slice(record, odds_type: str, side: str):
    return next(row for row in record.slices if (row.odds_type, row.side) == (odds_type, side))


def test_every_slice_is_reported_and_an_accruing_one_stays_gray_however_far_it_strays() -> None:
    record = build_ranking_record(_inputs([_call(i, hit=i % 10 != 0) for i in range(40)]), 2026, GRADED_AT)

    assert [(row.odds_type, row.side) for row in record.slices] == [
        ("standard", "over"), ("standard", "under"), ("goblin", "over"), ("demon", "over"),
    ]
    over = _slice(record, "standard", "over")
    assert (over.verdict, over.n, over.hits) == ("insufficient", 40, 36)
    assert over.standard_error == pytest.approx((0.9 * 0.1 / 40) ** 0.5)
    assert over.signal == "neutral"
    assert _slice(record, "goblin", "over").n == 0


def test_a_unanimous_slice_shows_no_error_bar() -> None:
    record = build_ranking_record(_inputs([_call(i) for i in range(5)]), 2026, GRADED_AT)

    over = _slice(record, "standard", "over")
    assert over.hit_rate == 1.0
    assert over.standard_error is None


def test_a_decided_slice_is_colored_as_the_rule_judged_it() -> None:
    calls = [_call(i, week=1 + i % 4, hit=i % 20 < 17) for i in range(MIN_PICKS)]

    over = _slice(build_ranking_record(_inputs(calls), 2026, GRADED_AT), "standard", "over")

    assert (over.verdict, over.n, over.weeks) == ("adopt", MIN_PICKS, 4)
    assert over.signal == "positive"


def test_the_record_carries_weeks_coverage_and_exclusions_in_order() -> None:
    record = build_ranking_record(_inputs([_call(1)]), 2026, GRADED_AT)

    assert record.finished_weeks == [2, 3]
    assert record.last_settled_week == 3
    assert [(c.week, c.lines, c.frozen) for c in record.coverage] == [(2, 5380, 0), (3, 6087, 5729)]
    assert list(record.excluded) == ["push", "void_dnp"]
    assert record.funnel.calls == 1


def test_no_finished_week_means_no_last_settled_week() -> None:
    assert build_ranking_record(_inputs([], finished=set()), 2026, GRADED_AT).last_settled_week is None


def test_an_accruing_market_stays_gray_and_leads_with_every_pick() -> None:
    picks = [_clv_pick(i, 2, 1.0 + (i % 3) * 0.5) for i in range(12)]

    market = build_clv_record([_grade(picks, [47.3, 80.0, 78.5])], 2026, GRADED_AT).markets[0]

    assert (market.verdict, market.model_version) == ("accruing", "NFL_SCORING_V1")
    assert market.headline == market.all
    assert market.headline.n == 12
    assert market.signal == "neutral"
    assert (market.median_lead_hours, market.min_lead_hours) == (78.5, 47.3)
    assert market.early.n == 12 and market.late.n == 0


def test_a_decided_market_leads_with_its_fixed_sample() -> None:
    sample = [_clv_pick(i, 1, 0.5 + (i % 2)) for i in range(VERDICT_PICKS)]
    later = [_clv_pick(i, 6, -3.0) for i in range(10)]

    market = build_clv_record([_grade(sample + later)], 2026, GRADED_AT).markets[0]

    assert (market.verdict, market.verdict_weeks) == ("pass", [1])
    assert market.headline.n == VERDICT_PICKS
    assert market.all.n == VERDICT_PICKS + 10
    assert market.late.n == 10
    assert market.signal == "positive"
    assert market.min_lead_hours is None


def test_line_record_counts_coverage_and_keeps_every_edge_bucket_in_order() -> None:
    lines = [
        _line(1, stat_value=6.0), _line(2, stat_value=3.0), _line(3, stat_value=2.0),
        _line(4, stat_value=None, offense_snaps=None), _line(5, segment="first_half"),
        _line(6, market="anytime_touchdown", line=0.5, stat_value=1.0),
    ]

    record = build_line_record(_line_inputs(lines, {1: 1.0, 2: 1.0, 3: -1.0}), 2026, GRADED_AT)

    coverage = record.coverage
    assert (coverage.loaded, coverage.settled, coverage.void_dnp, coverage.unsettleable_segment) == (6, 4, 1, 1)
    assert (record.calls.calls, record.calls.hits) == (3, 2)
    assert [row.bucket for row in record.by_edge] == ["small", "medium", "large"]
    assert [row.calls for row in record.by_edge] == [0, 0, 3]
    assert record.by_edge[0].hit_rate is None and record.by_edge[0].signal == "neutral"
    assert [row.market for row in record.by_market] == ["receptions"]  # anytime TD had no call
    assert [(row.week, row.calls) for row in record.by_week] == [(2, 3)]


def test_a_market_far_below_break_even_reads_negative() -> None:
    lines = [_line(i, stat_value=6.0 if i < 30 else 3.0) for i in range(100)]

    record = build_line_record(_line_inputs(lines, {i: 1.0 for i in range(100)}), 2026, GRADED_AT)

    market = record.by_market[0]
    assert (market.calls, market.hits) == (100, 30)
    assert market.signal == "negative"
    assert record.calls.signal == "negative"


def test_forward_p_over_reads_carry_no_signal() -> None:
    lines = [_line(i, stat_value=6.0 if i % 2 else 3.0) for i in range(10)]

    record = build_line_record(_line_inputs(lines, {}, {i: 0.4 for i in range(10)}), 2026, GRADED_AT)

    assert "signal" not in {field.name for field in fields(OverProbabilityRow)}
    assert [row.odds_type for row in record.over_probability] == ["standard", "all"]
    overall = record.over_probability[-1]
    assert (overall.scored, overall.over_rate) == (10, 0.5)
    assert sum(b.n for b in record.reliability) == 10
    assert record.calls.calls == 0

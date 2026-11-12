from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

import pytest

from app.core.box_score_join import BoxScoreCandidate
from app.core.tennis_prop_reasons import (
    SPLIT_WINDOW,
    LogMatch,
    PropReasons,
    ReasonInput,
    RecentValue,
    build_reasons,
    recent_values,
    thin_margin,
)

START = date(2026, 10, 1)


def box(aces: int | None) -> BoxScoreCandidate:
    return BoxScoreCandidate(
        stats_id=1, match_date=START, result="W", opponent_name="B. Rival", score=None,
        aces=aces, double_faults=2, break_points_converted=3,
    )


def match(day: int, score: str | None = "6-4 7-6", *, match_id: int | None = None,
          aces: int | None = 8, has_box: bool = True, best_of: int = 3) -> LogMatch:
    return LogMatch(
        match_id=match_id if match_id is not None else day,
        match_date=START + timedelta(days=day),
        opponent_name="B. Rival",
        surface="Hard",
        best_of=best_of,
        score=score,
        box=box(aces) if has_box else None,
    )


def test_score_stat_counts_a_tie_break_set_as_thirteen_games():
    [value] = recent_values("Total Games", [match(1, "6-4 7-6")], exclude_match_id=None)
    assert value.value == 23


def test_score_stat_is_read_for_the_player_side():
    [value] = recent_values("total_games_won", [match(1, "4-6 6-3 6-2")], exclude_match_id=None)
    assert value.value == 16


def test_box_score_stat_reads_the_joined_box_score():
    [value] = recent_values("Aces", [match(1, aces=11)], exclude_match_id=None)
    assert value.value == 11


def test_match_without_a_box_score_or_its_count_is_skipped():
    log = [match(1, has_box=False), match(2, aces=None), match(3, aces=5)]
    assert [v.value for v in recent_values("aces", log, exclude_match_id=None)] == [5]


def test_retirement_and_walkover_are_skipped():
    log = [match(1, "6-4 3-1"), match(2, None), match(3, "6-3 6-3")]
    assert [v.match_date for v in recent_values("total_games", log, exclude_match_id=None)] == [START + timedelta(days=3)]


def test_best_of_five_needs_three_sets_to_count_as_completed():
    log = [match(1, "6-4 6-4", best_of=5), match(2, "6-4 6-4 6-4", best_of=5)]
    assert [v.value for v in recent_values("total_sets", log, exclude_match_id=None)] == [3]


def test_the_props_own_match_is_left_out():
    log = [match(1, match_id=900), match(2, match_id=901)]
    values = recent_values("total_games", log, exclude_match_id=901)
    assert [v.match_date for v in values] == [START + timedelta(days=1)]


def test_matches_on_or_after_the_cutoff_are_left_out():
    log = [match(1), match(2), match(3)]
    values = recent_values("total_games", log, exclude_match_id=None, before=START + timedelta(days=2))
    assert [v.match_date for v in values] == [START + timedelta(days=1)]


def test_unsupported_stat_returns_no_values():
    assert recent_values("Fantasy Score", [match(1)], exclude_match_id=None) == []


def test_values_are_newest_first_and_capped():
    log = [match(day) for day in range(SPLIT_WINDOW + 5)]
    values = recent_values("total_games", log, exclude_match_id=None)
    assert len(values) == SPLIT_WINDOW
    assert values[0].match_date == START + timedelta(days=SPLIT_WINDOW + 4)
    assert values == sorted(values, key=lambda v: v.match_date, reverse=True)


def recent(*nums: int, surface: str | None = "Hard", best_of: int = 3) -> list[RecentValue]:
    """Newest first: the first number is the latest match."""
    return [
        RecentValue(START + timedelta(days=len(nums) - i), "B. Rival", surface, best_of, n)
        for i, n in enumerate(nums)
    ]


def given(values: list[RecentValue], **changes: object) -> ReasonInput:
    base = ReasonInput(
        stat_type="aces", line=7.5, recent=values, player_linked=True, projection=None,
        rolling_matches=20, opponent_figure=None, opponent_matches=None, surface=None,
        best_of=None, stats_stale=False,
    )
    return replace(base, **changes)


def keys(reasons: tuple) -> list[str]:
    return [r.key for r in reasons]


def text(reasons: tuple, key: str) -> str:
    return next(r.text for r in reasons if r.key == key)


def test_ten_of_ten_over_gives_hit_rate_and_center_over():
    result = build_reasons(given(recent(*[9] * 10)))
    assert keys(result.over) == ["hit_rate", "center"]
    assert text(result.over, "hit_rate") == "Cleared the line in 10 of 10 recent matches"
    assert text(result.over, "center") == "Average 9 and median 9, both above the 7.5 line"
    assert result.under == ()


def test_two_of_ten_over_gives_hit_rate_under():
    result = build_reasons(given(recent(8, 8, 6, 6, 6, 6, 6, 6, 6, 6)))
    assert text(result.under, "hit_rate") == "Stayed under the line in 8 of 10 recent matches"
    assert "hit_rate" not in keys(result.over)


def test_an_even_split_gives_no_hit_rate():
    result = build_reasons(given(recent(*[8, 6] * 5)))
    assert "hit_rate" not in keys(result.over) + keys(result.under)


def test_a_push_is_left_out_of_the_share():
    result = build_reasons(given(recent(8, 8, 8, 7, 8, 8, 6, 8, 6, 8), line=7.0))
    assert text(result.over, "hit_rate") == "Cleared the line in 7 of 9 recent matches"
    assert result.summary is not None and result.summary.push == 1


def test_average_above_and_median_below_puts_center_under():
    result = build_reasons(given(recent(5, 20, 6, 20, 6, 7, 20, 7, 5, 6)))
    assert text(result.under, "center") == "Median 6.5 is below the line; its highest values lift the average to 10.2"
    assert "center" not in keys(result.over)


def test_fewer_than_three_values_turn_off_history_rules():
    result = build_reasons(given(recent(9, 9)))
    assert (result.over, result.under, result.summary) == ((), (), None)
    assert keys(result.caveats) == ["small_sample"]
    assert text(result.caveats, "small_sample") == "Only 2 completed matches in the sample"


def test_unreadable_market_keeps_only_the_projection():
    result = build_reasons(given([], stat_type="fantasy_score", line=25.5, projection=30.0))
    assert keys(result.over) == ["projection"]
    assert text(result.over, "projection") == "Model projects 30, 4.5 above the line"
    assert keys(result.caveats) == ["no_history"]
    assert text(result.caveats, "no_history") == (
        "Scores and box scores do not record this market, so there is no recent history"
    )


def test_a_readable_market_with_no_matches_says_so():
    result = build_reasons(given([]))
    assert text(result.caveats, "no_history") == "No recent completed matches for this market"


def test_a_thin_projection_gap_is_a_caveat_not_a_side():
    result = build_reasons(given(recent(*[12] * 10), projection=7.8))
    assert "projection" not in keys(result.over) + keys(result.under)
    assert text(result.caveats, "thin_projection_gap") == "Model projection 7.8 is within 0.5 of the line"


def test_a_projection_below_the_line_is_an_under_reason():
    result = build_reasons(given([], projection=6.0))
    assert text(result.under, "projection") == "Model projects 6, 1.5 below the line"


def test_trend_counts_a_rise_of_exactly_the_thin_margin():
    result = build_reasons(given(recent(9, 9, 9, 9, 9, 8, 8, 8, 8, 8)))
    assert text(result.over, "trend") == "Last 5 average 9, up from 8.5 over 10"


def test_trend_needs_eight_values():
    result = build_reasons(given(recent(12, 12, 12, 12, 12, 8, 8)))
    assert "trend" not in keys(result.over)


def test_a_falling_trend_is_an_under_reason():
    result = build_reasons(given(recent(6, 6, 6, 6, 6, 9, 9, 9, 9, 9)))
    assert text(result.under, "trend") == "Last 5 average 6, down from 7.5 over 10"


def test_surface_needs_three_values_on_todays_surface():
    two_clay = recent(9, 9, surface="Clay") + recent(6, 6, 6, surface="Hard")
    assert "surface" not in keys(build_reasons(given(two_clay, surface="Clay")).over)
    three_clay = recent(9, 9, 9, surface="Clay")
    result = build_reasons(given(three_clay, surface="Clay"))
    assert text(result.over, "surface") == "On clay: over in 3 of 3 since Oct 2"


def test_unknown_surface_skips_the_surface_rule():
    result = build_reasons(given(recent(9, 9, 9, surface="Clay"), surface=None))
    assert "surface" not in keys(result.over)


def test_best_of_five_today_adds_over_for_a_volume_stat_only():
    values = recent(6, 8, 6, 8, 6, 8)
    assert text(build_reasons(given(values, best_of=5)).over, "format") == (
        "Best of five today; most recent matches were best of three"
    )
    sets = build_reasons(given(values, stat_type="total_sets", line=2.5, best_of=5))
    assert "format" not in keys(sets.over) + keys(sets.under)


def test_best_of_three_after_mostly_five_set_matches_is_under():
    result = build_reasons(given(recent(6, 8, 6, 8, best_of=5), best_of=3))
    assert "format" in keys(result.under)


def test_opponent_needs_a_full_sample():
    thin = build_reasons(given([], opponent_figure=9.8, opponent_matches=9))
    assert "opponent" not in keys(thin.over)
    full = build_reasons(given([], opponent_figure=9.8, opponent_matches=10))
    assert text(full.over, "opponent") == "Opponent typically gives up 9.8 per match"


def test_each_side_keeps_its_first_three_reasons_in_rule_order():
    values = recent(12, 12, 12, 12, 12, 9, 9, 9, 9, 9, surface="Clay")
    result = build_reasons(given(
        values, projection=11.0, surface="Clay", best_of=5, opponent_figure=11.0, opponent_matches=20,
    ))
    assert keys(result.over) == ["projection", "hit_rate", "center"]


def test_caveats_keep_the_first_two_in_priority_order():
    result = build_reasons(given([], player_linked=False, rolling_matches=5, stats_stale=True))
    assert keys(result.caveats) == ["no_player", "small_sample"]
    assert text(result.caveats, "small_sample") == "The model's rolling stats rest on 5 matches"


def test_a_line_with_its_average_close_by_gets_a_thin_margin_caveat():
    result = build_reasons(given(recent(8, 7, 8, 7, 8, 8, 7, 8, 7, 9)))
    assert text(result.caveats, "thin_margin") == "Average 7.7 sits within 0.5 of the line"


@pytest.mark.parametrize("values", [
    recent(*[9] * 10), recent(5, 20, 6, 20, 6, 7, 20, 7, 5, 6), recent(6, 6, 6, 6, 6, 9, 9, 9, 9, 9), [],
])
def test_no_key_appears_on_both_sides(values: list[RecentValue]):
    result: PropReasons = build_reasons(given(values, projection=5.0, best_of=5, surface="Hard"))
    assert not set(keys(result.over)) & set(keys(result.under))


def test_thin_margin_scales_with_the_line():
    assert thin_margin(7.5) == 0.5
    assert thin_margin(21.5) == pytest.approx(1.075)

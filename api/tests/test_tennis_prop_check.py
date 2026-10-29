from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest

from app.core.prop_ranking_rule import BREAK_EVEN_BY_ODDS_TYPE, FrozenCall
from app.core.tennis_prop_check import (
    EXCLUDED_FLAGS, NO_PROBABILITY, PERIOD_NOT_FINISHED, TENNIS_PROP_CHECK_RULE, UNKNOWN_ODDS_TYPE,
    TennisFrozenLine, TennisSlice, adopted, anchor_of, check, finished_periods, period_of, slice_key,
    to_frozen_call,
)

MONDAY = datetime(2026, 11, 2, 15, 0, tzinfo=UTC)
# Late enough that the four weeks from MONDAY are all mature.
AS_OF = date(2026, 12, 31)


def _line(line_id: int = 1, **overrides: object) -> TennisFrozenLine:
    base = TennisFrozenLine(
        line_id=line_id, player_id=line_id, match_id=line_id, stat_type="Aces", match_tour="ATP",
        p1_tour="ATP", p2_tour="ATP", odds_type="standard", start_time=MONDAY, p_over=0.7, p_under=0.3,
        p_push=0.0, market_total_games=22.5, data_quality_flags=(), outcome="over",
    )
    return replace(base, **overrides)


def _slice_lines(count: int, weeks: int, hits: int) -> list[TennisFrozenLine]:
    """`count` standard-over lines on distinct players over `weeks` weeks, the first `hits` going over."""
    return [
        _line(i, start_time=MONDAY + timedelta(weeks=i % weeks), outcome="over" if i < hits else "under")
        for i in range(count)
    ]


ACES_ATP = TennisSlice("aces", "ATP", "book", "standard", "over")


def test_rule_has_a_name() -> None:
    assert TENNIS_PROP_CHECK_RULE == "tennis-props-check-v1"


def test_probabilities_exclude_the_push() -> None:
    call = to_frozen_call(_line(p_over=0.6, p_under=0.3, p_push=0.1), finished_periods([period_of(MONDAY)], AS_OF))

    assert isinstance(call, FrozenCall)
    assert call.p_over == pytest.approx(0.6 / 0.9)
    assert call.p_under == pytest.approx(0.3 / 0.9)


def test_a_push_is_not_a_call() -> None:
    assert to_frozen_call(_line(outcome="push"), finished_periods([period_of(MONDAY)], AS_OF)) == "push"


@pytest.mark.parametrize("overrides", [{"p_over": None}, {"p_under": None}, {"p_push": None}, {"p_push": 1.0}])
def test_missing_probabilities_exclude_the_line(overrides: dict[str, object]) -> None:
    assert to_frozen_call(_line(**overrides), {period_of(MONDAY)}) == NO_PROBABILITY


def test_unknown_odds_type_is_excluded() -> None:
    assert to_frozen_call(_line(odds_type="flex"), {period_of(MONDAY)}) == UNKNOWN_ODDS_TYPE
    assert to_frozen_call(_line(odds_type=None), {period_of(MONDAY)}) == UNKNOWN_ODDS_TYPE


@pytest.mark.parametrize("flag", sorted(EXCLUDED_FLAGS))
def test_each_excluded_flag_excludes_the_line(flag: str) -> None:
    assert to_frozen_call(_line(data_quality_flags=(flag,)), {period_of(MONDAY)}) == flag


@pytest.mark.parametrize("flag", ["no_market_total", "small_sample", "stale_stats", "sim_level_unverified"])
def test_other_flags_are_graded(flag: str) -> None:
    assert isinstance(to_frozen_call(_line(data_quality_flags=(flag,)), {period_of(MONDAY)}), FrozenCall)


@pytest.mark.parametrize(("total", "anchor"), [(16.5, "model"), (17.0, "book"), (None, "model")])
def test_anchor_follows_the_book_total_threshold(total: float | None, anchor: str) -> None:
    assert anchor_of(total) == anchor


def test_tour_label_reads_wta_125_from_a_challenger_draw_with_wta_players() -> None:
    line = _line(match_tour="CHALLENGER", p1_tour="WTA", p2_tour="CHALLENGER")

    assert slice_key(line, "over").tour == "WTA 125"
    assert slice_key(_line(match_tour="CHALLENGER"), "over").tour == "CHALLENGER"
    assert slice_key(_line(stat_type="Double Faults", odds_type="Goblin"), "over") == TennisSlice(
        "double_faults", "ATP", "book", "goblin", "over",
    )


def test_weeks_start_on_monday_utc() -> None:
    sunday_late = datetime(2026, 11, 1, 23, 59, tzinfo=UTC)
    monday = datetime(2026, 11, 2, 0, 0, tzinfo=UTC)

    assert period_of(monday) - period_of(sunday_late) == 7
    assert period_of(datetime(2026, 11, 8, 23, 59, tzinfo=UTC)) == period_of(monday)


def test_a_week_counts_only_after_its_maturity_days() -> None:
    week = period_of(MONDAY)

    assert finished_periods([week], date(2026, 11, 11)) == frozenset()
    assert finished_periods([week], date(2026, 11, 12)) == {week}
    assert to_frozen_call(_line(), finished_periods([week], date(2026, 11, 11))) == PERIOD_NOT_FINISHED


def test_a_ladder_straddling_anchors_counts_once_in_the_surviving_rungs_slice() -> None:
    rungs = [
        _line(1, market_total_games=None, p_over=0.65, p_under=0.35),
        replace(_line(2, p_over=0.8, p_under=0.2), player_id=1, match_id=1),
    ]

    result = check(rungs, AS_OF)

    assert result.funnel.picks == 2
    assert result.funnel.bets == 1
    assert list(result.slices) == [ACES_ATP]


def test_a_slice_without_a_full_sample_is_insufficient_and_hidden() -> None:
    result = check(_slice_lines(199, 4, 199), AS_OF)

    assert result.slices[ACES_ATP].verdict == "insufficient"
    assert adopted(result) == frozenset()


def test_three_standard_errors_are_needed_to_adopt() -> None:
    # 132 of 200 is 2.47 SE over break-even: an adopt under 27i's 2 SE, a reject here.
    rejected = check(_slice_lines(200, 4, 132), AS_OF)
    adopted_check = check(_slice_lines(200, 4, 136), AS_OF)

    assert rejected.slices[ACES_ATP].verdict == "reject"
    assert adopted_check.slices[ACES_ATP].verdict == "adopt"
    assert adopted(adopted_check) == {ACES_ATP}
    assert adopted_check.slices[ACES_ATP].break_even == BREAK_EVEN_BY_ODDS_TYPE["standard"]


def test_a_later_week_never_changes_a_fixed_verdict() -> None:
    lines = _slice_lines(200, 4, 132)
    later = [
        _line(1000 + i, start_time=MONDAY + timedelta(weeks=4), outcome="over") for i in range(300)
    ]

    before = check(lines, AS_OF).slices[ACES_ATP]
    after = check(lines + later, AS_OF).slices[ACES_ATP]

    assert after == before


def test_no_lines_adopt_nothing() -> None:
    result = check([], AS_OF)

    assert result.slices == {}
    assert adopted(result) == frozenset()
    assert result.finished_weeks == 0

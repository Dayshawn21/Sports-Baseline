from datetime import UTC, datetime

from app.backtest.nfl_ranking_check import report
from app.core.nfl_line_grading import GradeableLine, settle_line
from app.core.prop_ranking_check import SLICES, FrozenLine, slice_results, to_frozen_call
from app.core.prop_ranking_rule import MIN_PICKS, FrozenCall, one_pick_per_bet, slice_verdict, to_pick

MODEL = "opponent-dvp-tg-blend-usage-snap-v4"
P_OVER = "nfl-pover-v1"
FETCHED = datetime(2026, 9, 27, 2, 24, tzinfo=UTC)


def _frozen(line_id: int = 1, *, week: int = 3, player_id: int = 7, odds_type: str = "standard", line: float = 55.5,
            stat_value: float | None = 70.0, segment: str = "full_game", snaps: int | None = 40,
            game_has_stats: bool = True, p_over: float | None = 0.7, model_version: str = MODEL,
            over_probability_version: str | None = P_OVER) -> FrozenLine:
    graded = GradeableLine(
        line_id=line_id, season=2026, week=week, game_id=100 + player_id, player_id=player_id,
        market="receiving_yards", segment=segment, odds_type=odds_type, line=line, fetched_at=FETCHED,
        stat_value=stat_value, offense_snaps=snaps, game_has_stats=game_has_stats,
    )
    return FrozenLine(
        line_id=line_id, period=week, player_id=player_id, game_id=100 + player_id, market="receiving_yards",
        odds_type=odds_type, outcome=settle_line(graded).outcome,
        p_over=p_over, p_under=None if p_over is None else 1 - p_over,
        model_version=model_version, over_probability_version=over_probability_version,
    )


def _call(frozen: FrozenLine, weeks: tuple[int, ...] = (3,)) -> FrozenCall:
    result = to_frozen_call(frozen, weeks, MODEL, P_OVER)
    assert isinstance(result, FrozenCall)
    return result


def test_settled_lines_become_calls_with_their_outcome() -> None:
    over = _call(_frozen(stat_value=70.0))
    under = _call(_frozen(stat_value=12.0))

    assert (over.outcome, under.outcome) == ("over", "under")
    assert (over.line_id, over.period, over.player_id, over.odds_type, over.p_over) == (1, 3, 7, "standard", 0.7)


def test_every_line_that_cannot_be_a_call_says_why() -> None:
    cases = {
        "period_not_finished": _frozen(week=4),
        "unsettleable_segment": _frozen(segment="first_half"),
        "week_not_loaded": _frozen(game_has_stats=False),
        "void_dnp": _frozen(stat_value=None, snaps=None),
        "push": _frozen(line=70.0, stat_value=70.0),
    }

    for reason, frozen in cases.items():
        assert to_frozen_call(frozen, (3,), MODEL, P_OVER) == reason, reason


def test_rows_under_another_model_or_p_over_version_are_excluded() -> None:
    assert to_frozen_call(_frozen(model_version="older"), (3,), MODEL, P_OVER) == "wrong_version"
    assert to_frozen_call(_frozen(over_probability_version="nfl-pover-v0"), (3,), MODEL, P_OVER) == "wrong_version"


def test_a_line_served_without_p_over_is_a_call_but_never_a_pick() -> None:
    call = _call(_frozen(p_over=None, over_probability_version=None))

    check = slice_results([call])

    assert call.p_over is None
    assert (check.funnel.calls, check.funnel.with_p_over, check.funnel.picks) == (1, 0, 0)


def test_ladder_rungs_of_one_bet_collapse_to_one_pick() -> None:
    rungs = [_call(_frozen(i, odds_type="demon", line=line, p_over=0.6)) for i, line in enumerate((65.5, 75.5), 1)]

    check = slice_results(rungs)

    assert (check.funnel.picks, check.funnel.bets) == (2, 1)
    assert check.slices[("demon", "over")].n == 1


def test_all_four_slices_are_reported_even_when_empty() -> None:
    check = slice_results([])

    assert list(check.slices) == list(SLICES) == [
        ("standard", "over"), ("standard", "under"), ("goblin", "over"), ("demon", "over"),
    ]
    assert all(result.verdict == "insufficient" and result.n == 0 for result in check.slices.values())
    assert check.slices[("goblin", "over")].break_even > 0.75


def test_a_slice_that_clears_its_break_even_adopts_exactly_as_slice_verdict_says() -> None:
    per_week = MIN_PICKS // 4
    calls = [
        _call(_frozen(i, week=3 + i % 4, player_id=i, stat_value=70.0 if i % 10 else 12.0), weeks=(3, 4, 5, 6))
        for i in range(per_week * 4)
    ]

    check = slice_results(calls)

    expected = slice_verdict(one_pick_per_bet(pick for call in calls if (pick := to_pick(call)) is not None))
    assert check.slices[("standard", "over")] == expected
    assert expected.verdict == "adopt"
    assert check.slices[("standard", "under")].verdict == "insufficient"


def test_a_week_held_open_for_late_stats_leaves_a_past_200_slice_undecided() -> None:
    # F-10: 210 standard-under picks over weeks 3-5, then a week 6 whose games
    # are final but not all loaded. Until week 6 counts as finished, its lines
    # never enter the sample, so the first four whole weeks are not yet fixed.
    lines = [_frozen(i, week=3 + i % 3, player_id=i, stat_value=12.0, p_over=0.3) for i in range(210)]
    week_six = [_frozen(1000 + i, week=6, player_id=1000 + i, stat_value=None, snaps=None, p_over=0.3)
                for i in range(40)]

    held_open = [c for f in lines + week_six if isinstance(c := to_frozen_call(f, (3, 4, 5), MODEL, P_OVER), FrozenCall)]
    result = slice_results(held_open).slices[("standard", "under")]

    assert result.n == 210
    assert result.verdict == "insufficient"
    assert all(to_frozen_call(f, (3, 4, 5), MODEL, P_OVER) == "period_not_finished" for f in week_six)


def test_report_prints_the_funnel_coverage_and_an_accruing_slice() -> None:
    call = _call(_frozen())
    text = report(2026, slice_results([call]), 3, {"week_not_loaded": 2}, {2: (5380, 0), 3: (324, 300)},
                  model_version=MODEL, over_probability_version=P_OVER)

    assert f"NFL forward ranking check, 2026 (model {MODEL}, P(over) {P_OVER})" in text
    assert "frozen rows on completed games 3; excluded: week_not_loaded 2" in text
    assert "coverage, 27a full-game lines with a frozen row: wk 2 0/5380, wk 3 300/324" in text
    assert "funnel: calls 1, with P(over) 1, picks 1, one per bet 1" in text
    assert "  standard over        1      1      1    100.0%    0.0%       57.7%   accruing, 1 of 200 picks, 1 of 4 weeks" in text
    assert "  demon over           0      0      0         -       -       41.3%   accruing, 0 of 200 picks, 0 of 4 weeks" in text


def test_report_states_a_fixed_verdict_plainly() -> None:
    calls = [
        _call(_frozen(i, week=3 + i % 4, player_id=i, stat_value=70.0 if i % 10 else 12.0), weeks=(3, 4, 5, 6))
        for i in range(MIN_PICKS)
    ]

    text = report(2026, slice_results(calls), len(calls), {}, {})

    assert "excluded: none" in text and "row: none" in text
    assert "  standard over      200      4    180     90.0%    2.1%       57.7%   adopt" in text

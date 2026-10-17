import pytest

from app.core.prop_ranking_rule import (
    BREAK_EVEN_BY_ODDS_TYPE, MIN_PERIODS, MIN_PICK_MARGIN, MIN_PICKS, FrozenCall, Pick, Side, one_pick_per_bet,
    pick_side, slice_verdict, to_pick, verdict_sample,
)

STANDARD = BREAK_EVEN_BY_ODDS_TYPE["standard"]


def _call(line_id: int = 1, *, week: int = 5, player_id: int = 1, odds_type: str = "standard",
          p_over: float | None = 0.3, outcome: Side = "under") -> FrozenCall:
    return FrozenCall(
        line_id=line_id, period=week, player_id=player_id, game_id=player_id, market="receiving_yards",
        odds_type=odds_type, p_over=p_over, p_under=None if p_over is None else 1 - p_over, outcome=outcome,
    )


def _picks(count: int, weeks: int, hits: int, first_week: int = 1) -> list[Pick]:
    """`count` standard-under picks spread evenly over `weeks` weeks, the first `hits` of them winning."""
    picks = []
    for i in range(count):
        call = _call(i, week=first_week + i % weeks, player_id=i, outcome="under" if i < hits else "over")
        pick = to_pick(call)
        assert pick is not None
        picks.append(pick)
    return sorted(picks, key=lambda p: (p.call.period, p.call.line_id))


def test_break_evens_come_from_the_payout_table() -> None:
    assert BREAK_EVEN_BY_ODDS_TYPE["standard"] == pytest.approx(0.577, abs=0.001)
    assert BREAK_EVEN_BY_ODDS_TYPE["goblin"] == pytest.approx(0.758, abs=0.001)
    assert BREAK_EVEN_BY_ODDS_TYPE["demon"] == pytest.approx(0.413, abs=0.001)


def test_standard_picks_whichever_side_clears_break_even_plus_the_margin() -> None:
    edge = STANDARD + MIN_PICK_MARGIN

    assert pick_side("standard", edge, 1 - edge) == ("over", edge)
    assert pick_side("standard", 1 - edge, edge) == ("under", edge)
    assert pick_side("standard", 0.55, 0.45) is None
    assert pick_side("standard", edge - 0.0001, 1 - edge + 0.0001) is None


def test_goblin_and_demon_lines_never_pick_the_under() -> None:
    assert pick_side("goblin", 0.1, 0.9) is None
    assert pick_side("demon", 0.2, 0.8) is None
    assert pick_side("goblin", 0.8, 0.2) == ("over", 0.8)
    assert pick_side("demon", 0.45, 0.55) == ("over", 0.45)


@pytest.mark.parametrize(("odds_type", "p_over"), [("standard", None), ("unknown", 0.9)])
def test_no_probability_or_an_unknown_odds_type_never_picks(odds_type: str, p_over: float | None) -> None:
    assert pick_side(odds_type, p_over, None if p_over is None else 1 - p_over) is None


def test_a_ladder_keeps_only_the_rung_that_clears_break_even_by_the_most() -> None:
    rungs = [_call(line_id, odds_type="goblin", p_over=p) for line_id, p in [(1, 0.79), (2, 0.86), (3, 0.81)]]
    other_player = _call(4, player_id=2, odds_type="goblin", p_over=0.80)

    kept = one_pick_per_bet(p for p in map(to_pick, rungs + [other_player]) if p is not None)

    assert [pick.call.line_id for pick in kept] == [2, 4]


def test_verdict_sample_is_the_first_whole_weeks_reaching_both_minimums() -> None:
    picks = _picks(260, 5, hits=0)  # 52 a week

    sample = verdict_sample(picks)

    # Four weeks hold 208 picks, the first run reaching 200 picks and 4 weeks.
    assert sample is not None and len(sample) == 208
    assert {p.call.period for p in sample} == {1, 2, 3, 4}


def test_a_later_week_never_changes_the_verdict() -> None:
    base = _picks(MIN_PICKS, MIN_PERIODS, hits=150)
    later = [to_pick(_call(10_000 + i, week=9, player_id=10_000 + i, outcome="over")) for i in range(100)]

    assert slice_verdict(base) == slice_verdict(base + [p for p in later if p is not None])


def test_199_picks_are_insufficient() -> None:
    result = slice_verdict(_picks(MIN_PICKS - 1, MIN_PERIODS, hits=199))

    assert (result.verdict, result.n) == ("insufficient", 199)


def test_three_weeks_are_insufficient_however_many_picks() -> None:
    result = slice_verdict(_picks(600, MIN_PERIODS - 1, hits=600))

    assert (result.verdict, result.periods) == ("insufficient", 3)


def test_adopt_needs_the_hit_rate_two_standard_errors_above_break_even() -> None:
    # 140 of 200 = 70%, SE 3.2 points: the lower bound 63.5% clears 57.7%.
    adopted = slice_verdict(_picks(MIN_PICKS, MIN_PERIODS, hits=140))
    # 124 of 200 = 62%, SE 3.4 points: the lower bound 55.1% does not.
    rejected = slice_verdict(_picks(MIN_PICKS, MIN_PERIODS, hits=124))

    assert adopted.verdict == "adopt" and adopted.hit_rate == pytest.approx(0.70)
    assert rejected.verdict == "reject"


def test_the_adopt_boundary_is_strict() -> None:
    # Find the first hit count that adopts, and check the one below it does not, so the
    # comparison is exactly "lower bound > break-even" rather than an off-by-one.
    verdicts = {hits: slice_verdict(_picks(MIN_PICKS, MIN_PERIODS, hits=hits)) for hits in range(120, 141)}
    first_adopt = min(hits for hits, result in verdicts.items() if result.verdict == "adopt")
    below = verdicts[first_adopt - 1]
    above = verdicts[first_adopt]

    assert below.hit_rate - 2 * below.standard_error <= STANDARD
    assert above.hit_rate - 2 * above.standard_error > STANDARD


def test_slice_verdict_refuses_mixed_slices() -> None:
    mixed = [to_pick(_call(1)), to_pick(_call(2, player_id=2, p_over=0.8, outcome="over"))]

    with pytest.raises(ValueError):
        slice_verdict([p for p in mixed if p is not None])


def test_the_pre_registered_constants_are_unchanged() -> None:
    # 27i fixed these on 2026-09-26; moving the rule to every sport (17c) must not touch them.
    assert {odds_type: round(value, 4) for odds_type, value in BREAK_EVEN_BY_ODDS_TYPE.items()} == {
        "standard": 0.5774, "goblin": 0.7576, "demon": 0.4132,
    }
    assert (MIN_PICK_MARGIN, MIN_PICKS, MIN_PERIODS) == (0.03, 200, 4)

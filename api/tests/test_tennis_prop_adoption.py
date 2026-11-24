import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest

from app.core.prop_ranking_rule import FrozenCall, SliceResult, SliceVerdict, to_pick
from app.core.tennis_prop_adoption import (
    ADOPTION_SEASON, UNSETTLED, adopted_from_payload, adopted_picks, adoption_report, to_payload,
)
from app.core.tennis_prop_check import (
    EXCLUDED_FLAGS, NO_PROBABILITY, UNKNOWN_ODDS_TYPE, CheckFunnel, CheckResult, TennisFrozenLine, TennisSlice,
    period_of, slice_key, to_frozen_call,
)

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)
START = NOW + timedelta(hours=3)
ACES_ATP = TennisSlice("aces", "ATP", "book", "standard", "over")


def _line(line_id: int = 1, **overrides: object) -> TennisFrozenLine:
    base = TennisFrozenLine(
        line_id=line_id, player_id=line_id, match_id=line_id, stat_type="Aces", match_tour="ATP",
        p1_tour="ATP", p2_tour="ATP", odds_type="standard", start_time=START, p_over=0.7, p_under=0.3,
        p_push=0.0, market_total_games=22.5, data_quality_flags=(), outcome=UNSETTLED,
    )
    return replace(base, **overrides)


PARITY_CASES = [
    {},
    {"market_total_games": 16.5},
    {"market_total_games": 17.0},
    {"market_total_games": None},
    {"p_over": 0.6, "p_under": 0.3, "p_push": 0.1},
    {"p_push": 1.0},
    {"p_over": None},
    {"odds_type": "flex"},
    {"odds_type": "Goblin", "p_over": 0.85, "p_under": 0.15},
    *({"data_quality_flags": (flag,)} for flag in sorted(EXCLUDED_FLAGS)),
    {"data_quality_flags": ("no_market_total", "small_sample")},
]


@pytest.mark.parametrize("overrides", PARITY_CASES)
def test_live_lines_are_excluded_and_keyed_as_the_grader_does(overrides: dict[str, object]) -> None:
    live = _line(**overrides)
    graded = to_frozen_call(replace(live, outcome="over"), {period_of(live.start_time)})
    picks = adopted_picks([live], {slice_key(live, "over"), slice_key(live, "under")}, NOW)

    expected = to_pick(graded) if isinstance(graded, FrozenCall) else None
    if expected is None:
        assert picks == {}
    else:
        assert (picks[1].side, picks[1].probability) == (expected.side, expected.probability)


def test_exclusions_that_the_parity_cases_cover() -> None:
    assert to_frozen_call(_line(p_push=1.0, outcome="over"), {period_of(START)}) == NO_PROBABILITY
    assert to_frozen_call(_line(odds_type="flex", outcome="over"), {period_of(START)}) == UNKNOWN_ODDS_TYPE


def test_nothing_adopted_means_no_picks() -> None:
    assert adopted_picks([_line()], frozenset(), NOW) == {}


def test_an_adopted_slice_picks_its_line() -> None:
    picks = adopted_picks([_line()], {ACES_ATP}, NOW)

    assert picks[1].side == "over"
    assert picks[1].probability == pytest.approx(0.7)
    assert picks[1].margin == pytest.approx(0.7 - picks[1].break_even)


def test_push_excluded_probability_decides_the_side() -> None:
    pick = adopted_picks([_line(p_over=0.6, p_under=0.3, p_push=0.1)], {ACES_ATP}, NOW)[1]

    assert pick.probability == pytest.approx(0.6 / 0.9)


@pytest.mark.parametrize("overrides", [
    {"data_quality_flags": ("match_finished",)},
    {"odds_type": "flex"},
    {"p_push": 1.0},
    # Break-even 57.7% plus the 0.03 margin needs 60.7%.
    {"p_over": 0.6, "p_under": 0.4},
])
def test_an_adopted_slice_still_skips_lines_the_rule_would_not_call(overrides: dict[str, object]) -> None:
    assert adopted_picks([_line(**overrides)], {ACES_ATP}, NOW) == {}


def test_an_unadopted_slice_is_not_a_pick() -> None:
    assert adopted_picks([_line(stat_type="Double Faults")], {ACES_ATP}, NOW) == {}


def test_a_goblin_under_is_never_a_pick() -> None:
    goblin_under = TennisSlice("aces", "ATP", "book", "goblin", "under")
    line = _line(odds_type="goblin", p_over=0.05, p_under=0.95)

    assert adopted_picks([line], {goblin_under}, NOW) == {}


def _ladder() -> list[TennisFrozenLine]:
    # One player's goblin ladder; the 0.92 rung clears break-even by the most.
    return [
        _line(10, player_id=7, match_id=8, odds_type="goblin", p_over=0.85, p_under=0.15),
        _line(11, player_id=7, match_id=8, odds_type="goblin", p_over=0.92, p_under=0.08),
        _line(12, player_id=7, match_id=8, odds_type="goblin", p_over=0.80, p_under=0.20),
    ]


def test_a_ladder_is_one_pick_on_its_best_rung() -> None:
    picks = adopted_picks(_ladder(), {TennisSlice("aces", "ATP", "book", "goblin", "over")}, NOW)

    assert list(picks) == [11]


def test_a_ladder_is_sliced_by_its_surviving_rung() -> None:
    # Synthetic: the best rung keys to the model anchor, a weaker rung to book.
    ladder = _ladder()
    ladder[1] = replace(ladder[1], market_total_games=None)
    book_goblin_over = TennisSlice("aces", "ATP", "book", "goblin", "over")

    assert adopted_picks(ladder, {book_goblin_over}, NOW) == {}


def test_wta_125_keys_from_a_challenger_match_with_wta_players() -> None:
    line = _line(match_tour="CHALLENGER", p1_tour="WTA", p2_tour="WTA")

    assert adopted_picks([line], {TennisSlice("aces", "WTA 125", "book", "standard", "over")}, NOW).keys() == {1}
    assert adopted_picks([line], {TennisSlice("aces", "CHALLENGER", "book", "standard", "over")}, NOW) == {}


def test_a_started_line_is_never_a_pick() -> None:
    assert adopted_picks([_line(start_time=NOW)], {ACES_ATP}, NOW) == {}
    assert adopted_picks([_line(start_time=NOW + timedelta(minutes=1))], {ACES_ATP}, NOW).keys() == {1}


DATE = date(2026, 11, 30)
COMPUTED = datetime(2026, 11, 30, 13, 5, tzinfo=UTC)
GOBLIN_WTA = TennisSlice("aces", "WTA", "model", "goblin", "over")


def _slice_result(verdict: SliceVerdict) -> SliceResult:
    return SliceResult(verdict=verdict, n=200, periods=4, hits=150, break_even=0.577)


def _result() -> CheckResult:
    return CheckResult(
        slices={
            ACES_ATP: _slice_result("adopt"),
            GOBLIN_WTA: _slice_result("adopt"),
            TennisSlice("double_faults", "ATP", "book", "standard", "under"): _slice_result("reject"),
            TennisSlice("total_games", "WTA", "book", "standard", "over"): _slice_result("insufficient"),
        },
        exclusions={"push": 3}, funnel=CheckFunnel(rows=10, calls=8, picks=6, bets=5), finished_weeks=5,
    )


def test_payload_round_trips_to_the_adopted_slices() -> None:
    payload = to_payload(_result(), "props-v3", DATE, COMPUTED)

    assert json.loads(json.dumps(payload)) == payload
    assert adopted_from_payload(payload, "props-v3") == {ACES_ATP, GOBLIN_WTA}
    assert payload["decidedSlices"] == 3
    assert payload["finishedWeeks"] == 5
    assert payload["asOf"] == "2026-11-30"


def test_payload_carries_no_slice_statistics() -> None:
    text = json.dumps(to_payload(_result(), "props-v3", DATE, COMPUTED))

    for leaked in ("hit", "hits", "\"n\"", "standard_error", "breakEven", "double_faults", "total_games"):
        assert leaked not in text


def test_an_empty_adopted_list_is_an_empty_set_not_unusable() -> None:
    payload = to_payload(replace(_result(), slices={}), "props-v3", DATE, COMPUTED)

    assert adopted_from_payload(payload, "props-v3") == frozenset()


@pytest.mark.parametrize("change", [
    {"rule": "tennis-props-check-v0"},
    {"projectionVersion": "props-v4"},
    {"adopted": None},
    {"adopted": "aces"},
    {"adopted": [{"stat": "aces", "tour": "ATP", "anchor": "market", "oddsType": "standard", "side": "over"}]},
    {"adopted": [{"stat": "aces", "tour": "ATP", "anchor": "book", "oddsType": "standard", "side": "both"}]},
    {"adopted": [{"stat": "aces", "tour": "ATP", "anchor": "book", "side": "over"}]},
    {"adopted": ["aces"]},
])
def test_an_untrustworthy_payload_decodes_to_none(change: dict[str, object]) -> None:
    payload = {**to_payload(_result(), "props-v3", DATE, COMPUTED), **change}

    assert adopted_from_payload(payload, "props-v3") is None


def test_a_missing_adopted_key_is_unusable() -> None:
    payload = to_payload(_result(), "props-v3", DATE, COMPUTED)
    del payload["adopted"]

    assert adopted_from_payload(payload, "props-v3") is None


def test_each_version_has_its_own_report() -> None:
    assert adoption_report("props-v3") == "tennis_prop_adoption:props-v3"
    assert adoption_report("props-v4") != adoption_report("props-v3")
    assert ADOPTION_SEASON == 0

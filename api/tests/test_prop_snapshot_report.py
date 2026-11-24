"""A tier's hit rate must grade the side the app recommended, and never count a push."""
from datetime import date
from itertools import count

import pytest

from app.backtest.tennis_prop_snapshots import grade, report
from app.core.box_score_join import BoxScoreCandidate, JoinResult
from app.repositories.prop_snapshots import GradedPropSnapshot

_ids = count(1)


def _row(recommendation="UNDER", line=19.5, stat="Total Games", odds_type="standard",
         confidence="LEAN", score="6-4 6-3", **kw) -> GradedPropSnapshot:
    fields = dict(
        snapshot_id=next(_ids), player_id=next(_ids), match_id=next(_ids), tour="ATP", stat_type=stat, odds_type=odds_type, line=line,
        recommendation=recommendation, confidence=confidence, hit_probability=0.6,
        player_is_p1=True, score=score, best_of=3,
    )
    fields.update(kw)
    return GradedPropSnapshot(**fields)


def test_an_under_recommendation_hits_when_the_line_goes_under():
    (pick,), _ = grade([_row(recommendation="UNDER", line=19.5)])  # 19 games
    assert pick.hit is True


def test_an_over_recommendation_misses_on_the_same_result():
    (pick,), _ = grade([_row(recommendation="OVER", line=19.5)])
    assert pick.hit is False and pick.units == -1.0


def test_a_push_is_neither_hit_nor_miss_and_scores_zero():
    (pick,), _ = grade([_row(line=19.0)])
    assert pick.hit is None and pick.units == 0.0


def test_a_standard_hit_wins_the_assumed_leg_payout():
    (pick,), _ = grade([_row(line=19.5)])
    assert pick.units == pytest.approx(0.732)


def test_rows_that_cannot_be_graded_are_counted_by_reason():
    picks, awaiting = grade([
        _row(recommendation=None),
        _row(stat="Aces", line=5.5),
        _row(stat="Double Faults", line=2.5),
        _row(score="6-4 2-1"),
        _row(),
    ])
    assert len(picks) == 1
    assert awaiting.no_recommendation == 1 and awaiting.incomplete_score == 1
    assert awaiting.unjoined == {"no_candidate": 2}


BOX = BoxScoreCandidate(
    stats_id=1, match_date=date(2026, 9, 21), result="W", opponent_name="An Opponent",
    score="6-4 6-3", aces=4, double_faults=3, break_points_converted=2,
)


def test_a_joined_aces_snapshot_is_graded_by_tier():
    under = _row(stat="Aces", recommendation="UNDER", line=5.5, confidence="STRONG")
    (pick,), _ = grade([under], {(under.player_id, under.match_id): JoinResult(BOX, "joined")})
    assert pick.hit is True and pick.row.confidence == "STRONG"


def test_an_unjoined_snapshot_is_counted_by_reason():
    over = _row(stat="Double Faults", recommendation="OVER", line=2.5)
    picks, awaiting = grade([over], {(over.player_id, over.match_id): JoinResult(None, "no_opponent_match")})
    assert picks == [] and awaiting.unjoined == {"no_opponent_match": 1}


def test_a_stat_with_no_source_is_counted_apart_from_join_failures():
    _, awaiting = grade([_row(stat="Fantasy Score", line=20.5)])
    assert awaiting.not_settleable == {"fantasy_score": 1} and awaiting.unjoined == {}


def test_pushes_are_left_out_of_the_hit_rate():
    text = report([_row(line=19.5), _row(recommendation="OVER", line=19.5), _row(line=19.0)], "props-v2")
    lean = next(line for line in text.splitlines() if line.strip().startswith("LEAN"))
    assert "50.0% +/- " in lean  # 1 hit, 1 miss, 1 push


def test_goblin_and_demon_tiers_carry_no_error_bar():
    text = report([
        _row(odds_type="goblin", recommendation="OVER", line=15.5),
        _row(odds_type="demon", recommendation="OVER", line=22.5),
    ], "props-v2")
    tier_lines = [line for line in text.splitlines() if line.strip().startswith("LEAN")]
    assert len(tier_lines) == 2 and all("+/-" not in line for line in tier_lines)


def test_an_empty_report_still_renders():
    text = report([])
    assert "graded:                                         0" in text
    assert "no decided picks yet" in text


def test_picks_are_also_reported_by_stat():
    text = report([
        _row(stat="1st Set Total Games", recommendation="OVER", line=9.5, score="6-4 6-3"),  # 10 games: hit
        _row(stat="1st Set Total Games", recommendation="OVER", line=9.5, score="6-2 6-3"),  # 8 games: miss
        _row(stat="Total Games", line=19.5),
    ])
    section = text.split("By stat and odds type")[1].split("Calibration")[0]
    first_set = next(line for line in section.splitlines() if line.strip().startswith("1st_set_total_games"))
    assert "    2 " in first_set and "50.0%" in first_set
    assert any(line.strip().startswith("total_games ") for line in section.splitlines())


def test_props_v3_and_later_report_no_tiers():
    text = report([_row(line=19.5)], "props-v3")
    assert "By confidence tier: no tiers under props-v3 (retired by 48f)" in text
    assert not any(line.strip().startswith("LEAN") for line in text.split("By stat")[0].splitlines())

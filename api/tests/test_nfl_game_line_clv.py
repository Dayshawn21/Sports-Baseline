from collections import Counter
from datetime import UTC, datetime, timedelta

import pytest

from app.backtest.nfl_game_line_clv import report
from app.core.nfl_game_line_clv import (
    FIRST_WEEK_WINDOW, MIN_LEAD, VERDICT_PICKS, WINDOW_AFTER_PREVIOUS_KICKOFF, ClvGame, ClvMarketGrade, ClvPick, GameModel,
    OddsCandidate, clv_pick, entry_line, grade_market, summarize, verdict, verdict_sample, window_open,
)

KICKOFF = datetime(2026, 9, 27, 17, 0, tzinfo=UTC)
OPENS = datetime(2026, 9, 22, 6, 15, tzinfo=UTC)


def _row(id_: int, book: str, hours_before: float, line: float = -3.0) -> OddsCandidate:
    return OddsCandidate(id_, book, line, KICKOFF - timedelta(hours=hours_before))


def test_window_opens_after_the_previous_weeks_last_kickoff() -> None:
    previous = datetime(2026, 9, 22, 0, 15, tzinfo=UTC)

    assert window_open(KICKOFF, previous) == previous + WINDOW_AFTER_PREVIOUS_KICKOFF
    assert window_open(KICKOFF, None) == KICKOFF - FIRST_WEEK_WINDOW


def test_draftkings_beats_an_earlier_line_from_another_book() -> None:
    chosen = entry_line([_row(1, "fanduel", 100), _row(2, "draftkings", 60), _row(3, "draftkings", 30)], OPENS, KICKOFF)

    assert chosen is not None and chosen.id == 2


def test_without_draftkings_the_earliest_other_book_wins_ties_by_book_then_id() -> None:
    rows = [_row(5, "fanduel", 100), _row(4, "betmgm", 100), _row(3, "betmgm", 100), _row(1, "bovada", 50)]

    chosen = entry_line(rows, OPENS, KICKOFF)

    assert chosen is not None and (chosen.book, chosen.id) == ("betmgm", 3)


def test_capitalized_books_from_the_old_code_path_are_ignored() -> None:
    chosen = entry_line([_row(1, "DraftKings", 100), _row(2, "fanduel", 60)], OPENS, KICKOFF)

    assert chosen is not None and chosen.id == 2


def test_rows_before_the_window_or_inside_the_last_day_are_ignored() -> None:
    before_window = OddsCandidate(1, "draftkings", -3.0, OPENS - timedelta(minutes=1))
    too_late = OddsCandidate(2, "draftkings", -3.0, KICKOFF - MIN_LEAD + timedelta(minutes=1))
    on_the_edges = [
        OddsCandidate(3, "fanduel", -3.0, OPENS),
        OddsCandidate(4, "fanduel", -3.0, KICKOFF - MIN_LEAD),
    ]

    assert entry_line([before_window, too_late], OPENS, KICKOFF) is None
    chosen = entry_line([before_window, too_late, *on_the_edges], OPENS, KICKOFF)
    assert chosen is not None and chosen.id == 3


def test_a_pick_needs_at_least_one_and_a_half_points_of_disagreement() -> None:
    assert clv_pick("g", 3, "spread", -4.4, -3.0, -3.0, 0) is None
    assert clv_pick("g", 3, "spread", -4.5, -3.0, -3.0, 0) is not None
    # A float hair under the threshold still counts.
    assert clv_pick("g", 3, "total", 42.9 + 1.5 - 1e-12, 42.9, 42.9, 0) is not None


def test_spread_clv_is_positive_when_the_close_moves_toward_a_model_that_likes_home() -> None:
    # Model: home -6.3. Entry: home -2.5. Close: home -3.5, a point toward the model.
    pick = clv_pick("2026_03_DAL_NYG", 3, "spread", -6.3, -2.5, -3.5, 7)

    assert pick is not None
    assert pick.direction == -1
    assert pick.clv == pytest.approx(1.0)


def test_spread_clv_is_negative_when_the_close_moves_away() -> None:
    pick = clv_pick("g", 3, "spread", -6.3, -2.5, -1.5, 7)

    assert pick is not None and pick.clv == pytest.approx(-1.0)


def test_total_clv_follows_the_models_over_or_under_direction() -> None:
    over = clv_pick("g", 3, "total", 44.4, 39.5, 41.0, 45)
    under = clv_pick("g", 3, "total", 37.0, 39.5, 41.0, 45)

    assert over is not None and over.direction == 1 and over.clv == pytest.approx(1.5)
    assert under is not None and under.direction == -1 and under.clv == pytest.approx(-1.5)


def test_no_movement_is_zero_clv_not_a_dropped_pick() -> None:
    pick = clv_pick("g", 3, "total", 44.4, 39.5, 39.5, 45)

    assert pick is not None and pick.clv == 0


def _total(week: int, clv: float, outcome: int = 45, i: int = 0) -> ClvPick:
    """An over pick (model 44, entry 40) whose close moved `clv` points toward the model."""
    return ClvPick(f"g{week}_{i}", week, "total", 44.0, 40.0, 40.0 + clv, outcome)


def _week_of(week: int, count: int, clv: float = 1.0) -> list[ClvPick]:
    return [_total(week, clv, i=i) for i in range(count)]


def test_summary_counts_movement_and_standard_error() -> None:
    summary = summarize([_total(5, 1.0), _total(5, -1.0), _total(5, 0.0), _total(5, 2.0)])

    assert summary.n == 4
    assert summary.mean_clv == pytest.approx(0.5)
    # Sample standard deviation of (1, -1, 0, 2) is sqrt(5/3); over sqrt(4).
    assert summary.standard_error == pytest.approx((5 / 3) ** 0.5 / 2)
    assert (summary.toward, summary.away, summary.flat) == (2, 1, 1)


def test_summary_grades_the_model_side_against_the_entry_line() -> None:
    # Totals: the over (model 44 vs entry 40) wins at 45, loses at 38, pushes at 40.
    totals = summarize([_total(5, 0, 45), _total(5, 0, 38), _total(5, 0, 40)])
    # Spreads in book sign: the model likes home (-6 vs -2.5). Home by 7 covers; home by 1 does not.
    spreads = summarize([
        ClvPick("a", 5, "spread", -6.0, -2.5, -3.0, 7),
        ClvPick("b", 5, "spread", -6.0, -2.5, -3.0, 1),
    ])

    assert (totals.record.hits, totals.record.misses, totals.record.pushes) == (1, 1, 1)
    assert (spreads.record.hits, spreads.record.misses) == (1, 1)


def test_one_pick_has_no_standard_error_and_reads_as_accruing() -> None:
    result = verdict([_total(2, 1.0)])

    assert result.summary.standard_error is None
    assert result.verdict == "accruing"
    assert verdict([]).summary.mean_clv is None


def test_the_week_that_crosses_the_sample_size_is_included_whole() -> None:
    picks = _week_of(2, VERDICT_PICKS - 10) + _week_of(3, 16) + _week_of(4, 16)

    sample = verdict_sample(picks)

    assert sample is not None
    assert len(sample) == VERDICT_PICKS + 6
    assert {pick.week for pick in sample} == {2, 3}


def test_later_weeks_never_change_the_sample() -> None:
    early = _week_of(2, VERDICT_PICKS)

    assert verdict_sample(early + _week_of(3, 50, clv=-9.0)) == verdict_sample(early)
    assert verdict(early + _week_of(3, 50, clv=-9.0)).weeks == (2,)


def test_short_of_the_sample_the_verdict_is_accruing_over_every_pick() -> None:
    result = verdict(_week_of(2, 10) + _week_of(3, 10))

    assert result.verdict == "accruing"
    assert result.summary.n == 20
    assert result.weeks == (2, 3)


def _alternating(mean: float, count: int = VERDICT_PICKS) -> list[ClvPick]:
    """Picks of mean +/- 1 point, so the standard error is about 1 / sqrt(count)."""
    return [_total(2, mean + (1.0 if i % 2 else -1.0), i=i) for i in range(count)]


def test_passes_only_when_mean_clv_clears_two_standard_errors() -> None:
    standard_error = summarize(_alternating(0.0)).standard_error
    assert standard_error is not None

    assert verdict(_alternating(2 * standard_error + 0.01)).verdict == "pass"
    assert verdict(_alternating(2 * standard_error - 0.01)).verdict == "reject"
    assert verdict(_alternating(-0.5)).verdict == "reject"


PREVIOUS = datetime(2026, 9, 22, 0, 15, tzinfo=UTC)


def _game(key: str = "2026_03_DAL_NYG", *, week: int = 3, completed: bool = True, spread_line: float | None = 3.5,
          total_line: float | None = 41.0, rows_hours_before: tuple[float, ...] = (70.0,)) -> ClvGame:
    """NYG home. NFLverse spread 3.5 is NYG -3.5 at the close; entry rows are NYG -2.5 and 39.5."""
    fetched = [KICKOFF - timedelta(hours=h) for h in rows_hours_before]
    return ClvGame(
        key, week, KICKOFF, completed, 27 if completed else None, 20 if completed else None,
        spread_line, total_line, PREVIOUS,
        {
            "spread": [OddsCandidate(i, "draftkings", -2.5, at) for i, at in enumerate(fetched)],
            "total": [OddsCandidate(100 + i, "draftkings", 39.5, at) for i, at in enumerate(fetched)],
        },
    )


MODELS = {"2026_03_DAL_NYG": GameModel(home_spread=-6.3, total=44.4)}


def test_grading_turns_a_game_into_a_spread_pick_in_book_sign() -> None:
    grade = grade_market([_game()], MODELS, "spread")

    (pick,) = grade.picks
    assert (pick.model, pick.entry, pick.close, pick.outcome) == (-6.3, -2.5, -3.5, 7)
    assert pick.clv == pytest.approx(1.0)
    assert grade.graded == 1
    assert grade.lead_hours == [pytest.approx(70.0)]


def test_grading_a_total_uses_points_scored_and_the_nflverse_total() -> None:
    (pick,) = grade_market([_game()], MODELS, "total").picks

    assert (pick.model, pick.entry, pick.close, pick.outcome) == (44.4, 39.5, 41.0, 47)
    assert pick.clv == pytest.approx(1.5)


def test_a_game_under_the_threshold_is_graded_but_not_a_pick() -> None:
    grade = grade_market([_game()], {"2026_03_DAL_NYG": GameModel(-3.0, 40.0)}, "spread")

    assert grade.graded == 1 and grade.picks == []
    assert sum(grade.excluded.values()) == 0


def test_every_left_out_game_is_counted_by_reason() -> None:
    games = [
        _game("played_in_open_week", week=3),
        _game("unplayed", week=3, completed=False),
        _game("no_close", week=2, spread_line=None),
        _game("no_model", week=2),
        _game("late_rows_only", week=2, rows_hours_before=(10.0,)),
    ]
    models = {key: MODELS["2026_03_DAL_NYG"] for key in ("played_in_open_week", "unplayed", "no_close", "late_rows_only")}

    grade = grade_market(games, models, "spread")

    assert grade.picks == [] and grade.graded == 0
    assert grade.excluded == {
        "week not finished": 1, "not played yet": 1, "no closing line or score": 1,
        "no model rating": 1, "no entry line": 1,
    }
    assert grade.median_lead_hours is None


def test_report_prints_coverage_context_rows_and_an_accruing_verdict() -> None:
    grade = grade_market([_game()], MODELS, "spread")

    text = report(2026, [grade])

    assert "NFL game-line CLV, 2026 (nfl-elo-v1 spread" in text
    assert "  games graded 1, picks 1 (|model - entry| >= 1.5)" in text
    assert "  excluded: none" in text
    assert "  entry line before kickoff: median 70.0h, min 70.0h" in text
    assert "  all          1     +1.00      -   1/0/0         1-0-0" in text
    assert "  wk 5+        0         -      -   0/0/0         0-0-0" in text
    assert "  Verdict: accruing, 1 of 150 picks (week 3)" in text


def test_report_states_a_final_verdict_with_its_sample() -> None:
    picks = _alternating(0.5)
    text = report(2026, [ClvMarketGrade("total", len(picks), picks, Counter(), [48.0] * len(picks))])

    assert "  Verdict: pass (week 2, 150 picks): mean CLV +0.50, SE 0.08" in text

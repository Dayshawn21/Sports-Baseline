from datetime import UTC, date, datetime

from app.backtest.tennis_prop_check import FALSE_ADOPT_RATE, report, to_frozen_lines
from app.core.box_score_join import BoxScoreCandidate, JoinResult
from app.core.prop_ranking_rule import BREAK_EVEN_BY_ODDS_TYPE, SliceResult
from app.core.tennis_prop_check import CheckFunnel, CheckResult, TennisSlice
from app.repositories.prop_snapshots import PropCheckSnapshot

AS_OF = date(2026, 12, 7)
STANDARD = BREAK_EVEN_BY_ODDS_TYPE["standard"]
DECIDED = TennisSlice("aces", "ATP", "book", "standard", "over")
ACCRUING = TennisSlice("total_games", "WTA", "book", "standard", "under")


def _result(slices: dict[TennisSlice, SliceResult]) -> CheckResult:
    return CheckResult(
        slices=slices, exclusions={"push": 3, "incomplete_score": 2},
        funnel=CheckFunnel(rows=50, calls=45, picks=30, bets=20), finished_weeks=5,
    )


def test_a_decided_slice_shows_its_numbers_and_reading() -> None:
    text = report(_result({DECIDED: SliceResult("reject", 200, 4, 124, STANDARD)}), "props-v3", AS_OF)

    row = next(line for line in text.splitlines() if line.strip().startswith("aces"))
    assert "62.0%" in row and "3.4%" in row and "51.7%" in row and "57.7%" in row
    assert row.endswith("hide (reject, final)")


def test_an_undecided_slice_never_shows_a_running_hit_rate() -> None:
    text = report(_result({ACCRUING: SliceResult("insufficient", 67, 3, 50, STANDARD)}), "props-v3", AS_OF)

    row = next(line for line in text.splitlines() if line.strip().startswith("total_games"))
    assert "74.6%" not in row
    assert row.split()[-6:] == ["-", "-", "-", "57.7%", "hide", "(insufficient)"]


def test_an_adopted_slice_reads_adopt() -> None:
    text = report(_result({DECIDED: SliceResult("adopt", 200, 4, 140, STANDARD)}), "props-v4", AS_OF)

    assert text.splitlines()[0] == (
        "Tennis forward prop check - tennis-props-check-v1 on props-v4 (as of 2026-12-07)"
    )
    assert text.splitlines()[-1].endswith("adopt")


def test_the_header_counts_exclusions_and_expected_false_adopts() -> None:
    slices = {
        DECIDED: SliceResult("reject", 200, 4, 124, STANDARD),
        ACCRUING: SliceResult("insufficient", 67, 3, 50, STANDARD),
    }
    text = report(_result(slices), "props-v3", AS_OF)

    assert "excluded: incomplete_score 2, push 3" in text
    assert "calls 45 | picks 30 | bets 20 | finished weeks 5" in text
    assert f"decided slices 1 | expected false adopts at 3 SE: {FALSE_ADOPT_RATE:.3f}" in text


def test_no_slices_says_so() -> None:
    assert report(_result({}), "props-v3", AS_OF).splitlines()[-1] == "  no slice has a pick yet"


def test_frozen_lines_carry_the_row_and_its_settled_outcome() -> None:
    start = datetime(2026, 11, 3, 12, tzinfo=UTC)
    base = dict(
        player_id=11, match_id=21, match_tour="CHALLENGER", p1_tour="WTA", p2_tour="WTA", odds_type="standard",
        start_time=start, p_over=0.6, p_under=0.4, p_push=0.0, market_total_games=None,
        data_quality_flags=("no_market_total",), player_is_p1=True, score="6-4 6-3", best_of=3,
    )
    rows = [
        PropCheckSnapshot(snapshot_id=1, stat_type="Total Games", line=18.5, **base),
        PropCheckSnapshot(snapshot_id=2, stat_type="Aces", line=4.5, **base),
    ]
    box = BoxScoreCandidate(
        stats_id=1, match_date=start.date(), result="W", opponent_name="Opponent", score="6-4 6-3",
        aces=3, double_faults=1, break_points_converted=2,
    )

    lines = to_frozen_lines(rows, {(11, 21): JoinResult(box, "joined")})

    assert [line.outcome for line in lines] == ["over", "under"]
    assert lines[0].line_id == 1 and lines[0].data_quality_flags == ("no_market_total",)
    assert to_frozen_lines(rows[1:], {})[0].outcome == "no_candidate"

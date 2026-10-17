"""The settlement report must count every line it drops and never put an error bar
on correlated goblin or demon lines."""
from datetime import date, datetime, timezone
from itertools import count

from app.backtest.tennis_prizepicks_lines import report, settle_rows
from app.core.box_score_join import BoxScoreCandidate, JoinResult
from app.repositories.props import PrizePicksCoverage, PrizePicksLineRow

START = datetime(2026, 9, 20, 12, tzinfo=timezone.utc)
_ids = count(1)
COVERAGE = PrizePicksCoverage(
    rows=100, rows_linked=50, player_matches=10, player_matches_settled=8,
    box_score_exact_date=1, box_score_unique_in_window=2,
)


def _row(stat="Total Games", odds_type="standard", line=20.5, score="6-4 6-3", **kw) -> PrizePicksLineRow:
    fields = dict(
        prop_id=next(_ids), player_id=next(_ids), match_id=next(_ids), tour="ATP",
        stat_type=stat, odds_type=odds_type, line=line, fetched_at=START.replace(hour=9),
        start_utc=START, player_is_p1=True, score=score, best_of=3, is_live=False, is_promo=False,
    )
    fields.update(kw)
    return PrizePicksLineRow(**fields)


ROWS = [
    _row(line=18.5),                    # 19 games: over
    _row(line=19.5),                    # under
    _row(line=19.0),                    # push
    _row(odds_type="goblin", line=15.5),
    _row(odds_type="demon", line=22.5),
    _row(is_live=True),
    _row(is_promo=True),
    _row(stat="Aces", line=5.5),        # no join attempted: no candidate
    _row(stat="Fantasy Score", line=20.5),
    _row(score="6-4 3-2"),              # retirement
]


def test_every_dropped_line_is_counted_under_its_reason():
    settled, excluded = settle_rows(ROWS)
    assert len(settled) == 5
    assert (excluded.live, excluded.promo, excluded.incomplete_score) == (1, 1, 1)
    assert excluded.not_settleable == {"fantasy_score": 1}
    assert excluded.unjoined == {"no_candidate": 1}


BOX = BoxScoreCandidate(
    stats_id=1, match_date=date(2026, 9, 14), result="W", opponent_name="An Opponent",
    score="6-4 6-3", aces=7, double_faults=1, break_points_converted=3,
)


def test_a_joined_ace_line_settles_from_the_box_score():
    ace = _row(stat="Aces", line=5.5)
    settled, _ = settle_rows([ace], {(ace.player_id, ace.match_id): JoinResult(BOX, "joined")})
    assert [(line.stat, line.actual, line.outcome) for line in settled] == [("aces", 7, "over")]


def test_an_ambiguous_join_is_counted_and_not_settled():
    ace = _row(stat="Aces", line=5.5)
    settled, excluded = settle_rows([ace], {(ace.player_id, ace.match_id): JoinResult(None, "ambiguous")})
    assert settled == [] and excluded.unjoined == {"ambiguous": 1}


def test_join_coverage_is_reported_by_tour():
    ace, wta_ace = _row(stat="Aces", line=5.5), _row(stat="Aces", line=5.5, tour="WTA")
    joins = {
        (ace.player_id, ace.match_id): JoinResult(BOX, "joined"),
        (wta_ace.player_id, wta_ace.match_id): JoinResult(None, "no_opponent_match"),
    }
    text = report([ace, wta_ace], COVERAGE, joins)
    assert "    all            1 of     2 (50.0%)" in text
    assert "    ATP            1 of     1 (100.0%)" in text
    assert "    WTA            0 of     1 (0.0%)" in text


def test_pushes_are_left_out_of_the_hit_rate():
    text = report(ROWS, COVERAGE)
    standard_row = next(line for line in text.splitlines() if line.strip().startswith("total_games"))
    # One over, one under, one push: 50% of decided lines, not 33%.
    assert " 50.0% +/- " in standard_row


def test_goblin_and_demon_rows_carry_no_error_bar():
    text = report(ROWS, COVERAGE)
    rows_by_type: dict[str, str] = {}
    current = ""
    for line in text.split("Standard lines, ATP")[0].splitlines():
        if line.startswith(" ") and not line.startswith("  "):
            current = line.split()[0]
        elif current and line.strip().startswith("total_games"):
            rows_by_type[current] = line
    assert "+/-" in rows_by_type["standard"]
    assert "+/-" not in rows_by_type["goblin"] and "+/-" not in rows_by_type["demon"]


def test_sections_are_present():
    text = report(ROWS, COVERAGE)
    for header in ("Coverage", "Closing pre-start lines", "Settlement by stat and odds type",
                   "Standard lines, ATP", "Standard lines, WTA", "Standard lines, CHALLENGER"):
        assert header in text
    assert "excluded, box-score stat with no join:       1" in text
    assert "excluded, no settlement source:             1" in text

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from app.repositories.matches import PlayerMatchLogRow
from app.repositories.props import Prop
from app.schemas.props import PropLine
from app.services.tennis.player_detail import MatchLogEntry
from app.services.tennis.prop_reasons import line_cutoff, log_match, reason_input

FETCHED = datetime(2026, 11, 10, 12, tzinfo=UTC)


def prop(**changes: object) -> Prop:
    base = dict(
        id=7, player_id=812, player_name="A. Player", match_id=55, source="prizepicks",
        stat_type="Aces", line=Decimal("7.5"), odds_type="standard", fetched_at=FETCHED,
        start_time=FETCHED, surface="Clay", best_of=5,
    )
    return Prop(**{**base, **changes})


def line(**changes: object) -> PropLine:
    base = dict(
        id=7, player_id=812, match_id=55, source="prizepicks", stat_type="Aces", odds_type="standard",
        fetched_at=FETCHED, start_time=FETCHED, stat_avg=9.1, matches_count=18,
        opponent_stat_avg=8.4, opponent_matches_count=12, stats_stale=None,
    )
    return PropLine(**{**base, **changes})


def test_reason_input_carries_the_rows_own_numbers():
    data = reason_input(prop(), line(), [])
    assert (data.line, data.projection, data.rolling_matches) == (7.5, 9.1, 18)
    assert (data.opponent_figure, data.opponent_matches) == (8.4, 12)
    assert (data.surface, data.best_of, data.player_linked, data.stats_stale) == ("Clay", 5, True, False)


def test_a_projection_without_an_ok_status_is_not_used():
    assert reason_input(prop(), line(projection_status="missing_stats"), []).projection is None


def test_an_unlinked_player_reads_as_not_linked():
    assert reason_input(prop(player_id=None), line(player_id=None), []).player_linked is False


def test_the_cutoff_is_the_lines_utc_start_day():
    late_evening_in_new_york = datetime(2026, 11, 11, 1, 30, tzinfo=UTC)
    assert line_cutoff(prop(start_time=late_evening_in_new_york)) == date(2026, 11, 11)


def test_a_line_without_a_start_time_cuts_off_at_its_fetch_day():
    assert line_cutoff(prop(start_time=None)) == date(2026, 11, 10)


def test_log_match_keeps_the_player_oriented_score_and_box():
    row = PlayerMatchLogRow(
        match_id=40, match_date=date(2026, 10, 30), tournament="Paris", round="R32", surface="Hard",
        best_of=3, opponent_id=9, opponent_name="B. Rival", opponent_rank=20, won=False, score="4-6 6-7",
    )
    match = log_match(MatchLogEntry(row, None))
    assert (match.match_id, match.score, match.best_of, match.box) == (40, "4-6 6-7", 3, None)

"""Shared fixtures and builders, first written for `test_prop_ranking_check.py`."""
from datetime import UTC, datetime

from app.core.nfl_line_grading import GradeableLine, settle_line
from app.core.prop_ranking_check import FrozenLine


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

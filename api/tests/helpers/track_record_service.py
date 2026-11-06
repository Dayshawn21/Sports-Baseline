"""Shared fixtures and builders, first written for `test_track_record_service.py`."""
from datetime import datetime, timedelta, timezone
from app.repositories.predictions import GradedPrediction
from app.repositories.props import PrizePicksLineRow  # noqa: E402
from app.services.tennis.track_record import build_line_settlement  # noqa: E402
from app.repositories.prop_snapshots import GradedPropSnapshot  # noqa: E402
from app.services.tennis.track_record import build_tier_grading  # noqa: E402


MODEL = "ensemble-v1+lgbm-v6"
GRADED_AT = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)
START = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)


def _row(i: int, tour: str = "ATP", *, p1_won: bool = True, market: float | None = 0.6,
         ensemble: float | None = 0.65, close: float | None = None, version: str = MODEL,
         completed: bool = True, ml: float | None = 0.62, elo: float | None = 0.6) -> GradedPrediction:
    start = START + timedelta(hours=i)
    return GradedPrediction(
        match_id=i, tour=tour, start_utc=start, generated_at=start - timedelta(hours=2),
        model_version=version, p1_won=p1_won, completed_score=completed,
        elo_prob=elo, ml_prob=ml, market_prob=market, ensemble_prob=ensemble,
        market_book="draftkings", closing_market_prob=close,
    )


def _line(i: int, line: float, odds_type: str = "standard", *, stat: str = "Total Games",
          live: bool = False, score: str = "6-4 6-3") -> PrizePicksLineRow:
    return PrizePicksLineRow(
        prop_id=i, player_id=i, match_id=1000 + i, tour="ATP", stat_type=stat, odds_type=odds_type,
        line=line, fetched_at=START, start_utc=START + timedelta(hours=1), player_is_p1=True,
        score=score, best_of=3, is_live=live, is_promo=False,
    )


AS_OF = GRADED_AT.date()
OLD_DAY = datetime(2026, 9, 1, 13, 30, tzinfo=timezone.utc)


def _snap(i: int, *, confidence: str = "LEAN", recommendation: str | None = "UNDER", line: float = 19.5,
          odds_type: str = "standard", snapshot_at: datetime = OLD_DAY, score: str = "6-4 6-3") -> GradedPropSnapshot:
    return GradedPropSnapshot(
        snapshot_id=i, player_id=i, match_id=2000 + i, tour="ATP", stat_type="Total Games", odds_type=odds_type,
        line=line, recommendation=recommendation, confidence=confidence, hit_probability=0.6,
        player_is_p1=True, score=score, best_of=3, snapshot_at=snapshot_at,
    )

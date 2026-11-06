"""Shared fixtures and builders, first written for `test_tennis_elo_comparison_repository.py`."""
from datetime import datetime, timedelta, timezone


from app.core.tennis_elo import TennisEloRating
from app.repositories.tennis_elo import SOURCE, TennisEloSnapshot
from app.repositories.tennis_elo_comparison import FrozenComparison, FrozenForecast, FrozenIncumbentRating, FrozenMarket


NOW = datetime(2026, 10, 21, 13, 30, tzinfo=timezone.utc)
KICKOFF = NOW + timedelta(hours=2)
DAY = NOW.date()


def pair(match_id: int = 50) -> FrozenComparison:
    candidates = tuple(TennisEloSnapshot(
        player_id=player_id, source=SOURCE, as_of_date=DAY,
        rating=TennisEloRating(1600.0, 1580.0, None, None, 20, 10, 0, 0),
        provider_namespace="ATP", provider_player_id=f"A{player_id}", computed_at=NOW - timedelta(hours=1),
        source_downloaded_at=NOW - timedelta(hours=2), replay_cutoff=DAY,
        method_version=SOURCE, manifest_sha256="a" * 64,
    ) for player_id in (1, 2))
    incumbents = tuple(FrozenIncumbentRating(i, DAY, 1600.0, 1580.0, None, None, 20) for i in (1, 2))
    forecast = FrozenForecast(0.5, 0.5, (("market", 0.8), ("elo", 0.2)), (), False)
    return FrozenComparison(
        match_id, 1, 2, "ATP", "Hard", KICKOFF, NOW, "ensemble-v3",
        "b" * 64, "c" * 64, "d" * 64,
        FrozenMarket(match_id, 100, "bet365", NOW - timedelta(minutes=10), -110, -110, 0.5),
        incumbents, candidates, forecast, forecast, None, "e" * 64, NOW - timedelta(days=1), DAY,
    )

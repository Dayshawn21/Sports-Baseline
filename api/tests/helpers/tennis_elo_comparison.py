"""Shared fixtures and builders, first written for `test_tennis_elo_comparison.py`."""
from datetime import datetime, timedelta, timezone


from app.core.tennis_elo import TennisEloRating
from app.ml.asof_features import HistoryIndex
from app.ml.elo_history import EloIndex
from app.repositories.matches import Match
from app.repositories.players import Player, PlayerElo
from app.repositories.tennis_elo import SOURCE, TennisEloSnapshot
from app.services.tennis import predictor
from app.services.tennis.elo_comparison import ExperimentConfig, runtime_pins


NOW = datetime(2026, 11, 8, 13, 30, tzinfo=timezone.utc)
DAY = NOW.date()


class Registry:
    def __init__(self):
        self.calls = []

    def get_lgbm_version(self, tour):
        return "v6" if tour in {"ATP", "WTA"} else None

    def predict_lgbm(self, tour, features):
        self.calls.append((tour, dict(features)))
        return 0.57

    def serves_tour(self, tour):
        return tour in {"ATP", "WTA"}


def match():
    return Match(50, "future", DAY, NOW + timedelta(hours=2), "ATP", "Hard", "Tokyo", "R16",
                 3, 1, 2, 10, 20, None, "scheduled", None)


def batch():
    results = [(DAY - timedelta(days=i), 1, 2, 1 if i % 2 else 2, "Hard") for i in range(1, 21)]
    return predictor.PredictionBatch(
        {i: Player(i, f"Player {i}", f"player {i}", "ATP") for i in (1, 2)},
        {1: PlayerElo(1, DAY, 1600., 1580., None, None),
         2: PlayerElo(2, DAY, 1560., 1560., None, None)}, {}, {}, {}, {},
        {50: {"book": "draftkings", "p1_odds": -110, "p2_odds": -110, "line": None,
              "fetched_at": NOW - timedelta(minutes=5), "row_id": 100}}, {}, {},
        HistoryIndex(results), EloIndex(results),
    )


def candidates():
    return {i: TennisEloSnapshot(
        player_id=i, source=SOURCE, as_of_date=DAY,
        rating=TennisEloRating(1550. if i == 1 else 1500., 1520. if i == 1 else 1500., None, None, 30, 20, 0, 0),
        provider_namespace="ATP", provider_player_id=f"A{i}", computed_at=NOW - timedelta(hours=1),
        source_downloaded_at=NOW - timedelta(hours=2), replay_cutoff=DAY, method_version=SOURCE,
        manifest_sha256="a" * 64,
    ) for i in (1, 2)}


def config(registry=None, active=True):
    registry = registry or Registry()
    return ExperimentConfig.from_record({**runtime_pins(registry, "d" * 64),
                                         "activated_at": (NOW - timedelta(days=1)).isoformat() if active else None})

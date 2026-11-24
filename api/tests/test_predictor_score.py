from types import SimpleNamespace

from app.services.tennis.predictor import _score


class _Registry:
    def __init__(self, serves: bool = True):
        self.serves = serves

    def predict_lgbm(self, tour, feat):
        return 0.6

    def serves_tour(self, tour):
        return self.serves


_MATCH = SimpleNamespace(tour="ATP")
_ELO = SimpleNamespace(elo=1900.0)
_FEAT = {"d_elo": 50.0}


def test_a_player_without_elo_reads_as_missing_not_fallback():
    scores = _score(_Registry(), _MATCH, _FEAT, ["p2_elo_missing"], _ELO, None, -150, 130, 40)
    assert scores.elo_prob is None
    assert "elo_missing" in scores.quality_flags
    assert "elo_fallback_used" not in scores.quality_flags


def test_flags_merge_builder_registry_and_blend_flags_sorted():
    scores = _score(_Registry(serves=False), _MATCH, _FEAT, ["stale_odds", "ctx_top20_missing"], _ELO, _ELO, -150, 130, 40)
    assert scores.quality_flags == ["ctx_top20_missing", "ml_not_trained_for_tour", "stale_odds"]
    assert scores.result is not None and scores.market_prob is not None


def test_no_source_at_all_reports_no_predictors():
    registry = _Registry()
    registry.predict_lgbm = lambda tour, feat: None
    scores = _score(registry, _MATCH, _FEAT, ["elo_missing", "market_missing"], None, None, None, None, None)
    assert scores.result is None
    assert scores.quality_flags == ["elo_missing", "market_missing", "no_predictors"]

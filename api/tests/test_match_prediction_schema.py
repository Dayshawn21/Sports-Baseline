"""The slate prediction carries the match format the model used (60a)."""

from app.routers.tennis import _to_schema
from app.services.tennis.predictor import PredictionOutput


def _output(best_of: int) -> PredictionOutput:
    return PredictionOutput(
        match_id=1, start_utc=None, p1_name="A", p2_name="B", tour="ATP",
        surface="Hard", tournament="Australian Open", round="R1",
        p1_win_prob=0.6, p2_win_prob=0.4, p1_elo_prob=0.6, p1_ml_prob=0.6, p1_market_prob=0.55,
        ensemble_weights={}, quality_flags=[], p1_odds_american=-150, p2_odds_american=130,
        h2h_p1_wins=0, h2h_p2_wins=0, best_of=best_of,
    )


def test_best_of_serializes_as_camel_case():
    assert _to_schema(_output(5)).model_dump(by_alias=True)["bestOf"] == 5
    assert _to_schema(_output(3)).model_dump(by_alias=True)["bestOf"] == 3

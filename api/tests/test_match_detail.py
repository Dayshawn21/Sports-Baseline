import asyncio
from dataclasses import replace
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.repositories.matches import Match, MatchMeeting, MatchMeta
from app.repositories.players import PlayerElo, PlayerProfile
from app.repositories.predictions import StoredPrediction, get_prestart_prediction
from app.routers import tennis as tennis_router
from app.services.tennis import match_detail
from app.services.tennis.best_picks import BestPick
from app.services.tennis.match_detail import (
    prediction_ref_date,
    stored_prediction_output,
    surface_elo,
    winner_side,
)
from app.services.tennis.predictor import PredictionOutput

TODAY = date(2026, 9, 28)
GENERATED = datetime(2026, 9, 28, 8, 0, tzinfo=timezone.utc)


def _match(status: str = "scheduled", match_date: date = TODAY, winner_id: int | None = None) -> Match:
    return Match(
        id=5, match_key="k5", match_date=match_date,
        start_utc=datetime(2026, 9, 28, 10, 30, tzinfo=timezone.utc),
        tour="ATP", surface="Hard", tournament="Tokyo", round="R16", best_of=None,
        p1_id=1, p2_id=2, p1_rank=19, p2_rank=7, winner_id=winner_id,
        status=status, sofascore_id=None,
    )


def _prediction() -> PredictionOutput:
    return PredictionOutput(
        match_id=5, start_utc=None, p1_name="Jakub Mensik", p2_name="Ben Shelton",
        tour="ATP", surface="Hard", tournament="Tokyo", round="R16",
        p1_win_prob=0.524, p2_win_prob=0.476, p1_elo_prob=0.463, p1_ml_prob=0.618,
        p1_market_prob=0.456, ensemble_weights={"elo": 0.3, "ml": 0.4, "market": 0.3},
        quality_flags=["h2h_small_sample"], p1_odds_american=122, p2_odds_american=-148,
        h2h_p1_wins=1, h2h_p2_wins=2, tour_label="ATP",
    )


def _pick() -> BestPick:
    return BestPick(
        pick_type="moneyline", label="Moneyline", pick="Mensik ML (+122)",
        player_name="Jakub Mensik", edge_pct=14.9, confidence="STRONG", reasoning="r",
        odds_american=122, ev_pct=16.3,
    )


def _stored(**overrides) -> StoredPrediction:
    base = dict(
        generated_at=GENERATED, model_version="ensemble-v6", p1_elo_prob=0.46,
        p1_ml_prob=0.62, p1_market_prob=0.45, p1_ensemble_prob=0.52,
        ensemble_weights={"elo": 0.3, "ml": 0.4, "market": 0.3},
        quality_flags=["h2h_small_sample"], p1_odds=120, p2_odds=-150,
    )
    base.update(overrides)
    return StoredPrediction(**base)


def _elo(**overrides) -> PlayerElo:
    base = dict(player_id=1, as_of_date=TODAY, elo=1942.0, elo_hard=1968.0, elo_clay=1881.0, elo_grass=1903.0)
    base.update(overrides)
    return PlayerElo(**base)


@pytest.fixture
def repos(monkeypatch):
    calls = {"predict": [], "stored": []}
    state = {"match": _match(), "predicted": [_prediction()], "stored": None}

    async def get_match(_db, match_id):
        return (state["match"], MatchMeta(indoor=True, score=None)) if match_id == 5 else None

    async def get_player_profiles(_db, _ids):
        return {
            1: PlayerProfile(id=1, name="Jakub Mensik", tour="ATP", hand="R", country="CZE"),
            2: PlayerProfile(id=2, name="Ben Shelton", tour="ATP", hand="L", country="USA"),
        }

    async def get_latest_elo_batch(_db, _ids):
        return {1: _elo(), 2: _elo(player_id=2, elo=1980.0, elo_hard=1994.0)}

    async def get_h2h(_db, _p1, _p2, surface):
        return {"p1_wins": 1, "p2_wins": 1} if surface else {"p1_wins": 1, "p2_wins": 2}

    async def predict_matches(_db, _registry, matches, ref_date):
        calls["predict"].append((matches, ref_date))
        return state["predicted"]

    async def get_prestart_prediction(_db, match_id, start_utc):
        calls["stored"].append((match_id, start_utc))
        return state["stored"]

    async def get_meetings(_db, _p1, _p2, _before):
        return [MatchMeeting(date(2026, 2, 18), "Doha", "R16", "Hard", "6-2 6-1", "p1")]

    monkeypatch.setattr(match_detail.match_repo, "get_meetings", get_meetings)
    monkeypatch.setattr(match_detail.prediction_repo, "get_prestart_prediction", get_prestart_prediction)
    monkeypatch.setattr(match_detail.match_repo, "get_match", get_match)
    monkeypatch.setattr(match_detail.player_repo, "get_player_profiles", get_player_profiles)
    monkeypatch.setattr(match_detail.player_repo, "get_latest_elo_batch", get_latest_elo_batch)
    monkeypatch.setattr(match_detail.match_repo, "get_h2h", get_h2h)
    monkeypatch.setattr(match_detail.predictor, "predict_matches", predict_matches)
    monkeypatch.setattr(match_detail, "generate_ml_pick", lambda _pred: _pick())
    monkeypatch.setattr(match_detail, "MONEYLINE_PICKS_ENABLED", True)
    return SimpleNamespace(calls=calls, state=state)


def _build(match_id: int = 5):
    return asyncio.run(match_detail.build_match_detail(None, None, match_id, TODAY))


def test_surface_elo_reads_the_match_surface():
    assert surface_elo(_elo(), "Hard") == 1968.0
    assert surface_elo(_elo(), "clay") == 1881.0
    assert surface_elo(_elo(), None) is None
    assert surface_elo(_elo(), "Carpet") is None
    assert surface_elo(None, "Hard") is None


def test_ref_date_never_runs_past_today():
    assert prediction_ref_date(date(2026, 9, 29), TODAY) == TODAY
    assert prediction_ref_date(TODAY, TODAY) == TODAY
    assert prediction_ref_date(date(2026, 9, 27), TODAY) == date(2026, 9, 27)


def test_winner_side():
    assert winner_side(_match(winner_id=None)) is None
    assert winner_side(_match(winner_id=1)) == "p1"
    assert winner_side(_match(winner_id=2)) == "p2"
    assert winner_side(_match(winner_id=99)) is None


def test_unknown_match_is_none(repos):
    assert _build(404) is None


def test_upcoming_match_predicts_live_through_the_shared_path(repos):
    repos.state["match"] = _match(match_date=date(2026, 9, 29))

    detail = _build()

    assert detail.prediction_source == "live"
    assert detail.prediction.p1_win_prob == 0.524
    assert detail.ml_pick.edge_pct == 14.9
    [(matches, ref_date)] = repos.calls["predict"]
    assert [m.id for m in matches] == [5]
    assert ref_date == TODAY


def test_moneyline_picks_off_leaves_no_pick_on_a_priced_prediction(repos, monkeypatch):
    monkeypatch.setattr(match_detail, "MONEYLINE_PICKS_ENABLED", False)

    detail = _build()

    assert detail.prediction.p1_win_prob == 0.524
    assert detail.ml_pick is None


def test_detail_carries_players_h2h_and_format(repos):
    detail = _build()

    assert (detail.p1.name, detail.p1.hand, detail.p1.country) == ("Jakub Mensik", "R", "CZE")
    assert (detail.p2.rank, detail.p2.elo, detail.p2.elo_surface) == (7, 1980.0, 1994.0)
    assert detail.h2h == {"p1_wins": 1, "p2_wins": 2}
    assert detail.h2h_surface == {"p1_wins": 1, "p2_wins": 1}
    assert detail.tour_label == "ATP"
    assert detail.best_of == 3


def test_a_skipped_prediction_leaves_no_pick(repos):
    repos.state["predicted"] = []

    detail = _build()

    assert detail.prediction is None
    assert detail.prediction_source is None
    assert detail.ml_pick is None


def test_a_completed_match_is_never_predicted_live(repos):
    repos.state["match"] = _match(status="completed", winner_id=1)

    detail = _build()

    assert repos.calls["predict"] == []
    assert detail.prediction is None


def test_a_completed_match_shows_its_stored_pre_match_prediction(repos):
    repos.state["match"] = _match(status="completed", winner_id=1)
    repos.state["stored"] = _stored()

    detail = _build()

    assert repos.calls["predict"] == []
    assert repos.calls["stored"] == [(5, repos.state["match"].start_utc)]
    assert detail.prediction_source == "stored"
    assert detail.prediction_generated_at == GENERATED
    assert detail.model_version == "ensemble-v6"
    assert detail.prediction.p1_win_prob == 0.52
    assert detail.prediction.p1_odds_american == 120
    assert detail.ml_pick is not None


def test_a_completed_match_without_a_stored_row_has_no_prediction(repos):
    repos.state["match"] = _match(status="completed", winner_id=2)

    detail = _build()

    assert detail.prediction is None
    assert detail.prediction_source is None
    assert detail.ml_pick is None


def test_a_completed_match_without_a_start_reads_nothing(repos):
    repos.state["match"] = replace(_match(status="completed", winner_id=1), start_utc=None)
    repos.state["stored"] = _stored()

    detail = _build()

    assert repos.calls["stored"] == []
    assert detail.prediction is None


def test_stored_output_mirrors_the_live_shape():
    out = stored_prediction_output(
        _stored(), _match(status="completed"), "Jakub Mensik", "Ben Shelton", "ATP", 3,
        {"p1_wins": 1, "p2_wins": 2},
    )

    assert (out.p1_win_prob, round(out.p2_win_prob, 2)) == (0.52, 0.48)
    assert (out.p1_elo_prob, out.p1_ml_prob, out.p1_market_prob) == (0.46, 0.62, 0.45)
    assert out.ensemble_weights == {"elo": 0.3, "ml": 0.4, "market": 0.3}
    assert out.quality_flags == ["h2h_small_sample"]
    assert (out.h2h_p1_wins, out.h2h_p2_wins) == (1, 2)
    assert (out.tour_label, out.best_of, out.surface) == ("ATP", 3, "Hard")


def test_stored_output_without_an_ensemble_has_no_probabilities():
    out = stored_prediction_output(
        _stored(p1_ensemble_prob=None), _match(), "A", "B", "ATP", 3, {"p1_wins": 0, "p2_wins": 0},
    )

    assert out.p1_win_prob is None and out.p2_win_prob is None


class _Row:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class _Db:
    def __init__(self, row):
        self.row = row
        self.params = None

    async def execute(self, _sql, params):
        self.params = params
        return _Row(self.row)


def test_prestart_prediction_reads_the_row_and_defaults_empty_json():
    start = datetime(2026, 9, 28, 10, 30, tzinfo=timezone.utc)
    db = _Db((GENERATED, "ensemble-v6", 0.46, 0.62, 0.45, 0.52, None, None, None, None))

    stored = asyncio.run(get_prestart_prediction(db, 5, start))

    assert db.params == {"mid": 5, "start": start}
    assert stored.generated_at == GENERATED and stored.p1_ensemble_prob == 0.52
    assert stored.ensemble_weights == {} and stored.quality_flags == []
    assert stored.p1_odds is None


def test_no_prestart_prediction_is_none():
    start = datetime(2026, 9, 28, 10, 30, tzinfo=timezone.utc)
    assert asyncio.run(get_prestart_prediction(_Db(None), 5, start)) is None


def _request():
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(registry=None)))


def test_route_returns_404_for_an_unknown_match(repos):
    with pytest.raises(HTTPException) as err:
        asyncio.run(tennis_router.get_match_detail(404, _request(), None))
    assert err.value.status_code == 404


def test_route_maps_the_detail_to_camel_case(repos):
    body = asyncio.run(tennis_router.get_match_detail(5, _request(), None)).model_dump(by_alias=True)

    assert body["matchId"] == 5
    assert body["indoor"] is True
    assert body["bestOf"] == 3
    assert body["winnerSide"] is None
    assert body["p1"]["eloSurface"] == 1968.0
    assert body["h2h"] == {"p1Wins": 1, "p2Wins": 2, "surfaceP1Wins": 1, "surfaceP2Wins": 1}
    assert body["prediction"]["p1WinProb"] == 0.524
    assert body["predictionSource"] == "live"
    assert body["mlPick"]["evPct"] == 16.3
    assert body["meetings"] == [{
        "matchDate": date(2026, 2, 18), "tournament": "Doha", "round": "R16",
        "surface": "Hard", "score": "6-2 6-1", "winnerSide": "p1",
    }]

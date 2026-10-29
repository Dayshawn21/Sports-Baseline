"""Best-picks orchestration, pinned to its exact output before and after it moved
out of the tennis router (47a). Every database and provider call is stubbed;
the pick logic itself (`build_best_picks`) is stubbed too, since it did not move."""
import asyncio
from datetime import date
from types import SimpleNamespace

from app.repositories import matches as match_repo
from app.routers import props as props_router
from app.routers.props import MarketTotal
from app.services.tennis import best_picks_response as target
from app.services.tennis.best_picks import BestPick

TODAY = date(2026, 10, 27)
START = "2026-10-27T14:00:00Z"

# Captured from the router implementation before the move.
GOLDEN = '{"date":"2026-10-27","count":1,"matches":[{"match_id":1,"start_utc":"2026-10-27T14:00:00Z","p1_name":"P1 1","p2_name":"P2 1","tour":"WTA","tour_label":"WTA","surface":"hard","tournament":"Tokyo","round":"R16","p1_win_prob":0.61,"p2_win_prob":0.39,"p1_odds_american":-150,"p2_odds_american":130,"h2h_p1_wins":2,"h2h_p2_wins":1,"picks":[{"pick_type":"prop","label":"Aces OVER 4.5","pick":"OVER 4.5","player_name":"P1 1","edge_pct":12.5,"confidence":"STRONG","reasoning":"Serve form","odds_american":-110,"ev_pct":4.2,"model_prob":0.55,"market_prob":0.52,"kelly_fraction":0.03,"data_quality_flags":["thin_sample"],"odds_source":"posted"}]}]}'
PLAYER_PROP = SimpleNamespace(player_id=30)
ODDS_PROP = SimpleNamespace(player_id=None)


def _pred(match_id: int):
    return SimpleNamespace(match_id=match_id, p1_odds_american=-150, p2_odds_american=130)


def _match_picks(match_id: int, picks: list[BestPick]):
    return SimpleNamespace(
        match_id=match_id, start_utc=START, p1_name=f"P1 {match_id}", p2_name=f"P2 {match_id}",
        tour="WTA", tour_label=None, surface="hard", tournament="Tokyo", round="R16",
        p1_win_prob=0.61, p2_win_prob=0.39, p1_odds_american=-150, p2_odds_american=130,
        h2h_p1_wins=2, h2h_p2_wins=1, picks=picks,
    )


PICK = BestPick(
    pick_type="prop", label="Aces OVER 4.5", pick="OVER 4.5", player_name="P1 1", edge_pct=12.5,
    confidence="STRONG", reasoning="Serve form", odds_american=-110, ev_pct=4.2, model_prob=0.55,
    market_prob=0.52, kelly_fraction=0.03, data_quality_flags=("thin_sample",),
)


def _stub_io(monkeypatch, calls: dict):
    async def predictions(_db, _registry, dates, _today):
        calls["dates"] = dates
        return [_pred(1), _pred(2)]

    async def player_props(_db):
        return [PLAYER_PROP]

    async def odds_props(_db, books):
        calls["books"] = books
        return [ODDS_PROP]

    async def upcoming(_db, dates):
        return [SimpleNamespace(id=1, p1_id=10, p2_id=11), SimpleNamespace(id=2, p1_id=20, p2_id=21)]

    async def rolling(_db, ids):
        calls["rolling_ids"] = sorted(ids)
        return {"rs": True}

    async def opponents(_db, _props):
        return {10: 11}

    async def totals(_db, _props):
        return {1: MarketTotal(21.5, -110, -110)}

    def enrich(*args):
        calls["enrich_args"] = args
        return ["line"]

    def build(pred, all_props, rolling_stats, pair, totals):
        calls.setdefault("build", []).append((pred.match_id, all_props, pair, totals))
        return _match_picks(pred.match_id, [PICK] if pred.match_id == 1 else [])

    monkeypatch.setattr(target, "cached_predictions", predictions)
    monkeypatch.setattr(target, "get_today_props", player_props)
    monkeypatch.setattr(target, "get_today_match_odds_as_props", odds_props)
    monkeypatch.setattr(match_repo, "get_upcoming", upcoming)
    monkeypatch.setattr(target, "get_rolling_stats_batch_all_surfaces", rolling)
    monkeypatch.setattr(target, "build_best_picks", build)
    monkeypatch.setattr(props_router, "_fetch_opponent_ids", opponents)
    monkeypatch.setattr(props_router, "_fetch_market_totals", totals)
    monkeypatch.setattr(props_router, "enrich_with", enrich)


def _run(match_date=None):
    return asyncio.run(target.build_best_picks_response(None, "registry", match_date, TODAY))


def test_orchestration_output_is_unchanged(monkeypatch):
    calls: dict = {}
    _stub_io(monkeypatch, calls)
    response = _run()
    assert response.model_dump_json() == GOLDEN
    assert calls["dates"] == [TODAY, date(2026, 10, 28)]
    assert calls["rolling_ids"] == [10, 11, 20, 21, 30]
    # 48f: PrizePicks lines are never cards, so best picks no longer builds board rows.
    assert "enrich_args" not in calls
    assert calls["build"][0] == (1, [PLAYER_PROP, ODDS_PROP], (10, 11), {1: 21.5})

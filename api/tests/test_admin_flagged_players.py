import asyncio
from datetime import date
from types import SimpleNamespace

import pytest

from app.repositories import matches as match_repo
from app.repositories import players as player_repo
from app.routers import admin
from app.services.tennis import predictor
from app.services.tennis.flagged_players import FlaggedPlayerRow, collect_flags, load_flagged_players

TODAY = date(2026, 11, 17)
REGISTRY = object()


class _FixedDate(date):
    @classmethod
    def today(cls) -> date:
        return TODAY


def _match(match_id: int, p1: int, p2: int, surface: str | None) -> SimpleNamespace:
    return SimpleNamespace(id=match_id, p1_id=p1, p2_id=p2, surface=surface)


def _pred(match_id: int, *flags: str) -> SimpleNamespace:
    return SimpleNamespace(match_id=match_id, quality_flags=list(flags))


def _player(name: str, tour: str = "ATP", ta_slug: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(name=name, tour=tour, ta_slug=ta_slug)


PREDICTIONS = [
    _pred(1, "p1_elo_missing", "odds_missing"),
    _pred(2, "ml_features_partial"),
    _pred(3, "elo_missing"),
    _pred(4, "p2_elo_missing"),
    _pred(99, "elo_missing"),
    _pred(5),
]
MATCHES = [
    _match(1, 10, 11, "Hard"),
    _match(2, 20, 21, "Clay"),
    _match(3, 30, 31, None),
    _match(4, 40, 41, "Grass"),
    _match(5, 50, 51, "Hard"),
]
PLAYERS = {
    10: _player("Felix Auger-Aliassime"),
    20: _player("Aryna Sabalenka", "WTA", "ArynaSabalenka"),
    21: _player("Iga Swiatek", "WTA"),
    30: _player("Jo-Wilfried Tsonga"),
    31: _player("Gael Monfils"),
}
ELO = {
    10: SimpleNamespace(elo=None),
    30: SimpleNamespace(elo=1700.0),
}
STATS = {
    (20, None): object(),
    (21, None): object(),
    (21, "Clay"): object(),
    (31, "Hard"): object(),
}


def _stub(monkeypatch: pytest.MonkeyPatch, calls: dict) -> None:
    async def predict_today(db, registry, dates):
        calls["predict"] = (registry, dates)
        return PREDICTIONS

    async def get_upcoming(db, dates):
        calls["upcoming"] = dates
        return MATCHES

    async def get_players_by_ids(db, ids):
        calls["ids"] = ids
        return {pid: PLAYERS[pid] for pid in ids if pid in PLAYERS}

    async def get_latest_elo_batch(db, ids):
        return {pid: ELO[pid] for pid in ids if pid in ELO}

    async def get_rolling_stats_batch_all_surfaces(db, ids, period):
        calls["period"] = period
        return {key: row for key, row in STATS.items() if key[0] in ids}

    monkeypatch.setattr(admin, "date", _FixedDate)
    monkeypatch.setattr(predictor, "predict_today", predict_today)
    monkeypatch.setattr(match_repo, "get_upcoming", get_upcoming)
    monkeypatch.setattr(player_repo, "get_players_by_ids", get_players_by_ids)
    monkeypatch.setattr(player_repo, "get_latest_elo_batch", get_latest_elo_batch)
    monkeypatch.setattr(
        player_repo, "get_rolling_stats_batch_all_surfaces", get_rolling_stats_batch_all_surfaces
    )


def _request() -> SimpleNamespace:
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(registry=REGISTRY)))


GOLDEN = (
    '{"count":3,"players":['
    '{"playerId":10,"playerName":"Felix Auger-Aliassime","tour":"ATP","flags":["p1_elo_missing"],'
    '"hasElo":false,"hasStats":false,"missingSurfaces":[],"taSlug":null,"autoSlug":"FelixAugerAliassime"},'
    '{"playerId":20,"playerName":"Aryna Sabalenka","tour":"WTA","flags":["ml_features_partial"],'
    '"hasElo":false,"hasStats":true,"missingSurfaces":["Clay"],"taSlug":"ArynaSabalenka",'
    '"autoSlug":"ArynaSabalenka"},'
    '{"playerId":31,"playerName":"Gael Monfils","tour":"ATP","flags":["elo_missing"],"hasElo":false,'
    '"hasStats":false,"missingSurfaces":[],"taSlug":null,"autoSlug":"GaelMonfils"}'
    ']}'
)


def test_flagged_players_response_is_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict = {}
    _stub(monkeypatch, calls)
    response = asyncio.run(admin.get_flagged_players(_request(), db=None))
    assert response.model_dump_json(by_alias=True) == GOLDEN
    assert calls["predict"] == (REGISTRY, [TODAY, date(2026, 11, 18)])
    assert calls["upcoming"] == [TODAY, date(2026, 11, 18)]
    assert calls["ids"] == [10, 20, 21, 30, 31, 41]
    assert calls["period"] == "last_52w"


def test_no_flags_skips_the_player_reads(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict = {}
    _stub(monkeypatch, calls)

    async def clean(db, registry, dates):
        return [_pred(1, "odds_missing")]

    monkeypatch.setattr(predictor, "predict_today", clean)
    response = asyncio.run(admin.get_flagged_players(_request(), db=None))
    assert response.model_dump_json(by_alias=True) == '{"count":0,"players":[]}'
    assert "ids" not in calls


def test_collect_flags_attributes_each_flag_to_its_players() -> None:
    collected = collect_flags(PREDICTIONS, {m.id: m for m in MATCHES})
    assert collected.flags == {
        10: {"p1_elo_missing"},
        20: {"ml_features_partial"},
        21: {"ml_features_partial"},
        30: {"elo_missing"},
        31: {"elo_missing"},
        41: {"p2_elo_missing"},
    }
    assert collected.surfaces == {20: {"Clay"}, 21: {"Clay"}}


def test_load_flagged_players_returns_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub(monkeypatch, {})
    rows = asyncio.run(load_flagged_players(None, REGISTRY, TODAY))
    assert [row.player_id for row in rows] == [10, 20, 31]
    assert rows[1] == FlaggedPlayerRow(
        player_id=20,
        player_name="Aryna Sabalenka",
        tour="WTA",
        flags=["ml_features_partial"],
        has_elo=False,
        has_stats=True,
        missing_surfaces=["Clay"],
        ta_slug="ArynaSabalenka",
        auto_slug="ArynaSabalenka",
    )

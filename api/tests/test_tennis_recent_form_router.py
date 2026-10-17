import asyncio
from datetime import date
from types import SimpleNamespace

from app.repositories.matches import MatchPlayer, RecentMatchResult
from app.routers import tennis


def test_recent_form_response_includes_last_52_week_stats(monkeypatch):
    async def players(_db, _match_id):
        return date(2026, 9, 22), [MatchPlayer(11, "Alycia Parks"), MatchPlayer(22, "Mei Yamaguchi")]

    async def results(_db, _ids, _before_date):
        return {11: [RecentMatchResult(date(2026, 9, 20), "Opponent", "6-4 6-4", "W")], 22: []}

    async def stats(_db, _ids):
        return {(11, None): SimpleNamespace(svc_pts_won=.584, ret_pts_won=.450, aces_per_game=.04, df_per_game=.03, hold_pct=.684, break_pct=.458, win_rate=.581)}

    monkeypatch.setattr(tennis.match_repo, "get_match_players", players)
    monkeypatch.setattr(tennis.match_repo, "get_recent_completed_matches", results)
    monkeypatch.setattr(tennis, "get_rolling_stats_batch_all_surfaces", stats)

    response = asyncio.run(tennis.get_match_recent_form(99, db=object()))

    assert response.players[0].last_52_w is not None
    assert response.players[0].last_52_w.hold_pct == .684
    assert response.players[0].matches[0].result == "W"
    assert response.players[1].last_52_w is None

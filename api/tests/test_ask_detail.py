import json

import pytest
from pydantic import ValidationError

from app.core.ask_detail import (
    MAX_GAME_PROPS,
    VERDICT_MEANING,
    nfl_lines,
    trim_clv_record,
    trim_nba_game,
    trim_nfl_game,
    trim_nfl_player,
    trim_ranking_record,
    trim_tennis_grading,
    trim_tennis_match,
    trim_tennis_player,
)
from app.schemas.ask import GetGameDetailInput

SIZE_BUDGET = 12_000


def _nba_detail() -> dict:
    return {
        "game_id": 7, "away_team": "POR", "home_team": "LAL", "start_utc": "2026-10-28T03:00:00Z",
        "status": "scheduled", "away_score": None, "home_score": None,
        "moneyline": {"book": "draftkings", "home_odds": -125, "away_odds": 105, "home_win_probability": 0.53246},
        "spread": {"home_line": -1.5}, "total": {"line": 233.5},
        "line_movement": [{"market": "spread", "open_line": -1.5, "current_line": -2.5}],
        "injury_report": {"source": "ESPN", "freshness": "fresh", "injuries": [
            {"player_name": "Adou Thiero", "team": "LAL", "status": "Out", "detail": "x" * 400},
        ]},
        "team_stats": {"away": {"team": "POR", "stats": {"points": {
            "for_": {"per_game": 126.0, "rank": 2}, "allowed": {"per_game": 101.5, "rank": 2}}}}},
    }


def _nba_line(player_id: int, name: str, market: str, odds_type: str = "standard", gap: float = 1.0) -> dict:
    return {"player_id": player_id, "player_name": name, "team": "POR", "market": market, "odds_type": odds_type,
            "line": 10.5, "projection": 10.5 + gap, "gap": gap, "p_over": None, "flags": [],
            "recent": [{"value": v} for v in (8, 12, 9, 14, 11, 30)]}


def _nfl_slate_game(lines: list[dict]) -> dict:
    return {"gameId": 3, "odds": {"book": "draftkings", "homeSpread": -2.5, "total": 41.5},
            "model": {"homeSpread": -3.3, "total": 39.4, "homeWinProbability": 0.615}, "lines": lines}


def _nfl_line(player_id: int, name: str, odds_type: str = "standard", segment: str = "full_game") -> dict:
    return {"playerId": player_id, "playerName": name, "position": "QB", "market": "passing_yards",
            "oddsType": odds_type, "segment": segment, "line": 223.5, "projection": 241.82, "edge": 18.32,
            "pOver": 0.61, "gamesInSample": 6}


def _record(verdicts: tuple[str, ...] = ("insufficient", "reject")) -> dict:
    return {
        "season": 2026, "model_version": "v4", "over_probability_version": "p1", "last_settled_week": 7,
        "rule": {"min_picks": 200}, "funnel": {"calls": 100, "picks": 10},
        "slices": [
            {"odds_type": "standard", "side": side, "verdict": verdict, "n": 157, "weeks": 5,
             "hit_rate": 0.52866, "standard_error": 0.0398, "break_even": 0.57737}
            for side, verdict in zip(("over", "under"), verdicts)
        ],
    }


class TestNbaGame:
    def test_props_are_listed_by_player_never_by_gap(self):
        lines = [_nba_line(2, "Zion", "points", gap=9.0), _nba_line(1, "Anfernee", "rebounds", gap=0.1),
                 _nba_line(1, "Anfernee", "assists", gap=4.0)]
        data, _ = trim_nba_game(_nba_detail(), {"lines": lines}, None)
        assert [(p["player"], p["market"]) for p in data["props"]] == [
            ("Anfernee", "assists"), ("Anfernee", "rebounds"), ("Zion", "points")]
        assert all(p["signal"] == "reference_only" for p in data["props"])
        assert data["props"][0]["last_5"] == [8, 12, 9, 14, 11]

    def test_default_shows_standard_lines_and_points_to_player_id(self):
        lines = [_nba_line(n, f"P{n:02d}", "points") for n in range(30)] + [_nba_line(99, "Goblin", "points", "goblin")]
        data, note = trim_nba_game(_nba_detail(), {"lines": lines}, None)
        assert len(data["props"]) == MAX_GAME_PROPS
        assert "Goblin" not in {p["player"] for p in data["props"]}
        assert note == "31 lines; showing 20 standard lines by player. Pass player_id for one player's full lines."
        assert len(json.dumps(data)) < SIZE_BUDGET

    def test_player_filter_returns_every_payout_type(self):
        lines = [_nba_line(5, "Scoot", "points"), _nba_line(5, "Scoot", "points", "demon"), _nba_line(6, "Other", "points")]
        data, note = trim_nba_game(_nba_detail(), {"lines": lines}, 5)
        assert [p["odds_type"] for p in data["props"]] == ["standard", "demon"] or \
            sorted(p["odds_type"] for p in data["props"]) == ["demon", "standard"]
        assert {p["player"] for p in data["props"]} == {"Scoot"} and note is None

    def test_game_injuries_and_stats_are_compact(self):
        data, _ = trim_nba_game(_nba_detail(), None, None)
        assert data["game"]["signal"] == "none" and data["game"]["url"] == "/nba/game/7"
        assert data["game"]["market_home_win_probability"] == 0.532
        assert len(data["injuries"]["players"][0]["detail"]) == 140
        assert data["team_stats_per_game"]["POR"]["points"] == {"for": 126.0, "for_rank": 2, "allowed": 101.5, "allowed_rank": 2}
        assert data["props"] == []


class TestNflGame:
    def test_slate_market_model_and_full_game_props(self):
        lines = [_nfl_line(1, "Bo Nix"), _nfl_line(1, "Bo Nix", segment="first_half"), _nfl_line(2, "Ali", "goblin")]
        data, note = trim_nfl_game(
            {"game_id": 3, "away_team": "KC", "home_team": "DEN", "season": 2026, "week": 8},
            _nfl_slate_game(lines),
            {"line_movement": [{"market": "total", "open_line": 41.5, "current_line": 40.5}],
             "away_form": {"rest_days": 7, "short_week": False, "recent": [
                 {"result": "L", "points_for": 3, "points_against": 20, "is_home": False, "opponent": "SEA"}]},
             "home_stats": {"points": {"value": 20.6123, "rank": 24}, "games": 7}},
            None,
        )
        assert data["game"]["model_not_a_pick"] == {"home_spread": -3.3, "total": 39.4, "home_win_probability": 0.615}
        assert data["game"]["signal"] == "reference_only"
        assert [p["player"] for p in data["props"]] == ["Bo Nix"]
        assert data["props"][0]["gap"] == 18.32 and data["props"][0]["url"] == "/nfl/player/1"
        assert data["away_form"]["last_3"] == ["L 3-20 at SEA"]
        assert data["home_team_stats"] == {"points": {"value": 20.61, "rank": 24}}
        assert note == "2 lines; showing 1 standard lines by player. Pass player_id for one player's full lines."

    def test_missing_stored_slate_is_explained(self):
        data, note = trim_nfl_game({"game_id": 3, "away_team": "KC", "home_team": "DEN"}, None, None, None)
        assert data["game"]["model_not_a_pick"] is None and data["props"] == []
        assert "stored NFL slate for this week is not available" in note

    def test_nfl_lines_keep_full_game_only(self):
        lines = nfl_lines(_nfl_slate_game([_nfl_line(1, "A"), _nfl_line(1, "A", segment="first_quarter")]))
        assert len(lines) == 1 and lines[0]["signal"] == "reference_only"


def test_tennis_match_model_is_reference_and_says_moneylines_are_off():
    data = trim_tennis_match({
        "match": {"id": 9, "tour": "WTA", "start_utc": "2026-10-28 01:30:00+00:00", "status": "scheduled"},
        "meta": {"indoor": True}, "tour_label": "WTA", "best_of": 3,
        "p1": {"player_id": 11, "name": "Alexandrova", "rank": 33, "elo": 1878.5},
        "p2": {"player_id": 12, "name": "Rakhimova", "rank": 66, "elo": 1762.1},
        "h2h": {"p1_wins": 0, "p2_wins": 1}, "h2h_surface": None,
        "prediction": {"p1_win_prob": 0.75279, "p1_market_prob": 0.719, "quality_flags": []},
        "model_version": "ensemble-v3+lgbm-v6",
    })
    assert data["model"]["signal"] == "reference_only"
    assert "moneyline picks are off" in data["model"]["label"]
    assert data["players"]["p1"]["url"] == "/tennis/player/11"
    assert data["head_to_head"] == "0-1" and data["head_to_head_this_surface"] is None
    assert data["match"]["start"] == "Tue Oct 27, 8:30 PM CT"


def test_nfl_player_keeps_recent_games_and_labels_past_lines_as_anecdote():
    detail = {
        "player_id": 920, "name": "Patrick Mahomes", "position": "QB", "team": "KC", "depth_position": "QB",
        "depth_rank": 1, "focus_market": "passing_yards", "summary": {"games": 6, "focus_per_game": 245.666},
        "game_log": [{"week": w, "opponent": "SEA", "team_score": 3, "opponent_score": 20, "passing_yards": 165,
                      "focus_line": 219.5, "focus_outcome": "under"} for w in range(10)],
        "past_lines": [{"market": "passing_yards", "overs": 3, "decided": 5}],
    }
    data = trim_nfl_player(detail, [{"market": "passing_yards", "url": "/nfl/player/920", "signal": "reference_only"}])
    assert data["player"]["depth"] == "QB1" and data["player"]["focus_per_game"] == 245.7
    assert len(data["recent_games"]) == 6 and data["recent_games"][0]["passing_yards"] == 165
    assert "anecdote" in data["past_lines_label"]
    assert data["this_week_lines"][0]["signal"] == "reference_only"


def test_tennis_player_summarizes_record_and_next_match():
    data = trim_tennis_player(
        {"header": {"id": 5, "name": "Alexandrova", "tour": "WTA"}, "rank": 33,
         "elo": {"history": [{"overall": 1900.4}, {"overall": 1878.5}], "tour_rank": 28},
         "next_match": {"match_id": 9, "opponent_name": "Rakhimova", "start_utc": "2026-10-28 01:30:00+00:00"}},
        {"log": [{"match": {"match_date": "2026-10-20", "opponent_name": "X", "won": True, "score": "6-3 6-4"}}],
         "record": {"window_start": "2025-10-27", "all": {"wins": 30, "losses": 15}, "hard": {"wins": 20, "losses": 9}}},
    )
    assert data["player"]["elo"] == 1878.0 and data["next_match"]["url"] == "/tennis/match/9"
    assert data["recent_matches"] == [{"date": "2026-10-20", "tournament": None, "round": None, "opponent": "X",
                                       "opponent_rank": None, "result": "W", "score": "6-3 6-4"}]
    assert data["record_52_weeks"] == {"all": "30-15", "hard": "20-9"}


def test_ranking_slices_explain_each_verdict():
    data = trim_ranking_record(_record(), "nfl", "label")
    over, under = data["slices"]
    assert over["meaning"] == VERDICT_MEANING["insufficient"] and "not validated" in over["meaning"]
    assert under["meaning"] == VERDICT_MEANING["reject"]
    assert over["picks_needed"] == 200 and over["hit_rate"] == 0.529 and over["url"] == "/nfl/model"


def test_clv_and_tennis_grading_carry_their_baselines():
    clv = trim_clv_record({"rule": {"verdict_picks": 150}, "markets": [{
        "market": "spread", "verdict": "accruing",
        "headline": {"n": 56, "mean_clv": 0.0268, "standard_error": 0.1415, "wins": 30, "losses": 23, "pushes": 3}}]})
    assert clv["markets"][0]["record_vs_entry_line"] == "30-23-3" and clv["markets"][0]["picks_needed"] == 150
    tennis = trim_tennis_grading(
        {"model_version": "ensemble-v3", "groups": [{"group": "ATP", "n": 120, "components": [
            {"name": "market"}, {"name": "ensemble", "vs_market": {"mean": -0.00161, "standard_error": 0.0017}}]}]},
        {"break_even": 0.57737, "verdict_sample": 200, "projection_version": "props-v2", "tiers": [
            {"tier": "LOCK", "verdict": "reject", "decided": 220, "hit_rate": 0.527, "standard_error": 0.034}]},
    )
    assert tennis["ensemble_vs_market"][0]["log_loss_vs_market"] == -0.0016
    assert "above zero means worse" in tennis["ensemble_vs_market_label"]
    assert tennis["prop_tiers"][0]["meaning"] == VERDICT_MEANING["reject"]
    assert tennis["prop_tiers_label"].startswith("retired PrizePicks tier record (props-v2), history only")


def test_player_filter_is_rejected_for_tennis_games():
    with pytest.raises(ValidationError, match="use get_player"):
        GetGameDetailInput.model_validate({"sport": "tennis", "game_id": 1, "player_id": 2})

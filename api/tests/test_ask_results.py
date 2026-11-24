import datetime as dt
import json

import pytest

from app.core.ask_results import (
    MAX_GAMES,
    ct_label,
    is_priced_best_bet,
    signal_for,
    trim_nba_gaps,
    trim_nba_slate,
    trim_nfl_slate,
    trim_tennis_picks,
    trim_tennis_slate,
)

SIZE_BUDGET = 12_000
START = "2026-10-28T00:30:00Z"
NOW = dt.datetime(2026, 10, 27, 12, 0, tzinfo=dt.UTC)


def _nba_game(game_id: int) -> dict:
    return {
        "game_id": game_id, "start_utc": START, "status": "scheduled", "away_team": "BOS", "home_team": "NYK",
        "away_score": None, "home_score": None, "away_record": {"wins": 2, "losses": 1},
        "home_record": {"wins": 1, "losses": 2}, "prop_line_count": 140,
        "moneyline": {"book": "draftkings", "home_odds": 120, "away_odds": -140, "home_win_probability": 0.43211},
        "spread": {"book": "draftkings", "home_line": 3.5}, "total": {"book": "draftkings", "line": 221.5},
        "line_movement": [{"market": "spread"}],
    }


def _nfl_game(game_id: int, model: bool = True) -> dict:
    return {
        "gameId": game_id, "startUtc": START, "status": "scheduled", "awayTeam": "KC", "homeTeam": "BUF",
        "awayContext": {"wins": 6, "losses": 1}, "homeContext": {"wins": 5, "losses": 2},
        "odds": {"book": "draftkings", "homeMoneyline": -130, "awayMoneyline": 110, "homeSpread": -2.5, "total": 47.5},
        "model": {"homeSpread": -1.04, "total": 45.88, "homeWinProbability": 0.5512} if model else None,
        "lines": [{"lineId": n} for n in range(300)],
    }


def _prediction(match_id: int, start: str = START) -> dict:
    return {
        "match_id": match_id, "start_utc": start, "p1_name": "Iga Swiatek", "p2_name": "Coco Gauff",
        "tour": "WTA", "tour_label": "WTA", "tournament": "Tokyo", "round": "QF", "surface": "hard",
        "p1_win_prob": 0.6123, "p2_win_prob": 0.3877, "p1_odds_american": -160, "p2_odds_american": 135,
        "feature_snapshot": {"x": 1.0},
    }


def _gap(rank: int, market: str = "points") -> dict:
    return {
        "game_id": 10 + rank, "away_team": "BOS", "home_team": "NYK", "start_utc": START, "player_id": rank,
        "player_name": f"Player {rank}", "market": market, "line": 20.5, "projection": 24.04, "gap": 3.54,
        "gap_share": 0.1727,
    }


def _pick(**over) -> dict:
    base = {"pick_type": "prop", "label": "Aces OVER 4.5", "pick": "OVER 4.5", "player_name": "Iga Swiatek",
            "confidence": "LEAN", "odds_american": -110, "ev_pct": 7.0, "kelly_fraction": 0.01,
            "model_prob": 0.56, "reasoning": "Serve form"}
    base.update(over)
    return base


def _match(match_id: int, picks: list[dict]) -> dict:
    return {"match_id": match_id, "p1_name": "Iga Swiatek", "p2_name": "Coco Gauff", "tour": "WTA",
            "tour_label": "WTA", "tournament": "Tokyo", "start_utc": START, "picks": picks}


def _assert_rows(rows: list[dict]) -> None:
    assert rows
    for row in rows:
        assert row["url"].startswith("/")
        assert row["signal"] in {"pick", "reference_only", "none"}
    assert len(json.dumps(rows)) < SIZE_BUDGET


class TestSignalRule:
    @pytest.mark.parametrize("sport", ["nba", "nfl"])
    def test_nba_and_nfl_model_numbers_are_never_picks(self, sport):
        assert signal_for(sport, "pick", priced_best_bet=True) == "reference_only"
        assert signal_for(sport, "model") == "reference_only"

    def test_only_a_priced_tennis_best_bet_is_a_pick(self):
        assert signal_for("tennis", "pick", priced_best_bet=True) == "pick"
        assert signal_for("tennis", "pick", priced_best_bet=False) == "reference_only"
        assert signal_for("tennis", "fact") == "none"

    def test_a_tennis_moneyline_is_never_a_priced_best_bet(self):
        assert not is_priced_best_bet(_pick(pick_type="moneyline", confidence="LOCK", ev_pct=40, kelly_fraction=0.2))

    @pytest.mark.parametrize(
        ("over", "priced"),
        [
            ({}, True),
            ({"ev_pct": 4.9}, False),
            ({"kelly_fraction": -0.01}, False),
            ({"odds_american": None}, False),
            ({"confidence": "STRONG", "ev_pct": 9.9, "kelly_fraction": 0.05}, False),
            ({"confidence": "STRONG", "ev_pct": 10, "kelly_fraction": 0.02}, True),
            ({"confidence": "LOCK", "ev_pct": 15, "kelly_fraction": 0.029}, False),
            ({"confidence": "PASS"}, False),
        ],
    )
    def test_priced_best_bet_matches_the_slate_rule(self, over, priced):
        assert is_priced_best_bet(_pick(**over)) is priced


def test_times_read_in_central():
    assert ct_label("2026-10-28T00:30:00Z") == "Tue Oct 27, 7:30 PM CT"
    assert ct_label(dt.datetime(2026, 1, 5, 18, 0, tzinfo=dt.UTC)) == "Mon Jan 5, 12:00 PM CT"
    assert ct_label(None) is None


def test_nba_slate_rows_are_facts_with_game_links():
    rows, truncated = trim_nba_slate([_nba_game(1)])
    _assert_rows(rows)
    assert not truncated
    assert rows[0]["url"] == "/nba/game/1" and rows[0]["signal"] == "none"
    assert rows[0]["away_record"] == "2-1" and rows[0]["market_home_win_probability"] == 0.432


def test_nfl_slate_keeps_the_model_muted_and_drops_prop_detail():
    rows, _ = trim_nfl_slate([_nfl_game(5), _nfl_game(6, model=False)])
    _assert_rows(rows)
    assert rows[0]["signal"] == "reference_only" and rows[0]["model_not_a_pick"]["home_spread"] == -1.0
    assert rows[1]["signal"] == "none" and rows[1]["model_not_a_pick"] is None
    assert rows[0]["prop_lines"] == 300 and "lines" not in rows[0]


def test_tennis_slate_sorts_by_start_and_caps_with_a_flag():
    predictions = [_prediction(n, f"2026-10-28T{n % 24:02d}:00:00Z") for n in range(MAX_GAMES + 5)]
    rows, truncated = trim_tennis_slate(predictions, NOW)
    _assert_rows(rows)
    assert truncated and len(rows) == MAX_GAMES
    assert [r["start_utc"] for r in rows] == sorted(r["start_utc"] for r in rows)
    assert all(r["signal"] == "reference_only" for r in rows)
    assert "feature_snapshot" not in rows[0]


def test_nba_gaps_keep_rank_and_stay_reference():
    items = [_gap(1), _gap(2, "assists"), _gap(3), *[_gap(n) for n in range(4, 30)]]
    rows, truncated = trim_nba_gaps(items, 5)
    _assert_rows(rows)
    assert truncated and len(rows) == 5
    assert [r["player"] for r in rows[:3]] == ["Player 1", "Player 2", "Player 3"]
    assert all(r["signal"] == "reference_only" for r in rows)
    assert rows[0]["gap_share_pct"] == 17.3


def test_tennis_picks_follow_the_digest_order_and_label_angles():
    matches = [
        _match(1, [_pick(label="Total Games OVER 21.5", ev_pct=6), _pick(label="Aces OVER 4.5")]),
        _match(2, [_pick(confidence="STRONG", ev_pct=2.0), _pick(label="Aces OVER 6.5")]),
    ]
    rows, truncated = trim_tennis_picks(matches, None, 10, NOW)
    _assert_rows(rows)
    assert not truncated
    assert [(r["game_id"], r["label"]) for r in rows] == [
        (1, "Total Games OVER 21.5"), (2, "Aces OVER 6.5"), (1, "Aces OVER 4.5"), (2, "Aces OVER 4.5"),
    ]
    assert [r["signal"] for r in rows] == ["pick", "pick", "pick", "reference_only"]
    assert rows[3]["kind"] == "angle, not a best bet"


def test_tennis_market_filter_matches_the_label():
    rows, _ = trim_tennis_picks([_match(1, [_pick(label="Total Games OVER 21.5"), _pick()])], "aces", 5, NOW)
    assert [r["label"] for r in rows] == ["Aces OVER 4.5"]


def test_tennis_slate_puts_started_matches_last():
    early, late = _prediction(1, "2026-10-27T09:00:00Z"), _prediction(2, "2026-10-27T18:00:00Z")
    rows, _ = trim_tennis_slate([early, late], NOW)
    assert [(r["game_id"], r["started"]) for r in rows] == [(2, False), (1, True)]


def test_tennis_picks_skip_pass_tier_and_started_matches():
    started = {**_match(1, [_pick()]), "start_utc": "2026-10-27T09:00:00Z"}
    upcoming = _match(2, [_pick(confidence="PASS"), _pick(label="Aces OVER 6.5")])
    rows, _ = trim_tennis_picks([started, upcoming], None, 10, NOW)
    assert [(r["game_id"], r["label"]) for r in rows] == [(2, "Aces OVER 6.5")]

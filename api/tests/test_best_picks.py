from types import SimpleNamespace
from datetime import datetime, timezone
from decimal import Decimal

from app.repositories.players import PlayerRollingStats
from app.repositories.props import Prop
from app.services.tennis import best_picks
from app.services.tennis.best_picks import BestPick, generate_ml_pick
from app.services.tennis.best_picks import generate_prop_picks


def _pred(**overrides):
    data = {
        "match_id": 1,
        "start_utc": None,
        "p1_name": "Player One",
        "p2_name": "Player Two",
        "tour": "ATP",
        "tour_label": "ATP",
        "surface": "Hard",
        "tournament": "Test",
        "round": "R32",
        "best_of": 3,
        "p1_win_prob": 0.61,
        "p2_win_prob": 0.39,
        "p1_odds_american": 110,
        "p2_odds_american": -130,
        "h2h_p1_wins": 0,
        "h2h_p2_wins": 0,
        "quality_flags": [],
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_ml_pick_uses_strict_ev_threshold():
    pick = generate_ml_pick(
        _pred(
            p1_win_prob=0.55,
            p2_win_prob=0.45,
            p1_odds_american=-130,
            p2_odds_american=110,
        )
    )

    assert pick is None


def test_ml_pick_exposes_bettable_fields():
    pick = generate_ml_pick(
        _pred(
            p1_win_prob=0.62,
            p2_win_prob=0.38,
            p1_odds_american=120,
            p2_odds_american=-145,
        )
    )

    assert pick is not None
    assert pick.confidence == "STRONG"
    assert pick.model_prob == 0.62
    assert pick.market_prob is not None
    assert pick.ev_pct is not None and pick.ev_pct >= 10.0
    assert pick.kelly_fraction is not None and pick.kelly_fraction >= 0.02
    assert pick.odds_source == "posted"


def _stats(player_id: int) -> PlayerRollingStats:
    return PlayerRollingStats(
        player_id=player_id,
        surface="Hard",
        stat_period="last_52w",
        split_type=None,
        split_value=None,
        win_rate=0.55,
        svc_pts_won=0.66,
        ret_pts_won=0.37,
        aces_per_game=0.5,
        df_per_game=0.2,
        hold_pct=0.82,
        break_pct=0.22,
        matches_count=30,
    )


def test_bo5_games_won_prop_uses_match_format():
    pred = _pred(best_of=5, p1_win_prob=0.74, p2_win_prob=0.26)
    prop = Prop(
        id=1,
        player_id=2,
        player_name="Stefanos Tsitsipas",
        match_id=1,
        source="prizepicks",
        stat_type="Games Won",
        line=Decimal("16.5"),
        odds_type=None,
        fetched_at=datetime.now(timezone.utc),
        start_time=None,
        surface="Hard",
        best_of=5,
    )

    picks = generate_prop_picks(
        pred,
        [prop],
        {
            (1, "Hard"): _stats(1),
            (2, "Hard"): _stats(2),
        },
        {(1, 1): 0.74, (2, 1): 0.26},
        {(1, 1): 2, (2, 1): 1},
        {},
    )

    tsitsipas_pick = next(pick for pick in picks if "Tsitsipas" in pick.pick)
    assert "8." not in tsitsipas_pick.reasoning
    assert tsitsipas_pick.reasoning.startswith("Tsitsipas projects for 11.")


def _unpriced(label: str, score: float) -> BestPick:
    return BestPick(
        pick_type="derived", label=label, pick=label, player_name=None,
        edge_pct=50.0, confidence="LOCK", reasoning="", score=score,
    )


def test_priced_moneyline_pick_is_never_pushed_out_by_unpriced_picks(monkeypatch):
    monkeypatch.setattr(best_picks, "MONEYLINE_PICKS_ENABLED", True)
    ml = generate_ml_pick(_pred())
    assert ml is not None and ml.ev_pct is not None
    derived = [_unpriced(f"Derived {i}", ml.score + 100 + i) for i in range(3)]
    monkeypatch.setattr(best_picks, "generate_derived_picks", lambda *a, **k: derived)
    monkeypatch.setattr(best_picks, "generate_serve_edge_picks", lambda *a, **k: [])

    result = best_picks.build_best_picks(_pred(start_utc=None), [], {}, {})

    labels = [p.label for p in result.picks]
    assert labels[0] == "Moneyline"
    assert labels[1:3] == ["Derived 2", "Derived 1"]


def test_first_set_props_are_no_best_pick_until_graded():
    def prop(prop_id: int, stat_type: str) -> Prop:
        return Prop(
            id=prop_id, player_id=1, player_name="Player One", match_id=1, source="prizepicks",
            stat_type=stat_type, line=Decimal("2.5"), odds_type=None,
            fetched_at=datetime.now(timezone.utc), start_time=None, surface="Hard", best_of=3,
        )

    picks = generate_prop_picks(
        _pred(),
        [prop(1, "Total Games Won"), prop(2, "1st Set Total Games"), prop(3, "1st Set Total Games Won")],
        {(1, "Hard"): _stats(1), (2, "Hard"): _stats(2)},
        {(1, 1): 0.61, (2, 1): 0.39},
        {(1, 1): 2, (2, 1): 1},
        {},
    )

    # The games-won control clears its 2.5 line easily, so only the skip keeps the first-set lines out.
    assert any("Games Won" in pick.pick and "1st Set" not in pick.pick for pick in picks)
    assert not any("1st Set" in pick.pick or "1st set" in pick.reasoning.lower() for pick in picks)


def test_moneyline_picks_off_skips_a_priced_positive_ev_pick(monkeypatch):
    assert generate_ml_pick(_pred()) is not None
    monkeypatch.setattr(best_picks, "generate_derived_picks", lambda *a, **k: [_unpriced("Derived", 1.0)])
    monkeypatch.setattr(best_picks, "generate_serve_edge_picks", lambda *a, **k: [])

    result = best_picks.build_best_picks(_pred(start_utc=None), [], {}, {})

    assert [p.pick_type for p in result.picks] == ["derived"]

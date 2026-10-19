from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.core.prop_probs import prop_over_under_probs

from app.repositories.players import PlayerRollingStats
from app.repositories.props import Prop
from app.routers.props import enrich_with
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

    lines = enrich_with(
        [prop],
        {(1, 1): 2, (2, 1): 1},
        {(1, "Hard"): _stats(1), (2, "Hard"): _stats(2)},
        {(1, 1): 0.74, (2, 1): 0.26},
        {},
        {},
    )
    picks = generate_prop_picks(pred, lines)

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

    lines = enrich_with(
        [prop(1, "Total Games Won"), prop(2, "1st Set Total Games"), prop(3, "1st Set Total Games Won")],
        {(1, 1): 2, (2, 1): 1},
        {(1, "Hard"): _stats(1), (2, "Hard"): _stats(2)},
        {(1, 1): 0.61, (2, 1): 0.39},
        {},
        {},
    )
    picks = generate_prop_picks(_pred(), lines)

    # The games-won control clears its 2.5 line easily, so only the skip keeps the first-set lines out.
    assert any("Games Won" in pick.pick and "1st Set" not in pick.pick for pick in picks)
    assert not any("1st Set" in pick.pick or "1st set" in pick.reasoning.lower() for pick in picks)


def test_moneyline_picks_off_skips_a_priced_positive_ev_pick(monkeypatch):
    assert generate_ml_pick(_pred()) is not None
    monkeypatch.setattr(best_picks, "generate_derived_picks", lambda *a, **k: [_unpriced("Derived", 1.0)])
    monkeypatch.setattr(best_picks, "generate_serve_edge_picks", lambda *a, **k: [])

    result = best_picks.build_best_picks(_pred(start_utc=None), [], {}, {})

    assert [p.pick_type for p in result.picks] == ["derived"]


_NOW = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)


def _parity_prop(stat_type: str, line: str, **overrides) -> Prop:
    data = {
        "id": 1, "player_id": 1, "player_name": "Player One", "match_id": 1, "source": "prizepicks",
        "stat_type": stat_type, "line": Decimal(line), "odds_type": None, "fetched_at": _NOW,
        "start_time": None, "surface": "Hard", "best_of": 3,
    }
    data.update(overrides)
    return Prop(**data)


def _parity_stats() -> dict:
    fresh = datetime.now(timezone.utc)
    return {
        (1, "Hard"): replace(_stats(1), computed_at=fresh, aces_per_game=0.15),
        (2, "Hard"): replace(_stats(2), computed_at=fresh),
    }


def _board_and_cards(prop: Prop, stats=None, opponents=None, win_probs=None):
    lines = enrich_with(
        [prop],
        {(1, 1): 2, (2, 1): 1} if opponents is None else opponents,
        _parity_stats() if stats is None else stats,
        {(1, 1): 0.61, (2, 1): 0.39} if win_probs is None else win_probs,
        {},
        {},
    )
    return lines[0], generate_prop_picks(_pred(), lines)


def _assert_card_is_board_row(board, cards):
    assert len(cards) == 1
    card = cards[0]
    assert card.pick.endswith(f"{board.recommendation} {float(board.line):.1f}")
    assert card.confidence == board.confidence
    assert card.model_prob == board.hit_probability
    assert card.edge_pct == board.edge_pct
    assert card.data_quality_flags == tuple(board.data_quality_flags)


@pytest.mark.parametrize(
    ("prop", "flag"),
    [
        (_parity_prop("Aces", "5.5", match_link_invalid=True), "match_link_invalid"),
        (_parity_prop("Aces", "5.5", match_status="completed"), "match_finished"),
        (_parity_prop("Total Sets", "3.5", best_of=5), "bo5_unsupported_stat"),
    ],
)
def test_board_hard_blocks_leave_no_card(prop, flag):
    board, cards = _board_and_cards(prop)

    assert flag in board.data_quality_flags and board.recommendation is None
    assert cards == []


def test_stale_stats_card_is_capped_like_the_board():
    stats = _parity_stats()
    stats[(1, "Hard")] = replace(stats[(1, "Hard")], computed_at=datetime(2020, 1, 1, tzinfo=timezone.utc))

    board, cards = _board_and_cards(_parity_prop("Aces", "5.5"), stats=stats)

    assert board.confidence == "LEAN" and "stale_stats" in board.data_quality_flags
    _assert_card_is_board_row(board, cards)


def test_small_sample_card_is_capped_like_the_board():
    stats = _parity_stats()
    small = replace(stats.pop((1, "Hard")), matches_count=6, surface=None)
    stats[(1, None)] = small

    board, cards = _board_and_cards(_parity_prop("Aces", "5.5"), stats=stats)

    assert board.confidence == "LEAN" and "small_sample" in board.data_quality_flags
    _assert_card_is_board_row(board, cards)
    assert cards[0].reasoning.endswith("(small sample)")


@pytest.mark.parametrize(
    ("kwargs", "flag"),
    [({"opponents": {}}, "missing_opponent_stats"), ({"win_probs": {}}, "missing_prediction")],
)
def test_missing_input_card_takes_the_boards_downgrade(kwargs, flag):
    full, _ = _board_and_cards(_parity_prop("Aces", "5.5"))
    board, cards = _board_and_cards(_parity_prop("Aces", "5.5"), **kwargs)

    assert full.confidence == "LOCK"
    assert board.confidence == "STRONG" and flag in board.data_quality_flags
    _assert_card_is_board_row(board, cards)


def test_total_games_card_uses_the_boards_format_aware_probability():
    board, cards = _board_and_cards(_parity_prop("Total Games", "25.5"))

    _assert_card_is_board_row(board, cards)
    assert (board.recommendation, board.confidence) == ("UNDER", "LEAN")
    # The card's old marginal normal put this UNDER near .67, a tier above the board.
    _, old_under = prop_over_under_probs("Total Games", 25.5, board.stat_avg)
    assert old_under - board.hit_probability > 0.04


def test_integer_line_card_is_push_conditioned_like_the_board():
    board, cards = _board_and_cards(_parity_prop("Total Games", "19"))

    assert board.p_push > 0
    assert board.hit_probability == pytest.approx(board.p_over / (board.p_over + board.p_under), abs=1e-3)
    _assert_card_is_board_row(board, cards)


def test_goblin_below_break_even_is_no_card():
    board, cards = _board_and_cards(_parity_prop("Aces", "9.5", odds_type="goblin"))

    assert board.confidence == "PASS"
    assert cards == []

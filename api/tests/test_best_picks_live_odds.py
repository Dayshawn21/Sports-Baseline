from dataclasses import replace
from datetime import datetime
from decimal import Decimal

import pytest

from app.repositories.players import PlayerRollingStats
from app.repositories.props import Prop
from app.routers.props import MarketTotal, enrich_with
from app.services.tennis.best_picks import (
    generate_market_odds_picks,
    generate_ml_pick,
    generate_prop_picks,
)
from app.services.tennis.predictor import PredictionOutput


def _stats(player_id: int, hold_pct: float, break_pct: float) -> PlayerRollingStats:
    return PlayerRollingStats(
        player_id=player_id,
        surface="Hard",
        stat_period="last_52w",
        split_type="overall",
        split_value="all",
        win_rate=0.6,
        svc_pts_won=0.65,
        ret_pts_won=0.38,
        aces_per_game=0.45,
        df_per_game=0.08,
        hold_pct=hold_pct,
        break_pct=break_pct,
        matches_count=24,
        first_in_pct=0.62,
        first_won_pct=0.72,
        second_won_pct=0.51,
        dominance_ratio=1.1,
    )


def _prediction() -> PredictionOutput:
    return PredictionOutput(
        match_id=99,
        start_utc=datetime(2026, 4, 7, 18, 0, 0),
        p1_name="Jannik Sinner",
        p2_name="Carlos Alcaraz",
        tour="ATP",
        surface="Hard",
        tournament="Test Open",
        round="R16",
        p1_win_prob=0.64,
        p2_win_prob=0.36,
        p1_elo_prob=0.61,
        p1_ml_prob=0.62,
        p1_market_prob=0.58,
        ensemble_weights={"elo": 0.4, "ml": 0.4, "market": 0.2},
        quality_flags=[],
        p1_odds_american=-135,
        p2_odds_american=115,
        h2h_p1_wins=3,
        h2h_p2_wins=2,
    )


def _total_games_prop(line: str) -> Prop:
    return Prop(
        id=1,
        player_id=None,
        player_name="Jannik Sinner vs Carlos Alcaraz",
        match_id=99,
        source="bet365",
        stat_type="total_games",
        line=Decimal(line),
        odds_type=None,
        fetched_at=datetime(2026, 4, 7, 12, 0, 0),
        start_time=datetime(2026, 4, 7, 18, 0, 0),
        p1_odds=-110,
        p2_odds=-110,
        surface="Hard",
    )


def _two_big_servers() -> dict:
    return {
        (10, "Hard"): _stats(10, 0.83, 0.24),
        (20, "Hard"): _stats(20, 0.81, 0.22),
    }


def test_generate_market_odds_picks_includes_total_games():
    # Two strong servers project ~22 games, so an 18.5 line is a clear OVER.
    picks = generate_market_odds_picks(
        _prediction(), [_total_games_prop("18.5")], _two_big_servers(), (10, 20)
    )

    assert any(p.label == "Total Games" for p in picks)
    assert any("Games" in p.pick for p in picks)


def test_total_games_pick_is_skipped_when_the_line_sits_on_the_projection():
    """No edge, no pick.

    This fixture used to produce a pick because the total-games model ran ~9%
    above the market (every one of 117 projections landed over the line). With
    the model calibrated, a 22.5 line against a ~22 projection is a coin flip
    and must not be recommended.
    """
    picks = generate_market_odds_picks(
        _prediction(), [_total_games_prop("22.5")], _two_big_servers(), (10, 20)
    )

    assert not any(p.label == "Total Games" for p in picks)


def test_a_book_total_is_not_graded_against_itself():
    """With a book total on file the projection is that line, so there is no view."""
    for line in ("18.5", "22.5"):
        picks = generate_market_odds_picks(
            _prediction(), [_total_games_prop(line)], _two_big_servers(), (10, 20),
            market_total_games_map={99: 22.5},
        )
        assert not any(p.label == "Total Games" for p in picks)


def _game_spread_case() -> tuple[list[Prop], dict]:
    props = [
        Prop(
            id=2,
            player_id=None,
            player_name="Jannik Sinner vs Carlos Alcaraz",
            match_id=99,
            source="betonline.ag",
            stat_type="game_spread",
            line=Decimal("-2.5"),
            odds_type=None,
            fetched_at=datetime(2026, 4, 7, 12, 0, 0),
            start_time=datetime(2026, 4, 7, 18, 0, 0),
            p1_odds=-105,
            p2_odds=-115,
            surface="Hard",
        )
    ]
    rolling = {
        (10, "Hard"): _stats(10, 0.86, 0.28),
        (20, "Hard"): _stats(20, 0.77, 0.18),
    }
    return props, rolling


def _market_picks(flags: list[str], label: str) -> list:
    pred = replace(_prediction(), quality_flags=flags)
    if label == "Total Games":
        picks = generate_market_odds_picks(pred, [_total_games_prop("18.5")], _two_big_servers(), (10, 20))
    else:
        props, rolling = _game_spread_case()
        picks = generate_market_odds_picks(pred, props, rolling, (10, 20))
    return [p for p in picks if p.label == label]


@pytest.mark.parametrize("label", ["Total Games", "Game Spread"])
def test_market_picks_take_the_predictions_downgrade_flags(label):
    assert [p.confidence for p in _market_picks([], label)] == ["STRONG"]
    downgraded = _market_picks(["stale_odds"], label)
    assert [p.confidence for p in downgraded] == ["LEAN"]
    assert "stale_odds" in downgraded[0].data_quality_flags


@pytest.mark.parametrize("label", ["Total Games", "Game Spread"])
def test_market_picks_are_dropped_on_unreliable_elo(label):
    assert _market_picks(["elo_unreliable"], label) == []


@pytest.mark.parametrize("label", ["Total Games", "Game Spread"])
def test_market_picks_ignore_ml_flags(label):
    picks = _market_picks(["ml_missing", "ml_not_trained_for_tour"], label)
    assert [p.confidence for p in picks] == ["STRONG"]
    assert "ml_missing" in picks[0].data_quality_flags


def test_generate_market_odds_picks_includes_game_spread():
    props, rolling = _game_spread_case()

    picks = generate_market_odds_picks(_prediction(), props, rolling, (10, 20))

    assert any(p.label == "Game Spread" for p in picks)
    assert any("Sinner" in p.pick or "Alcaraz" in p.pick for p in picks)


def test_priced_picks_carry_ev_pct():
    """ev_pct is the only axis on which pick types can be ranked against each other.

    edge_pct is not: it is a prob-vs-market edge for moneyline but a
    projection-vs-line delta for props. Any pick with real book odds must
    therefore expose an EV so the frontend can order it.
    """
    picks = generate_market_odds_picks(
        _prediction(), [_total_games_prop("18.5")], _two_big_servers(), (10, 20)
    )
    ml = generate_ml_pick(_prediction())

    assert picks
    assert all(p.ev_pct is not None for p in picks)
    assert ml is not None and ml.ev_pct is not None


def test_unpriced_picks_leave_ev_pct_none():
    """A pick with no payout has no honest EV — it must not be given a fabricated one.

    PrizePicks publishes no per-leg odds, so its props reach the generator with
    p1_odds/p2_odds unset.
    """
    prop = Prop(
        id=3,
        player_id=10,
        player_name="Jannik Sinner",
        match_id=99,
        source="prizepicks",
        stat_type="aces",
        line=Decimal("4.5"),
        odds_type="standard",
        fetched_at=datetime(2026, 4, 7, 12, 0, 0),
        start_time=datetime(2026, 4, 7, 18, 0, 0),
        p1_odds=None,
        p2_odds=None,
        surface="Hard",
    )

    lines = enrich_with([prop], {(10, 99): 20}, _two_big_servers(), {(10, 99): 0.64}, {}, {99: MarketTotal(22.5)})
    picks = generate_prop_picks(_prediction(), lines)

    assert picks
    assert all(p.ev_pct is None for p in picks)

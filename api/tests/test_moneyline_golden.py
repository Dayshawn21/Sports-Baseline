"""Golden output of the two moneyline pick builders, pinned before F-61 shares their side math."""
from types import SimpleNamespace

import pytest

from app.services.tennis.bankroll_builder import BankrollPick, _generate_ml_picks
from app.services.tennis.best_picks import BestPick, generate_ml_pick

# Both reasonings carry an em dash; spelled as an escape so this file stays ASCII.
DASH = "\u2014"

_BASE = {
    "match_id": 7, "start_utc": None, "p1_name": "Jannik Sinner", "p2_name": "Carlos Alcaraz",
    "tour": "ATP", "surface": "Hard", "tournament": "Test Open", "round": "QF", "best_of": 3,
    "h2h_p1_wins": 0, "h2h_p2_wins": 0, "quality_flags": [],
}

CASES = {
    "p1_more_ev": dict(p1_win_prob=0.62, p2_win_prob=0.38, p1_odds_american=120, p2_odds_american=-145,
                       h2h_p1_wins=2, h2h_p2_wins=1),
    "p2_more_ev": dict(p1_win_prob=0.38, p2_win_prob=0.62, p1_odds_american=-145, p2_odds_american=120,
                       h2h_p1_wins=1, h2h_p2_wins=3),
    "ev_tie": dict(p1_win_prob=0.55, p2_win_prob=0.55, p1_odds_american=110, p2_odds_american=110),
    "both_sides_pass": dict(p1_win_prob=0.60, p2_win_prob=0.57, p1_odds_american=130, p2_odds_american=115),
    "soft_flags": dict(p1_win_prob=0.62, p2_win_prob=0.38, p1_odds_american=120, p2_odds_american=-145,
                       quality_flags=["odds_missing", "ml_features_partial"]),
    "neither_side_passes": dict(p1_win_prob=0.55, p2_win_prob=0.45, p1_odds_american=-130, p2_odds_american=110),
    "blocking_flag": dict(p1_win_prob=0.62, p2_win_prob=0.38, p1_odds_american=120, p2_odds_american=-145,
                          quality_flags=["elo_unreliable"]),
    "missing_price": dict(p1_win_prob=0.62, p2_win_prob=0.38, p1_odds_american=120, p2_odds_american=None),
    "missing_prob": dict(p1_win_prob=None, p2_win_prob=None, p1_odds_american=120, p2_odds_american=-145),
}


def _pred(case: str) -> SimpleNamespace:
    return SimpleNamespace(**{**_BASE, **CASES[case]})


def _best(player: str, odds: int, edge: float, conf: str, reasoning: str, ev_pct: float, model: float,
          market: float, kelly: float, score: float, flags: tuple[str, ...] = ()) -> BestPick:
    last = player.split()[-1]
    sign = "+" if odds > 0 else ""
    return BestPick(
        pick_type="moneyline", label="Moneyline", pick=f"{last} ML ({sign}{odds})", player_name=player,
        edge_pct=edge, confidence=conf, reasoning=reasoning, odds_american=odds, ev_pct=ev_pct,
        model_prob=model, market_prob=market, kelly_fraction=kelly, data_quality_flags=flags,
        odds_source="posted", score=score,
    )


def _bank(side: str, label: str, our: float, market: float, odds: int, edge: float, ev: float,
          kelly: float, conf: str, reasoning: str, score: float) -> BankrollPick:
    return BankrollPick(
        match_id=7, p1_name="Jannik Sinner", p2_name="Carlos Alcaraz", tour="ATP", surface="Hard",
        tournament="Test Open", round="QF", start_utc=None, bet_type="ml", pick_label=label,
        pick_side=side, our_prob=our, market_prob=market, odds_american=odds, edge_pct=edge, ev=ev,
        kelly_frac=kelly, confidence=conf, reasoning=reasoning, rank_score=score,
    )


_SINNER_62 = f"Model gives Sinner 62% win prob vs 43% implied {DASH} 36.4% EV at +120"
_ALCARAZ_62 = f"Model gives Alcaraz 62% win prob vs 43% implied {DASH} 36.4% EV at +120"
_SINNER_60 = f"Model gives Sinner 60% win prob vs 48% implied {DASH} 38.0% EV at +130"

BEST_PICKS = {
    "p1_more_ev": _best("Jannik Sinner", 120, 42.7, "STRONG", _SINNER_62 + " | H2H 2-1 edge",
                        36.4, 0.62, 0.4344, 0.0758, 64.05000000000001),
    "p2_more_ev": _best("Carlos Alcaraz", 120, 42.7, "STRONG", _ALCARAZ_62 + " | H2H 3-1 edge",
                        36.4, 0.62, 0.4344, 0.0758, 64.05000000000001),
    "ev_tie": _best("Carlos Alcaraz", 110, 10.0, "LEAN",
                    f"Model gives Alcaraz 55% win prob vs 50% implied {DASH} 15.5% EV at +110",
                    15.5, 0.55, 0.5, 0.0352, 10.0),
    "both_sides_pass": _best("Jannik Sinner", 130, 24.2, "STRONG", _SINNER_60,
                             38.0, 0.6, 0.4831, 0.0731, 36.3),
    "soft_flags": _best("Jannik Sinner", 120, 42.7, "STRONG", _SINNER_62,
                        36.4, 0.62, 0.4344, 0.0758, 64.05000000000001,
                        flags=("ml_features_partial", "odds_missing")),
    "neither_side_passes": None,
    "blocking_flag": None,
    "missing_price": None,
    "missing_prob": None,
}

_BANK_SINNER_62 = _bank("p1", "Sinner ML (+120)", 0.62, 0.4344, 120, 42.7, 0.364, 0.0758, "STRONG",
                        _SINNER_62, 49.68599999999999)

BANKROLL = {
    "p1_more_ev": [_BANK_SINNER_62],
    "p2_more_ev": [_bank("p2", "Alcaraz ML (+120)", 0.62, 0.4344, 120, 42.7, 0.364, 0.0758, "STRONG",
                         _ALCARAZ_62, 49.68599999999999)],
    "ev_tie": [
        _bank("p1", "Sinner ML (+110)", 0.55, 0.5, 110, 10.0, 0.155, 0.0352, "LEAN",
              f"Model gives Sinner 55% win prob vs 50% implied {DASH} 15.5% EV at +110", 6.5522727272727375),
        _bank("p2", "Alcaraz ML (+110)", 0.55, 0.5, 110, 10.0, 0.155, 0.0352, "LEAN",
              f"Model gives Alcaraz 55% win prob vs 50% implied {DASH} 15.5% EV at +110", 6.5522727272727375),
    ],
    "both_sides_pass": [
        _bank("p1", "Sinner ML (+130)", 0.6, 0.4831, 130, 24.2, 0.38, 0.0731, "STRONG",
              _SINNER_60, 49.98461538461539),
        _bank("p2", "Alcaraz ML (+115)", 0.57, 0.5169, 115, 10.3, 0.2255, 0.049, "LEAN",
              f"Model gives Alcaraz 57% win prob vs 52% implied {DASH} 22.5% EV at +115", 13.26528260869563),
    ],
    "soft_flags": [_BANK_SINNER_62],
    "neither_side_passes": [],
    "blocking_flag": [],
    "missing_price": [],
    "missing_prob": [],
}


@pytest.mark.parametrize("case", CASES)
def test_best_picks_moneyline_is_unchanged(case: str) -> None:
    assert generate_ml_pick(_pred(case)) == BEST_PICKS[case]


@pytest.mark.parametrize("case", CASES)
def test_bankroll_moneyline_is_unchanged(case: str) -> None:
    assert _generate_ml_picks(_pred(case)) == BANKROLL[case]

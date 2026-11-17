"""Golden output of the four long tennis pick generators, pinned before F-73 splits them.

The expected output lives in fixtures/tennis_pick_generators_golden.json, captured from
the unsplit code. A split must reproduce it exactly, so never regenerate it to make a
refactor pass.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Callable

import pytest

from app.repositories.players import PlayerRollingStats
from app.services.tennis.bankroll_builder import _generate_set_picks, _generate_total_picks
from app.services.tennis.best_picks import generate_derived_picks, generate_market_odds_picks

GOLDEN_PATH = Path(__file__).parent / "fixtures" / "tennis_pick_generators_golden.json"

P1_ID, P2_ID = 101, 202


def _pred(**overrides) -> SimpleNamespace:
    data = {
        "match_id": 9, "start_utc": None, "p1_name": "Jannik Sinner", "p2_name": "Carlos Alcaraz",
        "tour": "ATP", "surface": "Hard", "tournament": "Test Open", "round": "SF", "best_of": 3,
        "p1_win_prob": 0.70, "p2_win_prob": 0.30, "p1_odds_american": -200, "p2_odds_american": 170,
        "quality_flags": [],
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _stats(player_id: int, surface: str | None = None, **overrides) -> PlayerRollingStats:
    data = {
        "player_id": player_id, "surface": surface, "stat_period": "last_52w", "split_type": None,
        "split_value": None, "win_rate": 0.62, "svc_pts_won": 0.66, "ret_pts_won": 0.39,
        "aces_per_game": 0.62, "df_per_game": 0.24, "hold_pct": 0.84, "break_pct": 0.27,
        "matches_count": 30, "first_in_pct": 0.63, "first_won_pct": 0.75, "second_won_pct": 0.54,
        "dominance_ratio": 1.2,
    }
    data.update(overrides)
    return PlayerRollingStats(**data)


STRONG = _stats(P1_ID, hold_pct=0.90, break_pct=0.35, win_rate=0.78, dominance_ratio=1.6)
WEAK = _stats(P2_ID, hold_pct=0.72, break_pct=0.15, win_rate=0.45, dominance_ratio=0.85)
_NO_RATES = dict.fromkeys(
    ("win_rate", "svc_pts_won", "ret_pts_won", "aces_per_game", "df_per_game", "hold_pct", "break_pct",
     "first_in_pct", "first_won_pct", "second_won_pct", "dominance_ratio"))
EMPTY_P1 = _stats(P1_ID, **_NO_RATES)
EMPTY_P2 = _stats(P2_ID, **_NO_RATES)


def _prop(stat_type: str, line: str | None, p1_odds: int | None = -110, p2_odds: int | None = -110,
          match_id: int = 9) -> SimpleNamespace:
    return SimpleNamespace(
        match_id=match_id, stat_type=stat_type, line=None if line is None else Decimal(line),
        p1_odds=p1_odds, p2_odds=p2_odds,
    )


def _rolling(*rows: PlayerRollingStats) -> dict:
    return {(row.player_id, row.surface): row for row in rows}


BOTH = _rolling(STRONG, WEAK)
IDS = (P1_ID, P2_ID)

MARKET_ODDS_CASES: dict[str, Callable[[], list]] = {
    "no_player_ids": lambda: generate_market_odds_picks(_pred(), [_prop("Total Games", "22.5")], BOTH),
    "total_games_both_sides": lambda: generate_market_odds_picks(
        _pred(), [_prop("Total Games", "19.5", 105, -125), _prop("total_games", "26.5", -120, 100)], BOTH, IDS),
    "total_games_one_side_priced": lambda: generate_market_odds_picks(
        _pred(), [_prop("Total Games", "19.5", 110, None), _prop("Total Games", "27.5", None, 110)], BOTH, IDS),
    "total_games_one_projection": lambda: generate_market_odds_picks(
        _pred(), [_prop("Total Games", "19.5", 105, -125)], _rolling(STRONG), IDS),
    "total_games_no_projection": lambda: generate_market_odds_picks(
        _pred(), [_prop("Total Games", "19.5", 105, -125)], {}, IDS),
    "total_games_other_projection": lambda: generate_market_odds_picks(
        _pred(), [_prop("Total Games", "19.5", 105, -125)], _rolling(WEAK), IDS),
    "total_games_skip_guards": lambda: generate_market_odds_picks(
        _pred(),
        [_prop("Total Games", "10.5"), _prop("Total Games", "0"), _prop("Total Games", None),
         _prop("Total Games", "22.5", match_id=77)],
        BOTH, IDS),
    "total_games_book_total_on_file": lambda: generate_market_odds_picks(
        _pred(), [_prop("Total Games", "19.5", 105, -125)], BOTH, IDS, {9: 22.5}),
    "total_games_short_book_total": lambda: generate_market_odds_picks(
        _pred(), [_prop("Total Games", "19.5", 105, -125)], BOTH, IDS, {9: 12.5}),
    "game_spread_both_sides": lambda: generate_market_odds_picks(
        _pred(), [_prop("Game Spread", "-1.5", 110, -130), _prop("game_spread", "-6.5", -120, 100)], BOTH, IDS),
    "game_spread_one_side_priced": lambda: generate_market_odds_picks(
        _pred(), [_prop("Game Spread", "-1.5", None, 110), _prop("Game Spread", "-6.5", 105, None)], BOTH, IDS),
    "game_spread_missing_stats": lambda: generate_market_odds_picks(
        _pred(), [_prop("Game Spread", "-1.5", 110, -130)], _rolling(STRONG), IDS),
    "game_spread_empty_stats": lambda: generate_market_odds_picks(
        _pred(p1_win_prob=None, p2_win_prob=None), [_prop("Game Spread", "-1.5", 110, -130)],
        _rolling(EMPTY_P1, EMPTY_P2), IDS),
    "game_spread_with_book_total": lambda: generate_market_odds_picks(
        _pred(), [_prop("Game Spread", "-2.5", 110, -130)], BOTH, IDS, {9: 22.5}),
    "unknown_stat_type": lambda: generate_market_odds_picks(_pred(), [_prop("Aces", "6.5")], BOTH, IDS),
    "p2_favorite_spread": lambda: generate_market_odds_picks(
        _pred(p1_win_prob=0.30, p2_win_prob=0.70), [_prop("Game Spread", "3.5", -110, -110)],
        _rolling(_stats(P1_ID, **{k: getattr(WEAK, k) for k in ("hold_pct", "break_pct", "win_rate")}),
                 _stats(P2_ID, **{k: getattr(STRONG, k) for k in ("hold_pct", "break_pct", "win_rate")})),
        IDS),
}

DERIVED_CASES: dict[str, Callable[[], list]] = {
    "no_win_prob": lambda: generate_derived_picks(_pred(p1_win_prob=None, p2_win_prob=None)),
    "bo3_heavy_favorite_dominant": lambda: generate_derived_picks(_pred(p1_win_prob=0.82, p2_win_prob=0.18), STRONG, WEAK),
    "bo3_favorite_no_stats": lambda: generate_derived_picks(_pred(p1_win_prob=0.74, p2_win_prob=0.26)),
    "bo3_close_match": lambda: generate_derived_picks(_pred(p1_win_prob=0.53, p2_win_prob=0.47), WEAK, STRONG),
    "bo3_p2_favorite": lambda: generate_derived_picks(_pred(p1_win_prob=0.31, p2_win_prob=0.69), WEAK, STRONG),
    "bo3_modest_dominance": lambda: generate_derived_picks(
        _pred(p1_win_prob=0.66, p2_win_prob=0.34), _stats(P1_ID, dominance_ratio=1.42), WEAK),
    "bo3_dominance_ratio_missing": lambda: generate_derived_picks(
        _pred(p1_win_prob=0.66, p2_win_prob=0.34), _stats(P1_ID, dominance_ratio=None), WEAK),
    "bo5_heavy_favorite_dominant": lambda: generate_derived_picks(
        _pred(p1_win_prob=0.84, p2_win_prob=0.16, best_of=5), STRONG, WEAK),
    "bo5_favorite": lambda: generate_derived_picks(_pred(p1_win_prob=0.72, p2_win_prob=0.28, best_of=5)),
    "bo5_close_match": lambda: generate_derived_picks(_pred(p1_win_prob=0.55, p2_win_prob=0.45, best_of=5), WEAK, STRONG),
    "bo5_p2_favorite": lambda: generate_derived_picks(_pred(p1_win_prob=0.35, p2_win_prob=0.65, best_of=5), WEAK, STRONG),
}


def _sh(line: str | None, p1_odds: int | None, p2_odds: int | None) -> dict:
    return {"set_handicap": {"line": line, "p1_odds": p1_odds, "p2_odds": p2_odds}}


SET_CASES: dict[str, Callable[[], list]] = {
    "no_win_prob": lambda: _generate_set_picks(_pred(p1_win_prob=None, p2_win_prob=None), _sh("1.5", -120, 100)),
    "market_p1_favorite": lambda: _generate_set_picks(_pred(p1_win_prob=0.80, p2_win_prob=0.20), _sh("-1.5", 110, -140)),
    "market_p2_favorite": lambda: _generate_set_picks(_pred(p1_win_prob=0.22, p2_win_prob=0.78), _sh("1.5", -110, 105)),
    "market_dog_value": lambda: _generate_set_picks(_pred(p1_win_prob=0.56, p2_win_prob=0.44), _sh("1.5", 160, -110)),
    "market_line_unspecified": lambda: _generate_set_picks(_pred(p1_win_prob=0.80, p2_win_prob=0.20), _sh(None, 110, -140)),
    "market_line_mismatch_uses_moneyline": lambda: _generate_set_picks(
        _pred(p1_win_prob=0.80, p2_win_prob=0.20), _sh("2.5", 110, -140)),
    "market_missing_odds_uses_moneyline": lambda: _generate_set_picks(
        _pred(p1_win_prob=0.80, p2_win_prob=0.20, p1_odds_american=-150, p2_odds_american=130), _sh("1.5", None, -140)),
    "moneyline_only_dog_set": lambda: _generate_set_picks(
        _pred(p1_win_prob=0.55, p2_win_prob=0.45, p1_odds_american=-250, p2_odds_american=210), {}),
    "moneyline_only_favorite_sweep": lambda: _generate_set_picks(
        _pred(p1_win_prob=0.88, p2_win_prob=0.12, p1_odds_american=-180, p2_odds_american=155), {}),
    "no_prices": lambda: _generate_set_picks(_pred(p1_odds_american=None, p2_odds_american=None), {}),
    "bo5_market": lambda: _generate_set_picks(
        _pred(p1_win_prob=0.86, p2_win_prob=0.14, best_of=5), _sh("2.5", 120, -150)),
    "bo5_moneyline_only": lambda: _generate_set_picks(
        _pred(p1_win_prob=0.60, p2_win_prob=0.40, best_of=5, p1_odds_american=-300, p2_odds_american=250), {}),
}


def _tg(line: str | None, over: int | None = -110, under: int | None = -110) -> dict:
    return {"total_games": {"line": line, "p1_odds": over, "p2_odds": under}}


TOTAL_CASES: dict[str, Callable[[], list]] = {
    "no_market": lambda: _generate_total_picks(_pred(), {}, STRONG, WEAK),
    "no_line": lambda: _generate_total_picks(_pred(), _tg(None), STRONG, WEAK),
    "zero_line": lambda: _generate_total_picks(_pred(), _tg("0"), STRONG, WEAK),
    "per_set_line": lambda: _generate_total_picks(_pred(), _tg("10.5"), STRONG, WEAK),
    "over_value": lambda: _generate_total_picks(_pred(), _tg("18.5", 120, -150), STRONG, WEAK),
    "under_value": lambda: _generate_total_picks(_pred(), _tg("27.5", -150, 120), STRONG, WEAK),
    "close_line": lambda: _generate_total_picks(_pred(p1_win_prob=0.52, p2_win_prob=0.48), _tg("22.5"), WEAK, STRONG),
    "one_projection": lambda: _generate_total_picks(_pred(), _tg("18.5", 120, -150), STRONG, None),
    "other_projection": lambda: _generate_total_picks(_pred(), _tg("27.5", -150, 120), None, WEAK),
    "no_projection": lambda: _generate_total_picks(_pred(), _tg("22.5"), None, None),
    "over_unpriced": lambda: _generate_total_picks(_pred(), _tg("18.5", None, -150), STRONG, WEAK),
    "over_overpriced": lambda: _generate_total_picks(_pred(), _tg("18.5", -900, 500), STRONG, WEAK),
    "under_overpriced": lambda: _generate_total_picks(_pred(), _tg("27.5", 500, -900), STRONG, WEAK),
    "no_win_prob": lambda: _generate_total_picks(
        _pred(p1_win_prob=None, p2_win_prob=None), _tg("18.5", 120, -150), STRONG, WEAK),
    "bo5": lambda: _generate_total_picks(_pred(best_of=5), _tg("30.5", -150, 120), STRONG, WEAK),
}

GENERATORS: dict[str, dict[str, Callable[[], list]]] = {
    "generate_market_odds_picks": MARKET_ODDS_CASES,
    "generate_derived_picks": DERIVED_CASES,
    "_generate_set_picks": SET_CASES,
    "_generate_total_picks": TOTAL_CASES,
}


def run_case(generator: str, case: str) -> list[dict]:
    # A JSON round trip turns tuples into lists, the same as the stored copy.
    return json.loads(json.dumps([asdict(pick) for pick in GENERATORS[generator][case]()], default=str))


def _golden() -> dict[str, dict[str, list[dict]]]:
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("generator", "case"),
    [(generator, case) for generator, cases in GENERATORS.items() for case in cases],
)
def test_generator_output_is_unchanged(generator: str, case: str) -> None:
    assert run_case(generator, case) == _golden()[generator][case]


def test_every_golden_case_is_run() -> None:
    golden = _golden()
    assert {g: set(c) for g, c in golden.items()} == {g: set(c) for g, c in GENERATORS.items()}


def test_the_cases_produce_picks() -> None:
    # Guards against a fixture of empty lists, which would pin nothing.
    golden = _golden()
    for generator, cases in golden.items():
        assert sum(len(picks) for picks in cases.values()) >= 5, generator

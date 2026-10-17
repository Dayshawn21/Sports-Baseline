from datetime import datetime

from app.core.tennis_format import (
    infer_best_of,
    infer_best_of_or_none,
    is_grand_slam,
    is_qualifying_round,
)
from app.repositories.players import PlayerRollingStats
from app.services.tennis.best_picks import generate_derived_picks
from app.services.tennis.predictor import PredictionOutput


def _prediction(
    best_of: int,
    tournament: str = "French Open, Paris, France Men Singles",
    tour: str = "ATP",
) -> PredictionOutput:
    return PredictionOutput(
        match_id=1,
        start_utc=datetime(2026, 5, 24, 12, 0, 0),
        p1_name="Carlos Alcaraz",
        p2_name="Jannik Sinner",
        tour=tour,
        surface="Clay",
        tournament=tournament,
        round="R128",
        best_of=best_of,
        p1_win_prob=0.66,
        p2_win_prob=0.34,
        p1_elo_prob=0.60,
        p1_ml_prob=0.61,
        p1_market_prob=0.58,
        ensemble_weights={},
        quality_flags=[],
        p1_odds_american=-150,
        p2_odds_american=130,
        h2h_p1_wins=0,
        h2h_p2_wins=0,
    )


def test_atp_french_open_main_draw_infers_best_of_five():
    assert infer_best_of("ATP", "French Open, Paris, France Men Singles", "R128") == 5
    assert infer_best_of("ATP", "Roland Garros", "Q1") == 3
    assert infer_best_of("WTA", "French Open, Paris, France Women Singles", "R128") == 3


def test_main_draw_rounds_starting_with_q_are_not_qualifying():
    assert not is_qualifying_round("Quarterfinal")
    assert not is_qualifying_round("Quarter-final")
    assert infer_best_of("ATP", "US Open", "Quarterfinal") == 5


def test_qualifying_round_forms_are_detected():
    for round_name in ("Q", "Q1", "Q3", "Qual", "Qualifying", "Qualifying Round 2"):
        assert is_qualifying_round(round_name), round_name
        assert infer_best_of("ATP", "US Open", round_name) == 3


def test_grand_slam_keywords_match_on_word_boundaries():
    assert is_grand_slam("US Open")
    assert not is_grand_slam("Columbus Open")
    assert infer_best_of("ATP", "Columbus Open", "Quarterfinal") == 3


def test_infer_best_of_or_none_withholds_a_value_when_undecidable():
    # Nothing to go on — must not persist a fallback 3 over a stored 5.
    assert infer_best_of_or_none("ATP", None, "R32") is None
    assert infer_best_of_or_none(None, "US Open", "R32") is None
    # Inside an ATP slam the round decides main draw vs qualifying.
    assert infer_best_of_or_none("ATP", "US Open", None) is None
    # Decidable cases still return a value.
    assert infer_best_of_or_none("ATP", "US Open", "Quarterfinal") == 5
    assert infer_best_of_or_none("ATP", "US Open", "Q1") == 3
    assert infer_best_of_or_none("WTA", "US Open", "R32") == 3
    assert infer_best_of_or_none("ATP", "Madrid Open", "R32") == 3
    # An explicitly known format wins regardless of missing context.
    assert infer_best_of_or_none(None, None, None, explicit_best_of=5) == 5


def test_best_of_five_emits_format_specific_derived_set_picks():
    picks = generate_derived_picks(_prediction(best_of=5))

    labels = {p.label for p in picks}
    pick_names = {p.pick for p in picks}

    assert "Set Score 3-0" in labels
    assert "Win a Set" in labels
    assert "Total Sets" in labels
    assert "Alcaraz wins 3-0" in pick_names
    assert "Sinner wins a set" in pick_names
    assert "Match goes 4+ sets" in pick_names
    assert "Set Score 2-0" not in labels
    assert "Match goes 3 sets" not in pick_names


def test_best_of_three_still_allows_derived_set_picks():
    picks = generate_derived_picks(_prediction(best_of=3, tournament="Madrid Open"))

    assert any(p.label == "Set Score 2-0" for p in picks)


def test_serve_dominance_survives_best_of_five():
    """The best-of-5 gate covers set-score picks only; Serve Dominance is format-agnostic."""
    dominant = PlayerRollingStats(
        player_id=1,
        surface="Clay",
        stat_period="last_52w",
        split_type="overall",
        split_value="all",
        win_rate=0.72,
        svc_pts_won=0.70,
        ret_pts_won=0.42,
        aces_per_game=0.55,
        df_per_game=0.07,
        hold_pct=0.90,
        break_pct=0.30,
        matches_count=30,
        first_in_pct=0.64,
        first_won_pct=0.78,
        second_won_pct=0.56,
        dominance_ratio=1.6,
    )

    picks = generate_derived_picks(_prediction(best_of=5), p1_stats=dominant)

    assert any(p.label == "Serve Dominance" for p in picks)
    assert not any(p.label == "Set Score 2-0" for p in picks)
    assert not any(p.pick == "Match goes 3 sets" for p in picks)


def test_wta_french_open_still_allows_best_of_three_derived_set_picks():
    picks = generate_derived_picks(
        _prediction(
            best_of=infer_best_of("WTA", "French Open, Paris, France Women Singles", "R128"),
            tournament="French Open, Paris, France Women Singles",
            tour="WTA",
        )
    )

    assert any(p.label == "Set Score 2-0" for p in picks)

from types import SimpleNamespace

import pytest

from app.services.tennis.feature_builder import build_features
from app.services.tennis.predictor import _elo_probability


def _match(surface: str | None = "Hard") -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        tour="ATP",
        surface=surface,
        tournament="Test Open",
        round="R32",
        best_of=3,
        match_date=None,
        p1_id=1,
        p2_id=2,
        p1_rank=10,
        p2_rank=20,
    )


def _elo(**overrides: float | None) -> SimpleNamespace:
    values = {
        "elo": 1500.0,
        "elo_hard": None,
        "elo_clay": None,
        "elo_grass": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _features(p1_elo: SimpleNamespace, p2_elo: SimpleNamespace) -> dict:
    feat, _ = build_features(
        match=_match(),
        p1=None,
        p2=None,
        p1_elo=p1_elo,
        p2_elo=p2_elo,
        p1_stats=None,
        p2_stats=None,
        p1_surf_stats=None,
        p2_surf_stats=None,
        h2h_p1_wins=0,
        h2h_p2_wins=0,
        h2h_surf_p1_wins=0,
        h2h_surf_p2_wins=0,
    )
    return feat


def test_build_features_marks_real_surface_elo() -> None:
    feat = _features(
        _elo(elo=1600.0, elo_hard=1500.0),
        _elo(elo=1500.0, elo_hard=1500.0),
    )

    assert feat["has_surface_elo"] == 1.0
    assert feat["d_surface_elo"] == 0.0


def test_build_features_does_not_mark_default_surface_elo() -> None:
    feat = _features(_elo(elo=1600.0), _elo(elo=1500.0))

    assert "has_surface_elo" not in feat
    assert "d_surface_elo" not in feat


def test_missing_surface_elo_falls_back_to_overall_elo() -> None:
    result = _elo_probability({"d_elo": 100.0, "d_surface_elo": 0.0})

    assert result == pytest.approx(1.0 / (1.0 + 10 ** (-100.0 / 400.0)))


def test_real_equal_surface_elo_stays_neutral() -> None:
    result = _elo_probability({
        "d_elo": 100.0,
        "d_surface_elo": 0.0,
        "has_surface_elo": 1.0,
    })

    assert result == pytest.approx(0.5)

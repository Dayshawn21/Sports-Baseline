import pytest

from app.core.tennis_surface_overrides import apply_surface_override


@pytest.mark.parametrize("tournament_id", ["14767", "14763"])
def test_lyon_october_draws_use_indoor_hard(tournament_id: str) -> None:
    assert apply_surface_override(tournament_id, "Clay", None) == ("Hard", True)


@pytest.mark.parametrize("tournament_id", ["other-lyon-edition", None])
@pytest.mark.parametrize("surface,indoor", [("Clay", False), ("Grass", True), (None, None)])
def test_unlisted_tournaments_preserve_inputs(
    tournament_id: str | None, surface: str | None, indoor: bool | None,
) -> None:
    assert apply_surface_override(tournament_id, surface, indoor) == (surface, indoor)

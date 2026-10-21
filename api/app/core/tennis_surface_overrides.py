from __future__ import annotations


SURFACE_OVERRIDES: dict[str, tuple[str, bool]] = {
    "14767": ("Hard", True),  # Lyon October 2026 main draw is indoor hard, misfiled as clay.
    "14763": ("Hard", True),  # Lyon October 2026 qualifying is indoor hard, misfiled as clay.
}


def apply_surface_override(
    tournament_id: str | None,
    surface: str | None,
    indoor: bool | None,
) -> tuple[str | None, bool | None]:
    return SURFACE_OVERRIDES.get(tournament_id, (surface, indoor))

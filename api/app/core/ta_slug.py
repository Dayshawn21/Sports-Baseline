"""TennisAbstract player-page slugs, shared by the stats ingest and the admin queue."""
from __future__ import annotations

# Sofascore name to TennisAbstract slug overrides (add new mismatches here)
TA_SLUG_OVERRIDES: dict[str, str] = {
    "Catherine McNally": "CatyMcnally",
    "Guiomar Maristany": "GuiomarMaristanyZuletaDeReales",
    # Hyphenated names: ta_slug() only strips spaces, not hyphens
    "Felix Auger-Aliassime": "FelixAugerAliassime",
    "Elena-Gabriela Ruse": "ElenaGabrielaRuse",
    # Sofascore first-name abbreviations / alternate spellings
    "Alex De Minaur": "AlexDeMinaur",
    "Jo-Wilfried Tsonga": "JoWilfriedTsonga",
}


def ta_slug(name: str) -> str:
    """'Aryna Sabalenka' -> 'ArynaSabalenka', with known override support."""
    if name in TA_SLUG_OVERRIDES:
        return TA_SLUG_OVERRIDES[name]
    return name.replace(" ", "")

"""Helpers for tennis match format inference."""

from __future__ import annotations

import re
from typing import Optional


GRAND_SLAM_KEYWORDS = (
    "australian open",
    "french open",
    "roland garros",
    "wimbledon",
    "us open",
    "u.s. open",
)

# Keywords must match on word boundaries so "Columbus Open" is not read as "us open".
_GRAND_SLAM_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(k) for k in GRAND_SLAM_KEYWORDS) + r")\b"
)

# Qualifying rounds are word-form or short codes: "Q", "Q1".."Q3", "QR1", "Qual",
# "Qualifying", "Qualification Round 2", "Qualification Final". A bare "Q" prefix would
# also swallow "Quarterfinal", which is main draw, hence the explicit alternatives.
#
# The trailing group used to be digits only, so "Qualification Final" fell through and an
# ATP slam qualifying final was inferred best-of-5. Qualifying is best-of-3 at every slam.
_QUALIFYING_RE = re.compile(
    r"^(?:Q\d*|QR\s*\d+|QUAL(?:IFYING|IFICATION)?(?:\s*ROUND)?(?:\s*(?:\d+|FINAL))?)$"
)

# Providers also flag qualifying in the tournament name itself, e.g.
# "US Open, New York, USA, Qualifying". That is the more reliable signal, because the
# round can arrive empty or in a vocabulary we have not seen.
_QUALIFYING_EVENT_RE = re.compile(r"qualif", re.IGNORECASE)


def is_grand_slam(tournament: Optional[str]) -> bool:
    return bool(_GRAND_SLAM_RE.search((tournament or "").lower()))


def is_qualifying_round(round_name: Optional[str]) -> bool:
    normalized = " ".join((round_name or "").upper().split())
    return bool(_QUALIFYING_RE.match(normalized))


def is_qualifying_event(tournament: Optional[str]) -> bool:
    """True when the tournament name itself marks the event as qualifying."""
    return bool(_QUALIFYING_EVENT_RE.search(tournament or ""))


def display_tour(
    match_tour: Optional[str],
    p1_tour: Optional[str] = None,
    p2_tour: Optional[str] = None,
) -> str:
    """
    The label to show for a match's tour. Display only — never write this to
    `matches.tour`, which stays on the provider's three-value vocabulary that
    parlay pairing, tour ordering and the ELO lookup all key on.

    livetennisapi files WTA 125 (and women's ITF) under `challenger` alongside
    the men's Challenger tour, so a women's 125 draw reaches us labelled
    CHALLENGER. The players carry the honest signal, so read gender off them.

    Player tour can itself be CHALLENGER (that is how a player first ingested
    from a Challenger draw is stored), so this asks "any WTA and no ATP"
    rather than "both WTA" — a mixed WTA/CHALLENGER pair is still a 125 draw.
    Unknown on both sides falls back to CHALLENGER rather than guessing.
    """
    tour_key = (match_tour or "").strip().upper()
    if tour_key != "CHALLENGER":
        return tour_key or "TENNIS"

    tours = {(t or "").strip().upper() for t in (p1_tour, p2_tour)}
    if "WTA" in tours and "ATP" not in tours:
        return "WTA 125"
    return "CHALLENGER"


def infer_best_of(
    tour: Optional[str],
    tournament: Optional[str],
    round_name: Optional[str],
    explicit_best_of: Optional[int] = None,
) -> int:
    """Infer match format.

    ATP Grand Slam main-draw singles are best-of-5. WTA, Challengers, and
    qualifying rounds stay best-of-3.
    """
    tour_key = (tour or "").upper()

    is_qualifying = is_qualifying_round(round_name) or is_qualifying_event(tournament)
    if tour_key == "ATP" and is_grand_slam(tournament) and not is_qualifying:
        return 5

    if explicit_best_of in (3, 5):
        return int(explicit_best_of)

    return 3


def infer_best_of_or_none(
    tour: Optional[str],
    tournament: Optional[str],
    round_name: Optional[str],
    explicit_best_of: Optional[int] = None,
) -> Optional[int]:
    """Like `infer_best_of`, but returns None when the inputs cannot decide the format.

    `infer_best_of` falls back to 3, which is the right default for a projection but
    the wrong thing to persist: on re-ingest a fallback 3 would overwrite a correct
    stored 5. Ingest paths should use this and let the DB keep the existing value
    (see the COALESCE in `upsert_match`).
    """
    if explicit_best_of in (3, 5):
        return int(explicit_best_of)

    if not (tour or "").strip() or not (tournament or "").strip():
        return None

    # Inside an ATP slam the round decides main draw (5) vs qualifying (3).
    if (tour or "").upper() == "ATP" and is_grand_slam(tournament) and not (round_name or "").strip():
        return None

    return infer_best_of(tour, tournament, round_name)

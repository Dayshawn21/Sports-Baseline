"""
WTA 125 draws reach us labelled CHALLENGER.

livetennisapi files women's 125/ITF events under `tour: challenger` alongside
the men's Challenger tour, so the match label alone cannot tell the two apart.
The embedded players can — verified against the recorded payload below, where
'Philadelphia (Usa)' carries tour=challenger with two WTA players.
"""
import json
from pathlib import Path

import pytest

from app.core.tennis_format import display_tour
from app.ingest.livetennis import _player_tour, normalize_match

FIXTURE = Path(__file__).parent / "fixtures" / "livetennis_matches.json"


# =============================================================================
# display_tour — the label itself
# =============================================================================

@pytest.mark.parametrize("match_tour,p1,p2,expected", [
    # Unambiguous tours pass straight through, players irrelevant.
    ("ATP", "ATP", "ATP", "ATP"),
    ("WTA", "WTA", "WTA", "WTA"),
    ("ATP", None, None, "ATP"),
    ("atp", "atp", "atp", "ATP"),
    # The reported case: women filed under challenger.
    ("CHALLENGER", "WTA", "WTA", "WTA 125"),
    # Player tour is itself CHALLENGER for anyone first seen in a Challenger
    # draw, so one WTA side is enough — this is the live Philadelphia shape.
    ("CHALLENGER", "WTA", "CHALLENGER", "WTA 125"),
    ("CHALLENGER", "CHALLENGER", "WTA", "WTA 125"),
    ("CHALLENGER", "WTA", None, "WTA 125"),
    # Men's Challengers keep their label.
    ("CHALLENGER", "ATP", "ATP", "CHALLENGER"),
    ("CHALLENGER", "ATP", "CHALLENGER", "CHALLENGER"),
    ("CHALLENGER", "CHALLENGER", "CHALLENGER", "CHALLENGER"),
    # Unknown on both sides must not guess.
    ("CHALLENGER", None, None, "CHALLENGER"),
])
def test_display_tour(match_tour, p1, p2, expected):
    assert display_tour(match_tour, p1, p2) == expected


def test_a_contradictory_pair_is_not_called_wta_125():
    """An ATP side outvotes a WTA side — mixed means the data is wrong, not 125."""
    assert display_tour("CHALLENGER", "ATP", "WTA") == "CHALLENGER"


def test_missing_tour_does_not_render_empty():
    assert display_tour(None) == "TENNIS"
    assert display_tour("") == "TENNIS"


# =============================================================================
# _player_tour — reading gender off the embedded Player
# =============================================================================

@pytest.mark.parametrize("raw,expected", [
    ("atp", "ATP"),
    ("wta", "WTA"),
    # Player.tour is NOT the filter vocabulary — these are its own forms.
    ("challenger_men", "ATP"),
    ("challenger_women", "WTA"),
    ("ATP", "ATP"),
    ("itf_men", "ATP"),
    ("", None),
    (None, None),
    ("something_else", None),
])
def test_player_tour(raw, expected):
    assert _player_tour({"tour": raw}) == expected


def test_player_tour_tolerates_a_missing_player():
    assert _player_tour(None) is None
    assert _player_tour({}) is None


# =============================================================================
# End to end on the recorded payload
# =============================================================================

def _records():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))["data"]
    return [r for r in (normalize_match(m) for m in data) if r]


def test_the_philadelphia_womens_125_is_labelled_wta_125():
    recs = [r for r in _records() if r["tournament"] == "Philadelphia (Usa)"]
    assert recs, "fixture should contain the women's 125 draw"
    for rec in recs:
        # The match row itself stays CHALLENGER — parlay pairing keys on it.
        assert rec["tour"] == "CHALLENGER"
        assert rec["p1_tour"] == "WTA"
        assert display_tour(rec["tour"], rec["p1_tour"], rec["p2_tour"]) == "WTA 125"


def test_a_mens_challenger_in_the_same_payload_is_untouched():
    recs = [r for r in _records() if r["tournament"].startswith("Kingston 2")]
    assert recs
    for rec in recs:
        assert rec["tour"] == "CHALLENGER"
        assert display_tour(rec["tour"], rec["p1_tour"], rec["p2_tour"]) == "CHALLENGER"


def test_player_tour_falls_back_to_the_match_tour_when_absent():
    """p2.tour is null on some rows; the fallback must not write None."""
    for rec in _records():
        assert rec["p1_tour"] and rec["p2_tour"]

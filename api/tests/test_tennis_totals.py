import copy
import datetime as dt
import json
from pathlib import Path

from app.core.tennis_totals import TennisTotal, book_totals, match_stored, preferred_total

# Trimmed from GET /v4/sports/tennis_atp_swiss_indoors/odds?regions=us,eu&markets=totals, 2026-10-28.
EVENTS = json.loads((Path(__file__).parent / "fixtures" / "the_odds_api_tennis_totals.json").read_text())
FILS, SHAPOVALOV, KYM = EVENTS


def _match(match_id, p1, p2, start="2026-10-29T13:00:00+00:00"):
    return {"match_id": match_id, "p1_name": p1, "p2_name": p2, "start_utc": dt.datetime.fromisoformat(start)}


def test_pinnacle_wins_when_it_prices_the_match():
    assert preferred_total(FILS) == TennisTotal("pinnacle", 22.5, -111, -103)


def test_falls_back_to_the_next_preferred_book():
    assert preferred_total(SHAPOVALOV) == TennisTotal("marathonbet", 22.5, -109, -122)


def test_us_books_are_parsed_but_never_preferred():
    assert book_totals(FILS)["betus"] == TennisTotal("betus", 23.0, -110, -120)
    event = copy.deepcopy(FILS)
    event["bookmakers"] = [b for b in event["bookmakers"] if b["key"] != "pinnacle"]
    assert preferred_total(event) is None


def test_event_without_totals_gives_nothing():
    assert book_totals(KYM) == {}
    assert preferred_total(KYM) is None


def test_a_ladder_resolves_to_the_rung_closest_to_even():
    event = copy.deepcopy(FILS)
    pinnacle = next(b for b in event["bookmakers"] if b["key"] == "pinnacle")
    pinnacle["markets"][0]["outcomes"] += [
        {"name": "Over", "price": 3.1, "point": 25.5},
        {"name": "Under", "price": 1.35, "point": 25.5},
        {"name": "Over", "price": 1.5, "point": 20.5},
    ]
    assert preferred_total(event) == TennisTotal("pinnacle", 22.5, -111, -103)


def test_matches_one_stored_match_in_either_order():
    matches = [_match(1, "Arthur Fils", "Alex Michelsen"), _match(2, "Taylor Fritz", "Denis Shapovalov")]
    assert match_stored(FILS, matches) == 1


def test_a_start_outside_the_window_does_not_match():
    assert match_stored(FILS, [_match(1, "Alex Michelsen", "Arthur Fils", "2026-10-30T13:00:00+00:00")]) is None


def test_an_ambiguous_pairing_is_refused():
    siblings = copy.deepcopy(FILS)
    siblings["home_team"], siblings["away_team"] = "Alex Fils", "Arthur Fils"
    assert match_stored(siblings, [_match(1, "Alex Fils", "Arthur Fils")]) is None
    twice = [_match(1, "Alex Michelsen", "Arthur Fils"), _match(2, "Alex Michelsen", "Arthur Fils")]
    assert match_stored(FILS, twice) is None

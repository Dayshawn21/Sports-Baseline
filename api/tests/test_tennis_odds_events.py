"""An Odds-API.io event is only this match when it is tour singles, starts near the
match, and names both players by whole surname, oriented from the pairing itself."""
from datetime import datetime, timedelta, timezone

import pytest

from app.core.tennis_odds_events import (
    event_start,
    match_event,
    names_player,
    near_start_events,
    odds_event_tour,
    tour_level_circuit,
)

START = datetime(2026, 9, 25, 14, 0, tzinfo=timezone.utc)


class TestLeagueFilter:
    # League names as Odds-API.io returned them on 2026-09-25.
    @pytest.mark.parametrize(("league", "tour"), [
        ("ATP - Chengdu, China", "ATP"),
        ("WTA - Seoul, Korea Republic", "WTA"),
        ("WTA 125K - Jingshan, China, Qualifying", "WTA"),
        ("Challenger - San Diego 2, USA", "CHALLENGER"),
    ])
    def test_tour_singles_leagues_are_kept(self, league, tour):
        assert odds_event_tour(league) == tour

    @pytest.mark.parametrize("league", [
        "ATP - Chengdu, China, Doubles",
        "Challenger - Buenos Aires 2, Argentina, Doubles",
        "Tennis - ITF Men Columbia - R16",
        "UTR Men - UTR PTT Saitama Men 09, 1-4 Playoff",
        "Billie Jean King Cup - Finals",
        "Exhibition - Laver Cup, Singles Matches",
        "",
    ])
    def test_doubles_itf_utr_team_and_exhibition_leagues_are_rejected(self, league):
        assert odds_event_tour(league) is None


class TestMatchEvent:
    def test_a_straight_pairing_matches_with_home_as_p1(self):
        assert match_event("Jannik Sinner", "Carlos Alcaraz", "Jannik Sinner", "Carlos Alcaraz") is True

    def test_a_reversed_pairing_matches_with_home_as_p2(self):
        assert match_event("Jannik Sinner", "Carlos Alcaraz", "Carlos Alcaraz", "Jannik Sinner") is False

    def test_a_surname_inside_another_does_not_match(self):
        assert match_event("Na Li", "Ana Konjuh", "Yu-Hsiou Lin", "Ana Konjuh") is None

    def test_accents_and_hyphens_do_not_block_a_match(self):
        assert match_event("Felix Auger-Aliassime", "Tomas Machac", "Felix Auger Aliassime", "Tomáš Macháč") is True

    def test_surname_first_names_and_non_breaking_spaces_still_match(self):
        assert match_event("Tristan Boyer", "Timo Legout", "Boyer, Tristan", "Legout, Timo") is True

    def test_players_sharing_a_surname_are_refused_rather_than_guessed(self):
        assert match_event("Stefanos Tsitsipas", "Petros Tsitsipas", "Petros Tsitsipas", "Stefanos Tsitsipas") is None

    def test_an_event_twelve_hours_away_still_matches(self):
        assert match_event("A Sinner", "B Alcaraz", "A Sinner", "B Alcaraz", START, START + timedelta(hours=12)) is True

    def test_an_event_more_than_twelve_hours_away_is_rejected(self):
        later = START + timedelta(hours=12, minutes=1)
        assert match_event("A Sinner", "B Alcaraz", "A Sinner", "B Alcaraz", START, later) is None

    def test_an_unknown_start_skips_the_time_check(self):
        assert match_event("A Sinner", "B Alcaraz", "A Sinner", "B Alcaraz", START, None) is True


class TestEventStart:
    def test_a_z_suffix_parses_as_utc(self):
        assert event_start({"date": "2026-09-25T14:00:00Z"}) == START

    def test_a_naive_time_is_read_as_utc(self):
        assert event_start({"start": "2026-09-25T14:00:00"}) == START

    def test_missing_or_garbage_is_none(self):
        assert event_start({}) is None
        assert event_start({"date": "soon"}) is None


class TestNameSuffixes:
    def test_a_suffix_on_either_side_is_ignored(self):
        assert names_player("Martin Damm Jr", "Martin Damm") is True
        assert names_player("Martin Damm", "Martin Damm Jr") is True
        assert names_player("Martin Damm Jr.", "Damm, Martin") is True
        assert names_player("John Smith III", "J. Smith") is True

    def test_a_suffix_is_never_a_surname(self):
        assert names_player("Martin Damm Jr", "Jr Smith") is False

    def test_names_without_a_suffix_are_unchanged(self):
        assert names_player("Juan Martin del Potro", "Juan Martin Del Potro") is True
        assert names_player("Li", "Lin") is False
        assert names_player("Zhizhen Zhang", "Z. Zhang") is True

    def test_a_suffix_alone_is_still_a_name(self):
        assert names_player("Jr", "Jr") is True


class TestTourLevelCircuit:
    @pytest.mark.parametrize(("league", "tour"), [
        ("ATP - Paris, France", "ATP"),
        ("WTA - Riyadh", "WTA"),
    ])
    def test_main_tour_singles_map_to_their_tour(self, league, tour):
        assert tour_level_circuit(league) == tour

    @pytest.mark.parametrize("league", [
        "ATP - Paris, Doubles",
        "WTA 125K - Adana",
        "Challenger - Bari",
        "Tennis - ITF Men Columbia - R16",
        "",
    ])
    def test_doubles_wta_125_challenger_and_itf_are_rejected(self, league):
        assert tour_level_circuit(league) is None


def _event(event_id, league, start):
    return {"id": event_id, "league": {"name": league}, "date": start}


class TestNearStartEvents:
    def test_only_main_tour_singles_inside_the_window_are_kept(self):
        events = [
            _event(1, "ATP - Paris, France", "2026-09-25T15:00:00Z"),
            _event(2, "ATP - Paris, France", "2026-09-25T13:59:00Z"),
            _event(3, "WTA - Riyadh", "2026-09-25T20:01:00Z"),
            _event(4, "WTA - Riyadh", "soon"),
            _event(5, "Challenger - Bari", "2026-09-25T15:00:00Z"),
            {"league": {"name": "ATP - Paris, France"}, "date": "2026-09-25T15:00:00Z"},
            _event(6, "WTA - Riyadh", "2026-09-25T20:00:00Z"),
        ]
        assert [e["id"] for e in near_start_events(events, START, 6, 10)] == [1, 6]

    def test_the_result_is_sorted_soonest_first_and_capped(self):
        events = [_event(i, "ATP - Paris, France", f"2026-09-25T{19 - i}:00:00Z") for i in range(5)]
        assert [e["id"] for e in near_start_events(events, START, 6, 3)] == [4, 3, 2]

    def test_an_empty_listing_gives_an_empty_list(self):
        assert near_start_events([], START, 6, 10) == []

import random
from dataclasses import replace
from datetime import date

import pytest

from app.core.tennis_elo import TennisEloMatch, TennisEloReplay
from app.ml.elo_history import EloIndex

A, B, C = ("ATP", "A"), ("ATP", "B"), ("ATP", "C")
BEFORE = date(2021, 1, 5)


@pytest.fixture
def matches() -> list[TennisEloMatch]:
    first = TennisEloMatch(
        namespace="ATP", family="ATP", event_id="2021-synthetic", match_number=1,
        provider_date=date(2021, 1, 1), round="R32", level="250", surface="hard",
        winner_id="A", winner_name="Player A", loser_id="B", loser_name="Player B",
        tournament="Synthetic", score="6-4 6-3", best_of=3,
    )
    return [
        first,
        replace(first, match_number=2, provider_date=date(2021, 1, 2), surface="clay",
                winner_id="C", winner_name="Player C", loser_id="A", loser_name="Player A"),
        replace(first, match_number=3, provider_date=date(2021, 1, 3), surface="grass",
                winner_id="B", winner_name="Player B", loser_id="C", loser_name="Player C"),
        replace(first, match_number=4, provider_date=date(2021, 1, 4), surface=None),
    ]


def test_hand_worked_rating_updates_and_surface_specific_k_counts(matches):
    replay = TennisEloReplay(matches)
    k0, k1 = 250 / 5**0.4, 250 / 6**0.4
    a1, b1 = 1500 + k0 / 2, 1500 - k0 / 2
    c_expected = 1 / (1 + 10 ** ((a1 - 1500) / 400))
    a2, c2 = a1 - k1 * (1 - c_expected), 1500 + k0 * (1 - c_expected)
    b_expected = 1 / (1 + 10 ** ((c2 - b1) / 400))
    b3 = b1 + k1 * (1 - b_expected)
    c3 = c2 - k1 * (1 - b_expected)
    a, b, c = (replay.rating(key, date(2021, 1, 4)) for key in (A, B, C))
    assert a is not None and b is not None and c is not None
    assert (a.overall, b.overall, c.overall) == pytest.approx((a2, b3, c3), abs=1e-9)
    assert (a.hard, b.hard) == pytest.approx((a1, b1), abs=1e-9)
    assert (a.clay, c.clay) == pytest.approx((1500 - k0 / 2, 1500 + k0 / 2), abs=1e-9)
    assert (b.grass, c.grass) == pytest.approx((1500 + k0 / 2, 1500 - k0 / 2), abs=1e-9)


def test_replay_matches_the_existing_index_without_changing_its_behavior(matches):
    reference = EloIndex([
        (date(2021, 1, 1), 1, 2, 1, "hard"),
        (date(2021, 1, 2), 1, 3, 3, "clay"),
        (date(2021, 1, 3), 2, 3, 2, "grass"),
        (date(2021, 1, 4), 1, 2, 1, None),
    ])
    replay = TennisEloReplay(matches)
    for key, player_id in [(A, 1), (B, 2), (C, 3)]:
        rating = replay.rating(key, BEFORE)
        assert rating is not None
        assert rating.overall == pytest.approx(reference.rating(player_id, BEFORE), abs=1e-9)
        for surface in ("hard", "clay", "grass"):
            assert getattr(rating, surface) == reference.surface_rating(player_id, surface, BEFORE)


def test_first_appearance_and_unseen_players_have_no_observed_rating(matches):
    replay = TennisEloReplay(matches)
    assert replay.rating(A, date(2021, 1, 1)) is None
    assert replay.rating(C, date(2021, 1, 2)) is None
    assert replay.rating(("ATP", "UNKNOWN"), BEFORE) is None
    a = replay.rating(A, date(2021, 1, 2))
    assert a is not None and a.hard is not None and a.clay is None and a.grass is None
    assert (a.overall_matches, a.hard_matches, a.clay_matches, a.grass_matches) == (1, 1, 0, 0)


@pytest.mark.parametrize("surface", [None, "carpet"])
def test_unknown_surface_updates_overall_and_counts_only(matches, surface):
    matches[-1] = replace(matches[-1], surface=surface)
    replay = TennisEloReplay(matches)
    prior, after = replay.rating(A, date(2021, 1, 4)), replay.rating(A, BEFORE)
    assert prior is not None and after is not None
    assert after.overall > prior.overall
    assert (after.hard, after.clay, after.grass) == (prior.hard, prior.clay, prior.grass)
    assert (after.overall_matches, after.hard_matches, after.clay_matches, after.grass_matches) == (3, 1, 1, 0)


def test_all_same_date_results_and_counts_are_excluded_at_the_cutoff(matches):
    day = date(2021, 1, 1)
    replay = TennisEloReplay([replace(m, provider_date=day) for m in matches])
    assert replay.rating(A, day) is None
    assert replay.rating(B, day) is None
    after = replay.rating(A, date(2021, 1, 2))
    assert after is not None and after.overall_matches == 3


def test_later_results_and_new_provider_ids_do_not_change_an_earlier_snapshot(matches):
    future = replace(matches[0], provider_date=date(2030, 1, 1), event_id="future",
                     winner_id="000", winner_name="New Player")
    early, full = TennisEloReplay(matches[:2]), TennisEloReplay([future, *matches])
    for player in (A, B, C):
        assert early.rating(player, date(2021, 1, 3)) == full.rating(player, date(2021, 1, 3))


def test_same_day_order_is_deterministic_even_when_updates_are_order_sensitive(matches):
    same_day = [replace(m, provider_date=date(2021, 1, 1)) for m in matches]
    first = TennisEloReplay(same_day)
    expected = [first.rating(p, BEFORE) for p in first.players]
    rng = random.Random(41)
    for _ in range(10):
        rng.shuffle(same_day)
        replay = TennisEloReplay(iter(same_day))
        assert replay.players == first.players
        assert [replay.rating(p, BEFORE) for p in replay.players] == expected


def test_duplicate_rows_do_not_count_or_update_twice(matches):
    single, repeated = TennisEloReplay(matches), TennisEloReplay(matches * 2)
    assert single.matches_count == repeated.matches_count == 4
    assert [single.rating(p, BEFORE) for p in single.players] == [repeated.rating(p, BEFORE) for p in repeated.players]
    with pytest.raises(ValueError, match="Conflicting TennisMyLife match"):
        TennisEloReplay([*matches, replace(matches[0], winner_id="C")])


def test_atp_families_share_a_network_but_wta_ids_stay_separate(matches):
    challenger = replace(matches[0], family="CHALLENGER", level="C", event_id="challenger")
    wta = replace(matches[0], namespace="WTA", family="WTA", winner_id="B", loser_id="A")
    replay = TennisEloReplay([matches[0], challenger, wta])
    atp_a, wta_a = replay.rating(A, BEFORE), replay.rating(("WTA", "A"), BEFORE)
    assert atp_a is not None and wta_a is not None
    assert atp_a.overall_matches == 2 and atp_a.overall > 1500
    assert wta_a.overall_matches == 1 and wta_a.overall < 1500


@pytest.mark.parametrize("surface", ["hard", " Hard "])
def test_probability_prefers_surface_only_when_both_ratings_exist(matches, surface):
    replay = TennisEloReplay(matches)
    a, b = replay.rating(A, BEFORE), replay.rating(B, BEFORE)
    assert a is not None and b is not None and a.hard is not None and b.hard is not None
    expected = 1 / (1 + 10 ** ((b.hard - a.hard) / 400))
    overall = 1 / (1 + 10 ** ((b.overall - a.overall) / 400))
    probability = replay.probability(A, B, surface, BEFORE)
    assert probability == pytest.approx(expected, abs=1e-9)
    assert probability != pytest.approx(overall, abs=1e-6)
    assert replay.probability(B, A, surface, BEFORE) == pytest.approx(1 - probability, abs=1e-9)


@pytest.mark.parametrize("surface", [None, "carpet", "clay"])
def test_missing_surface_on_either_player_uses_both_overall_ratings(matches, surface):
    replay = TennisEloReplay(matches)
    a, b = replay.rating(A, BEFORE), replay.rating(B, BEFORE)
    assert a is not None and b is not None
    expected = 1 / (1 + 10 ** ((b.overall - a.overall) / 400))
    assert replay.probability(A, B, surface, BEFORE) == pytest.approx(expected, abs=1e-9)


def test_probability_stays_missing_until_both_players_have_history(matches):
    replay = TennisEloReplay(matches)
    assert replay.probability(A, C, "hard", date(2021, 1, 2)) is None
    assert replay.probability(A, ("ATP", "UNKNOWN"), "hard", BEFORE) is None
    with pytest.raises(ValueError, match="distinct players"):
        replay.probability(A, A, None, BEFORE)


def test_empty_replay_and_audit_note_do_not_imply_played_time_availability():
    replay = TennisEloReplay([])
    assert replay.players == () and replay.matches_count == 0
    assert replay.rating(A, BEFORE) is None
    assert replay.probability(A, B, None, BEFORE) is None
    assert "0 matches, 0 players" in replay.audit_summary()
    assert "tournament-week dates" in replay.audit_summary()
    assert "do not prove pre-match availability" in replay.audit_summary()
